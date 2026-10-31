import random

import pytest
from helpers import AB, random_cnf

from automata.cfg import Grammar, Production, check_upto, cnf_violations, cyk, enumerate_upto
from automata.dfa import all_words
from graders.oracles import t07_enumerate, t07_member, t08_enumerate, t08_member, t08_shortest_longer_than
from reference.build import t07_reference_grammar, t08_reference_grammar

BR = ["(", ")", "[", "]"]


def g(start, *rules):
    return Grammar(start=start, productions=[Production(lhs=l, rhs=r) for l, r in rules])


@pytest.mark.parametrize(
    "grammar, n_problems",
    [
        (g("S", ("S", ["A", "B"]), ("A", ["a"]), ("B", ["b"])), 0),
        (g("S", ("S", ["A"]), ("A", ["a"])), 1),  # unit production
        (g("S", ("S", []), ("A", ["a"])), 1),  # epsilon production
        (g("S", ("S", ["a", "B"]), ("B", ["b"])), 1),  # mixed rhs
        (g("S", ("S", ["A", "B", "C"]), ("A", ["a"])), 1),  # too long
        (g("a", ("a", ["b"])), 2),  # terminal used as start and lhs
        (g("S", ("S", ["A B"])), 1),  # whitespace in a name
    ],
)
def test_cnf_violations(grammar, n_problems):
    assert len(cnf_violations(grammar, AB)) == n_problems


@pytest.mark.parametrize("seed", range(80))
def test_cyk_matches_enumeration(seed):
    gr = random_cnf(random.Random(seed), n_nt=3)
    by_len, capped = enumerate_upto(gr, AB, 7)
    assert not capped
    for w in all_words(AB, 7):
        if w:
            assert cyk(gr, AB, w) == (w in by_len[len(w)]), w


def truth_from(gr: Grammar, n: int):
    by_len, _ = enumerate_upto(gr, AB, n)
    member = lambda w: bool(w) and len(w) <= n and w in by_len[len(w)]  # noqa: E731
    return member, by_len


@pytest.mark.parametrize("seed", range(200))
def test_check_upto_matches_brute_force(seed):
    """Truth = language of one random grammar (cut at N), candidate = another random grammar.
    check_upto must report a shortest genuine mismatch, or none if they agree up to N."""
    rng = random.Random(10_000 + seed)
    n = 7
    truth_g, cand = random_cnf(rng, 3), random_cnf(rng, 3)
    member, truth_by_len = truth_from(truth_g, n)
    res = check_upto(cand, AB, n, member, truth_by_len, lambda k: None)
    mismatches = [w for w in all_words(AB, n) if w and cyk(cand, AB, w) != member(w)]
    if not mismatches:
        assert res.kind is None
        return
    assert res.kind in ("over", "under")
    w = res.counterexample
    assert len(w) == len(mismatches[0])  # shortest
    if res.kind == "over":
        assert cyk(cand, AB, w) and not member(w)
    else:
        assert member(w) and not cyk(cand, AB, w)


def test_reference_grammars_match_language():
    by_len, _ = enumerate_upto(t07_reference_grammar(), BR, 12)
    assert by_len == {n: s for n, s in t07_enumerate(12).items()}
    for w in all_words(["a", "b"], 12):
        if w:
            assert cyk(t08_reference_grammar(), ["a", "b"], w) == t08_member(w), w
    assert cyk(t07_reference_grammar(), BR, "([][])") and t07_member("([][])")
    assert not cyk(t07_reference_grammar(), BR, "([])") and not t07_member("([])")


def test_finite_grammar_is_rejected_even_if_correct_up_to_n():
    """A grammar listing only the words up to N must not pass: L is infinite."""
    words = ["aba"]  # the only word of L with length <= 5
    gr = g("S", ("S", ["TA", "M"]), ("M", ["TB", "TA"]), ("TA", ["a"]), ("TB", ["b"]))
    res = check_upto(gr, ["a", "b"], 5, t08_member, t08_enumerate(5), t08_shortest_longer_than)
    assert words == sorted(w for s in t08_enumerate(5).values() for w in s)
    assert res.kind == "under" and res.finite_language
    assert t08_member(res.counterexample) and len(res.counterexample) == 6
