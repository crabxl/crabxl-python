# Canonical cell number formats

Status: native/Python integration verified locally; A9 publication pending.

The adapter pins core `84b7aa06e587ce1c4f7f5779d954bdef4a7788a4`.
`Cell.number_format` reads and updates the canonical shared format. `style_id`
and `has_style` reflect native formatting rather than a Python shadow table.
Numeric cells use native number-format classification for `is_date`. Deleted
and overwritten live cell views retain detached value/format snapshots.

Ordinary owned saves now adopt the bank's canonical catalog and use borrowed
workbook export. Cell values are not cloned; the repeatable writer currently
clones the style catalog into its own bounded registry. That temporary metadata
copy remains an optimization opportunity and is not presented as zero-copy
catalog export. Deferred active indexes and empty-workbook error mapping retain
the prior public behavior.

Write-only cells carry an optional format code into the native row operation.
Plain scalar rows do not construct a Python per-cell format list. The native
writer interns each explicit format and uses `Cell::set_style`; automatic date
inference cannot override an explicitly assigned General format. Empty formatted
cells are retained. Other style component properties remain explicitly pending.

Loaded edits delegate to the preserving core coordinator. Only the first guarded
transition validates the complete source/model; subsequent style-only edits reuse
that state and retain aggregate resource checks. Unknown style IDs, signed or
unmodeled styles, data-only edits, missing source stylesheets and affected
unimplemented feature graphs reject explicitly. This does not close M4/M5.

The existing shared temporal test now verifies owned, loaded and write-only
format assignment, unchanged live temporal values, General date integer reload,
empty formatted cells, repeated saves and detached aliases. All 547 existing
compatibility cases pass; no new test functions were added. Ruff formatting,
Ruff checks and strict Clippy pass. Performance acceptance is recorded separately
with exact preview binary hashes; this wheel still carries the unreleased A8
version label and is distinct from the published A8 package.


## Complete-operation measurements

The [worker](../../benchmarks/style_assignment.py) verifies every coordinate,
value and format across 100,000 cells. One warm-up and three alternating
fresh-process samples compare each applicable public mode. Creation/conversion,
all format assignments and ZIP finalization are timed; loaded mode includes
loading. Read-back is outside timing/RSS collection. Linux VmHWM excludes
inherited pre-exec parent peaks. Source fixture generation precedes all workers;
CrabXL imports the verification engine only after measurement. Temp sampling
is a 5 ms lower-bound observation, with output ZIPs excluded and zero remaining
spool bytes verified. No builds/tests overlap the timed runs.

| Mode | CrabXL median seconds | openpyxl median seconds | CrabXL RSS KiB | openpyxl RSS KiB |
| --- | ---: | ---: | ---: | ---: |
| owned | 0.3296 | 0.7467 | 24,084 | 80,132 |
| loaded | 0.4570 | 1.0357 | 24,760 | 84,388 |
| write_only | 0.3398 | 0.8227 | 20,448 | 32,736 |

[Raw final results](../../benchmarks/results/alpha9-style-assignment-python.json)
retain all samples, worker/core identity, CPU time, output sizes, spool observations
and native binary SHA-256. The earlier interrupted run is retained separately;
its single loaded sample took 17.206 seconds before the repeated validation fix.
It is not a repeated before/after median. These workloads establish the required
openpyxl speed target for this scope, not a general native-competitor performance
claim or complete M5 acceptance.

The A9 release pins published core `511d91e60df0b2cc492658f0d867362646f1da20`, with an exact Cargo prerelease version constraint as well as the Git revision. The actual `0.1.0a9` CPython 3.12 release wheel passes all 547 cases and strict Clippy; five-platform workflow/OIDC publication and public-install verification remain pending. Earlier benchmark hashes continue to identify the measured pre-release binary.
