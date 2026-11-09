"""Features (tables, filters, rules, validation, comments, names) against openpyxl."""

import importlib
from io import BytesIO
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import canonicalize
from zipfile import ZipFile

import crabxl
import openpyxl
import pytest


@pytest.mark.parametrize(
    "backend",
    [
        pytest.param(
            "openpyxl",
            marks=pytest.mark.xfail(
                strict=True,
                raises=KeyError,
                reason="openpyxl 3.1.5 repeated shared-cache saves reference missing pivotCacheRecords2.xml",
            ),
        ),
        "crabxl",
    ],
)
@pytest.mark.parametrize("mode", ["new", "loaded", "write_only"])
def test_create_pivots_with_shared_cache_and_repeat_save(tmp_path, backend, mode):
    if backend == "openpyxl" and mode == "write_only":
        pytest.skip("openpyxl 3.1.5 write-only worksheets do not support add_pivot")
    engine = importlib.import_module(backend)
    cache_types = importlib.import_module(backend + ".pivot.cache")
    table_types = importlib.import_module(backend + ".pivot.table")
    record_types = importlib.import_module(backend + ".pivot.record")
    fields = importlib.import_module(backend + ".pivot.fields")
    source = tmp_path / "input.xlsx"
    seed = openpyxl.Workbook()
    seed.active.title = "Data"
    for row in [("Category", "Units"), ("North", 12), ("Central", 20), ("South", 15)]:
        seed.active.append(row)
    seed.save(source)
    seed.close()
    book = (
        engine.load_workbook(source)
        if mode == "loaded"
        else engine.Workbook(write_only=mode == "write_only")
    )
    try:
        if mode != "loaded":
            data = book.create_sheet("Data") if mode == "write_only" else book.active
            data.title = "Data"
            for row in [
                ("Category", "Units"),
                ("North", 12),
                ("Central", 20),
                ("South", 15),
            ]:
                data.append(row)
        report = book.create_sheet("Pivot")
        cache = cache_types.CacheDefinition(
            cacheSource=cache_types.CacheSource(
                type="worksheet",
                worksheetSource=cache_types.WorksheetSource(ref="A1:B4", sheet="Data"),
            ),
            cacheFields=[
                cache_types.CacheField(
                    name="Category",
                    sharedItems=cache_types.SharedItems(
                        _fields=[
                            fields.Text(v=value)
                            for value in ["North", "Central", "South"]
                        ]
                    ),
                ),
                cache_types.CacheField(name="Units"),
            ],
            recordCount=3,
            refreshOnLoad=True,
        )
        cache.records = record_types.RecordList(
            r=[
                record_types.Record(
                    _fields=[fields.Index(v=index), fields.Number(v=units)]
                )
                for index, units in enumerate([12, 20, 15])
            ]
        )
        for index, coordinate in enumerate(["A3:B7", "D3:E7"]):
            pivot = table_types.TableDefinition(
                name=f"Summary{index}",
                cacheId=1,
                dataCaption="Total Units",
                location=table_types.Location(
                    ref=coordinate, firstHeaderRow=1, firstDataRow=1, firstDataCol=1
                ),
                pivotFields=[
                    table_types.PivotField(
                        axis="axisRow",
                        items=[table_types.FieldItem(x=value) for value in range(3)]
                        + [table_types.FieldItem(t="default")],
                    ),
                    table_types.PivotField(dataField=True),
                ],
                rowFields=[table_types.RowColField(x=0)],
                rowItems=[
                    table_types.RowColItem(x=[fields.Index(v=value)])
                    for value in range(3)
                ]
                + [table_types.RowColItem(t="grand", x=[fields.Index(v=0)])],
                colItems=[table_types.RowColItem()],
                dataFields=[
                    table_types.DataField(name="Total Units", fld=1, subtotal="sum")
                ],
            )
            pivot.cache = cache
            report.add_pivot(pivot)
        target = tmp_path / "pivots.xlsx"
        book.save(target)
        if mode != "write_only":
            book.save(target)
    finally:
        book.close()
    verified = openpyxl.load_workbook(target)
    try:
        pivots = verified["Pivot"]._pivots
        assert [pivot.name for pivot in pivots] == ["Summary0", "Summary1"]
        assert pivots[0].cacheId == pivots[1].cacheId
        assert pivots[0].cache.records.count == 3
        assert pivots[0].cache.records.r[0]._fields[1].v == 12
        if backend == "crabxl":
            assert pivots[0].cache.cacheFields[1].sharedItems is not None
        assert verified["Data"]["B2"].value == 12
    finally:
        verified.close()
    with ZipFile(target) as archive:
        assert (
            sum(
                name.startswith("xl/pivotCache/pivotCacheDefinition")
                for name in archive.namelist()
            )
            == 1
        )
        assert (
            sum(
                name.startswith("xl/pivotTables/pivotTable")
                for name in archive.namelist()
            )
            == 2
        )


@pytest.mark.parametrize("loaded", [False, True])
def test_printing_properties_and_breaks_round_trip(tmp_path, loaded):
    from crabxl.worksheet.pagebreak import Break

    source = tmp_path / "source.xlsx"
    target = tmp_path / "output.xlsx"
    baseline = openpyxl.Workbook()
    baseline.active["A1"] = "preserved"
    baseline.save(source)
    baseline.close()
    book = crabxl.load_workbook(source) if loaded else crabxl.Workbook()
    try:
        sheet = book.active
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToPage = True
        sheet.page_margins.left = 0.4
        sheet.print_options.horizontalCentered = True
        sheet.row_breaks.append(Break(id=12))
        sheet.col_breaks.append(Break(id=3))
        sheet.freeze_panes = "C4"
        copied = book.copy_worksheet(sheet)
        assert copied.title != sheet.title
        book.save(target)
        book.save(target)
    finally:
        book.close()
    verified = openpyxl.load_workbook(target)
    try:
        sheet = verified.active
        assert sheet.page_setup.orientation == "landscape"
        assert sheet.sheet_properties.pageSetUpPr.fitToPage
        assert sheet.page_margins.left == 0.4
        assert sheet.print_options.horizontalCentered
        assert sheet.row_breaks.brk[0].id == 12
        assert sheet.col_breaks.brk[0].id == 3
        if loaded:
            assert sheet["A1"].value == "preserved"
        copied = verified.worksheets[1]
        assert copied.page_setup.orientation == "landscape"
        assert copied.page_margins.left == 0.4
        assert copied.freeze_panes == "C4"
        assert copied.row_breaks.brk[0].id == 12
    finally:
        verified.close()


