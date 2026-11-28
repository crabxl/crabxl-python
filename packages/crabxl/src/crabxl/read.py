"""Streaming reads with bounded memory.

>>> import crabxl as xl
>>> with xl.Reader.open("events.xlsx") as reader:  # doctest: +SKIP
...     for row in reader.worksheets["Events"].iter_rows(columns="A:C", skip=1):
...         event_id, kind, amount = row
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Self, overload, override

from crabxl_bindings import _native
from crabxl_bindings._native import ApiReader

from ._values import Formula, Value
from .errors import NotFoundError, StateError
from .workbook import Dates, Limits, Numbers, Source, _open

if TYPE_CHECKING:
    from types import TracebackType

__all__ = ["Reader", "Row", "WorksheetReader", "WorksheetReaders"]


class Row(Sequence[Value]):
    """One row of values, dense from its first column, with ``None`` for
    empty cells. It behaves like a tuple."""

    __slots__ = ("_index", "_values", "_formulas")

    # One Row per row read: skip the empty object.__init__ call.
    def __init__(  # pyright: ignore[reportMissingSuperCall]
        self,
        index: int,
        values: tuple[Value, ...],
        formulas: tuple[str | None, ...] | None,
    ) -> None:
        # Zero-based internally; `number` is what users see.
        self._index = index
        self._values = values
        self._formulas = formulas

    @property
    def number(self) -> int:
        """The row number as Excel shows it."""
        return self._index + 1

    @property
    def values(self) -> tuple[Value, ...]:
        """The values as a tuple."""
        return self._values

    @property
    def formulas(self) -> tuple[Formula | None, ...]:
        """The formula of each cell, or ``None``."""
        if self._formulas is None:
            return (None,) * len(self._values)
        return tuple(None if text is None else Formula(text) for text in self._formulas)

    @overload
    def __getitem__(self, index: int) -> Value: ...
    @overload
    def __getitem__(self, index: slice) -> tuple[Value, ...]: ...
    @override
    def __getitem__(self, index: int | slice) -> Value | tuple[Value, ...]:
        return self._values[index]

    @override
    def __len__(self) -> int:
        return len(self._values)

    @override
    def __iter__(self) -> Iterator[Value]:
        return iter(self._values)

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Row):
            return (self._index, self._values) == (other._index, other._values)
        return isinstance(other, tuple) and self._values == other

    @override
    def __hash__(self) -> int:
        return hash((self._index, self._values))

    @override
    def __repr__(self) -> str:
        return f"Row(number={self.number}, values={self._values!r})"


class Reader:
    """A forward-only reader for workbooks of any size.

    Each iterator reads its own stream, so several can run at once.
    """

    __slots__ = ("_native", "_closed")

    def __init__(self, native: ApiReader, /) -> None:
        """Use :meth:`Reader.open`."""
        super().__init__()
        self._native = native
        self._closed = False

    @classmethod
    def open(
        cls,
        source: Source,
        *,
        limits: Limits = "default",
        numbers: Numbers = "float",
        dates: Dates = "native",
    ) -> Self:
        """Open a workbook for reading. See :meth:`crabxl.Workbook.open` for
        the options."""
        path, data = _open(cls, source)
        return cls(
            _native.ApiReader.open(
                path, data, limits, numbers == "exact", dates == "serial"
            )
        )

    @property
    def sheet_names(self) -> list[str]:
        """The names of every sheet, in tab order."""
        self._check()
        names: list[str] = self._native.sheet_names()
        return names

    def _check(self) -> None:
        if self._closed:
            raise StateError("The reader is closed")

    @property
    def worksheets(self) -> WorksheetReaders:
        """The worksheets by name or position."""
        self._check()
        return WorksheetReaders(self)

    def close(self) -> None:
        """Close the reader. Open iterators stop, and later use raises
        StateError."""
        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class WorksheetReaders:
    """The worksheets of a :class:`Reader`: index by name or position, or
    iterate."""

    __slots__ = ("_reader",)

    def __init__(self, reader: Reader) -> None:
        super().__init__()
        self._reader = reader

    @property
    def names(self) -> list[str]:
        """The sheet names, in tab order."""
        return self._reader.sheet_names

    def __getitem__(self, key: str | int) -> WorksheetReader:
        names = self._reader.sheet_names
        if isinstance(key, int):
            try:
                return WorksheetReader(self._reader, names[key])
            except IndexError:
                raise NotFoundError(f"No sheet at position {key}") from None
        for name in names:
            if name.casefold() == key.casefold():
                return WorksheetReader(self._reader, name)
        raise NotFoundError(f"No sheet named {key!r}", sheet=key)

    def __iter__(self) -> Iterator[WorksheetReader]:
        return (
            WorksheetReader(self._reader, name) for name in self._reader.sheet_names
        )

    def __len__(self) -> int:
        return len(self._reader.sheet_names)


class WorksheetReader:
    """The rows of one worksheet."""

    __slots__ = ("_reader", "name")

    def __init__(self, reader: Reader, name: str) -> None:
        super().__init__()
        self._reader = reader
        #: The sheet name.
        self.name = name

    def iter_batches(
        self,
        size: int = 1024,
        *,
        columns: str | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> Iterator[list[Row]]:
        """The rows in lists of up to ``size``. See :meth:`iter_rows`."""
        stream = self._reader._native.rows(self.name, columns, skip, limit, size)
        try:
            while True:
                if self._reader._closed:
                    raise StateError("The reader is closed")
                batch = stream.next_batch()
                if batch is None:
                    return
                yield [
                    Row(index, values, formulas) for index, values, formulas in batch
                ]
        finally:
            stream.close()

    def iter_rows(
        self,
        *,
        columns: str | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> Iterator[Row]:
        """The rows that hold at least one cell, in order.

        :param columns: Only these columns, such as ``"A:D"``. Every row then
            has exactly these columns.
        :param skip: Skip this many rows from the top, such as a header row.
        :param limit: Stop after this many rows of the sheet.
        """
        for batch in self.iter_batches(1024, columns=columns, skip=skip, limit=limit):
            yield from batch

    @override
    def __repr__(self) -> str:
        return f"<crabxl.WorksheetReader {self.name!r}>"
