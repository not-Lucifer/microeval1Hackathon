"""Grader validation protocol (PROJECT_GUIDE §7.5): every reference scores 1.0 and every
deliberately wrong answer (mutant) gets the expected failure code."""
import copy

import pytest
from helpers import load_task_files

from automata.cfg import Grammar
from automata.dfa import DFA, accepts
from graders.failure_codes import FailureCode as F
from graders.grader import grade_answer, load_reference, reference_dfa
from graders.oracles import t07_member, t08_enumerate, t08_member

TASKS = {t["id"]: t for t in load_task_files()}
DFA_TASKS = [tid for tid, t in TASKS.items() if t["grader"]["type"] == "dfa_exact"]


def ref_answer(tid: str) -> dict:
    return copy.deepcopy(load_reference(tid)["answer"])


def grade(tid: str, answer) -> tuple:
    res = grade_answer(TASKS[tid], answer)
    return res.score, res.failure_code, res


def assert_genuine_counterexample(tid: str, answer: dict, cex: str) -> None:
    model = DFA(alphabet=TASKS[tid]["grader"]["params"]["alphabet"], **answer)
    assert accepts(model, cex) != accepts(reference_dfa(TASKS[tid]), cex)


@pytest.mark.parametrize("tid", sorted(TASKS))
def test_reference_scores_one(tid):
    score, code, _ = grade(tid, ref_answer(tid))
    assert (score, code) == (1.0, None)


# --------------------------------------------------------------------------- DFA mutants


@pytest.mark.parametrize("tid", DFA_TASKS)
def test_renaming_all_states_still_passes(tid):
    a = ref_answer(tid)
    m = {q: f"Z{i}_{q}" for i, q in enumerate(a["states"])}
    renamed = {
        "states": [m[q] for q in reversed(a["states"])],
        "start": m[a["start"]],
        "accepting": [m[q] for q in a["accepting"]],
        "transitions": {m[q]: {s: m[r] for s, r in row.items()} for q, row in a["transitions"].items()},
    }
    assert grade(tid, renamed)[:2] == (1.0, None)


@pytest.mark.parametrize("tid", DFA_TASKS)
def test_flipping_any_accepting_state_fails(tid):
    a = ref_answer(tid)
    for q in a["states"]:
        m = copy.deepcopy(a)
        m["accepting"] = [s for s in a["accepting"] if s != q] if q in a["accepting"] else a["accepting"] + [q]
        score, code, res = grade(tid, m)
        assert (score, code) == (0.0, F.NOT_EQUIVALENT), q
        assert_genuine_counterexample(tid, m, res.counterexample)


@pytest.mark.parametrize("tid", DFA_TASKS)
def test_redirecting_any_transition_fails(tid):
    a = ref_answer(tid)
    for q in a["states"]:
        for sym, target in a["transitions"][q].items():
            others = [s for s in a["states"] if s != target]
            m = copy.deepcopy(a)
            m["transitions"][q][sym] = others[0]
            score, code, res = grade(tid, m)
            assert (score, code) == (0.0, F.NOT_EQUIVALENT), (q, sym)
            assert_genuine_counterexample(tid, m, res.counterexample)


@pytest.mark.parametrize("tid", DFA_TASKS)
def test_deleting_a_transition_is_incomplete(tid):
    m = ref_answer(tid)
    q = m["states"][-1]
    del m["transitions"][q][sorted(m["transitions"][q])[0]]
    assert grade(tid, m)[:2] == (0.0, F.INCOMPLETE_DFA)


@pytest.mark.parametrize("tid", DFA_TASKS)
def test_duplicate_equivalent_state_scores_half(tid):
    m = ref_answer(tid)
    # clone the target of the start state's first transition and route that edge to the clone
    sym = sorted(m["transitions"][m["start"]])[0]
    target = m["transitions"][m["start"]][sym]
    m["states"].append("CLONE")
    m["transitions"]["CLONE"] = dict(m["transitions"][target])
    if target in m["accepting"]:
        m["accepting"].append("CLONE")
    m["transitions"][m["start"]][sym] = "CLONE"
    score, code, res = grade(tid, m)
    assert (score, code) == (0.5, F.NON_MINIMAL_STATE_BLOAT)
    assert res.details["states_given"] == res.details["states_minimal"] + 1


