"""Font values with openpyxl-compatible aliases."""

from ._base import StyleValue
from .colors import Color
from .colors import color as to_color


class Font(StyleValue):
    def __setattr__(self, name, value):
        if name == "color":
            value = to_color(value)
        elif name in ("sz", "family") and value is not None:
            value = float(value)
        elif name == "charset" and value is not None:
            value = int(value)
        super().__setattr__(name, value)

    _component = "font"
    _children = ("color",)
    _fields = (
        "name",
        "sz",
        "b",
        "i",
        "charset",
        "u",
        "strike",
        "color",
        "scheme",
        "family",
        "vertAlign",
        "outline",
        "shadow",
        "condense",
        "extend",
    )
    _aliases = {
        "size": "sz",
        "bold": "b",
        "italic": "i",
        "strikethrough": "strike",
        "underline": "u",
    }

    def __init__(
        self,
        name=None,
        sz=None,
        b=None,
        i=None,
        charset=None,
        u=None,
        strike=None,
        color=None,
        scheme=None,
        family=None,
        size=None,
        bold=None,
        italic=None,
        strikethrough=None,
        underline=None,
        vertAlign=None,
        outline=None,
        shadow=None,
        condense=None,
        extend=None,
    ):
        values = locals()
        for field in self._fields:
            setattr(self, field, values[field])
        for alias, value in (
            ("size", size),
            ("bold", bold),
            ("italic", italic),
            ("strikethrough", strikethrough),
            ("underline", underline),
        ):
            if value is not None:
                setattr(self, alias, value)
        self.b = bool(self.b)
        self.i = bool(self.i)
        self.color = to_color(color)


DEFAULT_FONT = Font(
    name="Calibri", sz=11, family=2, color=Color(theme=1), scheme="minor"
)
