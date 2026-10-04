# Python compatibility roadmap

Target: openpyxl 3.1.5 public calls, mental model and observable behavior. Core capabilities remain governed by the CrabXL M4-M7 roadmap at https://github.com/crabxl/crabxl/blob/main/docs/roadmap.md.

Current acceptance is partial: 242 tests, including 63 unchanged original test bodies, cover supported owned scalar/formula models and lazy preserving edits. Full styles/date/rich-string reading, loaded structural/feature editing, optimized modes, file-like I/O, tokenizer and all advanced baseline features remain required. This is not full-suite compatibility.

Pin and validate the core revision before updates. Shared reference assertions and separate extension tests should evolve independently. Python is first priority; Node and WASM later share an ExcelJS-compatible interface.

Plain shared strings and inline literal-pattern workflows now use core revision dd38e85 with explicit empty-SST save preservation differences. Loaded component allowances are separate; full rich text, date/style catalogs and aggregate loaded budgets remain incomplete.