@pytest.mark.parametrize("loaded", [False, True])
@pytest.mark.parametrize("coordinate", ["A4", "D1", "D4"])
def test_sheet_views_freeze_and_round_trip(tmp_path, loaded, coordinate):
    path = tmp_path / "views.xlsx"
    reference = openpyxl.Workbook()
    reference.active.sheet_view.zoomScale = 85
    reference.save(path)
    reference.close()
    book = crabxl.load_workbook(path) if loaded else crabxl.Workbook()
    try:
        sheet = book.active
        sheet.freeze_panes = coordinate
        sheet.sheet_view.selection[-1].activeCell = "F6"
        sheet.sheet_view.selection[-1].sqref = "F6:G7"
        sheet.sheet_view.showGridLines = False
        book.save(path)
        book.save(path)
    finally:
        book.close()
    result = openpyxl.load_workbook(path)
    try:
        sheet = result.active
        assert sheet.freeze_panes == coordinate
        assert sheet.sheet_view.selection[-1].activeCell == "F6"
        assert sheet.sheet_view.selection[-1].sqref == "F6:G7"
        assert sheet.show_gridlines is False
        if loaded:
            assert sheet.sheet_view.zoomScale == 85
    finally:
        result.close()


def test_worksheet_indexing_and_empty_defaults_match_openpyxl():
    for backend in (crabxl, openpyxl):
        book = backend.Workbook()
        try:
            sheet = book.active
            assert tuple(sheet.columns) == ()
            sheet["B2"] = 42
            assert sheet["A1":"B2"] == (
                (sheet["A1"], sheet["B1"]),
                (sheet["A2"], sheet["B2"]),
            )
            assert sheet[2] == sheet["2"] == sheet["2:2"]
            assert sheet["B"] == sheet["B:B"]
            sheet.column_dimensions["A"]
            sheet.column_dimensions.group("F", "K")
            assert sheet.column_groups == ["F:K"]
            sheet.print_area = "A1:B2"
            sheet.print_area = None
            assert sheet.print_area == ""
        finally:
            book.close()


@pytest.mark.parametrize("write_only", [False, True])
def test_binary_stream_round_trip(write_only):
    source = BytesIO()
    workbook = crabxl.Workbook(write_only=write_only)
    sheet = workbook.create_sheet() if write_only else workbook.active
    sheet.append(["Value", 42])
    workbook.save(source)
    workbook.close()
    position = source.tell()
    edited = BytesIO(b"\0" * 16384)
    loaded = crabxl.load_workbook(source)
    try:
        assert source.tell() == position
        loaded.active["B1"] = 84
        loaded.save(edited)
    finally:
        loaded.close()
    assert not source.closed and not edited.closed
    assert edited.tell() == len(edited.getbuffer()) < 16384
    verified = openpyxl.load_workbook(edited)
    try:
        assert list(verified.active.values) == [("Value", 84)]
    finally:
        verified.close()
    readonly = crabxl.load_workbook(edited, read_only=True)
    try:
        assert list(readonly.active.values) == [("Value", 84)]
    finally:
        readonly.close()


@pytest.mark.parametrize("backend", ["openpyxl", "crabxl"])
@pytest.mark.parametrize("data_only", [False, True])
def test_unused_external_link_removal_keeps_local_formulas_and_structured_names(
    tmp_path, backend, data_only
):
    from openpyxl.packaging.relationship import Relationship
    from openpyxl.workbook.external_link.external import ExternalBook, ExternalLink

    source = tmp_path / "unused-external.xlsx"
    output = tmp_path / "removed-unused-external.xlsx"
    original = openpyxl.Workbook()
    sheet = original.active
    sheet.append(["Units", "Total"])
    sheet.append([2, "=SUM(A2:A3)"])
    sheet.append([3])
    sheet.add_table(openpyxl.worksheet.table.Table(displayName="Table1", ref="A1:A3"))
    original.defined_names.add(
        openpyxl.workbook.defined_name.DefinedName("Units", attr_text="Table1[Units]")
    )
    original.defined_names.add(
        openpyxl.workbook.defined_name.DefinedName("Literal", attr_text='"[1]Sheet!A1"')
    )
    validation = openpyxl.worksheet.datavalidation.DataValidation(
        type="custom", formula1='A2="[1]!"', sqref="A2:A3"
    )
    sheet.add_data_validation(validation)
    link = ExternalLink(externalBook=ExternalBook(id="rId1"))
    link.file_link = Relationship(
        type="externalLinkPath", Target="unused.xlsx", TargetMode="External"
    )
    original._external_links.append(link)
    original.save(source)
    original.close()
    engine = importlib.import_module(backend)
    loaded = engine.load_workbook(source, keep_links=False, data_only=data_only)
    loaded.active.title = "Renamed"
    loaded.save(output)
    if backend == "crabxl":
        previous = output.read_bytes()
        loaded.active["B2"] = "=[1]Sheet!A1"
        with pytest.raises(NotImplementedError, match="retaining formulas"):
            loaded.save(output)
        assert output.read_bytes() == previous
    loaded.close()
    with ZipFile(output) as archive:
        assert not any(
            name.startswith("xl/externalLinks/") for name in archive.namelist()
        )
    checked = openpyxl.load_workbook(output)
    assert checked.active["B2"].value == (None if data_only else "=SUM(A2:A3)")
    assert checked.defined_names["Units"].attr_text == "Table1[Units]"
    assert checked.defined_names["Literal"].attr_text == '"[1]Sheet!A1"'
    assert checked.active.data_validations.dataValidation[0].formula1 == 'A2="[1]!"'
    checked.close()


