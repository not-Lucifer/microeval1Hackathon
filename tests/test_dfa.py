import random

import pytest
from helpers import AB, brute_first_difference, brute_nerode_count, random_dfa, rename_states

from automata.dfa import (
    DFA,
    accepts,
    agreement_upto,
    all_words,
    complement,
    complete,
    equivalent,
    is_complete,
    minimal_size,
    minimize,
    missing_transitions,
    remove_unreachable,
    shortest_accepted,
)

EVEN_A = DFA(
    states=["e", "o"], alphabet=AB, start="e", accepting=["e"],
    transitions={"e": {"a": "o", "b": "e"}, "o": {"a": "e", "b": "o"}},
)


def test_accepts_and_epsilon():
    assert accepts(EVEN_A, "")
    assert accepts(EVEN_A, "abab")
    assert not accepts(EVEN_A, "ab")


@pytest.mark.parametrize(
    "bad",
    [
        {"start": "zz"},
        {"accepting": ["zz"]},
        {"states": ["e", "e"]},
        {"transitions": {"e": {"a": "zz", "b": "e"}, "o": {"a": "e", "b": "o"}}},
        {"transitions": {"e": {"c": "e"}, "o": {"a": "e", "b": "o"}}},
        {"transitions": {"zz": {"a": "e"}}},
    ],
)
def test_invalid_structure_rejected(bad):
    with pytest.raises(ValueError):
        DFA(**{**EVEN_A.model_dump(), **bad})


def test_complete_adds_trap_only_when_needed():
    assert complete(EVEN_A) is EVEN_A
    partial = DFA(states=["x"], alphabet=AB, start="x", accepting=["x"], transitions={"x": {"a": "x"}})
    assert missing_transitions(partial) == [("x", "b")]
    c = complete(partial)
    assert is_complete(c) and len(c.states) == 2
    assert all(accepts(c, w) == accepts(partial, w) for w in all_words(AB, 6))


def test_equivalent_gives_shortest_counterexample():
    all_words_dfa = DFA(states=["x"], alphabet=AB, start="x", accepting=["x"], transitions={"x": {"a": "x", "b": "x"}})
    assert equivalent(EVEN_A, all_words_dfa) == (False, "a")
    assert equivalent(EVEN_A, rename_states(EVEN_A)) == (True, None)
    assert equivalent(complement(complement(EVEN_A)), EVEN_A)[0]


def test_minimize_merges_and_is_canonical():
    # 4-state DFA for "even number of a" with duplicated states
    dup = DFA(
        states=["e1", "o1", "e2", "o2", "junk"], alphabet=AB, start="e1", accepting=["e1", "e2"],
        transitions={"e1": {"a": "o2", "b": "e2"}, "o1": {"a": "e2", "b": "o2"},
                     "e2": {"a": "o1", "b": "e1"}, "o2": {"a": "e1", "b": "o1"}, "junk": {"a": "junk", "b": "junk"}},
    )
    m = minimize(dup)
    assert len(m.states) == 2
    assert minimize(m) == m  # idempotent
    assert minimize(rename_states(dup)) == m  # canonical: renaming changes nothing


def test_remove_unreachable_and_shortest_accepted():
    d = DFA(states=["a0", "a1", "x"], alphabet=AB, start="a0", accepting=["a1", "x"],
            transitions={"a0": {"a": "a0", "b": "a1"}, "a1": {"a": "a1", "b": "a1"}, "x": {"a": "x", "b": "x"}})
    assert remove_unreachable(d).states == ["a0", "a1"]
    assert shortest_accepted(d) == "b"


@pytest.mark.parametrize("seed", range(150))
def test_equivalent_matches_brute_force(seed):
    rng = random.Random(seed)
    d1, d2 = random_dfa(rng, rng.randint(1, 3)), random_dfa(rng, rng.randint(1, 3), prefix="t")
    same, cex = equivalent(d1, d2)
    # inequivalent DFAs with n1, n2 states differ on a word shorter than n1*n2 <= 9
    assert cex == brute_first_difference(d1, d2, 9)
    assert same == (cex is None)


@pytest.mark.parametrize("seed", range(150))
def test_minimize_matches_brute_force_nerode(seed):
    rng = random.Random(1000 + seed)
    d = random_dfa(rng, rng.randint(1, 5), p_missing=0.2)
    m = minimize(d)
    assert is_complete(m)
    assert brute_first_difference(d, m, 10) is None
    assert len(m.states) == brute_nerode_count(remove_unreachable(complete(d)))
    assert minimal_size(rename_states(d)) == len(m.states)


@pytest.mark.parametrize("seed", range(40))
def test_agreement_upto_matches_enumeration(seed):
    rng = random.Random(2000 + seed)
    d1, d2 = random_dfa(rng, 3), random_dfa(rng, 3, prefix="t")
    words = list(all_words(AB, 7))
    expected = sum(accepts(d1, w) == accepts(d2, w) for w in words)
    assert agreement_upto(d1, d2, 7) == (expected, len(words))


def test_shortest_accepted_is_shortlex_least():
    rng = random.Random(7)
    for _ in range(50):
        d = random_dfa(rng, 4)
        expected = next((w for w in all_words(AB, 8) if accepts(d, w)), None)
        assert shortest_accepted(d) == expected
