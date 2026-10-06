# A8 buffered scalar Python integration

Core revision `bfeb2714dcea31f0facaa5c999547b071e7a55c8` supplies the bounded
numeric, Boolean and SST-ID decoder. The adapter remains unchanged apart from
its exact dependency pin. A fresh release wheel passes 547 compatibility tests,
Ruff format/check and strict Clippy.

The baseline is the A7 release wheel built from adapter
`e0fe86ad83390c3788759bc514a1400660ddd83a`. Raw installed-module hashes,
fixture hashes, versions and individual samples are in the
[ordinary report](results/alpha8-buffered-scalars-python-normal.json) and
[read-only report](results/alpha8-buffered-scalars-python-stream.json).
Each scale has one warmup and three rotating serial cold-process samples,
without overlapping compilation. Generation is excluded; imports, loading,
iteration, checksums and cleanup are included. Both CrabXL modes use the same
1 GiB component allowance. Calamine retains a noneditable decoded range, so its
iterator is not equivalent to a bounded ZIP stream.

| One million numeric cells | A7 seconds | Candidate seconds | python-calamine seconds |
| --- | ---: | ---: | ---: |
| Ordinary load and values iteration | 0.740572 | 0.404173 | 0.526771 |
| Read-only load and values iteration | 0.659802 | 0.297117 | 0.524083 |

Ordinary candidate median peak RSS is 52,236 KiB versus calamine's 87,716 KiB;
read-only candidate RSS is 20,248 KiB versus 87,764 KiB. Timing split fields are
diagnostic only: deferred parsing must stay in the total comparison.

This establishes improvement for the generated numeric workload, not general
Python read acceptance. Unique shared strings remain slower in core comparisons;
large real-world NYC data, all text layouts, editing/write targets and conservative
model resource accounting remain separate gates. A8 has not been released.

## Shared-text integration

The adapter now pins `4f25c545684a03a879d717c27cf1bb91acd14676`, adding core
ADR 0078's simple SST preparation. A rebuilt wheel passes all 547 compatibility
tests, Ruff and Clippy. Compared with the same A7 baseline, complete reads of
one million unique shared strings include conversion, exact per-cell text/order
assertions, imports and cleanup. RAM SST uses an explicit 256 MiB component
budget with a 1 GiB model allowance; no read temporary files are used.

| Unique shared strings | A7 seconds | Candidate seconds | python-calamine seconds |
| --- | ---: | ---: | ---: |
| Ordinary load and values iteration | 1.646715 | 1.054141 | 1.300432 |
| Read-only load and values iteration | 1.347921 | 0.897952 | 1.288530 |

Ordinary median RSS is 239,752 KiB versus calamine's 321,748 KiB. Read-only
RSS is 161,992 KiB versus 321,716 KiB; retained SST metadata is additional to
the bounded row stream. The workload is generated plain ASCII shared text,
not arbitrary rich/Unicode XML or the real NYC fixture. Cold-process CPU time
can exceed wall time for read-only producer/consumer overlap and is retained
in the [ordinary](results/alpha8-direct-sst-python-normal.json) and
[read-only](results/alpha8-direct-sst-python-stream.json) raw reports.

## Writer integration

The adapter now pins `b5990868623e31b8cc3e47f4ba3bf0f906e54865`, adopting
core ADR 0079's byte-oriented XML escaping. A fresh wheel passes 547 tests,
Ruff and Clippy. Python write-only numeric append/save compared with A7 is
1.355817 versus 1.377241 seconds, with 20,524 versus 20,432 KiB median RSS.
Both produce 2,942,955-byte archives and report a 32,866,902-byte spool peak;
all values are independently verified after timing. These small differences
do not establish a meaningful Python numeric-write improvement.
[Raw observations](results/alpha8-byte-escape-python-writes.json) include native
module hashes and complete cold-process conversion/save costs. The core's
larger Unicode/text improvements remain distinct from this numeric workload.
