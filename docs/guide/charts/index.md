---
title: Charts
description: Create charts from worksheet data.
---

This page is adapted from the [openpyxl 3.1.5 documentation](https://openpyxl.readthedocs.io/en/3.1/) (MIT license). The calls are the same in CrabXL.

## Chart types

The following charts are available:

## Creating a chart

Charts are composed of at least one series of one or more data points. Series
themselves are comprised of references to cell ranges.

```python
>>> from crabxl import Workbook
>>> wb = Workbook()
>>> ws = wb.active
>>> for i in range(10):
...     ws.append([i])
>>>
>>> from crabxl.chart import BarChart, Reference, Series
>>> values = Reference(ws, min_col=1, min_row=1, max_col=1, max_row=10)
>>> chart = BarChart()
>>> chart.add_data(values)
>>> ws.add_chart(chart, "E15")
>>> wb.save("SampleChart.xlsx")
```

By default the top-left corner of a chart is anchored to cell E15 and the
size is 15 x 7.5 cm (approximately 5 columns by 14 rows). This can be changed
by setting the `anchor`, `width` and `height` properties of the chart. The
actual size will depend on operating system and device. Other anchors are
possible; see `spreadsheet_drawing` for further information.

## Working with axes

## Change the chart layout

## Styling charts

## Advanced charts

Charts can be combined to create new charts:

## Using chartsheets

Charts can be added to special worksheets called chartsheets:

## Positioning charts

Position charts using anchors:

## Advanced chart formatting

Use graphical properties for advanced chart formatting:
