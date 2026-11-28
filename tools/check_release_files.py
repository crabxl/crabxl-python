"""Check the release files of packages, and reject files that differ from ones
already on PyPI.

    python tools/check_release_files.py dist crabxl crabxl-openpyxl
"""

import email
import hashlib
import json
import re
import sys
import tarfile
import tomllib
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from release import BINDINGS, ROOT, validate, version_of


def platform(tag):
    if tag == "win_amd64":
        return "windows-x86_64"
    for prefix, system in (("manylinux_", "linux"), ("macosx_", "macos")):
        if tag.startswith(prefix):
            for suffix in ("x86_64", "aarch64", "arm64"):
                if tag.endswith("_" + suffix):
                    return f"{system}-{suffix}"
    raise ValueError(f"Unsupported wheel platform: {tag}")


def requires_python(package):
    path = ROOT / "packages" / package / "pyproject.toml"
    return tomllib.loads(path.read_text())["project"]["requires-python"]


def metadata(path):
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError(f"Corrupt wheel: {path}")
            name = next(
                item
                for item in archive.namelist()
                if item.endswith(".dist-info/METADATA")
            )
            return email.message_from_bytes(archive.read(name))
    with tarfile.open(path) as archive:
        name = next(item for item in archive.getnames() if item.endswith("/PKG-INFO"))
        return email.message_from_bytes(archive.extractfile(name).read())


def check(files, package):
    version = validate(package, version_of(package))
    stem = package.replace("-", "_")
    mine = [path for path in files if path.name.startswith(f"{stem}-{version}")]
    wheels = [path for path in mine if path.suffix == ".whl"]
    sources = [path for path in mine if path.name.endswith(".tar.gz")]
    if len(sources) != 1 or len(mine) != len(wheels) + 1:
        raise ValueError(f"Expected one source distribution of {package} {version}")
    if package == BINDINGS:
        minors = range(9, 16)
        expected = {
            (minor, system)
            for minor in minors
            for system in (
                "linux-x86_64",
                "linux-aarch64",
                "windows-x86_64",
                "macos-x86_64",
                "macos-arm64",
            )
        }
        observed = set()
        for path in wheels:
            match = re.fullmatch(
                rf"{stem}-{version}-cp3(\d+)-cp3\1-(.+)\.whl", path.name
            )
            if not match:
                raise ValueError(f"Unexpected wheel filename: {path.name}")
            key = int(match[1]), platform(match[2])
            if key in observed:
                raise ValueError(f"Duplicate Python/platform wheel: {key}")
            observed.add(key)
        if observed != expected:
            raise ValueError(f"Missing wheels: {sorted(expected - observed)}")
    elif [path.name for path in wheels] != [f"{stem}-{version}-py3-none-any.whl"]:
        raise ValueError(f"Expected one pure-Python wheel of {package} {version}")
    for path in mine:
        found = metadata(path)
        if found["Name"] != package or found["Version"] != version:
            raise ValueError(f"Unexpected package identity in {path}")
        if found["Requires-Python"] != requires_python(package):
            raise ValueError(f"Unexpected Python support in {path}")
    try:
        with urllib.request.urlopen(
            f"https://pypi.org/pypi/{package}/{version}/json", timeout=30
        ) as response:
            existing = json.load(response)["urls"]
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        existing = []
    hashes = {item["filename"]: item["digests"]["sha256"] for item in existing}
    for path in mine:
        if (
            path.name in hashes
            and hashlib.sha256(path.read_bytes()).hexdigest() != hashes[path.name]
        ):
            raise ValueError(f"PyPI already contains different bytes for {path.name}")
    print(f"Verified {len(mine)} release files of {package} {version}")
    return mine


def main(directory, packages):
    files = sorted(Path(directory).glob("*"))
    checked = [path for package in packages for path in check(files, package)]
    extra = set(files) - set(checked)
    if extra:
        raise ValueError(f"Unexpected files: {sorted(path.name for path in extra)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
