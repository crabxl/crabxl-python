---
title: Memory limits
description: Set memory limits and shared text storage when you load a workbook.
---

CrabXL manages its own memory. These options are CrabXL extensions. openpyxl
does not have them.

## Set a memory limit

Set `max_memory_bytes` to limit the memory that CrabXL manages for a workbook.
The memory limit is not a limit for the full process.

```python
from crabxl import load_workbook

book = load_workbook("input.xlsx", max_memory_bytes=512 * 1024 * 1024)
```

If an operation needs more memory than the limit, CrabXL raises an error.

## Set resource options

Use `ResourceOptions` for detailed limits.

```python
from crabxl import ResourceOptions, SharedStringOptions, load_workbook

options = ResourceOptions(
    shared_strings=SharedStringOptions(storage="disk"),
)
book = load_workbook("input.xlsx", read_only=True, resource_options=options)
```

- `SharedStringOptions.storage` is `"auto"`, `"memory"` or `"disk"`. With
  `"disk"`, CrabXL keeps the shared text of the workbook in a temporary file.
- `ResourceLimits` sets limits for the file size, the number of parts and the
  size of rows and batches.
- `AutoMemory` calculates a memory limit from the available memory.

## Set the compression level

`save` accepts `compression_level` from 0 to 9. A low level saves faster and
makes a larger file.

```python
book.save("output.xlsx", compression_level=1)
```
