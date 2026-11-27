"""Exceptions raised by CrabXL.

Every CrabXL error derives from :class:`CrabXLError` and from the built-in
exception that matches its meaning, so ``except ValueError`` and
``except KeyError``-style handlers keep working. File-system failures raise the
built-in :class:`OSError` subclasses unchanged.
"""

from __future__ import annotations

__all__ = [
    "ConversionError",
    "CrabXLError",
    "FileFormatError",
    "InvalidInputError",
    "LimitExceededError",
    "MemoryLimitError",
    "NotFoundError",
    "StateError",
    "UnsupportedError",
]


class CrabXLError(Exception):
    """Base class of every CrabXL error.

    Attributes give the location of the problem when it is known.
    """

    #: The sheet name, or ``None``.
    sheet: str | None
    #: The cell in A1 notation, or ``None``.
    cell: str | None
    #: The package part, such as ``xl/worksheets/sheet1.xml``, or ``None``.
    part: str | None

    def __init__(
        self,
        message: str,
        *,
        sheet: str | None = None,
        cell: str | None = None,
        part: str | None = None,
    ) -> None:
        super().__init__(message)
        self.sheet = sheet
        self.cell = cell
        self.part = part


class FileFormatError(CrabXLError, ValueError):
    """The file is not a valid XLSX package, or it is damaged."""


class InvalidInputError(CrabXLError, ValueError):
    """An argument is invalid: a bad reference, shape, name or value, or a
    value outside an Excel limit."""


class NotFoundError(CrabXLError, LookupError):
    """A sheet, table, defined name or other named item does not exist."""


class ConversionError(CrabXLError, TypeError):
    """A cell value does not have the requested type."""


class UnsupportedError(CrabXLError):
    """The operation cannot be done without losing data, or the file holds
    content that the operation cannot handle."""


class LimitExceededError(CrabXLError):
    """A safety limit was reached while reading a file."""


class MemoryLimitError(LimitExceededError, MemoryError):
    """The memory budget was reached."""


class StateError(CrabXLError):
    """The object cannot do this now: it is closed, finished, or the
    operation comes in the wrong order."""
