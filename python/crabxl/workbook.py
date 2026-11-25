"""The editable workbook: ``Workbook``, ``Worksheet`` and ``Range``."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from typing import IO, TYPE_CHECKING, Literal, TypeAlias, TypeVar, cast, overload

from . import _native
from ._features import (
    ConditionalFormat,
    DataValidation,
    DefinedName,
    Hyperlink,
    Image,
    Note,
    Properties,
    Table,
)
from ._native import ApiWorkbook
from ._values import CellInput, Formula, Value
from .errors import ConversionError, InvalidInputError, NotFoundError
from .styles import Style

if TYPE_CHECKING:
    from types import TracebackType

__all__ = [
    "Columns",
    "Range",
    "Rows",
    "Source",
    "Target",
    "Visibility",
    "Workbook",
    "Worksheet",
    "Worksheets",
]

Source: TypeAlias = "str | os.PathLike[str] | bytes | IO[bytes]"
"""Where a workbook comes from: a path, the file's bytes or a binary file."""
Target: TypeAlias = "str | os.PathLike[str] | IO[bytes]"
"""Where a workbook goes: a path (saved atomically) or a binary file."""
Visibility: TypeAlias = Literal["visible", "hidden", "very_hidden"]
Limits: TypeAlias = Literal["default", "strict", "unlimited"]
T = TypeVar("T")

_CELL = re.compile(r"^\$?([A-Za-z]{1,3})\$?([0-9]{1,7})$")
# A reference already in normal form: one cell, uppercase, no $, no leading zero.
_NORMAL_CELL = re.compile(r"[A-Z]{1,3}[1-9][0-9]{0,6}")


def _split(ref: str) -> tuple[int, int]:
    """Zero-based row and column of an A1 cell reference."""
    match = _CELL.match(ref)
    if not match:
        raise InvalidInputError(f"{ref!r} is not a cell reference")
    letters, digits = match.groups()
    column = 0
    for letter in letters.upper():
        column = column * 26 + ord(letter) - 64
    return int(digits) - 1, column - 1


def _name(row: int, column: int) -> str:
    letters = ""
    column += 1
    while column:
        column, rest = divmod(column - 1, 26)
        letters = chr(65 + rest) + letters
    return f"{letters}{row + 1}"


def _bounds(ref: str) -> tuple[int, int, int, int]:
    first, _, second = ref.partition(":")
    top, left = _split(first)
    bottom, right = _split(second) if second else (top, left)
    return min(top, bottom), min(left, right), max(top, bottom), max(left, right)


def _normalize(ref: str) -> str:
    if _NORMAL_CELL.fullmatch(ref):
        return ref
    top, left, bottom, right = _bounds(ref)
    start, end = _name(top, left), _name(bottom, right)
    return start if start == end else f"{start}:{end}"


def _open(cls: type, source: Source) -> tuple[str | None, bytes | None]:
    if isinstance(source, (str, os.PathLike)):
        return os.fspath(source), None
    if isinstance(source, (bytes, bytearray, memoryview)):
        return None, bytes(source)
    if hasattr(source, "read"):
        return None, source.read()
    raise TypeError(
        f"{cls.__name__} opens a path, bytes or a binary file, not {type(source).__name__}"
    )


