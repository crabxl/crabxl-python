---
title: CrabXL for Python
description: Install the crabxl package and use it in place of openpyxl.
---

## Install

```sh
python -m pip install --pre crabxl
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

## Limits

- An unsupported call raises `NotImplementedError`. CrabXL does not fall back
  to openpyxl.
- `load_workbook` and `save` accept a path only. File-like objects are not
  supported.
- To open an `.xlsm` or `.xltm` file, set `keep_vba=True`.
- CrabXL does not calculate formulas. With `data_only=True`, a formula cell
  contains the cached result from the file.
