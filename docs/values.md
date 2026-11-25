---
title: Values
description: The Python types of cell values and formulas.
---

## Types

| Cell content | Python type |
|---|---|
| Empty | `None` |
| `TRUE` / `FALSE` | `bool` |
| Integer | `int`, of any size |
| Other number | `float`, or `Decimal` with `numbers="exact"` |
| Text | `str` |
| Formatted text | `RichText` |
| Date | `datetime.date` |
| Date and time | `datetime.datetime` |
| Time of day | `datetime.time` |
| Duration | `datetime.timedelta` |
| Error | `ErrorValue`, such as `ErrorValue.DIV0` |

The number format of a cell decides its date kind. A date format with a time
part that it hides, such as 12:00 in a `yyyy-mm-dd` cell, reads as
`datetime.datetime`, so nothing is lost. A serial without a Python date, such
as Excel's 1900-02-29, raises `ConversionError`; open the workbook with
`dates="serial"` to read serial numbers.

When you write a date or time to a cell without a number format, the cell
gets a default format for its kind, so it reads back as the same type.

## Exact numbers

Excel stores numbers as 64-bit floats. A file can hold a number with more
digits; CrabXL keeps such numbers exactly and saves them unchanged. Open with
`numbers="exact"` to read every non-integer as a `Decimal` with the exact text
of the file. Write a `Decimal` to store its exact text.

## Formulas

A cell's `value` is the cached result of its formula. `formula` returns the
`Formula` or `None`.

```python
sheet["C1"].value = xl.Formula("A1+B1")   # The leading = is optional.
sheet["C1"].formula                        # Formula(text='A1+B1')
sheet["D1"].value = "=A1"                  # Text, not a formula.
```

Text never becomes a formula. A new formula has no cached result: its value
is `None` until Excel or `book.calculate()` calculates it. Save with
`recalculate_on_open=True` to make Excel calculate every formula when it opens
the file.
