"""Pattern and gradient fill values."""

from ._base import StyleValue
from .colors import Color
from .colors import color as to_color


class PatternFill(StyleValue):
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

    def __init__(self, color, position):
        self.color, self.position = to_color(color), float(position)


class GradientFill(StyleValue):
    _component = "fill"
    _children = ("stop",)
    _fields = ("type", "degree", "left", "right", "top", "bottom", "stop")
    _aliases = {"fill_type": "type"}

    def __init__(
        self, type="linear", degree=0, left=0, right=0, top=0, bottom=0, stop=()
    ):
        values = locals()
        for field in self._fields[:-1]:
            setattr(self, field, values[field])
        items = list(stop)
        existing = [isinstance(item, Stop) for item in items]
        if any(existing) and not all(existing):
            raise ValueError("Cannot mix gradient stops and colors")
        self.stop = (
            items
            if all(existing)
            else [
                Stop(item, index / max(1, len(items) - 1))
                for index, item in enumerate(items)
            ]
        )
