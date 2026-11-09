# Third-party code

## openpyxl

Source: openpyxl 3.1.5, revision `13627b03ca25a1a98becf40e533b955615b13429`
(https://foss.heptapod.net/openpyxl/openpyxl). License: MIT, Copyright (c)
2010-2024 openpyxl, in [licenses/openpyxl-MIT.txt](licenses/openpyxl-MIT.txt).

Copied or adapted code:

- The Serialisable descriptor classes in `python/crabxl`: `descriptors`,
  `compat`, `xml`, `packaging`, `formatting`, `comments`, `chart`,
  `chartsheet`, `drawing`, `pivot`, `styles` (except the native style
  bridge), most of `utils`, and the feature modules of `worksheet` and
  `workbook`. Each file starts with the openpyxl copyright line. These classes
  only convert to and from XML; the Rust core owns models and package codecs.
  ZIP reading and writing, VML and stylesheet writers are not copied.
- The scanner constants in `formula/tokenizer.py`.
- The user documentation in `docs/` is adapted from the openpyxl
  documentation (`doc/*.rst`) with CrabXL imports and notes.

Tests:

- Selected openpyxl tests are copied without change into
  `tests/test_upstream_*.py`. [python-tests.json](python-tests.json),
  [python-workbook-tests.json](python-workbook-tests.json) and
  [python-formula-tests.json](python-formula-tests.json) record each source.
  `tools/verify_python_test_provenance.py` checks that the copies are
  unchanged.
- `tools/run_openpyxl_suite.py` runs the full upstream suite from a reference
  checkout. It copies no test files.
