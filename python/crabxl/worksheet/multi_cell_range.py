"""Standalone range containers; coordinate operations use the native geometry."""

from copy import copy

from . import cell_range


class MultiCellRange:
    def __init__(self, ranges=()):
        self.ranges = ranges

    @property
    def ranges(self):
        return self._ranges

    @ranges.setter
    def ranges(self, values):
        if isinstance(values, str):
            values = values.split()
        converted = set()
        for value in values:
            if isinstance(value, str):
                value = cell_range.CellRange(value)
            if not isinstance(value, cell_range.CellRange):
                raise TypeError("MultiCellRange entries must be CellRange objects")
            converted.add(value)
        self._ranges = converted

    def __contains__(self, value):
        if isinstance(value, str):
            value = cell_range.CellRange(value)
        if not isinstance(value, cell_range.CellRange):
            return False
        return any(
            value.title == existing.title and value.issubset(existing)
            for existing in self.ranges
        )

    def add(self, value):
        if isinstance(value, str):
            value = cell_range.CellRange(value)
        if not isinstance(value, cell_range.CellRange):
            raise ValueError("Provide a coordinate string or CellRange")
        if value not in self:
            self.ranges.add(value)

    def remove(self, value):
        if isinstance(value, str):
            value = cell_range.CellRange(value)
        self.ranges.remove(value)

    def sorted(self):
        return sorted(
            self.ranges,
            key=lambda value: (
                value.min_col,
                value.min_row,
                value.max_col,
                value.max_row,
            ),
        )

    def __iter__(self):
        return iter(self.ranges)

    def __bool__(self):
        return bool(self.ranges)

    def __str__(self):
        return " ".join(str(value) for value in self.sorted())

    def __repr__(self):
        return f"<MultiCellRange [{self}]>"

    def __eq__(self, other):
        if isinstance(other, str):
            other = type(self)(other)
        if not isinstance(other, MultiCellRange):
            return False
        return self.ranges == other.ranges

    def __copy__(self):
        return type(self)(copy(value) for value in self.ranges)

    def __iadd__(self, value):
        self.add(value)
        return self
