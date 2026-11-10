"""Compare the pinned openpyxl workbooks through public read/edit/save APIs on 3.15.

Checks values, cell formatting, notes, hyperlinks, merges, filters and frozen panes.
This is a development oracle; it is not imported by the CrabXL package.
"""

import argparse
import sys
import warnings
from datetime import date, time, timedelta
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree.ElementTree import canonicalize, tostring
from zipfile import BadZipFile

import crabxl
import openpyxl


def close(book):
    if isinstance(book, openpyxl.Workbook) and book.vba_archive is not None:
        book.vba_archive.close()
    book.close()


def cell_value(value):
    if type(value).__name__ == "CellRichText":
        return "rich", canonicalize(tostring(value.to_tree()), rewrite_prefixes=True)
    if value is None or isinstance(
        value, (str, int, float, bool, date, time, timedelta)
    ):
        return value
    if hasattr(value, "ref"):
        return type(value).__name__, tuple(value), getattr(value, "text", None)
    return str(value)


def style(cell):
    result = [cell.number_format]
    for name in ("font", "fill", "border", "alignment", "protection"):
        value = getattr(cell, name, None)
        result.append(
            canonicalize(tostring(value.to_tree()), rewrite_prefixes=True)
            if value is not None
            else None
        )
    return tuple(result)


def snapshot(book):
    sheets = []
    for sheet in book.worksheets:
        cells = []
        for coordinate, cell in sorted(sheet._cells.items()):
            if (
                cell.value is None
                and not cell.has_style
                and not cell.hyperlink
                and not cell.comment
            ):
                continue
            link, note = cell.hyperlink, cell.comment
            cells.append(
                (
                    coordinate,
                    cell_value(cell.value),
                    cell.data_type,
                    style(cell),
                    (link.target, link.location, link.tooltip, link.display)
                    if link
                    else None,
                    (note.text, note.author, note.width, note.height) if note else None,
                )
            )
        sheets.append(
            (
                sheet.title,
                sheet.sheet_state,
                cells,
                sorted(str(value) for value in sheet.merged_cells.ranges),
                sheet.freeze_panes,
                sheet.auto_filter.ref,
            )
        )
    return book.sheetnames, sheets


def check_mode(path, coordinates, readonly, dataonly, output, **options):
    reference = openpyxl.load_workbook(
        path, read_only=readonly, data_only=dataonly, **options
    )
    actual = None
    try:
        actual = crabxl.load_workbook(
            path, read_only=readonly, data_only=dataonly, **options
        )
        assert actual.sheetnames == reference.sheetnames, "sheet names"
        for name, addresses in coordinates.items():
            for address in addresses:
                expected = reference[name].cell(*address)
                observed = actual[name].cell(*address)
                assert cell_value(expected.value) == cell_value(observed.value), (
                    f"{name}!{expected.coordinate} value"
                )
                assert expected.data_type == observed.data_type, (
                    f"{name}!{expected.coordinate} data type"
                )
                assert style(expected) == style(observed), (
                    f"{name}!{expected.coordinate} style"
                )
                if readonly and hasattr(expected, "style_array"):
                    assert tuple(expected.style_array) == tuple(observed.style_array), (
                        f"{name}!{expected.coordinate} indexed style"
                    )
        if not readonly:
            expected = snapshot(reference)
            for _ in range(2):
                actual.save(output)
                verified = openpyxl.load_workbook(output, data_only=dataonly, **options)
                try:
                    assert snapshot(verified) == expected, "saved workbook content"
                finally:
                    close(verified)
    finally:
        close(reference)
        if actual is not None:
            close(actual)


def check_edit(path, output, **options):
    reference = openpyxl.load_workbook(path, **options)
    actual = None
    try:
        actual = crabxl.load_workbook(path, **options)
        for sheet in reference.worksheets:
            # Materialize styles before editing to exercise the canonical loaded model.
            assert actual[sheet.title]["A1"].number_format == sheet["A1"].number_format
            sheet["A1"] = "CrabXL corpus edit"
            actual[sheet.title]["A1"] = "CrabXL corpus edit"
        expected = snapshot(reference)
        for _ in range(2):
            actual.save(output)
            verified = openpyxl.load_workbook(output, **options)
            try:
                assert snapshot(verified) == expected, "edited workbook content"
            finally:
                close(verified)
    finally:
        close(reference)
        if actual is not None:
            close(actual)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-checkout", type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 15) or openpyxl.__version__ != "3.1.5":
        parser.error("Run with CPython 3.15 and openpyxl 3.1.5")
    root = args.reference_checkout.resolve() / "openpyxl"
    files = sorted(
        path
        for path in root.rglob("*")
        if path.suffix.lower() in (".xlsx", ".xlsm", ".xltx", ".xltm")
    )
    if not files:
        parser.error(f"No workbook fixtures found under {root}")
    passed = failed = rejected = 0
    with (
        TemporaryDirectory(prefix="crabxl-corpus-") as directory,
        warnings.catch_warnings(),
    ):
        warnings.simplefilter("ignore")
        output = Path(directory) / "output.xlsx"
        for path in files:
            label = path.relative_to(root)
            try:
                reference = openpyxl.load_workbook(path)
            except BadZipFile:
                try:
                    actual = crabxl.load_workbook(path)
                except (ValueError, BadZipFile):
                    rejected += 1
                    continue
                close(actual)
                failed += 1
                print(
                    f"FAIL {label}: accepted a corrupt ZIP rejected by openpyxl",
                    flush=True,
                )
                continue
            coordinates = {
                sheet.title: list(sheet._cells) for sheet in reference.worksheets
            }
            close(reference)
            for readonly, dataonly, vba, links, rich in product(
                (False, True), repeat=5
            ):
                options = dict(keep_vba=vba, keep_links=links, rich_text=rich)
                phase = f"read_only={readonly}, data_only={dataonly}, {options}"
                try:
                    check_mode(path, coordinates, readonly, dataonly, output, **options)
                    passed += 1
                except Exception as error:
                    failed += 1
                    print(
                        f"FAIL {label} [{phase}]: {type(error).__name__}: {error}",
                        flush=True,
                    )
            for vba, links, rich in product((False, True), repeat=3):
                options = dict(keep_vba=vba, keep_links=links, rich_text=rich)
                try:
                    check_edit(path, output, **options)
                    passed += 1
                except Exception as error:
                    failed += 1
                    print(
                        f"FAIL {label} [edit {options}]: {type(error).__name__}: {error}",
                        flush=True,
                    )
            print(f"CHECKED {label}", flush=True)
    print(
        f"{len(files)} fixtures: {passed} public API checks passed, {failed} failed; {rejected} corrupt ZIP inputs rejected by both implementations"
    )
    return bool(failed)


if __name__ == "__main__":
    raise SystemExit(main())
