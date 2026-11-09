"""A12 openpyxl compatibility: sheet properties, write-only settings and legacy API."""

import importlib
import warnings

import crabxl
import openpyxl
import pytest
from crabxl.cell import WriteOnlyCell
from crabxl.worksheet.datavalidation import DataValidation
from crabxl.worksheet.formula import ArrayFormula


def _apply_sheet_settings(ws):
    ws.sheet_properties.tabColor = "FF00FF00"
    ws.sheet_properties.outlinePr.summaryBelow = False
    ws.sheet_properties.codeName = "Code1"
    ws.sheet_format.defaultRowHeight = 22
    ws.page_setup.fitToPage = True
    ws.freeze_panes = "B2"
    ws.page_setup.orientation = "landscape"


def _sheet_settings(path, name):
    ws = openpyxl.load_workbook(path)[name]
    return (
        ws.sheet_properties.tabColor.rgb,
        ws.sheet_properties.outlinePr.summaryBelow,
        ws.sheet_properties.codeName,
        ws.sheet_format.defaultRowHeight,
        ws.sheet_properties.pageSetUpPr.fitToPage,
        ws.freeze_panes,
        ws.page_setup.orientation,
    )


EXPECTED = ("FF00FF00", False, "Code1", 22.0, True, "B2", "landscape")


def test_sheet_properties_on_new_loaded_and_new_in_loaded_sheets(tmp_path):
    wb = crabxl.Workbook()
    _apply_sheet_settings(wb.active)
    wb.save(tmp_path / "new.xlsx")
    assert _sheet_settings(tmp_path / "new.xlsx", "Sheet") == EXPECTED

    source = openpyxl.Workbook()
    source.active["A1"] = 1
    source.active.sheet_properties.tabColor = "FF0000FF"
    source.save(tmp_path / "source.xlsx")

    loaded = crabxl.load_workbook(tmp_path / "source.xlsx")
    assert loaded.active.sheet_properties.tabColor.rgb == "FF0000FF"
    _apply_sheet_settings(loaded.active)
    loaded.save(tmp_path / "loaded.xlsx")
    assert _sheet_settings(tmp_path / "loaded.xlsx", "Sheet") == EXPECTED

    # A new sheet in a loaded workbook used to lose its views and printing.
    loaded = crabxl.load_workbook(tmp_path / "source.xlsx")
    _apply_sheet_settings(loaded.create_sheet("New"))
    loaded.save(tmp_path / "new_in_loaded.xlsx")
    assert _sheet_settings(tmp_path / "new_in_loaded.xlsx", "New") == EXPECTED

    # Printing-only edits keep the source tab color.
    loaded = crabxl.load_workbook(tmp_path / "source.xlsx")
    loaded.active.page_margins.left = 2.0
    loaded.save(tmp_path / "margins.xlsx")
    assert _sheet_settings(tmp_path / "margins.xlsx", "Sheet")[0] == "FF0000FF"


def test_write_only_sheet_settings_and_features_match_openpyxl(tmp_path):
    def build(module, path):
        def load(name):
            return importlib.import_module(f"{module.__name__}.{name}")

        wb = module.Workbook(write_only=True)
        ws = wb.create_sheet("S")
        rule = load("formatting.rule").CellIsRule
        ws.freeze_panes = "B2"
        ws.sheet_view.zoomScale = 80
        ws.sheet_properties.tabColor = "FF0000"
        ws.page_setup.orientation = "landscape"
        ws.page_margins.left = 1.0
        ws.print_options.gridLines = True
        ws.oddHeader.center.text = "Hi"
        ws.protection.set_password("x")
        ws.auto_filter.ref = "A1:B5"
        ws.merged_cells.add("A1:B1")
        ws.row_breaks.append(load("worksheet.pagebreak").Break(id=3))
        ws.conditional_formatting.add(
            "B2:B5", rule(operator="greaterThan", formula=["1"])
        )
        ws.add_table(load("worksheet.table").Table(displayName="T1", ref="A1:B5"))
        ws.append(["h1", "h2"])
        for index in range(4):
            ws.append([index, index])
        wb.save(path)

    def read(path):
        ws = openpyxl.load_workbook(path)["S"]
        return (
            ws.freeze_panes,
            ws.sheet_view.zoomScale,
            ws.sheet_properties.tabColor.rgb,
            ws.page_setup.orientation,
            ws.page_margins.left,
            ws.print_options.gridLines,
            ws.oddHeader.center.text,
            ws.protection.sheet,
            ws.auto_filter.ref,
            str(ws.merged_cells),
            len(ws.row_breaks.brk),
            len(list(ws.conditional_formatting)),
            list(ws.tables),
            ws.max_row,
        )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        build(openpyxl, tmp_path / "reference.xlsx")
        build(crabxl, tmp_path / "actual.xlsx")
    assert read(tmp_path / "actual.xlsx") == read(tmp_path / "reference.xlsx")


