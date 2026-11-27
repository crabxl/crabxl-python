"""Tables, validation, conditional formats, charts, page setup, notes,
hyperlinks, names and images."""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from .styles import PartialStyle

__all__ = [
    "Chart",
    "ChartKind",
    "Comparison",
    "ConditionalFormat",
    "DataValidation",
    "DefinedName",
    "Hyperlink",
    "Image",
    "Margins",
    "Note",
    "Orientation",
    "PageSetup",
    "PlacedChart",
    "PlacedImage",
    "Properties",
    "Series",
    "Table",
    "ValidationValue",
]

type Comparison = Literal["between", "not_between", "==", "!=", ">", ">=", "<", "<="]
"""A comparison for validation and conditional formats."""


type Ranges = str | Sequence[str]
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
    totals_row: bool = False
    """Whether the last row of ``ref`` is a totals row."""


type ValidationValue = int | float | str | dt.date | dt.time | tuple[str, ...]
"""A bound, formula, source range or list of choices of a validation rule."""


@dataclass(frozen=True, slots=True)
class DataValidation:
    """A rule that limits what users can type into cells.

    Build one with a class method, such as
    ``DataValidation.list(["Yes", "No"], ranges="C2:C100")``. Rules read from a
    file come back as the same type. ``any`` rules, which only show a prompt,
    can be read but not created.
    """

    kind: Literal[
        "list",
        "list_from",
        "whole",
        "decimal",
        "text_length",
        "custom",
        "date",
        "time",
        "any",
    ]
    ranges: tuple[str, ...]
    first: ValidationValue | None
    """The choices, source range, formula or first bound."""
    second: int | float | str | dt.date | dt.time | None = None
    """The second bound of a ``between`` or ``not_between`` rule."""
    comparison: Comparison | None = None
    allow_blank: bool = True
    prompt: tuple[str, str] | None = None
    """The title and message shown when a user selects the cell."""
    error: tuple[str, str] | None = None
    """The title and message shown when the rule rejects a value."""

    @classmethod
    def list(cls, choices: Sequence[str], *, ranges: Ranges) -> DataValidation:
        """A drop-down list of fixed choices."""
        return cls("list", _ranges(ranges), tuple(str(choice) for choice in choices))

    @classmethod
    def list_from(cls, source: str, *, ranges: Ranges) -> DataValidation:
        """A drop-down list of the values in a range, such as ``"$H$1:$H$10"``."""
        return cls("list_from", _ranges(ranges), source.removeprefix("="))

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
        return cls(
            "decimal",
            _ranges(ranges),
            float(value),
            None if second is None else float(second),
            comparison,
        )

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
    def date(
        cls,
        comparison: Comparison,
        value: dt.date,
        second: dt.date | None = None,
        *,
        ranges: Ranges,
    ) -> DataValidation:
        """Dates that compare with one date, or two for ``between``."""
        return cls("date", _ranges(ranges), _day(value), _day(second), comparison)

    @classmethod
    def time(
        cls,
        comparison: Comparison,
        value: dt.time,
        second: dt.time | None = None,
        *,
        ranges: Ranges,
    ) -> DataValidation:
        """Times of day, to the second, that compare with one time, or two for
        ``between``."""
        return cls("time", _ranges(ranges), _second(value), _second(second), comparison)

    @classmethod
    def custom(cls, formula: str, *, ranges: Ranges) -> DataValidation:
        """Values for which a formula is true, such as ``"ISNUMBER(A1)"``."""
        return cls("custom", _ranges(ranges), formula.removeprefix("="))


@dataclass(frozen=True, slots=True)
class ConditionalFormat:
    """A rule that formats cells when a condition holds.

    Build one with :meth:`cell` or :meth:`formula`. Rules read from a file come
    back as the same type. Other rule types, such as color scales and data
    bars, read as ``kind="other"`` and cannot be created.
    """

    kind: Literal["cell", "formula", "other"]
    ranges: tuple[str, ...]
    value: str | None
    """The first value or the formula, without a leading ``=``."""
    style: PartialStyle | None
    second: str | None = None
    comparison: Comparison | None = None
    stop_if_true: bool = False

    @classmethod
    def cell(
        cls,
        comparison: Comparison,
        value: int | float | str,
        second: int | float | str | None = None,
        *,
        ranges: Ranges,
        style: PartialStyle,
        stop_if_true: bool = False,
    ) -> ConditionalFormat:
        """Format cells whose value compares with one value, or two for
        ``between``. Text values need quotes: ``'"Done"'``."""
        return cls(
            "cell",
            _ranges(ranges),
            _formula(value),
            style,
            None if second is None else _formula(second),
            comparison,
            stop_if_true,
        )

    @classmethod
    def formula(
        cls,
        formula: str,
        *,
        ranges: Ranges,
        style: PartialStyle,
        stop_if_true: bool = False,
    ) -> ConditionalFormat:
        """Format cells for which a formula is true. Relative references
        refer to the top-left cell of the first range."""
        return cls(
            "formula",
            _ranges(ranges),
            _formula(formula),
            style,
            None,
            None,
            stop_if_true,
        )


