"""Public cell compatibility imports."""

from .cell import Cell as Cell

__all__ = ["Cell", "WriteOnlyCell"]


def __getattr__(name):
    if name == "WriteOnlyCell":
        from ..optimized import WriteOnlyCell

        return WriteOnlyCell
    raise AttributeError(name)
