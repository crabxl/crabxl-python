"""Compare complete Python reads of the core's generated unique SST fixture."""

import argparse
import hashlib
import json
import statistics
import subprocess
from pathlib import Path

from values_calls import identity


def worker(engine, source, read_only):
    if engine == "python-calamine":
        from python_calamine import CalamineWorkbook

        book = CalamineWorkbook.from_path(source)
        rows = book.get_sheet_by_name("Sheet").iter_rows()
    else:
        import crabxl
        from crabxl.resources import ResourceOptions, SharedStringOptions

        book = crabxl.load_workbook(
            source,
            read_only=read_only,
            max_memory_bytes=1024**3,
            resource_options=ResourceOptions(
                shared_strings=SharedStringOptions(
                    storage="memory", memory_bytes=256 * 1024**2
                )
            ),
        )
        rows = book.active.iter_rows(values_only=True)
    count = checksum = 0
    suffix = "x" * 96
    for row in rows:
        for value in row:
            assert value == f"item-{count:08}-{suffix}"
            count += 1
            checksum += len(value)
    book.close()
    print(json.dumps({"cells": count, "checksum": checksum}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=["crabxl", "python-calamine"])
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--cells", type=int, default=1_000_000)
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--before-python", type=Path)
    parser.add_argument("--after-python", type=Path)
    parser.add_argument("--measure", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.source, args.read_only)
        return
    if not all((args.before_python, args.after_python, args.measure, args.output)):
        parser.error("Specify both installed interpreters, measure and output")
    commands = {
        "before": (args.before_python, "crabxl"),
        "after": (args.after_python, "crabxl"),
        "python_calamine": (args.after_python, "python-calamine"),
    }
    report = {
        "semantics": "Complete load and values iteration, exact per-cell string "
        "and order assertions, length checksum. One warmup then rotating serial "
        "cold-process samples include imports, conversion and cleanup. No builds, "
        "tests or generation overlap. Calamine retains a noneditable decoded "
        "range rather than providing a bounded ZIP stream.",
        "read_only": args.read_only,
        "cells": args.cells,
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "installed_packages": {
            label: identity(python)
            for label, python in (
                ("before", args.before_python),
                ("after", args.after_python),
            )
        },
        "resources": "CrabXL 1 GiB model allowance and forced RAM SST with "
        "256 MiB component budget. No read temporary files; not an RSS cap.",
        "samples": {label: [] for label in commands},
    }
    names = list(commands)
    for trial in range(args.runs + 1):
        for label in names[trial % len(names) :] + names[: trial % len(names)]:
            python, engine = commands[label]
            result = subprocess.run(
                [
                    str(args.measure),
                    str(python),
                    str(Path(__file__).resolve()),
                    "--worker",
                    engine,
                    "--source",
                    str(args.source),
                    *(["--read-only"] if args.read_only else []),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            output = json.loads(result.stdout)
            assert output == {"cells": args.cells, "checksum": args.cells * 110}
            sample = json.loads(result.stderr.split("MEASURE ")[-1])
            if trial:
                report["samples"][label].append(sample)
            print(label, trial, sample, flush=True)
    report["medians"] = {
        label: {
            key: statistics.median(sample[key] for sample in samples)
            for key in samples[0]
        }
        for label, samples in report["samples"].items()
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
