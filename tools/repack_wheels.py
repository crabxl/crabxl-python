"""Release Python-only changes without rebuilding the native module.

`reusable` prints the newest release tag when nothing since it changes the
native build. `repack` turns that release's wheels into wheels of the current
version: the compiled module and its SBOM stay, the Python files come from this
commit and the metadata from this commit's source distribution.
"""

import argparse
import base64
import csv
import hashlib
import io
import re
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

from release import PATTERN, ROOT, number, run

# Paths whose changes never reach the compiled module.
PYTHON_ONLY = (
    "python/",
    "tests/",
    "docs/",
    "internal/",
    "tools/",
    ".github/",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
)


def without_version(path, text):
    """The build inputs of a manifest, ignoring the release version."""
    data = tomllib.loads(text)
    if path == "Cargo.toml":
        data["package"].pop("version")
    elif path == "Cargo.lock":
        for package in data["package"]:
            if package["name"] == "crabxl-python":
                package.pop("version")
    else:
        # Project metadata comes from the new source distribution.
        data.pop("project")
    return data


def reusable(version):
    tags = [
        tag
        for tag in run("git", "tag", "--list").splitlines()
        if PATTERN.fullmatch(tag) and number(tag) < number(version)
    ]
    if not tags:
        return None
    tag = max(tags, key=number)
    for path in run("git", "diff", "--name-only", tag, "HEAD").splitlines():
        if path.startswith(PYTHON_ONLY):
            continue
        if path not in ("Cargo.toml", "Cargo.lock", "pyproject.toml"):
            return None
        old = run("git", "show", f"{tag}:{path}")
        if without_version(path, old) != without_version(
            path, (ROOT / path).read_text()
        ):
            return None
    return tag


def record_line(name, data):
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return [name, f"sha256={digest.decode()}", str(len(data))]


def repack(wheel, version, metadata, sources, out):
    old = re.fullmatch(r"crabxl-([^-]+)-(.+)\.whl", wheel.name)
    info = f"crabxl-{version}.dist-info/"
    files = {}
    with zipfile.ZipFile(wheel) as archive:
        old_info = f"crabxl-{old[1]}.dist-info/"
        for name in archive.namelist():
            if name.startswith("crabxl/_native."):
                files[name] = archive.read(name)
            elif name.startswith(old_info) and not name.endswith(
                ("/METADATA", "/RECORD")
            ):
                files[info + name.removeprefix(old_info)] = archive.read(name)
    if sum(name.startswith("crabxl/_native.") for name in files) != 1:
        raise ValueError(f"Expected one native module in {wheel.name}")
    files.update(sources)
    files[info + "METADATA"] = metadata
    target = out / f"crabxl-{version}-{old[2]}.whl"
    rows = [record_line(name, data) for name, data in files.items()]
    rows.append([info + "RECORD", "", ""])
    text = io.StringIO()
    csv.writer(text, lineterminator="\n").writerows(rows)
    files[info + "RECORD"] = text.getvalue().encode()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("reusable").add_argument("version")
    command = sub.add_parser("repack")
    command.add_argument("old", type=Path, help="folder with the old wheels")
    command.add_argument("dist", type=Path, help="folder with the new sdist")
    args = parser.parse_args()
    if args.command == "reusable":
        print(reusable(args.version) or "")
        return
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    (sdist,) = args.dist.glob(f"crabxl-{version}.tar.gz")
    prefix = f"crabxl-{version}/"
    with tarfile.open(sdist) as archive:
        metadata = archive.extractfile(prefix + "PKG-INFO").read()
        sources = {
            member.name.removeprefix(prefix + "python/"): archive.extractfile(
                member
            ).read()
            for member in archive.getmembers()
            if member.isfile() and member.name.startswith(prefix + "python/crabxl/")
        }
    wheels = sorted(args.old.glob("*.whl"))
    if not wheels:
        sys.exit("No wheels to repack")
    for wheel in wheels:
        print(repack(wheel, version, metadata, sources, args.dist).name)


if __name__ == "__main__":
    main()
