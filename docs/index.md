---
title: CrabXL for Python
description: Install the crabxl package, then create, edit and stream XLSX workbooks.
---

CrabXL reads, writes and edits Excel XLSX files. The Rust core does the work,
so CrabXL is fast and uses little memory. The API is fully typed.

## Install

```sh
pip install crabxl
```

Or with uv:

```sh
uv add crabxl
```

CrabXL needs CPython 3.13 or newer. Wheels of its native module are available
for Linux, Windows and macOS.

## Choose an entry point

| Class | Use it to | Memory |
|---|---|---|
| `Workbook` | Create a workbook, or open one and change it. | The sheets you use. |
| `Reader` | Read large files row by row. | One batch of rows. |
| `Writer` | Write large files row by row. | One row. |

All three use the same values, styles and errors.

## Create a workbook

```python
import crabxl as xl

header = xl.Style(font=xl.Font(bold=True), fill=xl.Fill("DDEBF7"))

with xl.Workbook() as book:
    sheet = book.worksheets.add("Sales")
    sheet.append(["Region", "Q1", "Q2", "Total"], style=header)
    sheet.extend(
        [
            ["North", 120.5, 98, xl.Formula("B2+C2")],
            ["South", 80, 95, xl.Formula("B3+C3")],
        ]
    )
    sheet.columns("A:D").width = 14
    sheet.freeze_panes = "A2"
    book.save("sales.xlsx")
```

## Edit a file

```python
import crabxl as xl

with xl.Workbook.open("sales.xlsx") as book:
    sheet = book.worksheets["Sales"]
    total = sheet["D2"].value  # The cached result of the formula.
    sheet.rows("3").insert()  # D4 now reads =B4+C4.
    sheet["A3:C3"].values = [["East", 60, 70]]
    book.save("sales.xlsx")  # Atomic, even over the source.
```

A save copies every part you did not change. When a save would remove content
that CrabXL cannot keep, it raises `UnsupportedError` instead.

## Stream a large file

```python
import crabxl as xl

with xl.Reader.open("events.xlsx") as reader:
    for row in reader.worksheets["Events"].iter_rows(columns="A:C", skip=1):
        event_id, kind, amount = row
```

## Next steps

- [Workbooks](workbooks.md): sheets, ranges, layout, tables and other objects.
- [Values](values.md): the Python types of cell values and formulas.
- [Styles](styles.md): fonts, fills, borders and number formats.
- [Streaming](streaming.md): `Reader` and `Writer`.
- [Errors](errors.md): the exceptions CrabXL raises.
- [openpyxl interface](openpyxl/index.md): the crabxl-openpyxl package runs
  openpyxl code, on Python 3.9 and newer.
