"""Grader verdicts vs exhaustive enumeration on small random instances (PROJECT_GUIDE §7.5.3)."""
import random

import pytest
from helpers import AB, brute_first_difference, brute_nerode_count, random_dfa

from automata.cfg import Grammar, Production, check_upto, cyk
from automata.dfa import all_words, complete, minimize, remove_unreachable
from automata.regex import ast_matches, parse
from graders.answers import DFAAnswer, WitnessAnswer
from graders.dfa_grader import grade_dfa
from graders.failure_codes import FailureCode as F
from graders.oracles import t07_enumerate, t07_member, t08_enumerate, t08_member
from graders.witness_grader import grade_witness
from reference.build import t07_reference_grammar, t08_reference_grammar
from test_regex import random_regex


@pytest.mark.parametrize("seed", range(300))
def test_dfa_grader_vs_brute_force(seed):
    rng = random.Random(seed)
    ref = minimize(random_dfa(rng, rng.randint(1, 3)))
    cand = random_dfa(rng, rng.randint(1, 4), prefix="c")
    res = grade_dfa(DFAAnswer(**cand.model_dump(exclude={"alphabet"})), ref)
    diff = brute_first_difference(cand, ref, 12)  # n1*n2 <= 12 bounds the shortest difference
    if diff is not None:
        assert (res.score, res.failure_code, res.counterexample) == (0.0, F.NOT_EQUIVALENT, diff)
    elif len(cand.states) == brute_nerode_count(remove_unreachable(complete(ref))):
        assert (res.score, res.failure_code) == (1.0, None)
    else:
        assert (res.score, res.failure_code) == (0.5, F.NON_MINIMAL_STATE_BLOAT)


@pytest.mark.parametrize("seed", range(150))
def test_witness_grader_vs_brute_force(seed):
    rng = random.Random(seed)
    r1, r2 = random_regex(rng, 3), random_regex(rng, 3)
    a1, a2 = parse(r1, AB), parse(r2, AB)
    words = list(all_words(AB, 9))
    differing = [w for w in words if ast_matches(a1, w) != ast_matches(a2, w)]
    if not differing:
        pytest.skip("pair equivalent up to length 9")
    shortest = len(differing[0])
    for w in rng.sample(words, 40) + differing[:3]:
        res = grade_witness(WitnessAnswer(witness=w), r1, r2, AB)
        if ast_matches(a1, w) == ast_matches(a2, w):
            expected = (0.0, F.WITNESS_NOT_DISTINGUISHING)
        elif len(w) == shortest:
            expected = (1.0, None)
        else:
            expected = (0.5, F.WITNESS_NOT_SHORTEST)
        assert (res.score, res.failure_code) == expected, (r1, r2, w)


def mutate(grammar: Grammar, rng: random.Random) -> Grammar:
    """Drop one production and/or add one random production."""
    prods = list(grammar.productions)
    nts = sorted({p.lhs for p in prods})
    if rng.random() < 0.5:
        prods.pop(rng.randrange(len(prods)))
    if rng.random() < 0.7:
        prods.append(Production(lhs=rng.choice(nts), rhs=[rng.choice(nts), rng.choice(nts)]))
    return Grammar(start=grammar.start, productions=prods)


@pytest.mark.parametrize("seed", range(60))
def test_cfg_check_vs_cyk_on_mutated_t08(seed):
    rng = random.Random(seed)
    gr, n = mutate(t08_reference_grammar(), rng), 10
    res = check_upto(gr, ["a", "b"], n, t08_member, t08_enumerate(n), lambda k: None)
    mism = [w for w in all_words(["a", "b"], n) if w and cyk(gr, ["a", "b"], w) != t08_member(w)]
    if not mism:
        assert res.kind is None
    else:
        assert len(res.counterexample) == len(mism[0])
        assert cyk(gr, ["a", "b"], res.counterexample) != t08_member(res.counterexample)


@pytest.mark.parametrize("seed", range(40))
def test_cfg_check_vs_cyk_on_mutated_t07(seed):
    rng = random.Random(seed)
    br = ["(", ")", "[", "]"]
    gr, n = mutate(t07_reference_grammar(), rng), 6
    res = check_upto(gr, br, n, t07_member, t07_enumerate(n), lambda k: None)
    mism = [w for w in all_words(br, n) if w and cyk(gr, br, w) != t07_member(w)]
    if not mism:
        assert res.kind is None
    else:
        assert len(res.counterexample) == len(mism[0])
        assert cyk(gr, br, res.counterexample) != t07_member(res.counterexample)
