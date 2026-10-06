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
