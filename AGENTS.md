# Instructions for AI agents

These rules apply to AI agents that work on this repository. Where they differ
from [CONTRIBUTING.md](CONTRIBUTING.md), these rules win.

Read [internal/STATUS.md](internal/STATUS.md) before you start. It gives the
current state and the next tasks.

## Goal

This package gives Python users the openpyxl 3.1.5 API on top of the CrabXL
Rust core. It has two hard requirements:

1. **Fast.** Faster than openpyxl. Faster than python-calamine (reading) and
   XlsxWriter (writing) is the target.
2. **Low memory.** Lower peak memory than openpyxl, python-calamine and
   XlsxWriter.

Everything else (code style, module layout, how files are split or merged,
internal names) is up to you.

## How to work

- **Plan a whole stage, then build it.** A stage normally adds a feature group
  to the Rust core and to this package together. Implement the whole stage,
  then test and fix in one pass.
- **Copy code freely.** You may read and copy any code whose license is
  compatible with MIT, including openpyxl. Keep the original copyright notice
  and record the project once in `third_party/`.
- **Measure at the end of a stage.** Run the fixed benchmark suite once per
  stage against openpyxl, python-calamine and XlsxWriter. Do not write a
  benchmark script or a report for each feature.
- **Keep records short.** Update `internal/STATUS.md` when a stage ends. Do not
  write new ADRs, checkpoint reports or validation records.

## Product rules

- The public API must match openpyxl 3.1.5: call names, object access and
  observable behavior. Extensions are permitted.
- Implement spreadsheet features in the Rust core, not in Python. This package
  only adapts the core to the openpyxl API.
- Do not fall back to openpyxl at run time. Do not accept a property that is
  lost on save. Raise an explicit error for an unsupported feature.
- Pin the Rust core to an exact Git revision in `Cargo.toml`. During a stage
  you can use a local path or patch to the core; pin the revision before you
  push.
- Do not change the assertions of the selected openpyxl tests. Track expected
  failures explicitly. Do not count them as passes.

## Memory and performance

- Convert values between Python and Rust in batches. Release the GIL for
  native work.
- Do not create one Python object per cell unless the openpyxl API returns
  one.
- Keep timing measurements out of ordinary tests.

## Repository map

| Path | Use |
|---|---|
| `python/crabxl` | Public Python package. Its modules follow the openpyxl module layout. |
| `src/` | PyO3 bindings to the Rust core. |
| `tests/` | Compatibility tests, including selected openpyxl tests. |
| `third_party/` | Licenses and sources of copied code and tests. |
| `docs/` | Public user documentation. The documentation site publishes this folder. |
| `internal/` | Status, roadmap and architecture. Not published. Older ADRs and reports are history; do not add to them. |
| `benchmarks/` | Benchmark scripts and results. |
| `tools/` | Release, wheel and provenance scripts. |

The Rust core is in [crabxl](https://github.com/crabxl/crabxl). The
documentation site is in [crabxl-docs](https://github.com/crabxl/crabxl-docs).

## Writing

- Write all repository content in English.
- User documentation in `docs/` and the README is for people. Follow the
  documentation style in [CONTRIBUTING.md](CONTRIBUTING.md) and the content
  specification in crabxl-docs.
- Code comments, internal records and commit messages only need to be clear
  and short. No word limits apply.

## Commits

- Use this Git identity for author and committer, unless the user gives another
  identity: `cmostw <300344883+cmostw@users.noreply.github.com>`. Set it in the
  repository configuration.
- Use Conventional Commits: `<type>(<scope>): <description>`.
- Commit at natural boundaries. A whole stage can be one commit or a few.
- Push when a stage is complete or when the user asks. Do not force-push unless
  the user authorizes it.
