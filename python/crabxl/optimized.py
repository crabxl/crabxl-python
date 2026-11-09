"""Optimized Python surfaces over bounded canonical Rust stream handles."""

from weakref import WeakValueDictionary

from . import Worksheet, _decode, _encode, _letters
from .chartsheet import Chartsheet
from .styles import Alignment, Border, Font, GradientFill, PatternFill, Protection
from .styles._base import StyleProxy
from .utils.exceptions import WorkbookAlreadySaved

_STYLE_COMPONENT_TYPES = {
    "font": Font,
    "fill": (PatternFill, GradientFill),
    "border": Border,
    "alignment": Alignment,
    "protection": Protection,
}


class EmptyCell:
    __slots__ = ()
    value = None
    internal_value = None
    data_type = "n"
    is_date = False
    has_style = False
    number_format = None
    font = None
    fill = None
    border = None
    alignment = None

    def __repr__(self):
        return "<EmptyCell>"


EMPTY_CELL = EmptyCell()


class ReadOnlyCell:
    __slots__ = ("parent", "row", "column", "_value", "_kind", "_style_id")

    def __init__(self, sheet, row, column, value, data_type="n", style_id=0):
        self.parent, self.row, self.column = sheet, row, column
        self._kind, self._value = data_type, value
        self._style_id = style_id

    @classmethod
    def _from_native(cls, worksheet, row, column, tagged, style_id):
        cell = cls.__new__(cls)
        cell.parent, cell.row, cell.column = worksheet, row, column
        cell._kind, cell._value = tagged[0], _decode(tagged)
        if cell._kind == "typed":
            cell._kind = tagged[1][0]
        cell._style_id = style_id
        return cell

    def __repr__(self):
        return f"<ReadOnlyCell {self.parent.title!r}.{self.coordinate}>"

    def __eq__(self, other):
        for name in ("parent", "row", "column", "_value", "data_type", "_style_id"):
            if getattr(self, name) != getattr(other, name):
                return None
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if self._value is not None:
            raise AttributeError("Cell is read only")
        self._value = value

    @property
    def internal_value(self):
        return self._value

    @property
    def data_type(self):
        return (
            "f"
            if self._kind in ("array", "table")
            else "d"
            if self._kind in ("d", "date", "datetime", "time", "duration")
            else "n"
            if self._kind == "bigint"
            else "s"
            if self._kind == "rich"
            else self._kind
        )

    @data_type.setter
    def data_type(self, value):
        self._kind = value

    @property
    def is_date(self):
        from .styles.numbers import is_date_format

        return self.data_type == "d" or (
            self.data_type == "n" and is_date_format(self.number_format)
        )

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
        workbook = self.parent.parent
        if hasattr(workbook, "_style_owner"):
            return workbook._style_owner().number_format(self._style_id)
        from .styles.numbers import BUILTIN_FORMATS, BUILTIN_FORMATS_MAX_SIZE

        number = self.style_array.numFmtId
        return (
            BUILTIN_FORMATS.get(number, "General")
            if number < BUILTIN_FORMATS_MAX_SIZE
            else workbook._number_formats[number - BUILTIN_FORMATS_MAX_SIZE]
        )

    @property
    def style_array(self):
        from .styles.cell_style import StyleArray

        workbook = self.parent.parent
        if hasattr(workbook, "_style_owner"):
            return StyleArray(workbook._style_owner().style_array(self._style_id))
        return workbook._cell_styles[self._style_id]

    def __getattr__(self, name):
        if name in ("font", "fill", "border", "alignment", "protection"):
            workbook = self.parent.parent
            if not hasattr(workbook, "_style_owner"):
                collections = {
                    "font": ("_fonts", "fontId"),
                    "fill": ("_fills", "fillId"),
                    "border": ("_borders", "borderId"),
                    "alignment": ("_alignments", "alignmentId"),
                    "protection": ("_protections", "protectionId"),
                }
                collection, key = collections[name]
                return getattr(workbook, collection)[getattr(self.style_array, key)]
            from .styles._base import StyleProxy, component

            return StyleProxy(
                component(
                    name,
                    self.parent.parent._style_owner().style_component(
                        self._style_id, name
                    ),
                )
            )
        raise AttributeError(name)


