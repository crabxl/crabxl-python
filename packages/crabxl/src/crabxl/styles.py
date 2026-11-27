"""Cell appearance.

Every style type is an immutable value. Change one with ``replace``, which
returns a new value:

>>> from crabxl.styles import Font, Style
>>> header = Style(font=Font(bold=True))
>>> money = header.replace(number_format="#,##0.00")
>>> header.number_format, money.number_format
('General', '#,##0.00')
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Literal

__all__ = [
    "Alignment",
    "Border",
    "BorderStyle",
    "Color",
    "ColorLike",
    "Fill",
    "Font",
    "HorizontalAlignment",
    "PartialStyle",
    "Protection",
    "Side",
    "Style",
    "Underline",
    "VerticalAlignment",
]


@dataclass(frozen=True, slots=True)
class Color:
    """A color: RGB, a theme color with a tint, an indexed palette color, or
    automatic.

    Create RGB colors from hex text: ``Color("1F4E79")`` or ``Color("#1F4E79")``.
    Wherever a color is expected, hex text works too.
    """

    value: str | int = "000000"
    kind: Literal["rgb", "theme", "indexed", "auto"] = "rgb"
    tint: float = 0.0

    def __post_init__(self) -> None:
        if self.kind == "rgb":
            text = str(self.value).removeprefix("#").upper()
            if len(text) not in (6, 8) or any(
                c not in "0123456789ABCDEF" for c in text
            ):
                from .errors import InvalidInputError

                raise InvalidInputError(
                    f"{self.value!r} is not a hex color such as 'FF0000'"
                )
            object.__setattr__(self, "value", text[-6:])
        elif self.kind == "theme":
            if not (
                isinstance(self.value, int)
                and 0 <= self.value <= 11
                and -1.0 <= self.tint <= 1.0
            ):
                from .errors import InvalidInputError

                raise InvalidInputError(
                    "A theme color needs an index from 0 to 11 and a tint from -1 to 1"
                )

    @classmethod
    def theme(cls, index: int, tint: float = 0.0) -> Color:
        """A theme color: 0 and 1 are the dark and light text colors, 4 to 9
        the accents. The tint lightens (positive) or darkens (negative)."""
        return cls(index, "theme", tint)

    @classmethod
    def indexed(cls, index: int) -> Color:
        """A color of the legacy indexed palette."""
        return cls(index, "indexed")

    @classmethod
    def automatic(cls) -> Color:
        """The automatic color chosen by the application."""
        return cls(0, "auto")

    def __str__(self) -> str:
        return f"#{self.value}" if self.kind == "rgb" else f"{self.kind}:{self.value}"


type ColorLike = Color | str
"""A color, or hex text such as ``"1F4E79"``."""


def _color(value: ColorLike | None) -> Color | None:
    if value is None or isinstance(value, Color):
        return value
    return Color(value)


type Underline = Literal["single", "double", "single_accounting", "double_accounting"]


@dataclass(frozen=True, slots=True)
class Font:
    """A font. ``None`` attributes inherit the workbook's default font."""

    name: str | None = None
    size: float | None = None
    bold: bool = False
    italic: bool = False
    strike: bool = False
    underline: Underline | Literal["none"] | None = None
    color: Color | None = None

    def __init__(
        self,
        name: str | None = None,
        size: float | None = None,
        bold: bool = False,
        italic: bool = False,
        strike: bool = False,
        underline: Underline | Literal["none"] | None = None,
        color: ColorLike | None = None,
    ) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "size", size)
        object.__setattr__(self, "bold", bold)
        object.__setattr__(self, "italic", italic)
        object.__setattr__(self, "strike", strike)
        object.__setattr__(
            self, "underline", None if underline == "none" else underline
        )
        object.__setattr__(self, "color", _color(color))

    def replace(self, **changes: object) -> Font:
        """A copy with some attributes changed."""
        return dataclasses.replace(self, **changes)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class Fill:
    """A solid background fill."""

    color: Color

    def __init__(self, color: ColorLike) -> None:
        object.__setattr__(self, "color", _color(color))

    @classmethod
    def solid(cls, color: ColorLike) -> Fill:
        """A solid fill of one color."""
        return cls(color)


type BorderStyle = Literal[
    "thin",
    "medium",
    "thick",
    "dashed",
    "dotted",
    "double",
    "hair",
    "dash_dot",
    "dash_dot_dot",
    "medium_dashed",
    "medium_dash_dot",
    "medium_dash_dot_dot",
    "slant_dash_dot",
]


@dataclass(frozen=True, slots=True)
class Side:
    """One border line."""

    style: BorderStyle = "thin"
    color: Color | None = None

    def __init__(
        self, style: BorderStyle = "thin", color: ColorLike | None = None
    ) -> None:
        object.__setattr__(self, "style", style)
        object.__setattr__(self, "color", _color(color))


@dataclass(frozen=True, slots=True)
class Border:
    """The four outer border lines of a cell."""

    left: Side | None = None
    right: Side | None = None
    top: Side | None = None
    bottom: Side | None = None

    @classmethod
    def all(cls, side: Side) -> Border:
        """The same line on all four edges."""
        return cls(side, side, side, side)

    def replace(self, **changes: Side | None) -> Border:
        """A copy with some edges changed."""
        return dataclasses.replace(self, **changes)


type HorizontalAlignment = Literal[
    "general",
    "left",
    "center",
    "right",
    "fill",
    "justify",
    "center_continuous",
    "distributed",
]
type VerticalAlignment = Literal["bottom", "center", "top", "justify", "distributed"]


@dataclass(frozen=True, slots=True)
class Alignment:
    """Text position, wrapping, indent and rotation."""

    horizontal: HorizontalAlignment | None = None
    vertical: VerticalAlignment | None = None
    wrap_text: bool = False
    shrink_to_fit: bool = False
    indent: int = 0
    rotation: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.indent <= 250 or not (
            0 <= self.rotation <= 180 or self.rotation == 255
        ):
            from .errors import InvalidInputError

            raise InvalidInputError(
                "Indent is 0 to 250; rotation is 0 to 180, or 255 for vertical text"
            )

    def replace(self, **changes: object) -> Alignment:
        """A copy with some attributes changed."""
        return dataclasses.replace(self, **changes)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class Protection:
    """Cell protection. It takes effect when the sheet is protected."""

    locked: bool = True
    hidden: bool = False


@dataclass(frozen=True, slots=True)
class Style:
    """The complete appearance of a cell."""

    number_format: str = "General"
    font: Font = Font()
    fill: Fill | None = None
    border: Border = Border()
    alignment: Alignment = Alignment()
    protection: Protection = Protection()

    def replace(
        self,
        *,
        number_format: str | None = None,
        font: Font | None = None,
        fill: Fill | None = None,
        border: Border | None = None,
        alignment: Alignment | None = None,
        protection: Protection | None = None,
    ) -> Style:
        """A copy with some parts changed. Pass ``fill=Fill(...)`` to change
        the fill; use :meth:`without_fill` to remove it."""
        return Style(
            number_format=self.number_format
            if number_format is None
            else number_format,
            font=self.font if font is None else font,
            fill=self.fill if fill is None else fill,
            border=self.border if border is None else border,
            alignment=self.alignment if alignment is None else alignment,
            protection=self.protection if protection is None else protection,
        )

    def without_fill(self) -> Style:
        """A copy without a fill."""
        return dataclasses.replace(self, fill=None)


@dataclass(frozen=True, slots=True)
class PartialStyle:
    """Formatting that a conditional format applies on top of a cell's
    style. Only the parts that are set change."""

    font: Font | None = None
    fill: Fill | None = None
