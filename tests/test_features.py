"""Features (tables, filters, rules, validation, comments, names) against openpyxl."""

import importlib
from xml.etree.ElementTree import canonicalize

import crabxl
import openpyxl
import pytest


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
