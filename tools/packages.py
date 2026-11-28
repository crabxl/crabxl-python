"""Build the native wheels and test the packages in clean environments.

``build`` compiles crabxl-bindings wheels for the given CPython versions with a
shared Cargo target. ``test`` installs, for each version, the matching
crabxl-bindings wheel or source distribution from dist/ (or from PyPI when
dist/ has neither), crabxl-openpyxl and, on 3.13 or newer, crabxl (from dist/
when it holds their wheels, otherwise from this checkout), and runs the tests.

Interpreters come from ``uv python find``; install them with
``uv python install 3.9 3.10 3.11 3.12 3.13 3.14 3.15``.
"""

import argparse
import os
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
VERSIONS = ("3.9", "3.10", "3.11", "3.12", "3.13", "3.14", "3.15")
CRABXL_MINIMUM = (3, 13)


def interpreter(version):
    path = subprocess.check_output(
        ["uv", "python", "find", "--no-project", "--system", version], text=True
    ).strip()
    reported = subprocess.check_output(
        [path, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"], text=True
    ).strip()
    if reported != version:
        raise ValueError(f"Expected CPython {version}, found {reported} at {path}")
    return path


def build(versions, target):
    maturin = shutil.which("maturin")
    if maturin is None:
        raise ValueError("Install maturin, or run: uv run --with maturin ...")
    command = [
        maturin,
        "build",
        "--release",
        "--locked",
        "--manifest-path",
        str(ROOT / "packages/crabxl-bindings/Cargo.toml"),
        "--out",
        str(DIST),
    ]
    if target:
        command.extend(["--target", target])
    command.extend(["--interpreter", *map(interpreter, versions)])
    subprocess.run(command, cwd=ROOT, check=True)


def one(pattern):
    found = sorted(DIST.glob(pattern))
    if len(found) > 1:
        raise ValueError(f"Expected at most one file matching {pattern}")
    return str(found[0]) if found else None


def requirement(package, name):
    project = tomllib.loads(
        (ROOT / "packages" / package / "pyproject.toml").read_text()
    )
    return next(
        item for item in project["project"]["dependencies"] if item.startswith(name)
    )


def test(versions):
    for version in versions:
        abi = version.replace(".", "")
        bindings = (
            one(f"crabxl_bindings-*-cp{abi}-cp{abi}-*.whl")
            or one("crabxl_bindings-*.tar.gz")
            or requirement("crabxl-openpyxl", "crabxl-bindings")
        )
        packages = [bindings]
        packages.append(
            one("crabxl_openpyxl-*-py3-none-any.whl")
            or str(ROOT / "packages/crabxl-openpyxl")
        )
        suites = ["tests/adapter"]
        if tuple(map(int, version.split("."))) >= CRABXL_MINIMUM:
            packages.append(
                one("crabxl-*-py3-none-any.whl") or str(ROOT / "packages/crabxl")
            )
            suites.append("tests/api")
        print(f"Testing CPython {version} with {', '.join(packages)}", flush=True)
        with tempfile.TemporaryDirectory(prefix="crabxl-test-") as directory:
            env = {**os.environ, "VIRTUAL_ENV": directory}
            subprocess.run(
                ["uv", "venv", "--quiet", "--python", interpreter(version), directory],
                check=True,
            )
            # The test group comes from the workspace pyproject.toml.
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--quiet",
                    "--no-sources",
                    *packages,
                    "--group",
                    "test",
                ],
                cwd=ROOT,
                env=env,
                check=True,
            )
            python = Path(directory) / (
                "Scripts/python.exe" if os.name == "nt" else "bin/python"
            )
            # Run from a copy so the checkout's sources cannot shadow the wheels.
            with tempfile.TemporaryDirectory(prefix="crabxl-tests-") as copy:
                shutil.copytree(ROOT / "tests", Path(copy) / "tests")
                subprocess.run(
                    [
                        str(python),
                        "-m",
                        "pytest",
                        *suites,
                        "-q",
                        "-p",
                        "no:cacheprovider",
                    ],
                    cwd=copy,
                    check=True,
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=("build", "test"))
    parser.add_argument(
        "--python",
        nargs="+",
        default=VERSIONS,
        choices=VERSIONS,
        help="CPython versions (default: all supported)",
    )
    parser.add_argument("--target", help="a Rust target triple for build")
    args = parser.parse_args()
    if args.command == "build":
        build(args.python, args.target)
    else:
        test(args.python)
