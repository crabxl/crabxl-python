# Canonical namespace optimization through Python

The adapter pins published core `c5b4cf2`, which caches semantic default namespace
scope without duplicating XML codecs in Python. The before wheel pins core
`02f7c1c`; both candidate wheels have unreleased `0.1.0a6` metadata. This is an
A7 development checkpoint, not a new package release. Native and Python source
hashes distinguish the installed candidates in the reports.

Python 3.12.14/Linux, same release toolchain/features and numeric fixtures.
Ordinary and read-only `load_workbook` + complete `iter_rows(values_only=True)`
are measured separately. Each fixture warms once, then runs three alternating
serial cold processes per candidate. Imports, loading, iteration and cleanup are
included; generation/build/tests are excluded and do not overlap timing. Every
cell count and exact numeric checksum is checked. Numeric reads create no SST or
output temporary files. No new reference-engine measurements are claimed.

| Mode / cells | Before seconds | After seconds | Before/after peak RSS KiB |
| --- | ---: | ---: | ---: |
| Ordinary / 100,000 | 0.1707 | 0.1622 | 27,532 / 27,656 |
| Ordinary / 1,000,000 | 1.3611 | 1.2910 | 97,676 / 97,672 |
| Read-only / 100,000 | 0.1251 | 0.1244 | 20,244 / 20,240 |
| Read-only / 1,000,000 | 0.8327 | 0.7158 | 20,244 / 20,112 |

At one million cells, median complete wall time drops approximately 5.1% in
ordinary mode and 14.0% in read-only mode. The smaller read-only fixture changes
by less than 1%; these results do not imply a universal improvement. RSS remains
similar. Full native text/style results and remaining performance gaps are in
the [core evidence](https://github.com/crabxl/crabxl/blob/main/benchmarks/alpha7-namespace-scope.md).

Raw reports: [ordinary](results/alpha7-namespace-values.json) and
[read-only](results/alpha7-namespace-read-only.json). Full 547-test compatibility
suite and Ruff format/check passed against the rebuilt installed wheel.

```sh
python benchmarks/values_calls.py --before-python /path/to/before/python \
  --after-python /path/to/after/python --measure /path/to/core/benchmarks/measure \
  --rows 10000 100000 --runs 3 --skip-reference \
  --output benchmarks/results/namespace-values.local.json
# Repeat with --read-only and a separate output file.
```
