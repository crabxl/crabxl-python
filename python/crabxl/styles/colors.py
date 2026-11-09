"""Color identities retain theme and indexed references."""

import re

from ..descriptors import Typed
from ..xml.functions import Element
from ._base import StyleValue
from ._x.colors import RGB  # noqa: F401

aRGB_REGEX = re.compile(r"^([A-Fa-f0-9]{8}|[A-Fa-f0-9]{6})$")
BLACK = "00000000"
WHITE = "00FFFFFF"
BLUE = "000000FF"
RED = "00FF0000"


class Color(StyleValue):
    tagname = "color"
    _fields = ("type", "value", "tint")

    def __setattr__(self, name, value):
        if name == "value":
            kind = getattr(self, "type", "rgb")
            if kind == "rgb" and not isinstance(value, str):
                raise TypeError("RGB color values must be strings")
            if kind in ("theme", "indexed"):
                value = int(value)
            if kind == "auto":
                value = value not in (False, 0, "0", "false", "f")
        super().__setattr__(name, value)

    def __add__(self, other):
        if not isinstance(other, Color):
            return NotImplemented
        return self

    def __init__(
        self,
        rgb="00000000",
        indexed=None,
        auto=None,
        theme=None,
        tint=0.0,
        index=None,
        type="rgb",
    ):
        if index is not None:
            indexed = index
        if indexed is not None:
            type, value = "indexed", indexed
        elif theme is not None:
            type, value = "theme", theme
        elif auto is not None:
            type, value = "auto", auto
        else:
            value = rgb
        if type == "rgb":
            if not isinstance(value, str) or not re.fullmatch(
                r"[0-9a-fA-F]{6}|[0-9a-fA-F]{8}", value
            ):
                raise ValueError("Colors must be six or eight hexadecimal digits")
            value = value if len(value) == 8 else "00" + value
        if not -1 <= float(tint) <= 1:
            raise ValueError("Tint must be between -1 and 1")
        self.type, self.value, self.tint = type, value, float(tint)

    @property
    def index(self):
        return self.value

    @property
    def rgb(self):
        return self.value if self.type == "rgb" else None

    @property
    def indexed(self):
        return self.value if self.type == "indexed" else None

    @property
    def theme(self):
        return self.value if self.type == "theme" else None

    @property
    def auto(self):
        return self.value if self.type == "auto" else None

    def __iter__(self):
        value = self.value
        yield self.type, str(int(value)) if isinstance(value, bool) else str(value)
        if self.tint:
            yield "tint", str(self.tint)

    def to_tree(self, tagname=None, idx=None, namespace=None):
        tag = tagname or self.tagname
        return Element(f"{{{namespace}}}{tag}" if namespace else tag, dict(self))

    @classmethod
    def from_tree(cls, node):
        values = dict(node.attrib)
        for name in ("indexed", "theme"):
            if name in values:
                values[name] = int(values[name])
        if "auto" in values:
            values["auto"] = values["auto"] in ("1", "true")
        return cls(**values)


class ColorDescriptor(Typed):
    expected_type = Color

    def __set__(self, instance, value):
        super().__set__(instance, color(value))


def color(value):
    if value is None or isinstance(value, Color):
        return value
    return Color(rgb=value)


def __getattr__(name):
    if name in ("ColorList", "RgbColor", "COLOR_INDEX"):
        from ._x import colors

        return getattr(colors, name)
    raise AttributeError(name)
