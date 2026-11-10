# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Before version 1.0, a minor version can change the API.

Each release uses a pinned revision of the Rust core. The core has its own
[changelog](https://github.com/crabxl/crabxl/blob/main/CHANGELOG.md).

## [0.1.0]

First release. It uses the Rust core 0.1.0.

### Added

- `Workbook`, `load_workbook`, `Worksheet` and `Cell` with openpyxl call names,
  in normal, `read_only` and `write_only` modes. Paths and file-like objects.
- Values, dates, formulas with cached results and rich text.
- Cell styles (`Font`, `PatternFill`, `GradientFill`, `Border`, `Alignment`,
  `Protection`, number formats), named styles, themes, row and column styles,
  `cell.quotePrefix` and `cell.pivotButton`.
- Merged cells, row and column dimensions, outline groups and hyperlinks,
  including in `write_only` mode.
- Sheet create, copy, remove, rename and move; `append`, `insert_rows`,
  `delete_rows`, `insert_cols`, `delete_cols` and `move_range`.
- Tables, auto filters, conditional formatting, data validation, comments,
  sheet protection, headers and footers, print areas and titles, defined
  names, scenarios, workbook protection and document properties.
- Images, charts, chartsheets, drawings, pivot tables, external links and
  `wb.vba_archive`.
- `ws.sheet_properties` and `ws.sheet_format` in all modes.
- The openpyxl import paths, for example `crabxl.worksheet.table`,
  `crabxl.formatting.rule` and `crabxl.comments`, and the deprecated openpyxl
  3.1 calls such as `get_sheet_by_name`, which emit a `DeprecationWarning`.
- `max_memory_bytes`, `ResourceOptions`, `ResourceLimits`,
  `SharedStringOptions` and `AutoMemory` to control memory, temporary storage
  and shared strings.
- `save(path, compression_level=...)`. Level 0 stores without compression;
  levels 1–9 use Deflate; the default is 6.
- Rows of plain values (`None`, `bool`, `int`, `float`, `str` and dates and
  times) are converted in Rust when appended.
- `tools/run_openpyxl_suite.py` runs the unchanged openpyxl 3.1.5 test suite
  against crabxl and checks the result against a tracked list of expected
  failures. `--report` writes the compatibility page of the documentation.
- The user guide, adapted from the openpyxl documentation, and pages for
  memory limits, migration, supported features and compatibility.
- One benchmark suite (`benchmarks/run.py`) that compares crabxl with wolfxl,
  oxlsx, python-calamine, fastexcel, XlsxWriter and openpyxl.

[0.1.0]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0
