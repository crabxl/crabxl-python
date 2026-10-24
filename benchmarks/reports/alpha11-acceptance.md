# A11 feature acceptance: Windows constrained-resource measurements

Measured on 2026-10-21: Windows 11 x86_64, CPython 3.12.14, Rust 1.99 release
extension, openpyxl 3.1.5. Every process inherits **one logical CPU** and
BelowNormal priority, as requested by the user. No builds or tests overlap the
samples. These are constrained-machine measurements, not general throughput
claims or comparisons with calamine/rust_xlsxwriter.

The native candidate is based on core `a43ab98` plus ADR 0102; the adapter is
based on `022e829` plus ADR 0042 and selective alias relocation. A temporary
local Cargo patch selects the candidate core; it is not a published revision
pin. The exact measured extension SHA256 is
`704c89809ae26dae08b69f4757328a69e7a987f24b99e59ee3089ae1a695b9ca`.
The same native source was subsequently published as
`dbb911f131d24c7e72b7638e4e17099527828ef1`; the candidate adapter now pins that
Git revision without the temporary local patch.

Each engine/mode has one 50-record warmup, then three fresh-process samples at
500 and 2,000 records, alternating engine order per pair. Input generation,
builds and independent verification are outside measured operation time.
Imports, workbook work, output and cleanup are included. Every output is reopened
with openpyxl and checked for the numeric checksum, final numeric/rich value,
named appearance, hyperlink target and applicable merge count. Peak working set
is sampled from Windows before reference reopening, without baseline subtraction.

Owned and loaded workflows use one named numeric style, editable rich text,
hyperlinks and 2x2 merges, followed by row insertion, range movement and two
saves to the same target. Records are three rows apart, so 2,000 records cover
about 6,000 sparse rows. Loaded input is generated in a separate process.
Write-only uses named numeric style, rich snapshots and hyperlinks, with one save;
it has no merge/edit operations. Compare engines within a mode, not modes as
equivalent feature workloads.

## Median wall time and peak working set

| Records | Mode | CrabXL seconds / MiB | openpyxl seconds / MiB |
| ---: | --- | ---: | ---: |
| 500 | Owned | 0.2363 / 28.85 | 0.8170 / 37.29 |
| 500 | Loaded | 0.0988 / 24.80 | 0.7671 / 37.96 |
| 500 | Write-only | 0.2007 / 23.86 | 0.4943 / 32.54 |
| 2,000 | Owned | 1.3693 / 42.57 | 2.4189 / 53.83 |
| 2,000 | Loaded | 0.2609 / 27.28 | 2.3454 / 55.11 |
| 2,000 | Write-only | 0.5627 / 23.82 | 0.8813 / 36.01 |

CrabXL is faster and has lower peak working set in these six measured pairs.
CPU time is also lower in every pair; raw samples retain CPU, output size and
checksum values. This does not establish complete baseline performance.

## Temporary storage and corrected regression

A thread samples files in the dedicated temporary directory every 10 ms,
excluding the final output. All samples verify no temporary files remain after
save/close. Sampling is a lower bound on actual transient disk peaks, especially
for brief atomic-output files; it is not an exact I/O-byte counter.

At 2,000 records, median sampled temporary bytes are 522,447 vs 935,594 for owned,
34,629 vs 935,594 for loaded, and **815,306 vs 689,661 for write-only**
(CrabXL vs openpyxl). The bounded native group/event spools trade additional
write-only disk space for lower measured memory. Disk I/O throughput was not
separately instrumented; cleanup/failure behavior also has deterministic tests.

Initial measurements exposed worksheet-wide rich/hyperlink rebinding after
every merge. A fresh 2,000-record sample took about 41.5 seconds. Profiling a
500-record case identified repeated `_relocate_rich_views`/`_bind`/`_observe`
work. The adapter now updates bindings only for positions actually changed by
the operation. Its regressions passed before the final alternating measurements.
The partial initial run is retained as diagnostic evidence, not pooled with the
final candidate samples.

Reproduce with `benchmarks/alpha11_acceptance.py ENGINE MODE COUNT DIRECTORY
[SOURCE]`; use mode `generate` to prepare a source in a separate process. Apply
the same CPU/priority settings to both engines and keep other validation idle.

- [Final raw samples](../results/alpha11-acceptance.jsonl)
- [Initial diagnostic samples](../results/alpha11-before-alias-filter.jsonl)
