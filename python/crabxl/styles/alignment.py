"""Cell alignment values."""

from ._base import StyleValue


class Alignment(StyleValue):
    _component = "alignment"
    _children = ()
    _fields = (
        "horizontal",
        "vertical",
        "textRotation",
        "wrapText",
        "shrinkToFit",
        "indent",
        "relativeIndent",
        "justifyLastLine",
        "readingOrder",
        "mergeCell",
    )
    _aliases = {
        "text_rotation": "textRotation",
        "wrap_text": "wrapText",
        "shrink_to_fit": "shrinkToFit",
    }

    def __init__(
        self,
        horizontal=None,
        vertical=None,
        textRotation=0,
        wrapText=None,
        shrinkToFit=None,
        indent=0,
        relativeIndent=0,
        justifyLastLine=None,
        readingOrder=0,
        text_rotation=None,
        wrap_text=None,
        shrink_to_fit=None,
        mergeCell=None,
    ):
        values = locals()
        for field in self._fields:
            setattr(self, field, values[field])
        for alias, value in (
            ("text_rotation", text_rotation),
            ("wrap_text", wrap_text),
            ("shrink_to_fit", shrink_to_fit),
        ):
            if value is not None:
                setattr(self, alias, value)
