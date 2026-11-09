
Optional/literal array text compatibility tests and same-call benchmark fixtures are original public API comparisons, without further reference implementation inspection. Rust core owns expression presence and Unicode body slicing; the adapter only converts properties and optional ownership. Existing selected upstream tests/assertions remain unchanged. See ADR 0008.

Literal formula reference/input tests are original public constructor/save/reload/property comparisons. They add no copied implementation. Canonical ownership and coordinate validation live in Rust core. All 63 selected upstream bodies and parameters remain unchanged. See ADR 0009.

Raw flag and compatible formula-header comparisons are original public API tests. The 63 selected pinned test bodies/parameters remain unchanged and verified. No additional reference implementation is copied or inspected. See ADR 0010.

Temporal default-format readback cases are original shared public API comparisons. The canonical format defaults and style variants live in Rust core. All 63 selected original test bodies/parameters remain unchanged. See ADR 0011.

Temporal replacement/repeated-save tests and same-call benchmarks are original public API comparisons. Canonical temporal assignment and style ownership live in Rust core; the adapter only carries existing IDs. All 63 selected original test bodies and parameters remain unchanged. See ADR 0012.

Literal shared-ID tests and benchmarks are original public API/OOXML fixture comparisons. All 63 selected reference test bodies and parameter sets remain unchanged and verified. The adapter adds no shared-formula codec or translation engine. See ADR 0013.

Feature classes (tables, filters, conditional-format rules, data validation, comments, protection, header/footer, defined names, document properties) are copied from openpyxl 3.1.5 (MIT, `licenses/openpyxl-MIT.txt`): `python/crabxl/descriptors`, `compat`, `xml`, `comments`, `packaging`, `formatting`, `styles/_x`, `styles/differential.py`, selected `utils` modules, and the matching `worksheet` and `workbook` modules. Each file starts with an attribution line. They are serialisation shells; the Rust core owns the model and the package codecs (the bridge passes XML). No openpyxl tests are copied for this group; `tests/test_features.py` compares public calls with openpyxl.

Chart classes in `python/crabxl/chart`, their DrawingML descriptors in `drawing/{colors,effect,fill,geometry,line,text}.py` and `worksheet/page.py` are adapted from openpyxl 3.1.5 under the same MIT notice. Chart objects serialize their properties to XML and Rust writes the package. The projected pie serializer preserves the OOXML child order and omits the default split marker for Excel interoperability.
Worksheet view descriptors in `python/crabxl/worksheet/views.py` and the pane layout in `Worksheet.freeze_panes` are adapted from the pinned openpyxl reference's `worksheet/views.py` and `worksheet/worksheet.py`. Copyright (c) 2010–2024 openpyxl, MIT license in `licenses/openpyxl-MIT.txt`. Canonical view parsing, validation and persistence remain in Rust.

The XML descriptor classes in `worksheet/{properties,pagebreak}.py`, `cell/text.py` and `pivot/{cache,table,record,fields}.py` use the same pinned openpyxl 3.1.5 revision and MIT notice. Pivot ZIP-writing methods and package-relationship helpers are excluded from the copied classes. The native bridge creates the canonical pivot graph and writes its relationships, records and shared caches. Public style XML conversion reuses the existing local `styles/_x` descriptors.

The comment XML descriptors in `comments/{author,comment_sheet}.py` use the same pinned reference and MIT notice. Python VML generation is excluded; the native package writer owns comment shapes.

Chartsheet property descriptors in `chartsheet/{custom,properties,protection,publish,views}.py` use the same pinned reference and MIT notice. The native chartsheet graph owns their package persistence.


The style XML descriptors and StyleArray in styles/cell_style.py use the same pinned openpyxl 3.1.5 reference and MIT notice. Native StyleCatalog projects canonical format identities; Python only wraps the returned metadata.

The descriptor modules drawing/{properties,picture,graphic,relation,xdr}, workbook/{properties,views,smart_tags,web}, worksheet/scenario.py and styles/table.py, plus the drawing/drawing.py coordinate adapter, use the same pinned openpyxl 3.1.5 reference and MIT notice. Package and worksheet writers remain native; these modules only construct and serialize metadata.

The standalone content-type, relationship, worksheet drawing-reference and OLE
XML metadata descriptors are also adapted from openpyxl 3.1.5. Archive loading
and workbook package writing remain in the Rust core.

Named-style metadata, built-in style definitions and the standalone styleable
object descriptors in `styles/{named_styles,builtins,styleable}.py` are adapted
from the same pinned openpyxl 3.1.5 reference and MIT notice. Native workbooks
retain canonical ownership of style registration and saved snapshots.

`styles/stylesheet.py` provides the openpyxl stylesheet XML metadata projection.
Workbook archive loading and stylesheet package serialization remain native.

The standalone `workbook/child.py` metadata base and explicit conversions in
`utils/inference.py` use the same pinned reference and MIT notice. Native
worksheet ownership, title changes and cell value inference are unchanged.

`reader/strings.py` adapts the pinned shared-string XML projections. Entry
decoding uses the existing native rich-text codec; workbook shared-string
storage and package loading remain native.

The standalone metadata descriptors in `drawing/connector.py`,
`worksheet/controls.py`, `workbook/{external_reference,function_group}.py`,
`workbook/external_link/external.py`, and `packaging/{extended,workbook}.py`
use the same pinned openpyxl 3.1.5 reference and MIT notice. Explicit caller-owned
ZIP metadata projections use native URI resolution; workbook package discovery,
ownership and persistence remain native.
The standalone chartsheet drawing relationship descriptors in
`chartsheet/relation.py` use the same source and license.

Dimension iteration, representation and explicit XML projections in
`worksheet/dimensions.py` follow the same pinned reference and MIT notice.
Sparse dimension ownership, grouping, validation and style registration remain native.
The abstract file metadata contract in `packaging/interface.py` uses the same
source and license; it does not implement archive loading or writing.
The exposed scanner constants and token-state adapters in `formula/tokenizer.py`
follow the same pinned reference and license. Full and explicit fragment scans
share the Rust quotation, bracket, operator and boundary primitives; formula
tokenization and operand classification remain native.
