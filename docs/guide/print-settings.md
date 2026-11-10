---
title: Print settings
description: Page setup, print areas, titles, headers and footers.
---

This page is adapted from the [openpyxl 3.1.5 documentation](https://openpyxl.readthedocs.io/en/3.1/) (MIT license). The calls are the same in CrabXL.

CrabXL provides reasonably full support for print settings.

## Edit Print Options

```python
>>> from crabxl.workbook import Workbook
>>>
>>> wb = Workbook()
>>> ws = wb.active
>>>
>>> ws.print_options.horizontalCentered = True
>>> ws.print_options.verticalCentered = True
```

## Headers and Footers

Headers and footers use their own formatting language. This is fully
supported when writing them but, due to the complexity and the possibility of
nesting, only partially when reading them. There is support for the font,
size and color for a left, centre/center, or right element. Granular control
(highlighting individuals words) will require applying control codes
manually.

```python
>>> from crabxl.workbook import Workbook
>>>
>>> wb = Workbook()
>>> ws = wb.active
>>>
>>> ws.oddHeader.left.text = "Page &[Page] of &N"
>>> ws.oddHeader.left.size = 14
>>> ws.oddHeader.left.font = "Tahoma,Bold"
>>> ws.oddHeader.left.color = "CC3366"
```

Also supported are `evenHeader` and `evenFooter` as well as `firstHeader` and `firstFooter`.

## Add Print Titles

You can print titles on every page to ensure that the data is properly
labelled.

```python
>>> from crabxl.workbook import Workbook
>>>
>>> wb = Workbook()
>>> ws = wb.active
>>>
>>> ws.print_title_cols = 'A:B' # the first two cols
>>> ws.print_title_rows = '1:1' # the first row
```

## Add a Print Area

You can select a part of a worksheet as the only part that you want to print

```python
>>> from crabxl.workbook import Workbook
>>>
>>> wb = Workbook()
>>> ws = wb.active
>>>
>>> ws.print_area = 'A1:F10'
```

## Change page layout and size

You can adjust the size and print orientation per sheet of a workbook.

```python
>>>
>>> wb = Workbook()
>>> ws = wb.active
>>>
>>> ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
>>> ws.page_setup.paperSize = ws.PAPERSIZE_A5
```

The table size is stored internally as an integer, some alias variables are
also available for common sizes (refer to PAPERSIZE_* in `worksheet` ).
If you need a non-standard size, a full list can be found by searching `ECMA-376 pageSetup`
and setting that value as the paperSize
