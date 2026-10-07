"""Inline font values for canonical rich-text runs."""

from ..styles.fonts import Font


class InlineFont(Font):
    _aliases = {**Font._aliases, "rFont": "name"}

    def __init__(
        self,
        rFont=None,
        charset=None,
        family=None,
        b=None,
        i=None,
        strike=None,
        outline=None,
        shadow=None,
        condense=None,
        extend=None,
        color=None,
        sz=None,
        u=None,
        vertAlign=None,
        scheme=None,
    ):
        super().__init__(
            name=rFont,
            charset=charset,
            family=family,
            b=b,
            i=i,
            strike=strike,
            outline=outline,
            shadow=shadow,
            condense=condense,
            extend=extend,
            color=color,
            sz=sz,
            u=u,
            vertAlign=vertAlign,
            scheme=scheme,
        )
