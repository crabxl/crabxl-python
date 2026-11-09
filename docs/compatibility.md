---
title: Compatibility
description: Results of the openpyxl 3.1.5 test suite run against CrabXL.
---

CrabXL runs the test suite of openpyxl 3.1.5 without changes. Each
`openpyxl` module that the tests use resolves to the matching `crabxl`
module.

## Summary

- 2,115 tests pass. This is 99.8% of the tests of the public API.
- 4 tests fail because CrabXL is different on
  purpose. The next section lists them.
- 325 tests use private parts of openpyxl, for example the
  `_reader` and `_writer` classes or the `_style` attribute. CrabXL does
  this work in Rust, so these tests do not apply.
- 28 tests are skipped or expected to fail in openpyxl itself.

## Deliberate differences

- CrabXL keeps the source names of VBA, external link and comment parts.
  openpyxl renames them.
- CrabXL keeps an unchanged calculation chain. openpyxl removes it.
- CrabXL writes the elements of a projected pie chart in the order that the
  file format specifies, because Excel requires it.

## Results by package

| openpyxl package | Pass | Private API | Different on purpose | Skipped |
|---|---:|---:|---:|---:|
| `(top level)` | 52 | 10 | 2 | 0 |
| `cell` | 62 | 44 | 0 | 3 |
| `chart` | 189 | 0 | 1 | 0 |
| `chartsheet` | 21 | 4 | 0 | 0 |
| `comments` | 15 | 1 | 0 | 0 |
| `compat` | 11 | 0 | 0 | 3 |
| `descriptors` | 150 | 0 | 0 | 0 |
| `drawing` | 116 | 17 | 0 | 4 |
| `formatting` | 39 | 0 | 0 | 0 |
| `formula` | 315 | 0 | 0 | 0 |
| `packaging` | 72 | 2 | 0 | 0 |
| `pivot` | 101 | 3 | 0 | 2 |
| `reader` | 3 | 16 | 0 | 0 |
| `styles` | 213 | 5 | 0 | 0 |
| `utils` | 272 | 0 | 0 | 7 |
| `workbook` | 132 | 19 | 1 | 1 |
| `worksheet` | 347 | 203 | 0 | 0 |
| `writer` | 0 | 1 | 0 | 0 |
| `xml` | 5 | 0 | 0 | 8 |
| **Total** | **2,115** | **325** | **4** | **28** |

To run the suite, see `tools/run_openpyxl_suite.py` in the
[repository](https://github.com/crabxl/crabxl-python/blob/main/tools/run_openpyxl_suite.py).
