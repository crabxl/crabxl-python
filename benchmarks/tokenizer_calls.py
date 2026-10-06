"""Serial cold-process measurements of complete public tokenization calls."""

import argparse
import hashlib
import importlib
import json
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

FORMULAS = (
    '=IF(A1>=2,"a""b",#N/A)',
    "=-1.2E-3%+TRUE",
    "={1,2;3,4}",
    "='it''s a sheet'!A1+T[[#Headers],[B]]",
    "=SUM((A1:B2 C1:D3))",
    "=A1\nB1",
    "=1:2+A:B+$1:$2+$A:$B",
    "=LOG10(A1)+SUM(A1:B2:C3)",
)


def worker(engine, repetitions):
    module = importlib.import_module(engine + ".formula.tokenizer")
    count = checksum = 0
    start = time.perf_counter()
    for _ in range(repetitions):
        for formula in FORMULAS:
            parsed = module.Tokenizer(formula)
            rendered = parsed.render()
            assert rendered == "=" + "".join(t.value for t in parsed.items)
            for token in parsed.items:
                count += 1
                checksum += sum(
                    ord(c) for c in token.value + token.type + token.subtype
                )
    elapsed = time.perf_counter() - start
    native = None
    if engine == "crabxl":
        native = Path(importlib.import_module("crabxl._native").__file__)
    return {
        "engine": engine,
        "seconds": elapsed,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "calls": repetitions * len(FORMULAS),
        "tokens": count,
        "checksum": checksum,
        "native_sha256": hashlib.sha256(native.read_bytes()).hexdigest()
        if native
        else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("openpyxl", "crabxl"))
    parser.add_argument("--repetitions", type=int, default=2500)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repetitions < 1 or args.samples < 1:
        parser.error("repetitions and samples must be positive")
    if args.worker:
        print(json.dumps(worker(args.worker, args.repetitions)))
        return

    def invoke(engine):
        result = subprocess.run(
            [
                sys.executable,
                __file__,
                "--worker",
                engine,
                "--repetitions",
                str(args.repetitions),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    for engine in ("openpyxl", "crabxl"):
        invoke(engine)
    samples = []
    for index in range(args.samples):
        for engine in (
            ("openpyxl", "crabxl") if index % 2 == 0 else ("crabxl", "openpyxl")
        ):
            sample = invoke(engine)
            samples.append(sample)
            print(json.dumps(sample), flush=True)
    assert len({(s["calls"], s["tokens"], s["checksum"]) for s in samples}) == 1
    report = {
        "python": sys.version,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "formulas": FORMULAS,
        "samples": samples,
        "summary": {
            engine: {
                "median_seconds": statistics.median(
                    s["seconds"] for s in samples if s["engine"] == engine
                ),
                "median_peak_rss_kib": statistics.median(
                    s["peak_rss_kib"] for s in samples if s["engine"] == engine
                ),
            }
            for engine in ("openpyxl", "crabxl")
        },
        "boundary": "Warm imports precede timing; tokenization, Python objects, complete iteration, rendering and token spelling/category checksum are timed. Separate serial processes; no worksheet processing or temp files.",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
