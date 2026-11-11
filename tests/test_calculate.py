"""Workbook.save(calculate=True) stores formula results as cached values."""

import crabxl
import openpyxl
import pytest


def _cached(path, coordinate):
    return openpyxl.load_workbook(path, data_only=True).active[coordinate].value


def test_new_workbook_saves_formula_results(tmp_path):
    wb = crabxl.Workbook()
    ws = wb.active
    ws["A1"] = 2
    ws["A2"] = 3.5
    ws["B1"] = "=SUM(A1:A2)*2"
    ws["B2"] = '="x"&A1'
    path = tmp_path / "new.xlsx"
    wb.save(path, calculate=True)
    assert _cached(path, "B1") == 11
    assert _cached(path, "B2") == "x2"
    assert openpyxl.load_workbook(path).active["B1"].value == "=SUM(A1:A2)*2"


def test_loaded_workbook_saves_results_of_edited_inputs(tmp_path):
    source = tmp_path / "source.xlsx"
    wb = crabxl.Workbook()
    wb.active["A1"] = 2
    wb.active["B1"] = "=A1*3"
    wb.save(source, calculate=True)

    wb = crabxl.load_workbook(source)
    wb.active["A1"] = 5
    plain = tmp_path / "plain.xlsx"
    wb.save(plain)
    calculated = tmp_path / "calculated.xlsx"
    wb.save(calculated, calculate=True)

    assert _cached(source, "B1") == 6
    assert _cached(plain, "B1") is None
    assert _cached(calculated, "B1") == 15


def test_write_only_workbooks_cannot_calculate(tmp_path):
    wb = crabxl.Workbook(write_only=True)
    wb.create_sheet().append([1, "=A1"])
    with pytest.raises(ValueError):
        wb.save(tmp_path / "stream.xlsx", calculate=True)
