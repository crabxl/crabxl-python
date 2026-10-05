# ADR 0019: Source-backed worksheet titles

Loaded `Worksheet.title` calls the canonical preserving coordinator using the
current display title. The adapter applies the existing reference-compatible
title validation and case-insensitive suffix selection before the native call;
it updates its display view only after success. It does not force a worksheet
model to load or change the stable native handle. The native call releases the
GIL during source metadata validation. Core owns name uniqueness, original
source/part identity, bounded title overlays and atomic model/package updates.

The shared loaded numeric edit/save workflow now covers a lazily renamed second
sheet, duplicate suffixes, a renamed materialized first sheet, live Cell aliases,
invalid-name rejection, subsequent value/append changes and repeated saves.
Public openpyxl readback verifies original formula and defined-name text remains
unchanged, matching openpyxl 3.1.5 title semantics. The existing opaque-content
workflow verifies renamed packages retain styles, images, comments and unknown
parts. Original selected upstream assertions are unchanged.

The candidate pins published core `150cc84f092a7bd92e8019c7b7e7c934bacb1773`.
All 547 tests, Ruff format/check and strict Clippy pass using a fresh release
wheel on Python 3.12.14/Rust 1.99. Core release resources and full streaming
readback are recorded in
[lazy rename evidence](https://github.com/crabxl/crabxl/blob/main/benchmarks/alpha7-lazy-renaming.md).
This feature checkpoint does not close remaining A7 structural gates or publish
a new package version. Typed metadata graph support remains separately staged.
