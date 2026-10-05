# Direct scalar rows and buffered streaming

This candidate pins canonical core
`21f1f11e2e2d44ba7d51b15e652fa3a5179dbe09`. The prior installed adapter pins
`b6277d039233f598e32f288003c566407afe9a73`. Both are development builds carrying
the unchanged alpha.6 version; this report is not release acceptance.

Ordinary loaded values iteration uses the canonical ordered row cursor instead
of repeated point lookups. Scalar Python objects cross the boundary without a
tagged Python tuple and Python decoding call for every cell. Temporal values use
the existing decoder; structured formulas retain live editable cell views.
Read-only iteration consumes already buffered rows without releasing and
reacquiring the GIL, but releases it for channel waits and worker joins. Buffer
and producer limits are unchanged. Both modes share the conversion helper.

Python 3.12.14, release Rust 1.99, Linux x86-64, two-CPU cgroup quota. One warmup
and three rotating serial cold-process samples per engine and scale; builds,
tests and generation are excluded. Wall time includes imports and cleanup.
The identical numeric input, complete count and exact checksum are verified.
The editable model allowance is 1 GiB, not an RSS cap. Neither read mode creates
temporary files for this workload. Reference python-calamine is 0.8.2 and is a
benchmark-only dependency; its installed package features are not claimed to
match the separately pinned native calamine comparison.

At 100,000 rows by 10 columns:

| Completed operation | Before wall (s) | After wall (s) | Calamine wall (s) | Before RSS (KiB) | After RSS (KiB) | Calamine RSS (KiB) |
|---|---:|---:|---:|---:|---:|---:|
| Ordinary editable load and values scan | 1.0385 | 0.7813 | 0.5628 | 51,824 | 51,864 | 87,712 |
| Read-only load and values scan | 0.6388 | 0.6227 | 0.5230 | 20,284 | 20,384 | 87,604 |

Ordinary total time decreases about 25%; values traversal decreases from 0.3270
to 0.1019 seconds. Full model loading still takes about 0.6205 seconds.
Read-only total time decreases about 3%; gains are modest and remain sensitive
to producer scheduling. Both are still slower than python-calamine. Ordinary
and read-only peak RSS are lower on this input; this does not establish universal
RAM superiority or performance on the unavailable NYC workbook.

The probe now constructs the row iterator before recording `open_seconds`.
For ordinary CrabXL this includes deferred materialization, so that field must
not be compared with older reports that counted lazy opening alone. Complete
process wall times retain the same operation boundary. Calamine materializes a
noneditable range; it is not a bounded ZIP worksheet stream or a preserving
editable workbook. Its timings provide the overlapping value-reading target,
not evidence of equivalent editing or streaming capabilities.

All 547 compatibility/resource tests, Ruff format/check and strict Clippy pass.
Existing shared workflows cover sparse gaps, missing rows, edits between rows,
live structured formulas, stream cancellation and resource cleanup.

Both streaming and full-model loading continue to target lower elapsed time
than calamine; full-model peak RSS also targets a lower value. Parser/model and
Python conversion costs must be recorded separately without excluding deferred
work from the headline. Pandas/Polars integration and bounded dataframe delivery
remain planned and are not implemented or accepted by this checkpoint.

Raw samples and installed hashes:
[ordinary](results/alpha7-direct-values-python.json),
[read-only](results/alpha7-buffered-python-read-only.json).
