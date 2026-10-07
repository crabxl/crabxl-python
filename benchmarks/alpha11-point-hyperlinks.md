# Python point hyperlink checkpoint

CPython 3.12.14, rebuilt wheel pinned to core e74d865. Three fresh serial processes
per size; no build/test overlaps. [Worker](point_hyperlinks.py) generates point
metadata through Cell.hyperlink, saves, reloads, accesses every live point, changes
the last target and preserves the source package. [Raw observations](alpha11-point-hyperlinks.txt).

| Rows | Median preparation | Median initial save | Median load/scan/edit/save | Median process peak RSS |
| --- | --- | --- | --- | --- |
| 2,000 | 0.030425 s | 0.007387 s | 0.045656 s | 28,272 KiB |
| 8,000 | 0.137969 s | 0.026123 s | 0.216805 s | 50,576 KiB |

Checksums are 56,893 and 230,893. VmHWM includes runtime, original workbook and
requested live Python views, so it cannot be compared directly with the native
probe. Canonical point targets are converted individually. Requested view identity
is retained, which adds Python memory; this is not a memory optimization claim.
Caller-owned outputs are excluded from managed temporary storage; this worker
does not measure physical temporary disk high-water usage. Independent openpyxl
readback is covered by the lifecycle test. No competitor timing is claimed.
