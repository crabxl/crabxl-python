# Alpha.3 scalar writing and canonical edit/save

CPython 3.12.14, Linux x86_64, Rust 1.99 release wheels. The baseline is the
public PyPI 0.1.0a2 wheel; the candidate is the 0.1.0a3 wheel pinned to canonical
core d9fddb01abf3da4715fa6f0cc7c00371d5826471. Both append 100,000 ten-number rows
through Workbook(write_only=True), save and clean up. One warmup and three
rotating serial cold-process samples include imports, conversion and save.
Builds, tests and public readback do not overlap timing.

| One million numeric cells | Alpha.2 | Alpha.3 |
| --- | ---: | ---: |
| Median elapsed seconds | 1.8726 | 1.4659 |
| Median peak RSS KiB | 18,548 | 18,668 |
| Logical worksheet spool peak bytes | 32,866,902 | 32,866,902 |
| Output ZIP bytes | 2,942,935 | 2,942,935 |

Measured writing time falls about 21.7% (1.28x speedup). Common scalar conversion
now precedes formula-class imports and structured-object checks. Scalar ordering,
integer precision, text/error/formula classification and temporal conversion
remain unchanged. All written values are checked with public openpyxl readback.
This numeric evidence does not establish gains for every type or full feature
parity. Source tests pass on each supported CPython version against the installed
candidate wheels; Rustfmt, Clippy and Ruff format/check pass.

Canonical loaded edit/save also gains fixed 64 KiB compression buffering. The
core measurement is 7.0485 seconds to 1.3450 seconds for a one-million-numeric-cell
A1 replacement/save, with every uncompressed package part identical. It excludes
Python full-model loading/conversion and is not an end-to-end Python editing
measurement. See the [canonical core evidence](https://github.com/crabxl/crabxl/blob/main/benchmarks/alpha3-edit-buffering.md).

Write-only mode still uses worksheet XML spools plus an adjacent output ZIP at
save. The table reports logical worksheet storage, not total filesystem peak;
the existing target and new ZIP can coexist during atomic replacement. Managed
allowances and peak RSS observations are not a hard process RSS cap.

Raw samples: [results](results/alpha3-write-regression.json).

```sh
python benchmarks/write_regression.py --before-python /path/to/alpha2/python \
  --after-python /path/to/alpha3/python --measure /path/to/measure \
  --output /tmp/write-regression.json
```
