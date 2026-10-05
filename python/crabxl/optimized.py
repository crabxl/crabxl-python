"""Optimized Python surfaces over bounded canonical Rust stream handles."""

from weakref import WeakValueDictionary

from . import Worksheet, _decode, _encode, _letters
from .utils.exceptions import WorkbookAlreadySaved


class EmptyCell:
    __slots__ = ()
    value = None
    internal_value = None
    data_type = "n"
    is_date = False
    has_style = False
    number_format = None


EMPTY_CELL = EmptyCell()


class ReadOnlyCell:
    __slots__ = ("parent", "row", "column", "_value", "_kind", "_style_id")

    def __init__(self, worksheet, row, column, tagged, style_id=0):
        self.parent, self.row, self.column = worksheet, row, column
        self._kind, self._value = tagged[0], _decode(tagged)
        self._style_id = style_id

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        raise AttributeError("Cell is read only")

    @property
    def internal_value(self):
        return self._value

    @property
    def data_type(self):
        return (
            "f"
            if self._kind in ("array", "table")
            else "d"
            if self.is_date
            else "n"
            if self._kind == "bigint"
            else self._kind
        )

    @property
    def is_date(self):
        return self._kind in ("date", "datetime", "time", "duration")

    @property
    def coordinate(self):
        return f"{_letters(self.column)}{self.row}"

    @property
    def column_letter(self):
        return _letters(self.column)

    @property
    def has_style(self):
        return self._style_id != 0

    @property
    def number_format(self):
        return self.parent.parent._reader.number_format(self._style_id)

    @property
    def style_array(self):
        raise NotImplementedError("Full read-only style arrays are not implemented")

    def __getattr__(self, name):
        if name in ("font", "fill", "border", "alignment", "protection"):
            raise NotImplementedError(f"Read-only {name} objects are not implemented")
        raise AttributeError(name)


class ReadOnlyWorksheet(Worksheet):
    __slots__ = ("_dimension", "_sheet_state")

    def __init__(self, workbook, title):
        super().__init__(workbook, title, _existing=True)
        self._dimension = workbook._reader.dimension(title)
        self._sheet_state = workbook._reader.sheet_state(title)

    @property
    def sheet_state(self):
        return self._sheet_state

    @sheet_state.setter
    def sheet_state(self, state):
        # Read-only metadata is a view; this mode cannot serialize a workbook.
        self._sheet_state = state

    def _model(self):
        raise NotImplementedError("Read-only worksheets do not have editable models")

    def _set(self, row, column, value):
        raise TypeError("Read-only worksheets cannot be modified")

    @property
    def min_row(self):
        return self._dimension[0] if self._dimension else None

    @property
    def min_column(self):
        return self._dimension[1] if self._dimension else None

    @property
    def max_row(self):
        return self._dimension[2] if self._dimension else None

    @property
    def max_column(self):
        return self._dimension[3] if self._dimension else None

    def reset_dimensions(self):
        self._dimension = None

    def calculate_dimension(self, force=False):
        if self._dimension is None:
            if not force:
                raise ValueError(
                    "Worksheet is unsized, use calculate_dimension(force=True)"
                )
            rows = columns = 0
            for row in self.iter_rows(values_only=True):
                rows += 1
                columns = max(columns, len(row))
            self._dimension = (1, 1, max(rows, 1), max(columns, 1))
        first_row, first_column, last_row, last_column = self._dimension
        return f"{_letters(first_column)}{first_row}:{_letters(last_column)}{last_row}"

    def cell(self, row, column, value=None):
        if value is not None:
            raise AttributeError("Cell is read only")
        rows = self.iter_rows(min_row=row, max_row=row, min_col=column, max_col=column)
        try:
            return next(rows)[0]
        finally:
            rows.close()

    def iter_rows(
        self, min_row=None, max_row=None, min_col=None, max_col=None, values_only=False
    ):
        self.parent._check_open()
        min_row, min_col = min_row or 1, min_col or 1
        max_row = self.max_row if max_row is None else max_row
        max_col = self.max_column if max_col is None else max_col
        for value, maximum in (
            (min_row, 1048576),
            (min_col, 16384),
            (max_row, 1048576),
            (max_col, 16384),
        ):
            if value is not None and (
                not isinstance(value, int) or not 1 <= value <= maximum
            ):
                raise ValueError("Row or column values must be within Excel bounds")
        if (max_row is not None and max_row < min_row) or (
            max_col is not None and max_col < min_col
        ):
            return iter(())

        def rows():
            self.parent._check_open()
            stream = self.parent._reader.stream(
                self.title,
                self.parent.data_only,
                min_row - 1,
                max_row - 1 if max_row else None,
                min_col - 1,
                max_col - 1 if max_col else None,
            )
            self.parent._streams.add(stream)
            expected = min_row
            try:
                while True:
                    self.parent._check_open()
                    native = (
                        stream.next_values_row()
                        if values_only
                        else stream.next_row(True)
                    )
                    if native is None:
                        break
                    if values_only:
                        index, tagged = native
                        styles = ()
                    else:
                        index, tagged, styles = native
                    width = (
                        max(0, max_col - min_col + 1)
                        if max_col is not None
                        else len(tagged)
                    )
                    empty = (None if values_only else EMPTY_CELL,) * width
                    while expected < index + 1:
                        yield empty
                        expected += 1
                    if values_only:
                        yield tuple(tagged)
                    else:
                        yield tuple(
                            EMPTY_CELL
                            if style is None
                            else ReadOnlyCell(self, index + 1, column, value, style)
                            for column, value, style in zip(
                                range(min_col, min_col + len(tagged)), tagged, styles
                            )
                        )
                    expected = index + 2
                if max_row is not None:
                    empty = (None if values_only else EMPTY_CELL,) * max(
                        0, (max_col or min_col) - min_col + 1
                    )
                    while expected <= max_row:
                        yield empty
                        expected += 1
            finally:
                stream.close()
                self.parent._streams.discard(stream)

        return rows()

    def iter_cols(self, *args, **kwargs):
        raise NotImplementedError("Column-wise read-only iteration is not implemented")

    def append(self, iterable):
        raise TypeError("Read-only worksheets cannot be modified")

    def insert_rows(self, *args, **kwargs):
        raise TypeError("Read-only worksheets cannot be modified")

    insert_cols = delete_rows = delete_cols = move_range = insert_rows