def test_write_only_data_validation_and_late_header_error(tmp_path):
    wb = crabxl.Workbook(write_only=True)
    ws = wb.create_sheet("S")
    dv = DataValidation(type="whole")
    ws.add_data_validation(dv)
    dv.add("A1:A3")
    ws.append([1])
    wb.save(tmp_path / "dv.xlsx")
    loaded = openpyxl.load_workbook(tmp_path / "dv.xlsx")["S"]
    assert len(loaded.data_validations.dataValidation) == 1

    wb = crabxl.Workbook(write_only=True)
    ws = wb.create_sheet("S")
    ws.append([1])
    ws.freeze_panes = "B2"  # The header was written with the first row.
    with pytest.raises(ValueError, match="before rows are appended"):
        wb.save(tmp_path / "late.xlsx")


def test_quote_prefix_and_pivot_button(tmp_path):
    wb = crabxl.Workbook()
    ws = wb.active
    ws["A1"] = "=1"
    ws["A1"].quotePrefix = True
    ws["B1"] = 5
    ws["B1"].pivotButton = True
    assert (ws["A1"].quotePrefix, ws["B1"].pivotButton, ws["B1"].quotePrefix) == (
        True,
        True,
        False,
    )
    wb.save(tmp_path / "flags.xlsx")
    reference = openpyxl.load_workbook(tmp_path / "flags.xlsx").active
    assert reference["A1"].quotePrefix and reference["B1"].pivotButton

    loaded = crabxl.load_workbook(tmp_path / "flags.xlsx")
    assert loaded.active["A1"].quotePrefix
    loaded.active["A2"] = 1
    loaded.active["A2"].quotePrefix = True
    loaded.save(tmp_path / "edited.xlsx")
    assert openpyxl.load_workbook(tmp_path / "edited.xlsx").active["A2"].quotePrefix

    stream = crabxl.Workbook(write_only=True)
    sheet = stream.create_sheet("W")
    cell = WriteOnlyCell(sheet, "x")
    cell.quotePrefix = True
    sheet.append([cell])
    stream.save(tmp_path / "stream.xlsx")
    assert openpyxl.load_workbook(tmp_path / "stream.xlsx")["W"]["A1"].quotePrefix


def test_legacy_workbook_worksheet_and_cell_api():
    wb = crabxl.Workbook()
    ws = wb.active
    ws["C1"] = ArrayFormula("C1:C2", "=SUM(A1:B1)")
    ws.merge_cells("D1:E1")
    assert ws.array_formulae == {"C1": "C1:C2"}
    assert [str(r) for r in ws.merged_cell_ranges] == ["D1:E1"]
    assert ws.path == "/xl/worksheets/sheet1.xml"
    assert ws.encoding == "utf-8" and ws.PAPERSIZE_A4 == "9"
    ws.set_printer_settings(ws.PAPERSIZE_A4, ws.ORIENTATION_LANDSCAPE)
    assert ws.page_setup.orientation == "landscape"
    assert ws["C1"].col_idx == 3 and ws["C1"].base_date == wb.epoch
    assert wb.style_names == ["Normal"] and wb.excel_base_date == wb.epoch
    assert wb.path == "/xl/workbook.xml" and wb.is_template is False
    with pytest.warns(DeprecationWarning):
        assert wb.get_sheet_names() == ["Sheet"]
    with pytest.warns(DeprecationWarning):
        wb.create_named_range("nr", ws, "$A$1")
    assert wb.defined_names["nr"].value == "'Sheet'!$A$1"
    assert wb.vba_archive is None
    wb.vba_archive = True
    assert wb.mime_type.endswith("macroEnabled.main+xml")