class Workbook:
    """An XLSX workbook to create, or to open, change and save.

    A workbook opened from a file loads each sheet on first use. A save copies
    every part you did not change, and it raises
    :class:`~crabxl.errors.UnsupportedError` instead of dropping content that
    CrabXL cannot keep. Saving to a path is atomic, so saving over the file you
    opened is safe.

    >>> import crabxl as xl
    >>> with xl.Workbook() as book:
    ...     sheet = book.worksheets.add("Data")
    ...     sheet.append(["Region", "Amount"])
    ...     sheet["B2"].value = 12.5
    ...     data = book.to_bytes()
    """

    __slots__ = ("_native",)
    _native: ApiWorkbook

    def __init__(self, *, dates: Literal["native", "serial"] = "native") -> None:
        """A new workbook with no sheets. Add a worksheet before you save."""
        self._native = _native.ApiWorkbook.create(dates == "serial")

    @classmethod
    def open(
        cls,
        source: Source,
        *,
        limits: Limits = "default",
        memory: int | None = None,
        data_loss: Literal["reject", "allow"] = "reject",
        numbers: Literal["float", "exact"] = "float",
        dates: Literal["native", "serial"] = "native",
    ) -> Workbook:
        """Open a workbook.

        :param limits: Input safety limits. Use ``"strict"`` for files from
            untrusted sources and ``"unlimited"`` only for files you trust.
        :param memory: A memory budget in bytes for loaded sheets and edits.
        :param data_loss: ``"allow"`` lets a save remove content that CrabXL
            cannot keep, such as an invalidated digital signature.
        :param numbers: ``"exact"`` returns non-integers as
            :class:`decimal.Decimal` with the exact text of the file.
        :param dates: ``"serial"`` returns dates and times as serial numbers.
        """
        path, data = _open(cls, source)
        book = cls.__new__(cls)
        if path is not None:
            book._native = _native.ApiWorkbook.open_path(
                path, limits, memory, data_loss, numbers == "exact", dates == "serial"
            )
        else:
            book._native = _native.ApiWorkbook.open_bytes(
                data, limits, memory, data_loss, numbers == "exact", dates == "serial"
            )
        return book

    # ----- Lifetime -----

    def close(self) -> None:
        """Release the source file and memory. Later use raises StateError."""
        self._native.close()

    @property
    def closed(self) -> bool:
        """Whether the workbook is closed."""
        return self._native.is_closed()

    def __enter__(self) -> Workbook:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # ----- Saving -----

    def save(
        self,
        target: Target,
        *,
        compression: int | None = None,
        recalculate_on_open: bool = False,
    ) -> None:
        """Save to a path or a binary file. A save to a path is atomic: the
        file is either replaced completely or left unchanged.

        :param compression: ZIP level 0 (store) to 9. The default is 6.
        :param recalculate_on_open: Ask Excel to recalculate every formula
            when it opens the file.
        """
        if isinstance(target, (str, os.PathLike)):
            self._native.save_path(os.fspath(target), compression, recalculate_on_open)
        elif hasattr(target, "write"):
            target.write(
                self.to_bytes(
                    compression=compression, recalculate_on_open=recalculate_on_open
                )
            )
        else:
            raise TypeError(
                f"Save to a path or a binary file, not {type(target).__name__}"
            )

    def to_bytes(
        self, *, compression: int | None = None, recalculate_on_open: bool = False
    ) -> bytes:
        """The workbook as XLSX bytes."""
        return bytes(self._native.save_bytes(compression, recalculate_on_open))

    def calculate(self) -> None:
        """Calculate every formula and store the results as cached values."""
        self._native.calculate()

    # ----- Sheets -----

    @property
    def worksheets(self) -> Worksheets:
        """The worksheets, in tab order."""
        return Worksheets(self)

    @property
    def sheet_names(self) -> list[str]:
        """The names of every sheet, including chartsheets, in tab order."""
        return self._native.sheet_names()

    @property
    def active_sheet(self) -> str | None:
        """The name of the sheet shown when the file opens."""
        return self._native.active_sheet()

    @active_sheet.setter
    def active_sheet(self, name: str) -> None:
        self._native.set_active_sheet(name)

    # ----- Workbook data -----

    @property
    def defined_names(self) -> DefinedNames:
        """The defined names, including print areas."""
        return DefinedNames(self)

    @property
    def properties(self) -> Properties:
        """The document properties."""
        return Properties(**self._native.properties())

    @properties.setter
    def properties(self, properties: Properties) -> None:
        self._native.set_properties(
            {
                name: getattr(properties, name)
                for name in Properties.__dataclass_fields__
            }
        )

    def __repr__(self) -> str:
        if self.closed:
            return "<crabxl.Workbook closed>"
        return f"<crabxl.Workbook sheets={self.sheet_names!r}>"