class ReadOnlyWorksheet(Worksheet):
    __slots__ = ("_dimension", "_sheet_state", "_min_row", "_min_column")

    def __init__(self, workbook, title):
        super().__init__(workbook, title, _existing=True)
        self._dimension = workbook._reader.dimension(title)
        self._min_row, self._min_column = (
            self._dimension[:2] if self._dimension else (1, 1)
        )
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
        return self._min_row

    @property
    def min_column(self):
        return self._min_column

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
            self._dimension = (
                self.min_row,
                self.min_column,
                max(rows, 1),
                max(columns, 1),
            )
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
                            else ReadOnlyCell._from_native(
                                self, index + 1, column, value, style
                            )
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
    __slots__ = (
        "parent",
        "_value",
        "_explicit_type",
        "row",
        "column",
        "_number_format",
        "_components",
        "_named_style",
        "_hyperlink",
        "_comment",
    )

    def __init__(self, ws=None, value=None):
        self.parent, self.row, self.column = ws, 1, 1
        self._number_format = None
        self._components = {}
        self._named_style = None
        self._hyperlink = None
        self._comment = None
        self.value = value

    @property
    def comment(self):
        return self._comment

    @comment.setter
    def comment(self, value):
        if value is not None:
            from copy import copy

            from .comments import Comment

            if not isinstance(value, Comment):
                raise TypeError("Comment must be a Comment or None")
            if value.parent is not None:
                value = copy(value)
            value.bind(self)
        if self._comment is not None:
            self._comment.unbind()
        self._comment = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if isinstance(value, bytes):
            value = value.decode(self.encoding)
        if isinstance(value, str):
            value = value[:32767]
        tagged = _encode(value)
        if tagged[0] in ("date", "datetime", "time", "duration"):
            from .cell.cell import get_time_format
            from .styles.numbers import is_date_format

            if not is_date_format(self.number_format):
                self.number_format = get_time_format(type(value))
        self._value = value
        self._explicit_type = None

    @property
    def internal_value(self):
        return self.value

    @property
    def encoding(self):
        return self.parent.parent.encoding

    @property
    def column_letter(self):
        return _letters(self.column)

    @property
    def is_date(self):
        from .styles.numbers import is_date_format

        return self.data_type == "d" or (
            self.data_type == "n" and is_date_format(self.number_format)
        )

    def _style_directives(self):
        result = {
            name: component._native() for name, component in self._components.items()
        }
        if self._named_style is not None:
            result["style_id"] = self._named_style[1]
        if self._number_format is not None:
            result["number_format"] = self._number_format
        return result

    @property
    def style_id(self):
        return self.parent.parent._stream_writer.prepare_cell_style(
            self._style_directives()
        )

    @property
    def has_style(self):
        return any(self.parent.parent._stream_writer.style_array(self.style_id))

    @property
    def hyperlink(self):
        return self._hyperlink

    @hyperlink.setter
    def hyperlink(self, value):
        from ._native import initial_hyperlink_value
        from .worksheet.hyperlink import Hyperlink

        if value is not None:
            if isinstance(value, str):
                value = Hyperlink(ref=self.coordinate, target=value)
            if not isinstance(value, Hyperlink):
                raise TypeError("Hyperlink must be a target string, Hyperlink, or None")
            value.ref = self.coordinate
            if self.value is None:
                self.value = _decode(initial_hyperlink_value(value._fields()))
        self._hyperlink = value

    @property
    def style(self):
        return self._named_style[0] if self._named_style is not None else "Normal"

    @style.setter
    def style(self, value):
        from .styles.named_styles import resolve_named_style

        workbook = self.parent.parent
        value = resolve_named_style(workbook, value)
        identity = workbook._stream_writer.named_style_format(value)
        self._named_style = (value, identity)
        self._number_format = None
        self._components.clear()

    @property
    def number_format(self):
        if self._number_format is not None:
            return self._number_format
        if self._named_style is not None:
            return self.parent.parent._stream_writer.number_format(self._named_style[1])
        return "General"

    @number_format.setter
    def number_format(self, code):
        if not isinstance(code, str):
            raise TypeError("Number format must be a string")
        self._number_format = code

    @property
    def data_type(self):
        from . import _data_type

        return (
            self._explicit_type
            if self._explicit_type is not None
            else _data_type(_encode(self.value))
        )

    @data_type.setter
    def data_type(self, value):
        self._explicit_type = value

    @property
    def coordinate(self):
        return f"{_letters(self.column)}{self.row}"

    def __getattr__(self, name):
        if name in ("font", "fill", "border", "alignment", "protection"):
            from ._native import default_style_component
            from .styles._base import StyleProxy, component

            value = self._components.get(name)
            if value is None:
                native = (
                    self.parent.parent._stream_writer.style_component(
                        self._named_style[1], name
                    )
                    if self._named_style is not None
                    else default_style_component(name)
                )
                value = component(name, native)
            return StyleProxy(value)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in ("font", "fill", "border", "alignment", "protection"):
            expected = _STYLE_COMPONENT_TYPES[name]
            if isinstance(value, StyleProxy):
                value = value._target
            if not isinstance(value, expected):
                raise TypeError(f"Invalid {name} component")
            self._components[name] = value
            return
        object.__setattr__(self, name, value)


