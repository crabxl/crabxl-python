# Architecture

Update this file only when the architecture changes.

The Rust core (https://github.com/crabxl/crabxl) is the only spreadsheet
engine. This package has two interfaces over it: the native `crabxl` API and
the openpyxl 3.1.5 interface `crabxl.openpyxl`. `Cargo.toml` pins the core to
an exact version.

## Layers

| Layer | Responsibility |
|---|---|
| `python/crabxl` | The native API: typed classes (`workbook.py`, `read.py`, `write.py`) and frozen value, style and feature types. |
| `python/crabxl/openpyxl` | The openpyxl interface. Its modules follow the openpyxl module layout. Compatible objects are views over native handles. |
| `src/api/` (`crabxl._native.Api*`) | The native API's engine, built on the `crabxl` crate: `ApiWorkbook`, `ApiReader` (row streams on a background thread with a bounded channel) and `ApiWriter`. Converts values in bulk and releases the GIL for file work. |
| `src/` (other modules) | The openpyxl interface's PyO3 handles, built on `crabxl-xlsx` and `crabxl-core` through `src/engine.rs`. |
| Rust core | Models, validation, resources and every XLSX codec. |

## openpyxl workbook modes

| Python mode | Native owner |
|---|---|
| `Workbook()` | Registered owned workbook bank. |
| `load_workbook(path)` | `NativeReader` plus `NativeEditor` over one loaded source. Saves preserve unchanged parts. |
| `load_workbook(path, read_only=True)` | `NativeReader` row streams. |
| `Workbook(write_only=True)` | Native interleaved streaming writer. |

File-like objects are spooled to a temporary file and use the path code.

## Features

Feature classes (tables, rules, validation, comments, charts, drawings, pivots,
print settings and similar) are openpyxl Serialisable descriptors. They convert
to and from SpreadsheetML; the core parses that XML into its typed or
tree-based models (`_features.py` and `src/features.rs`). Features load on first
access, and only changed features are pushed back before save.

## Rules

- Never fall back to openpyxl at run time.
- The native API never creates one Python object per cell unless it returns
  values; bulk reads and writes convert in one native call.
- The openpyxl interface selects openpyxl's behavior through core options
  (cells-only row edits, value-based date kinds, `DataLossPolicy::Allow`,
  openpyxl's copy scope). These are never core defaults.
- Do not create one Python object per cell unless the openpyxl API returns one.

## Source modules

- `python/crabxl/__init__.py` and `python/crabxl/openpyxl/__init__.py` only
  compose exports.
- In `crabxl.openpyxl`, `cell/cell.py`, `worksheet/worksheet.py` and
  `workbook/workbook.py` hold the compatible objects. `workbook/loader.py` selects the loading mode.
  `optimized.py` holds the read-only and write-only views.
- `src/lib.rs` registers classes. `workbook.rs`, `worksheet.rs`, `reader.rs`,
  `editor.rs` and `streaming/` implement the handles. `values.rs` shares value
  conversion and error mapping.

Compatibility is checked by `tests/` and by the unchanged openpyxl 3.1.5 suite
(`tools/run_openpyxl_suite.py`).
