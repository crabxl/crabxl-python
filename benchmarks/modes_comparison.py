"""Compare CrabXL modes with openpyxl, python-calamine and XlsxWriter.

The script measures three operations on numeric cells with ten columns:

- read: open a file and sum every value.
- write: create a new file row by row and save it.
- edit: open a file, change ten values and save it to a new path.

Each sample runs in a fresh process that is pinned to a fixed set of CPUs.
The wall time includes interpreter start, imports, the operation and cleanup.
The parent process reads the peak RSS of each child with wait4. Input
generation and output verification are not part of the measured time.

Usage:
    python benchmarks/modes_comparison.py --python /path/to/venv/bin/python \
        --cpus 2,3 --cells 10000 100000 1000000 --runs 3 \
        --output benchmarks/results/modes-comparison.json
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

COLUMNS = 10
EDITS = 10  # number of changed cells in the edit operation

# Operation, library, mode
CASES: list[tuple[str, str, str]] = [
    ("read", "crabxl", "standard"),
    ("read", "crabxl", "read_only"),
    ("read", "openpyxl", "standard"),
    ("read", "openpyxl", "read_only"),
    ("read", "python-calamine", "standard"),
    ("write", "crabxl", "standard"),
    ("write", "crabxl", "write_only"),
    ("write", "openpyxl", "standard"),
    ("write", "openpyxl", "write_only"),
    ("write", "xlsxwriter", "standard"),
    ("write", "xlsxwriter", "constant_memory"),
    ("edit", "crabxl", "standard"),
    ("edit", "openpyxl", "standard"),
]

PACKAGES = ["crabxl", "openpyxl", "python-calamine", "XlsxWriter"]


def case_name(case: tuple[str, str, str]) -> str:
    return "/".join(case)


# ---------------------------------------------------------------------------
# Worker side: runs in the measured child process.


def rows(cells: int):
    for r in range(cells // COLUMNS):
        start = r * COLUMNS
        yield list(range(start, start + COLUMNS))


def edit_targets(cells: int) -> list[tuple[int, int]]:
    """Return (row, column) pairs, 1-based, spread over the sheet."""
    nrows = cells // COLUMNS
    step = max(1, nrows // EDITS)
    return [(1 + i * step, 1 + i % COLUMNS) for i in range(EDITS)]


def sum_values(values) -> tuple[int, int]:
    count = 0
    total = 0
    for row in values:
        for value in row:
            count += 1
            total += int(value)
    return count, total


def worker(operation: str, library: str, mode: str, source: str, target: str, cells: int) -> dict:
    if operation == "read":
        if library == "python-calamine":
            from python_calamine import CalamineWorkbook

            book = CalamineWorkbook.from_path(source)
            count, total = sum_values(book.get_sheet_by_index(0).to_python())
            book.close()
        else:
            module = __import__(library)
            book = module.load_workbook(source, read_only=(mode == "read_only"))
            count, total = sum_values(book.active.iter_rows(values_only=True))
            book.close()
        return {"count": count, "total": total}

    if operation == "write":
        if library == "xlsxwriter":
            import xlsxwriter

            options = {"constant_memory": True} if mode == "constant_memory" else {}
            book = xlsxwriter.Workbook(target, options)
            sheet = book.add_worksheet()
            for r, values in enumerate(rows(cells)):
                sheet.write_row(r, 0, values)
            book.close()
        else:
            module = __import__(library)
            if mode == "write_only":
                book = module.Workbook(write_only=True)
                sheet = book.create_sheet()
            else:
                book = module.Workbook()
                sheet = book.active
            for values in rows(cells):
                sheet.append(values)
            book.save(target)
            book.close()
        return {}

    if operation == "edit":
        module = __import__(library)
        book = module.load_workbook(source)
        sheet = book.active
        for row, column in edit_targets(cells):
            sheet.cell(row=row, column=column).value = -1
        book.save(target)
        book.close()
        return {}

    raise ValueError(operation)


# ---------------------------------------------------------------------------
# Parent side: generation, measurement and verification.


def generate(python: str, path: Path, cells: int) -> None:
    code = (
        "import sys, openpyxl\n"
        f"sys.path.insert(0, {str(Path(__file__).parent)!r})\n"
        "from modes_comparison import rows\n"
        "book = openpyxl.Workbook(write_only=True)\n"
        "sheet = book.create_sheet()\n"
        f"for values in rows({cells}):\n"
        "    sheet.append(values)\n"
        f"book.save({str(path)!r})\n"
    )
    subprocess.run([python, "-c", code], check=True)


def expected_total(cells: int, edited: bool) -> int:
    total = cells * (cells - 1) // 2
    if edited:
        for row, column in edit_targets(cells):
            old = (row - 1) * COLUMNS + (column - 1)
            total += -1 - old
    return total


def verify(python: str, path: str, cells: int, edited: bool) -> None:
    code = (
        "import json, sys\n"
        "from python_calamine import CalamineWorkbook\n"
        f"book = CalamineWorkbook.from_path({path!r})\n"
        "count = total = 0\n"
        "for row in book.get_sheet_by_index(0).to_python():\n"
        "    for value in row:\n"
        "        if value != '':\n"
        "            count += 1\n"
        "            total += int(value)\n"
        "print(json.dumps({'count': count, 'total': total}))\n"
    )
    result = json.loads(subprocess.run([python, "-c", code], check=True, capture_output=True, text=True).stdout)
    if result != {"count": cells, "total": expected_total(cells, edited)}:
        raise RuntimeError(f"verification failed for {path}: {result}")


def measure(python: str, cpus: set[int], case, source: Path, target: Path, cells: int) -> dict:
    operation, library, mode = case
    if target.exists():
        target.unlink()
    command = [python, __file__, "--worker", operation, library, mode, str(source), str(target), str(cells)]
    start = time.perf_counter()
    child = subprocess.Popen(command, stdout=subprocess.PIPE, preexec_fn=lambda: os.sched_setaffinity(0, cpus))
    output = child.stdout.read()
    _, status, usage = os.wait4(child.pid, 0)
    wall = time.perf_counter() - start
    child.returncode = os.waitstatus_to_exitcode(status)
    if child.returncode != 0:
        raise RuntimeError(f"{case_name(case)} failed with exit code {child.returncode}")
    result = json.loads(output)
    if operation == "read" and result != {"count": cells, "total": expected_total(cells, False)}:
        raise RuntimeError(f"{case_name(case)} read wrong values: {result}")
    if operation in ("write", "edit"):
        verify(python, str(target), cells, edited=operation == "edit")
    return {
        "seconds": round(wall, 6),
        "cpu_seconds": round(usage.ru_utime + usage.ru_stime, 6),
        "peak_rss_kib": usage.ru_maxrss,
        "output_bytes": target.stat().st_size if target.exists() else None,
    }


def environment(python: str, cpus: set[int]) -> dict:
    code = (
        "import importlib.metadata as m, json, platform, sys\n"
        f"print(json.dumps({{'python': sys.version.split()[0], 'packages': {{p: m.version(p) for p in {PACKAGES!r}}}}}))\n"
    )
    info = json.loads(subprocess.run([python, "-c", code], check=True, capture_output=True, text=True).stdout)
    cpu_model = ""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    return {
        **info,
        "platform": platform.platform(),
        "cpu_model": cpu_model,
        "logical_cpus_on_host": os.cpu_count(),
        "pinned_cpus": sorted(cpus),
    }


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        operation, library, mode, source, target, cells = sys.argv[2:8]
        print(json.dumps(worker(operation, library, mode, source, target, int(cells))))
        return

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--python", required=True, help="interpreter with all packages installed")
    parser.add_argument("--cpus", default="2,3", help="CPUs for every measured process")
    parser.add_argument("--cells", type=int, nargs="+", default=[10_000, 100_000, 1_000_000])
    parser.add_argument("--runs", type=int, default=3, help="measured samples per case after one warmup")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cpus = {int(c) for c in args.cpus.split(",")}
    report = {
        "method": (
            "Fresh process per sample, pinned to the listed CPUs. One warmup, then the measured samples. "
            "The case order rotates in each round. Wall time includes interpreter start, imports and cleanup. "
            "Peak RSS comes from wait4. Generation and verification are not measured."
        ),
        "environment": environment(args.python, cpus),
        "columns": COLUMNS,
        "edited_cells": EDITS,
        "sizes": [],
    }

    with tempfile.TemporaryDirectory(prefix="crabxl-modes-") as tmp:
        directory = Path(tmp)
        for cells in args.cells:
            source = directory / f"input-{cells}.xlsx"
            generate(args.python, source, cells)
            size = {
                "cells": cells,
                "rows": cells // COLUMNS,
                "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "input_bytes": source.stat().st_size,
                "cases": {case_name(c): [] for c in CASES},
            }
            target = directory / "output.xlsx"
            for round_index in range(args.runs + 1):
                shift = round_index % len(CASES)
                for case in CASES[shift:] + CASES[:shift]:
                    sample = measure(args.python, cpus, case, source, target, cells)
                    if round_index > 0:  # round 0 is the warmup
                        size["cases"][case_name(case)].append(sample)
                print(f"{cells} cells: round {round_index} done", file=sys.stderr, flush=True)
            size["medians"] = {
                name: {
                    key: statistics.median(s[key] for s in samples)
                    for key in ("seconds", "cpu_seconds", "peak_rss_kib")
                }
                for name, samples in size["cases"].items()
            }
            report["sizes"].append(size)

    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
