# Status

Last update: 2026-10-24.

Replace this file when the status changes. Do not append a history log.

## Current release

- Latest release: `0.1.0a11` on PyPI (Git tag `0.1.0-alpha.11`).
- It uses the Rust core revision `12bcc05d47f4ee60dc3b7cff447834fff2b1ad1d`
  (core release `0.1.0-alpha.11`).
- Wheels: CPython 3.11–3.15 on Linux x86_64 and ARM64, Windows x86_64, and
  macOS Intel and Apple Silicon. Python 3.15 is tested with its release
  candidate.
- No release is in preparation.

## What works

- `Workbook`, `load_workbook`, `Worksheet` and `Cell` with openpyxl call names.
- Normal, `read_only` and `write_only` modes.
- Values, dates, formulas with cached results and rich text.
- Cell styles: `Font`, `PatternFill`, `GradientFill`, `Border`, `Alignment`,
  `Protection` and number formats. Named styles, themes and row and column
  styles.
- Merged cells, row and column dimensions, outline groups and hyperlinks.
- Sheet create, copy, remove, rename and move. Row and column insertion and
  deletion. Range moves.
- Tables, auto filters, conditional formatting, data validation, comments,
  sheet and workbook protection, headers and footers, defined names, print
  areas and titles, and document properties in normal and `read_only` modes
  (not in `write_only` mode). Stage 1 is on branch `stage1`, not released.
- `ResourceOptions` for memory limits and shared-string storage.
  `compression_level` on save.

## Known limits

- File-like objects are not supported for input or output. Use a path.
- `.xlsm` and `.xltm` files require `keep_vba=True`.
- `keep_links=False` is not supported.
- Formulas are not calculated.
- Features of the next core releases are not available yet: tables, data
  validation, conditional formatting, comments, images and charts.

## Next tasks

### Documentation (to do)

The documentation site is in [crabxl-docs](https://github.com/crabxl/crabxl-docs).
It publishes `docs/` from this repository. Follow the content specification in
crabxl-docs.

1. Write `docs/` user pages:
   - Installation.
   - Migration from openpyxl. This is the most important page. List what works
     without change, what is different and what is not supported.
   - The three modes: normal, `read_only` and `write_only`.
   - Styles.
   - Memory and resource options.
   - Compatibility table by openpyxl module.
   - Performance: a plain summary of the benchmark results.
2. Change the README links that point to ADRs. Link them to user pages
   instead.
3. Make the README shorter. Link it to the documentation site after the site
   is published.
4. Rewrite `internal/roadmap.md` in plain language. Use the writing rules in
   [AGENTS.md](../AGENTS.md). Remove completed items.
5. Consider a Python API reference generated with `fumadocs-python`.

### Features

Follow the core release plan. Add the Python API for each core feature group
when the core supports it. See the core
[status](https://github.com/crabxl/crabxl/blob/main/internal/STATUS.md).

## Known problems

- `crabxl/__init__.py` exports private helpers (`_address`, `_decode` and
  others). Make sure that they are not part of the public API.

## Terms in older records

Older records use these codes:

| Code | Meaning |
|---|---|
| M0–M7 | Milestones of the Rust core. See the core status file. |
| A6, A11, … | Alpha release numbers, for example A11 is `0.1.0a11`. |
| ADR | Architecture Decision Record in [decisions/](decisions/). |
