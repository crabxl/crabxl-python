# Direct Python data-table calls

Both engines execute identical owned Workbook/cell/DataTableFormula/property/save calls. Six repeating literals cover empty, false/zero, opaque, whitespace and escaped strings across all five flag properties. Assigned getters and every saved reference/flag/cache are checked; public readback is outside timing. The adapter uses core a090dc45d90e1b506eaf50df8d2482bd9c935bae without a reference fallback. This is supported feature overlap, not full workbook compatibility. No earlier adapter accepts every raw flag/edit case, so no equivalent old baseline is fabricated.

One warmup plus five rotating serial cold-process wall/CPU/RSS samples include Python/import baseline. Builds/tests do not overlap timed samples. Run table_calls.py with the compiled core measure.c helper. Raw samples: results/table-calls.json.

| Cells | crabxl seconds / peak RSS KiB | openpyxl seconds / peak RSS KiB |
| --- | --- | --- |
| 1,000 | 0.060433359 / 15,628 | 0.186752033 / 35,348 |
| 10,000 | 0.196756911 / 20,492 | 0.314956828 / 41,012 |

Required speed and desired RSS goals hold for this identical-call owned workload. These timings include binding conversion and must not be conflated with core-only/lazy-edit results. Native competitor overlap remains separate.

Temporary storage is sampled every 25 ms and cleanup checked. Native sampled medians are zero/1,372,339 bytes, public 65,915/1,442,636 bytes. Short spool peaks may be missed; there is no adapter exact-spool counter. Native zero at the smaller size is not no temporary I/O. Final ZIP output is outside monitored temporary storage and excluded. No improvement over an equivalent prior implementation is claimed.
