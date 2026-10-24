# Live merged sets and A11 structural integration

Worksheet merged collections now expose mutable raw membership, exact set
insertion, stable live coordinate views and atomic bulk replacement. Coordinates
and membership remain native; weak Python observations preserve caller-visible
view identity. Removed observations become detached coordinate snapshots. Raw
metadata edits retain existing physical values and realized virtual appearances.

Insertion/deletion and range movement update cached rich/hyperlink owners only
after native success. Serialized merge declarations and hyperlink references
retain their independent public semantics. Native sparse virtual pieces preserve
border geometry without materializing covered cells. Source mutations use the
canonical loaded coordinator and repeat-save relationship handling.

Rich list copies keep shared public run objects but start with independent
worksheet bindings. The optimization utility uses the same transactional native
value update as list mutation. Sparse dimension index conversion uses the native
coordinate facade rather than a missing package-root export.

Explicit write-only worksheet close is a serialization boundary in the pinned
reference. Hyperlink groups are therefore worksheet-local observations of a
shared public object. Closed sheet groups retain their last payload; open sheet
groups remain live. The native bounded identity visitor updates public IDs at
close, and final save applies IDs in worksheet output order. This supersedes
ADR 0041's assumption that closed-sheet groups should continue to mutate.

Consolidated acceptance uses shared assertions against openpyxl 3.1.5 for owned,
loaded and applicable sequential behavior. Resource extensions and sparse-grid
checks remain separate native/adapter assertions. Compilation alone does not
establish A11 publication or complete baseline compatibility.
