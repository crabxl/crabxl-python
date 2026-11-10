---
title: Pivot tables
description: Read and preserve pivot tables.
---

This page is adapted from the [openpyxl 3.1.5 documentation](https://openpyxl.readthedocs.io/en/3.1/) (MIT license). The calls are the same in CrabXL.

CrabXL provides read-support for pivot tables so that they will be
preserved in existing files. The specification for pivot tables, while
extensive, is not very clear and it is not intended that client code should
be able to create pivot tables. However, it should be possible to edit and
manipulate existing pivot tables, eg. change their ranges or whether they
should update automatically settings.

As is the case for charts, images and tables there is currently no management
API for pivot tables so that client code will have to loop over the
`_pivots` list of a worksheet.

## Example

```python
from crabxl import load_workbook

wb = load_workbook("campaign.xlsx")
ws = wb["Results"]
pivot = ws._pivots[0]  # any will do as they share the same cache
pivot.cache.refreshOnLoad = True
```

For further information see `CacheDefinition`
