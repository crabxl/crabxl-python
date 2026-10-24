# Mode comparison: read, write and edit

This report compares the published CrabXL release `0.1.0a11` from PyPI with
openpyxl, python-calamine and XlsxWriter. It measures each CrabXL mode against
the matching mode of the other libraries.

## Setup

- CrabXL 0.1.0a11, openpyxl 3.1.5, python-calamine 0.9.0, XlsxWriter 3.3.0.
- CPython 3.12.3 on Linux x86_64 (kernel 6.18.44), Intel Xeon at 2.10 GHz.
- The host has 4 logical CPUs. Every measured process is pinned to CPUs 2 and 3.
- All packages are installed from PyPI into one virtual environment.

Each sample runs in a fresh process. The wall time includes interpreter start,
imports, the operation and cleanup. The parent reads the peak RSS of each child
with `wait4`. Peak RSS includes the Python interpreter, which uses about 20 MiB
here.

Each size has one warmup round and three measured rounds. The case order
rotates in each round. The tables show the median of the three samples.

The input files have ten integer columns and consecutive values. openpyxl
`write_only` generates them before the measurement. All files are generated
again for each size.

| Cells | Rows | Input bytes | SHA-256 prefix |
|---:|---:|---:|---|
| 10,000 | 1,000 | 35,819 | `674e4b75cbdd60c5` |
| 100,000 | 10,000 | 325,473 | `53c9e50825626233` |
| 1,000,000 | 100,000 | 3,140,973 | `469ae3a58fd93ef2` |

## Operations

- Read: open the file and sum every value with `iter_rows(values_only=True)`.
  python-calamine uses `to_python()` on the first sheet.
- Write: create a new workbook, append the rows and save it.
- Edit: open the file in the standard mode, set ten cells to -1 and save to a
  new path.

Every read checks the count and the exact checksum. Every written or edited
file is read again with python-calamine and checked. The checks are outside
the measured time.

## Results

All values are median seconds / peak RSS MiB.

### Read

| Cells | CrabXL standard | CrabXL `read_only` | openpyxl standard | openpyxl `read_only` | python-calamine |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 0.079 / 24.2 | 0.083 / 23.9 | 0.209 / 29.5 | 0.223 / 25.8 | 0.058 / 20.3 |
| 100,000 | 0.148 / 27.0 | 0.129 / 24.0 | 0.887 / 66.7 | 0.698 / 27.0 | 0.129 / 27.0 |
| 1,000,000 | 0.569 / 55.0 | 0.520 / 23.9 | 10.909 / 427.2 | 6.064 / 34.4 | 0.719 / 95.4 |

### Write

| Cells | CrabXL standard | CrabXL `write_only` | openpyxl standard | openpyxl `write_only` | XlsxWriter default | XlsxWriter `constant_memory` |
|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | 0.102 / 24.2 | 0.099 / 24.0 | 0.231 / 28.6 | 0.232 / 25.5 | 0.144 / 23.9 | 0.150 / 22.8 |
| 100,000 | 0.259 / 27.0 | 0.273 / 23.9 | 0.932 / 59.6 | 0.793 / 25.5 | 0.470 / 36.0 | 0.469 / 22.6 |
| 1,000,000 | 1.770 / 54.9 | 1.799 / 23.9 | 11.253 / 365.1 | 7.163 / 25.5 | 4.640 / 157.4 | 3.761 / 22.6 |

### Edit

| Cells | CrabXL standard | openpyxl standard |
|---:|---:|---:|
| 10,000 | 0.095 / 24.8 | 0.289 / 30.2 |
| 100,000 | 0.238 / 27.5 | 1.548 / 75.5 |
| 1,000,000 | 1.668 / 55.5 | 18.850 / 522.7 |

## Limits

- python-calamine reads only. XlsxWriter writes only. Neither library edits a
  file. Compare them only in the operations that they support.
- Small sizes have a large spread between samples: up to 49% at 10,000 and
  100,000 cells. The spread at 1,000,000 cells is 21% or less.
- CrabXL `read_only` uses a producer thread. Its CPU time can be larger than
  its wall time.
- These cases use numeric values only. Text, styles, formulas and other
  features can give different results.
- The machine is a shared cloud host. Compare values only within this report.

## Reproduce

```sh
python benchmarks/modes_comparison.py --python /path/to/venv/bin/python \
  --cpus 2,3 --cells 10000 100000 1000000 --runs 3 \
  --output benchmarks/results/modes-comparison.json
```

Raw samples and environment data: [modes-comparison.json](../results/modes-comparison.json).