class WriteOnlyCell:
    __slots__ = ("parent", "value", "row", "column")

    def __init__(self, ws=None, value=None):
        self.parent, self.value, self.row, self.column = ws, value, 1, 1

    @property
    def data_type(self):
        from . import _data_type

        return _data_type(_encode(self.value))

    @property
    def coordinate(self):
        return f"{_letters(self.column)}{self.row}"

    def __setattr__(self, name, value):
        if name in (
            "font",
            "fill",
            "border",
            "alignment",
            "protection",
            "number_format",
            "hyperlink",
            "comment",
        ):
            raise NotImplementedError(f"Write-only {name} is not implemented")
        object.__setattr__(self, name, value)


class WriteOnlyWorksheet(Worksheet):
    __slots__ = ("_id", "_row", "_finished", "_sheet_state")

    def __init__(self, workbook, title, identifier):
        self.parent, self._title, self._id = workbook, title, identifier
        self._existing, self._native = False, None
        self._cells = WeakValueDictionary()
        self._row, self._finished = 0, False
        self._sheet_state = "visible"

    @property
    def sheet_state(self):
        return self._sheet_state

    @sheet_state.setter
    def sheet_state(self, state):
        self.parent._check_open()
        self.parent._stream_writer.set_sheet_state(self._id, state)
        self._sheet_state = state

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, title):
        self.parent._check_open()
        self._validate_title(title)
        title = self.parent._unique_title(title, exclude=self)
        self.parent._stream_writer.rename_sheet(self._id, title)
        self._title = title

    @property
    def closed(self):
        return self._finished

    def _model(self):
        raise NotImplementedError("Write-only worksheets do not have editable models")

    def cell(self, *args, **kwargs):
        raise NotImplementedError(
            "Random access is unavailable on write-only worksheets"
        )

    def iter_rows(self, *args, **kwargs):
        raise NotImplementedError("Reading write-only worksheets is not implemented")

    iter_cols = iter_rows

    def append(self, iterable):
        self.parent._check_open()
        if self._finished or self.parent._saved:
            raise WorkbookAlreadySaved("You cannot add cells to a closed worksheet")
        if isinstance(iterable, (str, bytes, dict)):
            raise TypeError("Write-only append requires a row iterable")
        tagged = []
        retained = 0
        allowance = min(self.parent._max_bytes, 1024 * 1024)
        for column, value in enumerate(iterable):
            if column >= 16384:
                raise ValueError("Row exceeds Excel column limits")
            if isinstance(value, WriteOnlyCell):
                value = value.value
            encoded = _encode(value)
            payload = encoded[1]
            retained += 128
            if isinstance(payload, str):
                retained += len(payload.encode("utf-8"))
            elif isinstance(payload, dict):
                retained += sum(
                    len(item.encode("utf-8"))
                    for item in payload.values()
                    if isinstance(item, str)
                )
            if retained > allowance:
                raise MemoryError("Write-only row exceeds its byte allowance")
            tagged.append(encoded)
        self.parent._stream_writer.append(self._id, self._row, tagged)
        self._row += 1

    def close(self):
        if not self._finished:
            self.parent._check_open()
            self.parent._stream_writer.close_sheet(self._id)
            self._finished = True

    def insert_rows(self, *args, **kwargs):
        raise NotImplementedError(
            "Structural edits of flushed worksheets are not implemented"
        )

    insert_cols = delete_rows = delete_cols = move_range = insert_rows
