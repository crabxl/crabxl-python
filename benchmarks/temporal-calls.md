# Direct Python temporal replacement calls

Both engines execute identical owned Workbook/cell/value/getter calls, assigning four initial temporal kinds and replacing each with four kinds or a numeric value. Every cell is checked before saving twice. Public readback outside timing verifies every saved value/type/number format in both output files. The adapter carries canonical core IDs and pins 1b1a8726f266917ec589ae4eefc43d0e61c9b732 without a reference fallback. This supported overlap does not claim general style APIs or complete workbook parity.

One warmup plus five rotating serial cold-process wall/CPU/RSS samples include Python/import baseline. No builds/tests overlap timing. Run temporal_calls.py with the compiled core measure.c helper. Raw samples are results/temporal-calls.json. No equivalent prior adapter feature baseline is fabricated because prior value replacement lost temporal formatting.

| Cells / saves | crabxl seconds / peak RSS KiB | openpyxl seconds / peak RSS KiB |
| --- | --- | --- |
| 5,000 / 2 | 0.086289 / 15,716 | 0.280735 / 36,792 |
| 50,000 / 2 | 0.442111 / 20,684 | 0.986428 / 57,648 |

Required speed and desired RSS goals hold for these identical owned calls. Native competitor overlap remains separate. These timings include adapter conversions and are distinct from native Rust measurements.

Temporary storage is sampled every 25 ms with cleanup asserted. Native sampled medians are 225,525/2,313,531 bytes and public 251,144/2,583,828. Sampling can miss peaks; the adapter has no exact-spool counter. Both final ZIPs and adjacent atomic output staging are outside monitored TMPDIR. No speed optimization over an equivalent prior implementation is claimed.
