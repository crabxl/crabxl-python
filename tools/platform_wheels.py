"""Build and test five CPython wheels on one runner with a shared Cargo target."""

import argparse
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from release import ROOT

ABIS = ("311", "312", "313", "314", "315")


def interpreters():
    paths = json.loads(os.environ["PYTHON_PATHS"])
    selected = []
    for abi in ABIS:
        executable = paths[f"python-{abi}"]
        if not Path(executable).is_file():
            raise ValueError(f"Missing CPython {abi} executable: {executable}")
        reported = subprocess.check_output(
            [
                executable,
                "-c",
                "import sys; print(str(sys.version_info.major) + str(sys.version_info.minor))",
            ],
            text=True,
        ).strip()
        if reported != abi:
            raise ValueError(f"Expected CPython {abi}, found {reported}")
        selected.append((abi, executable))
    return selected


def build(target):
    selected = interpreters()
    command = [
        sys.executable,
        "-m",
        "maturin",
        "build",
        "--release",
        "--locked",
        "--out",
        "dist",
    ]
    if target:
        command.extend(["--target", target])
    command.extend(["--interpreter", *(path for _, path in selected)])
    # Maturin switches ABI fingerprints and reuses ordinary Rust dependencies.
    subprocess.run(command, cwd=ROOT, check=True)


def test():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    prefix = f"{project['name']}-{project['version']}"
    for abi, executable in interpreters():
        print(f"Testing installed CPython {abi} wheel", flush=True)
        subprocess.run(
            [
                executable,
                "tools/test_distribution.py",
                f"{prefix}-cp{abi}-cp{abi}-*.whl",
            ],
            cwd=ROOT,
            check=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "test"])
    parser.add_argument("--target")
    args = parser.parse_args()
    if args.command == "build":
        build(args.target)
    else:
        test()
