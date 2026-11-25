---
title: Supported features
description: The openpyxl features that CrabXL for Python can read, create and edit.
---

| Feature | Read | Create | Edit |
|---|---|---|---|
| Values, dates and formulas | Yes | Yes | Yes |
| Rich text | Yes | Yes | Yes |
| Styles, named styles and themes | Yes | Yes | Yes |
| Merged cells, row and column dimensions | Yes | Yes | Yes |
| Row and column insertion and deletion, range moves | – | – | Yes |
| Hyperlinks and comments | Yes | Yes | Yes |
| Tables and auto filters | Yes | Yes | Yes |
| Conditional formatting and data validation | Yes | Yes | Yes |
| Sheet and workbook protection | Yes | Yes | Yes |
| Views, freeze panes and sheet properties | Yes | Yes | Yes |
| Print settings, headers and footers | Yes | Yes | Yes |
| Defined names, print areas and print titles | Yes | Yes | Yes |
| Document properties | Yes | Yes | Yes |
| Images and drawings | Yes | Yes | Yes |
| Charts and chartsheets | Yes | Yes | Yes |
| Pivot tables | Yes | Yes | Yes |
| External links | Yes | Yes | Yes |
| VBA projects | Yes | – | Yes |
| Scenarios | Yes | Yes | Yes |
| Templates (`.xltx`, `.xltm`) | Yes | Yes | Yes |

All features are available in normal, read-only and write-only mode. See
[optimized modes](guide/optimized.md).
You cannot save a workbook in read-only mode.

`wb.save(path, calculate=True)` calculates formulas, except array formulas,
and saves each result as the cached value that `data_only=True` reads.
CrabXL does not calculate chart data or pivot table results.
