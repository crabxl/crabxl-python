"""Native conversion of plain appended rows matches the Python conversion."""

from datetime import date, datetime, time, timedelta, timezone

import crabxl
import pytest
from crabxl.utils.exceptions import IllegalCharacterError

ROW = [
    None,
    True,
    7,
    1.5,
    "text",
    "=SUM(A1:B1)",
    "#N/A",
    "x" * 40000,
    datetime(2024, 5, 6, 7, 8, 9, 123000),
    date(2024, 5, 6),
    time(1, 2, 3),
    timedelta(days=2, seconds=5),
]


def _saved(tmp_path, name, write_only, rows):
    book = crabxl.Workbook(write_only=write_only)
    sheet = book.create_sheet("Data") if write_only else book.active
    for row in rows:
        sheet.append(row)
    path = tmp_path / f"{name}.xlsx"
    book.save(path)
    loaded = crabxl.load_workbook(path)
    sheet = loaded.worksheets[0]
    return [
        [(cell.value, cell.number_format, cell.data_type) for cell in row]
        for row in sheet.iter_rows()
    ]


@pytest.mark.parametrize("write_only", [False, True])
def test_plain_rows_save_like_the_python_path(tmp_path, write_only):
    # A generator is not a plain list or tuple, so it takes the Python path.
    expected = _saved(tmp_path, "python", write_only, [iter(ROW), iter(ROW)])
    assert _saved(tmp_path, "native", write_only, [ROW, tuple(ROW)]) == expected


@pytest.mark.parametrize("write_only", [False, True])
@pytest.mark.parametrize(
    ("value", "error"),
    [
        ("bad\x01text", IllegalCharacterError),
        (datetime(2024, 1, 1, tzinfo=timezone.utc), TypeError),
        (object(), ValueError),
    ],
)
def test_plain_rows_keep_python_errors(write_only, value, error):
    book = crabxl.Workbook(write_only=write_only)
    sheet = book.create_sheet("Data") if write_only else book.active
    with pytest.raises(error):
        sheet.append([1, value])


def test_loaded_sheet_appends_without_loading_and_reads_back(tmp_path):
    source = tmp_path / "source.xlsx"
    book = crabxl.Workbook()
    book.active.title = "Data"
    for index in range(5):
        book.active.append([index, f"row {index}"])
    book.save(source)

    loaded = crabxl.load_workbook(source)
    sheet = loaded["Data"]
    sheet["B2"] = "changed"
    sheet.append([5, "row 5", date(2024, 1, 2)])
    assert sheet._native is None
    assert sheet.max_row == 6
    assert sheet["C6"].value == date(2024, 1, 2)
    sheet.append(iter([6]))
    target = tmp_path / "target.xlsx"
    loaded.save(target)
    values = [list(row) for row in crabxl.load_workbook(target)["Data"].values]
    assert values[1][1] == "changed"
    assert values[5] == [5, "row 5", datetime(2024, 1, 2)]
    assert values[6] == [6, None, None]
