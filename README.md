<div align="center">

# CrabXL for Python

**Read, write and edit Excel XLSX files in Python, with a Rust core.**

[![PyPI](https://img.shields.io/pypi/v/crabxl)](https://pypi.org/project/crabxl/)
[![Python](https://img.shields.io/badge/Python-3.12–3.15-blue?logo=python&logoColor=white)](https://pypi.org/project/crabxl/#files)
[![CI](https://github.com/crabxl/crabxl-python/actions/workflows/python.yml/badge.svg)](https://github.com/crabxl/crabxl-python/actions/workflows/python.yml)
[![License](https://img.shields.io/github/license/crabxl/crabxl-python)](LICENSE)

[Rust engine](https://github.com/crabxl/crabxl) · [Status](internal/STATUS.md) · [Report an issue](https://github.com/crabxl/crabxl-python/issues)

</div>

## About

CrabXL reads, writes and edits XLSX files. The Rust core does the work, so it
is fast and uses little memory. The API is fully typed and checked with mypy
and pyright in strict mode.

- `Workbook` creates a workbook, or opens one to change and save it.
  `Reader` and `Writer` stream rows of files of any size in bounded memory.
- Saves are lossless: they copy every part you did not change, and they raise
  an error instead of dropping content. Saves to a path are atomic.
- Inserting or deleting rows or columns updates every reference to the moved
  cells.
- Numbers keep their precision, and text never turns into a formula.
- `crabxl.openpyxl` runs openpyxl 3.1.5 code unchanged:
  `import crabxl.openpyxl as openpyxl`. openpyxl is not a runtime dependency.

Before version 1.0, a minor version can change the API. See the
[documentation](docs/index.md) and the [migration guide](docs/openpyxl/migration.md).

## Installation

```sh
pip install crabxl
```

Or with uv:

```sh
uv add crabxl
```

Wheels are available for **CPython 3.12–3.15** on Linux x86_64/ARM64, Windows
x86_64, and macOS Intel/Apple Silicon. Python 3.15 validation currently uses its
release candidate. Source builds require Rust 1.99 or newer and Maturin.

## Usage

### Create a workbook

```python
import crabxl as xl

header = xl.Style(font=xl.Font(bold=True), fill=xl.Fill("DDEBF7"))

with xl.Workbook() as book:
    sheet = book.worksheets.add("Sales")
    sheet.append(["Region", "Q1", "Q2", "Total"], style=header)
    sheet.append(["North", 120.5, 98, xl.Formula("B2+C2")])
    sheet.columns("A:D").width = 14
    sheet.freeze_panes = "A2"
    book.save("sales.xlsx")
```

### Edit a file

```python
with xl.Workbook.open("sales.xlsx") as book:
    sheet = book.worksheets["Sales"]
    sheet.rows("2").insert()  # The formula now reads =B3+C3.
    sheet["A2:C2"].values = [["South", 80, 95]]
    sheet["B2:C3"].map_style(lambda s: s.replace(number_format="#,##0.00"))
    book.save("sales.xlsx")  # Atomic, even over the source.
```

### Stream rows

```python
with xl.Reader.open("events.xlsx") as reader:
    for row in reader.worksheets["Events"].iter_rows(columns="A:C", skip=1):
        event_id, kind, amount = row

with xl.Writer.create("export.xlsx") as writer:
    sheet = writer.worksheets.add("Events")
    sheet.extend((n, "sale", n * 1.5) for n in range(1_000_000))
```

### openpyxl code

```python
import crabxl.openpyxl as openpyxl

book = openpyxl.load_workbook("input.xlsx")
book.active["A1"] = "Updated"
book.save("output.xlsx")
book.close()
```

The openpyxl 3.1.5 public API is supported, and the unchanged openpyxl test
suite passes for it. `wb.save(path, calculate=True)` also calculates formulas
and saves their results. See [the openpyxl interface](docs/openpyxl/index.md)
and [supported features](docs/openpyxl/support.md).

## Documentation

- [Documentation](docs/index.md): workbooks, values, styles, streaming and errors
- [openpyxl interface](docs/openpyxl/index.md), with a
  [guide](docs/openpyxl/guide/tutorial.md) adapted from the openpyxl documentation
- [Migration from openpyxl](docs/openpyxl/migration.md)
- [Compatibility](docs/openpyxl/compatibility.md): the openpyxl test suite results
- [Project status](internal/STATUS.md)
- [Changelog](CHANGELOG.md)

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before you open a pull request. Report
security problems as described in [SECURITY.md](SECURITY.md).

## License

Distributed under the [MIT License](LICENSE). Third-party notices and test
provenance are listed in [third_party](third_party).
