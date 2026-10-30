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
from automata.cfg import cyk, enumerate_upto  # noqa: E402
from automata.dfa import DFA, accepts, all_words, minimal_size  # noqa: E402
from automata.nfa import ENFA, subset_construction  # noqa: E402
from automata.nfa import accepts as nfa_accepts  # noqa: E402
from automata.regex import ast_matches, parse, to_python_regex  # noqa: E402
from graders import oracles  # noqa: E402
from graders.grader import grade_answer, load_reference, reference_dfa  # noqa: E402
from reference import build  # noqa: E402

EXPECTED = {
    "T01 minimal DFA states": 10,
    "T01 naive product states (counter x minimal suffix DFA)": 14,
    "T02 minimal DFA states (W=3)": 6,
    "T02 minimal states for W=3..6": [6, 7, 8, 9],
    "T03 minimal quotient DFA states": 4,
    "T04 minimal DFA states": 14,
    "T05 shortest distinguishing word length": 10,
    "T06 reachable subsets (incl. empty set)": 11,
    "T06 minimal DFA states": 7,
    "T07 minimal truth DFA states (ε excluded)": 12,
    "T07 words by length 2,4,6,8,10": [2, 7, 29, 126, 558],
    "T08 words of length <= 14": 16,
    "T08 words of length <= 30": 100,
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
    got["T01 naive product states (counter x minimal suffix DFA)"] = build.t01_naive_product_size()
    t01_member = lambda w: w.count("0") % 3 == 1 and "010" not in w and not w.endswith("11")  # noqa: E731
    check(brute_mismatches(t01, t01_member, 12) == 0, "T01 construction disagrees with the definition (len <= 12)")

    # --- T02
    got["T02 minimal DFA states (W=3)"] = minimal_size(build.t02_construction(3))
    got["T02 minimal states for W=3..6"] = [minimal_size(build.t02_construction(w)) for w in range(3, 7)]
    for w in (3, 4):
        check(
            brute_mismatches(build.t02_construction(w), lambda s: build.t02_member(s, w), 9) == 0,
            f"T02 construction (W={w}) disagrees with the definition (len <= 9)",
        )

    # --- T03
    inst = load_task("task_03_right_quotient")["instance"]
    m1, m2 = DFA(**inst["m1"]), DFA(**inst["m2"])
    check(build.t03_constraint_failures(m1, m2) == [], f"T03 constraints: {build.t03_constraint_failures(m1, m2)}")
    quotient = build.t03_reference(m1, m2)
    got["T03 minimal quotient DFA states"] = len(quotient.states)
    m2_words = [y for y in all_words(["a", "b"], 10) if accepts(m2, y)]
    sanity = sum(
        accepts(quotient, x) != any(accepts(m1, x + y) for y in m2_words) for x in all_words(["a", "b"], 8)
    )
    check(sanity == 0, f"T03 quotient disagrees with bounded oracle (|x|<=8, |y|<=10) on {sanity} words")

    # --- T04
    t04 = build.t04_construction()
    got["T04 minimal DFA states"] = minimal_size(t04)
    check(brute_mismatches(t04, build.t04_member, 8) == 0, "T04 construction disagrees with the definition (len <= 8)")

    # --- T05: product BFS vs two independent matchers
    params = load_task("task_05_regex_witness")["grader"]["params"]
    r1, r2 = params["r1"], params["r2"]
    witness = build.t05_shortest_witness(build.RegexPair(r1, r2, "", ""))
    got["T05 shortest distinguishing word length"] = len(witness)
    ast1, ast2 = parse(r1, ["a", "b"]), parse(r2, ["a", "b"])
    py1, py2 = re.compile(to_python_regex(ast1)), re.compile(to_python_regex(ast2))
    first_diff = None
    for w in all_words(["a", "b"], 12):
        m_ast = (ast_matches(ast1, w), ast_matches(ast2, w))
        m_py = (bool(py1.fullmatch(w)), bool(py2.fullmatch(w)))
        check(m_ast == m_py, f"T05 matchers disagree on {w!r}")
        if first_diff is None and m_ast[0] != m_ast[1]:
            first_diff = w
    check(first_diff is not None and len(first_diff) == len(witness), "T05 brute force min length != BFS min length")
    check(len(witness) >= build.T05_MIN_WITNESS_LEN, "T05 regexes differ on a word shorter than 9")
    harder = build.t05_shortest_witness(build.T05_HARDER_PAIR)
    print(f"  (T05 harder alternative knob: shortest witness length {len(harder)})")

    # --- T06
    nfa = ENFA(**load_task("task_06_enfa_minimal_dfa")["instance"]["nfa"])
    det, n_subsets = subset_construction(nfa)
    got["T06 reachable subsets (incl. empty set)"] = n_subsets
    got["T06 minimal DFA states"] = minimal_size(det)
    check(build.t06_constraint_failures(nfa) == [], f"T06 constraints: {build.t06_constraint_failures(nfa)}")
    check(brute_mismatches(det, lambda w: nfa_accepts(nfa, w), 10) == 0, "T06 subset DFA disagrees with NFA simulation")

    # --- T07
    truth_dfa = oracles.t07_truth_dfa()
    got["T07 minimal truth DFA states (ε excluded)"] = minimal_size(truth_dfa)
    by_len = oracles.t07_enumerate(16)
    got["T07 words by length 2,4,6,8,10"] = [len(by_len[n]) for n in (2, 4, 6, 8, 10)]
    check(brute_mismatches(truth_dfa, oracles.t07_member, 8) == 0, "T07 truth DFA disagrees with predicate (len <= 8)")
    g7 = build.t07_reference_grammar()
    sample = sorted(by_len[8])[:40] + ["[()]", "(((())))", "(]", "[[()]]"]
    check(
        all(cyk(g7, ["(", ")", "[", "]"], w) == oracles.t07_member(w) for w in sample),
        "T07 reference grammar: CYK disagrees with predicate on a sample",
    )

    # --- T08
    by_len8 = oracles.t08_enumerate(30)
    got["T08 words of length <= 14"] = sum(len(by_len8[n]) for n in range(1, 15))
    got["T08 words of length <= 30"] = sum(len(v) for v in by_len8.values())
    check(
        all(oracles.t08_member(w) == (w in by_len8[len(w)]) for w in all_words(["a", "b"], 14) if w),
        "T08 enumeration disagrees with predicate (len <= 14)",
    )
    gen8, capped = enumerate_upto(build.t08_reference_grammar(), ["a", "b"], 18)
    check(not capped and all(gen8[n] == by_len8[n] for n in range(1, 19)), "T08 reference grammar != language up to 18")
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