@pytest.mark.parametrize("external_rule", [None, "validation", "conditional"])
def test_external_links_can_be_removed_from_cached_value_output(
    tmp_path, external_rule
):
    from crabxl.chart import BarChart, Reference
    from crabxl.workbook.defined_name import DefinedName
    from openpyxl.packaging.relationship import Relationship
    from openpyxl.workbook.external_link.external import ExternalBook, ExternalLink

    source, target = tmp_path / "source.xlsx", tmp_path / "target.xlsx"
    reference = openpyxl.Workbook()
    reference.active["A1"] = "=[1]Sheet!A1"
    if external_rule == "validation":
        rule = openpyxl.worksheet.datavalidation.DataValidation(
            type="list", formula1="[1]Sheet!$A$1", sqref="B1"
        )
        reference.active.add_data_validation(rule)
    if external_rule == "conditional":
        rule = openpyxl.formatting.rule.FormulaRule(formula=["[1]Sheet!$A$1>0"])
        reference.active.conditional_formatting.add("B1", rule)
    link = ExternalLink(externalBook=ExternalBook(id="rId1"))
    link.file_link = Relationship(
        type="externalLinkPath", Target="source-values.xlsx", TargetMode="External"
    )
    reference._external_links.append(link)
    reference.save(source)
    reference.close()
    with ZipFile(source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    part = "xl/worksheets/sheet1.xml"
    parts[part] = parts[part].replace(b"<v></v>", b"<v>42</v>")
    with ZipFile(source, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)

    with pytest.raises(NotImplementedError, match="retaining formulas"):
        crabxl.load_workbook(source, keep_links=False)
    if external_rule:
        target.write_bytes(b"existing output")
        with pytest.raises(NotImplementedError, match="worksheet rule"):
            crabxl.load_workbook(source, data_only=True, keep_links=False)
        assert target.read_bytes() == b"existing output"
        return
    book = crabxl.load_workbook(source, data_only=True, keep_links=False)
    try:
        book.save(target)
        saved = target.read_bytes()
        book.defined_names.add(DefinedName("ExternalValue", attr_text="[1]Sheet!$A$1"))
        with pytest.raises(NotImplementedError, match="defined name"):
            book.save(target)
        assert target.read_bytes() == saved
        del book.defined_names["ExternalValue"]
        chart = BarChart()
        chart.add_data(Reference(book.active, min_col=1, min_row=1, max_row=1))
        chart.series[0].val.numRef.f = "[1]Sheet!$A$1"
        book.active.add_chart(chart)
        with pytest.raises(NotImplementedError, match="chart"):
            book.save(target)
        assert target.read_bytes() == saved
    finally:
        book.close()
    with ZipFile(target) as archive:
        assert not any(
            name.startswith("xl/externalLinks/") for name in archive.namelist()
        )
    result = openpyxl.load_workbook(target)
    try:
        assert result.active["A1"].value == 42
        assert not result._external_links
    finally:
        result.close()


@pytest.fixture
def loaded_pivot_source(tmp_path, separate_sheets):
    from openpyxl.pivot.cache import (
        CacheDefinition,
        CacheField,
        CacheSource,
        SharedItems,
        WorksheetSource,
    )
    from openpyxl.pivot.fields import Index, Number, Text
    from openpyxl.pivot.record import Record, RecordList
    from openpyxl.pivot.table import (
        DataField,
        FieldItem,
        Location,
        PivotField,
        RowColField,
        RowColItem,
        TableDefinition,
    )

    source = tmp_path / "full-pivot-source.xlsx"
    reference = openpyxl.Workbook()
    reference.active.title = "Data"
    for row in [
        ("Region", "Units", "Note", "Count"),
        ("North", 4, "one", 2),
        ("South", 7, "two", 3),
    ]:
        reference.active.append(row)
    cache = CacheDefinition(
        cacheSource=CacheSource(
            type="worksheet", worksheetSource=WorksheetSource(ref="A1:D3", sheet="Data")
        ),
        cacheFields=[
            CacheField(
                name="Region",
                sharedItems=SharedItems(_fields=[Text(v="North"), Text(v="South")]),
            ),
            *[
                CacheField(
                    name=name,
                    sharedItems=SharedItems(
                        containsSemiMixedTypes=False,
                        containsNonDate=False,
                        containsString=False,
                    ),
                )
                for name in ("Units", "Note", "Count")
            ],
        ],
        recordCount=2,
    )
    # Keep openpyxl's cache hash stable while its writer assigns relationships.
    cache.id = "rId1"
    cache.records = RecordList(
        r=[
            Record(_fields=[Index(v=0), Number(v=4), Text(v="one"), Number(v=2)]),
            Record(_fields=[Index(v=1), Number(v=7), Text(v="two"), Number(v=3)]),
        ]
    )
    report = reference.create_sheet("Report")
    for index in range(2):
        if separate_sheets and index:
            report = reference.create_sheet("Other")
        pivot = TableDefinition(
            name=f"Summary{index}",
            cacheId=1,
            dataCaption="Values",
            location=Location(
                ref="A3:B6" if index == 0 or separate_sheets else "D3:E6",
                firstHeaderRow=1,
                firstDataRow=1,
                firstDataCol=1,
            ),
            pivotFields=[
                PivotField(
                    axis="axisRow",
                    items=[FieldItem(x=0), FieldItem(x=1), FieldItem(t="default")],
                ),
                PivotField(dataField=True),
                PivotField(),
                PivotField(),
            ],
            rowFields=[RowColField(x=0)],
            rowItems=[
                RowColItem(x=[Index(v=0)]),
                RowColItem(x=[Index(v=1)]),
                RowColItem(t="grand", x=[Index(v=0)]),
            ],
            colItems=[RowColItem()],
            dataFields=[DataField(name="Total Units", fld=1, subtotal="sum")],
        )
        pivot.cache = cache
        report.add_pivot(pivot)
    reference.save(source)
    reference.close()
    return source


@pytest.mark.parametrize("backend", ["openpyxl", "crabxl"])
@pytest.mark.parametrize("separate_sheets", [False, True])
def test_loaded_pivot_full_objects_and_shared_cache_edits(
    tmp_path, backend, separate_sheets, loaded_pivot_source
):
    source = loaded_pivot_source
    if backend == "crabxl":
        ET.register_namespace("probe", "urn:crabxl:test:pivot-preservation")
        ET.register_namespace(
            "mc", "http://schemas.openxmlformats.org/markup-compatibility/2006"
        )
        with ZipFile(source) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        for name in list(parts):
            if name.startswith(
                ("xl/pivotTables/pivotTable", "xl/pivotCache/pivotCache")
            ) and name.endswith(".xml"):
                root = ET.fromstring(parts[name])
                if "pivotCacheDefinition" in name:
                    for field in root.find("{*}cacheFields"):
                        items = field.find("{*}sharedItems")
                        if items is not None and len(items) == 0:
                            field.remove(items)
                root.set("{urn:crabxl:test:pivot-preservation}keep", name)
                root.set(
                    "{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable",
                    "probe",
                )
                for child in root.iter():
                    if child.tag.rsplit("}", 1)[-1] == "n":
                        child.set("{urn:crabxl:test:pivot-preservation}keep", "number")
                parts[name] = ET.tostring(root)
        with ZipFile(source, "w") as archive:
            for name, payload in parts.items():
                archive.writestr(name, payload)
    engine = importlib.import_module(backend)
    book = engine.load_workbook(source)
    pivots = [pivot for sheet in book.worksheets for pivot in sheet._pivots]
    assert len(pivots) == 2
    assert (pivots[0].cache is pivots[1].cache) == (not separate_sheets)
    cls = importlib.import_module(backend + ".pivot.table").TableDefinition
    assert all(isinstance(pivot, cls) for pivot in pivots)
    pivots[0].name = "EditedSummary"
    pivots[0].dataCaption = "Edited Values"
    pivots[0].grandTotalCaption = "All Regions"
    pivots[0].location.ref = "G3:H6"
    pivots[0].pivotFields[0].showAll = False
    pivots[0].pivotFields[1].name = "Edited Units"
    pivots[0].dataFields[0].subtotal = "average"
    pivots[0].dataFields[0].name = "Average Units"
    pivots[0].cache.refreshOnLoad = True
    pivots[0].cache.cacheFields[1].numFmtId = 2
    pivots[0].cache.records.r[0]._fields[1].v = 9
    if separate_sheets:
        # openpyxl's writer does not update cacheId when edited caches diverge.
        pivots[1].cacheId = 2
    for index in range(1 if backend == "openpyxl" else 2):
        output = tmp_path / f"full-pivot-{index}.xlsx"
        book.save(output)
        check = openpyxl.load_workbook(output)
        actual = [pivot for sheet in check.worksheets for pivot in sheet._pivots]
        assert actual[0].name == "EditedSummary"
        assert actual[0].dataCaption == "Edited Values"
        assert actual[0].grandTotalCaption == "All Regions"
        assert actual[0].location.ref == "G3:H6"
        assert not actual[0].pivotFields[0].showAll
        assert actual[0].pivotFields[1].name == "Edited Units"
        assert actual[0].dataFields[0].subtotal == "average"
        assert actual[0].dataFields[0].name == "Average Units"
        assert (actual[0].cache is actual[1].cache) == (not separate_sheets)
        if separate_sheets:
            assert actual[0].cacheId != actual[1].cacheId
        assert actual[0].cache.refreshOnLoad
        assert actual[0].cache.cacheFields[1].numFmtId == 2
        assert all(
            field.sharedItems is not None for field in actual[0].cache.cacheFields
        )
        assert actual[0].cache.records.r[0]._fields[1].v == 9
        assert actual[0].cache.records.r[0]._fields[0].v == 0
        assert actual[0].cache.records.r[0]._fields[2].v == "one"
        assert actual[0].cache.records.r[0]._fields[3].v == 2
        assert actual[0].cache.records.r[1]._fields[1].v == 7
        check.close()
        if backend == "crabxl":
            with ZipFile(output) as archive:
                for name in archive.namelist():
                    if name.startswith(
                        ("xl/pivotTables/pivotTable", "xl/pivotCache/pivotCache")
                    ) and name.endswith(".xml"):
                        assert (
                            ET.fromstring(archive.read(name)).get(
                                "{urn:crabxl:test:pivot-preservation}keep"
                            )
                            is not None
                        )
                        for child in ET.fromstring(archive.read(name)).iter():
                            if child.tag.rsplit("}", 1)[-1] == "n":
                                assert (
                                    child.get(
                                        "{urn:crabxl:test:pivot-preservation}keep"
                                    )
                                    == "number"
                                )
    if backend == "crabxl":
        from copy import deepcopy

        records = deepcopy(pivots[0].cache.records)
        pivots[0].cache.records = None
        cleared = tmp_path / "cleared-pivot-records.xlsx"
        book.save(cleared)
        check = openpyxl.load_workbook(cleared)
        actual = [pivot for sheet in check.worksheets for pivot in sheet._pivots]
        assert actual[0].cache.records is None
        assert actual[0].cache.recordCount == 0
        if not separate_sheets:
            assert actual[1].cache.records is None
        check.close()
        pivots[0].cache.records = records
        pivots[0].cache.id = "reassigned by the native graph"
        restored = tmp_path / "restored-pivot-records.xlsx"
        book.save(restored)
        check = openpyxl.load_workbook(restored)
        actual = [pivot for sheet in check.worksheets for pivot in sheet._pivots]
        assert actual[0].cache.records.r[0]._fields[1].v == 9
        assert actual[0].cache.recordCount == 2
        check.close()
        if not separate_sheets:
            pivots[0].cache = deepcopy(pivots[0].cache)
            pivots[0].cache.cacheFields[1].numFmtId = 3
            forked = tmp_path / "forked-pivot-cache.xlsx"
            book.save(forked)
            check = openpyxl.load_workbook(forked)
            actual = check["Report"]._pivots
            assert actual[0].cacheId != actual[1].cacheId
            assert actual[0].cache.cacheFields[1].numFmtId == 3
            assert actual[1].cache.cacheFields[1].numFmtId == 2
            check.close()
        original_output = restored.read_bytes()
        pivots[0].cache.cacheFields[1].caption = "Unsupported worksheet caption"
        with pytest.raises(NotImplementedError, match="cache field captions"):
            book.save(restored)
        assert restored.read_bytes() == original_output
        pivots[0].cache.cacheFields[1].caption = None
        book.save(restored)
    book.close()


@pytest.mark.parametrize("backend", ["openpyxl", "crabxl"])
@pytest.mark.parametrize("separate_sheets", [False, True])
def test_added_pivot_reuses_loaded_cache(
    tmp_path, backend, separate_sheets, loaded_pivot_source
):
    from copy import copy, deepcopy

    engine = importlib.import_module(backend)
    book = engine.load_workbook(loaded_pivot_source)
    original = book["Report"]._pivots[0]
    if backend == "crabxl":
        cloned = copy(original)
        assert cloned.cache is not original.cache
        assert cloned.cache.records.r[0]._fields[1].v == 4
        assert copy(original.cache).records is not original.cache.records
        assert copy(original.cache.records).r[0]._fields[1].v == 4
    added = deepcopy(original)
    added.name = "AddedSummary"
    added.location = copy(original.location)
    added.location.ref = "A3:B6" if separate_sheets else "J3:K6"
    added.cache = original.cache
    target = book.create_sheet("New", 0) if separate_sheets else book["Report"]
    target.add_pivot(added)
    original.cache.cacheFields[1].numFmtId = 2
    if separate_sheets:
        book["Other"]._pivots[0].cacheId = 2
    try:
        for number in (9, 10):
            original.cache.records.r[0]._fields[1].v = number
            output = tmp_path / "added-shared-pivot.xlsx"
            book.save(output)
            check = openpyxl.load_workbook(output)
            pivots = {
                pivot.name: pivot
                for sheet in check.worksheets
                for pivot in sheet._pivots
            }
            assert len(pivots) == 3
            assert pivots["AddedSummary"].cacheId == pivots["Summary0"].cacheId
            assert pivots["AddedSummary"].cache.cacheFields[1].numFmtId == 2
            assert pivots["AddedSummary"].cache.records.r[0]._fields[1].v == number
            assert pivots["Summary0"].cache.records.r[0]._fields[1].v == number
            check.close()
    finally:
        book.close()


def test_loaded_pivot_flags_preserve_cache_records(tmp_path):
    from openpyxl.pivot.cache import (
        CacheDefinition,
        CacheField,
        CacheSource,
        WorksheetSource,
    )
    from openpyxl.pivot.fields import Number
    from openpyxl.pivot.record import Record, RecordList
    from openpyxl.pivot.table import Location, PivotField, TableDefinition

    source = tmp_path / "source.xlsx"
    output = tmp_path / "pivot.xlsx"
    reference = openpyxl.Workbook()
    reference.active.append(["Units"])
    reference.active.append([42])
    reference.active["A1"].hyperlink = "https://example.com"
    report = reference.create_sheet("Report")
    cache = CacheDefinition(
        cacheSource=CacheSource(
            type="worksheet",
            worksheetSource=WorksheetSource(ref="A1:A2", sheet="Sheet"),
        ),
        cacheFields=[CacheField(name="Units")],
        recordCount=1,
    )
    cache.records = RecordList(r=[Record(_fields=[Number(v=42)])])
    pivot = TableDefinition(
        name="Summary",
        cacheId=1,
        dataCaption="Values",
        location=Location(
            ref="A3:B5", firstHeaderRow=1, firstDataRow=1, firstDataCol=1
        ),
        pivotFields=[PivotField()],
    )
    pivot.cache = cache
    report.add_pivot(pivot)
    reference.save(source)
    reference.close()
    with ZipFile(source) as archive:
        parts = {part: archive.read(part) for part in archive.namelist()}
    data_part = "xl/worksheets/sheet1.xml"
    parts[data_part] = parts[data_part].replace(
        b"<hyperlink ",
        b'<hyperlink xmlns:xr="http://schemas.microsoft.com/office/spreadsheetml/2014/revision" '
        b'xr:uid="{00000000-0004-0000-0100-000000000000}" ',
    )
    with ZipFile(source, "w") as archive:
        for part, data in parts.items():
            archive.writestr(part, data)

    workbook = crabxl.load_workbook(source)
    try:
        (settings,) = workbook["Report"]._pivots
        assert settings.name == "Summary"
        workbook["Sheet"].title = "Renamed Data"
        settings.cache.cacheSource.worksheetSource.sheet = "Renamed Data"
        settings.rowGrandTotals = False
        settings.showDrill = False
        assert settings.compact and not settings.outline
        settings.compact = settings.compactData = False
        settings.outline = settings.outlineData = True
        workbook.save(output)
        settings.showHeaders = False
        workbook.save(output)
    finally:
        workbook.close()
    with ZipFile(output) as archive:
        assert b'xr:uid="' in archive.read(data_part)
    verified = openpyxl.load_workbook(output)
    try:
        (pivot,) = verified["Report"]._pivots
        assert (
            not pivot.rowGrandTotals and not pivot.showDrill and not pivot.showHeaders
        )
        assert pivot.colGrandTotals
        assert not pivot.compact and not pivot.compactData
        assert pivot.outline and pivot.outlineData
        assert pivot.cache.records.r[0]._fields[0].v == 42
        assert pivot.cache.cacheSource.worksheetSource.sheet == "Renamed Data"
    finally:
        verified.close()


@pytest.mark.parametrize(
    "keep_vba,missing_project", [(False, False), (True, False), (False, True)]
)
@pytest.mark.parametrize("template", [False, True])
def test_loaded_macro_policy(tmp_path, keep_vba, missing_project, template):
    source = tmp_path / "source.xlsm"
    target = (
        tmp_path
        / f"output.{('xlt' if template else 'xls')}{('m' if keep_vba else 'x')}"
    )
    openpyxl.Workbook().save(source)
    with ZipFile(source) as archive:
        parts = {part: archive.read(part) for part in archive.namelist()}
    parts["[Content_Types].xml"] = (
        parts["[Content_Types].xml"]
        .replace(
            b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
            b"application/vnd.ms-excel.sheet.macroEnabled.main+xml",
        )
        .replace(
            b"</Types>",
            b'<Override PartName="/xl/vbaProject.bin" '
            b'ContentType="application/vnd.ms-office.vbaProject"/></Types>',
        )
    )
    rels = "xl/_rels/workbook.xml.rels"
    parts[rels] = parts[rels].replace(
        b"</Relationships>",
        b'<Relationship Id="vba" Target="vbaProject.bin" '
        b'Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject"/>'
        b"</Relationships>",
    )
    if not missing_project:
        parts["xl/vbaProject.bin"] = b"opaque VBA project"
    with ZipFile(source, "w") as archive:
        for part, data in parts.items():
            archive.writestr(part, data)

    workbook = crabxl.load_workbook(source, keep_vba=keep_vba)
    try:
        workbook.active["A1"] = 42
        workbook.template = template
        workbook.properties.title = "Macro policy"
        workbook.save(target)
    finally:
        workbook.close()
    with ZipFile(target) as archive:
        assert ("xl/vbaProject.bin" in archive.namelist()) == keep_vba
        assert (b"macroEnabled" in archive.read("[Content_Types].xml")) == keep_vba
        if keep_vba:
            assert archive.read("xl/vbaProject.bin") == parts["xl/vbaProject.bin"]
        else:
            assert b"vbaProject" not in archive.read(rels)
            assert b"vbaProject" not in archive.read("[Content_Types].xml")
    verified = openpyxl.load_workbook(target)
    try:
        assert verified.active["A1"].value == 42
        assert verified.properties.title == "Macro policy"
        assert verified.template == template
    finally:
        verified.close()


@pytest.mark.parametrize("write_only", [False, True])
def test_template_content_type_and_conversion(tmp_path, write_only):
    template = tmp_path / "template.xltx"
    ordinary = tmp_path / "workbook.xlsx"
    reference = openpyxl.Workbook()
    reference.template = True
    workbook = crabxl.Workbook(write_only=write_only)
    sheet = workbook.create_sheet() if write_only else workbook.active
    sheet.append(["template"])
    workbook.template = True
    assert workbook.mime_type == reference.mime_type
    workbook.save(template)
    workbook.close()

    with ZipFile(template) as archive:
        assert reference.mime_type.encode() in archive.read("[Content_Types].xml")
    loaded = crabxl.load_workbook(template)
    try:
        assert loaded.template and loaded.active["A1"].value == "template"
        loaded.template = False
        loaded.save(ordinary)
    finally:
        loaded.close()
    verified = openpyxl.load_workbook(ordinary)
    try:
        assert not verified.template
        assert verified.active["A1"].value == "template"
    finally:
        verified.close()


def test_data_only_template_save_writes_cached_values(tmp_path):
    source = tmp_path / "source.xltx"
    target = tmp_path / "target.xltx"
    reference = openpyxl.Workbook()
    reference.template = True
    reference.active["A1"] = "=1+1"
    reference.save(source)
    reference.close()
    with ZipFile(source) as archive:
        parts = {part: archive.read(part) for part in archive.namelist()}
    worksheet = "xl/worksheets/sheet1.xml"
    parts[worksheet] = parts[worksheet].replace(b"<v></v>", b"<v>2</v>")
    with ZipFile(source, "w") as archive:
        for part, data in parts.items():
            archive.writestr(part, data)
    workbook = crabxl.load_workbook(source, data_only=True)
    try:
        assert workbook.active["A1"].value == 2
        workbook.active["A2"] = "edit"
        workbook.save(target)
    finally:
        workbook.close()
    verified = openpyxl.load_workbook(target)
    try:
        assert verified.template
        assert list(verified.active.values) == [(2,), ("edit",)]
    finally:
        verified.close()


def test_images_match_openpyxl_and_survive_loaded_feature_edits(tmp_path):
    from crabxl.comments import Comment
    from crabxl.drawing.image import Image
    from openpyxl.drawing.image import Image as ReferenceImage
    from PIL import Image as PillowImage

    picture = tmp_path / "picture.png"
    PillowImage.new("RGB", (8, 6), "blue").save(picture)

    def images(path):
        book = openpyxl.load_workbook(path)
        try:
            return [
                (
                    item.anchor._from.row,
                    item.anchor._from.col,
                    item.anchor.ext.cx,
                    item.anchor.ext.cy,
                    item._data(),
                )
                for item in book.active._images
            ]
        finally:
            book.close()

    reference = openpyxl.Workbook()
    native = crabxl.Workbook()
    source, target = tmp_path / "source.xlsx", tmp_path / "target.xlsx"
    for book, image_type, output in (
        (reference, ReferenceImage, source),
        (native, Image, target),
    ):
        image = image_type(str(picture))
        book.active.add_image(image, "D2")
        image.width = 12
        book.save(output)
        book.close()
    assert images(source) == images(target)

    loaded = crabxl.load_workbook(source)
    try:
        added = Image(picture)
        loaded.active.add_image(added, "F4")
        loaded.save(target)
        added.anchor = "G5"
        loaded.active["A1"].comment = Comment("Preserve images", "QA")
        loaded.save(target)
    finally:
        loaded.close()
    actual = images(target)
    assert len(actual) == 2
    assert actual[0] == images(source)[0]
    assert actual[1][:2] == (4, 6)
    assert actual[1][-1] == picture.read_bytes()


def test_image_anchor_variants_round_trip(tmp_path):
    from crabxl.chart import BarChart, Reference
    from crabxl.drawing.image import Image
    from crabxl.drawing.spreadsheet_drawing import (
        AbsoluteAnchor,
        AnchorClientData,
        AnchorMarker,
        OneCellAnchor,
        TwoCellAnchor,
    )
    from crabxl.drawing.xdr import XDRPoint2D, XDRPositiveSize2D
    from PIL import Image as PillowImage

    picture = BytesIO()
    PillowImage.new("RGB", (8, 6), "blue").save(picture, format="PNG")
    anchors = [
        OneCellAnchor(AnchorMarker(1, 42, 2, 80), XDRPositiveSize2D(600, 400)),
        TwoCellAnchor("oneCell", AnchorMarker(3, 12, 4, 10), AnchorMarker(5, 6, 7, 8)),
        AbsoluteAnchor(XDRPoint2D(150, 300), XDRPositiveSize2D(600, 400)),
    ]
    workbook = crabxl.Workbook()
    workbook.active.append(["Units", 7])
    for anchor in anchors:
        anchor.clientData = AnchorClientData(
            fLocksWithSheet=False, fPrintsWithSheet=True
        )
        workbook.active.add_image(Image(picture), anchor)
        chart = BarChart()
        chart.add_data(Reference(workbook.active, min_col=2, min_row=1, max_row=1))
        workbook.active.add_chart(chart, anchor)
    output = tmp_path / "anchors.xlsx"
    workbook.save(output)
    workbook.close()

    reference = openpyxl.load_workbook(output)
    try:
        actual = {
            type(image.anchor).__name__: image.anchor
            for image in reference.active._images
        }
        assert len(reference.active._charts) == 3
        for chart in reference.active._charts:
            assert chart.anchor.clientData.fLocksWithSheet is False
            assert chart.anchor.clientData.fPrintsWithSheet is True
        for anchor in actual.values():
            assert anchor.clientData.fLocksWithSheet is False
            assert anchor.clientData.fPrintsWithSheet is True
        one = actual["OneCellAnchor"]
        assert (one._from.row, one._from.col, one._from.rowOff, one._from.colOff) == (
            2,
            1,
            80,
            42,
        )
        assert (one.ext.cx, one.ext.cy) == (600, 400)
        two = actual["TwoCellAnchor"]
        assert (two.editAs, two.to.row, two.to.col, two.to.rowOff, two.to.colOff) == (
            "oneCell",
            7,
            5,
            8,
            6,
        )
        absolute = actual["AbsoluteAnchor"]
        assert (absolute.pos.x, absolute.pos.y, absolute.ext.cx, absolute.ext.cy) == (
            150,
            300,
            600,
            400,
        )
    finally:
        reference.close()


def build(m, path):
    """Same public calls on openpyxl (m=openpyxl) and crabxl."""
    imp = lambda name: importlib.import_module(f"{m.__name__}.{name}")  # noqa: E731
    table = imp("worksheet.table")
    rule = imp("formatting.rule")
    dv = imp("worksheet.datavalidation")
    dn = imp("workbook.defined_name")
    prot = imp("workbook.protection")
    custom = imp("packaging.custom")
    comments = imp("comments")
    wb = m.Workbook()
    ws = wb.active
    ws.title = "Data"
    for row in [
        ("name", "value", "flag"),
        ("a", 1, True),
        ("b", 2, False),
        ("c", 3, True),
    ]:
        ws.append(row)
    t = table.Table(displayName="Tbl", ref="A1:C4")
    t.tableStyleInfo = table.TableStyleInfo(
        name="TableStyleMedium9", showRowStripes=True, showFirstColumn=True
    )
    ws.add_table(t)
    ws2 = wb.create_sheet("Filtered")
    for row in [("k", "v"), (1, "x"), (2, "y"), (3, "z")]:
        ws2.append(row)
    ws2.auto_filter.ref = "A1:B4"
    ws2.auto_filter.add_filter_column(0, ["1", "2"])
    ws2.auto_filter.add_sort_condition("B2:B4", descending=True)
    ws.conditional_formatting.add(
        "B2:B4",
        rule.CellIsRule(
            operator="greaterThan",
            formula=["1"],
            font=m.styles.Font(bold=True, color="FF0000"),
            fill=m.styles.PatternFill(bgColor="FFC7CE", fill_type="solid"),
        ),
    )
    ws.conditional_formatting.add(
        "A2:A4", rule.FormulaRule(formula=["ISBLANK(A2)"], stopIfTrue=True)
    )
    ws.conditional_formatting.add(
        "B2:B4",
        rule.ColorScaleRule(
            start_type="min", start_color="FF0000", end_type="max", end_color="00FF00"
        ),
    )
    ws.conditional_formatting.add(
        "B2:B4",
        rule.DataBarRule(
            start_type="num",
            start_value=0,
            end_type="num",
            end_value=10,
            color="638EC6",
        ),
    )
    ws.conditional_formatting.add(
        "B2:B4", rule.IconSetRule("3Arrows", "percent", [0, 33, 67])
    )
    v = dv.DataValidation(type="list", formula1='"x,y,z"', allow_blank=True)
    v.error = "bad"
    ws.add_data_validation(v)
    v.add("C2:C4")
    ws["A2"].comment = comments.Comment("note text", "me", height=100, width=200)
    ws.protection.sheet = True
    ws.protection.password = "secret"
    ws.protection.formatCells = False
    ws.oddHeader.center.text = "Page &P"
    ws.oddFooter.left.text = "left"
    ws.evenHeader.right.text = "even"
    ws.HeaderFooter.differentOddEven = True
    ws.print_area = "A1:C4"
    ws.print_title_rows = "1:1"
    ws.print_title_cols = "A:A"
    wb.defined_names.add(dn.DefinedName("Global1", attr_text="Data!$A$1:$A$4"))
    ws.defined_names.add(dn.DefinedName("Local1", attr_text="Data!$B$1"))
    wb.security = prot.WorkbookProtection(lockStructure=True, workbookPassword="pw")
    wb.properties.title = "Title"
    wb.properties.creator = "someone"
    wb.custom_doc_props.append(custom.StringProperty(name="s", value="text"))
    wb.custom_doc_props.append(custom.IntProperty(name="i", value=7))
    wb.save(path)


def canon(obj):
    if obj is None:
        return None
    from xml.etree.ElementTree import tostring

    element = obj.to_tree()
    if "lxml" in type(element).__module__:
        from lxml.etree import tostring
    if element.tag == "workbookPr":
        element.tag = "workbookProtection"
    return canonicalize(tostring(element).decode())


def normalized(path):
    wb = openpyxl.load_workbook(path)
    out = {}
    for ws in wb.worksheets:
        out[ws.title] = {
            "tables": {t.name: canon(t) for t in ws.tables.values()},
            "auto_filter": canon(ws.auto_filter),
            "cf": [canon(c) for c in ws.conditional_formatting],
            "dv": canon(ws.data_validations)
            if ws.data_validations.dataValidation
            else None,
            "comments": {
                c.coordinate: (
                    c.comment.text,
                    c.comment.author,
                    c.comment.width,
                    c.comment.height,
                )
                for row in ws.iter_rows()
                for c in row
                if c.comment
            },
            "protection": canon(ws.protection),
            "hf": canon(ws.HeaderFooter),
            "print": (ws.print_area, ws.print_title_rows, ws.print_title_cols),
            "names": sorted(ws.defined_names),
        }
    p = wb.properties
    out["wb"] = {
        "names": sorted(wb.defined_names),
        "security": canon(wb.security),
        "props": (p.title, p.creator),
        "custom": [
            (type(x).__name__, x.name, x.value) for x in wb.custom_doc_props.props
        ],
    }
    return out


def clean(value):
    # table and filter ids are assigned by the writer; compare the rest
    return value


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    root = tmp_path_factory.mktemp("features")
    a, b = root / "openpyxl.xlsx", root / "crabxl.xlsx"
    build(openpyxl, a)
    build(crabxl, b)
    return a, b


def test_new_workbook_matches_openpyxl(pair):
    a, b = (normalized(p) for p in pair)
    assert a.keys() == b.keys()
    for key in a:
        assert a[key] == b[key], key


def test_default_properties(tmp_path):
    wb = crabxl.Workbook()
    assert wb.properties.creator == "openpyxl"
    assert wb.properties.created is not None and wb.properties.modified is not None
    path = tmp_path / "p.xlsx"
    wb.save(path)
    assert openpyxl.load_workbook(path).properties.creator == "openpyxl"


def test_import_paths():
    from crabxl.comments import Comment  # noqa: F401
    from crabxl.formatting.formatting import ConditionalFormattingList  # noqa: F401
    from crabxl.formatting.rule import (  # noqa: F401
        CellIsRule,
        ColorScale,
        DataBar,
        IconSet,
        Rule,
    )
    from crabxl.packaging.core import DocumentProperties  # noqa: F401
    from crabxl.worksheet.datavalidation import (  # noqa: F401
        DataValidation,
        DataValidationList,
    )
    from crabxl.worksheet.filters import (  # noqa: F401
        AutoFilter,
        FilterColumn,
        SortState,
    )
    from crabxl.worksheet.header_footer import HeaderFooter  # noqa: F401
    from crabxl.worksheet.protection import SheetProtection  # noqa: F401
    from crabxl.worksheet.table import (  # noqa: F401
        Table,
        TableColumn,
        TableList,
        TableStyleInfo,
    )


def test_protection_hash_matches_openpyxl():
    a, b = openpyxl.Workbook().active, crabxl.Workbook().active
    a.protection.password = b.protection.password = "secret"
    assert a.protection.password == b.protection.password


def test_comment_binding_semantics():
    from crabxl.comments import Comment

    ws = crabxl.Workbook().active
    c = Comment("t", "a")
    ws["A1"].comment = c
    assert c.parent is ws["A1"]
    ws["B1"].comment = c  # bound comments are copied
    assert ws["A1"].comment is c and ws["B1"].comment is not c
    assert ws["B1"].comment.text == "t"
    ws["A1"].comment = None
    assert ws["A1"].comment is None and c.parent is None


def test_duplicate_table_name():
    from crabxl.worksheet.table import Table

    ws = crabxl.Workbook().active
    ws.add_table(Table(displayName="T", ref="A1:B2"))
    with pytest.raises(ValueError):
        ws.add_table(Table(displayName="T", ref="C1:D2"))


def test_write_only_features_not_supported():
    ws = crabxl.Workbook(write_only=True).create_sheet()
    with pytest.raises(NotImplementedError):
        ws.tables


@pytest.fixture(scope="module")
def made_by_openpyxl(pair):
    return pair[0]


def test_read_features_from_openpyxl_file(made_by_openpyxl):
    expected = normalized(made_by_openpyxl)
    wb = crabxl.load_workbook(made_by_openpyxl, read_only=True)
    ws = wb["Data"]
    assert list(ws.tables) == ["Tbl"]
    assert canon(ws.tables["Tbl"]) == expected["Data"]["tables"]["Tbl"]
    assert [canon(c) for c in ws.conditional_formatting] == expected["Data"]["cf"]
    assert canon(ws.protection) == expected["Data"]["protection"]
    assert wb["Filtered"].auto_filter.ref == "A1:B4"
    assert wb.properties.title == "Title"
    assert sorted(wb.defined_names) == expected["wb"]["names"]
    assert [
        (type(x).__name__, x.name, x.value) for x in wb.custom_doc_props.props
    ] == expected["wb"]["custom"]
    wb.close()


def test_loaded_features_match(made_by_openpyxl):
    expected = normalized(made_by_openpyxl)
    wb = crabxl.load_workbook(made_by_openpyxl)
    ws = wb["Data"]
    assert canon(ws.tables["Tbl"]) == expected["Data"]["tables"]["Tbl"]
    assert [canon(c) for c in ws.conditional_formatting] == expected["Data"]["cf"]
    assert ws["A2"].comment.text == "note text"
    assert (ws.print_area, ws.print_title_rows, ws.print_title_cols) == expected[
        "Data"
    ]["print"]
    assert sorted(ws.defined_names) == expected["Data"]["names"]
    assert canon(ws.HeaderFooter) == expected["Data"]["hf"]
    wb.close()


def test_loaded_edit_roundtrip(made_by_openpyxl, tmp_path):
    wb = crabxl.load_workbook(made_by_openpyxl)
    ws = wb["Data"]
    ws.tables["Tbl"].tableStyleInfo.name = "TableStyleLight1"
    ws["A2"].comment.text = "changed"
    ws.conditional_formatting.add(
        "C2:C4",
        crabxl.formatting.rule.FormulaRule(
            formula=["C2"], fill=crabxl.PatternFill(bgColor="00FF00", fill_type="solid")
        ),
    )
    wb.properties.title = "Edited"
    out = tmp_path / "edit.xlsx"
    wb.save(out)
    reloaded = openpyxl.load_workbook(out)
    ws = reloaded["Data"]
    assert ws.tables["Tbl"].tableStyleInfo.name == "TableStyleLight1"
    assert ws["A2"].comment.text == "changed"
    assert len(list(ws.conditional_formatting)) == 3
    assert reloaded.properties.title == "Edited"
    new = [c for c in ws.conditional_formatting if str(c.sqref) == "C2:C4"][0]
    assert new.rules[0].dxf.fill.bgColor.rgb == "0000FF00"


def test_loaded_untouched_features_survive(made_by_openpyxl, tmp_path):
    wb = crabxl.load_workbook(made_by_openpyxl)
    wb["Data"]["E1"] = 1
    out = tmp_path / "plain.xlsx"
    wb.save(out)
    assert (
        normalized(out)["Data"]["tables"]
        == normalized(made_by_openpyxl)["Data"]["tables"]
    )


def test_loaded_created_sheet_features(made_by_openpyxl, tmp_path):
    from crabxl.comments import Comment
    from crabxl.worksheet.datavalidation import DataValidation
    from crabxl.worksheet.table import Table

    wb = crabxl.load_workbook(made_by_openpyxl)
    ws = wb.create_sheet("Created")
    ws.append(["a", "b"])
    ws.append([1, 2])
    ws.add_table(Table(displayName="CreatedTbl", ref="A1:B2"))
    ws["A2"].comment = Comment("new", "me")
    dv = DataValidation(type="whole")
    dv.add("B2")
    ws.add_data_validation(dv)
    ws.print_area = "A1:B2"
    out = tmp_path / "created.xlsx"
    wb.save(out)
    reloaded = openpyxl.load_workbook(out)
    created = reloaded["Created"]
    assert list(created.tables) == ["CreatedTbl"]
    assert created["A2"].comment.text == "new"
    assert len(created.data_validations.dataValidation) == 1
    assert created.print_area == "'Created'!$A$1:$B$2"
    assert "Tbl" in reloaded["Data"].tables


def test_loaded_cells_after_feature_access(made_by_openpyxl):
    reference = openpyxl.load_workbook(made_by_openpyxl)["Data"]
    expected = [
        (cell.coordinate, cell.value, cell.comment.text if cell.comment else None)
        for row in reference.iter_rows()
        for cell in row
    ]
    wb = crabxl.load_workbook(made_by_openpyxl)
    ws = wb["Data"]
    assert len(ws.tables) == len(reference.tables)
    assert [
        (cell.coordinate, cell.value, cell.comment.text if cell.comment else None)
        for row in ws.iter_rows()
        for cell in row
    ] == expected
