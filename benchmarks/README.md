# Benchmarks

One suite compares CrabXL for Python with other Python XLSX libraries on three
tasks. The latest results are in [results/results.md](results/results.md).

| Scenario | Task | Libraries |
|---|---|---|
| Read | Open the file and visit every cell value. | crabxl, wolfxl, oxlsx, python-calamine (`iter_rows` and `to_python`), fastexcel, openpyxl |
| Write | Create the sheet with `append` (or `write_row`) and save it. | crabxl, wolfxl, oxlsx, XlsxWriter, openpyxl |
| Edit | Load the file, change one cell in every 100 rows, append 100 rows and save. | crabxl, wolfxl (`modify=True`), oxlsx, openpyxl |

crabxl, wolfxl and openpyxl run in their normal mode and in their
`read_only` or `write_only` mode. XlsxWriter runs in normal and
`constant_memory` mode. python-calamine and fastexcel only read, and XlsxWriter
only writes.

openpyxl is slow, so it runs on the small size only.

## Data

XlsxWriter generates the input, so no compared reader reads its own output.
Each row has 10 cells: an integer, a decimal number, a repeated text (1,000
different values), a unique text, a date, a boolean and four decimal numbers.
The [Rust suite](https://github.com/crabxl/crabxl/tree/main/benchmarks) uses
the same data.

| Size | Rows × columns | Cells | File | Scenarios |
|---|---:|---:|---:|---|
| small | 10,000 × 10 | 100,000 | 0.6 MB | all |
| medium | 100,000 × 10 | 1,000,000 | 6 MB | all |
| large | 1,000,000 × 10 | 10,000,000 | 60 MB | all |
| xl | 1,000,000 × 100 | 100,000,000 | about 370 MB | read |
| xxl | 1,000,000 × 280 | 280,000,000 | about 1 GB | read |
| nyc311 | 1,000,001 × 41 | 28,056,975 non-empty | 181 MB | read |

Sheets wider than 10 columns repeat the same 10-column pattern. The xl, xxl
and nyc311 files are read only, by the readers that can hold them in memory.
They come from the Rust suite: XlsxWriter can only write files of that size in
constant-memory mode, which stores text inline instead of in a shared string
table. nyc311 is the NYC 311 data set from the calamine README, saved by
Excel; the Rust suite's README explains how to build it. Run the Rust suite
first, then pass its data folder with `--fixtures`. Readers count non-empty
cells only and read the first worksheet.

## Method

- Each case runs in a new Python process. Time is the wall time of the whole
  process, including interpreter start-up and imports. Memory is the peak
  resident memory of the process (`PeakWorkingSetSize` on Windows,
  `ru_maxrss` on Linux and macOS).
- On Windows, the suite starts the base interpreter directly with the virtual
  environment on `PYTHONPATH`. The `python.exe` of a virtual environment is a
  launcher process, so its memory is not the memory of the case.
- Each case runs two ways. **All CPUs**: the library can use every logical CPU,
  as in normal use. **One CPU**: the process starts suspended, is pinned to the
  same single logical CPU for every library, and only then runs. This shows
  how fast a library is without extra threads. The tables also show the CPU
  time (user plus kernel) of the process.
- Each case runs one time to warm the file cache, then three times (one time
  if the warm-up takes more than 10 seconds). The
  tables show the median of the three.
- Safety limits that would reject the large files are raised for every library
  that has them (crabxl memory limit, wolfxl size limits).
- Run the suite on an idle computer that is connected to power. Do not run
  builds or tests at the same time.
- Every case prints the number of cells it handled. Check `cells` in
  `results.json` to confirm that all libraries did the same work.
- A case that takes more than 5 minutes is shown as a timeout. If a case takes
  more than 30 seconds, it is not run at the next size (10 times more rows) and
  is shown as an estimated timeout. A case that raises an error is shown as
  failed.

## Run

Install the package and the compared libraries in one environment:

```sh
python -m pip install . wolfxl oxlsx python-calamine fastexcel pyarrow xlsxwriter openpyxl==3.1.5
python benchmarks/run.py
python benchmarks/run.py --sizes small --runs 1 --libraries crabxl openpyxl
python benchmarks/run.py --sizes xl xxl nyc311 --fixtures ../crabxl/benchmarks/data
```

Generated input files are kept in `benchmarks/data/` (ignored by Git).
