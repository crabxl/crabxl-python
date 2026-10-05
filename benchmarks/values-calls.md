# Ordinary editable values iteration

This checkpoint batches native value conversion by row for
`iter_rows(values_only=True)` and `Worksheet.values`. Scalar values no longer
require temporary Python Cell views, weak-reference bookkeeping, or per-cell
native pending/model/get calls. Structured formula values retain their live
Cell binding and identity. Pending changes are synchronized between rows.
Owned-model missing cells retain ordinary iteration's creation semantics.

The Rust parser and original-package editor are unchanged. The Python adapter
still materializes the editable worksheet; this does not implement `read_only`
or `write_only`, or establish parity with calamine's read-only feature set.

Reproduce with separately installed release and candidate wheels:

```sh
python benchmarks/values_calls.py \
  --before-python /path/to/released/venv/bin/python \
  --after-python /path/to/candidate/venv/bin/python \
  --measure /path/to/compiled/core/benchmarks/measure
```

The released baseline is PyPI 0.1.0a1. Both adapter binaries use core revision
`d39d5e8f413a0f239075464906f984e6c66c8350`. Candidate package metadata remains
0.1.0a1 for local testing; the public release is unchanged. Installed Python
source/native binary hashes identify the exact candidates in
[raw results](results/values-calls.json).

One warmup and five rotating serial cold-process samples per implementation
include imports, ordinary `load_workbook`, complete values iteration and
cleanup. Generated files contain ten numeric columns. Every run checks the
cell count and exact checksum. Generation and compilation are excluded; no
other builds or tests overlap timing. Python is 3.12.14 and the reference is
openpyxl 3.1.5. The explicit editable-model allowance is 1 GiB; it is not a
whole-process memory ceiling. Numeric reading requires no temporary storage.

| Cells | Released seconds / RSS KiB | Candidate seconds / RSS KiB | openpyxl ordinary seconds / RSS KiB |
|---|---|---|---|
| 10,000 | 0.0660 / 18,876 | 0.0456 / 18,944 | 0.1579 / 36,712 |
| 100,000 | 0.3297 / 25,824 | 0.1483 / 25,856 | 0.6705 / 74,948 |
| 1,000,000 | 3.1917 / 95,812 | 1.1955 / 95,792 | 8.0764 / 444,000 |

At one million cells, complete read/consume time improves by 2.67 times
(62.5% less time), with approximately unchanged peak RSS. These results cover
numeric ordinary-model iteration, not every workbook or feature. Open and
iterate phase times are diagnostic: CrabXL loads sheet data lazily during
iteration while openpyxl loads eagerly, so individual phases are not equivalent.

552 correctness tests pass. New coverage verifies pending edits between yielded
rows, sparse bounded iteration, and the identity/edit/save behavior of a loaded
array formula returned through values iteration. Original upstream test bodies
remain unchanged. Output conversion retains one row at a time, bounded by Excel
column limits and the existing model/value allowances; caller-retained output is
additional memory. Complete source materialization and core XML throughput
remain separate optimization targets.
