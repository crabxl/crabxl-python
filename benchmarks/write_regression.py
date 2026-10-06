"""Compare installed write-only packages with serial isolated measurements."""

import argparse
import json
import statistics
import subprocess
import tempfile
from pathlib import Path

from values_calls import identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-python", type=Path, required=True)
    parser.add_argument("--after-python", type=Path, required=True)
    parser.add_argument("--measure", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=100000)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import openpyxl

    interpreters = {"before": args.before_python, "after": args.after_python}
    report = {
        "scope": "One warmup and rotating serial write_only numeric append/save "
        "in cold processes. Imports and cleanup included; builds, tests and public "
        "readback excluded. No full feature parity claim.",
        "rows": args.rows,
        "columns": 10,
        "versions": {
            name: subprocess.check_output(
                [str(executable), "-c", "import crabxl; print(crabxl.__version__)"],
                text=True,
            ).strip()
            for name, executable in interpreters.items()
        },
        "installed_packages": {
            name: identity(executable) for name, executable in interpreters.items()
        },
        "samples": {name: [] for name in interpreters},
    }
    with tempfile.TemporaryDirectory(prefix="crabxl-write-regression-") as temp:
        outputs = {name: Path(temp) / f"{name}.xlsx" for name in interpreters}
        for trial in range(args.runs + 1):
            for name in list(interpreters)[:: (-1 if trial % 2 else 1)]:
                result = subprocess.run(
                    [
                        str(args.measure),
                        str(interpreters[name]),
                        str(Path(__file__).with_name("optimized_modes.py")),
                        "--worker",
                        "crabxl",
                        "--operation",
                        "write",
                        "--rows",
                        str(args.rows),
                        "--path",
                        str(outputs[name]),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                sample = json.loads(result.stderr.split("MEASURE ")[-1])
                sample.update(json.loads(result.stdout))
                assert sample["cells"] == args.rows * 10
                assert (
                    sample["checksum"] == sample["cells"] * (sample["cells"] - 1) // 2
                )
                if trial:
                    report["samples"][name].append(sample)
        for name, output in outputs.items():
            book = openpyxl.load_workbook(output, read_only=True)
            count = 0
            for index, row in enumerate(book.active.values):
                assert row == tuple(index * 10 + column for column in range(10))
                count += 1
            book.close()
            assert count == args.rows
        report["all_written_values_verified"] = True
    report["median"] = {
        name: {
            key: statistics.median(sample[key] for sample in samples)
            for key in ["seconds", "peak_rss_kib", "spool_peak_bytes", "output_bytes"]
        }
        for name, samples in report["samples"].items()
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["median"], indent=2))


if __name__ == "__main__":
    main()
