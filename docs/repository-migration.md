# Repository migration

The adapter is extracted from `bindings/python/` at original core revision `5c80ecaa080e3605cff98eb8c80721d85aa4af00`. Useful adapter history is retained with rewritten paths and commit IDs; the original repository remains backed up.

The canonical Rust implementation is https://github.com/crabxl/crabxl.git, pinned to `95c21e7734b375cde16489e2adc4684c70d7677f`. This repository contains compatibility wrappers, native handle conversion and tests, not a second spreadsheet engine.

Package and imports are renamed to `crabxl`. Existing supported openpyxl calls can use `import crabxl as openpyxl`. This migration does not implement additional spreadsheet features or rerun historical performance measurements.
