# crabxl-bindings

The native module of [CrabXL](https://crabxl.com): PyO3 bindings to the
[CrabXL Rust core](https://github.com/crabxl/crabxl), shared by two Python
packages:

- [crabxl](https://pypi.org/project/crabxl/): the typed CrabXL API for Excel
  `.xlsx` files, for Python 3.13 and later.
- [crabxl-openpyxl](https://pypi.org/project/crabxl-openpyxl/): a drop-in
  replacement for openpyxl, for Python 3.9 and later.

This package has no public API, and its interface can change in any release.
Install one of the packages above; each requires the version of
crabxl-bindings it was built for.

Wheels are available for CPython 3.9–3.15 on Linux x86_64/ARM64, Windows
x86_64, and macOS Intel/Apple Silicon. Building from source needs Rust 1.99 or
newer.

MIT License. Source code:
[crabxl/crabxl-python](https://github.com/crabxl/crabxl-python).
