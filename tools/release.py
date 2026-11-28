"""Prepare and validate releases of the three packages.

Each package has its own version, changelog and release tags, named
``<package>-X.Y.Z``. The plain ``X.Y.Z`` tags of earlier releases are crabxl's.

    python tools/release.py prepare crabxl-bindings 0.6.1 --core 0.4.1
    python tools/release.py prepare crabxl 0.6.1
    python tools/release.py check crabxl 0.6.1
"""

import argparse
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
BINDINGS = "crabxl-bindings"
# The package directory and, for a pure-Python package, its __init__.py.
PACKAGES = {
    BINDINGS: None,
    "crabxl": "src/crabxl/__init__.py",
    "crabxl-openpyxl": "src/crabxl_openpyxl/__init__.py",
}
CORE_CRATES = ("crabxl", "crabxl-core", "crabxl-xlsx", "crabxl-calc")


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def number(version):
    return tuple(int(part) for part in PATTERN.fullmatch(version).groups())


def folder(package):
    return ROOT / "packages" / package


def version_of(package):
    if package == BINDINGS:
        cargo = tomllib.loads((folder(package) / "Cargo.toml").read_text())
        return cargo["package"]["version"]
    return tomllib.loads((folder(package) / "pyproject.toml").read_text())["project"][
        "version"
    ]


def tag(package, version):
    return f"{package}-{version}"


def released(package):
    """Every released version of the package, by its tags."""
    versions = []
    for name in run("git", "tag", "--list").splitlines():
        if name.startswith(package + "-"):
            name = name.removeprefix(package + "-")
        elif package != "crabxl":
            continue
        if PATTERN.fullmatch(name):
            versions.append(name)
    return versions


def check_history(package, version):
    """A new version is newer than every release and builds on the newest."""
    versions = released(package)
    if version in versions:
        names = (tag(package, version), version)
        found = next(name for name in names if name in run("git", "tag", "--list"))
        if run("git", "rev-parse", found + "^{commit}") != run(
            "git", "rev-parse", "HEAD"
        ):
            raise ValueError("An existing release tag points to another commit")
        if number(version) != max(map(number, versions)):
            raise ValueError("Only the newest release can be resumed")
    elif versions and number(version) <= max(map(number, versions)):
        raise ValueError(f"Use a {package} version newer than every release")
    lower = [item for item in versions if number(item) < number(version)]
    if lower:
        newest = max(lower, key=number)
        found = tag(package, newest)
        if found not in run("git", "tag", "--list").splitlines():
            found = newest
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", found, "HEAD"], cwd=ROOT, check=True
        )


def compatible(spec, version):
    """Whether version satisfies a ``~=X.Y.Z`` requirement."""
    pinned = number(spec.removeprefix("~="))
    have = number(version)
    return have[:2] == pinned[:2] and have >= pinned


def validate(package, version, history=True):
    if package not in PACKAGES:
        raise ValueError(f"Unknown package {package}")
    if not PATTERN.fullmatch(version):
        raise ValueError("Expected X.Y.Z without leading zeros")
    if version_of(package) != version:
        raise ValueError(f"Commit {package} {version} before releasing it")
    if package == BINDINGS:
        cargo = tomllib.loads((folder(package) / "Cargo.toml").read_text())
        pins = set()
        for name in CORE_CRATES:
            core = cargo["dependencies"][name]
            if (
                set(core) & {"git", "path", "rev", "branch", "tag"}
                or not PATTERN.fullmatch(core.get("version", "").removeprefix("="))
                or not core["version"].startswith("=")
            ):
                raise ValueError(f"Require an exact crates.io version of {name}")
            pins.add(core["version"])
        if len(pins) != 1:
            raise ValueError("Pin every Rust core crate to the same version")
    else:
        source = (folder(package) / PACKAGES[package]).read_text()
        if f'__version__ = "{version}"' not in source:
            raise ValueError(f"Update the __version__ of {package}")
        project = tomllib.loads((folder(package) / "pyproject.toml").read_text())
        requirement = next(
            item
            for item in project["project"]["dependencies"]
            if item.startswith(BINDINGS + "~=")
        )
        spec = requirement.removeprefix(BINDINGS)
        if not compatible(spec, version_of(BINDINGS)):
            raise ValueError(
                f"{package} requires {requirement}, but this commit builds"
                f" {BINDINGS} {version_of(BINDINGS)}"
            )
    if history:
        check_history(package, version)
    return version


