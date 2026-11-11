"""Workbook compatibility facade over canonical native handles."""

import sys
from datetime import datetime
from os import PathLike
from pathlib import Path
from weakref import WeakSet, WeakValueDictionary

from .._native import (
    NativeBook,
    NativeWriteBook,
    resolve_model_budget,
    save_models,
)
from ..compat import deprecated
from ..resources import AutoMemory, ResourceOptions
from ..worksheet.worksheet import Worksheet

INTEGER_TYPES = (int,)


_CHARTSHEET_MODULE = __name__.rsplit(".", 2)[0] + ".chartsheet.chartsheet"


def _is_chartsheet(sheet):
    # Without the chartsheet module loaded, no sheet can be a chartsheet. This
    # keeps the drawing and XML modules out of plain reads.
    module = sys.modules.get(_CHARTSHEET_MODULE)
    return module is not None and isinstance(sheet, module.Chartsheet)


class Workbook:
    """Workbook-compatible entry point; models and package editing remain Rust-owned."""

    __slots__ = (
        "__weakref__",
        "_max_bytes",
        "_closed",
        "_reader",
        "_editor",
        "data_only",
        "encoding",
        "read_only",
        "write_only",
        "_active",
        "_sheets",
        "_book",
        "_iso_dates",
        "_stream_writer",
        "_streams",
        "_saved",
        "_stream_links",
        "_wfeat",
        "_template",
        "_keep_vba",
        "_input_spool",
        "is_template",
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
        self.encoding = "utf-8"
        self._wfeat = None
        self._template = self._keep_vba = self.is_template = False
        self._reader = self._editor = None
        self._input_spool = None
        self._iso_dates = bool(iso_dates)
        self.data_only = self.read_only = False
        self.write_only = bool(write_only)
        self._streams = WeakSet()
        self._saved = False
        self._stream_links = WeakValueDictionary()
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

    def _wstate(self):
        state = self._wfeat
        if state is None:
            self._check_open()
            from .._features import WorkbookState

            state = self._wfeat = WorkbookState(self)
        return state

    def _names_state(self):
        state = self._wstate()
        if not state.bound:
            state.build(self)
        return state

    def _wobj(self, key):
        return self._names_state().objs[key]

    @property
    def code_name(self):
        return self._wobj("workbook_properties").codeName

    @code_name.setter
    def code_name(self, value):
        self._wobj("workbook_properties").codeName = value

    @property
    def views(self):
        return self._wobj("views")

    @views.setter
    def views(self, value):
        from .views import BookView

        if not isinstance(value, (list, tuple)) or any(
            not isinstance(view, BookView) for view in value
        ):
            raise TypeError("Expected a sequence of BookView objects")
        self._names_state().objs["views"] = value

    @property
    def calculation(self):
        return self._wobj("calculation")

    @calculation.setter
    def calculation(self, value):
        from .properties import CalcProperties

        if value is not None and not isinstance(value, CalcProperties):
            raise TypeError("Expected CalcProperties or None")
        self._names_state().objs["calculation"] = value

    @property
    def defined_names(self):
        return self._wobj("names")

    @defined_names.setter
    def defined_names(self, value):
        self._names_state().objs["names"] = value

    @property
    def security(self):
        return self._wobj("security")

    @security.setter
    def security(self, value):
        self._names_state().objs["security"] = value

    @property
    def properties(self):
        return self._wobj("properties")

    @properties.setter
    def properties(self, value):
        self._names_state().objs["properties"] = value

    @property
    def custom_doc_props(self):
        return self._wobj("custom")

    @custom_doc_props.setter
    def custom_doc_props(self, value):
        self._names_state().objs["custom"] = value

    def _duplicate_name(self, name):
        """Check defined names and the tables of each worksheet (case-insensitive)."""
        name = name.lower()
        for sheet in self.worksheets:
            for table in sheet.tables:
                if name == table.lower():
                    return True
        return name in {key.lower() for key in self.defined_names}

    def _flush_features(self):
        if self.read_only:
            return
        if self.write_only:
            if self._wfeat is not None:
                self._wfeat.push(self)
            return
        for sheet in self._sheets:
            sheet._flush_features()
        if self._wfeat is None and self._editor is None:
            # New workbook: openpyxl's default properties, set natively so that
            # saving does not load the property classes.
            from datetime import datetime, timezone

            from .._native import workbook_default_properties

            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            workbook_default_properties(self._book, now)
        if self._wfeat is not None:
            self._wfeat.push(self)

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
    def _fonts(self):
        from ..styles._collections import StyleCollection

        return StyleCollection(self, "font")

    @property
    def _fills(self):
        from ..styles._collections import StyleCollection

        return StyleCollection(self, "fill")

    @property
    def _borders(self):
        from ..styles._collections import StyleCollection

        return StyleCollection(self, "border")

    @property
    def _alignments(self):
        from ..styles._collections import StyleCollection

        return StyleCollection(self, "alignment")

    @property
    def _protections(self):
        from ..styles._collections import StyleCollection

        return StyleCollection(self, "protection")

    @property
    def _number_formats(self):
        from ..styles._collections import StyleCollection

        return StyleCollection(self, "number_format")

    @property
    def _named_styles(self):
        from ..styles._collections import NamedStyleCollection

        return NamedStyleCollection(self)

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
    def template(self):
        return self._template

    @template.setter
    def template(self, value):
        self._check_open()
        value = bool(value)
        if value != self._template and self._editor is not None:
            self._editor.set_template(value, self._keep_vba)
        self._template = value

    @property
    def vba_archive(self):
        # VBA parts stay in the Rust package model; there is no separate ZipFile.
        return True if self._keep_vba else None

    @vba_archive.setter
    def vba_archive(self, value):
        self._check_open()
        keep = bool(value)
        if keep == self._keep_vba:
            return
        if self._editor is not None:
            self._editor.set_vba(keep)
        self._keep_vba = keep

    @property
    def mime_type(self):
        from ..xml.constants import XLSM, XLSX, XLTM, XLTX

        if self.template:
            return XLTM if self._keep_vba else XLTX
        return XLSM if self._keep_vba else XLSX

    @property
    def iso_dates(self):
        return self._iso_dates

    @iso_dates.setter
    def iso_dates(self, value):
        value = bool(value)
        if self._editor is not None and value != self._iso_dates:
            self._iso_dates = value
            self._rewrite_dates(
                lambda: self._editor.set_date_options(self._reader.date_1904(), value)
            )
            return
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
        mac = value == datetime(1904, 1, 1)
        if self._reader is not None:
            if self._editor is None:
                # Read-only: later reads use the new epoch, as in openpyxl.
                self._reader.set_date_1904(mac)
            elif mac != self._reader.date_1904():
                self._rewrite_dates(
                    lambda: self._editor.set_date_options(mac, self._iso_dates)
                )
            return
        if self.write_only:
            self._stream_writer.configure(value == datetime(1904, 1, 1), self.iso_dates)
        self._book.set_date_1904(value == datetime(1904, 1, 1))

    def _rewrite_dates(self, change):
        # openpyxl keeps dates as datetime values and encodes them on save, so a
        # new epoch or ISO setting applies to every date cell. Read them first.
        from datetime import date, time, timedelta

        cells = [
            (cell, cell.value)
            for sheet in self.worksheets
            for row in sheet.iter_rows()
            for cell in row
            if isinstance(cell.value, (date, time, timedelta))
        ]
        change()
        for cell, value in cells:
            cell.value = value

    @property
    def worksheets(self):
        return [sheet for sheet in self._sheets if not _is_chartsheet(sheet)]

    @property
    def chartsheets(self):
        return [sheet for sheet in self._sheets if _is_chartsheet(sheet)]

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
        raise KeyError(f"Worksheet {key} does not exist.")

    def __contains__(self, key):
        return key in self.sheetnames

    def __iter__(self):
        return iter(self.worksheets)

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
        return self._create_sheet(title, index, chartsheet=False)

    def create_chartsheet(self, title=None, index=None):
        return self._create_sheet(title, index, chartsheet=True)

    def _create_sheet(self, title, index, *, chartsheet):
        self._check_open()
        if self.read_only:
            from ..utils.exceptions import ReadOnlyWorkbookException

            raise ReadOnlyWorkbookException(
                "Cannot create new sheet in a read-only workbook"
            )
        sheet_type = Worksheet
        if chartsheet:
            from ..chartsheet import Chartsheet

            sheet_type = Chartsheet
        title = self._unique_title(title or ("Chart" if chartsheet else "Sheet"))
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
            from ..optimized import WriteOnlyChartsheet, WriteOnlyWorksheet

            if self._saved:
                from ..utils.exceptions import WorkbookAlreadySaved

                raise WorkbookAlreadySaved("Workbook has already been saved")
            sheet_type = WriteOnlyChartsheet if chartsheet else WriteOnlyWorksheet
            sheet = sheet_type(self, title, self._stream_writer.create_sheet(title))
            if position != len(self._sheets):
                self._stream_writer.move_sheet(sheet._id, position)
            self._sheets.insert(position, sheet)
            return sheet
        if self._editor is not None:
            native = self._editor.create_sheet(title, chartsheet)
            if position != len(self._sheets):
                self._editor.move_sheet(title, position)
            sheet = sheet_type(self, title, _existing=True, _native=native)
            self._sheets.insert(position, sheet)
            return sheet
        native = self._book.create_sheet(title, chartsheet)
        sheet = sheet_type(self, title, _native=native)
        if position != len(self._sheets):
            self._book.move_sheet(native, position)
        self._sheets.insert(position, sheet)
        return sheet

    def index(self, worksheet):
        return self._sheets.index(worksheet)

    def move_sheet(self, sheet, offset=0):
        if not isinstance(sheet, Worksheet):
            sheet = self[sheet]
        if not isinstance(offset, int):
            raise TypeError("Sheet offset must be an integer")
        old = self.index(sheet)
        remaining = len(self._sheets) - 1
        index = old + offset
        # Match list.insert after removing the source, including negative offsets.
        position = max(0, min(remaining, index if index >= 0 else remaining + index))
        if self.write_only:
            self._stream_writer.move_sheet(sheet._id, position)
        elif self._editor is not None:
            self._editor.move_sheet(sheet.title, position)
        elif not self.read_only:
            self._book.move_sheet(sheet._native, position)
        self._sheets.pop(old)
        self._sheets.insert(position, sheet)

    def copy_worksheet(self, from_worksheet):
        from ..chartsheet import Chartsheet

        if self.read_only or self.write_only:
            raise ValueError("Cannot copy worksheets in read-only or write-only mode")
        if (
            not isinstance(from_worksheet, Worksheet)
            or isinstance(from_worksheet, Chartsheet)
            or from_worksheet.parent is not self
        ):
            raise ValueError("Cannot copy between workbooks")
        self.index(from_worksheet)
        from_worksheet._flush_features()
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
        self._check_open()
        self.index(worksheet)
        if self.write_only:
            self._stream_writer.remove_sheet(worksheet._id)
            worksheet._finished = True
        elif self.read_only:
            pass
        elif self._editor is not None:
            if worksheet._native is None:
                worksheet._native = self._editor.sheet_handle(worksheet.title)
            self._editor.remove_sheet(worksheet._native)
            worksheet._existing = False
        else:
            self._book.remove_sheet(worksheet._native)
        self._sheets.remove(worksheet)

    def __delitem__(self, key):
        self.remove(self[key])

    path = "/xl/workbook.xml"

    @property
    def excel_base_date(self):
        return self.epoch

    @property
    def style_names(self):
        return list(self.named_styles)

    @deprecated("Use wb.remove(worksheet) or del wb[sheetname]")
    def remove_sheet(self, worksheet):
        self.remove(worksheet)

    @deprecated("Use wb[sheetname]")
    def get_sheet_by_name(self, name):
        return self[name]

    @deprecated("Use wb.index(worksheet)")
    def get_index(self, worksheet):
        return self.index(worksheet)

    @deprecated("Use wb.sheetnames")
    def get_sheet_names(self):
        return self.sheetnames

    @deprecated(
        "Assign scoped named ranges directly to worksheets or global ones to the workbook. Deprecated in 3.1"
    )
    def create_named_range(self, name, worksheet=None, value=None, scope=None):
        from ..utils import quote_sheetname
        from .defined_name import DefinedName

        defn = DefinedName(name=name)
        if worksheet is not None:
            defn.value = f"{quote_sheetname(worksheet.title)}!{value}"
        else:
            defn.value = value
        self.defined_names[name] = defn

    def save(self, filename, *, compression_level=None, calculate=False):
        """Save the workbook. With ``calculate=True``, every formula is
        calculated first and its result is saved as the cached value, so
        readers that do not calculate formulas see current results."""
        self._check_open()
        if compression_level is not None:
            if isinstance(compression_level, bool) or not isinstance(
                compression_level, int
            ):
                raise TypeError("Compression level must be an integer or None")
            if not 0 <= compression_level <= 9:
                raise ValueError("Compression level must be between 0 and 9")
        if self.read_only:
            raise TypeError("Workbook is read-only")
        if calculate and self.write_only:
            raise ValueError("Write-only workbooks cannot calculate formulas")
        if not isinstance(filename, (str, PathLike)):
            if not callable(getattr(filename, "write", None)):
                raise TypeError("Expected a path or writable binary stream")
            from tempfile import TemporaryDirectory

            with TemporaryDirectory(prefix="crabxl-output-") as directory:
                path = Path(directory) / "workbook.xlsx"
                self.save(
                    path, compression_level=compression_level, calculate=calculate
                )
                with path.open("rb") as source:
                    while chunk := source.read(1024 * 1024):
                        written = filename.write(chunk)
                        if written is not None and written != len(chunk):
                            raise OSError(
                                "Workbook stream did not accept a complete write"
                            )
                if getattr(filename, "seekable", lambda: False)():
                    filename.truncate()
                flush = getattr(filename, "flush", None)
                if flush is not None:
                    flush()
            return
        if self.write_only and not self._sheets:
            self.create_sheet()
        self._flush_features()
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
            for sheet in self._sheets:
                if not sheet.closed:
                    sheet.close()
            try:
                self._active, identities = self._stream_writer.save(
                    Path(filename),
                    self._active if self._active is not None else 0,
                    compression_level,
                    list(self._stream_links),
                    template=self.template,
                )
                owners = {}
                observed = {}
                for link in self._stream_links.values():
                    observed[id(link)] = link
                for link in observed.values():
                    for sheet, group in link._stream_bindings.items():
                        owners[group] = sheet._id
                for group, identity in sorted(
                    identities, key=lambda item: owners.get(item[0], -1)
                ):
                    link = self._stream_links.get(group)
                    if link is not None:
                        object.__setattr__(link, "id", identity)
            finally:
                # Packaging consumes spools even if output fails; never imply retry.
                self._saved = True
                for sheet in self._sheets:
                    sheet._finished = True
        elif self._editor is not None:
            self._active = self._editor.save(
                Path(filename), False, compression_level, calculate
            )
        else:
            self._book.set_template(self.template)
            self._active = save_models(
                Path(filename),
                [sheet._model() for sheet in self._sheets],
                self._active if self._active is not None else 0,
                self.iso_dates,
                self._book.date_1904(),
                compression_level,
                self._book,
                calculate,
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
        if self._input_spool is not None:
            self._input_spool.cleanup()
            self._input_spool = None
