# Contributing to CrabXL for Python

## Ways to contribute

- **Report a bug.** Use the [issue forms](https://github.com/crabxl/crabxl-python/issues/new/choose).
  Give the CrabXL version, the Python version and the smallest code or `.xlsx`
  file that shows the problem. Remove confidential data first.
- **Report a difference from openpyxl.** crabxl-openpyxl must behave like
  openpyxl 3.1.5. Give the code, the openpyxl result and the CrabXL result.
- **Improve the documentation.** User documentation is in [docs](docs). The
  documentation site is built from it by
  [crabxl-docs](https://github.com/crabxl/crabxl-docs).
- **Contribute code.** For a change that is larger than a small fix, open an
  issue first. Agree on the design before you start the work.

Do not report security problems in public issues. Read [SECURITY.md](SECURITY.md).

## How this package works

These packages do not implement spreadsheet features themselves. The Rust core
in [crabxl](https://github.com/crabxl/crabxl) implements them. This repository
offers two packages over it: `crabxl`, the native typed API, and
`crabxl-openpyxl`, the openpyxl interface. Both use the native module of
`crabxl-bindings`.

- If a feature is missing in the core, add it to the core first.
- `packages/crabxl-bindings/Cargo.toml` pins the core to an exact crates.io
  version. A change that needs a new core feature waits for a core release.
- The native API follows the core's lossless defaults: a save refuses to drop
  content unless the caller allows it.
- crabxl-openpyxl follows openpyxl: content the core does not model is
  dropped, not refused, and it selects that behavior through core options.
  Never raise `NotImplementedError`. The package never falls back to openpyxl.
- Keep the native API typed: pyright, mypy and pyrefly (configured in
  `pyproject.toml`) must pass in strict mode.
- crabxl supports Python 3.13 and newer; crabxl-openpyxl and the bindings
  support 3.9 and newer. Ruff checks each package for its oldest version.

## Repository layout

| Path | Contents |
|---|---|
| `packages/crabxl` | The crabxl package: the native, typed Python API. |
| `packages/crabxl-openpyxl` | The crabxl-openpyxl package: the openpyxl interface. Its modules follow the openpyxl module layout. |
| `packages/crabxl-bindings` | The crabxl-bindings package: PyO3 bindings to the Rust core. |
| `tests/api` | Tests of crabxl. |
| `tests/adapter` | Tests of crabxl-openpyxl. Files named `test_upstream_*.py` contain selected openpyxl tests. |
| `third_party/` | Provenance and licenses of the code and tests from openpyxl. |
| `docs/` | Public user documentation. |
| `tools/` | Release, wheel and provenance scripts. |

## Development setup

You need:

- [uv](https://docs.astral.sh/uv/).
- Rust 1.99 or later, installed with [rustup](https://rustup.rs/). The
  repository uses the latest stable toolchain. If the build reports that it
  requires a newer `rustc`, run `rustup update stable`.

```sh
git clone https://github.com/crabxl/crabxl-python.git
cd crabxl-python
uv sync --all-packages --group dev
```

The repository is a uv workspace. `uv sync` installs the three packages in
editable mode into `.venv` with Python 3.13 or newer, and builds the native
module. After you change Rust code, build it again:

```sh
uv sync --all-packages --group dev --reinstall-package crabxl-bindings
```

The Rust core comes from crates.io. To build against a local checkout of
[crabxl](https://github.com/crabxl/crabxl) instead, create
`.cargo/config.toml` (Git ignores it):

```toml
[patch.crates-io]
crabxl = { path = "../crabxl/crates/crabxl" }
```

## Checks

CI runs these checks. Run them before you open a pull request:

```sh
uvx ruff format --check .
uvx ruff check .
uvx pyright
uvx mypy
uvx pyrefly check
cargo fmt --all -- --check
cargo clippy --all-targets --locked -- -D warnings
uv run pytest tests -q
```

To test the oldest Python version, build its wheel and test it in a clean
environment:

```sh
uv run --no-project --with maturin tools/packages.py build --python 3.9
uv run --no-project tools/packages.py test --python 3.9
```

CI builds and tests the bindings for every supported Python version on Linux,
and for the oldest and newest on Windows and macOS.

## Code rules

- **Match openpyxl.** Use the same call names, arguments, object access and
  observable behavior as openpyxl 3.1.5. Extensions are permitted, but keep
  them separate from compatible calls.
- **Fail explicitly.** If a feature is not supported, raise an error. Do not
  accept a property that is lost on save.
- **Keep work in Rust.** Convert values in batches. Release the GIL during
  native work.
- **Write in English** in code, comments, documentation and commit messages.

### Tests

- Add tests that compare the CrabXL result with the openpyxl result for the
  same public calls.
- Do not change the assertions of the selected openpyxl tests. Their bodies are
  recorded in `third_party/`. To verify them, run
  `python tools/verify_python_test_provenance.py --reference-checkout <path>`
  with a checkout of openpyxl 3.1.5.
- Mark expected failures explicitly. Do not count them as passes.
- Do not put timing limits in tests. Measure performance with [crabxl-benchmarks](https://github.com/crabxl/crabxl-benchmarks).

### Performance changes

If you claim a speed or memory improvement, include the measurements. Compare
the same mode and the same behavior in CrabXL and openpyxl. Give the time, peak
memory and the commands that you used.

### Code from other projects

You can copy code from another project, including openpyxl, if its license is
compatible with MIT. Keep the original copyright notice and add the project to
[third_party/](third_party).

### Design decisions

Explain large design changes in the pull request.

## Documentation style

Follow the [writing rules](https://github.com/crabxl/crabxl-docs/blob/main/WRITING.md)
and the [page format](https://github.com/crabxl/crabxl-docs/blob/main/CONTENT-SPEC.md).
CI checks them with Vale.

## Commits and pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org/):
  `<type>(<scope>): <description>`. For example:
  `fix(worksheet): keep merged cells after a row insertion`. Common types are
  `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `ci` and `chore`.
- Put one coherent change in each commit. Related code, tests and documentation
  can be in the same commit. Put unrelated changes in separate commits.
- Describe the result, not the work process.
- Complete the pull request template. Link the related issue. Make sure that CI
  passes.

## Releases

Maintainers make releases with the release workflow. You do not need to change
version numbers.

## License

You agree that your contributions are licensed under the [MIT License](LICENSE).
