# Contributing to CrabXL for Python

## Ways to contribute

- **Report a bug.** Use the [issue forms](https://github.com/crabxl/crabxl-python/issues/new/choose).
  Give the CrabXL version, the Python version and the smallest code or `.xlsx`
  file that shows the problem. Remove confidential data first.
- **Report a difference from openpyxl.** CrabXL must behave like openpyxl
  3.1.5. Give the code, the openpyxl result and the CrabXL result.
- **Improve the documentation.** User documentation is in [docs](docs). The
  documentation site is built from it by
  [crabxl-docs](https://github.com/crabxl/crabxl-docs).
- **Contribute code.** For a change that is larger than a small fix, open an
  issue first. Agree on the design before you start the work.

Do not report security problems in public issues. Read [SECURITY.md](SECURITY.md).

## How this package works

This package does not implement spreadsheet features itself. The Rust core in
[crabxl](https://github.com/crabxl/crabxl) implements them. This package adapts
the core to the openpyxl API.

- If a feature is missing in the core, add it to the core first.
- `Cargo.toml` pins the core to an exact Git revision. A change that needs a
  new core feature also updates this revision.
- An unsupported feature raises an explicit error, usually
  `NotImplementedError`. The package never falls back to openpyxl.

## Repository layout

| Path | Contents |
|---|---|
| `python/crabxl` | Public Python package. Its modules follow the openpyxl module layout. |
| `src/` | PyO3 bindings to the Rust core. |
| `tests/` | Tests. Files named `test_upstream_*.py` contain selected openpyxl tests. |
| `third_party/` | Provenance and licenses of the selected openpyxl tests. |
| `docs/` | Public user documentation. |
| `internal/` | Maintainer records: [status](internal/STATUS.md), roadmap, architecture, design decisions and release evidence. |
| `benchmarks/` | Benchmark scripts. Reports are in `reports/`. Raw data is in `results/`. |
| `tools/` | Release, wheel and provenance scripts. |

## Development setup

You need:

- Python 3.11 or later.
- Rust 1.99 or later, installed with [rustup](https://rustup.rs/). The
  repository uses the latest stable toolchain. If the build reports that it
  requires a newer `rustc`, run `rustup update stable`.

```sh
git clone https://github.com/crabxl/crabxl-python.git
cd crabxl-python
python -m venv .venv
source .venv/bin/activate
python -m pip install "maturin>=1.15,<2"
python -m pip install -e ".[test,dev]"
```

The editable install builds the native extension. After you change Rust code in
`src/`, build it again:

```sh
maturin develop --release
```

## Checks

CI runs these checks. Run them before you open a pull request:

```sh
ruff format --check .
ruff check .
cargo fmt -- --check
cargo clippy --all-targets --locked -- -D warnings
python -m pytest tests -q
```

CI also builds and tests wheels for all supported Python versions on Linux,
Windows and macOS.

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
- Do not put timing limits in tests. Measure performance in `benchmarks/`.

### Performance changes

If you claim a speed or memory improvement, include the measurements. Compare
the same mode and the same behavior in CrabXL and openpyxl. Give the time, peak
memory and the commands that you used.

### Design decisions

Record a significant design decision as an Architecture Decision Record (ADR)
in [internal/decisions](internal/decisions). The ADR numbers in this
repository are independent of the ADR numbers in the Rust core.

## Documentation style

User documentation follows the principles of ASD-STE100 (Simplified Technical
English):

- Write short sentences: 20 words or fewer in an instruction, 25 or fewer in a
  description.
- Give one instruction in each sentence.
- Use the active voice.
- Use one word for one meaning. Use the terms in the project glossary in
  [crabxl-docs](https://github.com/crabxl/crabxl-docs).

The page format is defined in crabxl-docs. CI checks the style with Vale.

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
version numbers. [internal/releases.md](internal/releases.md) describes the
process.

## License

You agree that your contributions are licensed under the [MIT License](LICENSE).
