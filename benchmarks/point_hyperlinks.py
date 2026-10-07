import sys
import time
from pathlib import Path

from crabxl import Workbook, load_workbook

n = int(sys.argv[1])
p = Path(sys.argv[2])
b = Workbook()
s = b.active
start = time.perf_counter()
for i in range(1, n + 1):
    s.cell(i, 1).hyperlink = f"https://example.org/item/{i}"
prepare = time.perf_counter() - start
start = time.perf_counter()
b.save(p)
save = time.perf_counter() - start
b.close()
start = time.perf_counter()
b = load_workbook(p)
s = b.active
checksum = sum(len(s.cell(i, 1).hyperlink.target) for i in range(1, n + 1))
s.cell(n, 1).hyperlink.target = "https://example.org/changed"
b.save(str(p) + ".edited.xlsx")
edit = time.perf_counter() - start
rss = next(
    line.split()[1]
    for line in Path("/proc/self/status").read_text().splitlines()
    if line.startswith("VmHWM:")
)
print(
    f"rows={n} prepare={prepare:.6f} save={save:.6f} load_scan_edit_save={edit:.6f} checksum={checksum} peak_rss_kib={rss}"
)