class Worksheets:
    """The worksheets of a workbook: index by name or position, iterate, and
    add, copy, move or remove."""

    __slots__ = ("_book",)

    def __init__(self, book: Workbook) -> None:
        self._book = book

    @property
    def names(self) -> list[str]:
        """The worksheet names, in tab order."""
        return self._book._native.worksheet_names()

    def __len__(self) -> int:
        return len(self.names)

    def __iter__(self) -> Iterator[Worksheet]:
        return (Worksheet(self._book, name) for name in self.names)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and any(
            name.casefold() == other.casefold() for other in self.names
        )

    def __getitem__(self, key: str | int) -> Worksheet:
        names = self.names
        if isinstance(key, int):
            try:
                return Worksheet(self._book, names[key])
            except IndexError:
                raise NotFoundError(f"No worksheet at position {key}") from None
        for name in names:
            if name.casefold() == key.casefold():
                return Worksheet(self._book, name)
        raise NotFoundError(f"No worksheet named {key!r}", sheet=key)

    def get(self, name: str) -> Worksheet | None:
        """A worksheet by name, or ``None``."""
        return self[name] if name in self else None

    def add(self, name: str, *, index: int | None = None) -> Worksheet:
        """Add an empty worksheet, at the end or at a zero-based position.

        Names have 1 to 31 characters, cannot contain ``: \\ / ? * [ ]`` and are
        unique without regard to case.
        """
        return Worksheet(self._book, self._book._native.add_worksheet(name, index))

    def copy(self, source: str, name: str) -> Worksheet:
        """Copy a worksheet completely: cells, styles, layout, views, objects
        and notes. Table names get unique suffixes."""
        return Worksheet(self._book, self._book._native.copy_worksheet(source, name))

    def remove(self, name: str) -> None:
        """Remove a sheet."""
        self._book._native.remove_sheet(name)

    def move(self, name: str, index: int) -> None:
        """Move a sheet to a zero-based tab position."""
        self._book._native.move_sheet(name, index)

    def __repr__(self) -> str:
        return f"<crabxl.Worksheets {self.names!r}>"


class Worksheet:
    """A worksheet. Index it with A1 references to get :class:`Range` views:
    ``sheet["B2"]``, ``sheet["A1:D10"]``.

    Reading never changes the sheet: a missing cell reads as ``None``.
    """

    __slots__ = ("_book", "_name")

    def __init__(self, book: Workbook, name: str) -> None:
        self._book = book
        self._name = name

    @property
    def _native(self) -> ApiWorkbook:
        return self._book._native

    @property
    def name(self) -> str:
        """The sheet name. Assign to rename the sheet."""
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._native.rename_sheet(self._name, name)
        self._name = name

    @property
    def visibility(self) -> Visibility:
        """Whether the sheet tab shows."""
        return self._native.visibility(self._name)  # type: ignore[return-value]

    @visibility.setter
    def visibility(self, visibility: Visibility) -> None:
        self._native.set_visibility(self._name, visibility)

    def __getitem__(self, ref: str) -> Range:
        return Range(self, _normalize(ref))

    @property
    def used_range(self) -> Range | None:
        """The smallest range that holds every present cell, or ``None``."""
        ref = self._native.used_range(self._name)
        return None if ref is None else Range(self, ref)

    def append(self, row: Iterable[CellInput], *, style: Style | None = None) -> None:
        """Append a row after the last row that has cells."""
        self._native.append_rows(self._name, (row,), style)

    def extend(
        self, rows: Iterable[Iterable[CellInput]], *, style: Style | None = None
    ) -> None:
        """Append rows after the last row that has cells."""
        self._native.append_rows(self._name, rows, style)

    # ----- Layout -----

    def rows(self, span: str) -> Rows:
        """Whole rows, such as ``"5"`` or ``"5:7"`` (row numbers as Excel shows them)."""
        return Rows(self, span)

    def columns(self, span: str) -> Columns:
        """Whole columns, such as ``"B"`` or ``"B:D"``."""
        return Columns(self, span)

    @property
    def freeze_panes(self) -> str | None:
        """The first unfrozen cell, such as ``"A2"`` to freeze the top row,
        or ``None``. Assign ``None`` to unfreeze."""
        return self._native.frozen_panes(self._name)

    @freeze_panes.setter
    def freeze_panes(self, cell: str | None) -> None:
        self._native.freeze_panes(self._name, cell)

    # ----- Objects -----

    @property
    def merges(self) -> Merges:
        """The merged ranges."""
        return Merges(self)

    @property
    def tables(self) -> Tables:
        """The tables."""
        return Tables(self)

    @property
    def validations(self) -> Validations:
        """The data validation rules."""
        return Validations(self)

    @property
    def conditional_formats(self) -> ConditionalFormats:
        """The conditional formats."""
        return ConditionalFormats(self)

    @property
    def images(self) -> Images:
        """The pictures."""
        return Images(self)

    def protect(self, password: str | None = None) -> None:
        """Protect the sheet against edits. Cells whose style has
        ``Protection(locked=False)`` stay editable."""
        self._native.protect(self._name, password)

    def unprotect(self) -> None:
        """Remove sheet protection."""
        self._native.unprotect(self._name)

    @property
    def is_protected(self) -> bool:
        """Whether the sheet is protected."""
        return self._native.is_protected(self._name)

    def __repr__(self) -> str:
        return f"<crabxl.Worksheet {self._name!r}>"


