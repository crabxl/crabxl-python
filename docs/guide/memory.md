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
- `AutoMemory` calculates a memory limit from the available memory.

## Open untrusted files

CrabXL guards against files built to exhaust memory or CPU: ZIP bombs, deeply
nested XML and huge XML tokens. The guards apply when you load a workbook, not
to data you write. The default opens every file Excel writes. Choose another
preset with `limits`:

```python
from crabxl import load_workbook

# Uploads from strangers: tighter guards and memory caps.
book = load_workbook("upload.xlsx", limits="strict")
# Files you trust: no guards. The memory limit still applies.
book = load_workbook("trusted.xlsx", limits="unlimited")
```

For code that cannot pass arguments, such as `pandas.read_excel`, set the
`CRABXL_LIMITS` environment variable to `strict` or `unlimited`.

A file that exceeds a guard raises `crabxl.LimitExceededError`, a `ValueError`
whose message names the guard. To change one guard, pass `ResourceLimits`:

```python
from crabxl import ResourceLimits, load_workbook

book = load_workbook("input.xlsx", limits=ResourceLimits(max_expansion_ratio=1000))
```

| Guard | Default | `strict` |
|---|---|---|
| `max_expansion_ratio` (entries over 1 MiB) | 100 | 100 |
| `max_total_uncompressed_bytes` | 16 GiB | 1 GiB |
| `max_part_bytes` | 4 GiB | 256 MiB |
| `max_archive_entries` | 1,000,000 | 10,000 |
| `max_xml_depth` | 256 | 256 |
| `max_xml_event_bytes` | 10 MiB | 1 MiB |

## Set the compression level

`save` accepts `compression_level` from 0 to 9. A low level saves faster and
makes a larger file.

```python
book.save("output.xlsx", compression_level=1)
```
