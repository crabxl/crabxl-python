# Canonical packed models through Python

The adapter pins published core `b6277d039233f598e32f288003c566407afe9a73`,
including packed cells, source-aware atomic append and mode-aware retained text.
The paired prior wheel pins namespace-optimized core `c5b4cf2`; both use Python
3.12.14, the same adapter/probe semantics and release Rust 1.99. Exact installed
source/native hashes are recorded. This numeric probe measures cell packing
through ordinary `load_workbook` and complete `iter_rows(values_only=True)`;
it does not establish text-sharing gains through Python.

One warmup and three rotating serial cold-process samples at each scale,
including imports, deferred model population, value conversion and cleanup.
Generation, builds and tests occur outside timings. Every value contributes to
the exact count/sum checks. Both use a 1 GiB model allowance and no read-side
temporary files; this is not an RSS cap.

At one million cells, median total wall time decreases from 1.3054 to 1.0239
seconds (about 22%) and peak RSS from 97,672 to 51,696 KiB (about 47%). Iteration,
which triggers full materialization, decreases from 1.2177 to 0.9639 seconds.
Opening alone remains lazy and is not the complete loading cost.

The shared loaded-edit workflow now also verifies dictionary append, formulas,
empty-row cursor advancement and repeated preserving saves against openpyxl.
All 547 tests, Ruff format/check and strict Clippy pass. The Rust coordinator
remains responsible for resource preflight and atomic model/package updates.
Unsupported loaded values/graphs remain explicit errors.

No calamine Python or dataframe comparison is claimed. Native retained-model
speed remains slower than calamine; source-aware structural changes, further
parser improvements and bounded dataframe conversion remain open.
All sizes and samples: [raw report](results/alpha7-packed-python.json).
