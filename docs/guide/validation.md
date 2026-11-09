---
title: Data validation
description: Restrict the values that users can enter in cells.
---

This page is adapted from the [openpyxl 3.1.5 documentation](https://openpyxl.readthedocs.io/en/3.1/) (MIT license). The calls are the same in CrabXL.

Data validators can be applied to ranges of cells but are not enforced or evaluated. Ranges do not have to be contiguous: eg. "A1 B2:B5" is contains A1 and the cells B2 to B5 but not A2 or B2.

## Examples

```python
>>> from crabxl import Workbook
>>> from crabxl.worksheet.datavalidation import DataValidation
>>>
>>> # Create the workbook and worksheet we'll be working with
>>> wb = Workbook()
>>> ws = wb.active
>>>
>>> # Create a data-validation object with list validation
>>> dv = DataValidation(type="list", formula1='"Dog,Cat,Bat"', allow_blank=True)
>>>
>>> # Optionally set a custom error message
>>> dv.error ='Your entry is not in the list'
>>> dv.errorTitle = 'Invalid Entry'
>>>
>>> # Optionally set a custom prompt message
>>> dv.prompt = 'Please select from the list'
>>> dv.promptTitle = 'List Selection'
>>>
>>> # Add the data-validation object to the worksheet
>>> ws.add_data_validation(dv)
```

```python
>>> # Create some cells, and add them to the data-validation object
>>> c1 = ws["A1"]
>>> c1.value = "Dog"
>>> dv.add(c1)
>>> c2 = ws["A2"]
>>> c2.value = "An invalid value"
>>> dv.add(c2)
>>>
>>> # Or, apply the validation to a range of cells
>>> dv.add('B1:B1048576') # This is the same as for the whole of column B
>>>
>>> # Check with a cell is in the validator
>>> "B4" in dv
True
```

> **Note:**
    Validations without any cell ranges will be ignored when saving a workbook.

> **Note:**
    Excel and LibreOffice interpret the parameter `showDropDown=True` as the dropdown arrow should be hidden.

## Other validation examples

Any whole number:
:

```python
dv = DataValidation(type="whole")
```

Any whole number above 100:
:

```python
dv = DataValidation(type="whole",
                    operator="greaterThan",
                    formula1=100)
```

Any decimal number:
:

```python
dv = DataValidation(type="decimal")
```

Any decimal number between 0 and 1:
:

```python
dv = DataValidation(type="decimal",
                    operator="between",
                    formula1=0,
                    formula2=1)
```

Any date:
:

```python
dv = DataValidation(type="date")
```

or time:
:

```python
dv = DataValidation(type="time")
```

Any string at most 15 characters:
:

```python
dv = DataValidation(type="textLength",
                    operator="lessThanOrEqual"),
                    formula1=15)
```

Cell range validation:
:

```python
from crabxl.utils import quote_sheetname
dv = DataValidation(type="list",
                    formula1="{0}!$B$1:$B$10".format(quote_sheetname(sheetname))
                    )
```

Custom rule:
:

```python
dv = DataValidation(type="custom",
                    formula1"=SOMEFORMULA")
```

> **Note:** 
> See http://www.contextures.com/xlDataVal07.html for custom rules
