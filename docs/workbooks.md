---
title: Workbooks
description: Open, change and save workbooks; work with sheets, ranges, layout and objects.
---

## Open and save

`Workbook()` creates a workbook with no sheets. `Workbook.open` opens a path,
the bytes of a file (any bytes-like object) or a binary file object.

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
copy = book.worksheets.copy(
    "Sales", "Sales copy"
)  # Everything, including notes and tables.
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
sheet["B2"].value = 12.5  # One cell.
sheet["B2:B10"].value = 0  # Every cell of the range.
sheet["A1:C2"].values = [["a", "b", "c"], [1, 2, 3]]  # The exact shape.
rows = sheet["A1:C10"].values  # A tuple of row tuples.
price = sheet["B2"].value_as(float)  # Raises ConversionError for other types.
sheet["A1:C10"].clear()  # Values and formulas; styles stay.
```

`append(row)` and `extend(rows)` add rows after the last row that has cells.
`used_range` is the smallest range that holds every cell.

## Layout

```python
sheet.columns("A:C").width = 16
sheet.rows("1").height = 24
sheet.columns("D").hidden = True
sheet.freeze_panes = "B2"  # Freeze the first row and column. None unfreezes.
sheet.merges.add("E1:G1")
```

## Insert and delete rows and columns

```python
sheet.rows("5:7").insert()  # Three rows before row 5.
sheet.columns("B").delete()
```

Formulas on every sheet, defined names, tables, rules, merges, row heights,
charts, drawing anchors and internal hyperlinks follow the moved cells.
References into deleted cells become `#REF!`. If content cannot follow, such
as a pivot table on the sheet, the edit raises `UnsupportedError` and nothing
changes.

## Objects

```python
sheet.tables.add(xl.Table("Sales", "A1:D101", totals_row=True))
sheet.validations.add(xl.DataValidation.list(["North", "South"], ranges="A2:A100"))
sheet.conditional_formats.add(
    xl.ConditionalFormat.cell(
        ">", 1000, ranges="D2:D100", style=xl.PartialStyle(fill=xl.Fill("FFC7CE"))
    )
)
sheet["B2"].note = xl.Note("Preliminary", author="Finance")
sheet["A1"].hyperlink = xl.Hyperlink.url("https://example.com")
sheet.images.add(xl.Image.from_file("logo.png"), at="F2")
sheet.protect("password")
book.defined_names.add(xl.DefinedName("TaxRate", "Settings!$B$1"))
book.properties = xl.Properties(title="Q3 sales")
```

Every object is an immutable value, and reading gives back the same type:
`list(sheet.validations)` is a list of `DataValidation`. To remove a note or
hyperlink, assign `None`. Document dates, `Properties.created` and
`Properties.modified`, are timezone-aware `datetime` values. The cells of a
totals row hold text, a formula such as `SUBTOTAL(109,D2:D100)`, or nothing.
`book.calculate()` calculates every formula and stores the results.

Each collection removes by range: `sheet.validations.remove("A2:A9")`,
`sheet.conditional_formats.remove(...)`, `sheet.images.remove(...)` and
`sheet.charts.remove(...)` remove what applies to, or starts in, those cells
and return the count. Iterating `sheet.images` gives `PlacedImage` values:
the picture and the cell of its top-left corner. Iterating `sheet.charts`
gives `PlacedChart` values: the chart and the cells it covers.

Date and time rules take `datetime.date` and `datetime.time` values (`import datetime as dt`):

```python
sheet.validations.add(
    xl.DataValidation.date(
        "between", dt.date(2026, 1, 1), dt.date(2026, 12, 31), ranges="C2:C100"
    )
)
```

## Charts

```python
sheet.charts.add(
    xl.Chart(
        "column",
        [xl.Series("Sales!$B$2:$B$13", categories="Sales!$A$2:$A$13", title="Revenue")],
        title="Revenue by month",
    ),
    at="E2:L18",
)
```

A chart covers the range of cells given as `at`. The kinds are
`"column"`, `"bar"`, `"line"`, `"area"`, `"pie"`, `"doughnut"` and
`"scatter"`; the categories of a scatter series are its x values. Series refer
to cells, and Excel draws the chart from them when it opens the file. Charts of
other kinds in a file read as `kind="other"` and are kept on save.

## Filters, groups and tabs

```python
sheet.auto_filter = "A1:D100"  # Filter buttons on row 1; None removes them.
sheet.rows("2:10").outline_level = 1  # Group rows; 0 ungroups.
sheet.columns("C:D").outline_level = 1
sheet.tab_color = "C00000"
```

A worksheet filter cannot overlap a table, because tables have their own.

## Printing

```python
sheet.page_setup = xl.PageSetup(
    orientation="landscape",
    paper_size=9,  # A4
    fit_to=(1, 0),  # One page wide, any number of pages tall.
    margins=xl.Margins(left=0.5, right=0.5),
    print_area="A1:F40",
    title_rows="1",  # Repeat row 1 on every page.
)
```

`sheet.page_setup` reads the same value back. Assigning it keeps page breaks,
headers and footers.
