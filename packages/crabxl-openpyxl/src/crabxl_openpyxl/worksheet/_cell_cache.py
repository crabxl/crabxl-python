"""Weak cell views that can recover an existing native cell on lookup."""

from weakref import ref

# Plain refs without callbacks are created in C; WeakValueDictionary builds a
# Python KeyedRef and runs a Python callback for every cell. Dead entries are
# swept once the table doubles, which keeps the cost per cell constant.
_FIRST_SWEEP = 1024


class CellCache:
    __slots__ = ("_data", "_sweep_at", "_worksheet")

    def __init__(self, worksheet):
        self._data = {}
        self._sweep_at = _FIRST_SWEEP
        self._worksheet = ref(worksheet)

    def get_cached(self, key, default=None):
        entry = self._data.get(key)
        if entry is not None:
            cell = entry()
            if cell is not None:
                return cell
        return default

    def __contains__(self, key):
        return self.get_cached(key) is not None

    def __setitem__(self, key, cell):
        data = self._data
        data[key] = ref(cell)
        if len(data) >= self._sweep_at:
            for dead in [key for key, entry in data.items() if entry() is None]:
                del data[dead]
            self._sweep_at = max(_FIRST_SWEEP, 2 * len(data))

    def __getitem__(self, key):
        cell = self.get_cached(key)
        if cell is not None:
            return cell
        if (
            not isinstance(key, tuple)
            or len(key) != 2
            or not isinstance(key[0], int)
            or not isinstance(key[1], int)
            or not 1 <= key[0] <= 1048576
            or not 1 <= key[1] <= 16384
        ):
            raise KeyError(key)
        worksheet = self._worksheet()
        if worksheet is None:
            raise KeyError(key)
        present, merged = worksheet._model().cell_state(key[0] - 1, key[1] - 1)
        if not present and not merged:
            raise KeyError(key)
        from ..cell.cell import Cell, MergedCell

        value = (MergedCell if merged else Cell)(worksheet, *key)
        self[key] = value
        return value

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def pop(self, key, default=None):
        entry = self._data.pop(key, None)
        cell = None if entry is None else entry()
        return default if cell is None else cell

    def items(self):
        """Live entries only, as a list, so callers may change the cache while iterating."""
        return [
            (key, cell)
            for key, entry in self._data.items()
            if (cell := entry()) is not None
        ]

    def clear(self):
        self._data.clear()
        self._sweep_at = _FIRST_SWEEP
