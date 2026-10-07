"""Public cell compatibility imports."""

from .cell import Cell as Cell
from .cell import MergedCell as MergedCell

__all__ = ["Cell", "MergedCell", "WriteOnlyCell"]


def __getattr__(name):
    if name == "WriteOnlyCell":
        from ..optimized import WriteOnlyCell

        return WriteOnlyCell
    raise AttributeError(name)