_KINDS: tuple[type, ...] = (int, float, str, bool)


class Range:
    """A live view of a rectangle of cells. Creating a range reads nothing.

    Single-cell properties (``value``, ``formula``, ``style``, ``note``,
    ``hyperlink``) read one cell and raise :class:`InvalidInputError` for a
    larger range. Assigning ``value`` or ``style`` to a larger range sets every
    cell; ``values`` reads and writes the whole rectangle.
    """

    __slots__ = ("_sheet", "_ref")

    def __init__(self, sheet: Worksheet, ref: str) -> None:
        self._sheet = sheet
        self._ref = ref

    @property
    def ref(self) -> str:
        """The range in A1 notation."""
        return self._ref

    @property
    def is_cell(self) -> bool:
        """Whether the range is one cell."""
        return ":" not in self._ref

    @property
    def shape(self) -> tuple[int, int]:
        """The number of rows and columns."""
        top, left, bottom, right = _bounds(self._ref)
        return bottom - top + 1, right - left + 1

    def _cell(self, what: str) -> str:
        if not self.is_cell:
            raise InvalidInputError(
                f"{what} needs one cell, not {self._ref}", sheet=self._sheet.name
            )
        return self._ref

    @property
    def _native(self) -> ApiWorkbook:
        return self._sheet._book._native

    # ----- Values -----

    @property
    def value(self) -> Value:
        """The value of the cell; for a formula cell, its cached result."""
        return self._native.value(self._sheet.name, self._cell("value"))

    @value.setter
    def value(self, value: CellInput) -> None:
        if self.is_cell:
            self._native.set_value(self._sheet.name, self._ref, value)
        else:
            self._native.fill(self._sheet.name, self._ref, value)

    @property
    def values(self) -> tuple[tuple[Value, ...], ...]:
        """The values row by row, with ``None`` for empty cells."""
        return self._native.values(self._sheet.name, self._ref)

    @values.setter
    def values(self, rows: Sequence[Sequence[CellInput]]) -> None:
        self._native.set_values(self._sheet.name, self._ref, rows)

    @property
    def formula(self) -> Formula | None:
        """The formula of the cell, or ``None``."""
        text = self._native.formula(self._sheet.name, self._cell("formula"))
        return None if text is None else Formula(text)

    @overload
    def value_as(self, kind: type[bool]) -> bool: ...
    @overload
    def value_as(self, kind: type[int]) -> int: ...
    @overload
    def value_as(self, kind: type[float]) -> float: ...
    @overload
    def value_as(self, kind: type[str]) -> str: ...
    @overload
    def value_as(self, kind: type[T]) -> T: ...
    def value_as(self, kind: type[T]) -> T:
        """The value of the cell as ``kind``. An ``int`` reads as ``float``
        when you ask for ``float``; other mismatches raise ConversionError."""
        value = self.value
        wanted: type[object] = kind
        if wanted is float and type(value) is int:
            return cast(T, float(value))
        # A bool is an int in Python, but not a number in a cell.
        is_bool = isinstance(value, bool)
        if isinstance(value, kind) and not (wanted is int and is_bool):
            return value
        raise ConversionError(
            f"{self._sheet.name}!{self._ref} holds {type(value).__name__}, not {kind.__name__}",
            sheet=self._sheet.name,
            cell=self._ref,
        )

    def iter_rows(self) -> Iterator[tuple[Value, ...]]:
        """The rows of values, read in chunks."""
        top, left, bottom, right = _bounds(self._ref)
        chunk = 4096
        for start in range(top, bottom + 1, chunk):
            end = min(bottom, start + chunk - 1)
            yield from self._native.values(
                self._sheet.name, f"{_name(start, left)}:{_name(end, right)}"
            )

    def clear(self) -> None:
        """Clear values and formulas. Styles stay."""
        self._native.clear(self._sheet.name, self._ref)

    # ----- Style -----

    @property
    def style(self) -> Style:
        """The style of the cell. Assign to give every cell this style."""
        return self._native.style(self._sheet.name, self._cell("style"))

    @style.setter
    def style(self, style: Style) -> None:
        self._native.set_style(self._sheet.name, self._ref, style)

    def map_style(self, change: Callable[[Style], Style]) -> None:
        """Change the style of each cell: ``change`` gets the current style
        and returns the new one, such as
        ``lambda s: s.replace(number_format="0.00")``."""
        top, left, bottom, right = _bounds(self._ref)
        cache: dict[Style, Style] = {}
        for row in range(top, bottom + 1):
            for column in range(left, right + 1):
                cell = _name(row, column)
                current = self._native.style(self._sheet.name, cell)
                updated = cache.get(current)
                if updated is None:
                    updated = cache[current] = change(current)
                if updated != current:
                    self._native.set_style(self._sheet.name, cell, updated)

    # ----- Annotations -----

    @property
    def note(self) -> Note | None:
        """The note of the cell. Assign ``None`` to remove it."""
        found = self._native.note(self._sheet.name, self._cell("note"))
        return None if found is None else Note(*found)

    @note.setter
    def note(self, note: Note | None) -> None:
        cell = self._cell("note")
        if note is None:
            self._native.remove_note(self._sheet.name, cell)
        else:
            self._native.set_note(self._sheet.name, cell, note.text, note.author)

    @property
    def hyperlink(self) -> Hyperlink | None:
        """The hyperlink of the cell. Assign ``None`` to remove it."""
        found = self._native.hyperlink(self._sheet.name, self._cell("hyperlink"))
        if found is None:
            return None
        kind, target, tooltip = found
        return Hyperlink(target, kind, tooltip)  # type: ignore[arg-type]

    @hyperlink.setter
    def hyperlink(self, link: Hyperlink | None) -> None:
        cell = self._cell("hyperlink")
        if link is None:
            self._native.remove_hyperlink(self._sheet.name, cell)
        else:
            self._native.set_hyperlink(
                self._sheet.name, cell, link.kind, link.target, link.tooltip
            )

    def __repr__(self) -> str:
        return f"<crabxl.Range {self._sheet.name}!{self._ref}>"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Range)
            and other._sheet._book is self._sheet._book
            and (
                other._sheet.name,
                other._ref,
            )
            == (self._sheet.name, self._ref)
        )

    def __hash__(self) -> int:
        return hash((self._sheet.name, self._ref))


