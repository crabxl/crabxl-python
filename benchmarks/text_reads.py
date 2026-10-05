"""Read-only Unicode/escaped-text overlap with exact CRC sum checks."""

import argparse
import json
import statistics
import subprocess
import tempfile
import zlib
from pathlib import Path


def values(index):
    return [f"{index}:{column}:" + "文字 café &<> " * 8 for column in range(10)]


def worker(engine, path):
    module = __import__(engine if engine != "python-calamine" else "python_calamine")
    if engine == "python-calamine":
        book = module.CalamineWorkbook.from_path(str(path))
        rows = book.get_sheet_by_name("Sheet").iter_rows()
    else:
        options = {"max_memory_bytes": 64 * 1024**2} if engine == "crabxl" else {}
        book = module.load_workbook(path, read_only=True, **options)
        rows = book.active.iter_rows(values_only=True)
    count = checksum = 0
    for row in rows:
        count += len(row)
        checksum += sum(zlib.crc32(value.encode()) for value in row)
    book.close()
    print(json.dumps({"cells": count, "checksum": checksum}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=["crabxl", "openpyxl", "python-calamine"])
    parser.add_argument("--path", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--measure", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.path)
        return
    import openpyxl

    report = {
        "semantics": "Complete read-only Unicode/escaped inline text consumption; "
        "exact cell count and CRC32 sum. One warmup and three rotating serial "
        "cold-process samples including imports and cleanup; generation excluded. "
        "64 MiB component allowance, no SST or read temporary files.",
        "cases": [],
    }
    with tempfile.TemporaryDirectory(prefix="crabxl-text-benchmark-") as directory:
        for rows in [1000, 10000]:
            path = Path(directory) / "strings.xlsx"
            book = openpyxl.Workbook(write_only=True)
            sheet = book.create_sheet("Sheet")
            expected = 0
            for index in range(rows):
                row = values(index)
                expected += sum(zlib.crc32(value.encode()) for value in row)
                sheet.append(row)
            book.save(path)
            samples = {
                engine: [] for engine in ["crabxl", "openpyxl", "python-calamine"]
            }
            names = list(samples)
            for trial in range(4):
                for engine in names[trial % 3 :] + names[: trial % 3]:
                    result = subprocess.run(
                        [
                            str(args.measure),
                            str(args.python),
                            str(Path(__file__).resolve()),
                            "--worker",
                            engine,
                            "--path",
                            str(path),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    output = json.loads(result.stdout)
                    assert output == {"cells": rows * 10, "checksum": expected}
                    measured = json.loads(result.stderr.split("MEASURE ")[-1])
                    measured.update(output)
                    if trial:
                        samples[engine].append(measured)
                    print(rows, engine, measured["seconds"], flush=True)
            report["cases"].append(
                {
                    "rows": rows,
                    "columns": 10,
                    "file_bytes": path.stat().st_size,
                    "samples": samples,
                    "median": {
                        engine: {
                            key: statistics.median(item[key] for item in items)
                            for key in ["seconds", "peak_rss_kib"]
                        }
                        for engine, items in samples.items()
                    },
                }
            )
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
