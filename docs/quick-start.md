---
title: Quick start
description: Create, read and edit a workbook with CrabXL for Python.
---

## Create a workbook

```python
from crabxl import Workbook
from crabxl.styles import Font

book = Workbook()
sheet = book.active
sheet.title = "Sales"
sheet.append(["Month", "Amount"])
sheet.append(["January", 1200])
sheet.append(["February", 1350])
sheet["A1"].font = Font(bold=True)
sheet["B4"] = "=SUM(B2:B3)"
book.save("sales.xlsx")
```

## Read a workbook

```python
from crabxl import load_workbook

book = load_workbook("sales.xlsx")
for month, amount in book["Sales"].iter_rows(min_row=2, values_only=True):
    print(month, amount)
book.close()
```

CrabXL does not calculate formulas. To get the cached result of a formula, set
`data_only=True`. Excel stores the cached result when it saves the file.

## Edit a workbook

```python
from crabxl import load_workbook

book = load_workbook("sales.xlsx")
sheet = book["Sales"]
sheet.insert_rows(2)
sheet["A2"] = "December"
sheet["B2"] = 900
book.save("sales.xlsx")
book.close()
```

CrabXL preserves the parts of the file that you do not change.
