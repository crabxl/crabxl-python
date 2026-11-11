"""Prepare and validate Python releases (X.Y.Z)."""

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
    core = cargo["dependencies"]["crabxl"]
    if (
        set(core) & {"git", "path", "rev", "branch", "tag"}
        or not PATTERN.fullmatch(core.get("version", "").removeprefix("="))
        or not core["version"].startswith("=")
    ):
        raise ValueError("Require an exact crates.io version of the Rust core")
    if history:
        check_history(version)
    return version


def name_changelog_section(version, core):
    """Rename the Unreleased section of CHANGELOG.md and name the core it uses."""
    path = ROOT / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    if re.search(rf"^## \[{re.escape(version)}\]", text, re.M):
        return
    match = re.search(
        r"^## \[Unreleased\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.S | re.M
    )
    if not match or not match[1].strip():
        raise ValueError("Describe the changes under ## [Unreleased] in CHANGELOG.md")
    body = match[1].lstrip("\n")
    path.write_text(
        text[: match.start()]
        + f"## [{version}]\n\nIt uses the Rust core {core}.\n\n"
        + body
        + text[match.end() :],
        encoding="utf-8",
    )


def prepare(version, core=None):
    if not PATTERN.fullmatch(version):
        raise ValueError("Expected X.Y.Z without leading zeros")
    core = core or version
    if not PATTERN.fullmatch(core):
        raise ValueError("Expected a core version X.Y.Z")
    name_changelog_section(version, core)
    path = ROOT / "Cargo.toml"
    text, count = re.subn(
        r'(?m)^(crabxl = \{ version = ")=[^"]+(")', rf"\g<1>={core}\2", path.read_text()
    )
    if count != 1:
        raise ValueError("Expected one crabxl dependency in Cargo.toml")
    path.write_text(text)
    path = ROOT / ".github/ISSUE_TEMPLATE/bug_report.yml"
    text, count = re.subn(
        r"(?m)^(\s+placeholder: )[0-9]+\.[0-9]+\.[0-9]+$",
        rf"\g<1>{version}",
        path.read_text(encoding="utf-8"),
        count=1,
    )
    if count != 1:
        raise ValueError("Expected a version placeholder in the bug report form")
    path.write_text(text, encoding="utf-8")
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
    # Fails when the core version is not on crates.io yet.
    subprocess.run(["cargo", "update", "--workspace"], cwd=ROOT, check=True)
    validate(version)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "check"))
    parser.add_argument("version")
    parser.add_argument(
        "--core", help="the Rust core version on crates.io (default: the same version)"
    )
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.version, args.core)
    print(validate(args.version))
