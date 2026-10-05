# ADR 0016: Canonical resource controls as Python extensions

## Decision

`ResourceOptions` supplies `load_workbook` with immutable `ResourceLimits`,
`SharedStringOptions`, optional `AutoMemory` and optional editor patch caps.
Python validates argument shape/ranges and rejects incompatible modes. Native
configuration maps directly to canonical Rust options; no budget calculation,
SST codec, placement policy or cache implementation is duplicated in Python.

Both ordinary loading and read-only workers receive the same owned configuration.
Loaded editors receive archive/XML limits, Auto policy and patch caps. Ordinary
materialization additionally clamps the native Worksheet model allowance to an
explicit max_materialized_bytes. Batch controls apply to optimized read-only
workers and remain bounded by the model/work allowance. Python workers retain
existing cancellation, bounded channel and independent file-position ownership.

Default None fields preserve canonical or existing adapter mode defaults.
`SharedStringOptions.memory_bytes` is a component budget including parser reserve;
it is independent of caller-retained Python models. With no explicit SST budget,
the binding retains its existing resolved model allowance plus canonical working
reserve. `cache_bytes` accounts decoded disk-cache storage, not OS file cache.
Forced-memory storage rejects explicitly supplied disk/cache settings.

`Workbook(auto_memory=...)` tunes the existing resolved model/bank allowance for
ordinary and write-only creation. `model_memory_budget_bytes` exposes that chosen
allowance. Explicit max_memory_bytes and custom Auto controls are mutually
exclusive. Concurrency count divides Auto allowances; it creates no worker pool
or global memory reservation. Loaded models, reader catalogs and editor overlays
still have independent allowances; aggregate loaded-bank migration remains M4.

## Validation

Three batched extension tests cover ordinary/read-only resource failures and
complete outputs, actual custom-directory disk spill/cleanup, forced RAM/disk,
Auto thresholds, cache/temp/entry limits, invalid configuration, batch semantics,
Auto creation in both modes and atomic editor patch-limit failure/reuse.

An existing optimized-mode SST ownership test now shares generated fixture setup;
its behavioral assertions remain. Original upstream test files are unchanged.
The canonical pin is 472482c6f3c94d76ec71f73a4e92a6dc0c50a947. Ruff, native Clippy
and installed-wheel tests validate the checkpoint; this is not full Python
compatibility or a process RSS limit.
