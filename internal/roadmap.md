# Roadmap

CrabXL for Python 0.1.2 is the current release. It supports the public
openpyxl 3.1.5 API. The Rust core has its own
[roadmap](https://github.com/crabxl/crabxl/blob/main/internal/roadmap.md).

## Released

- 0.1.0: the openpyxl API in normal, read-only and write-only modes.
- 0.1.1: no call raises `NotImplementedError`. Content that CrabXL does not
  model is dropped or kept as written when you save, as in openpyxl. See the
  [changelog](../CHANGELOG.md).
- 0.1.2: faster import and faster reads.

## Next

1. Remove private helpers such as `_address` and `_decode` from the package
   namespace.
2. Shorten the README now that docs.crabxl.com has the guides.

## Not provided

- Formula calculation. CrabXL keeps the cached results that Excel saved.
- Legacy `.xls` and binary `.xlsb` files.

## Performance measurements

Measured before 0.1.0 on one Windows computer. These are development
measurements, not published benchmarks.

- Write of 100,000 rows: 1.79 s before the work, 0.89 s after.
- Edit of 1,000,000 rows: 34 s before the work, 16.6 s after.
