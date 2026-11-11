# Roadmap

CrabXL for Python supports the public openpyxl 3.1.5 API. Each release and its
changes are in the [changelog](../CHANGELOG.md). The Rust core has its own
[roadmap](https://github.com/crabxl/crabxl/blob/main/internal/roadmap.md).

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
