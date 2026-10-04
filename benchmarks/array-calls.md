# Direct Python array calls

Both engines execute identical supported Workbook/cell/ArrayFormula/property/save calls in explicitly owned worksheets. Six repeating text cases include None, empty, equals, non-equals/double-equals and a non-ASCII first character. Literal getters are checked before save. Every ordinary formula property and absent cache is checked through public openpyxl reload outside timing. The adapter calls the canonical core for expression presence/body conversion; no reference fallback is present.

The installed locked adapter pins core a3d957f992a90a174b0a81d0a2530203e1370bdd. This is partial feature overlap, not complete workbook compatibility. No earlier pin supported all these literal properties, so no equivalent prior-adapter baseline is fabricated.

Five rotating serial cold-process samples plus one warmup include Python/import baseline, wall/CPU and process peak RSS on the current Linux environment. Builds/public readback are excluded from timing. Run `python benchmarks/array_calls.py --measure /path/to/crabxl/benchmarks/measure` after compiling the core's original measure.c helper. Raw samples are results/array-calls.json.

| Array cells | crabxl seconds / KiB RSS | openpyxl seconds / KiB RSS |
| --- | --- | --- |
| 1,000 | 0.049374170 / 15,308 | 0.191936224 / 35,184 |
| 10,000 | 0.128547050 / 17,372 | 0.283662049 / 40,136 |

Speed and RSS targets hold for this same-call workload. These results include language conversion overhead and must be distinguished from Rust-only shared-template read benchmarks. Native competitor overlap acceptance remains separate.

Temporary files are sampled every 25 ms and cleanup is asserted after every process. Native median observed temporary bytes are zero, despite bounded worksheet spooling being part of save; short write/close peaks are missed by sampling and zero does not mean no temporary I/O or storage. Public medians are zero/563,337 bytes and can also miss peaks. The adapter currently exposes no exact native spool counter. Final ZIP output is stored outside the monitored temporary directory and excluded from spool accounting. These limitations remain explicit rather than counting missed samples as eliminated storage.
