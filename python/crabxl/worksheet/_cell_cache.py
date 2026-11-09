"""Weak cell views that can recover an existing native cell on lookup."""

from weakref import WeakValueDictionary, ref


class CellCache(WeakValueDictionary):
    get_cached = WeakValueDictionary.get

    def __init__(self, worksheet):
        super().__init__()
        self._worksheet = ref(worksheet)

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            pass
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
