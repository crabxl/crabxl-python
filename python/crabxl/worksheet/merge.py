"""Compact live merged-range views; geometry and appearance remain in Rust."""

from collections.abc import Set
from weakref import ref

from .cell_range import CellRange


class MergedCellRange(CellRange):
    def __init__(self, worksheet, coord):
        super().__init__(coord)
        self._worksheet = ref(worksheet)

    def __setattr__(self, name, value):
        if name in {"min_row", "min_col", "max_row", "max_col"} and hasattr(
            self, "_worksheet"
        ):
            raise NotImplementedError(
                "Live merged-range coordinate mutation is not implemented; unmerge and merge explicitly"
            )
        object.__setattr__(self, name, value)

    @property
    def start_cell(self):
        worksheet = self._worksheet()
        if worksheet is None:
            raise ValueError("Worksheet is no longer available")
        return worksheet.cell(self.min_row, self.min_col)


class MultiCellRange:
    def __init__(self, worksheet):
        self._worksheet = ref(worksheet)

    @property
    def ranges(self):
        return _BoundRanges(self)

    def _owner(self):
        worksheet = self._worksheet()
        if worksheet is None:
            raise ValueError("Worksheet is no longer available")
        return worksheet

    def _iter_ranges(self):
        worksheet = self._owner()
        native = worksheet._model()
        count = native.merge_count()
        for index in range(count):
            if native.merge_count() != count:
                raise RuntimeError("Merged range membership changed during iteration")
            first_row, first_col, last_row, last_col = native.merged_range(index)
            result = MergedCellRange.__new__(MergedCellRange)
            result.min_row, result.min_col = first_row, first_col
            result.max_row, result.max_col = last_row, last_col
            result._worksheet = ref(worksheet)
            yield result

    def __iter__(self):
        return iter(self.ranges)

    def __bool__(self):
        return bool(self.ranges)

    def __contains__(self, value):
        value = CellRange(str(value)) if not isinstance(value, CellRange) else value
        return (
            self._owner()
            ._model()
            .contains_merge(
                value.min_row - 1,
                value.min_col - 1,
                value.max_row - 1,
                value.max_col - 1,
                False,
            )
        )

    def __str__(self):
        return " ".join(
            item.coord for item in sorted(self.ranges, key=lambda item: item.bounds)
        )

    def add(self, value):
        raise NotImplementedError(
            "Raw merge declarations are not editable; use Worksheet.merge_cells"
        )

    def remove(self, value):
        raise NotImplementedError(
            "Raw merge declarations are not editable; use Worksheet.unmerge_cells"
        )


class _BoundRanges(Set):
    """Live read-only range membership; never silently mutate a temporary set."""

    @classmethod
    def _from_iterable(cls, values):
        return set(values)

    def __init__(self, owner):
        self._owner = owner

    def __iter__(self):
        return self._owner._iter_ranges()

    def __len__(self):
        return self._owner._owner()._model().merge_count()

    def __contains__(self, value):
        if not isinstance(value, CellRange):
            return False
        return (
            self._owner._owner()
            ._model()
            .contains_merge(
                value.min_row - 1,
                value.min_col - 1,
                value.max_row - 1,
                value.max_col - 1,
                True,
            )
        )

    @staticmethod
    def _unsupported(*args, **kwargs):
        raise NotImplementedError(
            "Raw merge membership mutation is not implemented; use Worksheet.merge_cells/unmerge_cells"
        )

    add = remove = discard = clear = pop = update = _unsupported
