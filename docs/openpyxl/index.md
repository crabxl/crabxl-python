---
title: openpyxl interface
description: Use crabxl.openpyxl in place of openpyxl.
---

`crabxl.openpyxl` gives you the openpyxl 3.1.5 API. The Rust core reads,
writes and edits the XLSX files. It is faster and uses less memory than
openpyxl.

## Use

Import `crabxl.openpyxl` in place of `openpyxl`. The calls are the same.

```python
import crabxl.openpyxl as openpyxl

book = openpyxl.load_workbook("input.xlsx")
book.active["A1"] = "Updated"
book.save("output.xlsx")
book.close()
```

This interface follows openpyxl's behavior, also where the native `crabxl`
API differs. For example, it moves only cells when you insert rows, it saves
without content it cannot model, and text that starts with `=` becomes a
formula. Use the [native API](../index.md) for new code.

## Next steps

- [Quick start](quick-start.md): create, read and edit a workbook.
- [Migration from openpyxl](migration.md): what is the same and what is
  different.
- [Supported features](support.md): the features that CrabXL can read, create
  and edit.

The user guide is adapted from the
[openpyxl 3.1.5 documentation](https://openpyxl.readthedocs.io/en/3.1/) (MIT
license).
