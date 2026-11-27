# CrabXL

**Read, write, edit and stream Excel `.xlsx` files in Python, with a Rust core.**

[![PyPI](https://img.shields.io/pypi/v/crabxl)](https://pypi.org/project/crabxl/)
[![Python](https://img.shields.io/pypi/pyversions/crabxl)](https://pypi.org/project/crabxl/)
[![CI](https://github.com/crabxl/crabxl-python/actions/workflows/python.yml/badge.svg)](https://github.com/crabxl/crabxl-python/actions/workflows/python.yml)
[![License](https://img.shields.io/pypi/l/crabxl)](https://github.com/crabxl/crabxl-python/blob/main/LICENSE)

CrabXL is a spreadsheet library for Excel workbooks. The
[Rust core](https://github.com/crabxl/crabxl) parses and writes the files, so it
is fast and uses little memory. The Python API is fully typed and checked with
mypy, pyright and pyrefly in strict mode.

- `Workbook` creates a workbook, or opens one to change and save it.
  `Reader` and `Writer` stream rows of files of any size in bounded memory.
- Saves are lossless: they copy every part you did not change, and they raise
  an error instead of dropping content. Saves to a path are atomic.
- Inserting or deleting rows or columns updates every reference to the moved
  cells.
- Numbers keep their precision, and text never turns into a formula.
- Styles, number formats, formulas, merged cells, tables, data validation,
  conditional formats, pictures and charts.
- Have openpyxl code? `crabxl.openpyxl` runs it unchanged. See
  [openpyxl code](#openpyxl-code).

Before version 1.0, a minor version can change the API.

## Installation

```sh
pip install crabxl
```

Or with uv:

```sh
uv add crabxl
```

CrabXL needs CPython 3.13 or newer. Its native module comes from the
[crabxl-bindings](https://pypi.org/project/crabxl-bindings/) package, with
wheels for Linux x86_64/ARM64, Windows x86_64, and macOS Intel/Apple Silicon.

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

The openpyxl interface is the
[crabxl-openpyxl](https://pypi.org/project/crabxl-openpyxl/) package. Install
it with CrabXL:

```sh
pip install "crabxl[openpyxl]"
```

```python
import crabxl.openpyxl as openpyxl

book = openpyxl.load_workbook("input.xlsx")
book.active["A1"] = "Updated"
book.save("output.xlsx")
```

`crabxl.openpyxl` is the module `crabxl_openpyxl`. On Python 3.9 to 3.12,
install crabxl-openpyxl alone and import `crabxl_openpyxl`.

## Documentation

- [Documentation](https://docs.crabxl.com/docs/python): workbooks, values,
  styles, streaming and errors
- [openpyxl interface](https://docs.crabxl.com/docs/python/openpyxl) and the
  [migration guide](https://docs.crabxl.com/docs/python/openpyxl/migration)
- [Changelog](https://github.com/crabxl/crabxl-python/blob/main/packages/crabxl/CHANGELOG.md)

## License

MIT. Source code, issues and contributions:
[crabxl/crabxl-python](https://github.com/crabxl/crabxl-python).
