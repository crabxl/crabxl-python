"""Prepare and validate manually numbered Python alpha releases."""

import argparse
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"0\.1\.0-alpha\.([1-9][0-9]*)\Z")


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def validate(version, history=True):
    match = PATTERN.fullmatch(version)
    if not match:
        raise ValueError("Expected 0.1.0-alpha.N with a positive, unpadded integer")
    python_version = "0.1.0a" + match[1]
    cargo = tomllib.loads((ROOT / "Cargo.toml").read_text())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    if cargo["package"]["version"] != version or project["version"] != python_version:
        raise ValueError("Commit matching Cargo and Python versions before releasing")
    source = (ROOT / "python/crabxl/__init__.py").read_text()
    if f'__version__ = "{python_version}"' not in source:
        raise ValueError("Update the public Python __version__")
    if not re.fullmatch(r"[0-9a-f]{40}", cargo["dependencies"]["crabxl"]["rev"]):
        raise ValueError("Pin a full canonical Rust core commit")
    if history:
        tags = run("git", "tag", "--list").splitlines()
        previous = [int(PATTERN.fullmatch(t)[1]) for t in tags if PATTERN.fullmatch(t)]
        number = int(match[1])
        if version in tags:
            if run("git", "rev-parse", version + "^{commit}") != run(
                "git", "rev-parse", "HEAD"
            ):
                raise ValueError("An existing release tag points to another commit")
            if number != max(previous):
                raise ValueError("Only the newest release can be resumed")
        elif number != max(previous, default=0) + 1:
            raise ValueError(
                "Use the next alpha number; old checkpoints are not backfilled"
            )
        lower = [n for n in previous if n < number]
        if lower:
            subprocess.run(
                [
                    "git",
                    "merge-base",
                    "--is-ancestor",
                    f"0.1.0-alpha.{max(lower)}",
                    "HEAD",
                ],
                cwd=ROOT,
                check=True,
            )
    return python_version


def prepare(version):
    match = PATTERN.fullmatch(version)
    if not match:
        raise ValueError("Expected 0.1.0-alpha.N")
    python_version = "0.1.0a" + match[1]
    for filename, key, value in (
        ("Cargo.toml", "version", version),
        ("pyproject.toml", "version", python_version),
        ("python/crabxl/__init__.py", "__version__", python_version),
    ):
        path = ROOT / filename
        text, count = re.subn(
            rf'(?m)^{key} = "[^"]+"$', f'{key} = "{value}"', path.read_text()
        )
        if count != 1:
            raise ValueError(f"Expected one {key} in {filename}")
        path.write_text(text)
    subprocess.run(["cargo", "update", "--workspace"], cwd=ROOT, check=True)
    validate(version)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "check"))
    parser.add_argument("version")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.version)
    print(validate(args.version))
