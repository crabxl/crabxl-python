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

| Size | Rows | Cells |
|---|---:|---:|
| small | 10,000 | 100,000 |
| medium | 100,000 | 1,000,000 |
| large | 1,000,000 | 10,000,000 |

## Method

- Each case runs in a new Python process. Time is the wall time of the whole
  process, including interpreter start-up and imports. Memory is the peak
  resident memory of the process (`PeakWorkingSetSize` on Windows,
  `ru_maxrss` on Linux and macOS).
- On Windows, the suite starts the base interpreter directly with the virtual
  environment on `PYTHONPATH`. The `python.exe` of a virtual environment is a
  launcher process, so its memory is not the memory of the case.
- Each case runs one time to warm the file cache, then three times. The
  tables show the median of the three.
- Run the suite on an idle computer that is connected to power. Do not run
  builds or tests at the same time.
- Every case prints the number of cells it handled. Check `cells` in
  `results.json` to confirm that all libraries did the same work.
- A case that takes more than 15 minutes is shown as a timeout. If a case takes
  more than 90 seconds, it is not run at the next size (10 times more rows) and
  is shown as an estimated timeout. A case that raises an error is shown as
  failed.

## Run

Install the package and the compared libraries in one environment:

```sh
python -m pip install . wolfxl oxlsx python-calamine fastexcel pyarrow xlsxwriter openpyxl==3.1.5
python benchmarks/run.py
python benchmarks/run.py --sizes small --runs 1 --libraries crabxl openpyxl
```

Generated input files are kept in `benchmarks/data/` (ignored by Git).
