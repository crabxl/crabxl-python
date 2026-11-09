# Compatibility constants adapted from openpyxl 3.1.5, Copyright (c) 2010–2024 openpyxl (MIT).
"""Public lexical token objects backed by the canonical Rust formula scanner."""

import re

from .._native import (
    classify_formula_operand,
    formula_scientific_prefix,
    scan_formula_fragment,
    tokenize_formula,
)


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
    SN_RE = re.compile(r"^[1-9](\.[0-9]+)?[Ee]$")
    WSPACE_RE = re.compile(r"[ \n]+")
    STRING_REGEXES = {
        '"': re.compile('"(?:[^"]*"")*[^"]*"(?!")'),
        "'": re.compile("'(?:[^']*'')*[^']*'(?!')"),
    }
    ERROR_CODES = (
        "#NULL!",
        "#DIV/0!",
        "#VALUE!",
        "#REF!",
        "#NAME?",
        "#NUM!",
        "#N/A",
        "#GETTING_DATA",
    )
    TOKEN_ENDERS = ",;}) +-*/^&=><%"

    def __init__(self, formula):
        self.formula = formula
        self.items = []
        self.token_stack = []
        self.offset = 0
        self.token = []
        self._parse()

    def _parse(self):
        if self.offset:
            return
        try:
            values = tokenize_formula(self.formula, self.MAX_TOKEN_BYTES)
        except ValueError as error:
            raise TokenizerError(str(error)) from error
        for value in values:
            token = Token(*value)
            self.items.append(token)
            if token.subtype == Token.OPEN:
                self.token_stack.append(token)
            elif token.subtype == Token.CLOSE:
                self.token_stack.pop()
        if self.formula.startswith("="):
            self.offset = len(self.formula)

    def _scan(self, operation, *, previous_operand=False, top=None):
        try:
            value, kind, subtype, consumed = scan_formula_fragment(
                self.formula,
                self.offset if self.offset >= 0 else len(self.formula) + self.offset,
                operation,
                "".join(self.token),
                bool(previous_operand),
                top,
                self.MAX_TOKEN_BYTES,
            )
        except ValueError as error:
            raise TokenizerError(str(error)) from error
        return Token(value, kind, subtype), consumed

    def _parse_string(self):
        self.assert_empty_token(can_follow=":")
        assert self.formula[self.offset] in ('"', "'")
        token, consumed = self._scan("string")
        if token.subtype == Token.TEXT:
            self.items.append(token)
        else:
            self.token.append(token.value)
        return consumed

    def _parse_brackets(self):
        assert self.formula[self.offset] == "["
        _, consumed = self._scan("brackets")
        self.token.append(self.formula[self.offset : self.offset + consumed])
        return consumed

    def _parse_error(self):
        self.assert_empty_token(can_follow="!")
        assert self.formula[self.offset] == "#"
        token, consumed = self._scan("error")
        self.items.append(Token.make_operand("".join(self.token) + token.value))
        del self.token[:]
        return consumed

    def _parse_whitespace(self):
        assert self.formula[self.offset] in (" ", "\n")
        token, consumed = self._scan("whitespace")
        self.items.append(token)
        return consumed

    def _parse_operator(self):
        assert self.formula[self.offset] in "%*/^&=><+-"
        previous = next(
            (token for token in reversed(self.items) if token.type != Token.WSPACE),
            None,
        )
        previous_operand = previous and (
            previous.subtype == Token.CLOSE
            or previous.type in (Token.OPERAND, Token.OP_POST)
        )
        token, consumed = self._scan("operator", previous_operand=previous_operand)
        self.items.append(token)
        return consumed

    def _parse_opener(self):
        assert self.formula[self.offset] in ("(", "{")
        token, consumed = self._scan("opener")
        del self.token[:]
        self.items.append(token)
        self.token_stack.append(token)
        return consumed

    def _parse_closer(self):
        assert self.formula[self.offset] in (")", "}")
        top = self.token_stack.pop()
        assert top.subtype == Token.OPEN and top.type in (
            Token.FUNC,
            Token.ARRAY,
            Token.PAREN,
        )
        token, consumed = self._scan("closer", top=top.type)
        self.items.append(token)
        return consumed

    def _parse_separator(self):
        assert self.formula[self.offset] in (";", ",")
        top = self.token_stack[-1].type if self.token_stack else None
        token, consumed = self._scan("separator", top=top)
        self.items.append(token)
        return consumed

    def check_scientific_notation(self):
        char = self.formula[self.offset]
        if (
            char in "+-"
            and self.token
            and formula_scientific_prefix("".join(self.token))
        ):
            self.token.append(char)
            self.offset += 1
            return True
        return False

    def assert_empty_token(self, can_follow=()):
        if self.token and self.token[-1] not in can_follow:
            raise TokenizerError(
                f"Unexpected character at position {self.offset} in '{self.formula}'"
            )

    def save_token(self):
        if self.token:
            self.items.append(Token.make_operand("".join(self.token)))
            del self.token[:]

    def render(self):
        if not self.items:
            return ""
        if self.items[0].type == Token.LITERAL:
            return self.items[0].value
        return "=" + "".join(token.value for token in self.items)
