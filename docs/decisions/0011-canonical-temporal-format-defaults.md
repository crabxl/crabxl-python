# ADR 0011: Canonical temporal default formats

The adapter pins published core 26f4f5d7d18aaf36a2669174d925e71041f51159. The canonical writer now uses the public date/datetime/clock/duration default codes and derives component-sharing variants for explicit non-date styles. This adapter adds no format table or style engine.

Eight shared tests compare assigned temporal values and all four saved default number-format codes through public readback. All 447 tests pass using the installed locked release wheel, including all 63 selected unchanged original test bodies and parameter sets verified at the pinned reference. General Python style assignment/views remain staged; supported saved defaults do not imply a complete style object surface.

Core ADR 0038 and benchmarks/m2-temporal-styles.md record twenty explicit style/value cases, streaming creation and immediate prior native regression. Those timings exclude Python adapter conversion and are not claimed as binding performance results. Existing direct array/table binding evidence remains historical and pinned to its measured revision. M2/M4/M5 and complete Python compatibility remain open.
