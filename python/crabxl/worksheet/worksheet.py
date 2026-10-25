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
        "_rich_views",
        "_assigned_rich_views",
        "_hyperlink_views",
        "_feat",
        "_names",
        "_print_rows",
        "_print_cols",
        "_print_area",
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
        self._rich_views = WeakValueDictionary()
        self._assigned_rich_views = {}
        self._hyperlink_views = {}
        self._feat = self._names = self._print_rows = self._print_cols = None
        self._print_area = None
        self._row_dimensions = self._column_dimensions = None
        self._merged_cells = None
        self._validate_title(self._title)

    # -- features (tables, filters, rules, validation, comments, names) ----

    def _feature_handle(self):
        # Features load without cells; do not store this lazy handle as the
        # cell model handle, or cell reads would see an unloaded sheet.
        if self._native is not None:
            return self._native
        return self.parent._editor.sheet_handle(self.title)

    def _state(self):
        if self.parent.write_only:
            raise NotImplementedError(
                "Features are not available on write-only worksheets"
            )
        state = self._feat
        if state is None:
            self.parent._check_open()
            from .._features import SheetState

            state = self._feat = SheetState(self)
        return state

    def _flush_features(self):
        state = None if self.parent.write_only else self._feat
        if state is not None and not self.parent.read_only:
            state.push()

    @property
    def tables(self):
        return self._state().get("tables")

    def add_table(self, table):
        """Check for a duplicate name in defined names and tables, then add."""
        from .table import Table

        if not isinstance(table, Table):
            raise TypeError("Only Table objects can be added")
        if self.parent._duplicate_name(table.name):
            raise ValueError("Table with name {0} already exists".format(table.name))
        self.tables.add(table)

    @property
    def auto_filter(self):
        return self._state().get("auto_filter")

    @auto_filter.setter
    def auto_filter(self, value):
        self._state().objs["auto_filter"] = value

    @property
    def conditional_formatting(self):
        return self._state().get("conditional_formatting")

    @conditional_formatting.setter
    def conditional_formatting(self, value):
        self._state().objs["conditional_formatting"] = value

    @property
    def data_validations(self):
        return self._state().get("data_validations")

    @data_validations.setter
    def data_validations(self, value):
        self._state().objs["data_validations"] = value

    def add_data_validation(self, data_validation):
        """Add a data-validation object to the sheet."""
        self.data_validations.append(data_validation)

    @property
    def protection(self):
        return self._state().get("protection")

    @protection.setter
    def protection(self, value):
        self._state().objs["protection"] = value

    @property
    def HeaderFooter(self):
        return self._state().get("header_footer")

    @HeaderFooter.setter
    def HeaderFooter(self, value):
        self._state().objs["header_footer"] = value

    def _comment_map(self):
        return self._state().get("comments")

    def _relocate_comments(self, transform):
        state = self._feat
        if state is None or "comments" not in state.objs:
            return
        moved = {}
        for key, comment in state.objs["comments"].items():
            target = transform(*key)
            comment._parent = None
            if target is not None:
                moved[target] = comment
        state.objs["comments"] = moved

    def _local_names(self):
        self.parent._names_state()
        if self._names is None:
            from ..workbook.defined_name import DefinedNameDict

            self._names = DefinedNameDict()
        return self._names

    @property
    def defined_names(self):
        return self._local_names()

    @defined_names.setter
    def defined_names(self, value):
        self.parent._names_state()
        self._names = value

    @property
    def print_title_rows(self):
        self.parent._names_state()
        if self._print_rows:
            return str(self._print_rows)

    @print_title_rows.setter
    def print_title_rows(self, rows):
        from .print_settings import RowRange

        self.parent._names_state()
        if rows is not None:
            self._print_rows = RowRange(rows)

    @property
    def print_title_cols(self):
        self.parent._names_state()
        if self._print_cols:
            return str(self._print_cols)

    @print_title_cols.setter
    def print_title_cols(self, cols):
        from .print_settings import ColRange

        self.parent._names_state()
        if cols is not None:
            self._print_cols = ColRange(cols)

    @property
    def print_titles(self):
        from .print_settings import PrintTitles

        self.parent._names_state()
        if not (self._print_rows or self._print_cols):
            return None
        return str(
            PrintTitles(cols=self._print_cols, rows=self._print_rows, title=self.title)
        )

    @property
    def print_area(self):
        self.parent._names_state()
        if self._print_area is None:
            return None
        self._print_area.title = self.title
        return str(self._print_area)

    @print_area.setter
    def print_area(self, value):
        from .print_settings import PrintArea

        self.parent._names_state()
        if not value:
            self._print_area = None
        elif isinstance(value, str):
            self._print_area = PrintArea.from_string(value)
        elif hasattr(value, "__iter__"):
            self._print_area = PrintArea.from_string(",".join(value))

    @property
    def oddHeader(self):
        return self.HeaderFooter.oddHeader

    @oddHeader.setter
    def oddHeader(self, value):
        self.HeaderFooter.oddHeader = value

    @property
    def oddFooter(self):
        return self.HeaderFooter.oddFooter

    @oddFooter.setter
    def oddFooter(self, value):
        self.HeaderFooter.oddFooter = value

    @property
    def evenHeader(self):
        return self.HeaderFooter.evenHeader

    @evenHeader.setter
    def evenHeader(self, value):
        self.HeaderFooter.evenHeader = value

    @property
    def evenFooter(self):
        return self.HeaderFooter.evenFooter

    @evenFooter.setter
    def evenFooter(self, value):
        self.HeaderFooter.evenFooter = value

    @property
    def firstHeader(self):
        return self.HeaderFooter.firstHeader

    @firstHeader.setter
    def firstHeader(self, value):
        self.HeaderFooter.firstHeader = value

    @property
    def firstFooter(self):
        return self.HeaderFooter.firstFooter

    @firstFooter.setter
    def firstFooter(self, value):
        self.HeaderFooter.firstFooter = value

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

    @merged_cells.setter
    def merged_cells(self, value):
        if value is self._merged_cells:
            return
        self.merged_cells.ranges = value.ranges if hasattr(value, "ranges") else value

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
            (key, cell, cell._snapshot(), cell.hyperlink)
            for key, cell in list(self._cells.items())
            if key != (first_row, first_col)
            and first_row <= key[0] <= last_row
            and first_col <= key[1] <= last_col
        ]
        self._model().merge_cells(*(value - 1 for value in bounds), merge)

        def relocate(row, column):
            if (row, column) != (first_row, first_col) and (
                first_row <= row <= last_row and first_col <= column <= last_col
            ):
                return None
            return row, column

        self._relocate_rich_views(relocate)
        self._relocate_hyperlink_views(relocate)
        self._relocate_comments(relocate)
        for key, cell, snapshot, hyperlink in aliases:
            cell._detached = snapshot
            cell._detached_hyperlink = hyperlink
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
        tagged = _encode(value)
        self._set_tagged(row, column, tagged)
        if tagged[0] == "rich":
            value._bind(self, row, column)

    def _set_tagged(self, row, column, tagged):
        self.parent._check_open()
        if self._existing:
            self.parent._editor.set(self.title, row - 1, column - 1, tagged)
        else:
            self._native.set(row - 1, column - 1, tagged)
        self._rich_views.pop((row, column), None)
        self._assigned_rich_views.pop((row, column), None)

    def _relocate_rich_views(self, transform):
        changed = []
        for coordinate, value in self._rich_views.items():
            target = transform(*coordinate)
            if target != coordinate:
                changed.append(
                    (coordinate, value, target, coordinate in self._assigned_rich_views)
                )
        for coordinate, value, _, _ in changed:
            self._rich_views.pop(coordinate, None)
            self._assigned_rich_views.pop(coordinate, None)
            value._bindings.get(self, set()).discard(coordinate)
        for _, value, target, assigned in changed:
            if target is not None:
                value._bind(self, *target, retain=assigned)

    def _relocate_hyperlink_views(self, transform):
        changed = []
        for coordinate, value in self._hyperlink_views.items():
            target = transform(*coordinate)
            if target != coordinate:
                changed.append((coordinate, value, target))
        for coordinate, value, _ in changed:
            self._hyperlink_views.pop(coordinate, None)
            value._bindings.get(self, set()).discard(coordinate)
        for coordinate, value, target in changed:
            if target is None:
                cell = self._cells.get(coordinate)
                if cell is not None:
                    cell._detached_hyperlink = value
            else:
                self._hyperlink_views[target] = value
                value._bindings.setdefault(self, set()).add(target)

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
        old, removed_hyperlink = self._model().remove(
            row - 1, column - 1, cell is not None
        )
        hyperlink = self._hyperlink_views.pop((row, column), None)
        self._rich_views.pop((row, column), None)
        self._assigned_rich_views.pop((row, column), None)
        if cell is not None:
            self._cells.pop((row, column), None)
            cell._detached = (*(old if old is not None else ("n", None)), *style)
            if hyperlink is None and removed_hyperlink is not None:
                from .hyperlink import Hyperlink

                target, location, tooltip, display, identity, reference = (
                    removed_hyperlink
                )
                hyperlink = Hyperlink(
                    reference or cell.coordinate,
                    location,
                    tooltip,
                    display,
                    identity,
                    target,
                )
            cell._detached_hyperlink = hyperlink

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
        tagged = [_encode(value) for value in values]
        row = self._model().append(tagged) + 1
        for column, (value, encoded) in enumerate(zip(values, tagged), 1):
            if encoded[0] == "rich":
                value._bind(self, row, column)

    def _shift(self, idx, amount, rows, insert):
        if idx < 1 or amount < 1:
            raise ValueError("Index and amount must be positive")
        cached = list(self._cells.items())
        detached = {
            (row, col): (cell._snapshot(), cell.hyperlink)
            for (row, col), cell in cached
            if not insert and idx <= (row if rows else col) < idx + amount
        }
        self._model().shift(idx - 1, amount, rows, insert)

        def relocate(row, column):
            coordinate = row if rows else column
            if not insert and idx <= coordinate < idx + amount:
                return None
            if coordinate >= idx + (0 if insert else amount):
                coordinate += amount if insert else -amount
                return (coordinate, column) if rows else (row, coordinate)
            return row, column

        self._relocate_rich_views(relocate)
        self._relocate_hyperlink_views(relocate)
        self._relocate_comments(relocate)
        self._cells.clear()
        for (row, col), cell in cached:
            coordinate = row if rows else col
            if (row, col) in detached:
                cell._detached, cell._detached_hyperlink = detached[row, col]
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
            (row, col): (cell._snapshot(), cell.hyperlink)
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

        def relocate(row, column):
            if first_row <= row <= last_row and first_col <= column <= last_col:
                return row + rows, column + cols
            if (
                first_row + rows <= row <= last_row + rows
                and first_col + cols <= column <= last_col + cols
            ):
                return None
            return row, column

        self._relocate_rich_views(relocate)
        self._relocate_hyperlink_views(relocate)
        self._relocate_comments(relocate)
        if range_object is not None:
            range_object.shift(row_shift=rows, col_shift=cols)
        self._cells.clear()
        for (row, col), cell in cached:
            if first_row <= row <= last_row and first_col <= col <= last_col:
                cell.row += rows
                cell.column += cols
            elif (row, col) in overwritten:
                cell._detached, cell._detached_hyperlink = overwritten[row, col]
                continue
            self._cells[cell.row, cell.column] = cell
