# Alpha.5 test consolidation

The temporal replacement matrix in `tests/test_parity.py` retains all four
initial temporal types and all five replacement values against both CrabXL and
openpyxl. The twenty independent cells for each engine now share workbook setup
and save/reopen operations. Assertions still compare live values, reference
values, number formats, original output and two subsequent saves.

This replaces forty parametrized invocations with two batched invocations.
Independent-cell diagnostics identify the initial/replacement pair on failure.
No original upstream test body or assertion was modified.

Validation with CPython 3.12 and the alpha.4 native wheel:

- Before: 40 targeted cases passed in 0.73 seconds.
- After: 2 targeted cases passed in 0.15 seconds.
- Full consolidated suite: 541 passed in 2.83 seconds.

These are local pytest durations, not spreadsheet performance benchmarks or a
coverage-percentage claim. All forty semantic combinations remain exercised.

Final alpha.5 resource controls add three batched tests for validation/modes,
actual read/edit limits and RAM/Auto/disk SST/cache/temp behavior. This yields
544 tests while retaining all original semantic combinations. The canonical
core revision is 7efa37b10c6b19757ff58dbf930f9e233b3af7d4; its M2 acceptance,
coverage, native-platform checks and measurements are linked in the core's
`docs/validation/alpha5-m2-acceptance.md`. Complete Python compatibility remains
staged. Ruff validation covers the whole repository, including README snippets.

Final installed alpha.5 candidate wheels, tested serially against the exact
canonical core pin:

| CPython | Result | Local pytest duration |
| --- | --- | --- |
| 3.11 | 544 passed | 3.68 s |
| 3.12 | 544 passed | 3.22 s |
| 3.13 | 544 passed | 2.93 s |
| 3.14 | 544 passed | 2.92 s |
| 3.15 RC | 544 passed | 2.81 s |

These local durations include test collection/setup and are not library speed
benchmarks. All five release-mode native wheels are installed independently;
Ruff format/check over the full repository, Rustfmt and strict Clippy pass.
