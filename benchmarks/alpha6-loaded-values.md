# A6 ordinary loaded-bank integration measurements

This checkpoint replaces the separate loaded reader/editor/model owners with the
canonical Rust source-backed bank. Source catalogs, all models, overlays and
SST/cache share a retained allowance. Python no longer applies cloned overlays
each time it requests a model; see [ADR 0017](../docs/decisions/0017-canonical-loaded-workbook-owner.md).
It is not complete A6 acceptance or a claim of general speed improvement.

## Same-mode comparison

Both CrabXL candidates use ordinary editable `load_workbook` and
`iter_rows(values_only=True)`, with a 1 GiB retained-model allowance. The before
environment installs public PyPI `0.1.0a5`; the candidate has unreleased alpha.5
metadata and pins published core `ea969d9`. Hashes distinguish installed code and
native binaries in [raw results](results/alpha6-loaded-values.json).

Python 3.12.14, Linux, openpyxl 3.1.5 with lxml 6.1.3. Each scale warms up once,
then runs three serial samples per implementation in rotating order. No builds
or tests overlap measurement. Wall/CPU and kernel peak RSS include imports,
ordinary loading, complete values iteration and cleanup; builds and generation
are excluded. Generated files have ten integer columns. All input cell counts
and exact checksums are checked. Reading these numeric files creates no temporary
SST or output ZIP; this does not describe disk use for text/edit workloads.

| Cells | Public alpha.5 seconds / RSS KiB | Loaded-bank candidate seconds / RSS KiB | openpyxl ordinary seconds / RSS KiB |
| --- | --- | --- | --- |
| 10,000 | 0.061361 / 20,708 | 0.065153 / 20,608 | 0.164788 / 36,684 |
| 100,000 | 0.166080 / 27,724 | 0.169228 / 27,520 | 0.742478 / 75,108 |
| 1,000,000 | 1.330312 / 97,672 | 1.342093 / 97,536 | 8.788695 / 443,908 |

The candidate's median total wall time is approximately 6.2%, 1.9% and 0.9%
higher at the three scales. Sample variation is visible in the raw data; these
measurements do not establish a reliable speed change. Joint ownership/accounting
does not cause a material large-input RSS increase here. Numeric performance
remains faster than the matched openpyxl ordinary workload, while text, complex
features, calamine comparisons and the broader performance backlog remain A7
work. Open and iterate phase timings are diagnostic only: CrabXL materializes
lazily during iteration and openpyxl loads eagerly.

The new resource regression verifies jointly failing second-sheet loading,
preserved first-sheet aliases and pending values, repeated save/reload, one
actual source descriptor, closed handles, unchanged source bytes and temporary
cleanup. All 545 CPython 3.12 compatibility cases pass locally. Multi-ABI and
platform acceptance remains a publication gate.

## Reproduction

```sh
python benchmarks/values_calls.py \
  --before-python /path/to/public-alpha5/venv/bin/python \
  --after-python /path/to/candidate/venv/bin/python \
  --measure /path/to/core/benchmarks/measure \
  --rows 1000 10000 100000 --runs 3 \
  --output benchmarks/results/alpha6-loaded-values.local.json
```
