"""Measure large reads with CrabXL and python-calamine.

Inputs:

- numeric: 1,000,000 rows by 10 integer columns (10,000,000 cells), generated
  by this script.
- nyc311: the file from nyc311_fixture.py (1,000,001 rows by 41 columns, text
  in a shared string table, dates and numbers).

Cases: CrabXL in the standard mode, CrabXL in the read_only mode, and
python-calamine. Each case reads every row and counts the cells that have a
value. CrabXL uses iter_rows(values_only=True). python-calamine uses
iter_rows() on the first sheet.

Each sample runs in a fresh process that is pinned to a fixed set of CPUs.
The wall time includes interpreter start, imports, the read and cleanup. The
parent reads the peak RSS of each child with wait4.

Usage:
    python benchmarks/large_reads.py --python /path/to/venv/bin/python \
        --cpus 2,3 --nyc311 nyc311-1m.xlsx --runs 3 \
        --output benchmarks/results/large-reads.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

NUMERIC_ROWS = 1_000_000
NUMERIC_COLUMNS = 10

CASES: list[tuple[str, str]] = [
    ("crabxl", "standard"),
    ("crabxl", "read_only"),
    ("python-calamine", "standard"),
]

PACKAGES = ["crabxl", "python-calamine", "XlsxWriter"]


def case_name(case: tuple[str, str]) -> str:
    return "/".join(case)


def has_value(value) -> bool:
    return value is not None and value != ""


def worker(library: str, mode: str, path: str, numeric: bool) -> dict:
    count = 0
    total = 0
    if library == "python-calamine":
        from python_calamine import CalamineWorkbook

        book = CalamineWorkbook.from_path(path)
        rows = book.get_sheet_by_index(0).iter_rows()
    else:
        import crabxl

        book = crabxl.load_workbook(path, read_only=(mode == "read_only"))
        rows = book.active.iter_rows(values_only=True)
    for row in rows:
        for value in row:
            if has_value(value):
                count += 1
                if numeric:
                    total += int(value)
    book.close()
    return {"count": count, "total": total}


def generate_numeric(python: str, path: Path) -> None:
    code = (
        "import xlsxwriter\n"
        f"book = xlsxwriter.Workbook({str(path)!r}, {{'constant_memory': True}})\n"
        "sheet = book.add_worksheet()\n"
        f"for r in range({NUMERIC_ROWS}):\n"
        f"    start = r * {NUMERIC_COLUMNS}\n"
        f"    sheet.write_row(r, 0, range(start, start + {NUMERIC_COLUMNS}))\n"
        "book.close()\n"
    )
    subprocess.run([python, "-c", code], check=True)


def measure(
    python: str, cpus: set[int], case, path: Path, numeric: bool
) -> tuple[dict, dict]:
    library, mode = case
    command = [
        python,
        __file__,
        "--worker",
        library,
        mode,
        str(path),
        "1" if numeric else "0",
    ]
    start = time.perf_counter()
    child = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        preexec_fn=lambda: os.sched_setaffinity(0, cpus),
    )
    output = child.stdout.read()
    _, status, usage = os.wait4(child.pid, 0)
    wall = time.perf_counter() - start
    if os.waitstatus_to_exitcode(status) != 0:
        raise RuntimeError(f"{case_name(case)} failed on {path.name}")
    sample = {
        "seconds": round(wall, 6),
        "cpu_seconds": round(usage.ru_utime + usage.ru_stime, 6),
        "peak_rss_kib": usage.ru_maxrss,
    }
    return sample, json.loads(output)


def environment(python: str, cpus: set[int]) -> dict:
    code = (
        "import importlib.metadata as m, json, sys\n"
        f"print(json.dumps({{'python': sys.version.split()[0], 'packages': {{p: m.version(p) for p in {PACKAGES!r}}}}}))\n"
    )
    info = json.loads(
        subprocess.run(
            [python, "-c", code], check=True, capture_output=True, text=True
        ).stdout
    )
    cpu_model = next(
        (
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        ),
        "",
    )
    return {
        **info,
        "platform": platform.platform(),
        "cpu_model": cpu_model,
        "logical_cpus_on_host": os.cpu_count(),
        "memory_bytes_on_host": os.sysconf("SC_PAGE_SIZE")
        * os.sysconf("SC_PHYS_PAGES"),
        "pinned_cpus": sorted(cpus),
    }


def run_input(
    python: str, cpus: set[int], name: str, path: Path, numeric: bool, runs: int
) -> dict:
    result = {
        "input": name,
        "input_bytes": path.stat().st_size,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "cases": {case_name(c): [] for c in CASES},
    }
    counts = set()
    for round_index in range(runs + 1):
        shift = round_index % len(CASES)
        for case in CASES[shift:] + CASES[:shift]:
            sample, values = measure(python, cpus, case, path, numeric)
            counts.add(values["count"])
            if numeric:
                cells = NUMERIC_ROWS * NUMERIC_COLUMNS
                if values != {"count": cells, "total": cells * (cells - 1) // 2}:
                    raise RuntimeError(f"{case_name(case)} read wrong values: {values}")
            if round_index > 0:  # round 0 is the warmup
                result["cases"][case_name(case)].append(sample)
        print(f"{name}: round {round_index} done", file=sys.stderr, flush=True)
    if len(counts) != 1:
        raise RuntimeError(f"the cases read different value counts: {sorted(counts)}")
    result["values"] = counts.pop()
    result["medians"] = {
        name: {
            key: statistics.median(s[key] for s in samples)
            for key in ("seconds", "cpu_seconds", "peak_rss_kib")
        }
        for name, samples in result["cases"].items()
    }
    return result


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        library, mode, path, numeric = sys.argv[2:6]
        print(json.dumps(worker(library, mode, path, numeric == "1")))
        return

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--python", required=True, help="interpreter with all packages installed"
    )
    parser.add_argument("--cpus", default="2,3", help="CPUs for every measured process")
    parser.add_argument("--nyc311", required=True, help="file from nyc311_fixture.py")
    parser.add_argument(
        "--runs", type=int, default=3, help="measured samples per case after one warmup"
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cpus = {int(c) for c in args.cpus.split(",")}
    report = {
        "method": (
            "Fresh process per sample, pinned to the listed CPUs. One warmup, then the measured samples. "
            "The case order rotates in each round. Wall time includes interpreter start, imports and cleanup. "
            "Peak RSS comes from wait4. Every case must read the same number of values."
        ),
        "environment": environment(args.python, cpus),
        "inputs": [],
    }
    with tempfile.TemporaryDirectory(prefix="crabxl-large-") as tmp:
        numeric = Path(tmp) / "numeric-10m.xlsx"
        generate_numeric(args.python, numeric)
        report["inputs"].append(
            run_input(args.python, cpus, "numeric", numeric, True, args.runs)
        )
    report["inputs"].append(
        run_input(args.python, cpus, "nyc311", Path(args.nyc311), False, args.runs)
    )
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
