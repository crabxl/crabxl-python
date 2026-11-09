"""Public cell compatibility imports."""

from .cell import Cell as Cell
from .cell import MergedCell as MergedCell

__all__ = ["Cell", "MergedCell", "WriteOnlyCell"]


def __getattr__(name):
    if name == "WriteOnlyCell":
        from ..optimized import WriteOnlyCell

        return WriteOnlyCell
    if name == "ReadOnlyCell":
        from ..optimized import ReadOnlyCell

        return ReadOnlyCell
    raise AttributeError(name)
