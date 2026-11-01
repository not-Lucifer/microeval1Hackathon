"""scripts/review_checks.py: its own helpers on tiny cases, and every review check passing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import review_checks as rc  # noqa: E402

EVEN_AS = rc.build_dfa(["a", "b"], 0, lambda q, x: q ^ (x == "a"), lambda q: q == 0)
NO_AS = rc.build_dfa(["a", "b"], 0, lambda q, x: 1 if x == "a" else q, lambda q: q == 0)


def test_own_dfa_helpers():
    assert rc.shortest_difference(EVEN_AS, EVEN_AS) is None
    assert rc.shortest_difference(EVEN_AS, NO_AS) == "aa"
    bloated = {"states": ["e", "o", "e2"], "start": "e", "accepting": ["e", "e2"],
               "transitions": {"e": {"a": "o", "b": "e2"}, "o": {"a": "e", "b": "o"}, "e2": {"a": "o", "b": "e"}}}
    assert rc.own_dfa_score(bloated, EVEN_AS) == (0.5, None)
    del bloated["transitions"]["e2"]["b"]
    assert rc.own_dfa_score(bloated, EVEN_AS) == (0.0, None)


def test_own_grammar_helpers():
    anbn = {"start": "S", "productions": [{"lhs": "S", "rhs": ["A", "B"]}, {"lhs": "S", "rhs": ["A", "T"]},
                                          {"lhs": "T", "rhs": ["S", "B"]}, {"lhs": "A", "rhs": ["a"]},
                                          {"lhs": "B", "rhs": ["b"]}]}
    assert rc.by_length(anbn, 6) == {1: set(), 2: {"ab"}, 3: set(), 4: {"aabb"}, 5: set(), 6: {"aaabbb"}}
    assert rc.cyk(anbn, "aabb") and not rc.cyk(anbn, "abab")
    assert rc.is_infinite(anbn)
    assert not rc.is_infinite({"start": "S", "productions": anbn["productions"][:1] + anbn["productions"][3:]})
    assert rc.cnf_problems({"start": "S", "productions": [{"lhs": "S", "rhs": ["a", "B"]}]}, ["a", "b"])


def test_own_definitions_on_prompt_examples():
    assert rc.t07_member("([][])") and not rc.t07_member("[[]]") and not rc.t07_member("(]")
    assert rc.t08_member("aba") and not rc.t08_member("abaa")
    assert rc.t02_member("abcba") and not rc.t02_member("abca")


def test_every_review_check_passes():
    failed = [(name, detail) for name, results in rc.all_checks() for ok, detail in results if not ok]
    assert failed == []