@pytest.mark.parametrize("tid", DFA_TASKS)
def test_unreachable_state_scores_half(tid):
    m = ref_answer(tid)
    m["states"].append("ISLAND")
    m["transitions"]["ISLAND"] = {s: "ISLAND" for s in TASKS[tid]["grader"]["params"]["alphabet"]}
    score, code, res = grade(tid, m)
    assert (score, code) == (0.5, F.NON_MINIMAL_STATE_BLOAT)
    assert res.details["unreachable_states"] == 1


@pytest.mark.parametrize("tid", DFA_TASKS)
def test_swapping_two_states_behaviour_fails(tid):
    m = ref_answer(tid)
    acc = m["accepting"][0]
    rej = next(q for q in m["states"] if q not in m["accepting"])
    m["accepting"] = [rej if q == acc else q for q in m["accepting"]]
    assert grade(tid, m)[:2] == (0.0, F.NOT_EQUIVALENT)


@pytest.mark.parametrize("tid", ["task_01", "task_02"])
def test_dropping_the_trap_state_is_incomplete(tid):
    m = ref_answer(tid)
    trap = next(q for q in m["states"] if q not in m["accepting"] and set(m["transitions"][q].values()) == {q})
    m["states"].remove(trap)
    del m["transitions"][trap]
    for row in m["transitions"].values():
        for s in [s for s, r in row.items() if r == trap]:
            del row[s]
    score, code, res = grade(tid, m)
    assert (score, code) == (0.0, F.INCOMPLETE_DFA)
    assert res.details["language_correct_if_missing_go_to_trap"] is True


@pytest.mark.parametrize(
    "patch",
    [
        {"start": "nope"},
        {"accepting": ["nope"]},
        {"states": ["dup", "dup"]},
    ],
)
def test_structurally_invalid_dfa(patch):
    m = {**ref_answer("task_04"), **patch}
    assert grade("task_04", m)[:2] == (0.0, F.INVALID_DFA)


def test_unknown_symbol_and_unknown_target_are_invalid():
    m = ref_answer("task_04")
    m["transitions"][m["start"]]["9"] = m["start"]
    assert grade("task_04", m)[1] == F.INVALID_DFA
    m = ref_answer("task_04")
    m["transitions"][m["start"]]["0"] = "nowhere"
    assert grade("task_04", m)[1] == F.INVALID_DFA


@pytest.mark.parametrize("bad", [{}, {"states": "q0"}, [], "text", {"states": [], "start": 3, "accepting": [], "transitions": {}}])
def test_schema_violations_are_parse_errors(bad):
    assert grade("task_01", bad)[:2] == (0.0, F.PARSE_ERROR)


# --------------------------------------------------------------------------- witness mutants


@pytest.mark.parametrize(
    "witness, expected",
    [
        ("bababbabaa", (1.0, None)),
        ("babababaa", (0.0, F.WITNESS_NOT_DISTINGUISHING)),  # the obvious guess: matched by both
        ("ab", (0.0, F.WITNESS_NOT_DISTINGUISHING)),  # matched by neither
        ("", (0.0, F.WITNESS_NOT_DISTINGUISHING)),
        ("bababbbabaa", (0.5, F.WITNESS_NOT_SHORTEST)),  # distinguishing, length 11
        ("bababbabac", (0.0, F.INVALID_WITNESS)),
    ],
)
def test_witness_grader(witness, expected):
    score, code, res = grade("task_05", {"witness": witness})
    assert (score, code) == expected
    if code is not None:
        assert res.counterexample == "bababbabaa"  # a correct shortest witness, for diagnosis


@pytest.mark.parametrize("bad", [{"witness": 5}, {"word": "ab"}, ["ab"]])
def test_witness_schema_errors(bad):
    assert grade("task_05", bad)[:2] == (0.0, F.PARSE_ERROR)


# --------------------------------------------------------------------------- grammar mutants


def productions(tid: str) -> list[dict]:
    return ref_answer(tid)["productions"]


@pytest.mark.parametrize("tid", ["task_07", "task_08"])
def test_dropping_any_production_undergenerates(tid):
    prods = productions(tid)
    member = t07_member if tid == "task_07" else t08_member
    for i in range(len(prods)):
        m = {"start": ref_answer(tid)["start"], "productions": prods[:i] + prods[i + 1 :]}
        score, code, res = grade(tid, m)
        assert (score, code) == (0.0, F.UNDERGENERATES), prods[i]
        assert member(res.counterexample)