class Rows:
    """Whole rows of a worksheet: height, visibility, insertion and deletion."""

    __slots__ = ("_sheet", "_span")

    def __init__(self, sheet: Worksheet, span: str) -> None:
        self._sheet = sheet
        self._span = span

    @property
    def height(self) -> float | None:
        """The height of the first row in points, or ``None`` for the default.
        Assign to set every row."""
        return self._sheet._native.row_height(
            self._sheet.name, self._span.split(":")[0]
        )

    @height.setter
    def height(self, points: float) -> None:
        self._sheet._native.set_row_height(self._sheet.name, self._span, points)

    def hide(self, hidden: bool = True) -> None:
        """Hide or show the rows."""
        self._sheet._native.set_rows_hidden(self._sheet.name, self._span, hidden)

    def insert(self) -> None:
        """Insert as many empty rows as the span holds, before its first row.
        Formulas, names, ranges and objects that refer to moved cells follow
        them. Content that cannot follow raises UnsupportedError first."""
        self._sheet._native.insert_rows(self._sheet.name, self._span)

    def delete(self) -> None:
        """Delete the rows. References into them become ``#REF!``."""
        self._sheet._native.delete_rows(self._sheet.name, self._span)

    def __repr__(self) -> str:
        return f"<crabxl.Rows {self._sheet.name}!{self._span}>"


