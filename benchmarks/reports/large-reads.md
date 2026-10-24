# Large reads: CrabXL and python-calamine

This report measures large reads with the published CrabXL release `0.1.0a11`
from PyPI and python-calamine. openpyxl is not part of this test.

## Setup

- CrabXL 0.1.0a11, python-calamine 0.9.0, XlsxWriter 3.3.0.
- CPython 3.12.3 on Linux x86_64 (kernel 6.18.44), Intel Xeon at 2.10 GHz,
  16 GiB of memory.
- The host has 4 logical CPUs. Every measured process is pinned to CPUs 2 and 3.

Each sample runs in a fresh process. The wall time includes interpreter start,
imports, the read and cleanup. The parent reads the peak RSS of each child with
`wait4`. Peak RSS includes the Python interpreter, which uses about 20 MiB.
Each input has one warmup round and three measured rounds. The case order
rotates in each round. The tables show the median of the three samples.

## Inputs

- Numeric: 10,000,000 integer cells in 1,000,000 rows and 10 columns. XlsxWriter
  writes the file in the `constant_memory` mode. The file has 31,412,539 bytes.
- NYC 311: 1,000,001 rows and 41 columns, with 28,478,615 cells that have a value.
  The file has 171,042,932 bytes. [nyc311_fixture.py](../nyc311_fixture.py) builds it
  from NYC Open Data. It has the same shape as the sample in the calamine
  README (1,000,001 rows, 41 columns and 28,056,975 values). It is not the same
  file. Text is in a shared string table. Dates and numbers are numeric cells.

## Operation

Each case reads every row of the first sheet and counts the cells that have a
value. CrabXL uses `iter_rows(values_only=True)`. python-calamine uses
`iter_rows()`. All cases must read the same number of values. The numeric read
also checks the exact checksum.

## Results

### Numeric, 10,000,000 cells

| Case | Seconds | Peak RSS MiB | CPU seconds |
|---|---:|---:|---:|
| CrabXL standard | 4.95 | 335.1 | 4.86 |
| CrabXL `read_only` | 3.53 | 23.9 | 6.30 |
| python-calamine | 6.34 | 706.3 | 6.29 |

### NYC 311, 1,000,001 rows by 41 columns

| Case | Seconds | Peak RSS MiB | CPU seconds |
|---|---:|---:|---:|
| CrabXL standard | 26.77 | 1,676.2 | 26.52 |
| CrabXL `read_only` | 35.05 | 55.6 | 53.84 |
| python-calamine | 32.66 | 2,391.4 | 32.36 |

## Limits

- On the NYC 311 file, CrabXL `read_only` is slower than the CrabXL standard
  mode. It uses about one thirtieth of the memory.
- CrabXL `read_only` uses a producer thread. Its CPU time can be larger than
  its wall time.
- python-calamine reads the full sheet into memory before `iter_rows()` returns
  rows. CrabXL `read_only` reads the sheet in bounded batches.
- The spread between samples is up to 17%.
- The machine is a shared cloud host. Compare values only within this report.

## Reproduce

```sh
python benchmarks/nyc311_fixture.py --cache /tmp/nyc311 --output nyc311-1m.xlsx
python benchmarks/large_reads.py --python /path/to/venv/bin/python \
  --cpus 2,3 --nyc311 nyc311-1m.xlsx --runs 3 \
  --output benchmarks/results/large-reads.json
```

Raw samples and environment data: [large-reads.json](../results/large-reads.json).
