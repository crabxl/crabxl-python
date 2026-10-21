"""Compact live merged declarations; geometry and appearance remain in Rust."""

from collections.abc import MutableSet
from copy import copy
from weakref import WeakValueDictionary, ref

from .cell_range import CellRange
from .multi_cell_range import MultiCellRange as StandaloneMultiCellRange

_BOUNDS = ("min_row", "min_col", "max_row", "max_col")


class MergedCellRange(CellRange):
    def __init__(self, worksheet, coord):
        super().__init__(coord)
        self._worksheet = ref(worksheet)
        self._identity = None

    def _sync(self):
        identity = self.__dict__.get("_identity")
        if identity is None:
            return
        worksheet = self._worksheet()
        if worksheet is None:
            raise ValueError("Worksheet is no longer available")
        bounds = worksheet._model().merge_declaration(identity)
        if bounds is None:
            object.__setattr__(self, "_identity", None)
        else:
            for name, value in zip(_BOUNDS, bounds):
                object.__setattr__(self, name, value)

    def __getattribute__(self, name):
        if name in _BOUNDS:
            object.__getattribute__(self, "_sync")()
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if name in _BOUNDS and self.__dict__.get("_identity") is not None:
            self._sync()
            if self._identity is not None:
                bounds = {key: object.__getattribute__(self, key) for key in _BOUNDS}
                bounds[name] = value
                candidate = CellRange(**bounds)
                self._replace(candidate.coord)
                return
        object.__setattr__(self, name, value)

    def _replace(self, coordinate):
        candidate = CellRange(coordinate)
        self._sync()
        if self._identity is not None:
            worksheet = self._worksheet()
            worksheet._model().edit_merge_declaration(
                candidate.coord, identity=self._identity
            )
        for name in _BOUNDS:
            object.__setattr__(self, name, getattr(candidate, name))

    def __copy__(self):
        return type(self)(self._worksheet(), self.coord)

    @property
    def start_cell(self):
        worksheet = self._worksheet()
        if worksheet is None:
            raise ValueError("Worksheet is no longer available")
        return worksheet.cell(self.min_row, self.min_col)


class MultiCellRange(StandaloneMultiCellRange):
    def __init__(self, worksheet):
        self._worksheet = ref(worksheet)
        self._views = WeakValueDictionary()

    @property
    def ranges(self):
        return _BoundRanges(self)

    @ranges.setter
    def ranges(self, values):
        if isinstance(values, _BoundRanges) and values._owner is self:
            return
        prepared = StandaloneMultiCellRange(values)
        self._sync_views()
        self._owner()._model().replace_merge_declarations(
            [value.coord for value in prepared.sorted()]
        )
        self._sync_views()

    def _owner(self):
        worksheet = self._worksheet()
        if worksheet is None:
            raise ValueError("Worksheet is no longer available")
        return worksheet

    def _sync_views(self):
        for value in list(self._views.values()):
            value._sync()

    def _iter_ranges(self):
        worksheet = self._owner()
        native = worksheet._model()
        identities = [
            native.merge_identity(index) for index in range(native.merge_count())
        ]
        for index, identity in enumerate(identities):
            if (
                native.merge_count() != len(identities)
                or native.merge_identity(index) != identity
            ):
                raise RuntimeError("Merged range membership changed during iteration")
            result = self._views.get(identity)
            if result is None:
                bounds = native.merged_range(index)
                result = MergedCellRange.__new__(MergedCellRange)
                result.title = None
                for name, value in zip(_BOUNDS, bounds):
                    object.__setattr__(result, name, value)
                result._worksheet = ref(worksheet)
                result._identity = identity
                self._views[identity] = result
            yield result

    def __contains__(self, value):
        if isinstance(value, str):
            value = CellRange(value)
        if not isinstance(value, CellRange) or value.title is not None:
            return False
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

    def add(self, value):
        if isinstance(value, str):
            value = CellRange(value)
        if not isinstance(value, CellRange):
            raise ValueError("Provide a coordinate string or CellRange")
        if value not in self:
            self._owner()._model().edit_merge_declaration(value.coord)

    def remove(self, value):
        self.ranges.remove(CellRange(value) if isinstance(value, str) else value)

    def __copy__(self):
        return StandaloneMultiCellRange(copy(value) for value in self.ranges)


class _BoundRanges(MutableSet):
    """Mutable membership backed by the canonical native declarations."""

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
        if not isinstance(value, CellRange) or value.title is not None:
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

    def add(self, value):
        if not isinstance(value, CellRange):
            raise TypeError("Merged range entries must be CellRange objects")
        if value not in self:
            self._owner._owner()._model().edit_merge_declaration(
                value.coord, exact=True
            )

    def discard(self, value):
        if value not in self:
            return
        self._owner._sync_views()
        self._owner._owner()._model().edit_merge_declaration(value.coord, remove=True)
        self._owner._sync_views()

    def clear(self):
        self._owner.ranges = ()

    def update(self, *values):
        self._owner.ranges = [*self, *(item for group in values for item in group)]
