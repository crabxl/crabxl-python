"""Border edges and diagonal flags."""

from ._base import StyleValue
from .colors import color as to_color

# Border style names, from openpyxl 3.1.5 (MIT), Copyright (c) 2010-2024 openpyxl.
BORDER_NONE = None
BORDER_DASHDOT = "dashDot"
BORDER_DASHDOTDOT = "dashDotDot"
BORDER_DASHED = "dashed"
BORDER_DOTTED = "dotted"
BORDER_DOUBLE = "double"
BORDER_HAIR = "hair"
BORDER_MEDIUM = "medium"
BORDER_MEDIUMDASHDOT = "mediumDashDot"
BORDER_MEDIUMDASHDOTDOT = "mediumDashDotDot"
BORDER_MEDIUMDASHED = "mediumDashed"
BORDER_SLANTDASHDOT = "slantDashDot"
BORDER_THICK = "thick"
BORDER_THIN = "thin"


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
        # openpyxl also accepts and ignores diagonal_direction; XLSX has no such field.
        values = locals()
        for field in self._fields:
            setattr(self, field, values[field])


DEFAULT_BORDER = Border(
    left=Side(), right=Side(), top=Side(), bottom=Side(), diagonal=Side()
)
