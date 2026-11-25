---
title: Workbooks
description: Open, change and save workbooks; work with sheets, ranges, layout and objects.
---

## Open and save

`Workbook()` creates a workbook with no sheets. `Workbook.open` opens a path,
the bytes of a file or a binary file object.

```python
import crabxl as xl

book = xl.Workbook.open("report.xlsx", limits="strict")
book.save("report.xlsx")
book.close()
```

| Option of `open` | Values | Effect |
|---|---|---|
| `limits` | `"default"`, `"strict"`, `"unlimited"` | Input safety limits. Use `"strict"` for files from untrusted sources. |
| `memory` | bytes or `None` | A memory budget for loaded sheets and edits. |
| `data_loss` | `"reject"`, `"allow"` | Whether a save may remove content CrabXL cannot keep. |
| `numbers` | `"float"`, `"exact"` | `"exact"` returns non-integers as `Decimal`. |
| `dates` | `"native"`, `"serial"` | `"serial"` returns dates as serial numbers. |

`save` writes to a path or a binary file. A save to a path is atomic: the file
is replaced completely or left unchanged, and an existing file keeps its
permissions. `to_bytes()` returns the file as bytes. Saves are byte-stable:
saving the same content twice gives the same bytes.

Use a workbook as a context manager, or call `close()`. A closed workbook
raises `StateError`.

## Sheets

`book.worksheets` is an ordered collection. Index it by name (without regard
to case) or by position.

```python
sales = book.worksheets.add("Sales")
copy = book.worksheets.copy("Sales", "Sales copy")   # Everything, including notes and tables.
book.worksheets.move("Sales copy", 0)
copy.name = "Backup"
copy.visibility = "hidden"
book.active_sheet = "Sales"
book.worksheets.remove("Backup")
```

## Ranges

Index a sheet with A1 text to get a `Range`. A range is a live view: creating
it reads nothing, and reading never creates cells.

```python
sheet = book.worksheets["Sales"]
sheet["B2"].value = 12.5                    # One cell.
sheet["B2:B10"].value = 0                   # Every cell of the range.
sheet["A1:C2"].values = [["a", "b", "c"], [1, 2, 3]]   # The exact shape.
rows = sheet["A1:C10"].values               # A tuple of row tuples.
price = sheet["B2"].value_as(float)         # Raises ConversionError for other types.
sheet["A1:C10"].clear()                     # Values and formulas; styles stay.
```

`append(row)` and `extend(rows)` add rows after the last row that has cells.
`used_range` is the smallest range that holds every cell.

## Layout

```python
sheet.columns("A:C").width = 16
sheet.rows("1").height = 24
sheet.columns("D").hide()
sheet.freeze_panes = "B2"      # Freeze the first row and column. None unfreezes.
sheet.merges.add("E1:G1")
```

## Insert and delete rows and columns

```python
sheet.rows("5:7").insert()      # Three rows before row 5.
sheet.columns("B").delete()
```

Formulas on every sheet, defined names, tables, rules, merges, row heights,
charts, drawing anchors and internal hyperlinks follow the moved cells.
References into deleted cells become `#REF!`. If content cannot follow, such
as a pivot table on the sheet, the edit raises `UnsupportedError` and nothing
changes.

## Objects

```python
sheet.tables.add(xl.Table("Sales", "A1:D100"))
sheet.validations.add(xl.DataValidation.list(["North", "South"], ranges="A2:A100"))
sheet.conditional_formats.add(
    xl.ConditionalFormat.cell("D2:D100", ">", 1000, style=xl.PartialStyle(fill=xl.Fill("FFC7CE")))
)
sheet["B2"].note = xl.Note("Preliminary", author="Finance")
sheet["A1"].hyperlink = xl.Hyperlink.url("https://example.com")
sheet.images.add(xl.Image.from_file("logo.png"), at="F2")
sheet.protect("password")
book.defined_names.add(xl.DefinedName("TaxRate", "Settings!$B$1"))
book.properties = xl.Properties(title="Q3 sales")
```

Every object is an immutable value. To remove a note or hyperlink, assign
`None`. `book.calculate()` calculates every formula and stores the results.
