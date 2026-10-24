# Array-call regression after literal reference ownership

The installed locked adapter pins core 5ecb5bd6e032294d7c18ae461befe61f86d88b79. This repeats the supported identical owned Workbook/cell/ArrayFormula/property/save workload documented in array-calls.md; the earlier evidence is retained. Current raw samples are results/literal-reference-array-calls.json. No builds/tests overlap samples. Five rotating serial cold-process measurements plus one warmup include Python/import baseline; public formula/cache verification is outside timing.

| Cells | crabxl seconds / peak RSS KiB | openpyxl seconds / peak RSS KiB |
| --- | --- | --- |
| 1,000 | 0.049568932 / 15,188 | 0.192520357 / 35,188 |
| 10,000 | 0.129466989 / 17,360 | 0.287266251 / 40,140 |

The larger native result is approximately 0.7% slower than the prior separately measured adapter checkpoint, not an optimization claim or paired isolated comparison. Required openpyxl speed and desired RSS goals hold for this workload; no native competitor or full workbook parity is implied.

Native sampled temporary medians are zero and public medians zero/530,437 bytes. Sampling every 25 ms misses short spool peaks; zero does not mean absent temporary storage/I/O. The adapter exposes no exact spool counter. Cleanup is asserted after every process, and final ZIP output is outside monitored temporary space. Empty/qualified/opaque references are correctness-tested separately; this regression uses ordinary A1 references.
