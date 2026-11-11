---
title: Migration from openpyxl
description: Replace openpyxl with CrabXL and learn the differences.
---

## Change the import

CrabXL uses the openpyxl 3.1.5 module layout and call names. Change the import
and keep the rest of your code.

```python
# Before
import openpyxl
from openpyxl.styles import Font

# After
import crabxl as openpyxl
from crabxl.styles import Font
```

Each public `openpyxl.<module>` has a `crabxl.<module>` with the same classes
and functions.

## What is the same

- `Workbook`, `load_workbook`, worksheets and cells.
- Values, dates, formulas, rich text and styles.
- Tables, filters, conditional formatting, data validation, comments,
  hyperlinks, protection, print settings and defined names.
- Images, charts, chartsheets, pivot tables, external links and VBA projects.
- The normal, read-only and write-only modes.
- Paths and file-like objects for input and output.

CrabXL runs the openpyxl 3.1.5 test suite without changes. The tests of the
public API pass.

## What is different

- CrabXL preserves the parts of a loaded file that you do not change. openpyxl
  writes the full file again and drops the parts that it does not know.
- CrabXL keeps the names of VBA, external link and comment parts. It also
  keeps the calculation chain if you do not change formulas.
- When you change a part that holds content CrabXL does not model, that
  content is dropped on save, as openpyxl does.
- In write-only mode, set the worksheet views and sheet properties before the
  first `append`.
- To open an `.xlsm` or `.xltm` file, set `keep_vba=True`.
- Close a loaded workbook with `close()` when you are done. This releases the
  source file.

## What is not supported

- The private modules and attributes of openpyxl, for example
  `openpyxl.reader.excel.ExcelReader`, `openpyxl.writer.excel`,
  `openpyxl.worksheet._reader` and `cell._style`. The Rust core does this work.
- Chart data and pivot table results are not calculated. Formulas are
  calculated only when you save with `calculate=True`; openpyxl cannot do this.
- `quotePrefix` and `pivotButton` on row and column dimensions.
