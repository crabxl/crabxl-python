---
title: CrabXL for Python
description: Install the crabxl package and use it in place of openpyxl.
---

CrabXL for Python gives you the openpyxl 3.1.5 API. The Rust core reads, writes
and edits the XLSX files. It is faster and uses less memory than openpyxl.

## Install

```sh
python -m pip install crabxl
```

Wheels are available for CPython 3.11–3.15 on Linux, Windows and macOS.

## Use

Import `crabxl` in place of `openpyxl`. The calls are the same.

```python
import crabxl as openpyxl

book = openpyxl.load_workbook("input.xlsx")
book.active["A1"] = "Updated"
book.save("output.xlsx")
book.close()
```

## Next steps

- [Quick start](quick-start.md): create, read and edit a workbook.
- [Migration from openpyxl](migration.md): what is the same and what is
  different.
- [Supported features](support.md): the features that CrabXL can read, create
  and edit.
