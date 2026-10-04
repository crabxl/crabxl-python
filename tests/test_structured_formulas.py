"""Run structured formula calls against the pinned public reference and adapter."""
from importlib import import_module
import gc
import weakref
import zipfile
import openpyxl
import crabxl
import pytest


@pytest.fixture(params=[openpyxl, crabxl], ids=["openpyxl", "crabxl"])
def engine(request):
    return request.param


@pytest.mark.parametrize("kind", ["array", "table"])
def test_structured_creation_mutation_and_readback(engine, kind, tmp_path):
    module = import_module(engine.__name__ + ".worksheet.formula")
    book = engine.Workbook()
    sheet = book.active
    value = module.ArrayFormula("A1:B2", "=SUM(C1:C2)") if kind == "array" else module.DataTableFormula("A1:B2", dt2D=True, r1="C1", r2="D1")
    sheet["A1"] = value
    assert sheet["A1"].data_type == "f"
    assert vars(sheet["A1"].value) == vars(value)
    attached = sheet["A1"].value
    attached.ref = "$A$1:$B$2"
    if kind == "array":
        attached.text = "=SUM(D1:D2)"
    else:
        attached.r1 = "$D$1"
        attached.del1 = True
    assert vars(sheet["A1"].value) == vars(attached)
    first = tmp_path / "first.xlsx"
    book.save(first)
    book.close()
    loaded = openpyxl.load_workbook(first)
    value = loaded.active["A1"].value
    assert value.ref == "$A$1:$B$2"
    if kind == "array":
        assert value.text == "=SUM(D1:D2)"
    else:
        assert value.r1 == "$D$1"
        assert value.del1 == "1"
    loaded.close()
    loaded = engine.load_workbook(first)
    value = loaded.active["A1"].value
    assert value.ref == "$A$1:$B$2"
    value.ref = "A1:B3"
    second = tmp_path / "second.xlsx"
    loaded.save(second)
    loaded.close()
    check = openpyxl.load_workbook(second)
    assert check.active["A1"].value.ref == "A1:B3"
    check.close()


def test_formula_prefix_is_removed_exactly_once(engine, tmp_path):
    book = engine.Workbook()
    book.active["A1"] = "==1"
    assert book.active["A1"].value == "==1"
    path = tmp_path / "prefix.xlsx"
    book.save(path)
    book.close()
    loaded = engine.load_workbook(path)
    assert loaded.active["A1"].value == "==1"
    loaded.close()


@pytest.mark.parametrize("cached", [False, True])
def test_shared_and_empty_caches_match_public_reference(engine, cached, tmp_path):
    path = tmp_path / "source.xlsx"
    source = openpyxl.Workbook()
    source.save(path)
    source.close()
    with zipfile.ZipFile(path) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    parts["xl/worksheets/sheet1.xml"] = b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="B1"><f t="shared" si="4294967295" ref="A1:D2">B1+$B$2+C3</f><v>0</v></c><c r="D1"><f t="shared" si="4294967295"/><v>1</v></c><c r="E1" t="str"><f>1</f><v/></c></row></sheetData></worksheet>'
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in parts.items():
            archive.writestr(name, payload)
    book = engine.load_workbook(path, data_only=cached)
    assert [book.active[cell].value for cell in ("B1", "D1", "E1")] == ([0, 1, None] if cached else ["=B1+$B$2+C3", "=D1+$B$2+E3", "=1"])
    book.close()


def test_adapter_formula_views_do_not_keep_workbooks_alive():
    from crabxl.worksheet.formula import ArrayFormula
    book = crabxl.Workbook()
    sheet = book.active
    sheet["A1"] = ArrayFormula("A1:B2", "=1")
    value = sheet["A1"].value
    sheet_ref = weakref.ref(sheet)
    book.close()
    del sheet, book
    gc.collect()
    assert sheet_ref() is None
    value.text = "=2"
    assert value.text == "=2"


@pytest.mark.parametrize("flags", [
    {},
    {"dt2D": True, "dtr": False, "del1": False, "del2": True, "r1": "C1", "r2": "D1"},
    {"dt2D": False, "dtr": False, "r1": ""},
    {"dt2D": "0", "dtr": "false", "del1": "0"},
])
def test_all_data_table_properties_match_public_save_reload(engine, flags, tmp_path):
    module = import_module(engine.__name__ + ".worksheet.formula")
    reference = openpyxl.Workbook()
    reference.active["A1"] = openpyxl.worksheet.formula.DataTableFormula(ref="A1:B2", **flags)
    reference_path = tmp_path / "reference.xlsx"
    reference.save(reference_path)
    reference.close()
    check = openpyxl.load_workbook(reference_path)
    expected = vars(check.active["A1"].value)
    check.close()
    book = engine.Workbook()
    book.active["A1"] = module.DataTableFormula(ref="A1:B2", **flags)
    output = tmp_path / "native.xlsx"
    book.save(output)
    book.close()
    loaded = engine.load_workbook(output)
    assert vars(loaded.active["A1"].value) == expected
    loaded.active["A1"].value.ref = "A1:B3"
    edited = tmp_path / "edited.xlsx"
    loaded.save(edited)
    loaded.close()
    check = openpyxl.load_workbook(edited)
    assert vars(check.active["A1"].value) == {**expected, "ref": "A1:B3"}
    check.close()

@pytest.mark.parametrize("content, cached, expected", [
    ('<c r="A1"><f t="future" ref="invalid">1+1</f><v>2</v></c>', True, 2),
    ('<c r="A1" cm="1"><f t="array" ref="A1">_xlfn.SEQUENCE(1)</f><v>7</v></c>', True, 7),
    ('<c r="A1" vm="not-an-index"><v>9</v></c>', False, 9),
])
def test_visible_metadata_and_discarded_formula_semantics(engine, content, cached, expected, tmp_path):
    path = tmp_path / "projected.xlsx"
    original = openpyxl.Workbook()
    original.save(path)
    original.close()
    with zipfile.ZipFile(path) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    parts["xl/worksheets/sheet1.xml"] = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1">' + content + '</row></sheetData></worksheet>').encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in parts.items():
            archive.writestr(name, payload)
    book = engine.load_workbook(path, data_only=cached)
    assert book.active["A1"].value == expected
    book.close()
