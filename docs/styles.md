---
title: Styles
description: Fonts, fills, borders, alignment, protection and number formats.
---

A `Style` is the complete appearance of a cell. Every style type is an
immutable value. Change one with `replace`, which returns a new value.

```python
import crabxl as xl

header = xl.Style(
    font=xl.Font(bold=True, color="FFFFFF"),
    fill=xl.Fill("1F4E79"),
    border=xl.Border.all(xl.Side("thin", "000000")),
    alignment=xl.Alignment(horizontal="center", wrap_text=True),
)
sheet["A1:D1"].style = header
money = header.replace(number_format="#,##0.00")
```

Assigning `style` to a range gives every cell that style. To change one part
of each cell's style and keep the rest, use `map_style`:

```python
sheet["B2:B100"].map_style(lambda style: style.replace(number_format="0.00"))
```

## Types

| Type | Contents |
|---|---|
| `Font` | Name, size, bold, italic, strike, underline, color. `None` attributes come from the workbook's default font. |
| `Fill` | A solid background color. |
| `Border`, `Side` | The four outer border lines. |
| `Alignment` | Horizontal and vertical alignment, wrapping, shrinking, indent and rotation. |
| `Protection` | Locked and hidden flags. They work when the sheet is protected. |
| `Color` | RGB hex text (`Color("1F4E79")`), a theme color (`Color.theme(4, tint=0.4)`), an indexed color or automatic. |

Wherever a color is expected, hex text works too: `xl.Font(color="FF0000")`.

`PartialStyle` holds the font and fill that a conditional format applies on
top of a cell's style.
