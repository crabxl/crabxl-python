"""Worksheet compatibility facade over canonical native handles."""

import re
from weakref import WeakValueDictionary

from .._native import (
    NativeSheet,
)
from .._values import _ADDRESS, _address, _column, _encode, _letters, _range
from ..cell.cell import Cell, MergedCell


class Worksheet:
    """Sparse worksheet using the same public call conventions as openpyxl."""

    SHEETSTATE_VISIBLE = "visible"
    SHEETSTATE_HIDDEN = "hidden"
    SHEETSTATE_VERYHIDDEN = "veryHidden"

    __slots__ = (
        "parent",
        "_title",
        "_existing",
        "_native",
        "_cells",
        "_row_dimensions",
        "_column_dimensions",
        "_merged_cells",
        "__weakref__",
    )

    def __init__(self, parent, title=None, *, _existing=False, _native=None):
        self.parent = parent
        self._title = (
            (title or "Sheet") if _existing else parent._unique_title(title or "Sheet")
        )
        self._existing = _existing
        self._native = (
            _native
            if _native is not None
            else None
            if _existing
            else NativeSheet(self._title, parent._max_bytes)
        )
        self._cells = WeakValueDictionary()
        self._row_dimensions = self._column_dimensions = None
        self._merged_cells = None
        self._validate_title(self._title)

    @property
    def row_dimensions(self):
        from ..worksheet.dimensions import DimensionHolder

        if self._row_dimensions is None:
            self._row_dimensions = DimensionHolder(self, rows=True)
        return self._row_dimensions

    @property
    def column_dimensions(self):
        from ..worksheet.dimensions import DimensionHolder

        if self._column_dimensions is None:
            self._column_dimensions = DimensionHolder(self)
        return self._column_dimensions

    @property
    def merged_cells(self):
        from .merge import MultiCellRange

        if self._merged_cells is None:
            self._merged_cells = MultiCellRange(self)
        return self._merged_cells

    def merge_cells(
        self,
        range_string=None,
        start_row=None,
        start_column=None,
        end_row=None,
        end_column=None,
    ):
        self._merge_cells(
            range_string, start_row, start_column, end_row, end_column, True
        )

    def unmerge_cells(
        self,
        range_string=None,
        start_row=None,
        start_column=None,
        end_row=None,
        end_column=None,
    ):
        self._merge_cells(
            range_string, start_row, start_column, end_row, end_column, False
        )

    def _merge_cells(
        self, range_string, start_row, start_column, end_row, end_column, merge
    ):
        if range_string is not None:
            bounds = _range(str(range_string))
        elif all(
            value is not None
            for value in (start_row, start_column, end_row, end_column)
        ):
            bounds = _range(
                f"{_letters(start_column)}{start_row}:{_letters(end_column)}{end_row}"
            )
        else:
            raise ValueError("A range or all four row/column bounds are required")
        first_row, first_col, last_row, last_col = bounds
        aliases = [
            (key, cell, cell._snapshot())
            for key, cell in list(self._cells.items())
            if key != (first_row, first_col)
            and first_row <= key[0] <= last_row
            and first_col <= key[1] <= last_col
        ]
        self._model().merge_cells(*(value - 1 for value in bounds), merge)
        for key, cell, snapshot in aliases:
            cell._detached = snapshot
            self._cells.pop(key, None)

    @staticmethod
    def _validate_title(title):
        if not isinstance(title, str) or not title:
            raise ValueError("Title must have at least one character")
        if re.search(r"[\\*?:/\[\]]", title):
            raise ValueError("Invalid character in sheet title")
        if len(title) > 31:
            raise NotImplementedError(
                "Titles longer than 31 characters are not implemented"
            )

    @property
    def title(self):
        return self._title

    @property
    def sheet_state(self):
        self.parent._check_open()
        if self._existing:
            return self.parent._reader.sheet_state(self.title)
        return self._native.sheet_state()

    @sheet_state.setter
    def sheet_state(self, state):
        self.parent._check_open()
        if self._existing:
            self.parent._editor.set_sheet_state(self.title, state, self.parent._active)
        else:
            self._native.set_sheet_state(state)

    @title.setter
    def title(self, title):
        self._validate_title(title)
        self.parent._check_open()
        if title != self._title:
            title = self.parent._unique_title(title, exclude=self)
            if self._existing:
                self.parent._editor.rename_sheet(self._title, title)
            else:
                self._native.rename(title)
            self._title = title

    def _model(self):
        self.parent._check_open()
        if self._native is None:
            self._native = self.parent._reader.load_sheet(
                self.title, self.parent._max_bytes, self.parent.data_only
            )
        return self._native

    def _get(self, row, column):
        self.parent._check_open()
        if self._existing:
            value = self.parent._editor.pending(self.title, row - 1, column - 1)
            if value is not None:
                return value
        return self._model().get(row - 1, column - 1)

    def _set(self, row, column, value):
        self.parent._check_open()
        tagged = _encode(value)
        if self._existing:
            self.parent._editor.set(self.title, row - 1, column - 1, tagged)
        else:
            self._native.set(row - 1, column - 1, tagged)

    def cell(self, row, column, value=None):
        if (
            not isinstance(row, int)
            or not isinstance(column, int)
            or not 1 <= row <= 1048576
            or not 1 <= column <= 16384
        ):
            raise ValueError("Row or column values must be within Excel bounds")
        key = row, column
        cell = self._cells.get(key)
        if cell is None:
            pending = (
                self.parent._editor.pending(self.title, row - 1, column - 1)
                if self._existing and self._native is None
                else None
            )
            present, merged = (
                (True, False)
                if pending is not None
                else self._model().cell_state(row - 1, column - 1)
            )
            cell = (MergedCell if merged else Cell)(self, row, column)
            self._cells[key] = cell
            if not self._existing and not present and not merged:
                self._native.set(row - 1, column - 1, ("empty", None))
        if value is not None:
            cell.value = value
        return cell

    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.iter_rows(min_row=key, max_row=key))[0]
        if isinstance(key, str) and ":" not in key and _ADDRESS.fullmatch(key):
            return self.cell(*_address(key))
        if isinstance(key, str) and key.isalpha():
            column = _column(key)
            return tuple(self.iter_cols(min_col=column, max_col=column))[0]
        if isinstance(key, str) and ":" in key:
            first, last = key.split(":", 1)
            if first.isdigit() and last.isdigit():
                return tuple(self.iter_rows(min_row=int(first), max_row=int(last)))
            if first.isalpha() and last.isalpha():
                return tuple(
                    self.iter_cols(min_col=_column(first), max_col=_column(last))
                )
            row, col, end_row, end_col = _range(key)
            return tuple(self.iter_rows(row, end_row, col, end_col))
        raise ValueError(f"{key} is not a valid coordinate or range")

    def __setitem__(self, key, value):
        row, column = _address(key)
        if self._existing and self._native is None:
            # Preserve bounded source overlays without forcing full-sheet loading.
            # The preserving core validates deferred affected graphs on save.
            self._set(row, column, value)
        else:
            self.cell(row, column).value = value

    def __delitem__(self, key):
        self.parent._check_open()
        row, column = _address(key)
        cell = self._cells.get((row, column))
        if self._native is None and self._existing:
            self._native = self.parent._editor.sheet_handle(self.title)
        style = cell._snapshot()[2:] if cell is not None else None
        old = self._model().remove(row - 1, column - 1, cell is not None)
        if cell is not None:
            self._cells.pop((row, column), None)
            cell._detached = (*(old if old is not None else ("n", None)), *style)

    @property
    def _current_row(self):
        return self._model().row_extent()

    @property
    def min_row(self):
        return self._model().bounds()[0]

    @property
    def min_column(self):
        return self._model().bounds()[1]

    @property
    def max_row(self):
        return self._model().bounds()[2]

    @property
    def max_column(self):
        return self._model().bounds()[3]

    def calculate_dimension(self):
        first_row, first_col, last_row, last_col = self._model().bounds()
        return f"{_letters(first_col)}{first_row}:{_letters(last_col)}{last_row}"

    @property
    def dimensions(self):
        return self.calculate_dimension()

    def iter_rows(
        self, min_row=None, max_row=None, min_col=None, max_col=None, values_only=False
    ):
        bounds = self._model().bounds()
        if (
            min_row is None
            and max_row is None
            and min_col is None
            and max_col is None
            and not self._native.contains(0, 0)
            and bounds == (1, 1, 1, 1)
        ):
            return iter(())
        min_row, min_col = min_row or 1, min_col or 1
        max_row, max_col = max_row or bounds[2], max_col or bounds[3]
        self.cell(min_row, min_col)
        if max_row < min_row or max_col < min_col:
            return iter(())

        def rows():
            for row in range(min_row, max_row + 1):
                if values_only:
                    values, formulas = self._model().row_values_only(
                        row - 1, min_col - 1, max_col - 1, not self._existing
                    )
                    # Structured formulas remain live cell-bound objects.
                    if formulas:
                        for column in formulas:
                            values[column] = self.cell(row, min_col + column).value
                    yield tuple(values)
                    continue
                cells = tuple(
                    self.cell(row, column) for column in range(min_col, max_col + 1)
                )
                yield cells

        return rows()

    def iter_cols(
        self, min_col=None, max_col=None, min_row=None, max_row=None, values_only=False
    ):
        min_col, min_row = min_col or 1, min_row or 1
        max_col, max_row = max_col or self.max_column, max_row or self.max_row
        for column in range(min_col, max_col + 1):
            cells = tuple(self.cell(row, column) for row in range(min_row, max_row + 1))
            yield tuple(cell.value for cell in cells) if values_only else cells

    def __iter__(self):
        return self.iter_rows()

    @property
    def rows(self):
        return self.iter_rows()

    @property
    def columns(self):
        return self.iter_cols()

    @property
    def values(self):
        return self.iter_rows(values_only=True)

    def append(self, iterable):
        if isinstance(iterable, (str, bytes)):
            raise TypeError("Append requires a row iterable or column dictionary")
        if isinstance(iterable, dict):
            positions = [(_column(column), value) for column, value in iterable.items()]
            values = [None] * max((column for column, _ in positions), default=0)
            for column, value in positions:
                values[column - 1] = value
        else:
            values = []
            for value in iterable:
                if len(values) == 16384:
                    raise ValueError("Appended row exceeds Excel column bounds")
                values.append(value)
        self._model().append([_encode(value) for value in values])

    def _shift(self, idx, amount, rows, insert):
        if idx < 1 or amount < 1:
            raise ValueError("Index and amount must be positive")
        cached = list(self._cells.items())
        detached = {
            (row, col): cell._snapshot()
            for (row, col), cell in cached
            if not insert and idx <= (row if rows else col) < idx + amount
        }
        self._model().shift(idx - 1, amount, rows, insert)
        self._cells.clear()
        for (row, col), cell in cached:
            coordinate = row if rows else col
            if (row, col) in detached:
                cell._detached = detached[row, col]
                continue
            if coordinate >= idx + (0 if insert else amount):
                coordinate += amount if insert else -amount
                if rows:
                    cell.row = coordinate
                else:
                    cell.column = coordinate
            self._cells[cell.row, cell.column] = cell

    def insert_rows(self, idx, amount=1):
        self._shift(idx, amount, True, True)

    def delete_rows(self, idx, amount=1):
        self._shift(idx, amount, True, False)

    def insert_cols(self, idx, amount=1):
        self._shift(idx, amount, False, True)

    def delete_cols(self, idx, amount=1):
        self._shift(idx, amount, False, False)

    def move_range(self, cell_range, rows=0, cols=0, translate=False):
        range_object = cell_range if hasattr(cell_range, "coord") else None
        first_row, first_col, last_row, last_col = _range(
            range_object.coord if range_object is not None else cell_range
        )
        cached = list(self._cells.items())
        overwritten = {
            (row, col): cell._snapshot()
            for (row, col), cell in cached
            if first_row + rows <= row <= last_row + rows
            and first_col + cols <= col <= last_col + cols
            and not (first_row <= row <= last_row and first_col <= col <= last_col)
        }
        self._model().move_range(
            (first_row - 1, first_col - 1, last_row - 1, last_col - 1),
            rows,
            cols,
            translate,
        )
        if range_object is not None:
            range_object.shift(row_shift=rows, col_shift=cols)
        self._cells.clear()
        for (row, col), cell in cached:
            if first_row <= row <= last_row and first_col <= col <= last_col:
                cell.row += rows
                cell.column += cols
            elif (row, col) in overwritten:
                cell._detached = overwritten[row, col]
                continue
            self._cells[cell.row, cell.column] = cell
