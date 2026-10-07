"""Workbook compatibility facade over canonical native handles."""

from datetime import datetime
from pathlib import Path
from weakref import WeakSet

from .._native import (
    NativeBook,
    NativeWriteBook,
    resolve_model_budget,
    save_models,
)
from ..resources import AutoMemory, ResourceOptions
from ..worksheet.worksheet import Worksheet


class Workbook:
    """Workbook-compatible entry point; models and package editing remain Rust-owned."""

    __slots__ = (
        "__weakref__",
        "_max_bytes",
        "_closed",
        "_reader",
        "_editor",
        "data_only",
        "read_only",
        "write_only",
        "_active",
        "_sheets",
        "_book",
        "_iso_dates",
        "_stream_writer",
        "_streams",
        "_saved",
    )

    def __init__(
        self,
        write_only=False,
        iso_dates=False,
        *,
        max_memory_bytes=None,
        temp_directory=None,
        auto_memory=None,
    ):
        if auto_memory is not None and not isinstance(auto_memory, AutoMemory):
            raise TypeError("auto_memory must be AutoMemory or None")
        native_resources = (
            ResourceOptions(auto_memory=auto_memory)._native(max_memory_bytes)
            if auto_memory is not None
            else None
        )
        self._max_bytes = resolve_model_budget(max_memory_bytes, native_resources)
        self._closed = False
        self._reader = self._editor = None
        self._iso_dates = bool(iso_dates)
        self.data_only = self.read_only = False
        self.write_only = bool(write_only)
        self._streams = WeakSet()
        self._saved = False
        self._stream_writer = (
            NativeWriteBook(
                self._max_bytes,
                bool(iso_dates),
                False,
                Path(temp_directory) if temp_directory is not None else None,
            )
            if write_only
            else None
        )
        self._active = 0
        self._sheets = []
        self._book = NativeBook(self._max_bytes)
        if not write_only:
            self.create_sheet("Sheet")

    def _style_owner(self):
        self._check_open()
        return self._reader or self._stream_writer or self._book

    @property
    def loaded_theme(self):
        return self._style_owner().theme()

    @loaded_theme.setter
    def loaded_theme(self, value):
        if value is not None and not isinstance(value, bytes):
            raise TypeError("Theme must be bytes or None")
        self._style_owner().set_theme(value)

    @property
    def named_styles(self):
        return self._style_owner().named_styles()

    def add_named_style(self, style):
        from ..styles import NamedStyle

        if not isinstance(style, NamedStyle):
            raise TypeError("Only NamedStyle instances can be registered")
        self._style_owner().add_named_style(style._native())
        style._bind(self)

    @property
    def model_memory_budget_bytes(self):
        """Resolved model allowance; loaded catalogs/overlays have separate budgets."""
        return self._max_bytes

    def _check_open(self):
        if self._closed:
            raise ValueError("Workbook is closed")

    @property
    def iso_dates(self):
        return self._iso_dates

    @iso_dates.setter
    def iso_dates(self, value):
        if self._reader is not None and value:
            raise NotImplementedError(
                "Changing loaded date storage requires loaded bank integration"
            )
        if self.write_only:
            self._stream_writer.configure(self._book.date_1904(), bool(value))
        self._iso_dates = bool(value)

    @property
    def epoch(self):
        self._check_open()
        mac = (
            self._reader.date_1904()
            if self._reader is not None
            else self._book.date_1904()
        )
        return datetime(1904, 1, 1) if mac else datetime(1899, 12, 30)

    @epoch.setter
    def epoch(self, value):
        if value not in (datetime(1899, 12, 30), datetime(1904, 1, 1)):
            raise ValueError("The epoch must be either 1900 or 1904")
        if self._reader is not None:
            raise NotImplementedError(
                "Changing a loaded workbook epoch is not implemented"
            )
        if self.write_only:
            self._stream_writer.configure(value == datetime(1904, 1, 1), self.iso_dates)
        self._book.set_date_1904(value == datetime(1904, 1, 1))

    @property
    def worksheets(self):
        return list(self._sheets)

    @property
    def sheetnames(self):
        return [sheet.title for sheet in self._sheets]

    @property
    def active(self):
        try:
            return self._sheets[self._active] if self._active is not None else None
        except IndexError:
            return None

    @active.setter
    def active(self, value):
        self._check_open()
        if isinstance(value, Worksheet) and value.sheet_state != "visible":
            raise ValueError("Only visible sheets can be made active")
        index = self._sheets.index(value) if isinstance(value, Worksheet) else value
        if not isinstance(index, int):
            raise TypeError("Active sheet must be a worksheet or integer index")
        if self._editor is not None:
            self._editor.set_active_view_index(index)
        elif self._book is not None and not self.write_only:
            self._book.set_active_view_index(index)
        self._active = index

    def __getitem__(self, key):
        for sheet in self._sheets:
            if sheet.title == key:
                return sheet
        raise KeyError(f"Worksheet {key} does not exist")

    def __contains__(self, key):
        return key in self.sheetnames

    def __iter__(self):
        return iter(self._sheets)

    def _unique_title(self, title, exclude=None):
        names = [sheet.title for sheet in self._sheets if sheet is not exclude]
        if title.lower() in {name.lower() for name in names}:
            suffixes = [
                name[len(title) :]
                for name in names
                if name.lower().startswith(title.lower())
            ]
            number = (
                max((int(suffix) for suffix in suffixes if suffix.isdigit()), default=0)
                + 1
            )
            title = f"{title}{number}"
        return title

    def create_sheet(self, title=None, index=None):
        self._check_open()
        if self.read_only:
            from ..utils.exceptions import ReadOnlyWorkbookException

            raise ReadOnlyWorkbookException(
                "Cannot create new sheet in a read-only workbook"
            )
        title = self._unique_title(title or "Sheet")
        Worksheet._validate_title(title)
        if index is not None and not isinstance(index, int):
            raise TypeError("Sheet position must be an integer")
        position = (
            len(self._sheets)
            if index is None
            else max(
                0,
                min(
                    len(self._sheets),
                    index if index >= 0 else len(self._sheets) + index,
                ),
            )
        )
        if self.write_only:
            from ..optimized import WriteOnlyWorksheet

            if position != len(self._sheets):
                raise NotImplementedError(
                    "Reordering streaming sheets is not implemented"
                )
            if self._saved:
                from ..utils.exceptions import WorkbookAlreadySaved

                raise WorkbookAlreadySaved("Workbook has already been saved")
            sheet = WriteOnlyWorksheet(
                self, title, self._stream_writer.create_sheet(title)
            )
            self._sheets.append(sheet)
            return sheet
        if self._editor is not None:
            native = self._editor.create_sheet(title)
            if position != len(self._sheets):
                self._editor.move_sheet(title, position)
            sheet = Worksheet(self, title, _existing=True, _native=native)
            self._sheets.insert(position, sheet)
            return sheet
        native = self._book.create_sheet(title)
        sheet = Worksheet(self, title, _native=native)
        if position != len(self._sheets):
            self._book.move_sheet(native, position)
        self._sheets.insert(position, sheet)
        return sheet

    def index(self, worksheet):
        return self._sheets.index(worksheet)

    def move_sheet(self, sheet, offset=0):
        if self.read_only or self.write_only:
            raise NotImplementedError(
                "Reordering optimized worksheets is not implemented"
            )
        if not isinstance(sheet, Worksheet):
            sheet = self[sheet]
        if not isinstance(offset, int):
            raise TypeError("Sheet offset must be an integer")
        old = self.index(sheet)
        remaining = len(self._sheets) - 1
        index = old + offset
        # Match list.insert after removing the source, including negative offsets.
        position = max(0, min(remaining, index if index >= 0 else remaining + index))
        if self._editor is not None:
            self._editor.move_sheet(sheet.title, position)
        else:
            self._book.move_sheet(sheet._native, position)
        self._sheets.pop(old)
        self._sheets.insert(position, sheet)

    def copy_worksheet(self, from_worksheet):
        if self.read_only or self.write_only:
            raise ValueError("Cannot copy worksheets in read-only or write-only mode")
        if (
            not isinstance(from_worksheet, Worksheet)
            or from_worksheet.parent is not self
        ):
            raise ValueError("Cannot copy between workbooks")
        self.index(from_worksheet)
        title = self._unique_title(from_worksheet.title + " Copy")
        Worksheet._validate_title(title)
        if self._editor is not None:
            native = self._editor.copy_sheet(from_worksheet.title, title)
            copied = Worksheet(self, title, _existing=True, _native=native)
            self._copy_rich_views(from_worksheet, copied)
            self._sheets.append(copied)
            return copied
        native = self._book.copy_sheet(from_worksheet._native, title)
        copied = Worksheet(self, title, _native=native)
        self._copy_rich_views(from_worksheet, copied)
        self._sheets.append(copied)
        return copied

    @staticmethod
    def _copy_rich_views(source, destination):
        for (row, column), value in list(source._rich_views.items()):
            # Copied cells share caller-visible value objects. Native values stay
            # independently owned and receive subsequent mutations through bindings.
            value._bind(destination, row, column)

    def remove(self, worksheet):
        if self.read_only or self.write_only:
            raise NotImplementedError(
                "Removing optimized worksheets is not implemented"
            )
        self._check_open()
        self.index(worksheet)
        if self._editor is not None:
            if worksheet._native is None:
                worksheet._native = self._editor.sheet_handle(worksheet.title)
            self._editor.remove_sheet(worksheet._native)
            worksheet._existing = False
        else:
            self._book.remove_sheet(worksheet._native)
        self._sheets.remove(worksheet)

    def __delitem__(self, key):
        self.remove(self[key])

    def save(self, filename, *, compression_level=None):
        self._check_open()
        if compression_level is not None:
            if isinstance(compression_level, bool) or not isinstance(
                compression_level, int
            ):
                raise TypeError("Compression level must be an integer or None")
            if not 0 <= compression_level <= 9:
                raise ValueError("Compression level must be between 0 and 9")
        if not isinstance(filename, (str, Path)):
            raise NotImplementedError("File-like binding output is not implemented")
        if self.read_only:
            raise TypeError("Workbook is read-only")
        hyperlink_sheets = []
        hyperlink_ids = []
        if not self.write_only:
            hyperlink_sheets = [
                sheet for sheet in self._sheets if sheet._hyperlink_views
            ]
            if hyperlink_sheets:
                requests = [
                    (
                        sheet._model(),
                        [
                            (row - 1, column - 1)
                            for row, column in sheet._hyperlink_views
                        ],
                    )
                    for sheet in hyperlink_sheets
                ]
                owner = self._editor if self._editor is not None else self._book
                hyperlink_ids = owner.hyperlink_output_ids(requests)
        if self.write_only:
            from ..utils.exceptions import WorkbookAlreadySaved

            if self._saved:
                raise WorkbookAlreadySaved("Workbook has already been saved")
            if not self._sheets:
                self.create_sheet()
            try:
                self._active = self._stream_writer.save(
                    Path(filename),
                    self._active if self._active is not None else 0,
                    compression_level,
                )
            finally:
                # Packaging consumes spools even if output fails; never imply retry.
                self._saved = True
                for sheet in self._sheets:
                    sheet._finished = True
        elif self._editor is not None:
            if self.data_only:
                raise NotImplementedError(
                    "Saving data-only loaded workbooks is not implemented"
                )
            self._active = self._editor.save(Path(filename), False, compression_level)
        else:
            self._active = save_models(
                Path(filename),
                [sheet._model() for sheet in self._sheets],
                self._active if self._active is not None else 0,
                self.iso_dates,
                self._book.date_1904(),
                compression_level,
                self._book,
            )
            self._book.set_active_view_index(self._active)
        for sheet, row, column, identity in hyperlink_ids:
            view = hyperlink_sheets[sheet]._hyperlink_views.get((row, column))
            if view is not None:
                object.__setattr__(view, "id", identity)

    def close(self):
        for stream in list(self._streams):
            stream.close()
        if self.write_only:
            self._stream_writer.close()
            self._closed = True
        if self._reader is not None:
            self._reader.close()
            if self._editor is not None:
                self._editor.close()
            self._closed = True
