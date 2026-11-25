"""Cell protection values, independent of sheet protection."""

from ._base import StyleValue


class Protection(StyleValue):
    _component = "protection"
    _children = ()
    _fields = ("locked", "hidden")

    def __init__(self, locked=True, hidden=False):
        self.locked, self.hidden = locked, hidden