def changelog(package):
    return folder(package) / "CHANGELOG.md"


def notes(package, version):
    """The changelog section of this version, without its heading."""
    text = changelog(package).read_text(encoding="utf-8")
    match = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)",
        text,
        re.S | re.M,
    )
    if not match or not match[1].strip():
        raise ValueError(f"Add a {version} section to {changelog(package)}")
    return match[1].strip()


def link_release(text, package, version):
    """Add the release link of this version above the older links."""
    line = (
        f"[{version}]: https://github.com/crabxl/crabxl-python/releases/tag/"
        f"{tag(package, version)}\n"
    )
    if line in text:
        return text
    match = re.search(r"^\[[0-9]+\.[0-9]+\.[0-9]+\]: ", text, re.M)
    if not match:
        return text.rstrip("\n") + "\n\n" + line
    return text[: match.start()] + line + text[match.start() :]


def name_changelog_section(package, version, core):
    """Rename the Unreleased section; a bindings release names its core."""
    path = changelog(package)
    text = path.read_text(encoding="utf-8")
    if re.search(rf"^## \[{re.escape(version)}\]", text, re.M):
        return
    match = re.search(
        r"^## \[Unreleased\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.S | re.M
    )
    if not match or not match[1].strip():
        raise ValueError(f"Describe the changes under ## [Unreleased] in {path}")
    intro = f"It uses the Rust core {core}.\n\n" if core else ""
    text = (
        text[: match.start()]
        + f"## [{version}]\n\n{intro}"
        + match[1].lstrip("\n")
        + text[match.end() :]
    )
    path.write_text(link_release(text, package, version), encoding="utf-8")


def replace_one(path, pattern, replacement):
    text, count = re.subn(pattern, replacement, path.read_text(encoding="utf-8"))
    if count != 1:
        raise ValueError(f"Expected one match of {pattern} in {path}")
    path.write_text(text, encoding="utf-8")


def prepare(package, version, core=None):
    if package not in PACKAGES:
        raise ValueError(f"Unknown package {package}")
    if not PATTERN.fullmatch(version):
        raise ValueError("Expected X.Y.Z without leading zeros")
    if (core is not None) != (package == BINDINGS):
        raise ValueError("--core is required for crabxl-bindings, and only for it")
    if core and not PATTERN.fullmatch(core):
        raise ValueError("Expected a core version X.Y.Z")
    name_changelog_section(package, version, core)
    if package == BINDINGS:
        path = folder(package) / "Cargo.toml"
        replace_one(path, r'(?m)^version = "[^"]+"$', f'version = "{version}"')
        for name in CORE_CRATES:
            replace_one(
                path,
                rf'(?m)^({name} = \{{ version = ")=[^"]+(")',
                rf"\g<1>={core}\2",
            )
        # Fails when the core version is not on crates.io yet.
        subprocess.run(["cargo", "update", "--workspace"], cwd=ROOT, check=True)
    else:
        replace_one(
            folder(package) / "pyproject.toml",
            r'(?m)^version = "[^"]+"$',
            f'version = "{version}"',
        )
        replace_one(
            folder(package) / PACKAGES[package],
            r'(?m)^__version__ = "[^"]+"$',
            f'__version__ = "{version}"',
        )
    if package == "crabxl":
        replace_one(
            ROOT / ".github/ISSUE_TEMPLATE/bug_report.yml",
            r"(?m)^(\s+placeholder: )[0-9]+\.[0-9]+\.[0-9]+$",
            rf"\g<1>{version}",
        )
    validate(package, version)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=("prepare", "check"))
    parser.add_argument("package", choices=tuple(PACKAGES))
    parser.add_argument("version")
    parser.add_argument("--core", help="the Rust core version on crates.io")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.package, args.version, args.core)
    print(validate(args.package, args.version))
