# Python releases

This repository releases three packages, each with its own version, changelog
and tags:

| Package | Contents | Python | Wheels |
| --- | --- | --- | --- |
| `crabxl-bindings` | The native module (`packages/crabxl-bindings`) | 3.9+ | 35 native |
| `crabxl` | The typed API (`packages/crabxl`) | 3.13+ | pure Python |
| `crabxl-openpyxl` | The openpyxl interface (`packages/crabxl-openpyxl`) | 3.9+ | pure Python |

Versions are `X.Y.Z`; tags are `<package>-X.Y.Z`. The plain `X.Y.Z` tags up to
0.5.0 are crabxl's. Before 1.0, a minor version can change the API. Only
tested, usable changes get a release.

crabxl and crabxl-openpyxl require `crabxl-bindings~=X.Y.Z`. The interface of
the bindings is private, so a minor bindings release breaks it: release it
together with both packages, and raise their requirements. A patch release of
the bindings, such as a new Rust core, must keep the interface, so the two
packages need no release.

Describe every change under `## [Unreleased]` in the package's
`CHANGELOG.md` as you make it.

## Release

Release the Rust core first when the bindings need a new core. Then prepare
each package to release:

```sh
python tools/release.py prepare crabxl-bindings 0.6.1 --core 0.4.1
python tools/release.py prepare crabxl 0.6.1
python tools/release.py prepare crabxl-openpyxl 0.6.1
```

This sets the version (and `__version__`), renames `## [Unreleased]` in the
package's changelog to the version, and for the bindings sets the core
dependency and Cargo.lock. It fails when the core version is not on crates.io
yet, and when a package requires bindings that this commit does not build.
Move a local `.cargo/config.toml` aside first, or Cargo.lock records the local
core path. Review the changes, commit them as `Release <packages>` and push to
`main`. Nothing else is manual.

The **Release Python** workflow runs on every push to `main` and releases each
package whose committed version has no tag yet:

1. The bindings build on five platforms for CPython 3.9 to 3.15, and each
   wheel runs the tests with this commit's crabxl-openpyxl and, on 3.13 and
   newer, crabxl. Their sdist is built, installed and tested on 3.15.
2. The pure-Python packages are built with `uv build` and tested on 3.9, 3.13
   and 3.15, with the bindings of this release or, when the bindings are not
   released, the ones on PyPI.
3. The bindings are published first, then each pure-Python package.
4. The tags and GitHub releases are created on that commit, with the
   changelog sections as notes.

A release of only crabxl or crabxl-openpyxl compiles nothing and takes a few
minutes.

## PyPI trusted publishers

Each package publishes from its own GitHub environment, so each PyPI project
has its own trusted publisher, and pending publishers never clash:

| PyPI project | Environment |
| --- | --- |
| `crabxl` | `pypi-crabxl` |
| `crabxl-openpyxl` | `pypi-crabxl-openpyxl` |
| `crabxl-bindings` | `pypi-crabxl-bindings` |

The other fields are the same for all three: owner `crabxl`, repository
`crabxl-python`, workflow `release.yml` (the filename, **not** the display
name). OIDC uses `id-token: write` only in the publish jobs; no API token is
needed. See https://docs.pypi.org/trusted-publishers/ .

## Platforms

| System | Architecture |
| --- | --- |
| Linux (manylinux 2.28) | x86_64, ARM64 |
| Windows | x86_64 |
| macOS | Intel x86_64, Apple Silicon ARM64 |

Each platform job builds all seven CPython wheels on one runner and shares the
Cargo target directory. Alpine/musllinux, Windows ARM64, PyPy, GraalPy and
free-threaded Python are not included.

Before publishing, `tools/check_release_files.py` checks every file, its
version and Python support, and any PyPI file of the same name. If an upload or
the GitHub release step fails, rerun the failed jobs, or run the workflow
manually on `main`. Identical PyPI files are skipped; different file hashes are
rejected. PyPI publication cannot be undone. Do not move tags or raise a
version only to hide an interrupted release.

## Quality checks

CI and release validation require `ruff format --check .` and `ruff check .`.
Ruff checks crabxl-openpyxl as Python 3.9 code and crabxl as 3.13 code. CI
also requires pyright, mypy and pyrefly in strict mode for crabxl; ty runs as
advice. The three provenance-tracked upstream test files are excluded from
Ruff so that their reference bodies stay unchanged; they still run in every
test job.
