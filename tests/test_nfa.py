import json
import random
from pathlib import Path

import pytest
from helpers import AB, random_dfa

from automata.dfa import accepts, all_words, minimal_size
from automata.nfa import EPS, ENFA, epsilon_closure, left_quotient, right_quotient, subset_construction
from automata.nfa import accepts as nfa_accepts
from reference.build import random_enfa, t06_constraint_failures

ROOT = Path(__file__).resolve().parents[1]


def test_epsilon_closure_follows_chains():
    nfa = ENFA(states=["p", "q", "r"], alphabet=AB, start="p", accepting=["r"],
               transitions={"p": {EPS: ["q"]}, "q": {EPS: ["r"]}, "r": {}})
    assert epsilon_closure(nfa, ["p"]) == {"p", "q", "r"}
    assert nfa_accepts(nfa, "")  # start's closure contains the accepting state


def test_subset_construction_counts_empty_set():
    nfa = ENFA(states=["p", "q"], alphabet=AB, start="p", accepting=["q"],
               transitions={"p": {"a": ["q"]}, "q": {}})
    dfa, n = subset_construction(nfa)
    assert n == 3  # {p}, {q}, {}
    assert "{}" in dfa.states


@pytest.mark.parametrize("seed", range(100))
def test_subset_construction_matches_direct_simulation(seed):
    nfa = random_enfa(random.Random(seed), n=4)
    dfa, _ = subset_construction(nfa)
    assert all(accepts(dfa, w) == nfa_accepts(nfa, w) for w in all_words(AB, 8))


@pytest.mark.parametrize("seed", range(150))
def test_right_quotient_matches_brute_force(seed):
    rng = random.Random(500 + seed)
    m1, m2 = random_dfa(rng, rng.randint(1, 3)), random_dfa(rng, rng.randint(1, 3), prefix="r")
    q = right_quotient(m1, m2)
    # with <= 3 states each, a suitable y (if any) exists of length < 9
    ys = [y for y in all_words(AB, 8) if accepts(m2, y)]
    for x in all_words(AB, 6):
        assert accepts(q, x) == any(accepts(m1, x + y) for y in ys), x


@pytest.mark.parametrize("seed", range(150))
def test_left_quotient_matches_brute_force(seed):
    rng = random.Random(900 + seed)
    m1, m2 = random_dfa(rng, rng.randint(1, 3)), random_dfa(rng, rng.randint(1, 3), prefix="r")
    q = left_quotient(m1, m2)
    # with <= 3 states each, if some x in L(M2) reaches a given M1 state, a short one does (< 9)
    xs = [x for x in all_words(AB, 8) if accepts(m2, x)]
    for y in all_words(AB, 6):
        assert accepts(q, y) == any(accepts(m1, x + y) for x in xs), y


def test_left_quotient_of_empty_language_is_empty():
    rng = random.Random(1)
    m1 = random_dfa(rng, 3)
    m2 = random_dfa(rng, 2, prefix="r").model_copy(update={"accepting": []})
    q = left_quotient(m1, m2)
    assert not any(accepts(q, y) for y in all_words(AB, 6))


def test_task06_instance_meets_generator_constraints():
    task = json.loads((ROOT / "tasks" / "task_06_enfa_minimal_dfa.json").read_text(encoding="utf-8"))
    nfa = ENFA(**task["instance"]["nfa"])
    assert t06_constraint_failures(nfa) == []
    dfa, n = subset_construction(nfa)
    assert minimal_size(dfa) < n  # minimization must merge something
