---
title: Optimized modes
description: Read and write large files in read-only and write-only mode.
---

This page is adapted from the [openpyxl 3.1.5 documentation](https://openpyxl.readthedocs.io/en/3.1/) (MIT license). The calls are the same in CrabXL.

## Read-only mode

Sometimes, you will need to open or write extremely large XLSX files,
and the common routines in CrabXL won't be able to handle that load.
Fortunately, there are two modes that enable you to read and write unlimited
amounts of data with (near) constant memory consumption.

Introducing `ReadOnlyWorksheet`:

```python
from crabxl import load_workbook

wb = load_workbook(filename="large_file.xlsx", read_only=True)
ws = wb["big_data"]

for row in ws.rows:
    for cell in row:
        print(cell.value)

# Close the workbook after reading
wb.close()
```

> **Warning:** 
> * `ReadOnlyWorksheet` is read-only
>
> * Unlike a normal workbook, a read-only workbook will use lazy loading.
>   The workbook must be explicitly closed with the `close()` method.

Cells returned are not regular `Cell` but
`ReadOnlyCell`.

## Worksheet dimensions

Read-only mode relies on applications and libraries that created the file
providing correct information about the worksheets, specifically the used
part of it, known as the dimensions. Some applications set this incorrectly.
You can check the apparent dimensions of a worksheet using
`ws.calculate_dimension()`. If this returns a range that you know is
incorrect, say `A1:A1` then simply resetting the max_row and max_column
attributes should allow you to work with the file:

```python
ws.reset_dimensions()
```

## Write-only mode

Here again, the regular `Worksheet` has been replaced
by a faster alternative, the `WriteOnlyWorksheet`.

```python
>>> from crabxl import Workbook
>>> wb = Workbook(write_only=True)
>>> ws = wb.create_sheet()
>>>
>>> # now we'll fill it with 100 rows x 200 columns
>>>
>>> for irow in range(100):
...     ws.append(['%d' % i for i in range(200)])
>>> # save the file
>>> wb.save('new_big_file.xlsx')
```

If you want to have cells with styles or comments then use a `WriteOnlyCell`

```python
>>> from crabxl import Workbook
>>> wb = Workbook(write_only = True)
>>> ws = wb.create_sheet()
>>> from crabxl.cell import WriteOnlyCell
>>> from crabxl.comments import Comment
>>> from crabxl.styles import Font
>>> cell = WriteOnlyCell(ws, value="hello world")
>>> cell.font = Font(name='Courier', size=36)
>>> cell.comment = Comment(text="A comment", author="Author's Name")
>>> ws.append([cell, 3.14, None])
>>> wb.save('write_only_file.xlsx')
```

This will create a write-only workbook with a single sheet, and append
a row of 3 cells: one text cell with a custom font and a comment, a
floating-point number, and an empty cell (which will be discarded
anyway).

> **Warning:** 
> * Unlike a normal workbook, a newly-created write-only workbook
>   does not contain any worksheets; a worksheet must be specifically
>   created with the `create_sheet()` method.
>
> * In a write-only workbook, rows can only be added with
>   `append()`. It is not possible to write (or read) cells at
>   arbitrary locations with `cell()` or `iter_rows()`.
>
> * It can export unlimited amount of data (even more than Excel can
>   handle actually), while keeping memory usage under 10Mb.
>
> * A write-only workbook can only be saved once. After
>   that, every attempt to save the workbook or append() to an existing
>   worksheet will raise an `WorkbookAlreadySaved`
>   exception.
>
> * Everything that appears in the file before the actual cell data must be created
>   before cells are added because it must written to the file before then.
>   For example, `freeze_panes` should be set before cells are added.

## Differences in CrabXL

- In write-only mode, you can add tables, data validation, conditional
  formatting, print settings and merged cells at any time before you save.
- Set the worksheet views (for example `freeze_panes`) and the sheet
  properties before the first `append`. A change after the first row raises
  `ValueError`. openpyxl ignores such a change.
- Read-only mode streams rows with bounded memory. To limit the memory for
  shared text, see [memory limits](memory.md).
