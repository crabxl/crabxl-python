"""One public-API test body runs against both implementations."""

import warnings
import zipfile
from contextlib import nullcontext
from datetime import date, datetime, time, timedelta

import crabxl
import openpyxl
import pytest


@pytest.fixture(params=[openpyxl, crabxl], ids=["openpyxl", "crabxl"])
def engine(request):
    return request.param


def test_alignment_xml_preserves_public_fields(engine):
    from xml.etree.ElementTree import fromstring

    cls = engine.styles.Alignment
    values = dict(
        horizontal="center",
        vertical="top",
        textRotation=45,
        indent=2,
        relativeIndent=1,
        readingOrder=2,
        wrapText=True,
        shrinkToFit=False,
        justifyLastLine=True,
    )
    expected = cls(**values)
    parsed = cls.from_tree(
        fromstring(
            '<alignment horizontal="center" vertical="top" textRotation="45" '
            'indent="2" relativeIndent="1" readingOrder="2" wrapText="1" '
            'shrinkToFit="0" justifyLastLine="1"/>'
        )
    )
    assert parsed == expected
    assert cls.from_tree(parsed.to_tree()) == expected


@pytest.mark.parametrize("edit", ["assign", "append"])
def test_loaded_blank_workbook_accepts_temporal_values(tmp_path, engine, edit):
    path = tmp_path / "empty.xlsx"
    book = engine.Workbook()
    book.save(path)
    book.close()
    book = engine.load_workbook(path)
    values = [
        date(2024, 2, 29),
        datetime(2024, 2, 29, 12, 34, 56),
        time(12, 34, 56),
        timedelta(days=2, seconds=42),
    ]
    if edit == "append":
        book.active.append(values)
    else:
        for column, value in enumerate(values, 1):
            book.active.cell(1, column, value)
    assert list(book.active.values) == [tuple(values)]
    for index in range(2):
        output = tmp_path / f"temporal-{index}.xlsx"
        book.save(output)
        check = openpyxl.load_workbook(output)
        assert list(check.active.values) == [
            (datetime(2024, 2, 29), values[1], values[2], values[3])
        ]
        assert all(cell.data_type == "d" for cell in check.active[1])
        check.close()
    book.close()


@pytest.mark.parametrize("code", ["s", "str"])
def test_append_explicit_rich_cell_keeps_live_value(tmp_path, engine, code):
    from importlib import import_module

    rich = import_module(f"{engine.__name__}.cell.rich_text").CellRichText
    cell_type = import_module(f"{engine.__name__}.cell.cell").Cell
    book = engine.Workbook()
    text = rich(["before"])
    cell = cell_type(book.active, value=text)
    cell.data_type = code
    book.active.append([cell])
    assert book.active["A1"] is cell
    assert cell.value is text
    text.append("after")
    assert str(cell.value) == "beforeafter"
    assert cell.data_type == code
    output = tmp_path / "rich.xlsx"
    book.save(output)
    check = openpyxl.load_workbook(output, rich_text=True)
    assert str(check.active["A1"].value) == "beforeafter"
    assert check.active["A1"].data_type == "s"
    check.close()
    book.close()


@pytest.mark.parametrize("mode", ["new", "loaded", "write_only"])
@pytest.mark.parametrize(
    "original,kind,expected",
    [
        ("=SUM(1,2)", "s", "=SUM(1,2)"),
        ("#N/A", "s", "#N/A"),
        ("12.5", "n", 12.5),
        ("0012", "n", 12),
        ("1", "b", True),
        (0, "b", False),
        (2, "b", True),
        (-1, "b", True),
        ("12", "b", True),
        (12, "str", "12"),
        (True, "str", "1"),
        ("#N/A", "f", "=N/A"),
        (True, "n", 1),
        ("SUM(A1)", "f", "=UM(A1)"),
        ("=A1", "f", "=A1"),
        ("12", "str", "12"),
        ("#DIV/0!", "e", "#DIV/0!"),
        (date(2024, 2, 29), "d", datetime(2024, 2, 29)),
        (None, "s", None),
        (None, "b", None),
        (None, "f", None),
        (None, "e", None),
    ],
)
def test_explicit_cell_types_preserve_values_and_round_trip(
    engine, tmp_path, mode, original, kind, expected
):
    from importlib import import_module

    book = engine.Workbook(write_only=mode == "write_only")
    sheet = book.create_sheet("Data")
    if mode == "loaded":
        source = tmp_path / "source.xlsx"
        book.save(source)
        book.close()
        book = engine.load_workbook(source)
        sheet = book["Data"]
    if mode == "write_only":
        cell = import_module(f"{engine.__name__}.cell.cell").WriteOnlyCell(
            sheet, original
        )
    else:
        cell = sheet["A1"]
        cell.value = original
    cell.data_type = kind
    assert cell.data_type == kind
    assert cell.value == original
    if mode == "write_only":
        sheet.append([cell])
    else:
        assert list(sheet.values) == [(original,)]
    for index in range(1 if mode == "write_only" else 2):
        output = tmp_path / f"output-{index}.xlsx"
        book.save(output)
        result = openpyxl.load_workbook(output)
        try:
            assert result["Data"]["A1"].value == expected
            assert result["Data"]["A1"].data_type == (
                "n" if expected is None else "s" if kind == "str" else kind
            )
        finally:
            result.close()
    book.close()


@pytest.mark.parametrize("kind", ["n", "d", "s", "b", "f", "e"])
def test_assigning_none_resets_explicit_cell_type(engine, kind):
    book = engine.Workbook()
    cell = book.active["A1"]
    cell.data_type = kind
    assert cell.data_type == kind
    cell.value = None
    assert cell.value is None
    assert cell.data_type == "n"
    book.close()


