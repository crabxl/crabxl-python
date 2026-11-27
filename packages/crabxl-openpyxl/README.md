# crabxl-openpyxl

**A drop-in replacement for openpyxl, with a Rust core.**

[![PyPI](https://img.shields.io/pypi/v/crabxl-openpyxl)](https://pypi.org/project/crabxl-openpyxl/)
[![Python](https://img.shields.io/pypi/pyversions/crabxl-openpyxl)](https://pypi.org/project/crabxl-openpyxl/)
[![CI](https://github.com/crabxl/crabxl-python/actions/workflows/python.yml/badge.svg)](https://github.com/crabxl/crabxl-python/actions/workflows/python.yml)
[![License](https://img.shields.io/pypi/l/crabxl-openpyxl)](https://github.com/crabxl/crabxl-python/blob/main/LICENSE)

crabxl-openpyxl gives you the openpyxl 3.1.5 API for reading, writing and
editing Excel `.xlsx` files. The [CrabXL Rust core](https://github.com/crabxl/crabxl)
does the work, so your openpyxl code runs faster and in less memory, without
changes. The unchanged openpyxl test suite passes for its public API.

- Workbooks, worksheets, cells, styles, number formats, formulas, merged cells,
  tables, data validation, conditional formatting, comments, hyperlinks,
  images and charts.
- `read_only=True` and `write_only=True` stream large files.
- `wb.save(path, calculate=True)` also calculates formulas and saves their
  results.
- openpyxl is not a dependency, and this package never falls back to it.

## Installation

```sh
pip install crabxl-openpyxl
```

It supports CPython 3.9 to 3.15. Its native module comes from the
[crabxl-bindings](https://pypi.org/project/crabxl-bindings/) package, with
wheels for Linux x86_64/ARM64, Windows x86_64, and macOS Intel/Apple Silicon.

## Usage

Import `crabxl_openpyxl` in place of `openpyxl`. The calls are the same.

```python
import crabxl_openpyxl as openpyxl
from crabxl_openpyxl.styles import Font

book = openpyxl.load_workbook("input.xlsx")
sheet = book.active
sheet["A1"] = "Updated"
sheet["A1"].font = Font(bold=True)
book.save("output.xlsx")
```

This package follows openpyxl's behavior. For example, inserting rows moves
only the cells, and text that starts with `=` becomes a formula.

## With the typed CrabXL API

On Python 3.13 and newer, [crabxl](https://pypi.org/project/crabxl/) offers a
typed API with lossless saves and streaming. Install both, and use the same
modules as `crabxl.openpyxl`:

```sh
pip install "crabxl[openpyxl]"
```

```python
import crabxl.openpyxl as openpyxl
```

## Documentation

- [openpyxl interface](https://docs.crabxl.com/docs/python/openpyxl)
- [Migration from openpyxl](https://docs.crabxl.com/docs/python/openpyxl/migration)
- [Supported features](https://docs.crabxl.com/docs/python/openpyxl/support)
- [Changelog](https://github.com/crabxl/crabxl-python/blob/main/packages/crabxl-openpyxl/CHANGELOG.md)

## License

MIT. Parts of this package are adapted from
[openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) (MIT,
Copyright (c) 2010-2024 openpyxl); see `licenses/openpyxl-MIT.txt`. Source
code: [crabxl/crabxl-python](https://github.com/crabxl/crabxl-python).
