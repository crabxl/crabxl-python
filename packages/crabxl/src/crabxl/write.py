"""Streaming writes with bounded memory.

>>> import crabxl as xl
>>> with xl.Writer.create("export.xlsx") as writer:  # doctest: +SKIP
...     sheet = writer.worksheets.add("Events")
...     sheet.freeze_panes = "A2"
...     sheet.append(["id", "amount"], style=xl.Style(font=xl.Font(bold=True)))
...     sheet.extend((n, n * 1.5) for n in range(1_000_000))
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator
from typing import TYPE_CHECKING, Self, cast, override

from crabxl_bindings import _native
from crabxl_bindings._native import ApiWriter

from ._features import ConditionalFormat, DataValidation
from ._values import CellInput
from .errors import NotFoundError, UnsupportedError
from .styles import Style
from .workbook import Target, _split

if TYPE_CHECKING:
    from types import TracebackType

__all__ = [
    "AddOnly",
    "ColumnSpanWriter",
    "WorksheetWriter",
    "WorksheetWriters",
    "Writer",
]


class Writer:
    """Writes a new workbook row by row. Rows spool to temporary files, so
    memory stays small for any number of rows.

    Used as a context manager, the writer finishes when the block ends and
    discards its output when the block raises.
    """

    __slots__ = ("_native", "_target", "_names", "_done", "_frozen", "_widths")

    def __init__(self, native: ApiWriter, target: Target, /) -> None:
        """Use :meth:`Writer.create`."""
        super().__init__()
        self._native = native
        self._target = target
        self._names: list[str] = []
        self._done = False
        self._frozen: dict[str, str] = {}
        self._widths: dict[tuple[str, int], float] = {}

    @classmethod
    def create(
        cls,
        target: Target,
        *,
        compression: int | None = None,
        temp_directory: str | os.PathLike[str] | None = None,
    ) -> Self:
        """Write to a path (replaced atomically on finish) or a binary file.

        :param compression: ZIP level 0 (store) to 9. The default is 6.
        :param temp_directory: Where the row spools go.
        """
        path = os.fspath(target) if isinstance(target, (str, os.PathLike)) else None
        temp = None if temp_directory is None else os.fspath(temp_directory)
        return cls(_native.ApiWriter.create(path, compression, temp), target)

    @property
    def worksheets(self) -> WorksheetWriters:
        """The worksheets: ``add`` one, or get an open one by name."""
        return WorksheetWriters(self)

    def finish(self) -> None:
        """Finish every sheet and write the workbook."""
        if self._done:
            return
        self._done = True
        if isinstance(self._target, (str, os.PathLike)):
            self._native.finish()
        else:
            _ = self._target.write(self._native.finish_bytes())

    def abort(self) -> None:
        """Discard everything written. The target is not touched."""
        self._done = True
        self._native.abort()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if kind is None:
            self.finish()
        else:
            self.abort()


class WorksheetWriters:
    """The worksheets of a :class:`Writer`: add one, get one by name, or
    iterate."""

    __slots__ = ("_writer",)

    def __init__(self, writer: Writer) -> None:
        super().__init__()
        self._writer = writer

    @property
    def names(self) -> list[str]:
        """The sheet names, in tab order."""
        return list(self._writer._names)

    def add(self, name: str) -> WorksheetWriter:
        """Start a worksheet after the last one."""
        self._writer._native.add_worksheet(name)
        self._writer._names.append(name)
        return WorksheetWriter(self._writer, name)

    def __getitem__(self, name: str) -> WorksheetWriter:
        for other in self._writer._names:
            if other.casefold() == name.casefold():
                return WorksheetWriter(self._writer, other)
        raise NotFoundError(f"No sheet named {name!r}", sheet=name)

    def __iter__(self) -> Iterator[WorksheetWriter]:
        return (WorksheetWriter(self._writer, name) for name in self._writer._names)

    def __len__(self) -> int:
        return len(self._writer._names)


class AddOnly[T]:
    """Objects of a streaming worksheet. You can add them, but not read them
    back: they are written when the sheet finishes."""

    __slots__ = ("_add",)

    def __init__(self, add: Callable[[T], None]) -> None:
        super().__init__()
        self._add = add

    def add(self, item: T) -> None:
        """Add an item."""
        self._add(item)


class WorksheetWriter:
    """Writes one worksheet. Rows go in order and cannot change once written."""

    __slots__ = ("_writer", "name")

    def __init__(self, writer: Writer, name: str) -> None:
        super().__init__()
        self._writer = writer
        #: The sheet name.
        self.name = name

    def append(self, row: Iterable[CellInput], *, style: Style | None = None) -> None:
        """Append one row, optionally giving each of its cells a style."""
        self._writer._native.append_rows(self.name, (row,), style)

    def extend(
        self, rows: Iterable[Iterable[CellInput]], *, style: Style | None = None
    ) -> None:
        """Append rows."""
        self._writer._native.append_rows(self.name, rows, style)

    def skip(self, count: int) -> None:
        """Leave rows empty before the next row."""
        self._writer._native.skip_rows(self.name, count)

    def columns(self, span: str) -> ColumnSpanWriter:
        """Whole columns, such as ``"B"`` or ``"B:D"``, to set their width."""
        return ColumnSpanWriter(self, span)

    @property
    def freeze_panes(self) -> str | None:
        """The first unfrozen cell, such as ``"A2"``, or ``None``. Set it
        before the first row."""
        return self._writer._frozen.get(self.name)

    @freeze_panes.setter
    def freeze_panes(self, cell: str) -> None:
        self._writer._native.freeze_panes(self.name, cell)
        self._writer._frozen[self.name] = cell

    @property
    def merges(self) -> AddOnly[str]:
        """The merged ranges, such as ``"D1:E1"``."""
        return AddOnly(lambda ref: self._writer._native.merge(self.name, ref))

    @property
    def validations(self) -> AddOnly[DataValidation]:
        """The data validation rules. A streaming writer accepts list rules."""
        return AddOnly(self._add_validation)

    @property
    def conditional_formats(self) -> AddOnly[ConditionalFormat]:
        """The conditional formats. A streaming writer accepts formula rules."""
        return AddOnly(self._add_conditional_format)

    def _add_validation(self, rule: DataValidation) -> None:
        if rule.kind != "list":
            raise UnsupportedError(
                "A streaming writer accepts list validations; use Workbook for others"
            )
        choices = cast("tuple[str, ...]", rule.first)
        self._writer._native.add_validation(self.name, list(choices), list(rule.ranges))

    def _add_conditional_format(self, rule: ConditionalFormat) -> None:
        if rule.kind != "formula" or rule.value is None or rule.style is None:
            raise UnsupportedError(
                "A streaming writer accepts formula rules; use Workbook for others"
            )
        self._writer._native.add_formula_format(
            self.name, list(rule.ranges), rule.value, rule.style
        )

    @override
    def __repr__(self) -> str:
        return f"<crabxl.WorksheetWriter {self.name!r}>"


class ColumnSpanWriter:
    """Whole columns of a streaming worksheet: their width."""

    __slots__ = ("_sheet", "_span", "_first", "_last")

    def __init__(self, sheet: WorksheetWriter, span: str) -> None:
        super().__init__()
        self._sheet = sheet
        self._span = span
        first, _, last = span.partition(":")
        self._first = _split(f"{first}1")[1]
        self._last = _split(f"{last or first}1")[1]

    @property
    def width(self) -> float | None:
        """The width of the first column in characters, or ``None`` for the
        default. Assign to set every column."""
        return self._sheet._writer._widths.get((self._sheet.name, self._first))

    @width.setter
    def width(self, characters: float) -> None:
        writer = self._sheet._writer
        writer._native.set_column_width(self._sheet.name, self._span, characters)
        for column in range(self._first, self._last + 1):
            writer._widths[(self._sheet.name, column)] = characters

    @override
    def __repr__(self) -> str:
        return f"<crabxl.ColumnSpanWriter {self._sheet.name}!{self._span}>"