def _day(value: dt.date | None) -> dt.date | None:
    # A datetime is a date; keep only its calendar day.
    return dt.date(value.year, value.month, value.day) if value is not None else None


def _second(value: dt.time | None) -> dt.time | None:
    return value.replace(microsecond=0, tzinfo=None) if value is not None else None


def _formula(value: int | float | str) -> str:
    return value.removeprefix("=") if isinstance(value, str) else str(value)


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
    """Document properties. ``created`` and ``modified`` are timezone-aware
    datetimes."""

    title: str | None = None
    subject: str | None = None
    creator: str | None = None
    description: str | None = None
    keywords: str | None = None
    category: str | None = None
    last_modified_by: str | None = None
    created: dt.datetime | None = None
    modified: dt.datetime | None = None


type Orientation = Literal["portrait", "landscape"]


@dataclass(frozen=True, slots=True)
class Margins:
    """Page margins in inches."""

    left: float = 0.75
    right: float = 0.75
    top: float = 1.0
    bottom: float = 1.0
    header: float = 0.5
    footer: float = 0.5


@dataclass(frozen=True, slots=True)
class PageSetup:
    """How a worksheet prints, such as
    ``PageSetup(orientation="landscape", fit_to=(1, 0), title_rows="1")``.
    ``None`` and ``False`` keep Excel's defaults."""

    orientation: Orientation | None = None
    paper_size: int | None = None
    """Excel's paper code, such as 1 for Letter or 9 for A4."""
    scale: int | None = None
    """Print scale in percent, from 10 to 400."""
    fit_to: tuple[int, int] | None = None
    """Fit to this many pages wide and tall; 0 leaves that direction free."""
    margins: Margins = Margins()
    center_horizontally: bool = False
    center_vertically: bool = False
    grid_lines: bool = False
    print_area: str | None = None
    """The range to print, such as ``"A1:F40"``; ``None`` prints the used range."""
    title_rows: str | None = None
    """Rows to repeat at the top of each page, such as ``"1"`` or ``"1:2"``."""
    title_columns: str | None = None
    """Columns to repeat at the left of each page, such as ``"A"`` or ``"A:B"``."""


type ChartKind = Literal[
    "column", "bar", "line", "area", "pie", "doughnut", "scatter", "other"
]
"""The kind of a chart. ``"other"`` charts are read but cannot be created."""


@dataclass(frozen=True, slots=True)
class Series:
    """One data series of a chart. References name their sheet, such as
    ``"Data!$B$2:$B$9"``. A scatter chart's categories are its x values."""

    values: str
    categories: str | None = None
    title: str | None = None
    """The name shown in the legend."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", self.values.removeprefix("="))
        if self.categories is not None:
            object.__setattr__(self, "categories", self.categories.removeprefix("="))


@dataclass(frozen=True, slots=True)
class Chart:
    """A chart, such as ``Chart("column", [Series("Data!$B$2:$B$9")], title="Sales")``.
    Place it with ``sheet.charts.add(chart, at="E2:L18")``."""

    kind: ChartKind
    series: tuple[Series, ...]
    title: str | None = None
    legend: bool = True

    def __init__(
        self,
        kind: ChartKind,
        series: Sequence[Series],
        *,
        title: str | None = None,
        legend: bool = True,
    ) -> None:
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "series", tuple(series))
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "legend", legend)


@dataclass(frozen=True, slots=True)
class PlacedChart:
    """A chart on a worksheet and the cells it covers, or ``None`` for a
    chart placed by position."""

    chart: Chart
    at: str | None


@dataclass(frozen=True, slots=True)
class PlacedImage:
    """A picture on a worksheet and the cell of its top-left corner, or
    ``None`` for a picture placed by position."""

    image: Image
    at: str | None
