# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Before version 1.0, a minor version can change the API.

Until 0.5.0, crabxl included the openpyxl interface and the native module, and
each release named the Rust core version it uses. Since 0.6.0 they are the
packages [crabxl-openpyxl](../crabxl-openpyxl/CHANGELOG.md) and
[crabxl-bindings](../crabxl-bindings/CHANGELOG.md), with their own changelogs.

## [0.6.0]

### Changed

- CrabXL needs Python 3.13 or newer.
- The openpyxl interface is the new package crabxl-openpyxl, which supports
  Python 3.9 and newer. Install it with `pip install "crabxl[openpyxl]"` to
  keep using `crabxl.openpyxl`, which is the module `crabxl_openpyxl`: its
  submodules and classes are the same objects.
- The native module is the new package crabxl-bindings, a dependency of
  crabxl, so the crabxl wheel is pure Python.
- `Reader.open` and `Writer.create` are typed to return the class they are
  called on, so a subclass gets its own type.
- `DataValidation.list` is typed to accept numbers, which it saves as text.

### Fixed

- `Workbook.to_bytes`, and saving or finishing into a binary file, no longer
  copy the file contents once more.

## [0.5.0]

It uses the Rust core 0.4.0.

### Changed

- CrabXL needs Python 3.12 or newer. The public type aliases use the
  `type` statement (PEP 695).
- A chart no longer holds its place: `sheet.charts.add(chart, at="E2:L18")`,
  as for pictures. `Chart` takes the kind, the series and the options.
  Iterating `sheet.charts` gives `PlacedChart` values.
- `Rows` and `Columns` are now `RowSpan` and `ColumnSpan`, so they differ
  from `Row`, a row that `Reader` reads.
- A streaming sheet uses the collections of a workbook sheet:
  `sheet.merges.add(...)`, `sheet.validations.add(...)` and
  `sheet.conditional_formats.add(...)` replace `merge`, `add_validation`
  and `add_conditional_format`.
- `freeze_panes` and `columns(...).width` of a streaming sheet read back the
  values you set, instead of `None`.
- `from crabxl import load_workbook` and the other openpyxl names now raise
  a plain `ImportError`. Import them from `crabxl.openpyxl`.

### Added

- `Workbook.open` and `Reader.open` accept any bytes-like object, such as
  `bytearray`, `memoryview` or `mmap`.
- The worksheet collections of `Reader` and `Writer` are public types,
  `WorksheetReaders` and `WorksheetWriters`, with a `names` property.
- `Source`, `Target`, `Limits`, `Numbers`, `Dates` and `Visibility` are
  exported for type annotations.

## [0.4.0]

It uses the Rust core 0.4.0.

### Changed

- Tables, validations and conditional formats read back as the values you
  add: iterating `sheet.validations` gives `DataValidation` values, and
  `sheet.conditional_formats` gives `ConditionalFormat` values, instead of
  tuples. Validation bounds read as numbers and list choices as a tuple.
- `ConditionalFormat` takes `ranges=` like `DataValidation`, and can apply
  to several ranges: `ConditionalFormat.cell(">", 5, ranges="B2:B9", ...)`.
- `DataValidation.list` stores its choices as a tuple, so rules are hashable.
  `list_from` and `custom` drop a leading `=`.
- `Properties.created` and `Properties.modified` are timezone-aware
  `datetime` values. Assigning a naive `datetime` raises `InvalidInputError`.
- `Table.totals_row` takes part in equality.

### Added

- Charts: `sheet.charts` adds, reads and removes column, bar, line, area,
  pie, doughnut and scatter charts made of `Series`.
- Printing: `sheet.page_setup` reads and sets a `PageSetup` with orientation,
  paper size, scale, fit to pages, `Margins`, centering, grid lines, print
  area and repeated title rows and columns.
- `sheet.auto_filter`, `sheet.tab_color`, and `outline_level` on
  `sheet.rows(...)` and `sheet.columns(...)` to group rows and columns.
