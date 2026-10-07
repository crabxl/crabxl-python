"""Border edges and diagonal flags."""

from ._base import StyleValue
from .colors import color as to_color


class Side(StyleValue):
    _children = ("color",)
    _fields = ("style", "color")
    _aliases = {"border_style": "style"}

    def __init__(self, style=None, color=None, border_style=None):
        self.style = style if border_style is None else border_style
        self.color = to_color(color)


class Border(StyleValue):
    _component = "border"
    _children = (
        "left",
        "right",
        "top",
        "bottom",
        "diagonal",
        "vertical",
        "horizontal",
        "start",
        "end",
    )
    _fields = (
        "left",
        "right",
        "top",
        "bottom",
        "diagonal",
        "vertical",
        "horizontal",
        "start",
        "end",
        "diagonalUp",
        "diagonalDown",
        "outline",
    )

    def __init__(
        self,
        left=None,
        right=None,
        top=None,
        bottom=None,
        diagonal=None,
        diagonal_direction=None,
        vertical=None,
        horizontal=None,
        diagonalUp=False,
        diagonalDown=False,
        outline=True,
        start=None,
        end=None,
    ):
        if diagonal_direction is not None:
            raise NotImplementedError("Legacy diagonal_direction has no XLSX encoding")
        values = locals()
        for field in self._fields:
            setattr(self, field, values[field])
