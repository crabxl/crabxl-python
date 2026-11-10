"""Prepare and validate manually numbered Python releases (X.Y.Z)."""

import argparse
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def number(version):
    return tuple(int(part) for part in PATTERN.fullmatch(version).groups())


def check_history(version):
    """A new version is newer than every release tag and builds on the newest."""
    tags = [
        tag
        for tag in run("git", "tag", "--list").splitlines()
        if PATTERN.fullmatch(tag)
    ]
    if version in tags:
        if run("git", "rev-parse", version + "^{commit}") != run(
            "git", "rev-parse", "HEAD"
        ):
            raise ValueError("An existing release tag points to another commit")
        if number(version) != max(map(number, tags)):
            raise ValueError("Only the newest release can be resumed")
    elif tags and number(version) <= max(map(number, tags)):
        raise ValueError("Use a version newer than every release tag")
    lower = [tag for tag in tags if number(tag) < number(version)]
    if lower:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", max(lower, key=number), "HEAD"],
            cwd=ROOT,
            check=True,
        )


def validate(version, history=True):
    if not PATTERN.fullmatch(version):
        raise ValueError("Expected X.Y.Z without leading zeros")
    cargo = tomllib.loads((ROOT / "Cargo.toml").read_text())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    if cargo["package"]["version"] != version or project["version"] != version:
        raise ValueError("Commit matching Cargo and Python versions before releasing")
    source = (ROOT / "python/crabxl/__init__.py").read_text()
    if f'__version__ = "{version}"' not in source:
        raise ValueError("Update the public Python __version__")
    if not re.fullmatch(r"[0-9a-f]{40}", cargo["dependencies"]["crabxl"]["rev"]):
        raise ValueError("Pin a full canonical Rust core commit")
    if history:
        check_history(version)
    return version


def prepare(version):
    if not PATTERN.fullmatch(version):
        raise ValueError("Expected X.Y.Z without leading zeros")
    for filename, key in (
        ("Cargo.toml", "version"),
        ("pyproject.toml", "version"),
        ("python/crabxl/__init__.py", "__version__"),
    ):
        path = ROOT / filename
        text, count = re.subn(
            rf'(?m)^{key} = "[^"]+"$', f'{key} = "{version}"', path.read_text()
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
