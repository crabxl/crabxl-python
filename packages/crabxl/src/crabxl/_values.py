"""Cell value types."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, Final, cast, override

if TYPE_CHECKING:
    from .styles import Font

__all__ = ["CellInput", "ErrorValue", "Formula", "RichText", "TextRun", "Value"]


@dataclass(frozen=True, slots=True)
class Formula:
    """A formula. The text is stored without its leading ``=``.

    >>> Formula("=SUM(A1:A3)").text
    'SUM(A1:A3)'
    >>> str(Formula("A1*2"))
    '=A1*2'

    Strings are never formulas: assign a ``Formula`` to write one.
    """

    text: str

    def __init__(self, text: str) -> None:
        # super() fails in a slotted dataclass before Python 3.14.
        object.__init__(self)
        given = cast("object", text)  # Checked at run time for untyped callers.
        if not isinstance(given, str):
            raise TypeError("A formula is text")
        body = text[1:] if text.startswith("=") else text
        if not body.strip():
            from .errors import InvalidInputError

            raise InvalidInputError("A formula cannot be empty")
        object.__setattr__(self, "text", body)

    @override
    def __str__(self) -> str:
        return f"={self.text}"


_KNOWN_ERRORS: Final = (
    "#NULL!",
    "#DIV/0!",
    "#VALUE!",
    "#REF!",
    "#NAME?",
    "#NUM!",
    "#N/A",
    "#GETTING_DATA",
    "#SPILL!",
    "#CALC!",
)


@dataclass(frozen=True, slots=True)
class ErrorValue:
    """A cell error such as ``#DIV/0!``.

    The common codes are class attributes: ``ErrorValue.DIV0``,
    ``ErrorValue.NA`` and so on. Unknown codes that start with ``#`` are kept.
    """

    code: str

    def __post_init__(self) -> None:
        code = cast("object", self.code)  # Checked at run time for untyped callers.
        if not (isinstance(code, str) and code.startswith("#") and len(code) > 1):
            from .errors import InvalidInputError

            raise InvalidInputError(f"{self.code!r} is not an error code")

    @override
    def __str__(self) -> str:
        return self.code

    @property
    def is_known(self) -> bool:
        """Whether the code is one of the codes Excel defines."""
        return self.code in _KNOWN_ERRORS

    NULL: ClassVar[ErrorValue]
    DIV0: ClassVar[ErrorValue]
    VALUE: ClassVar[ErrorValue]
    REF: ClassVar[ErrorValue]
    NAME: ClassVar[ErrorValue]
    NUM: ClassVar[ErrorValue]
    NA: ClassVar[ErrorValue]
    SPILL: ClassVar[ErrorValue]
    CALC: ClassVar[ErrorValue]


ErrorValue.NULL = ErrorValue("#NULL!")
ErrorValue.DIV0 = ErrorValue("#DIV/0!")
ErrorValue.VALUE = ErrorValue("#VALUE!")
ErrorValue.REF = ErrorValue("#REF!")
ErrorValue.NAME = ErrorValue("#NAME?")
ErrorValue.NUM = ErrorValue("#NUM!")
ErrorValue.NA = ErrorValue("#N/A")
ErrorValue.SPILL = ErrorValue("#SPILL!")
ErrorValue.CALC = ErrorValue("#CALC!")


@dataclass(frozen=True, slots=True)
class TextRun:
    """One run of rich text: text with an optional font. Font attributes
    that are not set come from the cell style."""

    text: str
    font: Font | None = None


@dataclass(frozen=True, slots=True)
class RichText:
    """Text made of runs with their own fonts."""

    runs: tuple[TextRun, ...]

    def __init__(self, runs: tuple[TextRun, ...] | list[TextRun]) -> None:
        # super() fails in a slotted dataclass before Python 3.14.
        object.__init__(self)
        object.__setattr__(self, "runs", tuple(runs))

    @override
    def __str__(self) -> str:
        return "".join(run.text for run in self.runs)

    @property
    def text(self) -> str:
        """The plain text."""
        return str(self)


type Value = (
    None
    | bool
    | int
    | float
    | Decimal
    | str
    | RichText
    | _dt.datetime
    | _dt.date
    | _dt.time
    | _dt.timedelta
    | ErrorValue
)
"""The value of a cell; for a formula cell, its cached result."""

type CellInput = Value | Formula
"""What a cell write accepts: a value or a formula."""
