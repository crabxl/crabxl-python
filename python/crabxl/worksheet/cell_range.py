"""Finite public range views over canonical Rust rectangle operations."""

from .. import _letters, _range
from .._native import adjust_range, combine_ranges, compare_ranges


class CellRange:
    def __init__(
        self,
        range_string=None,
        min_col=None,
        min_row=None,
        max_col=None,
        max_row=None,
        title=None,
    ):
        if range_string is not None:
            if not isinstance(range_string, str):
                raise TypeError("Range must be a coordinate string")
            if "!" in range_string:
                title, range_string = range_string.rsplit("!", 1)
                if title.startswith("'") and title.endswith("'"):
                    title = title[1:-1].replace("''", "'")
            bounds = _range(range_string)
        else:
            if None in (min_col, min_row, max_col, max_row):
                raise TypeError("Provide a range string or all four bounds")
            bounds = _range(
                f"{_letters(min_col)}{min_row}:{_letters(max_col)}{max_row}"
            )
        if title is not None and not isinstance(title, str):
            raise TypeError("Range title must be a string or None")
        self.title = title
        self.min_row, self.min_col, self.max_row, self.max_col = bounds

    @property
    def coord(self):
        first = f"{_letters(self.min_col)}{self.min_row}"
        last = f"{_letters(self.max_col)}{self.max_row}"
        return first if first == last else f"{first}:{last}"

    @property
    def bounds(self):
        return self.min_col, self.min_row, self.max_col, self.max_row

    def shift(self, col_shift=0, row_shift=0):
        self._replace(
            adjust_range(self.coord, col_shift, row_shift, col_shift, row_shift)
        )

    def _replace(self, coordinate):
        self.min_row, self.min_col, self.max_row, self.max_col = _range(coordinate)

    def expand(self, right=0, down=0, left=0, up=0):
        self._replace(adjust_range(self.coord, -left, -up, right, down))

    def shrink(self, right=0, bottom=0, left=0, top=0):
        self._replace(adjust_range(self.coord, left, top, -right, -bottom))

    @property
    def size(self):
        return {
            "columns": self.max_col - self.min_col + 1,
            "rows": self.max_row - self.min_row + 1,
        }

    @property
    def rows(self):
        for row in range(self.min_row, self.max_row + 1):
            yield [(row, column) for column in range(self.min_col, self.max_col + 1)]

    @property
    def cols(self):
        for column in range(self.min_col, self.max_col + 1):
            yield [(row, column) for row in range(self.min_row, self.max_row + 1)]

    @property
    def cells(self):
        return (
            (row, column)
            for row in range(self.min_row, self.max_row + 1)
            for column in range(self.min_col, self.max_col + 1)
        )

    @property
    def top(self):
        return [
            (self.min_row, column) for column in range(self.min_col, self.max_col + 1)
        ]

    @property
    def bottom(self):
        return [
            (self.max_row, column) for column in range(self.min_col, self.max_col + 1)
        ]

    @property
    def left(self):
        return [(row, self.min_col) for row in range(self.min_row, self.max_row + 1)]

    @property
    def right(self):
        return [(row, self.max_col) for row in range(self.min_row, self.max_row + 1)]

    def _other(self, other):
        if not isinstance(other, CellRange):
            raise TypeError("Expected a CellRange")
        if self.title != other.title:
            raise ValueError("Ranges must have the same worksheet title")
        return other

    def union(self, other):
        other = self._other(other)
        return CellRange(
            combine_ranges(self.coord, other.coord, False), title=self.title
        )

    def intersection(self, other):
        other = self._other(other)
        return CellRange(
            combine_ranges(self.coord, other.coord, True), title=self.title
        )

    def issubset(self, other):
        other = self._other(other)
        return compare_ranges(self.coord, other.coord)[1]

    def issuperset(self, other):
        other = self._other(other)
        return compare_ranges(self.coord, other.coord)[0]

    def isdisjoint(self, other):
        other = self._other(other)
        return not compare_ranges(self.coord, other.coord)[2]

    def __str__(self):
        if self.title is None:
            return self.coord
        return "'" + self.title.replace("'", "''") + "'!" + self.coord

    def __repr__(self):
        return f"<CellRange {self}>"

    def __eq__(self, other):
        return (
            isinstance(other, CellRange)
            and self.title == other.title
            and self.bounds == other.bounds
        )

    def __hash__(self):
        return hash((self.title, self.bounds))

    def __contains__(self, value):
        value = (
            CellRange(str(value), title=self.title)
            if not isinstance(value, CellRange)
            else value
        )
        return self.issuperset(value)

    def __le__(self, other):
        return self.issubset(other)

    def __ge__(self, other):
        return self.issuperset(other)

    def __lt__(self, other):
        return self != other and self.issubset(other)

    def __gt__(self, other):
        return self != other and self.issuperset(other)

    __or__ = union
    __and__ = intersection


__all__ = ["CellRange", "MultiCellRange"]


def __getattr__(name):
    if name == "MultiCellRange":
        from .multi_cell_range import MultiCellRange

        return MultiCellRange
    raise AttributeError(name)