class Columns:
    """Whole columns of a worksheet: width, visibility, insertion and deletion."""

    __slots__ = ("_sheet", "_span")

    def __init__(self, sheet: Worksheet, span: str) -> None:
        self._sheet = sheet
        self._span = span

    @property
    def width(self) -> float | None:
        """The width of the first column in characters, or ``None`` for the
        default. Assign to set every column."""
        return self._sheet._native.column_width(
            self._sheet.name, self._span.split(":")[0]
        )

    @width.setter
    def width(self, characters: float) -> None:
        self._sheet._native.set_column_width(self._sheet.name, self._span, characters)

    def hide(self, hidden: bool = True) -> None:
        """Hide or show the columns."""
        self._sheet._native.set_columns_hidden(self._sheet.name, self._span, hidden)

    def insert(self) -> None:
        """Insert empty columns before the first column. See :meth:`Rows.insert`."""
        self._sheet._native.insert_columns(self._sheet.name, self._span)

    def delete(self) -> None:
        """Delete the columns. See :meth:`Rows.delete`."""
        self._sheet._native.delete_columns(self._sheet.name, self._span)

    def __repr__(self) -> str:
        return f"<crabxl.Columns {self._sheet.name}!{self._span}>"


# ----- Collections -----


class Merges:
    """The merged ranges of a worksheet."""

    __slots__ = ("_sheet",)

    def __init__(self, sheet: Worksheet) -> None:
        self._sheet = sheet

    def _refs(self) -> list[str]:
        return self._sheet._native.merged_ranges(self._sheet.name)

    def __iter__(self) -> Iterator[str]:
        return iter(self._refs())

    def __len__(self) -> int:
        return len(self._refs())

    def __contains__(self, ref: object) -> bool:
        return isinstance(ref, str) and _normalize(ref) in self._refs()

    def add(self, ref: str) -> None:
        """Merge a range. Only its top-left cell keeps a value."""
        self._sheet._native.merge(self._sheet.name, ref)

    def remove(self, ref: str) -> None:
        """Split a merged range."""
        self._sheet._native.unmerge(self._sheet.name, ref)


class Tables:
    """The tables of a worksheet."""

    __slots__ = ("_sheet",)

    def __init__(self, sheet: Worksheet) -> None:
        self._sheet = sheet

    def _all(self) -> list[Table]:
        return [
            Table(name, ref, style, totals_row=totals)
            for name, ref, style, totals in self._sheet._native.tables(self._sheet.name)
        ]

    def __iter__(self) -> Iterator[Table]:
        return iter(self._all())

    def __len__(self) -> int:
        return len(self._all())

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and any(
            t.name.casefold() == name.casefold() for t in self._all()
        )

    def __getitem__(self, name: str) -> Table:
        for table in self._all():
            if table.name.casefold() == name.casefold():
                return table
        raise NotFoundError(f"No table named {name!r}", sheet=self._sheet.name)

    def add(self, table: Table) -> None:
        """Add a table."""
        self._sheet._native.add_table(
            self._sheet.name, table.name, table.ref, table.style, table.banded_rows
        )

    def remove(self, name: str) -> None:
        """Remove a table. Its cells keep their values."""
        self._sheet._native.remove_table(self._sheet.name, name)


