"""Color identities retain theme and indexed references."""

import re

from ._base import StyleValue


class Color(StyleValue):
    _fields = ("type", "value", "tint")

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


def color(value):
    if value is None or isinstance(value, Color):
        return value
    return Color(rgb=value)
