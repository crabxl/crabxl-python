"""Run the CrabXL for Python benchmark suite against other Python XLSX libraries.

Each case runs in its own Python process. The parent measures wall time and
the peak resident memory of that process. Results go to benchmarks/results/:
results.json, results.md and one SVG chart per scenario and size.

    python benchmarks/run.py
    python benchmarks/run.py --sizes small --runs 1

openpyxl is slow, so it runs on the small size only.
"""

import argparse
import ctypes
import datetime
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
SIZES = {"small": 10_000, "medium": 100_000, "large": 1_000_000}
COLUMNS = 10
SHEET = "Data"
EDIT_STEP = 100
EDIT_APPEND = 100
TIMEOUT = 900
SMALL_ONLY = ("openpyxl",)

SCENARIOS = {
    "read": [
        "crabxl (read_only)",
        "crabxl",
        "wolfxl (read_only)",
        "wolfxl",
        "oxlsx",
        "python-calamine (iter_rows)",
        "python-calamine",
        "fastexcel",
        "openpyxl (read_only)",
        "openpyxl",
    ],
    "write": [
        "crabxl (write_only)",
        "crabxl",
        "wolfxl (write_only)",
        "wolfxl",
        "oxlsx",
        "XlsxWriter (constant_memory)",
        "XlsxWriter",
        "openpyxl (write_only)",
        "openpyxl",
    ],
    "edit": ["crabxl", "wolfxl (modify)", "oxlsx", "openpyxl"],
}


def value(row, column):
    """The generated cell values. The Rust suite in crabxl uses the same data."""
    if column == 0:
        return row
    if column == 1:
        return row * 1.5
    if column == 2:
        return f"item-{row % 1000}"
    if column == 3:
        return f"row {row} unique text"
    if column == 4:
        day = row % 3650
        return datetime.date(
            2000 + day // 365, 1 + (day % 365) // 31 % 12, 1 + day % 28
        )
    if column == 5:
        return row % 2 == 0
    return row * column / 7


def rows(start, stop):
    for row in range(start, stop):
        yield [value(row, column) for column in range(COLUMNS)]


# ---------------------------------------------------------------- cases
# Each case returns the number of cells it handled.


def read_values(rows_iter):
    cells = 0
    for row in rows_iter:
        cells += len(row)
    return cells


def read(library, path):
    if library.startswith(("crabxl", "wolfxl", "openpyxl")):
        module = __import__(library.split()[0])
        book = module.load_workbook(path, read_only="read_only" in library)
        cells = read_values(book[SHEET].iter_rows(values_only=True))
        book.close()
        return cells
    if library == "oxlsx":
        import oxlsx

        return read_values(
            oxlsx.load_workbook(str(path))[SHEET].iter_rows(values_only=True)
        )
    if library.startswith("python-calamine"):
        from python_calamine import CalamineWorkbook

        sheet = CalamineWorkbook.from_path(str(path)).get_sheet_by_name(SHEET)
        return read_values(
            sheet.iter_rows() if "iter_rows" in library else sheet.to_python()
        )
    if library == "fastexcel":
        import fastexcel

        sheet = fastexcel.read_excel(str(path)).load_sheet(SHEET, header_row=None)
        table = sheet.to_arrow()
        return table.num_rows * table.num_columns
    raise ValueError(library)


def write(library, count, path):
    if library.startswith(("crabxl", "wolfxl", "openpyxl")):
        module = __import__(library.split()[0])
        book = module.Workbook(write_only="write_only" in library)
        if "write_only" in library:
            sheet = book.create_sheet(SHEET)
        else:
            sheet = book.active
            sheet.title = SHEET
        for row in rows(0, count):
            sheet.append(row)
        book.save(path)
    elif library == "oxlsx":
        import oxlsx

        book = oxlsx.Workbook()
        sheet = book.active  # oxlsx cannot rename or add sheets.
        for row in rows(0, count):
            sheet.append(row)
        book.save(str(path))
    elif library.startswith("XlsxWriter"):
        import xlsxwriter

        options = {
            "constant_memory": "constant_memory" in library,
            "default_date_format": "yyyy-mm-dd",
        }
        with xlsxwriter.Workbook(str(path), options) as book:
            sheet = book.add_worksheet(SHEET)
            for index, row in enumerate(rows(0, count)):
                sheet.write_row(index, 0, row)
    else:
        raise ValueError(library)
    return count * COLUMNS


def edit(library, source, path, count):
    """Change column B in one row of every 100, append 100 rows and save."""
    name = library.split()[0]
    if name in ("crabxl", "openpyxl", "wolfxl"):
        module = __import__(name)
        options = {"modify": True} if name == "wolfxl" else {}
        book = module.load_workbook(source, **options)
    elif name == "oxlsx":
        import oxlsx

        book = oxlsx.load_workbook(str(source))
    else:
        raise ValueError(library)
    sheet = book[SHEET]
    changed = 0
    for row in range(1, count + 1, EDIT_STEP):
        sheet[f"B{row}"] = "changed"
        changed += 1
    for row in rows(count, count + EDIT_APPEND):
        sheet.append(row)
        changed += COLUMNS
    book.save(str(path) if name == "oxlsx" else path)
    return changed


