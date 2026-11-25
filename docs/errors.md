---
title: Errors
description: The exceptions CrabXL raises and what they mean.
---

Every CrabXL error derives from `CrabXLError` and from the built-in exception
that matches its meaning. Each has `sheet`, `cell` and `part` attributes when
the location is known. File-system failures raise the built-in `OSError`
subclasses, such as `FileNotFoundError`.

| Exception | Also a | Raised when |
|---|---|---|
| `FileFormatError` | `ValueError` | The file is not a valid XLSX package, or it is damaged. |
| `InvalidInputError` | `ValueError` | An argument is invalid: a bad reference, shape, name or value, or a value outside an Excel limit. |
| `NotFoundError` | `LookupError` | A sheet, table, defined name or other item does not exist. |
| `ConversionError` | `TypeError` | A value does not have the requested type. |
| `UnsupportedError` | | The operation cannot be done without losing data. |
| `LimitExceededError` | | A safety limit stopped reading a file. |
| `MemoryLimitError` | `MemoryError` | The memory budget was reached. A subclass of `LimitExceededError`. |
| `StateError` | | The object is closed or finished, or a call comes in the wrong order. |

```python
import crabxl as xl

try:
    book = xl.Workbook.open(upload, limits="strict")
except (xl.FileFormatError, xl.LimitExceededError) as error:
    print("rejected:", error)
```

## Saves that would lose data

A save raises `UnsupportedError` when it would remove content that CrabXL
cannot keep, for example unknown attributes in a table you changed, or a
digital signature that your edit invalidates. The message names the content.
To save without it, open the workbook with `data_loss="allow"`.
