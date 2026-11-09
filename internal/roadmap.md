# Roadmap

A12 completed openpyxl 3.1.5 compatibility. The only stage before the beta is
A13: performance and memory. The core
[roadmap](https://github.com/crabxl/crabxl/blob/main/internal/roadmap.md) has
the plan and targets.

## A13 work in this repository

1. Run `benchmarks/run.py` against wolfxl, oxlsx, python-calamine, fastexcel,
   XlsxWriter and openpyxl.
2. Remove binding costs: batch value conversion, avoid per-cell Python objects
   where openpyxl does not return them, release the GIL for native work.
3. Pin the optimized core revision.
4. Check that the Python tests and `tools/run_openpyxl_suite.py --expected
   tools/openpyxl_suite_expected.json` still pass.

## Beta

Release `0.1.0b1` with the core beta.
