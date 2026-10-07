# Canonical appearance components

Status: A10 published and verified from public registries.

`crabxl.styles` exposes font, color, pattern/gradient fill, side/border, alignment
and protection values with familiar constructor aliases. Editable/loaded cell
properties return immutable proxies; callers copy, change and reassign them.
Read-only properties resolve the reader's catalog. Write-only directives carry
checked native component snapshots and remain bounded by the row byte allowance.
The Rust workbook or writer owns shared component and cell-format identities.

Each caller-owned mutable appearance value retains at most one current native
snapshot. A local revision and child revisions invalidate it after direct or
nested color/side/gradient-stop changes. There is no global unbounded style cache.
Detached aliases keep a separate small appearance snapshot. Default getters do
not allocate an entire registry. Full-component write-only rows count native
appearance payloads before cloning them into the detached writer operation.

Appearance updates retain number formats and automatic temporal behavior;
explicit General assignments continue to select numeric date serialization.
Sources retain core guards for signed/data-only packages, unknown style sections,
missing stylesheets and affected unmodeled graphs. Named styles, themes,
row/column appearance and advanced feature graph interactions remain later gates.

All 547 compatibility cases pass against the pinned native checkpoint
`626d3e24f6744237a975cf4b377242656cd58ed6`, including public-reference repeated
saves, gradients, diagonal borders, immutable proxies, nested cache invalidation,
read-only components and write-only dates with appearance but no explicit format.
Ruff and strict Clippy pass. The existing complete-operation benchmark now has a
full-component mode, one warm-up and three alternating samples per engine/mode,
with every saved appearance checked outside timing/RSS collection. Initial and
intermediate failed speed results remain alongside the final pinned evidence;
all final modes pass the required openpyxl speed gate. Public package/platform
receipts follow publication; no universal or native-competitor claim is made.

Publication pins release core `50e4861336a5a4b019f671dee8fa65f488bb4053`,
whose component implementation matches the measured checkpoint; manual package
versions are `0.1.0-alpha.10` / `0.1.0a10`.

The actual `0.1.0a10` release wheel passed all 547 cases in 4.61 seconds
on CPython 3.12.14; platform and public-registry receipts remain pending.

Release workflow 37561869461 passed all five platform jobs and CPython 3.11–3.15
gates before OIDC publication. PyPI now contains 25 wheels and one source archive.
A clean CPython 3.12 installation of the public manylinux 2.28 wheel passed the
release commit's unchanged 547 cases in 4.88 seconds. See the canonical
[artifact receipt](https://github.com/crabxl/crabxl/blob/main/docs/validation/alpha10-release.json).
