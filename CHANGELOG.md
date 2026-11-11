# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Before version 1.0, a minor version can change the API.

Each release names the Rust core version it uses. The core has its own
[changelog](https://github.com/crabxl/crabxl/blob/main/CHANGELOG.md).

## [Unreleased]

### Changed

- Loading no longer stops real workbooks at limits meant for hostile files.
  The old limits rejected, for example, files with more than 1,024 sheets or
  16,384 parts, 16 MiB of styles or names, or a cell over 64 KiB. The guards
  that remain stop ZIP bombs, deeply nested XML and huge XML tokens, and the
  default opens every file Excel writes.

### Added

- `load_workbook(..., limits=...)` takes `"strict"` for uploads from
  strangers, `"unlimited"` for files you trust, or a `ResourceLimits`.
  `ResourceLimits.strict()` and `ResourceLimits.unlimited()` give the presets,
  and the `CRABXL_LIMITS` environment variable sets the preset for code that
  cannot pass arguments, such as pandas.
- `max_expansion_ratio` stops ZIP bombs: an entry larger than 1 MiB may
  expand at most 100 times.
- `crabxl.LimitExceededError`, a `ValueError`, says which guard a file
  exceeded and how to relax it.

### Fixed

- `iter_rows` with all four limits no longer scans every cell of the sheet,
  and assigning a font, fill, border or alignment no longer imports the
  style module each time. Styling each appended row of a 34,000-row
  workbook took about 1.5 times as long as in openpyxl; it is now slightly
  faster than openpyxl.
- Reading and writing cells one at a time does less work per cell. Reading
  `cell.value` no longer imports modules, `ws.cell(row, column, value)`
  writes the cell once instead of twice, and checking text for illegal
  characters no longer loops over every character in Python.
- Reading a cell's font, fill, border, alignment or protection took about
  three times as long as in openpyxl, and creating a new `Font` or
  `Alignment` for each cell about 1.7 times. Both now take about as long as
  in openpyxl.
- On Windows, saving a workbook over a file that a loaded workbook still had
  open failed with "access denied". It now replaces the file.

## [0.2.0]

It uses the Rust core 0.2.0.

### Added

- `Workbook.save(filename, calculate=True)` calculates every formula first
  and saves each result as the formula's cached value, so programs that read
  cached values, such as `openpyxl` with `data_only=True` or pandas, see
  current results. It works for new and loaded workbooks, not write-only
  ones. Array formulas are not calculated and lose their cached values.

### Changed

- Wheels are about twice as large, because they include the calculation
  engine.

## [0.1.3]

It uses the Rust core 0.1.3.

### Changed

- Large worksheets are read and saved on several CPUs. On 12 CPUs, the
  1,000,001-row sheet reads in read-only mode in about 5.2 s instead of
  10.3 s, and saving an edited medium workbook takes 0.83 s instead of
  1.35 s. Values do not change. Set `CRABXL_MAX_THREADS` to use fewer
  threads; 1 keeps all work on the calling thread.

### Security

- The Rust core uses zip 9. Earlier versions accept archives whose local file
  headers disagree with the central directory (GHSA-m665-v7pm-7grj).

## [0.1.2]

It uses the Rust core 0.1.2.

### Changed

- `import crabxl` takes about half as long. Style classes, charts and the XML
  support load on first use, so reading cell values never imports them.
- Reading values is faster, most of all in read-only mode. Numbers, text,
  booleans and dates become Python objects in Rust, and read-only sheets hand
  rows to Python in batches. With the faster cell reading of core 0.1.2, a
  1,000,001-row sheet reads in read-only mode in about 11.4 s instead of
  15.5 s on one CPU.

## [0.1.1]

It uses the Rust core 0.1.1.

### Changed

- CrabXL never raises `NotImplementedError`. Content it does not model is
  dropped or kept as written when you save, as in openpyxl: signatures of a
  changed signed file, unknown XML attributes, elements and alternatives, and
  style extensions. Shared formulas whose first cell you replace become
  ordinary formulas.
- `keep_links=False` removes external links without checking formulas, names,
  rules or charts, as openpyxl does.
- Copying and removing sheets with unknown content, and editing dialog sheets,
  now work.
- Read-only and write-only sheets have the same attributes as in openpyxl.

### Added

- Restoring `vba_archive`, moving and removing write-only sheets, and changing
  `epoch` and `iso_dates` of a loaded or read-only workbook.
- Style changes on read-only workbooks, and styles on removed or unattached
  sheets.
- Long sheet titles warn as in openpyxl.

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

[0.2.0]: https://github.com/crabxl/crabxl-python/releases/tag/0.2.0
[0.1.3]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.3
[0.1.2]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.2
[0.1.1]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.1
[0.1.0]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0