@pytest.mark.parametrize("alternative_cells", [False, True])
@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("data_only", [False, True])
@pytest.mark.parametrize("edit", [False, True])
@pytest.mark.parametrize("materialize", [False, True])
def test_cell_edits_preserve_unrelated_alternatives_and_reject_hidden_cells(
    tmp_path, alternative_cells, nested, data_only, edit, materialize
):
    from xml.etree.ElementTree import canonicalize, fromstring, tostring

    source = tmp_path / "source.xlsx"
    output = tmp_path / "output.xlsx"
    book = openpyxl.Workbook()
    book.active["A1"] = "=1+1"
    book.save(source)
    book.close()
    with zipfile.ZipFile(source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    part = "xl/worksheets/sheet1.xml"
    branch = (
        b'<c r="B1"><f>2+2</f><v>4</v></c>'
        if alternative_cells
        else b'<x:opaque flag="keep"/>'
    )
    alternative = (
        b'<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:x="urn:crabxl:test">'
        b'<mc:Choice Requires="x">'
        + branch
        + b'</mc:Choice><mc:Fallback><x:opaque flag="fallback"/></mc:Fallback></mc:AlternateContent>'
    )
    inserted = b"<controls>" + alternative + b"</controls>" if nested else alternative
    parts[part] = (
        parts[part]
        .replace(b"<v></v>", b"<v>2</v>")
        .replace(b"</worksheet>", inserted + b"</worksheet>")
    )
    expected_alternative = fromstring(parts[part]).find(
        ".//{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
    )
    with zipfile.ZipFile(source, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    output.write_bytes(b"original output")
    book = crabxl.load_workbook(source, data_only=data_only)
    try:
        assert book.active["A1"].value == (2 if data_only else "=1+1")
        if materialize:
            assert book.active["A1"].number_format == "General"
        if edit:
            book.active["A1"] = 3
        if alternative_cells and (edit or data_only):
            with pytest.raises(NotImplementedError, match="alternative cell data"):
                book.save(output)
            assert output.read_bytes() == b"original output"
        else:
            for _ in range(2):
                book.save(output)
                with zipfile.ZipFile(output) as archive:
                    root = fromstring(archive.read(part))
                    actual = root.find(
                        ".//{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
                    )
                    assert canonicalize(
                        tostring(actual), rewrite_prefixes=True
                    ) == canonicalize(
                        tostring(expected_alternative), rewrite_prefixes=True
                    )
                verified = openpyxl.load_workbook(output)
                assert verified.active["A1"].value == (
                    3 if edit else 2 if data_only else "=1+1"
                )
                assert verified.active["A1"].data_type == (
                    "n" if edit or data_only else "f"
                )
                verified.close()
    finally:
        book.close()


@pytest.mark.parametrize("read_only", [False, True])
@pytest.mark.parametrize("stream", [False, True])
def test_public_reader_module_loads_and_preserves_content(
    engine, tmp_path, read_only, stream
):
    from importlib import import_module
    from io import BytesIO

    loader = import_module(f"{engine.__name__}.reader.excel").load_workbook
    assert loader is engine.load_workbook
    source = tmp_path / "source.xlsx"
    original = openpyxl.Workbook()
    original.active.append(["區域", "數量", "公式"])
    original.active.append(["北區", 12, "=B2*2"])
    original.active["B2"].number_format = "0.00"
    original.save(source)
    original.close()
    data = BytesIO(source.read_bytes()) if stream else source
    book = loader(data, read_only=read_only)
    assert list(book.active.values) == [
        ("區域", "數量", "公式"),
        ("北區", 12, "=B2*2"),
    ]
    assert book.active["B2"].number_format == "0.00"
    if not read_only:
        result = tmp_path / "result.xlsx"
        book.save(result)
        check = openpyxl.load_workbook(result)
        assert list(check.active.values) == list(book.active.values)
        assert check.active["B2"].number_format == "0.00"
        check.close()
    book.close()
    if stream:
        assert not data.closed


def test_public_coordinate_utility_exports(engine):
    from importlib import import_module

    utilities = import_module(f"{engine.__name__}.utils")
    cells = import_module(f"{engine.__name__}.utils.cell")
    for index in range(1, 18279):
        name = utilities.get_column_letter(index)
        assert name == cells.get_column_letter(index)
        assert utilities.column_index_from_string(name.lower()) == index
    assert utilities.get_column_letter(18278) == "ZZZ"
    assert utilities.coordinate_to_tuple("ZZZ7") == (7, 18278)
    assert utilities.range_boundaries("ZZA2:ZZZ7") == (18253, 2, 18278, 7)
    for index in (0, -1, 18279):
        with pytest.raises(ValueError):
            utilities.get_column_letter(index)
    for name in ("", "AAAA", "A1", "é"):
        with pytest.raises(ValueError):
            utilities.column_index_from_string(name)


def test_public_style_xml_values_can_be_applied_and_saved(engine, tmp_path):
    from xml.etree.ElementTree import fromstring

    font = engine.styles.Font.from_tree(
        fromstring(
            '<font><name val="Calibri"/><family val="2"/><color theme="1"/><b/></font>'
        )
    )
    fill_module = __import__(
        engine.__name__ + ".styles.fills", fromlist=["Fill", "Stop"]
    )
    fill = fill_module.Fill.from_tree(
        fromstring(
            '<fill><gradientFill><stop position="0"><color rgb="FFFF0000"/></stop>'
            '<stop position="1"><color rgb="FF0000FF"/></stop></gradientFill></fill>'
        )
    )
    assert font.family == 2
    assert font.bold
    assert fill.stop[0].color.rgb == "FFFF0000"
    assert engine.styles.Font.from_tree(font.to_tree()) == font
    with pytest.raises(ValueError):
        fill_module.Stop("FF0000", -0.1)
    book = engine.Workbook()
    try:
        book.active["A1"] = "styled"
        book.active["A1"].font = font
        book.active["A1"].fill = fill
        target = tmp_path / "style-xml.xlsx"
        book.save(target)
    finally:
        book.close()
    verified = openpyxl.load_workbook(target)
    try:
        cell = verified.active["A1"]
        assert cell.font.bold
        assert cell.font.color.theme == 1
        assert cell.fill.stop[0].color.rgb == "FFFF0000"
    finally:
        verified.close()


@pytest.mark.parametrize("loaded", [False, True])
def test_cell_offsets_and_workbook_string_encoding(engine, tmp_path, loaded):
    source = tmp_path / "encoding.xlsx"
    seed = openpyxl.Workbook()
    seed.save(source)
    seed.close()
    book = engine.load_workbook(source) if loaded else engine.Workbook()
    try:
        book.encoding = "latin1"
        sheet = book.active
        sheet["A1"] = "Price £".encode("latin1")
        sheet.append({"B": "Total £".encode("latin1")})
        assert sheet["A1"].offset(2, 1).coordinate == "B3"
        assert sheet["A1"].value == "Price £"
        assert sheet["B2"].value == "Total £"
        assert repr(sheet["A1"]) == "<Cell 'Sheet'.A1>"
        target = tmp_path / "encoded.xlsx"
        book.save(target)
    finally:
        book.close()
    result = openpyxl.load_workbook(target)
    try:
        assert result.active["A1"].value == "Price £"
        assert result.active["B2"].value == "Total £"
    finally:
        result.close()


def test_default_font_isolation_and_color_assignment(engine):
    from copy import copy

    first, second = engine.Workbook(), engine.Workbook()
    try:
        font = copy(first.active["A1"].font)
        font.color = "FF0000"
        first.active["A1"].font = font
        assert first.active["A1"].font.color.rgb == "00FF0000"
        assert second.active["A1"].font.color.index == 1
    finally:
        first.close()
        second.close()


def test_sheet_visibility_and_deferred_active_views(engine, tmp_path):
    cases = {
        2: [(-3, 0, 0), (-1, 0, 0), (1, 1, 0), (10, 10, 0)],
        3: [(-3, -3, 0), (-1, -1, 2), (1, 2, 2), (10, 10, 0)],
    }

    def active_title(book):
        return book.active.title if book.active is not None else None

    def selected_title(index, count):
        return ["A", "B", "C"][:count][index] if -count <= index < count else None

    for count, matrix in cases.items():
        for mode in ["owned", "loaded", "write_only"]:
            for requested, after, read_index in matrix:
                book = engine.Workbook(write_only=mode == "write_only")
                for index, title in enumerate(["A", "B", "C"][:count]):
                    sheet = (
                        book.active
                        if index == 0 and mode != "write_only"
                        else book.create_sheet(title)
                    )
                    sheet.title = title
                    sheet.append([index + 11])
                book["B"].sheet_state = "hidden"
                with pytest.raises(ValueError):
                    book.active = book["B"]
                if mode == "loaded":
                    source = tmp_path / f"source-{count}-{requested}.xlsx"
                    book.save(source)
                    book.close()
                    book = engine.load_workbook(source)
                book.active = requested
                assert active_title(book) == selected_title(requested, count)
                output = tmp_path / f"view-{count}-{mode}-{requested}.xlsx"
                for _ in range(1 if mode == "write_only" else 2):
                    book.save(output)
                    assert active_title(book) == selected_title(after, count)
                    checked = openpyxl.load_workbook(output, read_only=True)
                    assert active_title(checked) == ["A", "B", "C"][read_index]
                    assert checked["B"].sheet_state == "hidden"
                    assert [list(sheet.values) for sheet in checked] == [
                        [(index + 11,)] for index in range(count)
                    ]
                    checked.close()
                read = engine.load_workbook(output, read_only=True)
                assert read["B"].sheet_state == "hidden"
                # Read-only metadata changes affect the view, never source output.
                read["B"].sheet_state = "veryHidden"
                assert read["B"].sheet_state == "veryHidden"
                read.close()
                book.close()

    for loaded in [False, True]:
        book = engine.Workbook()
        book.active.title = "A"
        book.create_sheet("B")
        book["A"].append([11])
        book["B"].append([22])
        if loaded:
            source = tmp_path / "hidden-source.xlsx"
            book.save(source)
            book.close()
            book = engine.load_workbook(source)
        book["A"].sheet_state = "hidden"
        book["B"].sheet_state = "veryHidden"
        output = tmp_path / f"hidden-{loaded}.xlsx"
        with pytest.raises(IndexError):
            book.save(output)
        book["B"].sheet_state = "visible"
        book.save(output)
        assert active_title(book) == "B"
        read = openpyxl.load_workbook(output)
        assert read["A"].sheet_state == "hidden"
        assert read["B"].sheet_state == "visible"
        assert read["B"]["A1"].value == 22
        read.close()
        book.close()

    book = engine.Workbook()
    book.active.sheet_state = "hidden"
    copied = book.copy_worksheet(book.active)
    assert copied.sheet_state == "visible"
    book.remove(copied)
    with pytest.raises(ValueError):
        book.save(tmp_path / "only-hidden.xlsx")
    book.close()


def test_scalar_types_formulas_dimensions_and_live_views(engine):
    workbook = engine.Workbook()
    sheet = workbook.active
    values = [None, True, False, 5, 1.25, " whitespace ", "#DIV/0!", "=1+2"]
    sheet.append(values)
    assert list(sheet.values) == [tuple(values)]
    assert [sheet.cell(1, column).data_type for column in range(1, 9)] == [
        "n",
        "b",
        "b",
        "n",
        "n",
        "s",
        "e",
        "f",
    ]
    cell = sheet["D1"]
    assert sheet["D1"] is cell
    sheet.insert_rows(1, 2)
    assert cell.coordinate == "D3" and cell.value == 5
    sheet.delete_cols(1, 2)
    assert cell.coordinate == "B3" and sheet["B3"] is cell
    sheet.move_range("B3:C3", rows=1, cols=2)
    assert cell.coordinate == "D4" and sheet["D4"] is cell
    del sheet["D4"]
    assert cell.value == 5 and sheet["D4"].value is None
    cell.value = 42
    assert sheet["D4"].value is None


def test_new_save_public_readback_and_repeat(engine, tmp_path):
    workbook = engine.Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet.append(
        [
            True,
            5,
            1.25,
            " text ",
            "#N/A",
            "=SUM(B1:C1)",
            datetime(2020, 2, 29, 12, 3, 4, 123000),
            time(12, 3, 4),
            timedelta(days=2, seconds=3),
        ]
    )
    workbook.create_sheet("Other").append(["second"])
    path = tmp_path / "new.xlsx"
    workbook.save(path)
    book = openpyxl.load_workbook(path)
    assert book.sheetnames == ["Data", "Other"]
    row = tuple(book["Data"].values)[0]
    assert row[:6] == (True, 5, 1.25, " text ", "#N/A", "=SUM(B1:C1)")
    assert row[6:] == (
        datetime(2020, 2, 29, 12, 3, 4, 123000),
        time(12, 3, 4),
        timedelta(days=2, seconds=3),
    )
    book.close()
    workbook.save(tmp_path / "repeat.xlsx")
    assert set(tmp_path.iterdir()) == {path, tmp_path / "repeat.xlsx"}


def test_loaded_numeric_edit_and_sparse_insertion(engine, tmp_path):
    from openpyxl.workbook.defined_name import DefinedName

    source = tmp_path / "source.xlsx"
    original = openpyxl.Workbook()
    original.active.title = "First"
    original.active.append([1, 2, "=A1+B1"])
    original.create_sheet("Second")["A1"] = "=First!A1"
    original.defined_names.add(DefinedName("Pick", attr_text="'First'!$A$1"))
    original.save(source)
    original.close()
    workbook = engine.load_workbook(source)
    second = workbook["Second"]
    second.title = "first"
    assert second.title == "first1"
    assert workbook["first1"] is second
    sheet = workbook.active
    alias = sheet["A1"]
    assert sheet["B1"].value == 2
    sheet.title = 'Renamed<&" \u65b0'
    assert workbook[sheet.title] is sheet
    assert alias.parent is sheet
    with pytest.raises(ValueError):
        sheet.title = "Invalid/Name"
    assert sheet.title == 'Renamed<&" \u65b0'
    sheet["A1"] = 5
    sheet["D5"] = "new"
    assert sheet["A1"].value == 5 and sheet["D5"].value == "new"
    assert alias.value == 5
    assert sheet.max_row == 5 and sheet.max_column == 4
    assert list(sheet.iter_rows(min_row=5, max_row=5, values_only=True)) == [
        (None, None, None, "new")
    ]
    sheet.append({"C": "appended", "D": "=A1+B1"})
    sheet.append([])
    sheet.append([8, True])
    assert sheet["C6"].value == "appended"
    assert sheet["D6"].value == "=A1+B1"
    assert sheet["A8"].value == 8 and sheet["B8"].value is True
    workbook.move_sheet(second, offset=-1)
    assert workbook.active is second
    assert workbook.worksheets == [second, sheet]
    assert alias.parent is sheet and alias.value == 5
    workbook.active = sheet
    output = tmp_path / "output.xlsx"
    workbook.save(output)
    workbook.save(tmp_path / "repeat.xlsx")
    workbook.close()
    verified = openpyxl.load_workbook(output)
    assert verified.sheetnames == ["first1", 'Renamed<&" \u65b0']
    assert verified["first1"]["A1"].value == "=First!A1"
    assert verified.defined_names["Pick"].attr_text == "'First'!$A$1"
    assert verified.active["A1"].value == 5 and verified.active["D5"].value == "new"
    assert verified.active["C1"].value == "=A1+B1"
    assert verified.active["C6"].value == "appended"
    assert verified.active["D6"].value == "=A1+B1"
    assert verified.active["A8"].value == 8 and verified.active["B8"].value is True
    verified.close()

    # Retain one shared loaded workflow for alias coordinates, structural edits,
    # translated formulas, later scalar edits/append, and repeat-save readback.
    workbook = engine.load_workbook(output)
    sheet = workbook.active
    alias = sheet["A1"]
    sheet.insert_rows(1, 2)
    assert alias.coordinate == "A3" and alias.value == 5
    sheet.delete_rows(1, 2)
    sheet.insert_cols(1, 2)
    assert alias.coordinate == "C1" and alias.value == 5
    sheet.delete_cols(1, 2)
    assert alias.coordinate == "A1" and alias.value == 5
    sheet.move_range("C1", rows=2, cols=2, translate=True)
    assert sheet["C1"].value is None
    assert sheet["E3"].value == "=C3+D3"
    deleted = sheet["B1"]
    assert deleted.value == 2
    del sheet["B1"]
    assert deleted.value == 2
    assert sheet["B1"].value is None and sheet["B1"] is not deleted
    sheet["B1"] = 27
    assert deleted.value == 2 and sheet["B1"].value == 27
    del sheet["X100"]
    sheet["D5"] = "after shift"
    sheet.append([9])
    assert sheet["A9"].value == 9
    for filename in ("shifted.xlsx", "shifted-repeat.xlsx"):
        workbook.save(tmp_path / filename)
        verified = openpyxl.load_workbook(tmp_path / filename)
        assert verified.active["A1"].value == 5
        assert verified.active["E3"].value == "=C3+D3"
        assert verified.active["B1"].value == 27
        assert verified.active["D5"].value == "after shift"
        assert verified.active["A9"].value == 9
        assert verified["first1"]["A1"].value == "=First!A1"
        assert verified.defined_names["Pick"].attr_text == "'First'!$A$1"
        verified.close()
    workbook.close()

    # Adding sheets uses the same loaded owner and retains live worksheet views.
    workbook = engine.load_workbook(output)
    original_sheet = workbook.active
    added = workbook.create_sheet("Added", index=0)
    assert workbook.worksheets[0] is added
    added["A1"] = "created"
    added.append([42, "=A1"])
    alias = added["A1"]
    added.insert_rows(1)
    assert alias.coordinate == "A2" and alias.value == "created"
    added.title = 'Added<&"'
    added.sheet_state = "hidden"
    workbook.active = original_sheet
    for filename in ("created.xlsx", "created-repeat.xlsx"):
        workbook.save(tmp_path / filename)
        verified = openpyxl.load_workbook(tmp_path / filename)
        assert verified.sheetnames == ['Added<&"', "first1", 'Renamed<&" \u65b0']
        assert verified['Added<&"'].sheet_state == "hidden"
        assert verified['Added<&"']["A2"].value == "created"
        assert verified['Added<&"']["A3"].value == 42
        assert verified['Added<&"']["B3"].value == "=A1"
        assert verified.active["A1"].value == 5
        assert verified.defined_names["Pick"].attr_text == "'First'!$A$1"
        verified.close()
    copied = workbook.copy_worksheet(original_sheet)
    assert copied["A1"].value == 5 and copied["D5"].value == "new"
    copied["A1"] = 101
    assert original_sheet["A1"].value == 5
    copied.sheet_state = "hidden"
    again = workbook.copy_worksheet(copied)
    assert again.sheet_state == "visible" and again["A1"].value == 101
    workbook.active = again
    for filename in ("copied.xlsx", "copied-repeat.xlsx"):
        workbook.save(tmp_path / filename)
        verified = openpyxl.load_workbook(tmp_path / filename)
        assert verified[copied.title]["A1"].value == 101
        assert verified[original_sheet.title]["A1"].value == 5
        assert verified.active.title == again.title
        assert verified.active["A1"].value == 101
        assert verified[copied.title].sheet_state == "hidden"
        assert verified[again.title].sheet_state == "visible"
        verified.close()
    removed_alias = original_sheet["A1"]
    old_title = original_sheet.title
    workbook.remove(original_sheet)
    assert old_title not in workbook.sheetnames
    assert removed_alias.value == 5
    original_sheet["A1"] = 222
    replacement = workbook.create_sheet(old_title)
    replacement["A1"] = 8
    assert removed_alias.value == 222 and replacement["A1"].value == 8
    workbook.remove(added)
    assert added["A2"].value == "created"
    del workbook[copied.title]
    workbook.active = again
    for filename in ("removed.xlsx", "removed-repeat.xlsx"):
        workbook.save(tmp_path / filename)
        verified = openpyxl.load_workbook(tmp_path / filename)
        assert verified.sheetnames == ["first1", again.title, replacement.title]
        assert verified.active["A1"].value == 101
        assert verified[replacement.title]["A1"].value == 8
        assert verified.defined_names["Pick"].attr_text == "'First'!$A$1"
        verified.close()
    for worksheet in list(workbook.worksheets):
        workbook.remove(worksheet)
    assert workbook.sheetnames == []
    with pytest.raises(IndexError):
        workbook.save(tmp_path / "empty.xlsx")
    workbook.create_sheet("Recovered")["A1"] = 3
    workbook.save(tmp_path / "recovered.xlsx")
    verified = openpyxl.load_workbook(tmp_path / "recovered.xlsx")
    assert verified.sheetnames == ["Recovered"] and verified.active["A1"].value == 3
    verified.close()
    workbook.close()


@pytest.mark.parametrize("loaded", [False, True])
def test_values_iteration_observes_edits_between_rows(engine, loaded, tmp_path):
    workbook = engine.Workbook()
    worksheet = workbook.active
    worksheet.append([1, "first", None])
    worksheet.append([2, "second", "=A2+1"])
    if loaded:
        path = tmp_path / "values.xlsx"
        workbook.save(path)
        workbook.close()
        workbook = engine.load_workbook(path)
        worksheet = workbook.active
    rows = worksheet.iter_rows(max_row=3, max_col=3, values_only=True)
    assert next(rows) == (1, "first", None)
    worksheet["B2"] = "changed"
    worksheet["C3"] = False
    assert next(rows) == (2, "changed", "=A2+1")
    assert next(rows) == (None, None, False)
    assert list(rows) == []
    assert list(
        worksheet.iter_rows(
            min_row=2, max_row=2, min_col=2, max_col=3, values_only=True
        )
    ) == [("changed", "=A2+1")]
    worksheet["F2"] = "tail"
    assert list(
        worksheet.iter_rows(
            min_row=2, max_row=2, min_col=4, max_col=7, values_only=True
        )
    ) == [(None, None, "tail", None)]
    assert list(
        worksheet.iter_rows(
            min_row=4, max_row=4, min_col=4, max_col=7, values_only=True
        )
    ) == [(None, None, None, None)]
    workbook.close()


def test_values_iteration_retains_live_structured_formula_identity(tmp_path):
    from crabxl.worksheet.formula import ArrayFormula

    path = tmp_path / "values-formula.xlsx"
    book = crabxl.Workbook()
    book.active["A1"] = ArrayFormula("A1:A2", "=SUM(B1:B2)")
    book.save(path)
    book.close()
    book = crabxl.load_workbook(path)
    cell = book.active["A1"]
    value = cell.value
    assert (
        next(book.active.iter_rows(max_row=1, max_col=1, values_only=True))[0] is value
    )
    value.text = "=SUM(C1:C2)"
    assert cell.value.text == "=SUM(C1:C2)"
    book.save(path)
    book.close()
    verified = openpyxl.load_workbook(path)
    assert verified.active["A1"].value.text == "=SUM(C1:C2)"
    verified.close()


def test_loaded_formula_data_only(engine, tmp_path):
    source = tmp_path / "formula.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.append(["=1+2"])
    workbook.save(source)
    loaded = engine.load_workbook(source, data_only=True)
    assert loaded.active["A1"].value is None
    loaded.close()


def test_empty_append_cursor_and_dictionary_columns(engine):
    workbook = engine.Workbook()
    sheet = workbook.active
    sheet.append([])
    sheet.append({"C": 3})
    assert sheet["C2"].value == 3
    sheet.delete_rows(1, 2)
    sheet.append([5])
    assert sheet["A1"].value == 5


def test_loaded_style_image_comment_and_unknown_parts_are_preserved(tmp_path):
    from openpyxl.comments import Comment
    from openpyxl.drawing.image import Image as DrawingImage
    from openpyxl.styles import Font
    from openpyxl.workbook.defined_name import DefinedName
    from PIL import Image

    image_path = tmp_path / "image.png"
    Image.new("RGB", (8, 8), "red").save(image_path)
    source = tmp_path / "source.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active["A1"] = 1
    workbook.active["A1"].font = Font(bold=True)
    workbook.active["A1"].comment = Comment("comment", "author")
    workbook.active.add_image(DrawingImage(image_path), "D1")
    workbook.active.defined_names.add(DefinedName("Local", attr_text="Sheet!$A$1"))
    workbook.create_sheet("Other")
    workbook.save(source)
    with zipfile.ZipFile(source, "a") as archive:
        archive.writestr("custom/unknown.xml", '<x xmlns="urn:custom">keep</x>')
    loaded = crabxl.load_workbook(source)
    loaded.active.title = "Renamed"
    # Sheet-local names follow their sheet when sheets move.
    loaded.move_sheet(loaded.active, offset=1)
    assert loaded.sheetnames == ["Other", "Renamed"]
    loaded.move_sheet("Renamed", offset=-1)
    assert loaded.sheetnames == ["Renamed", "Other"]
    cell = loaded.active["A1"]
    loaded.active.insert_rows(1)
    assert loaded.active["A2"] is cell
    loaded.active.move_range("A2", rows=-1)
    assert loaded.active["A1"] is cell
    assert loaded.sheetnames == ["Renamed", "Other"]
    assert cell.coordinate == "A1" and cell.value == 1
    loaded.active["A1"] = 9
    for filename in ("first.xlsx", "second.xlsx"):
        target = tmp_path / filename
        loaded.save(target)
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(target) as saved:
            for name in ("xl/media/image1.png", "xl/styles.xml", "custom/unknown.xml"):
                assert original.read(name) == saved.read(name)
        verified = openpyxl.load_workbook(target)
        assert verified.active.title == "Renamed"
        assert verified.active.defined_names["Local"].attr_text == "Sheet!$A$1"
        assert verified.active["A1"].value == 9
        assert verified.active["A1"].font.bold
        assert verified.active["A1"].comment.text == "comment"
        verified.close()
    loaded.close()


def test_adapter_limits_exact_integers_closed_sources_and_unsupported_operations(
    tmp_path,
):
    workbook = crabxl.Workbook(max_memory_bytes=4096)
    sheet = workbook.active
    sheet["A1"] = 10**100
    assert sheet["A1"].value == 10**100
    with pytest.raises(MemoryError):
        sheet["A1"] = "x" * 8192
    assert sheet["A1"].value == 10**100
    with pytest.raises(TypeError):
        sheet["A1"].font = object()
    sheet.freeze_panes = "A1"
    assert sheet.freeze_panes is None
    streaming = crabxl.Workbook(write_only=True)
    with pytest.raises(NotImplementedError):
        streaming.create_sheet().cell(1, 1)
    streaming.close()
    source = tmp_path / "source.xlsx"
    workbook.save(source)
    loaded = crabxl.load_workbook(source)
    loaded.close()
    with pytest.raises(ValueError, match="closed"):
        loaded.active["A1"].value
    assert len(list(tmp_path.iterdir())) == 1


def test_atomic_new_output_failure_preserves_existing_target(tmp_path):
    target = tmp_path / "target.xlsx"
    target.write_bytes(b"original")
    workbook = crabxl.Workbook()
    # All sheets removed is invalid for the writer. The target must survive.
    workbook.remove(workbook.active)
    with pytest.raises(IndexError):
        workbook.save(target)
    assert target.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [target]


def test_sheet_names_and_order_match(engine):
    workbook = engine.Workbook()
    workbook.create_sheet("Sheet2")
    next_sheet = workbook.create_sheet()
    assert next_sheet.title == "Sheet3"
    next_sheet.title = "Data"
    workbook.create_sheet("data", index=0)
    assert workbook.sheetnames == ["data1", "Sheet", "Sheet2", "Data"]
    assert "Data" in workbook
    assert [sheet.title for sheet in workbook] == workbook.sheetnames
    workbook.remove(workbook["Sheet2"])
    assert workbook.sheetnames == ["data1", "Sheet", "Data"]


@pytest.mark.parametrize(
    "source,expected",
    [
        ("=A1+$B2+C$3+$D$4", "=B2+$B3+D$3+$D$4"),
        ("='A1'!A1+A1!B2", "='A1'!B2+A1!C3"),
        ("=T1[A1]+T2[[#Headers],[B2]]+A1", "=T1[A1]+T2[[#Headers],[B2]]+B2"),
        ('="A1"&"say ""B2"""+A1', '="A1"&"say ""B2"""+B2'),
        ("=LOG10(A1)+SUM(A1:B2:C3)", "=LOG10(B2)+SUM(B2:C3:D4)"),
        ("=XFD1048576", "=XFE1048577"),
        ("=AA1001001001+R1C1+named1", "=AA1001001001+R1C1+named1"),
    ],
)
def test_formula_translation_context(engine, source, expected):
    from importlib import import_module

    translator = import_module(engine.__name__ + ".formula.translate").Translator
    assert translator(source, "A1").translate_formula("B2") == expected


def test_formula_move_translation_and_failure_atomicity(engine):
    from importlib import import_module

    module = import_module(engine.__name__ + ".formula.tokenizer")
    translator = import_module(engine.__name__ + ".formula.translate").Translator
    cases = [
        (
            '=IF(A1>=2,"a""b",#N/A)',
            [
                ("IF(", "FUNC", "OPEN"),
                ("A1", "OPERAND", "RANGE"),
                (">=", "OPERATOR-INFIX", ""),
                ("2", "OPERAND", "NUMBER"),
                (",", "SEP", "ARG"),
                ('"a""b"', "OPERAND", "TEXT"),
                (",", "SEP", "ARG"),
                ("#N/A", "OPERAND", "ERROR"),
                (")", "FUNC", "CLOSE"),
            ],
        ),
        (
            "=-1.2E-3%+TRUE",
            [
                ("-", "OPERATOR-PREFIX", ""),
                ("1.2E-3", "OPERAND", "NUMBER"),
                ("%", "OPERATOR-POSTFIX", ""),
                ("+", "OPERATOR-INFIX", ""),
                ("TRUE", "OPERAND", "LOGICAL"),
            ],
        ),
        ("=A1\nB1", [("\n", "WHITE-SPACE", ""), ("A1B1", "OPERAND", "RANGE")]),
        (
            "={1,2;3,4}",
            [
                ("{", "ARRAY", "OPEN"),
                ("1", "OPERAND", "NUMBER"),
                (",", "SEP", "ARG"),
                ("2", "OPERAND", "NUMBER"),
                (";", "SEP", "ROW"),
                ("3", "OPERAND", "NUMBER"),
                (",", "SEP", "ARG"),
                ("4", "OPERAND", "NUMBER"),
                ("}", "ARRAY", "CLOSE"),
            ],
        ),
    ]
    for source, expected in cases:
        parsed = module.Tokenizer(source)
        assert [(t.value, t.type, t.subtype) for t in parsed.items] == expected
        assert parsed.render() == "=" + "".join(t[0] for t in expected)
    live = translator("=A1+2", "A1")
    assert live.get_tokens() is live.tokenizer.items
    live.get_tokens()[0].value = "B2"
    assert live.translate_formula("B2") == "=C3+2"
    for value, subtype in [
        ("", "RANGE"),
        ("1", "NUMBER"),
        ("NaN", "NUMBER"),
        ("true", "RANGE"),
        ("TRUE", "LOGICAL"),
        ('"text"', "TEXT"),
        ("#N/A", "ERROR"),
    ]:
        token = module.Token.make_operand(value)
        assert (token.value, token.type, token.subtype) == (value, "OPERAND", subtype)
    for value, kind in [("(", "PAREN"), ("SUM(", "FUNC"), ("{", "ARRAY")]:
        token = module.Token.make_subexp(value)
        assert (token.type, token.subtype) == (kind, "OPEN")
        closer = token.get_closer()
        assert (closer.type, closer.subtype) == (kind, "CLOSE")
    for source in ['="text', "='Sheet!A1", "=Table[A1", "=#SPILL!", "=A1#"]:
        with pytest.raises(module.TokenizerError):
            module.Tokenizer(source)
    workbook = engine.Workbook()
    sheet = workbook.active
    sheet["B2"] = "=C3+$D$4"
    sheet.move_range("B2", rows=1, cols=1, translate=True)
    assert sheet["C3"].value == "=D4+$D$4"
    assert sheet["B2"].value is None
    if engine is crabxl:
        sheet["C4"] = "=A1"
        before = tuple(sheet.values)
        with pytest.raises(ValueError):
            sheet.move_range("C3:C4", rows=-1, translate=True)
        assert tuple(sheet.values) == before


def test_active_sheet_creation_and_loaded_catalog_match(engine, tmp_path):
    workbook = engine.Workbook()
    first = workbook.active
    second = workbook.create_sheet("Other")
    first["A1"] = 1
    second["A1"] = 2
    workbook.active = second
    assert workbook.active is second
    path = tmp_path / "active.xlsx"
    workbook.save(path)
    verified = openpyxl.load_workbook(path)
    assert verified.active.title == "Other"
    verified.close()
    loaded = engine.load_workbook(path)
    assert loaded.active.title == "Other" and loaded.active["A1"].value == 2
    loaded.close()


def test_owned_workbook_copy_order_removed_aliases_and_independent_values(
    engine, tmp_path
):
    workbook = engine.Workbook()
    source = workbook.active
    source.title = "Data"
    source.append([1, "text", "=A1+1"])
    source.append([])
    copied = workbook.copy_worksheet(source)
    assert copied.title == "Data Copy"
    assert copied.parent is workbook and copied["C1"].value == "=A1+1"
    copied["A1"] = 7
    assert source["A1"].value == 1
    assert workbook.copy_worksheet(source).title == "Data Copy1"
    workbook.move_sheet(copied, offset=-1)
    assert workbook.sheetnames == ["Data Copy", "Data", "Data Copy1"]
    assert workbook.index(source) == 1
    workbook.active = source
    cell = copied["A1"]
    workbook.remove(copied)
    assert cell.value == 7 and copied["A1"] is cell
    cell.value = 8
    assert copied["A1"].value == 8
    assert workbook.sheetnames == ["Data", "Data Copy1"]
    del workbook["Data Copy1"]
    assert workbook.active is None
    workbook.active = source
    target = tmp_path / "bank.xlsx"
    workbook.save(target)
    verified = openpyxl.load_workbook(target)
    assert verified.sheetnames == ["Data"] and verified.active["A1"].value == 1
    verified.close()
    with pytest.raises(ValueError):
        workbook.copy_worksheet(engine.Workbook().active)


@pytest.mark.parametrize("offset", [-10, -4, -2, -1, 0, 1, 2, 10])
def test_move_sheet_offsets_match_list_insertion(engine, offset):
    workbook = engine.Workbook()
    workbook.create_sheet("B")
    source = workbook.create_sheet("C")
    expected = workbook.worksheets
    old = expected.index(source)
    expected.remove(source)
    expected.insert(old + offset, source)
    workbook.move_sheet("C", offset=offset)
    assert workbook.worksheets == expected


def test_python_bank_aggregate_limit_atomic_copy_and_freed_space():
    budget = 16 * 1024
    workbook = crabxl.Workbook(max_memory_bytes=budget)
    first = workbook.active
    original = "x" * 4096
    first["A1"] = original
    second = workbook.create_sheet("B")
    second["A1"] = 2
    for row in range(2, 1000):
        try:
            second.cell(row, 1, row)
        except MemoryError:
            break
    else:
        pytest.fail("Aggregate workbook limit was not enforced")
    assert workbook._book.charged_bytes() <= budget
    assert not second._native.contains(row - 1, 0)
    before = workbook._book.charged_bytes()
    with pytest.raises(MemoryError):
        workbook.copy_worksheet(first)
    assert workbook.sheetnames == ["Sheet", "B"]
    assert workbook._book.charged_bytes() == before
    with pytest.raises(MemoryError):
        second.insert_rows(1)
    assert first["A1"].value == original
    workbook.remove(first)
    assert first["A1"].value == original
    # Detached models remain caller-owned, outside the bank's allowance.
    second.cell(row, 1, 7)
    assert second.cell(row, 1).value == 7
    first["A1"] = 9
    assert first["A1"].value == 9


def test_native_bank_concurrent_copies_keep_owned_handles_valid():
    from concurrent.futures import ThreadPoolExecutor

    from crabxl._native import NativeBook

    book = NativeBook(10_000_000)
    source = book.create_sheet("Source")
    for row in range(400):
        source.append([("int", str(row))])

    def copies(worker):
        for iteration in range(10):
            copied = book.copy_sheet(source, f"Copy{worker}-{iteration}")
            assert copied.get(0, 0) == ("n", 0)
            assert copied.get(399, 0) == ("n", 399)
            book.remove_sheet(copied)
            assert copied.get(399, 0) == ("n", 399)
        return worker

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(copies, range(4))) == [0, 1, 2, 3]
    assert source.get(399, 0) == ("n", 399)
    assert book.charged_bytes() < 10_000_000


def test_loaded_calculation_chain_edit_removes_derived_parts(engine, tmp_path):
    source = tmp_path / "chain.xlsx"
    book = openpyxl.Workbook()
    book.active.append([1, "=A1+1"])
    book.save(source)
    with zipfile.ZipFile(source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(
        b"</Types>",
        b'<Override PartName="/custom/order.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml"/></Types>',
    )
    parts["xl/_rels/workbook.xml.rels"] = parts["xl/_rels/workbook.xml.rels"].replace(
        b"</Relationships>",
        b'<Relationship Id="chain" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/calcChain" Target="../custom/order.xml"/></Relationships>',
    )
    parts["custom/order.xml"] = (
        b'<calcChain xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><c r="B1" i="1"/></calcChain>'
    )
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    loaded = engine.load_workbook(source)
    loaded.active["A1"] = 7
    for filename in ["chain-edited.xlsx", "chain-repeat.xlsx"]:
        target = tmp_path / filename
        loaded.save(target)
        with zipfile.ZipFile(target) as archive:
            assert "custom/order.xml" not in archive.namelist()
            assert b"calcChain" not in archive.read("[Content_Types].xml")
            assert b"calcChain" not in archive.read("xl/_rels/workbook.xml.rels")
        verified = openpyxl.load_workbook(target)
        assert (
            verified.active["A1"].value == 7 and verified.active["B1"].value == "=A1+1"
        )
        verified.close()
    loaded.close()


@pytest.mark.parametrize(
    "value",
    [
        "_x0041_",
        "_x005F_x0041_",
        "_x005F__x0041_",
        "_x000D_",
        "_xD83D__xDE00_",
        "😀_x005f_<&>\r\n ",
    ],
)
def test_inline_ooxml_looking_literals_preserve_reference_spelling(
    engine, value, tmp_path
):
    book = engine.Workbook()
    book.active["A1"] = value
    assert book.active["A1"].value == value
    target = tmp_path / "literal.xlsx"
    book.save(target)
    checked = openpyxl.load_workbook(target)
    assert checked.active["A1"].value == value
    checked.close()
    own = engine.load_workbook(target)
    assert own.active["A1"].value == value
    own.active["B2"] = value
    own.save(tmp_path / "edited.xlsx")
    own.close()
    checked = openpyxl.load_workbook(tmp_path / "edited.xlsx")
    assert checked.active["A1"].value == checked.active["B2"].value == value
    checked.close()


@pytest.mark.parametrize("value", ["literal", "  a & b  ", "_x005F_x0041_", "", "🦀"])
def test_plain_shared_string_read_edit_and_repeat_save(engine, value, tmp_path):
    from xml.sax.saxutils import escape

    source = tmp_path / "shared-source.xlsx"
    initial = openpyxl.Workbook()
    initial.active["A1"] = "placeholder"
    initial.active["B1"] = "placeholder"
    initial.save(source)
    with zipfile.ZipFile(source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    parts["xl/sharedStrings.xml"] = (
        f'<sst xmlns="{main}" uniqueCount="1"><si><t>{escape(value)}</t></si></sst>'.encode()
    )
    parts["xl/_rels/workbook.xml.rels"] = parts["xl/_rels/workbook.xml.rels"].replace(
        b"</Relationships>",
        f'<Relationship Id="shared" Type="{rel}/sharedStrings" Target="sharedStrings.xml"/></Relationships>'.encode(),
    )
    parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(
        b"</Types>",
        b'<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>',
    )
    parts["xl/worksheets/sheet1.xml"] = (
        f'<worksheet xmlns="{main}"><dimension ref="A1:B1"/><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>0</v></c></row></sheetData></worksheet>'.encode()
    )
    with zipfile.ZipFile(source, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    expected = value.replace("x005F_", "")
    book = engine.load_workbook(source)
    assert list(book.active.values) == [(expected, expected)]
    book.active["A1"] = "changed"
    for index in range(2):
        target = tmp_path / f"shared-edited-{index}.xlsx"
        book.save(target)
        verified = openpyxl.load_workbook(target)
        assert verified.active["A1"].value == "changed"
        # The reference rewrites empty SST text as an absent inline literal.
        # Preserving core saves retain untouched source values instead.
        if value == "" and engine is openpyxl:
            assert verified.active["B1"].value is None
        else:
            assert verified.active["B1"].value == expected
        verified.close()
    book.close()


@pytest.mark.parametrize("location", ["inline", "shared"])
@pytest.mark.parametrize(
    "content,inline,shared",
    [
        (
            '<r><rPr><b/></rPr><t xml:space="preserve">  rich &amp; text </t></r><r><t>tail</t></r>',
            "  rich & text tail",
            "  rich & text tail",
        ),
        ("<r><rPr><b/></rPr><t>_x005F_x0041_</t></r>", "_x005F_x0041_", "_x0041_"),
        (
            "<r><rPr><b/></rPr><t>_x005F</t></r><r><t>_x0041_</t></r>",
            "_x005F_x0041_",
            "_x0041_",
        ),
        (
            '<r><t xml:space="preserve">  </t></r><r><rPr><i/></rPr><t></t></r>',
            "  ",
            "  ",
        ),
    ],
)
def test_default_rich_projection_edit_and_repeated_save(
    engine, location, content, inline, shared, tmp_path
):
    source = tmp_path / "rich-source.xlsx"
    initial = openpyxl.Workbook()
    initial.active["A1"] = initial.active["B1"] = "placeholder"
    initial.save(source)
    with zipfile.ZipFile(source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    if location == "shared":
        parts["xl/sharedStrings.xml"] = (
            f'<sst xmlns="{main}"><si>{content}</si></sst>'.encode()
        )
        parts["xl/_rels/workbook.xml.rels"] = parts[
            "xl/_rels/workbook.xml.rels"
        ].replace(
            b"</Relationships>",
            f'<Relationship Id="shared" Type="{rel}/sharedStrings" Target="sharedStrings.xml"/></Relationships>'.encode(),
        )
        parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(
            b"</Types>",
            b'<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>',
        )

        def cell(address):
            return f'<c r="{address}" t="s"><v>0</v></c>'
    else:

        def cell(address):
            return f'<c r="{address}" t="inlineStr"><is>{content}</is></c>'

    parts["xl/worksheets/sheet1.xml"] = (
        f'<worksheet xmlns="{main}"><dimension ref="A1:B1"/><sheetData><row r="1">{cell("A1")}{cell("B1")}</row></sheetData></worksheet>'.encode()
    )
    with zipfile.ZipFile(source, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    expected = inline if location == "inline" else shared
    book = engine.load_workbook(source, rich_text=False)
    assert list(book.active.values) == [(expected, expected)]
    book.active["A1"] = "changed"
    for index in range(2):
        target = tmp_path / f"rich-edited-{index}.xlsx"
        book.save(target)
        checked = openpyxl.load_workbook(target, rich_text=False)
        assert list(checked.active.values) == [("changed", expected)]
        checked.close()
    book.close()


def test_preserving_rich_runs_is_separate_from_default_text_projection(tmp_path):
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont

    original = CellRichText(
        TextBlock(InlineFont(b=True, color="80445566"), "formatted"), " tail"
    )
    source = tmp_path / "preserving-rich.xlsx"
    reference = openpyxl.Workbook()
    reference.active["A1"] = original
    reference.active["B1"] = 1
    reference.save(source)
    book = crabxl.load_workbook(source)
    assert book.active["A1"].value == "formatted tail"
    book.active["B1"] = 2
    for index in range(2):
        target = tmp_path / f"preserved-{index}.xlsx"
        book.save(target)
        checked = openpyxl.load_workbook(target, rich_text=True)
        assert checked.active["A1"].value == original
        assert checked.active["B1"].value == 2
        checked.close()
    book.close()
    typed = crabxl.load_workbook(source, rich_text=True)
    value = typed.active["A1"].value
    assert str(value) == "formatted tail"
    assert value[0].font.b and value[0].font.color.rgb == "80445566"
    typed.close()


@pytest.mark.parametrize("mac", [False, True], ids=["windows", "mac"])
@pytest.mark.parametrize("data_only", [False, True], ids=["formula", "cached"])
def test_loaded_numeric_dates_time_duration_and_formula_cache(
    engine, tmp_path, mac, data_only
):
    from openpyxl.utils.datetime import CALENDAR_MAC_1904, CALENDAR_WINDOWS_1900

    source = tmp_path / "styled-numeric.xlsx"
    reference = openpyxl.Workbook()
    reference.epoch = CALENDAR_MAC_1904 if mac else CALENDAR_WINDOWS_1900
    sheet = reference.active
    for row, value in enumerate(
        [0, 0.5, 59, 60, 61, -0.5, 2958466, 45292.123456789], 1
    ):
        sheet.cell(row, 1, value).number_format = "yyyy-mm-dd hh:mm:ss.000"
    sheet["B1"] = 1.25
    sheet["B1"].number_format = "[h]:mm:ss.000"
    sheet["B2"] = True
    sheet["B2"].number_format = "yyyy-mm-dd"
    sheet["B3"] = "text"
    sheet["B3"].number_format = "yyyy-mm-dd"
    sheet["C1"] = "=1"
    sheet["C1"].number_format = "yyyy-mm-dd"
    reference.save(source)
    reference.close()
    with zipfile.ZipFile(source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace(
        b"<f>1</f><v></v>", b"<f>1</f><v>61</v>"
    )
    assert b"<f>1</f><v>61</v>" in parts["xl/worksheets/sheet1.xml"]
    with zipfile.ZipFile(source, "w") as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    with pytest.warns(UserWarning) if engine is openpyxl else nullcontext():
        book = engine.load_workbook(source, data_only=data_only)
    sheet = book.active
    assert sheet["A1"].value == time(0)
    assert sheet["A2"].value == time(12)
    assert sheet["A3"].value == (
        datetime(1904, 2, 29) if mac else datetime(1900, 2, 28)
    )
    assert sheet["A4"].value == (datetime(1904, 3, 1) if mac else datetime(1900, 2, 28))
    assert sheet["A5"].value == (datetime(1904, 3, 2) if mac else datetime(1900, 3, 1))
    assert sheet["A6"].value == (
        datetime(1903, 12, 31, 12) if mac else datetime(1899, 12, 29, 12)
    )
    assert sheet["A7"].value == "#VALUE!" and sheet["A7"].data_type == "e"
    assert sheet["A8"].value == (
        datetime(2028, 1, 2, 2, 57, 46, 667000)
        if mac
        else datetime(2024, 1, 1, 2, 57, 46, 667000)
    )
    assert sheet["B1"].value == timedelta(days=1, hours=6)
    assert sheet["B2"].value is True and sheet["B3"].value == "text"
    assert sheet["C1"].value == (sheet["A5"].value if data_only else "=1")
    book.close()


@pytest.mark.parametrize("reference", [openpyxl, crabxl], ids=["openpyxl", "crabxl"])
@pytest.mark.parametrize(
    "format_code,expected",
    [
        ("hh:mm:ss.000", time(2, 57, 46, 667000)),
        ("[h]:mm:ss.000", timedelta(hours=2, minutes=57, seconds=46, milliseconds=667)),
    ],
)
def test_loaded_fractional_clock_duration_baseline_rounding(
    reference, tmp_path, format_code, expected
):
    source = tmp_path / "fractional-clock.xlsx"
    book = openpyxl.Workbook()
    book.active["A1"] = 0.123456789
    book.active["A1"].number_format = format_code
    book.save(source)
    book.close()
    loaded = reference.load_workbook(source)
    try:
        assert loaded.active["A1"].value == expected
    finally:
        loaded.close()


@pytest.mark.parametrize(
    "value",
    [
        datetime(2024, 2, 29, 12, 3, 4, 123456),
        datetime(1899, 12, 31, 12, 0, 0, 123456),
        time(2, 57, 46, 666570),
        timedelta(microseconds=-1),
        timedelta(days=999999999, seconds=86399, microseconds=999999),
    ],
)
def test_literal_date_clock_duration_precision_matches_reference(
    engine, tmp_path, value
):
    book = engine.Workbook()
    book.active["A1"] = value
    assert book.active["A1"].value == value
    assert book.active["A1"].data_type == "d"
    path = tmp_path / "literal-precision.xlsx"
    book.save(path)
    reference = openpyxl.Workbook()
    reference.active["A1"] = value
    expected_path = tmp_path / "expected-precision.xlsx"
    reference.save(expected_path)
    reference.close()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        expected = openpyxl.load_workbook(expected_path)
        loaded = openpyxl.load_workbook(path)
    assert loaded.active["A1"].value == expected.active["A1"].value
    loaded.close()
    expected.close()
    book.close()


@pytest.mark.parametrize("iso", [False, True], ids=["numeric", "iso"])
@pytest.mark.parametrize("mac", [False, True], ids=["windows", "mac"])
def test_date_only_iso_creation_epoch_and_loaded_types(engine, tmp_path, iso, mac):
    from datetime import date

    from openpyxl.utils.datetime import CALENDAR_MAC_1904, CALENDAR_WINDOWS_1900

    book = engine.Workbook(iso_dates=iso)
    assert book.iso_dates == iso
    assert book.epoch == CALENDAR_WINDOWS_1900
    book.epoch = CALENDAR_MAC_1904 if mac else CALENDAR_WINDOWS_1900
    values = (
        date(2024, 2, 29),
        datetime(2024, 2, 29, 12, 3, 4, 123456),
        time(12, 3, 4, 123456),
        timedelta(days=1, hours=6),
    )
    book.active.append(values)
    assert list(book.active.values) == [values]
    assert [book.active.cell(1, column).data_type for column in range(1, 5)] == [
        "d"
    ] * 4
    with pytest.raises(ValueError):
        book.epoch = 1904
    path = tmp_path / "date-mode.xlsx"
    book.save(path)
    loaded = engine.load_workbook(path)
    assert loaded.epoch == book.epoch
    expected = (
        date(2024, 2, 29) if iso else datetime(2024, 2, 29),
        datetime(2024, 2, 29, 12, 3, 4, 123000),
        time(12, 3, 4, 123000),
        timedelta(days=1, hours=6),
    )
    assert list(loaded.active.values) == [expected]
    assert type(loaded.active["A1"].value) is (date if iso else datetime)
    loaded.close()
    book.close()


def test_loaded_date_policy_changes_are_explicit_until_bank_integration(tmp_path):
    path = tmp_path / "loaded-policy.xlsx"
    book = openpyxl.Workbook()
    book.active["A1"] = datetime(2024, 1, 1)
    book.save(path)
    book.close()
    loaded = crabxl.load_workbook(path)
    try:
        with pytest.raises(NotImplementedError):
            loaded.iso_dates = True
        with pytest.raises(NotImplementedError):
            loaded.epoch = datetime(1904, 1, 1)
        assert loaded.iso_dates is False and loaded.epoch == datetime(1899, 12, 30)
    finally:
        loaded.close()


@pytest.mark.parametrize(
    "value, format_code",
    [
        (date(2024, 1, 2), "yyyy-mm-dd"),
        (datetime(2024, 1, 2, 3, 4, 5, 678900), "yyyy-mm-dd h:mm:ss"),
        (time(3, 4, 5, 678900), "h:mm:ss"),
        (timedelta(days=2, seconds=3, microseconds=678900), "[hh]:mm:ss"),
    ],
)
def test_saved_temporal_default_formats_match_public_assignments(
    engine, value, format_code, tmp_path
):
    book = engine.Workbook()
    book.active["A1"] = value
    assert book.active["A1"].value == value
    book.active["A1"].font = engine.styles.Font(name="Temporal appearance", bold=True)
    path = tmp_path / "temporal-format.xlsx"
    book.save(path)
    book.close()
    loaded = openpyxl.load_workbook(path)
    assert loaded.active["A1"].number_format == format_code
    assert loaded.active["A1"].font.name == "Temporal appearance"
    assert loaded.active["A1"].font.bold
    loaded.close()


def test_replacing_temporal_value_retains_format_across_repeated_save(engine, tmp_path):
    # Explicit write-only dates keep the same assigned format after finalization.
    streamed = engine.Workbook(write_only=True)
    stream_sheet = streamed.create_sheet()
    if engine is crabxl:
        from crabxl.cell.cell import WriteOnlyCell
    else:
        from openpyxl.cell.cell import WriteOnlyCell
    stream_date = WriteOnlyCell(stream_sheet, date(2024, 1, 2))
    stream_date.number_format = "General"
    stream_empty = WriteOnlyCell(stream_sheet)
    stream_empty.number_format = "0.0000"
    automatic_date = WriteOnlyCell(stream_sheet, date(2024, 1, 2))
    automatic_date.font = engine.styles.Font(
        name="Stream date",
        bold=True,
        underline="singleAccounting",
        vertAlign="superscript",
    )
    automatic_date.fill = engine.styles.GradientFill(stop=("FF010203", "FF102030"))
    automatic_date.border = engine.styles.Border(
        diagonal=engine.styles.Side(style="double", color="FF123456"), diagonalUp=True
    )
    automatic_date.alignment = engine.styles.Alignment(
        horizontal="right", shrink_to_fit=True
    )
    automatic_date.protection = engine.styles.Protection(locked=False, hidden=True)
    stream_sheet.append([stream_date, 9, stream_empty, automatic_date])
    stream_path = tmp_path / "explicit-stream-format.xlsx"
    streamed.save(stream_path)
    checked = openpyxl.load_workbook(stream_path)
    assert checked.active["A1"].value == 45293
    assert checked.active["A1"].number_format == "General"
    assert checked.active["C1"].value is None
    assert checked.active["C1"].number_format == "0.0000"
    assert checked.active["D1"].value == datetime(2024, 1, 2)
    assert checked.active["D1"].number_format == "yyyy-mm-dd"
    assert checked.active["D1"].font.name == "Stream date"
    assert checked.active["D1"].font.underline == "singleAccounting"
    assert checked.active["D1"].font.vertAlign == "superscript"
    assert checked.active["D1"].fill.stop[1].color.rgb == "FF102030"
    assert checked.active["D1"].border.diagonal.style == "double"
    assert checked.active["D1"].border.diagonalUp
    assert checked.active["D1"].alignment.shrinkToFit
    assert checked.active["D1"].protection.hidden
    readonly = engine.load_workbook(stream_path, read_only=True)
    streamed_cell = next(readonly.active.iter_rows())[3]
    assert streamed_cell.font.name == "Stream date"
    assert streamed_cell.fill.stop[1].color.rgb == "FF102030"
    assert streamed_cell.border.diagonal.style == "double"
    assert streamed_cell.alignment.shrinkToFit
    assert streamed_cell.protection.hidden
    readonly.close()
    checked.close()
    streamed.close()
    # Explicit format edits preserve temporal Python values until save/reload.
    for loaded_mode in (False, True):
        styled = engine.Workbook()
        styled.active["A1"] = date(2024, 1, 2)
        styled.active["B1"] = 12.5
        if loaded_mode:
            source = tmp_path / "styled-source.xlsx"
            styled.save(source)
            styled.close()
            styled = engine.load_workbook(source)
        before = styled.active["A1"].value
        styled.active["A1"].number_format = "General"
        styled.active["B1"].number_format = "0.0000"
        styled.active["C5"].number_format = "0.0000"
        assert styled.active["A1"].value == before
        assert not styled.active["A1"].has_style
        assert styled.active["B1"].number_format == "0.0000"
        assert styled.active["B1"].has_style
        from copy import copy

        style_api = engine.styles
        target = styled.active["B1"]
        target.font = style_api.Font(
            name="Appearance",
            size=13,
            bold=True,
            color=style_api.Color(theme=2, tint=0.2),
        )
        target.fill = style_api.PatternFill(fill_type="solid", fgColor="12abEF")
        target.border = style_api.Border(
            left=style_api.Side(style="thin", color="FF010203")
        )
        target.alignment = style_api.Alignment(horizontal="center", wrap_text=True)
        target.protection = style_api.Protection(locked=False, hidden=True)
        assert target.font.name == "Appearance" and target.font.b
        assert target.number_format == "0.0000"
        with pytest.raises(AttributeError):
            target.font.bold = False
        replacement = copy(target.font)
        replacement.italic = True
        target.font = replacement
        assert target.font.bold and target.font.italic
        replacement.color.tint = 0.3
        target.font = replacement
        assert target.font.color.tint == 0.3
        for index in range(2):
            path = tmp_path / f"restyled-{loaded_mode}-{index}.xlsx"
            styled.save(path)
            verified = openpyxl.load_workbook(path)
            assert verified.active["A1"].value == 45293
            assert type(verified.active["A1"].value) is int
            assert verified.active["A1"].number_format == "General"
            assert verified.active["B1"].value == 12.5
            assert verified.active["B1"].number_format == "0.0000"
            appearance = verified.active["B1"]
            assert appearance.font.name == "Appearance"
            assert appearance.font.bold and appearance.font.italic
            assert appearance.font.color.type == "theme"
            assert appearance.font.color.theme == 2
            assert appearance.font.color.tint == 0.3
            assert appearance.fill.fgColor.rgb == "0012abEF"
            assert appearance.border.left.style == "thin"
            assert appearance.alignment.horizontal == "center"
            assert appearance.alignment.wrapText
            assert not appearance.protection.locked and appearance.protection.hidden
            assert verified.active["C5"].value is None
            assert verified.active["C5"].number_format == "0.0000"
            verified.close()
        alias = styled.active["B1"]
        del styled.active["B1"]
        assert alias.value == 12.5 and alias.number_format == "0.0000"
        assert alias.font.name == "Appearance"
        alias.number_format = "0.00"
        assert alias.number_format == "0.00"
        assert styled.active["B1"].number_format == "General"
        styled.add_named_style(
            engine.styles.NamedStyle(
                name="Detached appearance", font=engine.styles.Font(italic=True)
            )
        )
        alias.style = "Detached appearance"
        assert alias.style == "Detached appearance" and alias.font.italic
        assert styled.active["B1"].value is None
        assert styled.active["B1"].number_format == "General"
        styled.close()
    initial_values = [
        (date(2024, 1, 2), "yyyy-mm-dd"),
        (datetime(2024, 1, 2, 3, 4, 5), "yyyy-mm-dd h:mm:ss"),
        (time(3, 4, 5), "h:mm:ss"),
        (timedelta(days=2, seconds=3), "[hh]:mm:ss"),
    ]
    replacements = [
        date(2024, 2, 3),
        datetime(2024, 2, 3, 4, 5, 6),
        time(4, 5, 6),
        timedelta(days=3, seconds=4),
        42,
    ]
    cases = [
        (initial, code, replacement)
        for initial, code in initial_values
        for replacement in replacements
    ]
    book = engine.Workbook()
    reference = openpyxl.Workbook()
    for row, (initial, _, _) in enumerate(cases, 1):
        book.active.cell(row, 1, initial)
        reference.active.cell(row, 1, initial)
    first = tmp_path / "first.xlsx"
    book.save(first)
    for row, (_, _, replacement) in enumerate(cases, 1):
        book.active.cell(row, 1).value = replacement
        assert book.active.cell(row, 1).value == replacement, cases[row - 1]
        reference.active.cell(row, 1).value = replacement
    expected_path = tmp_path / "expected.xlsx"
    reference.save(expected_path)
    reference.close()
    expected = openpyxl.load_workbook(expected_path)
    expected_values = []
    for row, (_, code, _) in enumerate(cases, 1):
        assert expected.active.cell(row, 1).number_format == code, cases[row - 1]
        expected_values.append(expected.active.cell(row, 1).value)
    expected.close()
    for index in range(2):
        path = tmp_path / f"replaced-{index}.xlsx"
        book.save(path)
        loaded = openpyxl.load_workbook(path)
        for row, (_, code, _) in enumerate(cases, 1):
            cell = loaded.active.cell(row, 1)
            assert cell.number_format == code, cases[row - 1]
            assert cell.value == expected_values[row - 1], cases[row - 1]
        loaded.close()
    original = openpyxl.load_workbook(first)
    for row, (_, code, _) in enumerate(cases, 1):
        assert original.active.cell(row, 1).number_format == code, cases[row - 1]
    original.close()
    book.close()


def test_append_detached_cell_preserves_identity_value_and_style():
    import crabxl
    from crabxl.cell import Cell
    from crabxl.styles import Font

    book = crabxl.Workbook()
    try:
        cell = Cell(None, 1, 1, 25)
        cell.font = Font(bold=True)
        cell.number_format = "0.00"
        book.active.append([])
        book.active.append([cell])
        assert book.active["A2"] is cell
        assert cell.value == 25
        assert cell.font.bold
        assert cell.number_format == "0.00"
        other = book.create_sheet()
        with pytest.raises(ValueError):
            other.append([cell])
        assert other["A1"].value is None
    finally:
        book.close()


@pytest.mark.parametrize("mode", ["normal", "loaded", "write_only"])
def test_named_style_binding_metadata_and_saved_snapshots(engine, tmp_path, mode):
    book = engine.Workbook(write_only=mode == "write_only")
    if mode == "loaded":
        source = tmp_path / "named-source.xlsx"
        book.save(source)
        book.close()
        book = engine.load_workbook(source)
    sheet = book.create_sheet("Styled") if mode == "write_only" else book.active
    style = engine.styles.NamedStyle(
        name="AuditStyle",
        font=engine.styles.Font(name="Arial", color="FF336699"),
        alignment=engine.styles.Alignment(horizontal="center"),
        number_format="0.0000",
    )
    style.bind(book)
    assert style._wb is book
    assert "AuditStyle" not in book.named_styles
    assert style.as_xf().alignment == style.alignment
    assert style.as_name().name == "AuditStyle"
    book.add_named_style(style)
    assert style.as_name().xfId == book.named_styles.index("AuditStyle")

    def append(value):
        if mode == "write_only":
            from importlib import import_module
            cell = import_module(engine.__name__ + ".cell").WriteOnlyCell(sheet, value)
            cell.style = style
            sheet.append([cell])
        else:
            cell = sheet.cell(row=sheet.max_row + 1, column=1, value=value)
            cell.style = style

    append(1.25)
    style.font = engine.styles.Font(name="Courier New", bold=True)
    style.number_format = "0.00"
    append(2.5)
    output = tmp_path / "named-output.xlsx"
    book.save(output)
    book.close()
    result = openpyxl.load_workbook(output)
    try:
        cells = [cell for row in result["Styled" if mode == "write_only" else sheet.title] for cell in row if cell.value is not None]
        assert [cell.value for cell in cells] == [1.25, 2.5]
        assert [cell.font.name for cell in cells] == ["Arial", "Courier New"]
        assert [cell.number_format for cell in cells] == ["0.0000", "0.00"]
        assert all(cell.alignment.horizontal == "center" for cell in cells)
    finally:
        result.close()


@pytest.mark.parametrize("mode", ["normal", "loaded", "write_only"])
def test_all_builtin_named_styles_save_with_reference_appearance(engine, tmp_path, mode):
    from importlib import import_module

    from openpyxl.styles.builtins import styles as reference_styles

    book = engine.Workbook(write_only=mode == "write_only")
    if mode == "loaded":
        source = tmp_path / "builtin-source.xlsx"
        book.save(source)
        book.close()
        book = engine.load_workbook(source)
    sheet = book.create_sheet("Builtins") if mode == "write_only" else book.active
    title = sheet.title
    names = [name for name in reference_styles if name != "Normal"]
    for row, name in enumerate(names, 1):
        if mode == "write_only":
            cell = import_module(engine.__name__ + ".cell").WriteOnlyCell(sheet, name)
            cell.style = name
            sheet.append([cell])
        else:
            cell = sheet.cell(row=row, column=1, value=name)
            cell.style = name
    output = tmp_path / "builtin-output.xlsx"
    book.save(output)
    book.close()
    result = openpyxl.load_workbook(output)
    try:
        for row, name in enumerate(names, 1):
            cell = result[title].cell(row=row, column=1)
            expected = reference_styles[name]
            assert cell.value == name
            for component in ("font", "fill", "border", "alignment", "protection", "number_format"):
                assert getattr(cell, component) == getattr(expected, component), (name, component)
    finally:
        result.close()


@pytest.mark.parametrize("copy_kind", ["copy", "deepcopy"])
def test_named_style_copy_keeps_original_registration_and_format(tmp_path, copy_kind):
    import copy

    book = crabxl.Workbook()
    style = crabxl.styles.NamedStyle(name="Original", number_format="0.0000")
    book.add_named_style(style)
    clone = getattr(copy, copy_kind)(book._named_styles["Original"])
    clone.name = "Cloned"
    clone.font = crabxl.styles.Font(bold=True)
    assert book.named_styles == ["Normal", "Original"]
    assert clone.number_format == "0.0000"
    assert clone._wb is None
    book.add_named_style(clone)
    book.active["A1"] = 1.25
    book.active["A1"].style = "Original"
    book.active["B1"] = 2.5
    book.active["B1"].style = "Cloned"
    output = tmp_path / "copied-named-style.xlsx"
    book.save(output)
    book.close()
    result = openpyxl.load_workbook(output)
    try:
        assert result.active["A1"].style == "Original"
        assert result.active["B1"].style == "Cloned"
        assert result.active["A1"].font.bold is False
        assert result.active["B1"].font.bold is True
        assert result.active["A1"].number_format == result.active["B1"].number_format == "0.0000"
    finally:
        result.close()


@pytest.mark.parametrize("mode", ["normal", "loaded", "write_only"])
@pytest.mark.parametrize("template", [False, True])
def test_calculation_properties_persist_and_can_be_removed(engine, tmp_path, mode, template):
    from importlib import import_module

    cls = import_module(engine.__name__ + ".workbook.properties").CalcProperties
    book = engine.Workbook(write_only=mode == "write_only")
    if mode == "write_only":
        book.create_sheet("Data").append([5])
    else:
        book.active.append([5])
    if mode == "loaded":
        source = tmp_path / "calc-source.xlsx"
        book.save(source)
        book.close()
        book = engine.load_workbook(source)
    assert book.calculation.calcId == 124519
    expected = cls(calcId=42, calcMode="manual", fullCalcOnLoad=False, refMode="R1C1",
                   iterate=True, iterateCount=211, iterateDelta=0.0001,
                   fullPrecision=False, calcCompleted=True, calcOnSave=False,
                   concurrentCalc=False, concurrentManualCount=3, forceFullCalc=False)
    book.calculation = expected
    book.template = template
    output = tmp_path / ("calc-output.xltx" if template else "calc-output.xlsx")
    book.save(output)
    book.close()
    for readonly in (False, True):
        result = engine.load_workbook(output, read_only=readonly)
        try:
            assert dict(result.calculation) == dict(expected)
            assert result.template is template
        finally:
            result.close()
    result = engine.load_workbook(output)
    result.calculation = None
    removed = tmp_path / ("calc-removed.xltx" if template else "calc-removed.xlsx")
    result.save(removed)
    result.close()
    checked = engine.load_workbook(removed)
    try:
        assert checked.calculation is None
    finally:
        checked.close()


def test_loaded_calculation_retains_opaque_attributes_on_repeated_metadata_saves(tmp_path):
    from xml.etree import ElementTree as ET

    source = tmp_path / "calc-opaque-source.xlsx"
    book = openpyxl.Workbook()
    book.save(source)
    book.close()
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    vendor = "urn:crabxl:calculation-test"
    original = source.read_bytes()
    from io import BytesIO

    with zipfile.ZipFile(BytesIO(original)) as incoming, zipfile.ZipFile(source, "w") as outgoing:
        for name in incoming.namelist():
            data = incoming.read(name)
            if name == "xl/workbook.xml":
                root = ET.fromstring(data)
                calc = root.find(f"{{{main}}}calcPr")
                calc.set("xmlns:proof", vendor)
                calc.set("proof:marker", "retain")
                calc.set(f"{{{mc}}}Ignorable", "proof")
                data = ET.tostring(root)
            outgoing.writestr(name, data)
    native = crabxl.load_workbook(source)
    native.calculation.calcMode = "manual"
    native.calculation.fullCalcOnLoad = False
    native.properties.title = "Calculation metadata"
    try:
        for count in (211, 212):
            native.calculation.iterateCount = count
            output = tmp_path / f"calc-opaque-{count}.xlsx"
            native.save(output)
            with zipfile.ZipFile(output) as archive:
                root = ET.fromstring(archive.read("xl/workbook.xml"))
                calculations = root.findall(f"{{{main}}}calcPr")
                assert len(calculations) == 1
                assert calculations[0].get(f"{{{vendor}}}marker") == "retain"
                assert calculations[0].get(f"{{{mc}}}Ignorable") == "proof"
                from crabxl.xml._preserve import (
                    inherit_namespace_context,
                    preserving_fromstring,
                )

                document = preserving_fromstring(archive.read("xl/workbook.xml"))
                calc = document.find(f"{{{main}}}calcPr")
                inherit_namespace_context(calc, document)
                assert calc._ns_bindings["proof"] == vendor
            result = openpyxl.load_workbook(output)
            try:
                assert result.calculation.calcMode == "manual"
                assert result.calculation.fullCalcOnLoad is False
                assert result.calculation.iterateCount == count
                assert result.properties.title == "Calculation metadata"
            finally:
                result.close()
    finally:
        native.close()


@pytest.mark.parametrize("mode", ["normal", "loaded", "write_only"])
@pytest.mark.parametrize("empty", [False, True])
def test_workbook_views_persist_all_fields_and_active_selection(engine, tmp_path, mode, empty):
    from importlib import import_module

    cls = import_module(engine.__name__ + ".workbook.views").BookView
    book = engine.Workbook(write_only=mode == "write_only")
    if mode == "write_only":
        book.create_sheet("One")
    else:
        book.active.title = "One"
    book.create_sheet("Two")
    book.create_sheet("Three")
    if mode == "loaded":
        source = tmp_path / "views-source.xlsx"
        book.save(source)
        book.close()
        book = engine.load_workbook(source)
    book.active = 1
    book.views = [] if empty else [
        cls(visibility="visible", minimized=True, showHorizontalScroll=False,
            showVerticalScroll=False, showSheetTabs=False, xWindow=10, yWindow=20,
            windowWidth=14900, windowHeight=7800, tabRatio=880, firstSheet=1,
            activeTab=2, autoFilterDateGrouping=False),
        cls(visibility="hidden", minimized=False, showHorizontalScroll=True,
            showVerticalScroll=False, showSheetTabs=True, xWindow=100, yWindow=200,
            windowWidth=11000, windowHeight=5000, tabRatio=300, firstSheet=0,
            activeTab=2, autoFilterDateGrouping=False),
    ]
    output = tmp_path / "views-output.xlsx"
    book.save(output)
    expected = [dict(view) for view in book.views]
    if not empty:
        assert book.views[0].activeTab == 1
        assert book.views[1].activeTab == 2
    book.close()
    for readonly in (False, True):
        result = engine.load_workbook(output, read_only=readonly)
        try:
            assert [dict(view) for view in result.views] == expected
            assert result.active.title == ("One" if empty else "Two")
        finally:
            result.close()
    result = engine.load_workbook(output)
    if not empty:
        result.views[0].activeTab = 2
        result.views[1].windowWidth = 17000
    result.properties.title = "View edit"
    second = tmp_path / "views-second.xlsx"
    result.save(second)
    result.close()
    check = engine.load_workbook(second)
    try:
        if not empty:
            assert check.views[0].activeTab == 1
            assert check.views[1].windowWidth == 17000
        else:
            assert check.views == []
    finally:
        check.close()


def test_reordered_workbook_views_keep_their_own_opaque_namespace_metadata(tmp_path):
    from io import BytesIO
    from xml.etree import ElementTree as ET

    from crabxl.xml._preserve import inherit_namespace_context, preserving_fromstring

    source = tmp_path / "opaque-views-source.xlsx"
    book = openpyxl.Workbook()
    book.create_sheet("Second")
    book.views = [type(book.views[0])(windowWidth=10000), type(book.views[0])(windowWidth=20000)]
    book.save(source)
    book.close()
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    vendor = "urn:crabxl:workbook-view-test"
    original = source.read_bytes()
    with zipfile.ZipFile(BytesIO(original)) as incoming, zipfile.ZipFile(source, "w") as outgoing:
        for name in incoming.namelist():
            data = incoming.read(name)
            if name == "xl/workbook.xml":
                root = ET.fromstring(data)
                for view, marker in zip(root.find(f"{{{main}}}bookViews"), ("first", "second")):
                    view.set("xmlns:proof", vendor)
                    view.set("proof:marker", marker)
                    view.set(f"{{{mc}}}Ignorable", "proof")
                data = ET.tostring(root)
            outgoing.writestr(name, data)
    native = crabxl.load_workbook(source)
    native.views.reverse()
    native.views[0].windowWidth = 21000
    native.views[1].windowWidth = 11000
    try:
        for phase in range(2):
            output = tmp_path / f"opaque-views-{phase}.xlsx"
            native.save(output)
            with zipfile.ZipFile(output) as archive:
                root = preserving_fromstring(archive.read("xl/workbook.xml"))
            views = root.find(f"{{{main}}}bookViews")
            inherit_namespace_context(views, root)
            assert [view.get(f"{{{vendor}}}marker") for view in views] == ["second", "first"]
            for view in views:
                inherit_namespace_context(view, views)
                assert view._ns_bindings["proof"] == vendor
            result = openpyxl.load_workbook(output)
            try:
                assert [view.windowWidth for view in result.views] == [21000, 11000]
            finally:
                result.close()
    finally:
        native.close()


@pytest.mark.parametrize("mode", ["normal", "loaded", "write_only"])
@pytest.mark.parametrize("mac_epoch", [False, True])
def test_workbook_code_name_keeps_date_epoch_and_can_be_cleared(engine, tmp_path, mode, mac_epoch):
    from datetime import datetime
    from importlib import import_module

    dates = import_module(engine.__name__ + ".utils.datetime")
    epoch = dates.CALENDAR_MAC_1904 if mac_epoch else dates.CALENDAR_WINDOWS_1900
    book = engine.Workbook(write_only=mode == "write_only")
    book.epoch = epoch
    sheet = book.create_sheet("Data") if mode == "write_only" else book.active
    sheet.append([datetime(2025, 3, 5, 12, 30)])
    if mode == "loaded":
        source = tmp_path / "codename-source.xlsx"
        book.save(source)
        book.close()
        book = engine.load_workbook(source)
    assert book.code_name is None
    book.code_name = "ThisWorkbook_Alpha"
    output = tmp_path / "codename-output.xlsx"
    book.save(output)
    book.close()
    for readonly in (False, True):
        result = engine.load_workbook(output, read_only=readonly)
        try:
            assert result.code_name == "ThisWorkbook_Alpha"
            assert result.epoch == epoch
            assert result.active.cell(1, 1).value == datetime(2025, 3, 5, 12, 30)
        finally:
            result.close()
    result = engine.load_workbook(output)
    result.code_name = None
    cleared = tmp_path / "codename-cleared.xlsx"
    result.save(cleared)
    result.close()
    checked = engine.load_workbook(cleared)
    try:
        assert checked.code_name is None
        assert checked.epoch == epoch
        assert checked.active.cell(1, 1).value == datetime(2025, 3, 5, 12, 30)
    finally:
        checked.close()


def test_empty_write_only_workbook_keeps_workbook_metadata(engine, tmp_path):
    book = engine.Workbook(write_only=True)
    book.code_name = "ThisWorkbook_Empty"
    book.calculation.calcMode = "manual"
    book.views[0].showSheetTabs = False
    output = tmp_path / "empty-workbook-metadata.xlsx"
    book.save(output)
    book.close()
    checked = engine.load_workbook(output)
    try:
        assert checked.sheetnames == ["Sheet"]
        assert checked.code_name == "ThisWorkbook_Empty"
        assert checked.calculation.calcMode == "manual"
        assert checked.views[0].showSheetTabs is False
    finally:
        checked.close()


def test_code_name_edits_keep_opaque_workbook_properties_and_mac_epoch(tmp_path):
    from datetime import datetime
    from io import BytesIO
    from xml.etree import ElementTree as ET

    from crabxl.xml._preserve import inherit_namespace_context, preserving_fromstring

    source = tmp_path / "opaque-workbook-properties.xlsx"
    book = openpyxl.Workbook()
    book.epoch = datetime(1904, 1, 1)
    book.code_name = "SourceBook"
    book.active["A1"] = datetime(2025, 3, 5, 12, 30)
    book.save(source)
    book.close()
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    vendor = "urn:crabxl:workbook-properties-test"
    original = source.read_bytes()
    with zipfile.ZipFile(BytesIO(original)) as incoming, zipfile.ZipFile(source, "w") as outgoing:
        for name in incoming.namelist():
            data = incoming.read(name)
            if name == "xl/workbook.xml":
                root = ET.fromstring(data)
                props = root.find(f"{{{main}}}workbookPr")
                props.set("filterPrivacy", "1")
                props.set("saveExternalLinkValues", "0")
                props.set("xmlns:proof", vendor)
                props.set("proof:marker", "retain")
                props.set(f"{{{mc}}}Ignorable", "proof")
                data = ET.tostring(root)
            outgoing.writestr(name, data)
    native = crabxl.load_workbook(source)
    assert native.code_name == "SourceBook"
    native.properties.title = "Property edit"
    native.views[0].showSheetTabs = False
    try:
        for phase, code_name in enumerate(("ChangedBook", None)):
            native.code_name = code_name
            output = tmp_path / f"opaque-workbook-properties-{phase}.xlsx"
            native.save(output)
            with zipfile.ZipFile(output) as archive:
                root = preserving_fromstring(archive.read("xl/workbook.xml"))
            properties = root.findall(f"{{{main}}}workbookPr")
            assert len(properties) == 1
            props = properties[0]
            inherit_namespace_context(props, root)
            assert props.get("codeName") == code_name
            assert props.get("date1904") == "1"
            assert props.get("filterPrivacy") == "1"
            assert props.get("saveExternalLinkValues") == "0"
            assert props.get(f"{{{vendor}}}marker") == "retain"
            assert props._ns_bindings["proof"] == vendor
            checked = openpyxl.load_workbook(output)
            try:
                assert checked.code_name == code_name
                assert checked.epoch == datetime(1904, 1, 1)
                assert checked.active["A1"].value == datetime(2025, 3, 5, 12, 30)
                assert checked.views[0].showSheetTabs is False
            finally:
                checked.close()
    finally:
        native.close()
