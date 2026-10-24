# Repository migration

The adapter is extracted from `bindings/python/` at original core revision `eececa0ee7d0606f9d9d7f0318bb4682eb04bf56`. Useful adapter history is retained with rewritten paths and commit IDs; the original repository remains backed up.

The canonical Rust implementation is https://github.com/crabxl/crabxl.git, pinned to `9592bd5ab9189c5f5ea493716665ab0b921cadaa`. This repository contains compatibility wrappers, native handle conversion and tests, not a second spreadsheet engine.

Package and imports are renamed to `crabxl`. Existing supported openpyxl calls can use `import crabxl as openpyxl`. This migration does not implement additional spreadsheet features or rerun historical performance measurements.
