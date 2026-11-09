# Architecture

Update this file only when the architecture changes.

The Rust core (https://github.com/crabxl/crabxl) is the only spreadsheet
engine. This package adapts it to the openpyxl 3.1.5 API. `Cargo.toml` pins
the core to an exact Git revision.

## Layers

| Layer | Responsibility |
|---|---|
| `python/crabxl` | Public package. Its modules follow the openpyxl module layout. Compatible objects are views over native handles. |
| `src/` (`crabxl._native`) | PyO3 handles for the owned bank, the loaded reader and editor, the streaming reader and the streaming writer. Converts values in batches and releases the GIL for native work. |
| Rust core | Models, validation, resources and every XLSX codec. |

## Workbook modes

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
- An unsupported property or call raises an explicit error; nothing is lost on
  save.
- Do not create one Python object per cell unless the openpyxl API returns one.

## Source modules

- `python/crabxl/__init__.py` only composes exports.
- `cell/cell.py`, `worksheet/worksheet.py` and `workbook/workbook.py` hold the
  compatible objects. `workbook/loader.py` selects the loading mode.
  `optimized.py` holds the read-only and write-only views.
- `src/lib.rs` registers classes. `workbook.rs`, `worksheet.rs`, `reader.rs`,
  `editor.rs` and `streaming/` implement the handles. `values.rs` shares value
  conversion and error mapping.

Compatibility is checked by `tests/` and by the unchanged openpyxl 3.1.5 suite
(`tools/run_openpyxl_suite.py`).
