# Instructions for AI agents

These rules apply to AI agents that work on this repository. Human contributors
use [CONTRIBUTING.md](CONTRIBUTING.md). The rules in CONTRIBUTING.md also apply
to agents.

Read [internal/STATUS.md](internal/STATUS.md) before you start. It tells you
the current state and the next tasks.

## Repository map

| Path | Use |
|---|---|
| `python/crabxl` | Public Python package. Its modules follow the openpyxl module layout. |
| `src/` | PyO3 bindings to the Rust core. |
| `tests/` | Compatibility tests, including selected openpyxl tests. |
| `third_party/` | Provenance and licenses of the selected openpyxl tests. |
| `docs/` | Public user documentation. The documentation site publishes this folder. |
| `internal/` | Records for maintainers and agents. Not published. |
| `benchmarks/` | Benchmark scripts. Reports are in `reports/`, raw data is in `results/`. |
| `tools/` | Release, wheel and provenance scripts. |

The Rust core is in [crabxl](https://github.com/crabxl/crabxl). The
documentation site is in [crabxl-docs](https://github.com/crabxl/crabxl-docs).

## Language and identity

- Write all repository content in English.
- Use this Git identity for author and committer, unless the user gives another
  identity: `cmostw <300344883+cmostw@users.noreply.github.com>`. Set it in the
  repository configuration. Do not use the global identity of the environment.

## Writing rules

These rules apply to all text: documentation, internal records, comments, error
messages and commit messages. They follow the principles of ASD-STE100
(Simplified Technical English). The STE dictionary is not used. Use the project
glossary in crabxl-docs instead.

- Write only information that the reader uses. Each sentence must give a fact,
  an instruction or a limit. Do not write slogans, praise, thanks or text about
  the text. Do not repeat a statement on the same page.
- Write short sentences. Use a maximum of 20 words in an instruction and 25
  words in a description.
- Give one instruction in each sentence.
- Use the active voice and the imperative for instructions.
- Use one word for one meaning. Use the glossary term. Do not use synonyms.
- Do not put more than three nouns in a sequence.
- Write for a reader who does not know the history of the project. Do not use
  milestone or release codes (for example "M4" or "A11") without a definition.
- Do not record conversations. Do not write "the user approved" or "the user
  asked". Record the decision and its reason.

## Where to write records

- `docs/` is public. Put only user documentation there. Follow the content
  specification in crabxl-docs.
- `internal/STATUS.md` is the single current status. Replace its content when
  the status changes. Do not append a history log.
- `internal/roadmap.md` is the long-term plan. Edit it in place. Remove items
  that are done or no longer planned.
- `internal/decisions/` contains Architecture Decision Records (ADRs) of this
  repository. Their numbers are independent of the ADRs in the Rust core.
  Write an ADR only for a decision that changes a public contract or a
  resource strategy.
- `internal/validation/` contains release acceptance evidence.
- `benchmarks/reports/` contains benchmark reports. `benchmarks/results/`
  contains raw data.

## Product rules

- The public API must match openpyxl 3.1.5: call names, object access and
  observable behavior. Users must not need to learn a different API.
  Additional capabilities are permitted as extensions.
- Implement spreadsheet features in the Rust core, not in Python. This
  package only adapts the core to the openpyxl API.
- Do not fall back to openpyxl at run time. Do not accept a property that is
  lost on save. Raise an explicit error for an unsupported feature.
- Pin the Rust core to an exact Git revision in `Cargo.toml`. Do not copy core
  code into this repository. Test changes against the pinned revision.
- Reuse selected openpyxl tests without changes to their assertions. Record
  their license and provenance in `third_party/`. Track expected failures
  explicitly. Do not count them as passes.
- Use openpyxl documentation, public behavior and fixtures as references. Do
  not read the openpyxl implementation broadly. Reading the diff of a pending
  openpyxl merge request is permitted to review a known defect.
- Follow the [binding contract](internal/binding-contract.md) and read
  [internal/architecture.md](internal/architecture.md) before you change an
  affected area.

## Memory and performance

- CrabXL must be faster than openpyxl. Compare equivalent modes and behavior.
- Do not claim an improvement without a measurement. Record time, peak memory,
  temporary storage and checksums.
- Keep conversion between Python and Rust in batches where possible. Release
  the GIL for native work.
- Keep timing measurements out of ordinary tests.

## Commits

- Read and follow [Coherent Commits](.agents/skills/commit/SKILL.md) before you
  make a commit.
- Use Conventional Commits: `<type>(<scope>): <description>`. Describe the
  result, not the work process.
- Put one coherent intent in each commit.
- Before you commit, review the staged changes, check the identity and run the
  applicable checks.
- Push each commit immediately after you make it. Make sure that the remote
  has the commit before you make the next commit.
- Do not force-push unless the user authorizes it.
- If a push fails, keep the local commit, report the problem and try again.
