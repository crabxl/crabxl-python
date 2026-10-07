"""Value conversion and one-based public coordinate adapters."""

import re
from datetime import date, datetime, time, timedelta

from ._native import (
    cell_address,
    column_index,
    column_letters,
    finite_range,
)

_ERRORS = {
    "#NULL!",
    "#DIV/0!",
    "#VALUE!",
    "#REF!",
    "#NAME?",
    "#NUM!",
    "#N/A",
    "#GETTING_DATA",
}
_ADDRESS = re.compile(r"^\$?([A-Za-z]+)\$?([1-9][0-9]*)$")


def _column(value):
    if isinstance(value, int):
        if not 1 <= value <= 16384:
            raise ValueError("Column index must be between 1 and 16384")
        return value
    if isinstance(value, str) and value.isascii() and value.isalpha():
        return column_index(value)
    raise ValueError("Invalid column index")


def _letters(column):
    return column_letters(_column(column))


def _address(value):
    if not isinstance(value, str):
        raise TypeError("A cell coordinate must be a string")
    return cell_address(value)


def _range(value):
    if not isinstance(value, str):
        raise TypeError("A cell range must be a string")
    return finite_range(value)


def _encode(value):
    if value is None:
        return "empty", None
    if isinstance(value, bool):
        return "bool", value
    if isinstance(value, int):
        return "int", str(value)
    if isinstance(value, float):
        return "float", value
    if isinstance(value, str):
        value = value[:32767]
        if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
            from .utils.exceptions import IllegalCharacterError

            raise IllegalCharacterError("Text contains an illegal XML character")
        if value.startswith("=") and len(value) > 1:
            return "formula", value[1:]
        return ("error" if value in _ERRORS else "text"), value
    from .worksheet.formula import ArrayFormula, DataTableFormula

    if isinstance(value, ArrayFormula):
        return "array", {"ref": value.ref, "text": value.text}
    if isinstance(value, DataTableFormula):
        return "table", dict(vars(value))
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            raise TypeError("Excel does not support timezones in datetimes")
        return "datetime", (
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
        )
    if isinstance(value, date):
        return "date", (value.year, value.month, value.day)
    if isinstance(value, time):
        if value.tzinfo is not None:
            raise TypeError("Excel does not support timezones in times")
        return "time", (value.hour, value.minute, value.second, value.microsecond)
    if isinstance(value, timedelta):
        return "duration", (value.days, value.seconds, value.microseconds)
    raise ValueError(f"Cannot convert {type(value).__name__} to Excel")


def _decode(tagged):
    kind, value = tagged
    if kind in ("array", "table"):
        from .worksheet.formula import ArrayFormula, DataTableFormula

        return (ArrayFormula if kind == "array" else DataTableFormula)(**value)
    if kind == "bigint":
        return int(value)
    if kind == "date":
        return date.fromisoformat(value)
    if kind == "datetime":
        return datetime.fromisoformat(value)
    if kind == "time":
        return time.fromisoformat(value)
    if kind == "duration":
        return timedelta(seconds=value[0], microseconds=value[1])
    return value


def _data_type(tag):
    return {
        "empty": "n",
        "bool": "b",
        "int": "n",
        "float": "n",
        "text": "s",
        "error": "e",
        "formula": "f",
        "array": "f",
        "table": "f",
    }.get(tag[0], "d")
