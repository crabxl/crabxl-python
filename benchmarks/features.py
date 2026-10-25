"""Compare CrabXL and openpyxl on workbooks with many worksheet features.

The workbook has numeric data, one table over the data, conditional formats,
data validations, comments, sheet protection and a print area. Three
operations run with the same public openpyxl calls in both libraries:

- write: build the workbook and save it.
- read: load the file and read every table, rule, validation and comment.
- edit: load the file, change a table style and one comment, and save.

Each sample runs in a fresh process pinned to fixed CPUs. Wall time includes
interpreter start, imports, the operation and cleanup. The parent reads peak
RSS with wait4.

Usage:
    python benchmarks/features.py --python /path/to/venv/bin/python \
        --cpus 6,7 --runs 3 --output benchmarks/results/features.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROWS = 20_000
COLUMNS = 5
RULES = 500
VALIDATIONS = 500
COMMENTS = 5_000

BUILD = f"""
from {{lib}} import Workbook
from {{lib}}.comments import Comment
from {{lib}}.formatting.rule import CellIsRule
from {{lib}}.styles import PatternFill
from {{lib}}.worksheet.datavalidation import DataValidation
from {{lib}}.worksheet.table import Table, TableStyleInfo

wb = Workbook()
ws = wb.active
ws.title = "Data"
ws.append([f"c{{{{i}}}}" for i in range({COLUMNS})])
for row in range({ROWS}):
    ws.append([row * {COLUMNS} + column for column in range({COLUMNS})])
table = Table(displayName="Data", ref="A1:E{ROWS + 1}")
table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
ws.add_table(table)
fill = PatternFill(fill_type="solid", bgColor="FFC7CE")
for index in range({RULES}):
    row = index * 40 + 2
    ws.conditional_formatting.add(
        f"B{{{{row}}}}:B{{{{row + 39}}}}",
        CellIsRule(operator="greaterThan", formula=[str(index)], fill=fill),
    )
for index in range({VALIDATIONS}):
    validation = DataValidation(type="whole", operator="between", formula1="0", formula2=str(index + 1))
    validation.add(f"C{{{{index * 40 + 2}}}}:C{{{{index * 40 + 41}}}}")
    ws.add_data_validation(validation)
for index in range({COMMENTS}):
    ws.cell(row=index * 4 + 2, column=4).comment = Comment(f"note {{{{index}}}}", "bench")
ws.protection.sheet = True
ws.print_area = "A1:E{ROWS + 1}"
"""

CODE = {
    "write": BUILD + "\nwb.save(OUTPUT)\n",
    "read": """
from {lib} import load_workbook
wb = load_workbook(INPUT)
ws = wb["Data"]
count = len(ws.tables)
count += sum(len(block.rules) for block in ws.conditional_formatting)
count += len(ws.data_validations.dataValidation)
count += sum(1 for row in ws.iter_rows() for cell in row if cell.comment is not None)
print(count)
""",
    "edit": """
from {lib} import load_workbook
wb = load_workbook(INPUT)
ws = wb["Data"]
ws.tables["Data"].tableStyleInfo.name = "TableStyleLight1"
ws["D2"].comment.text = "edited"
wb.save(OUTPUT)
""",
}
EXPECTED = 1 + RULES + VALIDATIONS + COMMENTS


def measure(python: str, cpus: str, lib: str, operation: str, folder: Path) -> dict:
    code = CODE[operation].replace("{lib}", lib)
    code = code.replace("{{", "{").replace("}}", "}")
    script = folder / f"{lib}-{operation}.py"
    script.write_text(
        f"INPUT = {str(folder / 'input.xlsx')!r}\nOUTPUT = {str(folder / f'{lib}-out.xlsx')!r}\n"
        + code
    )
    start = time.perf_counter()
    process = subprocess.Popen(
        ["taskset", "-c", cpus, python, str(script)], stdout=subprocess.PIPE, text=True
    )
    _, status, usage = os.wait4(process.pid, 0)
    elapsed = time.perf_counter() - start
    output = process.stdout.read() if process.stdout else ""
    if status != 0:
        raise RuntimeError(f"{lib} {operation} failed")
    if operation == "read" and int(output.strip()) != EXPECTED:
        raise RuntimeError(f"{lib} read {output.strip()} features, expected {EXPECTED}")
    return {"seconds": elapsed, "peak_rss_mib": usage.ru_maxrss / 1024}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True)
    parser.add_argument("--cpus", default="6,7")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    results: dict[str, list[dict]] = {}
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        build = (
            CODE["write"]
            .replace("{lib}", "openpyxl")
            .replace("{{", "{")
            .replace("}}", "}")
        )
        (folder / "make.py").write_text(
            f"OUTPUT = {str(folder / 'input.xlsx')!r}\n" + build
        )
        subprocess.run([args.python, str(folder / "make.py")], check=True)
        cases = [
            (lib, op)
            for op in ("write", "read", "edit")
            for lib in ("crabxl", "openpyxl")
        ]
        for round_index in range(args.runs + 1):
            order = (
                cases[round_index % len(cases) :] + cases[: round_index % len(cases)]
            )
            for lib, operation in order:
                sample = measure(args.python, args.cpus, lib, operation, folder)
                if round_index:
                    results.setdefault(f"{operation}/{lib}", []).append(sample)
    summary = {
        name: {
            "seconds": statistics.median(s["seconds"] for s in samples),
            "peak_rss_mib": statistics.median(s["peak_rss_mib"] for s in samples),
        }
        for name, samples in results.items()
    }
    report = {
        "workload": {
            "rows": ROWS,
            "columns": COLUMNS,
            "conditional_rules": RULES,
            "validations": VALIDATIONS,
            "comments": COMMENTS,
        },
        "python": sys.version,
        "platform": platform.platform(),
        "summary": summary,
        "samples": results,
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    for name, value in sorted(summary.items()):
        print(f"{name:20} {value['seconds']:.3f} s {value['peak_rss_mib']:.1f} MiB")


if __name__ == "__main__":
    main()
