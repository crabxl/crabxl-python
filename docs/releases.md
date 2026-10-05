# Python alpha releases

Only newly usable, tested functionality warrants the next manually chosen alpha
number. Do not backfill historical tags or increment versions on ordinary pushes.
The adapter numbers its releases independently from the Rust repository and pins
the verified canonical engine revision in Cargo.toml.

## Prepare the committed version

```sh
python tools/release.py prepare 0.1.0-alpha.1
```

The helper synchronizes Cargo's `0.1.0-alpha.N`, Python metadata and public
`__version__` as `0.1.0aN`, and Cargo.lock. It does not commit, tag or publish.
Review and commit the version with the usable feature checkpoint. The first release uses Git tag `0.1.0-alpha.1` and Python version `0.1.0a1`.

## PyPI Trusted Publisher configuration

Create a pending publisher for the first package upload, or add a publisher to
the existing project's publishing settings:

| PyPI field | Value |
| --- | --- |
| Project name | `crabxl` |
| Owner | `crabxl` |
| Repository | `crabxl-python` |
| Workflow name (filename) | `release.yml` |
| Environment name | `pypi` |

PyPI's workflow field is the filename, **not** the GitHub display name.
Create/use the GitHub environment `pypi`; any configured environment protections
apply to the publication job. OIDC uses `id-token: write` only in that job. No PyPI
API token is needed. See https://docs.pypi.org/trusted-publishers/ .

## Run and outputs

- GitHub Workflow name: **Release Python alpha**.
- Workflow file: `.github/workflows/release.yml`.
- Run on the default branch with the committed tag version, new-feature notes and
  `usable_feature` selected.

All five CPython versions (3.11 through 3.15) build native wheels on each of:

| System | Architecture |
| --- | --- |
| Linux (manylinux 2.28) | x86_64, ARM64 |
| Windows | x86_64 |
| macOS | Intel x86_64, Apple Silicon ARM64 |

Five platform/architecture build jobs each build all five CPython wheels in one
runner, sharing the Cargo target directory. Ordinary Rust dependencies are reused;
PyO3 and the adapter are rebuilt for each Python ABI. Linux builds use one
manylinux container per platform. Ordinary Linux CI uses the same multi-interpreter
builder. A failed platform job reruns that platform's five versions.

Each of the 25 combinations runs the complete selected compatibility suite after
installation into a clean, platform-native virtual environment. Only 3.15 permits
a release candidate until stable is available. The sdist is also built, installed
and tested independently. Alpine/musllinux, Windows ARM64, PyPy, GraalPy and
free-threaded Python are not included.

After every build/test job passes, the workflow checks all 26 artifacts, their
package versions and any existing PyPI file hashes, then publishes through
`pypa/gh-action-pypi-publish` using OIDC. PEP 740 attestations use the action's
default behavior. It then creates `0.1.0-alpha.N` as a GitHub prerelease with all
26 files attached, targeting the checked-out commit.

If an upload or GitHub release step fails, rerun the same workflow commit/version.
Identical existing PyPI files are skipped; conflicting file hashes and tags
pointing at a different commit are rejected. PyPI publication is irreversible
and can partially succeed before a later step fails. Do not overwrite tags or
increase the number merely to hide an interrupted release.

## Python quality checks

Ordinary CI and release validation require `ruff format --check .` and
`ruff check .`. Install the declared `dev` extra for Ruff. The configuration
targets Python 3.11 and checks syntax, errors, undefined/unused names and import
ordering. The three provenance-tracked upstream test files are excluded from
Ruff transformations to retain their unchanged reference bodies. They still run
in every compatibility test job. Original adapter tests, package code, tools and
benchmarks are formatted and checked.

Python wheels are compiled using the latest stable Rust toolchain (currently
1.99). Prebuilt wheel installation does not require Rust. Source builds require
Rust 1.99 or newer under the adapter manifest, independently of the core crate
MSRV. Alpha.3 pins canonical Rust alpha.3 commit
`d9fddb01abf3da4715fa6f0cc7c00371d5826471`, including quick-xml 0.42, streaming APIs,
Windows same-path save replacement and bounded editor compression buffering.
The core crate MSRV is Rust 1.88.

A committed `.github/release-request.json` can also initiate publication on push
to the default branch, using the same manual-version, feature and test gates.
