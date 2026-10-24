---
title: CrabXL for Python
description: An XLSX library with an openpyxl-compatible API and a Rust core.
---

CrabXL reads, writes and edits XLSX files. It uses the openpyxl API, so most
openpyxl code works after you change the import. The CrabXL Rust core does the
work. openpyxl is not a run-time dependency.

CrabXL is alpha software. An unsupported feature raises an explicit error. It
does not drop data. CrabXL does not calculate formulas.

## Install

```sh
python -m pip install --pre crabxl
```

Wheels are available for CPython 3.11–3.15 on Linux, Windows and macOS.

## Use

Change the import. Keep the rest of your openpyxl code.

```python
import crabxl as openpyxl

book = openpyxl.load_workbook("input.xlsx")
sheet = book.active
sheet["A1"] = "Updated"
book.save("output.xlsx")
book.close()
```

## Limits

- Open and save files by path. File-like objects are not supported.
- Open `.xlsm` and `.xltm` files with `keep_vba=True`.

More pages are in preparation.
