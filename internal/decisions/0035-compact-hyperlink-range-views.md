# Compact hyperlink range views

The adapter pins published core revision
`73d772dd5b057bc13a1f441084b54b024cb15689`. Native declarations retain compact
rectangle coverage. A requested cell receives a public hyperlink view with its
own coordinate; creating the view does not expand the remaining rectangle.
Actual native coverage is queried independently of a point object's serialized
reference, so live reference edits preserve their independent alias semantics.

Point field changes, assignment and removal inside a decoded range use the
native split coordinator. The adapter propagates fallible physical removal;
resource rejection leaves the value and metadata intact. No Python geometry
engine, per-cell URL table or alternative package writer is introduced.

Rust 1.99 library compilation passes. Imported empty-anchor values, write-only
live links, post-save identities, alias transaction scaling and full A11
acceptance remain tracked work. New tests and measurements are deferred until
the complete release scope is implemented.
