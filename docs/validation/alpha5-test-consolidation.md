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
