"""Recompute every number quoted in the docs and task prompts from first principles.

    python scripts/verify_specs.py      # prints a table; exit 1 on any mismatch

EXPECTED holds the values the docs quote. Each is recomputed here; when a doc and this
script disagree, the computed value wins and the doc must be fixed (CLAUDE.md rule 1).
Besides the headline numbers, it re-runs brute-force cross-checks, re-asserts the
generator constraints on the task files, checks that every reference answer scores 1.0,
and that tasks/ and reference/ are up to date with scripts/generate_instances.py.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import check_task08_noncf  # noqa: E402
import generate_instances  # noqa: E402
from automata.cfg import check_upto, enumerate_upto  # noqa: E402
from automata.dfa import DFA, accepts, all_words, minimal_size  # noqa: E402
from automata.nfa import ENFA, left_quotient, states_reached_by_language, subset_construction  # noqa: E402
from automata.nfa import accepts as nfa_accepts  # noqa: E402
from automata.regex import ast_matches, parse, to_python_regex  # noqa: E402
from graders import oracles  # noqa: E402
from graders.grader import grade_answer, load_reference, reference_dfa  # noqa: E402
from reference import build  # noqa: E402

EXPECTED = {
    "T01 minimal DFA states": 21,
    "T01 naive product states (counter x minimal pattern/suffix DFA)": 30,
    "T02 minimal DFA states (A-window 4, B-window 3)": 16,
    "T03 M1 states reachable by words of L(M2)": 3,
    "T03 reachable subsets of the left quotient": 14,
    "T03 minimal left-quotient DFA states": 13,
    "T04 minimal DFA states": 14,
    "T04 naive (value x 3^k x parity) DFA states": 84,
    "T05 shortest distinguishing word length": 16,
    "T05 number of shortest distinguishing words": 1,
    "T05 alternative pair: shortest witness length": 14,
    "T06 reachable subsets (incl. empty set)": 17,
    "T06 minimal DFA states": 16,
    "T07 words by length 2,4,...,16": [1, 3, 11, 43, 175, 734, 3151, 13778],
    "T08 words of length <= 30": 63,
    "T08 words of length <= 36": 92,
}


def load_task(stem: str) -> dict:
    return json.loads((ROOT / "tasks" / f"{stem}.json").read_text(encoding="utf-8"))


def brute_mismatches(dfa: DFA, member, max_len: int) -> int:
    return sum(accepts(dfa, w) != member(w) for w in all_words(dfa.alphabet, max_len))


def compute() -> tuple[dict, list[str]]:
    """Returns (computed values keyed like EXPECTED, list of failed side checks)."""
    got: dict = {}
    problems: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            problems.append(msg)

    # --- T01
    t01 = build.t01_construction()
    got["T01 minimal DFA states"] = minimal_size(t01)
    got["T01 naive product states (counter x minimal pattern/suffix DFA)"] = build.t01_naive_product_size()
    check(brute_mismatches(t01, build.t01_member, 12) == 0, "T01 construction disagrees with the definition (len <= 12)")

    # --- T02
    t02 = build.t02_construction()
    got["T02 minimal DFA states (A-window 4, B-window 3)"] = minimal_size(t02)
    check(brute_mismatches(t02, build.t02_member, 9) == 0, "T02 construction disagrees with the definition (len <= 9)")

    # --- T03
    inst = load_task("task_03_left_quotient")["instance"]
    m1, m2 = DFA(**inst["m1"]), DFA(**inst["m2"])
    check(build.t03_constraint_failures(m1, m2) == [], f"T03 constraints: {build.t03_constraint_failures(m1, m2)}")
    got["T03 M1 states reachable by words of L(M2)"] = len(states_reached_by_language(m1, m2))
    got["T03 reachable subsets of the left quotient"] = len(left_quotient(m1, m2).states)
    quotient = build.t03_reference(m1, m2)
    got["T03 minimal left-quotient DFA states"] = len(quotient.states)
    m2_words = [x for x in all_words(["a", "b"], 10) if accepts(m2, x)]
    sanity = sum(
        accepts(quotient, y) != any(accepts(m1, x + y) for x in m2_words) for y in all_words(["a", "b"], 8)
    )
    check(sanity == 0, f"T03 quotient disagrees with bounded oracle (|x|<=10, |y|<=8) on {sanity} words")

    # --- T04
    t04 = build.t04_construction()
    got["T04 minimal DFA states"] = minimal_size(t04)
    naive = build.t04_naive_construction()
    got["T04 naive (value x 3^k x parity) DFA states"] = len(naive.states)
    check(brute_mismatches(t04, build.t04_member, 8) == 0, "T04 construction disagrees with the definition (len <= 8)")
    check(brute_mismatches(naive, build.t04_member, 8) == 0, "T04 naive construction disagrees with the definition")
    check(minimal_size(naive) == minimal_size(t04), "T04 naive construction does not minimize to the same size")

    # --- T05: product BFS vs two independent matchers on every word up to the witness length
    params = load_task("task_05_regex_witness")["grader"]["params"]
    r1, r2 = params["r1"], params["r2"]
    witness = build.t05_shortest_witness(build.RegexPair(r1, r2, "", ""))
    got["T05 shortest distinguishing word length"] = len(witness)
    ast1, ast2 = parse(r1, ["a", "b"]), parse(r2, ["a", "b"])
    py1, py2 = re.compile(to_python_regex(ast1)), re.compile(to_python_regex(ast2))
    diffs = []
    for w in all_words(["a", "b"], len(witness)):
        m_ast = (ast_matches(ast1, w), ast_matches(ast2, w))
        m_py = (bool(py1.fullmatch(w)), bool(py2.fullmatch(w)))
        check(m_ast == m_py, f"T05 matchers disagree on {w!r}")
        if m_ast[0] != m_ast[1]:
            diffs.append(w)
    check(bool(diffs) and len(diffs[0]) == len(witness), "T05 brute force min length != BFS min length")
    got["T05 number of shortest distinguishing words"] = len(diffs)
    check(diffs == [witness], "T05 brute force: the shortest witness is not the BFS one")
    check(len(witness) >= build.T05_MIN_WITNESS_LEN, "T05 regexes differ on a word that is too short")
    got["T05 alternative pair: shortest witness length"] = len(build.t05_shortest_witness(build.T05_ALT_PAIR))

    # --- T06
    nfa = ENFA(**load_task("task_06_enfa_minimal_dfa")["instance"]["nfa"])
    det, n_subsets = subset_construction(nfa)
    got["T06 reachable subsets (incl. empty set)"] = n_subsets
    got["T06 minimal DFA states"] = minimal_size(det)
    check(build.t06_constraint_failures(nfa) == [], f"T06 constraints: {build.t06_constraint_failures(nfa)}")
    check(brute_mismatches(det, lambda w: nfa_accepts(nfa, w), 10) == 0, "T06 subset DFA disagrees with NFA simulation")

    # --- T07: enumeration vs the predicate on every word, reference grammar exact up to N
    br = ["(", ")", "[", "]"]
    by_len = oracles.t07_enumerate(16)
    got["T07 words by length 2,4,...,16"] = [len(by_len[n]) for n in range(2, 17, 2)]
    check(
        all(oracles.t07_member(w) == (w in by_len[len(w)]) for w in all_words(br, 10) if w),
        "T07 enumeration disagrees with predicate (len <= 10)",
    )
    n7 = load_task("task_07_parity_dyck_cfg")["grader"]["params"]["max_len"]
    res7 = check_upto(build.t07_reference_grammar(), br, n7, oracles.t07_member, by_len, oracles.t07_shortest_longer_than)
    check(res7.kind is None and not res7.finite_language, f"T07 reference grammar fails the bounded check: {res7}")

    # --- T08
    n8 = load_task("task_08_ratio_cfg")["grader"]["params"]["max_len"]
    by_len8 = oracles.t08_enumerate(n8)
    got["T08 words of length <= 30"] = sum(len(by_len8[n]) for n in range(1, 31))
    got["T08 words of length <= 36"] = sum(len(v) for v in by_len8.values())
    check(
        all(oracles.t08_member(w) == (w in by_len8[len(w)]) for w in all_words(["a", "b"], 16) if w),
        "T08 enumeration disagrees with predicate (len <= 16)",
    )
    gen8, capped = enumerate_upto(build.t08_reference_grammar(), ["a", "b"], 24)
    check(not capped and all(gen8[n] == by_len8[n] for n in range(1, 25)), "T08 reference grammar != language up to 24")
    res8 = check_upto(build.t08_reference_grammar(), ["a", "b"], n8, oracles.t08_member, by_len8, oracles.t08_shortest_longer_than)
    check(res8.kind is None and not res8.finite_language, f"T08 reference grammar fails the bounded check: {res8}")
    noncf = check_task08_noncf.run()
    check(all(v == 0 for v in noncf.values()), f"original T08 survived pumping for some N: {noncf}")

    # --- every reference answer scores 1.0 through the real grader
    for stem in generate_instances.TASK_BUILDERS:
        task = load_task(stem)
        res = grade_answer(task, load_reference(task["id"])["answer"])
        check(res.score == 1.0, f"{task['id']}: reference scored {res.score} ({res.failure_code})")
        if task["grader"]["type"] == "dfa_exact":
            check(len(reference_dfa(task).states) == minimal_size(reference_dfa(task)), f"{task['id']}: reference not minimal")

    # --- files up to date
    stale = [p for p, text in generate_instances.render_all().items() if p.read_text(encoding="utf-8") != text]
    check(not stale, f"stale generated files: {[str(p.relative_to(ROOT)) for p in stale]}")

    # --- every DFA-task example in the prompt agrees with the reference
    for stem in generate_instances.TASK_BUILDERS:
        task = load_task(stem)
        if task["grader"]["type"] != "dfa_exact":
            continue
        ref = reference_dfa(task)
        for w in task["examples"]["in"]:
            check(accepts(ref, w), f"{task['id']}: example {w!r} should be in L")
        for w in task["examples"]["out"]:
            check(not accepts(ref, w), f"{task['id']}: example {w!r} should not be in L")
    return got, problems


def main() -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):  # Windows consoles default to cp1252 (no ε)
        sys.stdout.reconfigure(encoding="utf-8")
    got, problems = compute()
    width = max(len(k) for k in EXPECTED)
    mismatches = 0
    print(f"{'quantity'.ljust(width)} | expected (docs) | computed | ok")
    for key, expected in EXPECTED.items():
        ok = got.get(key) == expected
        mismatches += not ok
        print(f"{key.ljust(width)} | {str(expected):15} | {str(got.get(key)):8} | {'yes' if ok else 'NO'}")
    for p in problems:
        print(f"SIDE CHECK FAILED: {p}")
    if mismatches or problems:
        print(f"\nverify_specs: FAILED ({mismatches} number mismatches, {len(problems)} side-check failures)")
        return 1
    print("\nverify_specs: all numbers and side checks OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