@pytest.mark.parametrize(
    "tid, extra, shortest_len",
    [
        ("task_07", {"lhs": "B2", "rhs": ["LP", "RP"]}, 4),  # allows [()]
        ("task_07", {"lhs": "A1", "rhs": ["LP", "X2"]}, 8),  # allows depth 4
        ("task_08", {"lhs": "S", "rhs": ["TA", "TA"]}, 2),  # aa
        ("task_08", {"lhs": "A1", "rhs": ["TA", "TB"]}, 5),  # A1 -> ab: S -> A1 B1 gives abbaa
    ],
)
def test_overgenerating_production(tid, extra, shortest_len):
    m = ref_answer(tid)
    m["productions"].append(extra)
    score, code, res = grade(tid, m)
    member = t07_member if tid == "task_07" else t08_member
    assert (score, code) == (0.0, F.OVERGENERATES)
    assert not member(res.counterexample) and len(res.counterexample) == shortest_len


@pytest.mark.parametrize(
    "tid, extra",
    [
        ("task_07", {"lhs": "A3", "rhs": ["A2"]}),  # unit production
        ("task_08", {"lhs": "S", "rhs": []}),  # epsilon production
        ("task_08", {"lhs": "S", "rhs": ["a", "B1"]}),  # mixed
        ("task_08", {"lhs": "S", "rhs": ["TA", "TB", "TA"]}),  # too long
    ],
)
def test_cnf_violations_score_zero(tid, extra):
    m = ref_answer(tid)
    m["productions"].append(extra)
    assert grade(tid, m)[:2] == (0.0, F.CNF_VIOLATION)


def chain(nonterminal: str, word: str, tag: str) -> list[dict]:
    """CNF productions making ``nonterminal`` derive exactly ``word`` (len >= 2)."""
    prods, cur = [], nonterminal
    for i, ch in enumerate(word[:-2]):
        nxt = f"{tag}_{i}"
        prods.append({"lhs": cur, "rhs": [f"T_{ch}", nxt]})
        cur = nxt
    prods.append({"lhs": cur, "rhs": [f"T_{word[-2]}", f"T_{word[-1]}"]})
    return prods


TERMS = [{"lhs": "T_a", "rhs": ["a"]}, {"lhs": "T_b", "rhs": ["b"]}]


def test_finite_list_of_all_words_up_to_n_fails():
    """Anti-gaming: listing every word of L up to N = 30 must not pass."""
    words = sorted(w for s in t08_enumerate(30).values() for w in s)
    prods = TERMS + [p for i, w in enumerate(words) for p in chain("S", w, f"W{i}")]
    score, code, res = grade("task_08", {"start": "S", "productions": prods})
    assert (score, code) == (0.0, F.UNDERGENERATES)
    assert res.details["finite_language"] is True and len(res.counterexample) == 33


def doubling_chain(k: int) -> list[dict]:
    """S -> P_k P_k with P_i -> P_(i-1) P_(i-1): derives a^(2^(k+2)), astronomically long."""
    prods = [{"lhs": "P0", "rhs": ["TA", "TA"]}]
    prods += [{"lhs": f"P{i}", "rhs": [f"P{i - 1}", f"P{i - 1}"]} for i in range(1, k + 1)]
    return prods + [{"lhs": "S", "rhs": [f"P{k}", f"P{k}"]}]


def test_grader_memory_does_not_depend_on_long_strings():
    """Regression: shortest strings used to be built literally, so a 30-rule doubling chain
    needed ~31 GB. Now nothing longer than N is materialized."""
    m = ref_answer("task_08")
    m["productions"] += doubling_chain(200)
    assert grade("task_08", m)[:2] == (1.0, None)  # the extra word is far beyond N


def test_finite_grammar_with_huge_longest_word():
    words = sorted(w for s in t08_enumerate(30).values() for w in s)
    prods = TERMS + [{"lhs": "TA", "rhs": ["a"]}] + [p for i, w in enumerate(words) for p in chain("S", w, f"W{i}")]
    score, code, res = grade("task_08", {"start": "S", "productions": prods + doubling_chain(200)})
    assert (score, code) == (0.0, F.UNDERGENERATES)
    assert res.details["finite_language"] is True
    assert res.counterexample is None  # exists, but is too long to store (noted in details)


def test_bounded_guarantee_is_honest():
    """Documents the limitation: an error that only shows beyond N (= 30) is NOT caught.
    The extra word a^33 is outside L but longer than N, so the grammar passes."""
    m = ref_answer("task_08")
    m["productions"] += TERMS + chain("S", "a" * 33, "LONG")
    assert grade("task_08", m)[:2] == (1.0, None)
    assert not t08_member("a" * 33)
    assert Grammar.model_validate(m)  # still a well-formed grammar
