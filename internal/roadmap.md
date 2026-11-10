# Roadmap

A12 completed openpyxl 3.1.5 compatibility. A13 (performance and memory) is
done; the core [roadmap](https://github.com/crabxl/crabxl/blob/main/internal/roadmap.md)
has the targets and results. The beta is next.

## A13 in this repository (done)

- Rows of plain values (`None`, `bool`, `int`, `float`, `str` and naive date
  and time values) are converted in Rust when appended. Other values use the
  Python conversion, so errors are unchanged.
- Appending to a loaded sheet that Python has not read yet does not load the
  sheet; the core streams the rows on save.
- 100,000-row write: 1.79 s to 0.89 s. Edit of 1,000,000 rows: 34 s to 16.6 s.

Before the beta, pin the optimized core revision. The core must be pushed
first so that the pinned revision resolves.

## Optional: benchmark results

Rerun `benchmarks/run.py` on an idle computer and commit the results. This is
not needed for the beta.

## Beta

Release `0.1.0b1` with the core beta.
