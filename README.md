<div align="center">

# CrabXL for Python

**Read, write and edit Excel XLSX files in Python, with a Rust core.**

[![crabxl on PyPI](https://img.shields.io/pypi/v/crabxl?label=crabxl)](https://pypi.org/project/crabxl/)
[![crabxl-openpyxl on PyPI](https://img.shields.io/pypi/v/crabxl-openpyxl?label=crabxl-openpyxl)](https://pypi.org/project/crabxl-openpyxl/)
[![CI](https://github.com/crabxl/crabxl-python/actions/workflows/python.yml/badge.svg)](https://github.com/crabxl/crabxl-python/actions/workflows/python.yml)
[![License](https://img.shields.io/github/license/crabxl/crabxl-python)](LICENSE)

[Documentation](https://docs.crabxl.com/docs/python) · [Rust engine](https://github.com/crabxl/crabxl) · [Report an issue](https://github.com/crabxl/crabxl-python/issues)

</div>

## Packages

This repository holds two Python packages over the
[CrabXL Rust core](https://github.com/crabxl/crabxl), which does the work, so
they are fast and use little memory:

| Package | For | Python |
|---|---|---|
| [crabxl](packages/crabxl) | New code: a fully typed API with lossless saves and streaming. | 3.13+ |
| [crabxl-openpyxl](packages/crabxl-openpyxl) | openpyxl code: the openpyxl 3.1.5 API, a drop-in replacement. | 3.9+ |

Both use the native module of a third package,
[crabxl-bindings](packages/crabxl-bindings). It has wheels for CPython 3.9–3.15
on Linux x86_64/ARM64, Windows x86_64, and macOS Intel/Apple Silicon.

## Installation

```sh
pip install crabxl                # the typed API
pip install crabxl-openpyxl       # the openpyxl interface
pip install "crabxl[openpyxl]"    # both, with crabxl.openpyxl
```

## Usage

```python
import crabxl as xl

with xl.Workbook() as book:
    sheet = book.worksheets.add("Sales")
    sheet.append(["Region", "Q1", "Q2", "Total"])
    sheet.append(["North", 120.5, 98, xl.Formula("B2+C2")])
    book.save("sales.xlsx")
```

```python
import crabxl_openpyxl as openpyxl  # or: import crabxl.openpyxl as openpyxl

book = openpyxl.load_workbook("input.xlsx")
book.active["A1"] = "Updated"
book.save("output.xlsx")
```

See the package READMEs for more: [crabxl](packages/crabxl/README.md) and
[crabxl-openpyxl](packages/crabxl-openpyxl/README.md).

## Documentation

- [Documentation](docs/index.md): workbooks, values, styles, streaming and errors
- [openpyxl interface](docs/openpyxl/index.md), with a
  [guide](docs/openpyxl/guide/tutorial.md) adapted from the openpyxl documentation
- [Migration from openpyxl](docs/openpyxl/migration.md)
- [Compatibility](docs/openpyxl/compatibility.md): the openpyxl test suite results
- Changelogs: [crabxl](packages/crabxl/CHANGELOG.md),
  [crabxl-openpyxl](packages/crabxl-openpyxl/CHANGELOG.md),
  [crabxl-bindings](packages/crabxl-bindings/CHANGELOG.md)

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before you open a pull request. Report
security problems as described in [SECURITY.md](SECURITY.md).

## License

Distributed under the [MIT License](LICENSE). Third-party notices and test
provenance are listed in [third_party](third_party).
