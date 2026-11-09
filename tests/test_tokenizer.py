"""Formula error operands keep their reference qualifiers."""

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    "error",
    [
        "#NULL!",
        "#DIV/0!",
        "#VALUE!",
        "#REF!",
        "#NAME?",
        "#NUM!",
        "#N/A",
        "#GETTING_DATA",
    ],
)
@pytest.mark.parametrize("qualifier", ["", "Sheet1!", "'Sheet 1'!", "[1]Sheet1!"])
def test_error_tokens_match_reference(error, qualifier):
    snapshots = []
    for engine in ("openpyxl", "crabxl"):
        tokenizer = import_module(engine + ".formula.tokenizer").Tokenizer
        parsed = tokenizer(f"={qualifier}{error}+A1")
        snapshots.append(
            (
                [(token.value, token.type, token.subtype) for token in parsed.items],
                parsed.render(),
            )
        )
    assert snapshots[0] == snapshots[1]


@pytest.mark.parametrize("prefix", ["A1", "1", "TRUE", "'Sheet 1'"])
def test_unqualified_error_cannot_follow_unfinished_operand(prefix):
    for engine in ("openpyxl", "crabxl"):
        module = import_module(engine + ".formula.tokenizer")
        with pytest.raises(module.TokenizerError):
            module.Tokenizer(f"={prefix}#REF!")


@pytest.mark.parametrize(
    "formula", ["= \n ", "=A1\n B2", "=SUM( \n A1)", "=A1\n\n  \nB2"]
)
def test_mixed_whitespace_matches_reference(formula):
    snapshots = []
    for engine in ("openpyxl", "crabxl"):
        parsed = import_module(engine + ".formula.tokenizer").Tokenizer(formula)
        snapshots.append(
            [(token.value, token.type, token.subtype) for token in parsed.items]
        )
    assert snapshots[0] == snapshots[1]


@pytest.mark.parametrize("formula", ["=A1'S'", '=1\n"a"', "=A1{", "=[1]'S'"])
def test_unfinished_operands_reject_invalid_transitions(formula):
    for engine in ("openpyxl", "crabxl"):
        module = import_module(engine + ".formula.tokenizer")
        with pytest.raises(module.TokenizerError):
            module.Tokenizer(formula)


@pytest.mark.parametrize(
    "literal",
    ["", "1_0", "1_0.0_5", "-1_0e+2_0", "1__0", "_1", "1_", "1._0", "1_.0", "1e_2"],
)
def test_operand_factory_numeric_literals_match_reference(literal):
    snapshots = []
    for engine in ("openpyxl", "crabxl"):
        token = import_module(engine + ".formula.tokenizer").Token.make_operand(literal)
        snapshots.append((token.value, token.type, token.subtype))
    assert snapshots[0] == snapshots[1]


def test_render_literal_keeps_reference_behavior_after_items_mutation():
    for engine in ("openpyxl", "crabxl"):
        module = import_module(engine + ".formula.tokenizer")
        parsed = module.Tokenizer("literal")
        parsed.items.append(module.Token("extra", module.Token.LITERAL))
        assert parsed.render() == "literal"


@pytest.mark.parametrize(
    "formula, offset, operation",
    [
        ('α"中文"尾', 1, "_parse_string"),
        ("α[中[文]]尾", 1, "_parse_brackets"),
        ("α#REF!尾", 1, "_parse_error"),
        ("α \n 尾", 1, "_parse_whitespace"),
        ("α[中]", -3, "_parse_brackets"),
    ],
)
def test_fragment_offsets_and_buffers_match_reference(formula, offset, operation):
    snapshots = []
    for engine in ("openpyxl", "crabxl"):
        parsed = import_module(engine + ".formula.tokenizer").Tokenizer(formula)
        parsed.items.clear()
        parsed.offset = offset
        consumed = getattr(parsed, operation)()
        snapshots.append(
            (
                consumed,
                parsed.offset,
                parsed.token[:],
                [(token.value, token.type, token.subtype) for token in parsed.items],
            )
        )
    assert snapshots[0] == snapshots[1]
