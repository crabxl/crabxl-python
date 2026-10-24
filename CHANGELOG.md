# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Before version 1.0, any release can change the API.

Each release uses a pinned revision of the Rust core. The core has its own
[changelog](https://github.com/crabxl/crabxl/blob/main/CHANGELOG.md).

## [0.1.0a11] - 2026-10-21

### Added

- Named styles, themes and row and column styles.
- Merged cells that you can edit, including `merged_cells` updates.
- Row and column dimensions and outline groups.
- Hyperlinks, including in `write_only` mode.
- Rich text that you can edit.
- `MultiCellRange` and range utilities.

## [0.1.0a10] - 2026-10-07

### Added

- `Font`, `Color`, `PatternFill`, `GradientFill`, `Side`, `Border`,
  `Alignment` and `Protection`, with openpyxl copy and assignment behavior.

## [0.1.0a9] - 2026-10-07

### Added

- `Cell.number_format`, `Cell.style_id`, `Cell.has_style` and a
  format-aware `Cell.is_date`.
- `WriteOnlyCell.number_format`.

### Fixed

- Repeated validation of loaded sheets.

## [0.1.0a8] - 2026-10-06

### Changed

- Faster reads of numbers and shared strings.
- Lower memory use for large loaded workbooks.

## [0.1.0a7] - 2026-10-06

### Added

- Loaded workbooks: create, copy, remove, rename and move sheets.
- `append`, `insert_rows`, `delete_rows`, `insert_cols`, `delete_cols` and
  `move_range`.

## [0.1.0a6] - 2026-10-05

### Fixed

- Valid ZIP and ZIP64 files made by streaming tools no longer cause a false
  size-limit error.

### Removed

- Default size limits on archives and worksheets.

## [0.1.0a5] - 2026-10-05

### Added

- `ResourceOptions`, `ResourceLimits`, `SharedStringOptions` and `AutoMemory`
  to control memory, temporary storage and shared strings.
- `load_workbook(resource_options=...)`.

## [0.1.0a4] - 2026-10-05

### Added

- `save(path, compression_level=...)`. Level 0 stores without compression.
  Levels 1–9 use Deflate. The default is 6.

## [0.1.0a3] - 2026-10-05

### Changed

- Faster writes in `write_only` mode, approximately 22% less time.

## [0.1.0a2] - 2026-10-05

### Added

- `read_only` and `write_only` modes.

### Changed

- Faster `iter_rows(values_only=True)`.

## [0.1.0a1] - 2026-10-05

### Added

- First release: `Workbook`, `Worksheet` and `Cell` with openpyxl call names,
  values, dates, formulas and edits of existing files.

[0.1.0a11]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0-alpha.11
[0.1.0a10]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0-alpha.10
[0.1.0a9]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0-alpha.9
[0.1.0a8]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0-alpha.8
[0.1.0a7]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0-alpha.7
[0.1.0a6]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0-alpha.6
[0.1.0a5]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0-alpha.5
[0.1.0a4]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0-alpha.4
[0.1.0a3]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0-alpha.3
[0.1.0a2]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0-alpha.2
[0.1.0a1]: https://github.com/crabxl/crabxl-python/releases/tag/0.1.0-alpha.1