def test_scenarios_are_read_kept_edited_and_written(tmp_path):
    from crabxl.worksheet.scenario import InputCells, Scenario, ScenarioList
    from openpyxl.worksheet.scenario import InputCells as RefInput
    from openpyxl.worksheet.scenario import Scenario as RefScenario
    from openpyxl.worksheet.scenario import ScenarioList as RefList

    def names(path):
        ws = openpyxl.load_workbook(path).active
        return [scenario.name for scenario in ws.scenarios.scenario]

    source = openpyxl.Workbook()
    source.active["A1"] = 1
    source.active.scenarios = RefList(
        scenario=[RefScenario(name="Best", inputCells=[RefInput(r="A1", val="10")])]
    )
    source.save(tmp_path / "source.xlsx")

    loaded = crabxl.load_workbook(tmp_path / "source.xlsx")
    assert [s.name for s in loaded.active.scenarios.scenario] == ["Best"]
    loaded.active.insert_rows(1)
    loaded.active.tables  # Touching features must not drop the scenarios.
    loaded.save(tmp_path / "kept.xlsx")
    assert names(tmp_path / "kept.xlsx") == ["Best"]

    loaded = crabxl.load_workbook(tmp_path / "source.xlsx")
    loaded.active.scenarios.scenario.append(
        Scenario(name="Worst", inputCells=[InputCells(r="A1", val="0")])
    )
    loaded.save(tmp_path / "edited.xlsx")
    assert names(tmp_path / "edited.xlsx") == ["Best", "Worst"]

    stream = crabxl.Workbook(write_only=True)
    sheet = stream.create_sheet("S")
    sheet.scenarios = ScenarioList(
        scenario=[Scenario(name="New", inputCells=[InputCells(r="A1", val="1")])]
    )
    sheet.append([1])
    stream.save(tmp_path / "stream.xlsx")
    assert names(tmp_path / "stream.xlsx") == ["New"]


PUBLIC_NAMES = {
    "cell": ["ReadOnlyCell"],
    "cell.cell": [
        "ILLEGAL_CHARACTERS_RE",
        "KNOWN_TYPES",
        "STRING_TYPES",
        "TIME_TYPES",
        "TYPE_BOOL",
        "TYPE_ERROR",
        "TYPE_FORMULA",
        "TYPE_FORMULA_CACHE_STRING",
        "TYPE_INLINE",
        "TYPE_NULL",
        "TYPE_NUMERIC",
        "TYPE_STRING",
        "VALID_TYPES",
    ],
    "drawing": ["Drawing"],
    "styles": [
        "DEFAULT_FONT",
        "Fill",
        "NumberFormatDescriptor",
        "is_builtin",
        "is_date_format",
    ],
    "styles.alignment": ["horizontal_alignments", "vertical_aligments"],
    "styles.borders": ["BORDER_NONE", "BORDER_THIN", "BORDER_MEDIUMDASHDOTDOT"],
    "styles.fills": [
        "FILL_NONE",
        "FILL_SOLID",
        "FILL_PATTERN_GRAY125",
        "fills",
        "StopList",
    ],
    "styles.colors": ["RGB"],
    "utils": ["FORMULAE"],
    "workbook.external_link": ["ExternalLink"],
    "workbook.workbook": ["INTEGER_TYPES"],
}


@pytest.mark.parametrize("module", sorted(PUBLIC_NAMES))
def test_public_module_names_match_openpyxl(module):
    ours = importlib.import_module(f"crabxl.{module}")
    reference = importlib.import_module(f"openpyxl.{module}")
    for name in PUBLIC_NAMES[module]:
        value = getattr(ours, name)
        expected = getattr(reference, name)
        if (
            isinstance(expected, (str, tuple, frozenset, int, type(None)))
            and name != "KNOWN_TYPES"
        ):
            if name != "STRING_TYPES":
                assert value == expected, name
        if name == "ILLEGAL_CHARACTERS_RE":
            assert value.pattern == expected.pattern


def test_missing_file_raises_file_not_found(tmp_path):
    for module in (crabxl, openpyxl):
        with pytest.raises(FileNotFoundError):
            module.load_workbook(tmp_path / "missing.xlsx")
    with pytest.raises(FileNotFoundError):
        crabxl.load_workbook(tmp_path / "missing.xlsx", read_only=True)


def test_border_accepts_legacy_diagonal_direction():
    from crabxl.styles import Border

    assert Border(diagonal_direction=0) == Border()
