"""Tables, validation, conditional formats, notes, hyperlinks, names and images."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from .styles import PartialStyle

__all__ = [
    "Comparison",
    "ConditionalFormat",
    "DataValidation",
    "DefinedName",
    "Hyperlink",
    "Image",
    "Note",
    "Properties",
    "Table",
]

Comparison: TypeAlias = Literal[
    "between", "not_between", "==", "!=", ">", ">=", "<", "<="
]
"""A comparison for validation and conditional formats."""


Ranges: TypeAlias = "str | Sequence[str]"
"""One A1 range, or several."""


def _ranges(ranges: Ranges) -> tuple[str, ...]:
    return (ranges,) if isinstance(ranges, str) else tuple(ranges)


@dataclass(frozen=True, slots=True)
class Table:
    """A table: a named range with a header row. The header cells name the
    columns, so they must hold distinct, non-empty text."""

    name: str
    ref: str
    style: str | None = "TableStyleMedium2"
    banded_rows: bool = True
    totals_row: bool = field(default=False, compare=False)


@dataclass(frozen=True, slots=True)
class DataValidation:
    """A rule that limits what users can type into cells.

    Build one with a class method, such as
    ``DataValidation.list(["Yes", "No"], ranges="C2:C100")``.
    """

    kind: Literal["list", "list_from", "whole", "decimal", "text_length", "custom"]
    ranges: tuple[str, ...]
    first: object
    second: object = None
    comparison: Comparison | None = None
    allow_blank: bool = True
    prompt: tuple[str, str] | None = None
    error: tuple[str, str] | None = None

    @classmethod
    def list(cls, choices: Sequence[str], *, ranges: Ranges) -> DataValidation:
        """A drop-down list of fixed choices."""
        return cls("list", _ranges(ranges), [str(choice) for choice in choices])

    @classmethod
    def list_from(cls, source: str, *, ranges: Ranges) -> DataValidation:
        """A drop-down list of the values in a range, such as ``"=$H$1:$H$10"``."""
        return cls("list_from", _ranges(ranges), source)

    @classmethod
    def whole(
        cls,
        comparison: Comparison,
        value: int,
        second: int | None = None,
        *,
        ranges: Ranges,
    ) -> DataValidation:
        """Whole numbers that compare with one value, or two for ``between``."""
        return cls("whole", _ranges(ranges), value, second, comparison)

    @classmethod
    def decimal(
        cls,
        comparison: Comparison,
        value: float,
        second: float | None = None,
        *,
        ranges: Ranges,
    ) -> DataValidation:
        """Numbers that compare with one value, or two for ``between``."""
        return cls("decimal", _ranges(ranges), value, second, comparison)

    @classmethod
    def text_length(
        cls,
        comparison: Comparison,
        value: int,
        second: int | None = None,
        *,
        ranges: Ranges,
    ) -> DataValidation:
        """Text whose length compares with one value, or two for ``between``."""
        return cls("text_length", _ranges(ranges), value, second, comparison)

    @classmethod
    def custom(cls, formula: str, *, ranges: Ranges) -> DataValidation:
        """Values for which a formula is true, such as ``"=ISNUMBER(A1)"``."""
        return cls("custom", _ranges(ranges), formula)


@dataclass(frozen=True, slots=True)
class ConditionalFormat:
    """A rule that formats cells when a condition holds."""

    ref: str
    kind: Literal["cell", "formula"]
    value: str
    style: PartialStyle
    second: str | None = None
    comparison: Comparison | None = None
    stop_if_true: bool = False

    @classmethod
    def cell(
        cls,
        ref: str,
        comparison: Comparison,
        value: object,
        second: object = None,
        *,
        style: PartialStyle,
        stop_if_true: bool = False,
    ) -> ConditionalFormat:
        """Format cells whose value compares with one value, or two for
        ``between``. Text values need quotes: ``'"Done"'``."""
        return cls(
            ref,
            "cell",
            str(value),
            style,
            None if second is None else str(second),
            comparison,
            stop_if_true,
        )

    @classmethod
    def formula(
        cls, ref: str, formula: str, *, style: PartialStyle, stop_if_true: bool = False
    ) -> ConditionalFormat:
        """Format cells for which a formula is true. Relative references
        refer to the top-left cell of the range."""
        return cls(
            ref, "formula", formula.removeprefix("="), style, None, None, stop_if_true
        )


@dataclass(frozen=True, slots=True)
class Note:
    """A cell note (comment)."""

    text: str
    author: str = ""


@dataclass(frozen=True, slots=True)
class Hyperlink:
    """A link to a web address, mail address or file, or to a place in the
    workbook."""

    target: str
    kind: Literal["url", "location"] = "url"
    tooltip: str | None = None

    @classmethod
    def url(cls, target: str, *, tooltip: str | None = None) -> Hyperlink:
        """A link to a web address, mail address or file path."""
        return cls(target, "url", tooltip)

    @classmethod
    def location(cls, reference: str, *, tooltip: str | None = None) -> Hyperlink:
        """A link to a cell or defined name in this workbook, such as ``"Summary!A1"``."""
        return cls(reference, "location", tooltip)


@dataclass(frozen=True, slots=True)
class DefinedName:
    """A named formula or range, such as ``DefinedName("Rate", "Settings!$B$1")``.
    Give ``sheet`` to limit the name to one sheet."""

    name: str
    formula: str
    sheet: str | None = None


@dataclass(frozen=True, slots=True)
class Image:
    """A PNG, JPEG or GIF picture."""

    data: bytes = field(repr=False)

    @classmethod
    def from_file(cls, path: str | os.PathLike[str]) -> Image:
        """Read a picture from a file."""
        with open(path, "rb") as file:
            return cls(file.read())


@dataclass(frozen=True, slots=True)
class Properties:
    """Document properties. Dates are W3CDTF text such as
    ``2026-11-25T09:30:00Z``."""

    title: str | None = None
    subject: str | None = None
    creator: str | None = None
    description: str | None = None
    keywords: str | None = None
    category: str | None = None
    last_modified_by: str | None = None
    created: str | None = None
    modified: str | None = None