class Validations:
    """The data validation rules of a worksheet."""

    __slots__ = ("_sheet",)

    def __init__(self, sheet: Worksheet) -> None:
        self._sheet = sheet

    def __iter__(self) -> Iterator[tuple[tuple[str, ...], str | None]]:
        """Each rule as its ranges and its first formula or list."""
        return (
            (tuple(ranges), first)
            for ranges, first in self._sheet._native.validations(self._sheet.name)
        )

    def __len__(self) -> int:
        return len(self._sheet._native.validations(self._sheet.name))

    def add(self, rule: DataValidation) -> None:
        """Add a rule."""
        self._sheet._native.add_validation(
            self._sheet.name,
            rule.kind,
            list(rule.ranges),
            rule.first,
            rule.second,
            rule.comparison,
            rule.allow_blank,
            rule.prompt,
            rule.error,
        )

    def remove(self, ref: str) -> int:
        """Remove every rule that applies to a cell of ``ref``. Returns the count."""
        return self._sheet._native.remove_validations(self._sheet.name, ref)


class ConditionalFormats:
    """The conditional formats of a worksheet."""

    __slots__ = ("_sheet",)

    def __init__(self, sheet: Worksheet) -> None:
        self._sheet = sheet

    def __iter__(self) -> Iterator[tuple[tuple[str, ...], tuple[str, ...]]]:
        """Each rule as its ranges and its formulas, in priority order."""
        return (
            (tuple(ranges), tuple(formulas))
            for ranges, formulas in self._sheet._native.conditional_formats(
                self._sheet.name
            )
        )

    def __len__(self) -> int:
        return len(self._sheet._native.conditional_formats(self._sheet.name))

    def add(self, rule: ConditionalFormat) -> None:
        """Add a rule with the lowest priority."""
        self._sheet._native.add_conditional_format(
            self._sheet.name,
            rule.ref,
            rule.kind,
            rule.style,
            rule.value,
            rule.second,
            rule.comparison,
            rule.stop_if_true,
        )


class Images:
    """The pictures of a worksheet."""

    __slots__ = ("_sheet",)

    def __init__(self, sheet: Worksheet) -> None:
        self._sheet = sheet

    def __len__(self) -> int:
        return self._sheet._native.image_count(self._sheet.name)

    def add(self, image: Image, *, at: str) -> None:
        """Place a picture with its top-left corner on a cell, at its natural size."""
        self._sheet._native.add_image(self._sheet.name, image.data, at)


class DefinedNames:
    """The defined names of a workbook."""

    __slots__ = ("_book",)

    def __init__(self, book: Workbook) -> None:
        self._book = book

    def _all(self) -> list[DefinedName]:
        return [DefinedName(*entry) for entry in self._book._native.defined_names()]

    def __iter__(self) -> Iterator[DefinedName]:
        return iter(self._all())

    def __len__(self) -> int:
        return len(self._all())

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and any(
            d.name.casefold() == name.casefold() for d in self._all()
        )

    def __getitem__(self, name: str) -> DefinedName:
        for defined in self._all():
            if defined.name.casefold() == name.casefold() and defined.sheet is None:
                return defined
        raise NotFoundError(f"No defined name {name!r}")

    def add(self, name: DefinedName) -> None:
        """Add a name, or replace one with the same name and scope."""
        self._book._native.add_defined_name(name.name, name.formula, name.sheet)

    def remove(self, name: str) -> None:
        """Remove a workbook-wide name."""
        self._book._native.remove_defined_name(name)
