# Python independent hyperlink reference checkpoint

Same fresh serial three-process workload and [worker](point_hyperlinks.py) as the
[initial point report](alpha11-point-hyperlinks.md), rebuilt against core 3754bb8.
No tests/builds overlap measurement. [Raw observations](alpha11-hyperlink-references.txt).

| Rows | Median preparation | Median initial save | Median load/scan/edit/save | Median peak RSS |
| --- | --- | --- | --- | --- |
| 2,000 | 0.031892 s | 0.007573 s | 0.045049 s | 28,240 KiB |
| 8,000 | 0.131358 s | 0.027092 s | 0.212798 s | 50,968 KiB |

Checksums remain 56,893 and 230,893. These ordinary point results do not establish
an optimization or measure large shared-alias groups. Public view retention and
conversion are included in Linux process VmHWM. Temporary physical disk high-water
usage is not measured; output files are caller-owned. Readback/alias correctness is
checked by the lifecycle test rather than timing thresholds. No competitor claim.