def fixture(count, path):
    import xlsxwriter

    with xlsxwriter.Workbook(str(path), {"default_date_format": "yyyy-mm-dd"}) as book:
        sheet = book.add_worksheet(SHEET)
        for index, row in enumerate(rows(0, count)):
            sheet.write_row(index, 0, row)


def worker(args):
    scenario, library, *rest = args
    if scenario == "read":
        cells = read(library, Path(rest[0]))
    elif scenario == "write":
        cells = write(library, int(rest[0]), Path(rest[1]))
    else:
        cells = edit(library, Path(rest[0]), Path(rest[1]), int(rest[2]))
    print(cells)


# ---------------------------------------------------------------- measurement


def slow(previous, scenario, library):
    """Whether the case at the previous size predicts a timeout (sizes grow 10x)."""
    record = previous.get((scenario, library))
    return record is not None and (
        "timeout" in record or record.get("seconds", 0) * 10 > TIMEOUT
    )


def check(record):
    """Mark a case that did not handle every expected cell as incomplete."""
    rows = record["rows"]
    expected = {"read": rows * 10, "write": rows * 10, "edit": -(-rows // 100) + 1000}
    want = expected[record["scenario"]]
    if "cells" in record and record["cells"] != want:
        record["error"] = f"incomplete: handled {record['cells']:,} of {want:,} cells"
        for key in ("seconds", "peak_mib"):
            record.pop(key, None)
    return record


def peak_memory(process):
    """Peak resident memory of a finished child, in bytes."""
    if os.name == "nt":

        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t)
                for name in ("peak", "rss", "a", "b", "c", "d", "e", "f")
            ]

        counters = Counters(cb=ctypes.sizeof(Counters))
        # The Popen handle stays open after exit, so the counters are still readable.
        if not ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.c_void_p(int(process._handle)), ctypes.byref(counters), counters.cb
        ):
            raise ctypes.WinError()
        return counters.peak
    return process.peak


def interpreter():
    """The command and environment that start this Python in one process.

    A virtual environment's python.exe on Windows is a launcher that starts the
    real interpreter as a child, so its peak memory would be the launcher's.
    """
    base = getattr(sys, "_base_executable", sys.executable)
    if os.name != "nt" or base == sys.executable:
        return [sys.executable], None
    import sysconfig

    paths = [sysconfig.get_paths()["purelib"], sysconfig.get_paths()["platlib"]]
    return [base], {**os.environ, "PYTHONPATH": os.pathsep.join(dict.fromkeys(paths))}


