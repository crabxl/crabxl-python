"""Check release artifacts and reject conflicting files already uploaded to PyPI."""

import email
import hashlib
import json
import re
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from release import validate


def main(tag):
    version = validate(tag)
    files = sorted(Path("dist").glob("*"))
    wheels = [path for path in files if path.suffix == ".whl"]
    sources = [path for path in files if path.name.endswith(".tar.gz")]
    platforms = {
        "linux-x86_64",
        "linux-aarch64",
        "windows-x86_64",
        "macos-x86_64",
        "macos-arm64",
    }
    expected = {(minor, platform) for minor in range(11, 16) for platform in platforms}
    if (
        len(wheels) != len(expected)
        or len(sources) != 1
        or len(files) != len(expected) + 1
    ):
        raise ValueError(
            "Expected 25 platform/CPython wheels and one source distribution"
        )
    observed = set()
    for path in wheels:
        match = re.fullmatch(
            r"crabxl-[^-]+-cp3(11|12|13|14|15)-cp3\1-(.+)\.whl", path.name
        )
        if not match:
            raise ValueError(f"Unexpected wheel filename: {path.name}")
        minor, tag = int(match[1]), match[2]
        if tag == "win_amd64":
            platform = "windows-x86_64"
        elif tag.startswith("manylinux_") and tag.endswith("_x86_64"):
            platform = "linux-x86_64"
        elif tag.startswith("manylinux_") and tag.endswith("_aarch64"):
            platform = "linux-aarch64"
        elif tag.startswith("macosx_") and tag.endswith("_x86_64"):
            platform = "macos-x86_64"
        elif tag.startswith("macosx_") and tag.endswith("_arm64"):
            platform = "macos-arm64"
        else:
            raise ValueError(f"Unsupported wheel platform: {tag}")
        key = minor, platform
        if key in observed:
            raise ValueError(f"Duplicate Python/platform wheel: {key}")
        observed.add(key)
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError(f"Corrupt wheel: {path}")
            metadata = email.message_from_bytes(
                archive.read(
                    next(
                        name
                        for name in archive.namelist()
                        if name.endswith(".dist-info/METADATA")
                    )
                )
            )
            if metadata["Name"] != "crabxl" or metadata["Version"] != version:
                raise ValueError(f"Unexpected package identity in {path}")
            if metadata["Requires-Python"] != ">=3.11":
                raise ValueError(f"Unexpected Python support in {path}")
    if observed != expected:
        raise ValueError(f"Missing platform/Python wheels: {expected - observed}")
    with tarfile.open(sources[0]) as archive:
        metadata = email.message_from_bytes(
            archive.extractfile(f"crabxl-{version}/PKG-INFO").read()
        )
        if metadata["Name"] != "crabxl" or metadata["Version"] != version:
            raise ValueError("Unexpected source distribution identity")
    try:
        with urllib.request.urlopen(
            f"https://pypi.org/pypi/crabxl/{version}/json", timeout=30
        ) as response:
            existing = json.load(response)["urls"]
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        existing = []
    hashes = {item["filename"]: item["digests"]["sha256"] for item in existing}
    for path in files:
        if (
            path.name in hashes
            and hashlib.sha256(path.read_bytes()).hexdigest() != hashes[path.name]
        ):
            raise ValueError(f"PyPI already contains different bytes for {path.name}")
    print(f"Verified 26 release artifacts for {version}")


if __name__ == "__main__":
    main(sys.argv[1])
