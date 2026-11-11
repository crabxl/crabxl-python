# Python releases

Versions are `X.Y.Z`, the same string for Cargo, PyPI and the Git tag. Before
1.0, a minor version can change the API. Only tested, usable changes get a
release. Each release depends on an exact Rust core version from crates.io.

Describe every change under `## [Unreleased]` in `CHANGELOG.md` as you make it.

## Release

Release the Rust core first when this release needs a new core. Then run:

```sh
python tools/release.py prepare 0.1.3
```

This sets the Cargo version, the Python version, `__version__`, the core
dependency (the same version by default; pass `--core 0.1.4` for another) and
Cargo.lock, renames `## [Unreleased]` to `## [0.1.3]` with the core version,
and updates the bug report form. It fails when the core version is not on
crates.io yet. Review the changes, commit them as `Release 0.1.3` and push to
`main`. Nothing else is manual.

The **Release Python** workflow runs on every push to `main`. When the
committed version has no tag yet, it builds and tests every wheel and the
sdist, publishes them to PyPI, and then creates the tag and the GitHub release
on that commit. The changelog section becomes the release notes. Pushes whose
version already has a tag stop after the version check.

## PyPI Trusted Publisher configuration

Create a pending publisher for the first upload, or add a publisher to the
existing project's publishing settings:

| PyPI field | Value |
| --- | --- |
| Project name | `crabxl` |
| Owner | `crabxl` |
| Repository | `crabxl-python` |
| Workflow name (filename) | `release.yml` |
| Environment name | `pypi` |

PyPI's workflow field is the filename, **not** the GitHub display name. The
GitHub environment `pypi` applies its protections to the publication job. OIDC
uses `id-token: write` only in that job. No PyPI API token is needed. See
https://docs.pypi.org/trusted-publishers/ .

## Run and outputs

- GitHub workflow name: **Release Python**.
- Workflow file: `.github/workflows/release.yml`.

All five CPython versions (3.11 through 3.15) build native wheels on each of:

| System | Architecture |
| --- | --- |
| Linux (manylinux 2.28) | x86_64, ARM64 |
| Windows | x86_64 |
| macOS | Intel x86_64, Apple Silicon ARM64 |

Each platform job builds all five CPython wheels on one runner and shares the
Cargo target directory. Linux builds use one manylinux container per platform.
A failed platform job reruns that platform's five versions.

Each of the 25 combinations runs the complete compatibility suite after
installation into a clean virtual environment. Only 3.15 may be a release
candidate until it is stable. The sdist is also built, installed and tested.
Alpine/musllinux, Windows ARM64, PyPy, GraalPy and free-threaded Python are not
included.

After every build and test job passes, the workflow checks all 26 artifacts,
their versions and any existing PyPI file hashes, then publishes with
`pypa/gh-action-pypi-publish` through OIDC. It then creates the tag and the
GitHub release with all 26 files.

If an upload or the GitHub release step fails, rerun the failed jobs of the same
workflow run, or run the workflow manually on `main`. Identical PyPI files are
skipped; different file hashes are rejected. PyPI publication cannot be undone
and can partly succeed before a later step fails. Do not move tags or raise the
version only to hide an interrupted release.

## Python quality checks

CI and release validation require `ruff format --check .` and `ruff check .`.
Install the `dev` extra for Ruff. The configuration targets Python 3.11. The
three provenance-tracked upstream test files are excluded from Ruff so that
their reference bodies stay unchanged; they still run in every test job.
