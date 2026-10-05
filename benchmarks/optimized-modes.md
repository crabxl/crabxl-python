# Optimized scalar modes and latest-core conversion evidence

The candidate pins canonical core `7e9eb8db613d1f9fd921f8698c50f858c76009bb`
(quick-xml 0.42, interleaved spools, bounded prefix reads). It is an unpublished
source candidate; local wheel metadata remains 0.1.0a1. Native/Python hashes and
reference versions identify the measured binaries in the raw results. CPython
3.12.14, Linux x86_64, Rust 1.99 release builds; openpyxl 3.1.5,
python-calamine 0.8.2, XlsxWriter 3.2.9.

One warmup and three rotating serial cold-process samples include imports,
complete scalar consumption or append/save, and cleanup. Generation, build and
write readback are excluded. No tests/builds overlap these final measurements.
All numeric runs check count and exact checksum; every written file is reopened
with openpyxl and checked. A 1 GiB component allowance is not a process RSS cap.
Numeric input has no shared-string table and reading uses no temporary files.
Read-only conversion avoids cells and per-scalar tagged tuples. Write-only
rows are byte bounded before crossing FFI and again in the canonical writer.

All table entries are median seconds / peak RSS KiB. These are overlapping
scalar operations, not complete feature equivalence; python-calamine has no
editable model and XlsxWriter has no reader. Calamine materializes its range
while CrabXL streams bounded batches. Full optimized-mode styles remain staged.

## Read-only numeric values

| Cells | CrabXL read_only | openpyxl read_only | python-calamine |
|---|---|---|---|
| 10,000 | 0.0429 / 18,796 | 0.1483 / 33,220 | 0.0379 / 18,276 |
| 100,000 | 0.1101 / 18,908 | 0.4912 / 34,600 | 0.0870 / 24,548 |
| 1,000,000 | 0.8014 / 18,664 | 4.3008 / 42,100 | 0.5190 / 87,908 |

## Write-only numeric values

| Cells | CrabXL write_only | openpyxl write_only | XlsxWriter constant_memory |
|---|---|---|---|
| 10,000 | 0.0549 / 18,752 | 0.1661 / 32,876 | 0.0909 / 19,728 |
| 100,000 | 0.2028 / 18,756 | 0.4764 / 33,056 | 0.3496 / 19,724 |
| 1,000,000 | 1.7340 / 18,828 | 4.0010 / 32,916 | 3.1079 / 19,724 |

At one million numeric cells the canonical worksheet spool peak is 32,866,902
bytes, and the final ZIP is 2,942,935 bytes. Packaging temporarily retains both;
these stats cover worksheet XML, not a total filesystem high-water measurement.
RAM savings trade worksheet storage for disk I/O. Openpyxl/XlsxWriter temporary
peaks are not instrumented here. Abort, failed target creation/rename, repeated
close and iterator cancellation have deterministic cleanup tests. Large SST
payload/index files are anonymous/delete-on-close; the partial-close test
checks live Linux descriptors and successful bounded full readback on all hosts.

## Ordinary editable numeric values

| Cells | PyPI alpha.1 | Current candidate | openpyxl ordinary |
|---|---|---|---|
| 10,000 | 0.0669 / 19,236 | 0.0469 / 19,344 | 0.1570 / 37,148 |
| 100,000 | 0.3302 / 26,272 | 0.1546 / 26,384 | 0.7009 / 75,184 |
| 1,000,000 | 3.0787 / 96,064 | 1.3445 / 96,240 | 8.4122 / 444,420 |

The current ordinary candidate improves complete numeric load/consume time by
2.29 times against the public wheel, with approximately unchanged model RSS.
This combines row-batched binding conversion with the later core/source-handle
changes; it does not isolate quick-xml's contribution. The earlier same-core
binding-only measurement remains in [values-calls.md](values-calls.md).
Required speed against openpyxl holds in these workloads. Desired read speed
against python-calamine remains unmet and is recorded rather than claimed.

577 tests pass on each CPython 3.11–3.15. Ruff format/check, Rustfmt and Clippy
pass. Original upstream test bodies remain unchanged. Canonical Rust CI verifies
Linux/Windows Rust 1.88 plus latest tooling. Adapter CI also builds/tests native
Windows/macOS wheels independently of the release workflow.

Reproduce with installed candidate/reference packages and the compiled core
`benchmarks/measure.c` helper:

```sh
python benchmarks/optimized_modes.py --python /path/to/venv/bin/python \
  --measure /path/to/measure --runs 3 --output /tmp/modes.json
python benchmarks/values_calls.py --before-python /path/to/pypi/bin/python \
  --after-python /path/to/candidate/bin/python --measure /path/to/measure \
  --runs 3 --output /tmp/ordinary.json
python benchmarks/text_reads.py --python /path/to/venv/bin/python \
  --measure /path/to/measure --output /tmp/text.json
```

Raw numeric evidence: [optimized modes](results/optimized-modes.json) and
[ordinary latest core](results/values-calls-optimized-core.json).

## Unicode and escaped inline text

A separate workload includes Unicode and XML escaping in every cell.
Exact count and CRC32 sums check full payloads. The same installed candidate
and references are used, with a 64 MiB component allowance and no SST/temp files.

| Cells | CrabXL read_only | openpyxl read_only | python-calamine |
|---|---|---|---|
| 10,000 | 0.1281 / 18,300 | 0.3088 / 33,060 | 0.0986 / 18,416 |
| 100,000 | 0.9357 / 18,508 | 1.9162 / 34,576 | 0.6093 / 38,968 |

Required openpyxl speed holds; desired calamine speed remains unmet.
[Raw text results](results/text-reads.json).
