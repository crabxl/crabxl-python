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
from collections.abc import Iterable, Iterator
from typing import IO, TYPE_CHECKING, cast

from . import _native
from ._features import ConditionalFormat, DataValidation
from ._native import ApiWriter
from ._values import CellInput
from .errors import NotFoundError, UnsupportedError
from .styles import Style

if TYPE_CHECKING:
    from types import TracebackType

__all__ = ["Writer", "WorksheetWriter"]


class Writer:
    """Writes a new workbook row by row. Rows spool to temporary files, so
    memory stays small for any number of rows.

    Used as a context manager, the writer finishes when the block ends and
    discards its output when the block raises.
    """

    __slots__ = ("_native", "_target", "_names", "_done")
    _native: ApiWriter
    _target: str | os.PathLike[str] | IO[bytes]
    _names: list[str]
    _done: bool

    @classmethod
    def create(
        cls,
        target: str | os.PathLike[str] | IO[bytes],
        *,
        compression: int | None = None,
        temp_directory: str | os.PathLike[str] | None = None,
    ) -> Writer:
        """Write to a path (replaced atomically on finish) or a binary file.

        :param compression: ZIP level 0 (store) to 9. The default is 6.
        :param temp_directory: Where the row spools go.
        """
        writer = cls.__new__(cls)
        path = os.fspath(target) if isinstance(target, (str, os.PathLike)) else None
        temp = None if temp_directory is None else os.fspath(temp_directory)
        writer._native = _native.ApiWriter.create(path, compression, temp)
        writer._target = target
        writer._names = []
        writer._done = False
        return writer

    @property
    def worksheets(self) -> _Worksheets:
        """The worksheets: ``add`` one, or get an open one by name."""
        return _Worksheets(self)

    def finish(self) -> None:
        """Finish every sheet and write the workbook."""
        if self._done:
            return
        self._done = True
        if isinstance(self._target, (str, os.PathLike)):
            self._native.finish()
        else:
            self._target.write(bytes(self._native.finish_bytes()))

    def abort(self) -> None:
        """Discard everything written. The target is not touched."""
        self._done = True
        self._native.abort()

    def __enter__(self) -> Writer:
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


class _Worksheets:
    __slots__ = ("_writer",)

    def __init__(self, writer: Writer) -> None:
        self._writer = writer

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


class WorksheetWriter:
    """Writes one worksheet. Rows go in order and cannot change once written."""

    __slots__ = ("_writer", "name")

    def __init__(self, writer: Writer, name: str) -> None:
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

    def columns(self, span: str) -> _Columns:
        """Whole columns, such as ``"A:C"``, to set their width."""
        return _Columns(self, span)

    @property
    def freeze_panes(self) -> None:
        """Write-only: the first unfrozen cell, such as ``"A2"``. Set it
        before the first row."""
        return None

    @freeze_panes.setter
    def freeze_panes(self, cell: str) -> None:
        self._writer._native.freeze_panes(self.name, cell)

    def merge(self, ref: str) -> None:
        """Merge a range. Merges are written when the sheet finishes."""
        self._writer._native.merge(self.name, ref)

    def add_validation(self, rule: DataValidation) -> None:
        """Add a drop-down list rule."""
        if rule.kind != "list":
            raise UnsupportedError(
                "A streaming writer accepts list validations; use Workbook for others"
            )
        choices = cast("list[str]", rule.first)
        self._writer._native.add_validation(self.name, list(choices), list(rule.ranges))

    def add_conditional_format(self, rule: ConditionalFormat) -> None:
        """Add a formula rule."""
        if rule.kind != "formula":
            raise UnsupportedError(
                "A streaming writer accepts formula rules; use Workbook for others"
            )
        self._writer._native.add_formula_format(
            self.name, rule.ref, rule.value, rule.style
        )

    def __repr__(self) -> str:
        return f"<crabxl.WorksheetWriter {self.name!r}>"


class _Columns:
    __slots__ = ("_sheet", "_span")

    def __init__(self, sheet: WorksheetWriter, span: str) -> None:
        self._sheet = sheet
        self._span = span

    @property
    def width(self) -> None:
        """Write-only: the width in characters."""
        return None

    @width.setter
    def width(self, characters: float) -> None:
        self._sheet._writer._native.set_column_width(
            self._sheet.name, self._span, characters
        )