- `DataValidation.date` and `DataValidation.time`. Date and time rules read
  back with `datetime.date` and `datetime.time` bounds.
- Iterating `sheet.images` gives `PlacedImage` values. `sheet.images`,
  `sheet.charts` and `sheet.conditional_formats` have `remove(ref)`.
- `Table(totals_row=True)` adds a table whose last row is a totals row. Its
  cells hold text, a formula or nothing; Excel rejects other values there.
- Tables read back `banded_rows`; rules read back their comparison, second
  bound, blank handling, prompt, error message and style.
- `Merges`, `Tables`, `Validations`, `ConditionalFormats`, `Images`,
  `DefinedNames` and `ValidationValue` are exported from `crabxl`.
- `crabxl.load_workbook` and other names that moved to `crabxl.openpyxl`
  raise an `ImportError` that names the new location.

### Fixed

- A worksheet renamed through one handle is renamed for every handle:
  `book.worksheets["Data"]` gives the same object each time.

## [0.3.0]

It uses the Rust core 0.3.0.

### Changed

- `crabxl` has its own, fully typed API. `Workbook` creates a workbook or
  opens one to change it; `Reader` and `Writer` stream rows with bounded
  memory. See the [documentation](docs/index.md).
- The openpyxl interface moved to `crabxl.openpyxl`. Change
  `import crabxl as openpyxl` to `import crabxl.openpyxl as openpyxl`. Its
  behavior is unchanged: the openpyxl 3.1.5 suite gives the same results.

### Added

- Lossless saves: a save raises `UnsupportedError` instead of dropping
  content CrabXL cannot keep. Open with `data_loss="allow"` to permit it.
- Row and column inserts and deletes update formulas on every sheet,
  defined names, tables, rules, merges, row heights, charts, anchors and
  internal hyperlinks.
- Atomic saves to paths. An existing file keeps its permissions.
- `numbers="exact"` returns non-integers as `Decimal`; integers of any size
  are exact `int` values.
- Date formats read by the parts they show: `datetime.date` for date-only
  formats and `datetime.time` for time-only formats.
- A typed exception hierarchy under `CrabXLError`, with `sheet`, `cell` and
  `part` attributes.
- `py.typed` and a stub for the native module. The public package passes
  mypy and pyright in strict mode.

## [0.2.2]

It uses the Rust core 0.2.2.

It needs the Rust core fixes listed under Unreleased in the core changelog.

### Fixed

- Freezing panes again, or unfreezing them, left selections for panes that no
  longer exist, and Excel repaired the file.
- `merge_cells` raises `ValueError` when the range overlaps another merged
  range. Excel removed such merges as damaged content.
- Write-only rows could hold at most about 8,000 cells or 1 MiB of text. They
  now take all 16,384 columns, limited only by the memory budget.
- Hyperlinks move with their cells on `insert_rows`, `insert_cols`,
  `delete_rows` and `delete_cols`.
- Excel's `_xHHHH_` escapes are decoded when reading, and literal text that
  looks like one is escaped when writing.
- `Tokenizer` accepts spill references such as `A1#`.

### Changed

- `sheet.cell()` and `iter_rows()` with cell objects are about 35% faster.
- Text longer than 32,767 characters raises `ValueError`. openpyxl cuts it
  off without a warning.

## [0.2.1]

It uses the Rust core 0.2.1.

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

[0.6.0]: https://github.com/crabxl/crabxl-python/releases/tag/crabxl-0.6.0
[0.5.0]: https://github.com/crabxl/crabxl-python/releases/tag/0.5.0
[0.4.0]: https://github.com/crabxl/crabxl-python/releases/tag/0.4.0
[0.2.2]: https://github.com/crabxl/crabxl-python/releases/tag/0.2.2
[0.2.1]: https://github.com/crabxl/crabxl-python/releases/tag/0.2.1
[0.2.0]: https://github.com/crabxl/crabxl-python/releases/tag/0.2.0
[0.1.3]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.3
[0.1.2]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.2
[0.1.1]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.1
[0.1.0]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0