class WriteOnlyWorksheet(Worksheet):
    __slots__ = ("_id", "_row", "_finished", "_sheet_state", "_drawings_prepared")

    def __init__(self, workbook, title, identifier):
        self.parent, self._title, self._id = workbook, title, identifier
        self._existing, self._native = False, None
        self._cells = WeakValueDictionary()
        self._row_dimensions = self._column_dimensions = None
        self._row, self._finished = 0, False
        self._images, self._charts = [], []
        self._new_pivots = []
        self._feat = self._names = self._print_rows = self._print_cols = None
        self._print_area = None
        self._drawings_prepared = False
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
        formats = None
        hyperlinks = None
        comments = None
        retained = 0
        allowance = min(self.parent._max_bytes, 1024 * 1024)
        for column, value in enumerate(iterable):
            if column >= 16384:
                raise ValueError("Row exceeds Excel column limits")
            explicit_type = None
            if isinstance(value, WriteOnlyCell):
                explicit_type = value._explicit_type
                value.row, value.column = self._row + 1, column + 1
                if value.comment is not None:
                    if comments is None:
                        comments = []
                    note = value.comment
                    comments.append(
                        (
                            self._row,
                            column,
                            note.author,
                            note.text,
                            note.width,
                            note.height,
                            False,
                        )
                    )
                    retained += (
                        128
                        + len(note.author.encode("utf-8"))
                        + len(note.text.encode("utf-8"))
                    )
                if value.hyperlink is not None:
                    if hyperlinks is None:
                        hyperlinks = []
                    hyperlinks.append((column, value.hyperlink))
                    retained += 256
                if (
                    value._number_format is not None
                    or value._components
                    or value._named_style is not None
                ):
                    if formats is None:
                        formats = []
                    directives = value._style_directives()
                    formats.append((column, directives))
                    retained += _style_payload_bytes(directives)
                value = value.value
            if isinstance(value, bytes):
                value = value.decode(self.parent.encoding)
            encoded = _encode(value)
            if explicit_type is not None:
                encoded = ("typed", (explicit_type, encoded))
            payload = encoded[1]
            retained += 128
            if isinstance(payload, str):
                retained += len(payload.encode("utf-8"))
            elif isinstance(payload, (dict, tuple)):
                retained += _style_payload_bytes(payload)
            if retained > allowance:
                raise MemoryError("Write-only row exceeds its byte allowance")
            tagged.append(encoded)
        if hyperlinks is None:
            self.parent._stream_writer.append(
                self._id, self._row, tagged, formats, comments=comments
            )
            self._row += 1
            return
        previous_refs = []
        groups = []
        try:
            for column, link in hyperlinks:
                previous_refs.append((link, link.ref))
                groups.append(
                    (
                        column,
                        link._bind_stream(
                            self, f"{_letters(column + 1)}{self._row + 1}"
                        ),
                    )
                )
            self.parent._stream_writer.append(
                self._id, self._row, tagged, formats, groups, comments
            )
        except BaseException:
            for link, previous in reversed(previous_refs):
                link.ref = previous
            raise
        self._row += 1

    def close(self):
        if not self._finished:
            self.parent._check_open()
            if not self._drawings_prepared and (
                self._images or self._charts or self._new_pivots
            ):
                self.parent._stream_writer.set_drawings(
                    self._id,
                    [image._native_input() for image in self._images],
                    [chart._native_input() for chart in self._charts],
                    self._pivot_inputs(),
                )
                self._drawings_prepared = True
            for index in self.parent._stream_writer.dimension_keys(self._id, True):
                if index >= self._row:
                    self.parent._stream_writer.remove_dimension(self._id, True, index)
            groups = [
                group
                for group, link in self.parent._stream_links.items()
                if link._stream_bindings.get(self) == group
            ]
            identities = self.parent._stream_writer.close_sheet(self._id, groups)
            for group, identity in identities:
                link = self.parent._stream_links.get(group)
                if link is not None:
                    object.__setattr__(link, "id", identity)
            self._finished = True

    def insert_rows(self, *args, **kwargs):
        raise NotImplementedError(
            "Structural edits of flushed worksheets are not implemented"
        )

    insert_cols = delete_rows = delete_cols = move_range = insert_rows


class WriteOnlyChartsheet(Chartsheet, WriteOnlyWorksheet):
    __slots__ = ()

    def add_image(self, img, anchor=None):
        raise TypeError("A streaming chartsheet accepts charts")

    def close(self):
        if not self._finished:
            self.parent._check_open()
            self.parent._stream_writer.close_chartsheet(
                self._id,
                [chart._native_input() for chart in self._charts],
                self._chartsheet_xml(),
            )
            self._finished = True


def _style_payload_bytes(value):
    if hasattr(value, "retained_bytes"):
        return value.retained_bytes
    if isinstance(value, str):
        return len(value.encode("utf-8")) + 64
    if isinstance(value, dict):
        return 128 + sum(
            _style_payload_bytes(k) + _style_payload_bytes(v) for k, v in value.items()
        )
    if isinstance(value, (list, tuple)):
        return 64 + sum(_style_payload_bytes(v) for v in value)
    return 32
