"""Pattern and gradient fill values."""

from ._base import StyleValue
from .colors import Color
from .colors import color as to_color


class Fill(StyleValue):
    @classmethod
    def from_tree(cls, node):
        from . import _x
        from ._base import _from_xml_style

        return _from_xml_style(_x.Fill.from_tree(node))


class PatternFill(Fill):
    _component = "fill"
    _children = ("fgColor", "bgColor")
    _fields = ("patternType", "fgColor", "bgColor")
    _aliases = {
        "fill_type": "patternType",
        "start_color": "fgColor",
        "end_color": "bgColor",
    }

    def __init__(
        self,
        patternType=None,
        fgColor=None,
        bgColor=None,
        fill_type=None,
        start_color=None,
        end_color=None,
    ):
        self.patternType = patternType if fill_type is None else fill_type
        self.fgColor = (
            to_color(fgColor if start_color is None else start_color) or Color()
        )
        self.bgColor = to_color(bgColor if end_color is None else end_color) or Color()


class Stop(StyleValue):
    _children = ("color",)
    _fields = ("color", "position")

    def __setattr__(self, name, value):
        if name == "position":
            value = float(value)
            if not 0 <= value <= 1:
                raise ValueError("Gradient stop position must be between 0 and 1")
        elif name == "color":
            value = to_color(value)
        super().__setattr__(name, value)

    def __init__(self, color, position):
        self.color, self.position = to_color(color), float(position)


def _assign_position(values):
    items = list(values)
    existing = [isinstance(item, Stop) for item in items]
    if any(existing) and not all(existing):
        raise ValueError("Cannot mix gradient stops and colors")
    if not all(existing):
        items = [
            Stop(item, index / max(1, len(items) - 1))
            for index, item in enumerate(items)
        ]
    if len({item.position for item in items}) != len(items):
        raise ValueError("Gradient stop positions must be unique")
    return items


class GradientFill(Fill):
    _component = "fill"
    _children = ("stop",)
    _fields = ("type", "degree", "left", "right", "top", "bottom", "stop")
    _aliases = {"fill_type": "type"}

    def __setattr__(self, name, value):
        if name == "stop":
            value = _assign_position(value)
        super().__setattr__(name, value)

    def __init__(
        self, type="linear", degree=0, left=0, right=0, top=0, bottom=0, stop=()
    ):
        values = locals()
        for field in self._fields[:-1]:
            setattr(self, field, values[field])
        self.stop = stop


DEFAULT_EMPTY_FILL = PatternFill()
DEFAULT_GRAY_FILL = PatternFill(patternType="gray125")
