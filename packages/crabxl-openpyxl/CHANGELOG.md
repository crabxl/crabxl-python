# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Before version 1.0, a minor version can change the API.

The native module is the package
[crabxl-bindings](../crabxl-bindings/CHANGELOG.md), whose changelog names the
Rust core version.

## [0.6.0]

### Added

- The first release as a package of its own. Until crabxl 0.5.0, this
  interface was `crabxl.openpyxl` in the crabxl package; its version numbers
  continue from there.
- It supports Python 3.9 and newer. Import `crabxl_openpyxl` in place of
  `openpyxl`. With `pip install "crabxl[openpyxl]"` on Python 3.13 or newer,
  `crabxl.openpyxl` is the same module.
- The wheel includes the openpyxl license for the code adapted from openpyxl.

[0.6.0]: https://github.com/crabxl/crabxl-python/releases/tag/crabxl-openpyxl-0.6.0
