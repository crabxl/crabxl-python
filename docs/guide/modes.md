---
title: Workbook modes
description: Select the normal, read-only or write-only mode for a workbook.
---

CrabXL has the same three modes as openpyxl.

| Mode | Use | Call |
|---|---|---|
| Normal | Read, create and edit a workbook. | `load_workbook(path)` or `Workbook()` |
| Read-only | Stream the rows of a large workbook. | `load_workbook(path, read_only=True)` |
| Write-only | Write a large workbook row by row. | `Workbook(write_only=True)` |

## Normal mode

A loaded workbook reads cells when you first use them. When you save, CrabXL
writes only the parts that you changed. It preserves the other parts.

## Read-only mode

Read-only mode streams rows with bounded memory. You cannot save the workbook.

```python
from crabxl import load_workbook

book = load_workbook("large.xlsx", read_only=True)
for row in book.active.iter_rows(values_only=True):
    print(row)
book.close()
```

Close the workbook when you are done. This releases the file.

## Write-only mode

Write-only mode writes rows to a temporary file. Memory does not increase with
the number of rows.

```python
from crabxl import Workbook

book = Workbook(write_only=True)
sheet = book.create_sheet("Data")
sheet.freeze_panes = "A2"
sheet.append(["ID", "Name"])
for number in range(100_000):
    sheet.append([number, f"Item {number}"])
book.save("large.xlsx")
```

- Set the worksheet views and sheet properties before the first `append`. A
  change after the first row raises `ValueError`.
- You can add tables, data validation, conditional formatting, print settings
  and merged cells at any time before you save.
- You can save a write-only workbook only one time.
