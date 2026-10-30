import random
import re

import pytest
from helpers import AB

from automata.dfa import accepts, all_words, equivalent
from automata.regex import RegexSyntaxError, ast_matches, parse, to_min_dfa, to_python_regex
from reference.build import T05_HARDER_PAIR, T05_PAIR, t05_shortest_witness


@pytest.mark.parametrize("text", ["a", "()", "a|b", "(ab)*", "a+b?", "(a|())*", "a**", "((a))", "(ba)*b+a(ba)+a"])
def test_parser_accepts_grammar(text):
    parse(text, AB)


@pytest.mark.parametrize("text", ["", "a|", "|a", "(a", "a)", "c", "*a", "a b", "(|a)", "a||b"])
def test_parser_rejects_everything_else(text):
    with pytest.raises(RegexSyntaxError):
        parse(text, AB)


def test_precedence():
    assert to_min_dfa("ab*", AB) == to_min_dfa("a(b*)", AB)
    assert to_min_dfa("ab|b", AB) == to_min_dfa("(ab)|b", AB)
    assert accepts(to_min_dfa("()", AB), "") and not accepts(to_min_dfa("()", AB), "a")


def random_regex(rng: random.Random, depth: int) -> str:
    if depth == 0 or rng.random() < 0.3:
        return rng.choice(["a", "b", "()"])
    k = rng.random()
    if k < 0.4:
        return random_regex(rng, depth - 1) + random_regex(rng, depth - 1)
    if k < 0.7:
        return f"({random_regex(rng, depth - 1)}|{random_regex(rng, depth - 1)})"
    return f"({random_regex(rng, depth - 1)}){rng.choice('*+?')}"


@pytest.mark.parametrize("seed", range(120))
def test_three_independent_matchers_agree(seed):
    text = random_regex(random.Random(seed), 4)
    ast = parse(text, AB)
    dfa = to_min_dfa(text, AB)
    py = re.compile(to_python_regex(ast))
    for w in all_words(AB, 7):
        expected = ast_matches(ast, w)
        assert accepts(dfa, w) == expected, (text, w)
        assert bool(py.fullmatch(w)) == expected, (text, w)


@pytest.mark.parametrize("pair", [T05_PAIR, T05_HARDER_PAIR])
def test_task05_pairs_agree_on_short_words(pair):
    w = t05_shortest_witness(pair)
    a1, a2 = parse(pair.r1, AB), parse(pair.r2, AB)
    assert len(w) >= 9
    assert ast_matches(a1, w) != ast_matches(a2, w)
    assert all(ast_matches(a1, u) == ast_matches(a2, u) for u in all_words(AB, len(w) - 1))


def test_task05_default_pair_hand_proof():
    """The hand proof in reference/build.py: unique shortest witness bababbabaa, and the
    obvious guess babababaa is matched by both."""
    d1, d2 = to_min_dfa(T05_PAIR.r1, AB), to_min_dfa(T05_PAIR.r2, AB)
    assert equivalent(d1, d2) == (False, "bababbabaa")
    shortest = [w for w in all_words(AB, 10) if len(w) == 10 and accepts(d1, w) != accepts(d2, w)]
    assert shortest == ["bababbabaa"]
    assert accepts(d1, "babababaa") and accepts(d2, "babababaa")
