"""Public lexical token objects backed by the canonical Rust formula scanner."""

from .._native import classify_formula_operand, tokenize_formula


class TokenizerError(Exception):
    """The formula cannot be tokenized."""


class Token:
    """A mutable compatibility token; lexical classification runs in Rust."""

    __slots__ = ("value", "type", "subtype")

    LITERAL = "LITERAL"
    OPERAND = "OPERAND"
    FUNC = "FUNC"
    ARRAY = "ARRAY"
    PAREN = "PAREN"
    SEP = "SEP"
    OP_PRE = "OPERATOR-PREFIX"
    OP_IN = "OPERATOR-INFIX"
    OP_POST = "OPERATOR-POSTFIX"
    WSPACE = "WHITE-SPACE"
    TEXT = "TEXT"
    NUMBER = "NUMBER"
    LOGICAL = "LOGICAL"
    ERROR = "ERROR"
    RANGE = "RANGE"
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    ARG = "ARG"
    ROW = "ROW"

    def __init__(self, value, type_, subtype=""):
        self.value = value
        self.type = type_
        self.subtype = subtype

    def __repr__(self):
        return f"{self.type} {self.subtype} {self.value}:"

    @classmethod
    def make_operand(cls, value):
        # Preserve the public empty-literal IndexError without native panics.
        value[0]
        return cls(value, cls.OPERAND, classify_formula_operand(value))

    @classmethod
    def make_separator(cls, value):
        assert value in (",", ";")
        return cls(value, cls.SEP, cls.ARG if value == "," else cls.ROW)

    @classmethod
    def make_subexp(cls, value, func=False):
        last = value[-1]
        assert last in "({)}"
        if value in ("{", "}"):
            assert not func
            type_ = cls.ARRAY
        elif value == "(":
            assert not func
            type_ = cls.PAREN
        elif value == ")":
            type_ = cls.FUNC if func else cls.PAREN
        else:
            assert last == "("
            type_ = cls.FUNC
        return cls(value, type_, cls.OPEN if last in "({" else cls.CLOSE)

    def get_closer(self):
        assert self.subtype == self.OPEN
        assert self.type in (self.FUNC, self.PAREN, self.ARRAY)
        return type(self)(
            "}" if self.type == self.ARRAY else ")", self.type, self.CLOSE
        )


class Tokenizer:
    """Tokenize a formula without evaluating it or loading worksheet cells."""

    MAX_TOKEN_BYTES = 32 * 1024 * 1024

    def __init__(self, formula):
        self.formula = formula
        try:
            values = tokenize_formula(formula, self.MAX_TOKEN_BYTES)
        except ValueError as error:
            raise TokenizerError(str(error)) from error
        self.items = [Token(*value) for value in values]

    def render(self):
        if not self.items:
            return ""
        prefix = "=" if self.items[0].type != Token.LITERAL else ""
        return prefix + "".join(token.value for token in self.items)