def run(command, env=None):
    """Run one case. Return (seconds, peak bytes, stdout) or None on timeout."""
    start = time.perf_counter()
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    if os.name == "nt":
        try:
            out, err = process.communicate(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return None
        seconds = time.perf_counter() - start
        code = process.returncode
    else:
        # shortcut: no timeout on POSIX; wait4 is the only way to read child peak RSS.
        out, err = process.stdout.read(), process.stderr.read()
        _, status, usage = os.wait4(process.pid, 0)
        seconds = time.perf_counter() - start
        code = os.waitstatus_to_exitcode(status)
        scale = 1 if sys.platform == "darwin" else 1024
        process.peak = usage.ru_maxrss * scale
    if code != 0:
        raise RuntimeError(f"{command} failed: {err.decode(errors='replace')}")
    return seconds, peak_memory(process), out.decode().strip()


def versions():
    from importlib.metadata import version

    names = [
        "crabxl",
        "wolfxl",
        "oxlsx",
        "python-calamine",
        "fastexcel",
        "XlsxWriter",
        "openpyxl",
    ]
    return {name: version(name) for name in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", nargs="+", choices=SIZES, default=list(SIZES))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="rewrite results.md from results.json",
    )
    parser.add_argument("--libraries", nargs="+", help="run only these libraries")
    args = parser.parse_args()
    if args.report_only:
        report = json.loads((RESULTS / "results.json").read_text())
        report["results"] = [check(record) for record in report["results"]]
        (RESULTS / "results.json").write_text(json.dumps(report, indent=1) + "\n")
        write_report(report, "Python")
        return

    python, env = interpreter()
    previous = {}
    work = ROOT / "data"
    work.mkdir(exist_ok=True)
    results = []
    for size in args.sizes:
        count = SIZES[size]
        source = work / f"{size}.xlsx"
        if not source.exists():
            fixture(count, source)
        for scenario, libraries in SCENARIOS.items():
            for library in libraries:
                if size != "small" and library.startswith(SMALL_ONLY):
                    continue
                if args.libraries and library not in args.libraries:
                    continue
                output = work / "out.xlsx"
                extra = {
                    "read": [source],
                    "write": [count, output],
                    "edit": [source, output, count],
                }[scenario]
                command = [
                    *python,
                    __file__,
                    "worker",
                    scenario,
                    library,
                    *map(str, extra),
                ]
                measured = []
                record = {
                    "size": size,
                    "rows": count,
                    "scenario": scenario,
                    "library": library,
                }
                if slow(previous, scenario, library):
                    record["timeout"] = TIMEOUT
                    record["estimated"] = True
                # One extra first run warms the file cache; it is not counted.
                for attempt in range(0 if "timeout" in record else args.runs + 1):
                    try:
                        result = run(command, env)
                    except RuntimeError as error:
                        record["error"] = str(error).strip().splitlines()[-1]
                        break
                    if result is None:
                        record["timeout"] = TIMEOUT
                        break
                    if attempt:
                        measured.append(result)
                if len(measured) == args.runs:
                    record["seconds"] = statistics.median(m[0] for m in measured)
                    record["peak_mib"] = (
                        statistics.median(m[1] for m in measured) / 2**20
                    )
                    record["cells"] = int(measured[0][2])
                results.append(check(record))
                previous[(scenario, library)] = record
                print(json.dumps(record), flush=True)
                output.unlink(missing_ok=True)

    report = {
        "machine": f"{platform.system()} {platform.release()}, {platform.processor() or platform.machine()}",
        "cpus": os.cpu_count(),
        "python": platform.python_version(),
        "versions": versions(),
        "runs": args.runs,
        "results": results,
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "results.json").write_text(json.dumps(report, indent=1) + "\n")
    write_report(report, "Python")


# ---------------------------------------------------------------- report
# Copied from benchmarks/run.py in crabxl, so that both suites look the same.


def write_report(report, title):
    lines = [
        f"# {title} benchmark results",
        "",
        f"Machine: {report['machine']}, {report['cpus']} logical CPUs. "
        f"Median of {report['runs']} runs. Time is the wall time of the whole "
        "process. Memory is the peak resident memory of the process.",
        "",
    ]
    if "versions" in report:
        lines += [
            f"Python {report['python']}. "
            + ", ".join(f"{name} {v}" for name, v in report["versions"].items())
            + ".",
            "",
        ]
    groups = {}
    for record in report["results"]:
        groups.setdefault((record["scenario"], record["size"]), []).append(record)
    for (scenario, size), records in groups.items():
        count = records[0]["rows"]
        lines += [
            f"## {scenario.capitalize()}, {size} ({count:,} rows × 10 columns)",
            "",
            f"![{scenario} {size}]({scenario}-{size}.svg)",
            "",
            "| Library | Time (s) | Peak memory (MiB) |",
            "|---|---:|---:|",
        ]
        for record in records:
            if "timeout" in record:
                note = (
                    " (estimated from the smaller size)"
                    if record.get("estimated")
                    else ""
                )
                lines.append(
                    f"| {record['library']} | > {record['timeout']}{note} | – |"
                )
            elif "error" in record:
                lines.append(f"| {record['library']} | failed: {record['error']} | – |")
            else:
                lines.append(
                    f"| {record['library']} | {record['seconds']:.3f} | {record['peak_mib']:.1f} |"
                )
        lines.append("")
        (RESULTS / f"{scenario}-{size}.svg").write_text(chart(records))
    (RESULTS / "results.md").write_text("\n".join(lines))


def chart(records):
    """Two horizontal bar panels (time and memory) for one scenario and size."""
    done = [r for r in records if "seconds" in r]
    label_width, panel, bar, gap = 230, 300, 22, 8
    height = 40 + len(records) * (bar + gap)
    width = label_width + 2 * panel + 60
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="system-ui, sans-serif" font-size="13">',
        "<style>text{fill:#334}.t{font-weight:600}.crabxl{fill:#e8590c}.other{fill:#8a94a6}"
        "@media (prefers-color-scheme: dark){text{fill:#dde}.other{fill:#6b7385}}</style>",
    ]
    for index, (key, name, unit) in enumerate(
        [("seconds", "Time", "s"), ("peak_mib", "Peak memory", "MiB")]
    ):
        x0 = label_width + index * (panel + 30)
        top = max((r[key] for r in done), default=1) or 1
        parts.append(
            f'<text class="t" x="{x0}" y="20">{name} ({unit}, lower is better)</text>'
        )
        for row, record in enumerate(records):
            y = 34 + row * (bar + gap)
            if index == 0:
                parts.append(
                    f'<text x="{label_width - 10}" y="{y + 16}" text-anchor="end">{record["library"]}</text>'
                )
            if "seconds" not in record:
                parts.append(
                    f'<text x="{x0}" y="{y + 16}">{"timeout" if "timeout" in record else "failed"}</text>'
                )
                continue
            length = max(2, record[key] / top * (panel - 70))
            css = "crabxl" if record["library"].startswith("crabxl") else "other"
            value = f"{record[key]:.2f}" if key == "seconds" else f"{record[key]:.0f}"
            parts.append(
                f'<rect class="{css}" x="{x0}" y="{y}" width="{length:.1f}" height="{bar}" rx="3"/>'
            )
            parts.append(f'<text x="{x0 + length + 6:.1f}" y="{y + 16}">{value}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    if sys.argv[1:2] == ["worker"]:
        worker(sys.argv[2:])
    else:
        main()
