# ADR 0014: Optimized-mode stream ownership

The Python adapter exposes `load_workbook(..., read_only=True)` and
`Workbook(write_only=True)` over canonical CrabXL streams. It contains no XML or
ZIP codec and never falls back to openpyxl.

Read-only loading retains one original file handle, metadata and dimensions,
without constructing editable sheets or an editor. Each row iterator owns a Rust
worker/parser and an independent logical input offset. A mutex makes seek/read
atomic over the original handle; cloning an OS handle alone would share offsets.
A one-batch channel and byte/count bounded canonical batches provide backpressure.
Values-only iteration converts a row in one native call and does not allocate
Python cells or per-scalar tagged tuples. Scalar Python values pass directly;
temporal, exact-integer and structured-formula objects use the compatibility
conversion. Shared strings spill into anonymous/delete-on-close data/index files
when their retained allowance is exhausted. Independent iterators are safe; each has its own bounded working
allowance and shared-string storage, so their allowances are not a global RSS cap.

Closing a generator drops queued rows, cancels its worker, disconnects the channel
and joins the thread while releasing the GIL. Closing the workbook cancels all
live native streams and closes the original handle. Finite row bounds, including the
worksheet's declared dimensions, opt into the core prefix policy: unread
worksheet XML and its CRC are not validated. Resetting dimensions and consuming
an unbounded stream retains complete core validation. Missing or unreliable dimensions can be
reset, then calculated by consuming a stream.

Write-only worksheets retain only a bounded encoded row and one disk spool per
sheet. The canonical writer supports interleaved append calls, final creation
order, renaming, active selection and temporal options before the first append.
A save consumes the writer once, packages into an adjacent temporary file and
renames it into place. Failure, abort and drop clean owned spools. Temporary space
contains worksheet XML plus a transient final ZIP; the memory allowance does not
limit disk space. Core writer statistics expose spool peak bytes.

Scalar values, temporal formats and supported normal/array/data-table formulas
use canonical conversion. Full style objects, rich-text objects, arbitrary
structural edits and file-like I/O remain staged and raise explicit errors.
Read-only sheets reject mutation; write-only sheets reject random access and
repeated saves. Mode parity is claimed only for the tested scalar/formula and
lifecycle behavior, not the complete openpyxl optimized feature set.
