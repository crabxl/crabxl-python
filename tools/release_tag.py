"""Decide which packages this push releases, and tell GitHub.

A push to main releases each package whose committed version has no release
tag yet. The release workflow creates the tags after publishing. A manual run
resumes the release of every package whose newest version is at this commit.
"""

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from release import BINDINGS, PACKAGES, ROOT, notes, run, tag, validate, version_of


def output(**values):
    if path := os.environ.get("GITHUB_OUTPUT"):
        with open(path, "a", encoding="utf-8") as stream:
            for key, value in values.items():
                delimiter = "value_" + uuid.uuid4().hex
                stream.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")


def pending():
    """The packages to release, with their versions."""
    tags = run("git", "tag", "--list").splitlines()
    head = run("git", "rev-parse", "HEAD")
    resume = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    found = {}
    for package in PACKAGES:
        version = version_of(package)
        name = tag(package, version)
        if name not in tags:
            found[package] = version
        elif resume and run("git", "rev-parse", name + "^{commit}") == head:
            found[package] = version
    return found


def main():
    releases = pending()
    if not releases:
        output(releases="[]", bindings="", pure="[]")
        print("Every package version is already released")
        return
    branch = os.environ.get("DEFAULT_BRANCH", "main")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", "HEAD", f"origin/{branch}"], cwd=ROOT
    ).returncode:
        raise ValueError(f"Release a commit that is on {branch}")
    items = []
    for package, version in releases.items():
        validate(package, version)
        items.append(
            {
                "package": package,
                "version": version,
                "tag": tag(package, version),
                "notes": notes(package, version),
            }
        )
        print(f"Releasing {package} {version}")
    output(
        releases=json.dumps(items),
        bindings="true" if BINDINGS in releases else "",
        pure=json.dumps([package for package in releases if package != BINDINGS]),
    )


def github(directory):
    """Create the tag and GitHub release of each published package, or add
    the files to a release that exists."""
    for item in json.loads(os.environ["RELEASES"]):
        stem = item["package"].replace("-", "_")
        files = [
            str(path)
            for path in sorted(Path(directory).glob(f"{stem}-{item['version']}*"))
        ]
        if (
            subprocess.run(
                ["gh", "release", "view", item["tag"]], capture_output=True
            ).returncode
            == 0
        ):
            subprocess.run(
                ["gh", "release", "upload", item["tag"], *files, "--clobber"],
                check=True,
            )
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as stream:
            stream.write(item["notes"] + "\n")
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                item["tag"],
                *files,
                "--target",
                os.environ["GITHUB_SHA"],
                "--title",
                f"{item['package']} {item['version']}",
                "--notes-file",
                stream.name,
            ],
            check=True,
        )


if __name__ == "__main__":
    if sys.argv[1:2] == ["github"]:
        github(sys.argv[2])
    else:
        main()
