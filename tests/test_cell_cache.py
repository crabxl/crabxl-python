import gc

import crabxl


def test_cell_cache_keeps_held_cells_and_sweeps_released_ones():
    sheet = crabxl.Workbook().active
    held = [sheet.cell(row, 1, row) for row in range(1, 101)]
    for row in range(1, 5001):
        sheet.cell(row, 2, row)
    gc.collect()
    sheet.cell(5001, 2, 0)
    assert all(sheet.cell(row, 1) is cell for row, cell in enumerate(held, 1))
    assert len(sheet._cells._data) < 3000
    assert sheet.cell(4000, 2).value == 4000
    assert {key for key, _ in sheet._cells.items()} >= {
        (row, 1) for row in range(1, 101)
    }
