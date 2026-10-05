<div align="center">

# CrabXL for Python

**A Rust-powered XLSX library with an openpyxl-compatible interface.**

[![PyPI](https://img.shields.io/pypi/v/crabxl?include_prereleases)](https://pypi.org/project/crabxl/)
[![Python](https://img.shields.io/badge/Python-3.11–3.15-blue?logo=python&logoColor=white)](https://pypi.org/project/crabxl/#files)
[![CI](https://github.com/crabxl/crabxl-python/actions/workflows/python.yml/badge.svg)](https://github.com/crabxl/crabxl-python/actions/workflows/python.yml)
[![License](https://img.shields.io/github/license/crabxl/crabxl-python)](LICENSE)

[Rust engine](https://github.com/crabxl/crabxl) · [Roadmap](docs/roadmap.md) · [Report an issue](https://github.com/crabxl/crabxl-python/issues)

</div>

## About

CrabXL supports reading, creating, and editing XLSX files, including streaming
`read_only` and `write_only` modes. Supported calls follow openpyxl conventions:
use `import crabxl as openpyxl` to migrate compatible code. Processing runs in the
shared Rust engine; openpyxl is not a runtime dependency.

**Currently alpha.** Full openpyxl compatibility remains in progress. Complete
style and rich-text object APIs, advanced worksheet features, and some loaded
structural edits are still unimplemented. Unsupported operations raise explicit
errors. Formula calculation is not provided. See the [roadmap](docs/roadmap.md)
for remaining work.

## Installation

```sh
python -m pip install --pre crabxl
```

Wheels are available for **CPython 3.11–3.15** on Linux x86_64/ARM64, Windows
x86_64, and macOS Intel/Apple Silicon. Python 3.15 validation currently uses its
release candidate. Source builds require Rust 1.99 or newer and Maturin.

## Usage

### Create and edit

```python
from crabxl import Workbook, load_workbook

book = Workbook()
sheet = book.active
sheet["A1"] = "Hello"
sheet.append([1, 2, 3])
book.save("example.xlsx")
book.close()

book = load_workbook("example.xlsx")
try:
    book.active["A1"] = "Updated"
    book.save("updated.xlsx")
finally:
    book.close()
```

### Streaming modes

```python
from crabxl import Workbook, load_workbook

book = load_workbook("input.xlsx", read_only=True)
try:
    for row in book.active.iter_rows(values_only=True):
        print(row)
finally:
    book.close()

book = Workbook(write_only=True)
sheet = book.create_sheet("Values")
sheet.append([1, "hello", "=A1+1"])
book.save("output.xlsx")
book.close()
```

Read-only mode streams bounded batches. Write-only mode spools rows to disk and
can be saved once; it does not support random cell access.

### Memory and compression

All save modes accept `compression_level`: **0** stores without compression,
**1–9** use Deflate, and the default is **6**.

```python
from crabxl import AutoMemory, ResourceOptions, SharedStringOptions, load_workbook

options = ResourceOptions(
    auto_memory=AutoMemory(maximum_bytes=64 * 1024**2),
    shared_strings=SharedStringOptions(storage="auto", cache_bytes=1024**2),
)
book = load_workbook("input.xlsx", resource_options=options)
try:
    book.active["A1"] = 42
    book.save("output.xlsx", compression_level=3)
finally:
    book.close()
```

Use `max_memory_bytes` for an explicit managed allowance, or `AutoMemory` to tune
Auto selection. `ResourceOptions` also exposes input limits, SST RAM/disk
strategies, cache and temporary-storage limits, and edit-overlay bounds.
These are managed component allowances, not a total process RSS cap. See
[resource configuration](docs/decisions/0016-canonical-resource-configuration.md)
for details.

## Documentation

- [Roadmap](docs/roadmap.md)
- [Streaming modes](docs/decisions/0014-optimized-stream-ownership.md)
- [Resource configuration](docs/decisions/0016-canonical-resource-configuration.md)
- [Benchmarks](benchmarks/optimized-modes.md)
- [Releases](docs/releases.md)

## License

Distributed under the [MIT License](LICENSE). Third-party notices and test
provenance are listed in [third_party](third_party).
