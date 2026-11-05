"""Independent re-checks behind the rows of docs/REVIEW_LOG.md.

    python scripts/review_checks.py          # about a minute; exit 1 if any check fails

Each check re-does one review row with code written separately from the project. The
automata, grammars and language definitions in this file use only the standard library and
the task files, never automata/, graders/ or reference/build.py, so a mistake shared by the
project and this file would have to be made twice. Project code appears only as the thing
under test (graders, left-quotient engine, parser, chat-app import, regrade guard).

These are machine checks run by Claude Code at the author's request. They are not the
author's review by hand, and docs/REVIEW_LOG.md says which is which.
"""
from __future__ import annotations

import itertools
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from functools import lru_cache
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AB, ABC, DIGITS = ["a", "b"], ["a", "b", "c"], ["0", "1", "2"]
BRACKETS = ["(", ")", "[", "]"]


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


TASKS = {t["id"]: t for t in (load(str(p.relative_to(ROOT))) for p in sorted((ROOT / "tasks").glob("task_*.json")))}
REF = {tid: load(f"reference/{tid}.ref.json")["answer"] for tid in TASKS}


def words(alphabet: list[str], max_len: int):
    """Every word over the alphabet of length 0..max_len, shortest first."""
    for n in range(max_len + 1):
        for t in itertools.product(alphabet, repeat=n):
            yield "".join(t)


# ============================================================ DFAs (own code)
# A DFA here is {"alphabet", "start", "accepting": set, "trans": {state: {symbol: state}}}.

def build_dfa(alphabet: list[str], start, step: Callable, accept: Callable) -> dict:
    """The DFA of all states reachable from start by BFS, where step(state, symbol) -> state."""
    trans: dict = {start: {}}
    todo = deque([start])
    while todo:
        q = todo.popleft()
        for x in alphabet:
            r = step(q, x)
            trans[q][x] = r
            if r not in trans:
                trans[r] = {}
                todo.append(r)
    return {"alphabet": alphabet, "start": start, "accepting": {q for q in trans if accept(q)}, "trans": trans}


def answer_dfa(answer: dict, alphabet: list[str]) -> dict:
    return {"alphabet": alphabet, "start": answer["start"], "accepting": set(answer["accepting"]),
            "trans": answer["transitions"]}


def is_complete(answer: dict, alphabet: list[str]) -> bool:
    """Every listed state has exactly one move per symbol, to a listed state."""
    states = set(answer["states"])
    rows = answer["transitions"]
    return (answer["start"] in states and set(answer["accepting"]) <= states
            and all(q in rows and set(rows[q]) == set(alphabet) and set(rows[q].values()) <= states
                    for q in states))


def run(d: dict, w: str):
    q = d["start"]
    for x in w:
        q = d["trans"][q][x]
    return q


def accepts(d: dict, w: str) -> bool:
    return run(d, w) in d["accepting"]


def shortest_difference(d1: dict, d2: dict) -> Optional[str]:
    """Shortlex-first word accepted by exactly one of two complete DFAs (BFS on the product), or None."""
    start = (d1["start"], d2["start"])
    seen, todo = {start: ""}, deque([start])
    while todo:
        p = todo.popleft()
        if (p[0] in d1["accepting"]) != (p[1] in d2["accepting"]):
            return seen[p]
        for x in sorted(d1["alphabet"]):
            r = (d1["trans"][p[0]][x], d2["trans"][p[1]][x])
            if r not in seen:
                seen[r] = seen[p] + x
                todo.append(r)
    return None


def reachable(d: dict) -> list:
    seen, todo = {d["start"]}, deque([d["start"]])
    while todo:
        q = todo.popleft()
        for x in d["alphabet"]:
            r = d["trans"][q][x]
            if r not in seen:
                seen.add(r)
                todo.append(r)
    return list(seen)


def moore_blocks(d: dict) -> dict:
    """Equivalence class of every reachable state (Moore refinement until stable)."""
    states = reachable(d)
    block = {q: (q in d["accepting"],) for q in states}
    while True:
        sig = {q: (block[q],) + tuple(block[d["trans"][q][x]] for x in d["alphabet"]) for q in states}
        if len(set(sig.values())) == len(set(block.values())):
            return block
        block = sig


def minimal_size(d: dict) -> int:
    return len(set(moore_blocks(d).values()))


def minimized(d: dict) -> dict:
    """The minimal DFA: one state per Moore class, moves taken from any member of the class."""
    blocks = moore_blocks(d)
    member = {b: q for q, b in blocks.items()}
    return build_dfa(d["alphabet"], blocks[d["start"]], lambda b, x: blocks[d["trans"][member[b]][x]],
                     lambda b: member[b] in d["accepting"])


def own_dfa_score(answer: dict, oracle: dict) -> tuple[float, Optional[str]]:
    """The score the prompt's rules give: 0 if incomplete or a different language, 0.5 if right but
    with more listed states than the minimum, else 1.0; plus the shortest counterexample."""
    if not is_complete(answer, oracle["alphabet"]):
        return 0.0, None
    cex = shortest_difference(answer_dfa(answer, oracle["alphabet"]), oracle)
    if cex is not None:
        return 0.0, cex
    return (1.0 if len(answer["states"]) == minimal_size(oracle) else 0.5), None


# ============================================================ the eight languages, read from the prompts

def t01_member(w: str) -> bool:
    return w.count("0") % 3 == 1 and "0101" not in w and len(w) >= 3 and w[-3] == "1"


def t01_dfa() -> dict:
    """State (number of 0s mod 3, last three symbols), or 'dead' once 0101 has occurred."""
    def step(q, x):
        if q == "dead":
            return q
        zeros, last = q
        if (last + x).endswith("0101"):
            return "dead"
        return ((zeros + (x == "0")) % 3, (last + x)[-3:])
    return build_dfa(["0", "1"], (0, ""), step,
                     lambda q: q != "dead" and q[0] == 1 and len(q[1]) == 3 and q[1][0] == "1")


def t02_member(w: str) -> bool:
    for i, ch in enumerate(w):
        if ch == "a" and not (i > 0 and w[i - 1] == "b") and "c" not in w[i + 1:i + 5]:
            return False
        if ch == "b" and "a" not in w[i + 1:i + 4]:
            return False
    return True


def t02_dfa() -> dict:
    """State (symbols left for the earliest open a-obligation to see a c, the same for the earliest
    open b-obligation to see an a, last symbol was b); None = no open obligation. A later deadline
    of the same kind never matters while an earlier one is open: the symbol that meets the earlier
    one meets it too."""
    def step(q, x):
        if q == "dead":
            return q
        a_left, b_left, _ = q
        if a_left is not None:
            a_left = None if x == "c" else a_left - 1
        if b_left is not None:
            b_left = None if x == "a" else b_left - 1
        if a_left == 0 or b_left == 0:
            return "dead"
        if x == "a" and not q[2] and a_left is None:
            a_left = 4
        if x == "b" and b_left is None:
            b_left = 3
        return (a_left, b_left, x == "b")
    return build_dfa(ABC, (None, None, False), step, lambda q: q != "dead" and q[0] is None and q[1] is None)


def t03_start_set() -> frozenset:
    """S = states of M1 reached by words of L(M2): BFS over pairs (M1 state, M2 state)."""
    m1, m2 = TASKS["task_03"]["instance"]["m1"], TASKS["task_03"]["instance"]["m2"]
    start = (m1["start"], m2["start"])
    seen, todo = {start}, deque([start])
    while todo:
        p, r = todo.popleft()
        for x in AB:
            nxt = (m1["transitions"][p][x], m2["transitions"][r][x])
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return frozenset(p for p, r in seen if r in m2["accepting"])


def t03_dfa() -> dict:
    """M1 started in any state of S, determinized by subsets of M1's states."""
    m1 = TASKS["task_03"]["instance"]["m1"]
    return build_dfa(AB, t03_start_set(), lambda T, x: frozenset(m1["transitions"][q][x] for q in T),
                     lambda T: bool(T & set(m1["accepting"])))


def t04_member(w: str) -> bool:
    return sum(int(d) * 3 ** i for i, d in enumerate(w)) % 7 == 4 and w.count("2") % 2 == 0


def t04_obvious_dfa() -> dict:
    """(value so far mod 7, current power of 3 mod 7, parity of 2s): the construction a reader of
    the definition writes first."""
    return build_dfa(DIGITS, (0, 1, 0), lambda q, d: ((q[0] + int(d) * q[1]) % 7, q[1] * 3 % 7, q[2] ^ (d == "2")),
                     lambda q: q[0] == 4 and q[2] == 0)


def t04_residue_dfa() -> dict:
    """(residue the remaining digits must still contribute, parity): digit d turns s into
    (s - d) * 5 mod 7, because 5 is the inverse of 3 mod 7."""
    return build_dfa(DIGITS, (4, 0), lambda q, d: ((q[0] - int(d)) * 5 % 7, q[1] ^ (d == "2")),
                     lambda q: q == (0, 0))


T05_R1 = re.compile(r"(ab)*a+b(ab)+a+(ba)+(ba)+a")
T05_R2 = re.compile(r"(ab)?a+b(ab)+a+(ba)+(ba)+a")


def t05_distinguishes(w: str) -> bool:
    return bool(T05_R1.fullmatch(w)) != bool(T05_R2.fullmatch(w))


T06_NFA = TASKS["task_06"]["instance"]["nfa"]


def t06_closure(states) -> frozenset:
    out, todo = set(states), list(states)
    while todo:
        for r in T06_NFA["transitions"].get(todo.pop(), {}).get("", []):
            if r not in out:
                out.add(r)
                todo.append(r)
    return frozenset(out)


def t06_dfa() -> dict:
    """Subset construction with ε-closures (the empty set, if reached, is the trap)."""
    step = lambda T, x: t06_closure({r for q in T for r in T06_NFA["transitions"].get(q, {}).get(x, [])})
    return build_dfa(AB, t06_closure({T06_NFA["start"]}), step, lambda T: bool(T & set(T06_NFA["accepting"])))


def t06_member(w: str) -> bool:
    """Direct search for an accepting path through the ε-NFA (no subsets): depth-first over
    (state, position), with ε-moves staying at the same position."""
    seen, stack = set(), [(T06_NFA["start"], 0)]
    while stack:
        q, i = stack.pop()
        if (q, i) in seen:
            continue
        seen.add((q, i))
        if i == len(w) and q in T06_NFA["accepting"]:
            return True
        moves = T06_NFA["transitions"].get(q, {})
        stack += [(r, i) for r in moves.get("", [])]
        if i < len(w):
            stack += [(r, i + 1) for r in moves.get(w[i], [])]
    return False


def t07_member(w: str) -> bool:
    """Rules (1)-(4) of the prompt: parse the groups with a stack, then check each group's children."""
    if not w:
        return False
    stack: list[tuple[str, list[str]]] = [("word", [])]
    for ch in w:
        if ch in "([":
            stack.append((ch, []))
            continue
        if len(stack) == 1 or {"(": ")", "[": "]"}[stack[-1][0]] != ch:
            return False
        kind, children = stack.pop()
        if kind == "(" and children.count("[") % 2:
            return False
        if kind == "[" and "(" in children:
            return False
        stack[-1][1].append(kind)
    return len(stack) == 1 and stack[0][1].count("[") % 2 == 0


@lru_cache(maxsize=None)
def t07_truth(n: int) -> dict[int, set[str]]:
    """L by length up to n: every well-nested word (built as o u c v), filtered by the rules."""
    nested = {0: {""}}
    for k in range(2, n + 1, 2):
        nested[k] = {o + u + c + v for i in range(0, k - 1, 2) for u in nested[i] for v in nested[k - 2 - i]
                     for o, c in (("(", ")"), ("[", "]"))}
    return {k: {w for w in nested.get(k, set()) if t07_member(w)} for k in range(1, n + 1)}


def t08_member(w: str) -> bool:
    m = re.fullmatch(r"(a+)(b*)(a+)", w)
    return bool(m) and 2 * len(m.group(1)) + len(m.group(3)) == 3 * len(m.group(2))


@lru_cache(maxsize=None)
def t08_truth(n: int) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {k: set() for k in range(1, n + 1)}
    for i in range(1, n + 1):
        for j in range(0, n + 1):
            k = 3 * j - 2 * i
            if k >= 1 and i + j + k <= n:
                out[i + j + k].add("a" * i + "b" * j + "a" * k)
    return out


# ============================================================ CNF grammars (own code)

def cnf_problems(g: dict, terminals: list[str]) -> list[str]:
    bad = []
    for p in g["productions"]:
        rhs = p["rhs"]
        ok = (len(rhs) == 1 and rhs[0] in terminals) or (len(rhs) == 2 and all(s not in terminals for s in rhs))
        if not ok:
            bad.append(f"{p['lhs']} -> {' '.join(rhs) or 'ε'}")
    return bad


def by_length(g: dict, n: int, cap: int = 3_000_000) -> Optional[dict[int, set[str]]]:
    """Words of length 1..n the start symbol derives, by dynamic programming over lengths: in CNF a
    word of length k >= 2 from A -> B C is a B-word of length i followed by a C-word of length k - i.
    None if more than cap strings would be stored."""
    gen: dict[str, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    pairs = [(p["lhs"], p["rhs"]) for p in g["productions"] if len(p["rhs"]) == 2]
    for p in g["productions"]:
        if len(p["rhs"]) == 1:
            gen[p["lhs"]][1].add(p["rhs"][0])
    stored = sum(len(gen[a][1]) for a in list(gen))
    for k in range(2, n + 1):
        for lhs, (b, c) in pairs:
            for i in range(1, k):
                left, right = gen[b].get(i), gen[c].get(k - i)
                if left and right:
                    gen[lhs][k].update(u + v for u in left for v in right)
        stored += sum(len(gen[a].get(k, ())) for a in list(gen))
        if stored > cap:
            return None
    return {k: set(gen[g["start"]].get(k, set())) for k in range(1, n + 1)}


def cyk(g: dict, w: str) -> bool:
    n = len(w)
    if n == 0:
        return False
    table = [[set() for _ in range(n + 1)] for _ in range(n)]  # table[i][l]: derive w[i:i+l]
    for i, ch in enumerate(w):
        table[i][1] = {p["lhs"] for p in g["productions"] if p["rhs"] == [ch]}
    for length in range(2, n + 1):
        for i in range(n - length + 1):
            for split in range(1, length):
                left, right = table[i][split], table[i + split][length - split]
                table[i][length] |= {p["lhs"] for p in g["productions"]
                                     if len(p["rhs"]) == 2 and p["rhs"][0] in left and p["rhs"][1] in right}
    return g["start"] in table[0][n]


def is_infinite(g: dict) -> bool:
    """A CNF grammar derives infinitely many words iff some useful nonterminal (deriving a word and
    reachable from the start through useful ones) can reach itself."""
    generating: set[str] = set()
    changed = True
    while changed:
        changed = False
        for p in g["productions"]:
            ok = len(p["rhs"]) == 1 or all(s in generating for s in p["rhs"])
            if ok and p["lhs"] not in generating:
                generating.add(p["lhs"])
                changed = True
    edges = defaultdict(set)
    for p in g["productions"]:
        if len(p["rhs"]) == 2 and p["lhs"] in generating and all(s in generating for s in p["rhs"]):
            edges[p["lhs"]] |= set(p["rhs"])
    useful, todo = set(), [g["start"]] if g["start"] in generating else []
    while todo:
        a = todo.pop()
        if a not in useful:
            useful.add(a)
            todo += list(edges[a])

    def reaches_itself(a: str) -> bool:
        seen, todo = set(), list(edges[a])
        while todo:
            b = todo.pop()
            if b == a:
                return True
            if b not in seen:
                seen.add(b)
                todo += list(edges[b])
        return False
    return any(reaches_itself(a) for a in useful)


def own_cfg_verdict(g: dict, truth: dict[int, set[str]], terminals: list[str], n: int) -> tuple[str, Optional[str]]:
    """('pass' | 'cnf' | 'finite' | 'wrong' | 'too big', shortest word up to n on which the grammar is wrong)."""
    if cnf_problems(g, terminals):
        return "cnf", None
    lang = by_length(g, n)
    if lang is None:
        return "too big", None
    for k in range(1, n + 1):
        diff = lang[k] ^ truth[k]
        if diff:
            return "wrong", min(diff)
    return ("pass" if is_infinite(g) else "finite"), None


# ============================================================ the checks, one per review row

Result = tuple[bool, str]
DFA_ORACLES: dict[str, Callable[[], dict]] = {
    "task_01": t01_dfa, "task_02": t02_dfa, "task_03": t03_dfa, "task_04": t04_residue_dfa, "task_06": t06_dfa}
ALPHABET = {"task_01": ["0", "1"], "task_02": ABC, "task_03": AB, "task_04": DIGITS, "task_06": AB}
MEMBER = {"task_01": t01_member, "task_02": t02_member, "task_04": t04_member, "task_06": t06_member,
          "task_07": t07_member, "task_08": t08_member}


def examples_agree(task_id: str) -> Result:
    ex = TASKS[task_id]["examples"]
    wrong = [w for w in ex["in"] if not MEMBER[task_id](w)] + [w for w in ex["out"] if MEMBER[task_id](w)]
    return not wrong, f"{len(ex['in'])} in / {len(ex['out'])} out examples agree with the definition" + (
        f"; WRONG: {wrong}" if wrong else "")


def oracle_matches_definition(task_id: str, max_len: int) -> Result:
    d = DFA_ORACLES[task_id]()
    bad = [w for w in words(ALPHABET[task_id], max_len) if accepts(d, w) != MEMBER[task_id](w)]
    return not bad, f"own DFA = definition on all words up to length {max_len}" + (f"; WRONG on {bad[:3]}" if bad else "")


def reference_is_exact(task_id: str, expected_states: int) -> Result:
    oracle, ref = DFA_ORACLES[task_id](), REF[task_id]
    score, cex = own_dfa_score(ref, oracle)
    n_min = minimal_size(oracle)
    ok = score == 1.0 and n_min == expected_states == len(ref["states"])
    return ok, (f"reference ({len(ref['states'])} states) is exactly equivalent to the own DFA, whose minimum "
                f"is {n_min} states (score {score}{', counterexample ' + repr(cex) if cex else ''})")


def check_decision() -> Result:
    passes: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    api_failures = []
    for p in sorted((ROOT / "pilot_v1" / "transcripts").glob("*/*/*.json")):
        t = json.loads(p.read_text(encoding="utf-8"))
        code = t["grade"].get("failure_code")
        if code == "API_ERROR":
            continue
        passes[p.parts[-3]][1] += 1
        passes[p.parts[-3]][0] += t["grade"]["score"] == 1.0
        if t["grade"]["score"] < 1.0 and p.parts[-3] != "chatgpt-free":
            api_failures.append((t["task_id"], code))
    ok = all(f == ("task_08", "TRUNCATED") for f in api_failures)
    summary = ", ".join(f"{m} {a}/{b}" for m, (a, b) in sorted(passes.items()))
    return ok, f"v1 pilot passes: {summary}; every API-model failure is a task_08 truncation: {ok}"


def check_t01_reference() -> list[Result]:
    counter = build_dfa(["0", "1"], 0, lambda q, x: (q + (x == "0")) % 3, lambda q: q == 1)
    rest = build_dfa(["0", "1"], "", lambda q, x: q if q == "dead" else ("dead" if (q + x).endswith("0101") else (q + x)[-3:]),
                     lambda q: q != "dead" and len(q) == 3 and q[0] == "1")
    small = minimized(rest)
    product = build_dfa(["0", "1"], (counter["start"], small["start"]),
                        lambda q, x: (counter["trans"][q[0]][x], small["trans"][q[1]][x]), lambda q: False)
    return [reference_is_exact("task_01", 21),
            (len(product["trans"]) == 30, f"mod-3 counter x minimal 'no 0101, third-to-last is 1' DFA ({len(small['trans'])} "
                                          f"states): {len(product['trans'])} reachable product states")]


def check_t02_task() -> list[Result]:
    traces = {w: t02_member(w) for w in ("abcba", "abca", "bacba")}
    return [examples_agree("task_02"),
            (traces["abcba"] and not traces["abca"], f"abcba in L: {traces['abcba']}, abca in L: {traces['abca']}, "
                                                    f"bacba in L: {traces['bacba']}")]


def check_t03_task() -> Result:
    m1, m2 = TASKS["task_03"]["instance"]["m1"], TASKS["task_03"]["instance"]["m2"]
    brute = {run({"start": m1["start"], "trans": m1["transitions"]}, x) for x in words(AB, 14)
             if run({"start": m2["start"], "trans": m2["transitions"]}, x) in m2["accepting"]}
    s = t03_start_set()
    ok = brute == set(s) and 1 < len(s) < len(m1["states"])
    return ok, f"S = {sorted(s)} (BFS) = states reached by every word of L(M2) up to length 14; neither one state nor all {len(m1['states'])}"


def check_t03_reference() -> list[Result]:
    d, s = t03_dfa(), t03_start_set()
    m1 = TASKS["task_03"]["instance"]["m1"]
    bad = [y for y in words(AB, 10) if accepts(d, y) != any(
        run({"start": q, "trans": m1["transitions"]}, y) in m1["accepting"] for q in s)]
    return [(not bad and len(d["trans"]) == 14, f"{len(d['trans'])} reachable subsets; subset DFA = 'some state of S accepts y' "
                                                f"on all y up to length 10"),
            reference_is_exact("task_03", 13)]


def check_t04_task() -> Result:
    values = {w: sum(int(c) * 3 ** i for i, c in enumerate(w)) for w in ("122", "221")}
    ok = t04_member("122") and not t04_member("221") and examples_agree("task_04")[0]
    return ok, f"122 = {values['122']} ≡ {values['122'] % 7} (mod 7), two 2s: in L; 221 = {values['221']} ≡ " \
               f"{values['221'] % 7}: not in L; " + examples_agree("task_04")[1]


def check_t04_reference() -> list[Result]:
    obvious, residue = t04_obvious_dfa(), t04_residue_dfa()
    bad = [w for w in words(DIGITS, 8) if accepts(obvious, w) != t04_member(w)]
    same = shortest_difference(obvious, residue) is None
    return [(not bad and len(obvious["trans"]) == 84 and minimal_size(obvious) == 14 and same,
             f"obvious construction: {len(obvious['trans'])} states, = definition up to length 8, minimizes to "
             f"{minimal_size(obvious)}; the residue DFA ({len(residue['trans'])} states) is exactly equivalent to it"),
            reference_is_exact("task_04", 14)]


def check_t05() -> list[Result]:
    found = [w for w in words(AB, 17) if t05_distinguishes(w)]
    short = [w for w in found if len(w) <= 16]
    both = bool(T05_R1.fullmatch("ababababababaa")) and bool(T05_R2.fullmatch("ababababababaa"))
    return [(both, f"ababababababaa is matched by both regexes (Python re): {both}"),
            (short == [REF["task_05"]["witness"]] == ["ababaababaababaa"],
             f"all {2 ** 18 - 1} words up to length 17 searched: the only distinguishing word up to length 16 is "
             f"{short}; {len(found) - len(short)} of length 17")]


def check_t06() -> list[Result]:
    d = t06_dfa()
    start = t06_closure({T06_NFA["start"]})
    succ = {x: sorted(d["trans"][start][x]) for x in AB}
    blocks = moore_blocks(d)
    merged = [sorted(map(sorted, group)) for group in
              (tuple(q for q in d["trans"] if blocks[q] == b) for b in set(blocks.values())) if len(group) > 1]
    return [(start == frozenset({"q0", "q3"}), f"start state = ε-closure(q0) = {sorted(start)}; a -> {succ['a']}, b -> {succ['b']}"),
            oracle_matches_definition("task_06", 12),
            (len(d["trans"]) == 17 and frozenset() not in d["trans"] and len(merged) == 1,
             f"{len(d['trans'])} reachable subsets, the empty set not among them (no trap state needed); "
             f"the one merged pair: {merged}"),
            reference_is_exact("task_06", 16)]


def check_t07_task() -> list[Result]:
    truth = t07_truth(16)
    counts = [len(truth[k]) for k in range(2, 17, 2)]
    return [examples_agree("task_07"),
            (counts == [1, 3, 11, 43, 175, 734, 3151, 13778] and not any(truth[k] for k in range(1, 17, 2)),
             f"words of L of length 2, 4, ..., 16 (own enumeration): {counts}")]


def check_cfg_reference(task_id: str, n: int, derive: list[str], cannot: list[str]) -> Result:
    g = REF[task_id]
    truth = t07_truth(n) if task_id == "task_07" else t08_truth(n)
    terminals = BRACKETS if task_id == "task_07" else AB
    verdict, cex = own_cfg_verdict(g, truth, terminals, n)
    derived = all(cyk(g, w) for w in derive) and not any(cyk(g, w) for w in cannot)
    return verdict == "pass" and derived, (
        f"{len(g['productions'])} CNF productions, infinite, generate exactly L up to length {n} (own "
        f"enumeration): {verdict}; derives {derive}" + (f", not {cannot}" if cannot else "") + f": {derived}")


def check_t08_task() -> Result:
    ex = TASKS["task_08"]["examples"]
    eqs = []
    for w in ex["in"]:
        m = re.fullmatch(r"(a+)(b*)(a+)", w)
        i, j, k = (len(m.group(g)) for g in (1, 2, 3))
        eqs.append(f"{w}: 2·{i}+{k}={3 * j}, i≡{i % 3}")
    ok = examples_agree("task_08")[0]
    return ok, examples_agree("task_08")[1] + "; " + "; ".join(eqs)


def check_noncf() -> Result:
    """Original T08 {a^i b^j a^k : i+k = 2j, i > k >= 1}: for each p, the word a^(p+1) b^p a^(p-1)
    has no pumping decomposition (|vxy| <= p, |vy| >= 1) that stays in the language for both
    m = 0 and m = 2, which is what the pumping lemma needs. Not a proof for all p (the proof is
    the general argument in scripts/check_task08_noncf.py), but no p up to 8 escapes."""
    def member(w):
        m = re.fullmatch(r"(a+)(b*)(a+)", w)
        return bool(m) and len(m.group(1)) + len(m.group(3)) == 2 * len(m.group(2)) and len(m.group(1)) > len(m.group(3))
    escapes = []
    for p in range(2, 9):
        w = "a" * (p + 1) + "b" * p + "a" * (p - 1)
        assert member(w)
        for s in range(len(w)):
            for lv, lx, ly in itertools.product(range(p + 1), repeat=3):
                if lv + ly == 0 or lv + lx + ly > p or s + lv + lx + ly > len(w):
                    continue
                u, v, x, y, z = (w[:s], w[s:s + lv], w[s + lv:s + lv + lx], w[s + lv + lx:s + lv + lx + ly],
                                 w[s + lv + lx + ly:])
                if all(member(u + v * m + x + y * m + z) for m in (0, 2)):
                    escapes.append((p, u, v, x, y, z))
    script = subprocess.run([sys.executable, "scripts/check_task08_noncf.py"], cwd=ROOT, capture_output=True, text=True)
    return not escapes and script.returncode == 0, (
        f"every decomposition of a^(p+1) b^p a^(p-1) fails pumping for p = 2..8 ({len(escapes)} escape); "
        f"scripts/check_task08_noncf.py exit {script.returncode}")


def check_dfa_grader() -> list[Result]:
    """Project grader vs own exact score on references and 220 deterministic mutants."""
    from graders.grader import grade_answer
    rng = random.Random(2026)
    results = []
    for task_id, make in DFA_ORACLES.items():
        oracle, ref, alphabet = make(), REF[task_id], ALPHABET[task_id]
        mutants = [ref]
        states = ref["states"]
        for _ in range(12):  # redirect one arrow
            m = json.loads(json.dumps(ref))
            q, x = rng.choice(states), rng.choice(alphabet)
            m["transitions"][q][x] = rng.choice([s for s in states if s != m["transitions"][q][x]])
            mutants.append(m)
        for q in rng.sample(states, 6):  # flip one accepting flag
            m = json.loads(json.dumps(ref))
            m["accepting"] = [s for s in states if (s in ref["accepting"]) != (s == q)]
            mutants.append(m)
        for _ in range(2):  # duplicate a state and send one arrow to the copy: same language, one state too many
            m = json.loads(json.dumps(ref))
            q = rng.choice(states)
            m["states"].append(q + "_copy")
            m["transitions"][q + "_copy"] = dict(m["transitions"][q])
            if q in m["accepting"]:
                m["accepting"].append(q + "_copy")
            into = [(p, x) for p in states for x in alphabet if m["transitions"][p][x] == q]
            if into:
                p, x = rng.choice(into)
                m["transitions"][p][x] = q + "_copy"
            mutants.append(m)
        m = json.loads(json.dumps(ref))  # delete one transition
        del m["transitions"][rng.choice(states)][alphabet[0]]
        mutants.append(m)
        disagree = []
        for m in mutants:
            g = grade_answer(TASKS[task_id], m)
            own, cex = own_dfa_score(m, oracle)
            cex_ok = g.counterexample is None or not is_complete(m, alphabet) or (
                cex is not None and len(g.counterexample) == len(cex)
                and accepts(answer_dfa(m, alphabet), g.counterexample) != accepts(oracle, g.counterexample))
            if g.score != own or not cex_ok:
                disagree.append((g.score, own, g.counterexample, cex))
        codes = Counter(own_dfa_score(m, oracle)[0] for m in mutants)
        results.append((not disagree, f"{task_id}: {len(mutants)} answers (scores {dict(codes)}): grader = own exact score"
                                      + (f"; DISAGREE {disagree[:2]}" if disagree else "")))
    return results


def check_witness_grader() -> Result:
    from graders.grader import grade_answer
    ref = REF["task_05"]["witness"]
    long_one = next(w for w in words(AB, 17) if len(w) == 17 and t05_distinguishes(w))
    candidates = ["", ref, long_one, ref + " ", "abc", ref[:-1], "ababababababaa"] + [
        ref[:i] + ("a" if ref[i] == "b" else "b") + ref[i + 1:] for i in range(len(ref))]
    disagree = []
    for w in candidates:
        own = 0.0 if set(w) - set("ab") else (1.0 if t05_distinguishes(w) and len(w) == 16 else 0.5 if t05_distinguishes(w) else 0.0)
        g = grade_answer(TASKS["task_05"], {"witness": w})
        if g.score != own:
            disagree.append((w, g.score, own))
    return not disagree, f"{len(candidates)} witnesses (ε, the reference, a distinguishing word of length 17, a space, " \
                         f"off-alphabet, every one-letter change): grader = own score" + (f"; DISAGREE {disagree}" if disagree else "")


def check_cfg_grader() -> list[Result]:
    """Project grader vs own enumeration on the references and mutants (drop each production, add
    random ones, one non-CNF rule). T08 uses the grader's own N = 36; T07 uses 14 < 16, so a T07
    failure found by the grader at length 15-16 is checked on its counterexample instead."""
    from graders.grader import grade_answer
    rng = random.Random(7)
    out = []
    for task_id, terminals, n, big_n in (("task_07", BRACKETS, 14, 16), ("task_08", AB, 36, 36)):
        ref = REF[task_id]
        truth = t07_truth(n) if task_id == "task_07" else t08_truth(n)
        member = MEMBER[task_id]
        nts = sorted({p["lhs"] for p in ref["productions"]})
        mutants = [ref] + [{"start": ref["start"], "productions": ref["productions"][:i] + ref["productions"][i + 1:]}
                           for i in range(len(ref["productions"]))]
        for _ in range(8):
            extra = {"lhs": rng.choice(nts), "rhs": [rng.choice(nts), rng.choice(nts)]}
            mutants.append({"start": ref["start"], "productions": ref["productions"] + [extra]})
        mutants.append({"start": ref["start"], "productions": ref["productions"] + [{"lhs": nts[0], "rhs": nts[:3]}]})
        disagree, skipped = [], 0
        for m in mutants:
            g = grade_answer(TASKS[task_id], m)
            verdict, cex = own_cfg_verdict(m, truth, terminals, n)
            if verdict == "too big":
                skipped += 1
                ok = g.score == 0.0 and g.counterexample is not None and cyk(m, g.counterexample) != member(g.counterexample)
            elif verdict == "pass":
                ok = g.score == 1.0 or (n < big_n and g.counterexample is not None and len(g.counterexample) > n
                                        and cyk(m, g.counterexample) != member(g.counterexample))
            elif verdict == "wrong":
                ok = g.score == 0.0 and g.counterexample is not None and len(g.counterexample) == len(cex) \
                     and cyk(m, g.counterexample) != member(g.counterexample)
            else:
                ok = g.score == 0.0
            if not ok:
                disagree.append((m["productions"][-1], g.score, g.failure_code, verdict, cex))
        out.append((not disagree, f"{task_id}: {len(mutants)} grammars, grader = own check up to length {n}"
                                  + (f" ({skipped} too large to enumerate, counterexample checked instead)" if skipped else "")
                                  + (f"; DISAGREE {disagree[:2]}" if disagree else "")))
    return out


def check_stored_grades() -> Result:
    """Every graded model answer in transcripts/ re-scored with the own oracles (exact for DFAs and
    T05, up to length 36 for T08 and 14 for T07)."""
    checked, disagree = 0, []
    truths = {"task_07": t07_truth(14), "task_08": t08_truth(36)}
    oracles = {tid: make() for tid, make in DFA_ORACLES.items()}
    for p in sorted((ROOT / "transcripts").glob("*/*/*.json")):
        t = json.loads(p.read_text(encoding="utf-8"))
        ans, g, tid = t["parsed_answer"], t["grade"], t["task_id"]
        if ans is None:
            continue
        checked += 1
        if tid in oracles:
            own, cex = own_dfa_score(ans, oracles[tid])
            ok = own == g["score"] and (cex is None or len(cex) == len(g["counterexample"] or ""))
        elif tid == "task_05":
            w = ans["witness"]
            own = 0.0 if set(w) - set("ab") else (1.0 if t05_distinguishes(w) and len(w) == 16 else 0.5 if t05_distinguishes(w) else 0.0)
            ok = own == g["score"]
        else:
            n = 14 if tid == "task_07" else 36
            verdict, cex = own_cfg_verdict(ans, truths[tid], BRACKETS if tid == "task_07" else AB, n)
            ok = (verdict == "pass") == (g["score"] == 1.0) and (cex is None or len(cex) == len(g["counterexample"] or ""))
            if verdict == "pass" and g["score"] == 0.0 and len(g["counterexample"] or "") > n:  # beyond the own bound
                ok = cyk(ans, g["counterexample"]) != MEMBER[tid](g["counterexample"])
        if not ok:
            disagree.append("/".join(p.parts[-3:]))
    return not disagree, f"{checked} graded answers re-scored by own code: {checked - len(disagree)} agree" + (
        f"; DISAGREE {disagree}" if disagree else "")


def check_left_quotient() -> Result:
    from automata.dfa import DFA
    from automata.nfa import left_quotient
    rng = random.Random(3)
    bad = 0
    for _ in range(300):
        dfas = []
        for n, prefix in ((rng.randint(1, 5), "p"), (rng.randint(1, 4), "r")):
            states = [f"{prefix}{i}" for i in range(n)]
            dfas.append({"states": states, "alphabet": AB, "start": states[0],
                         "accepting": [s for s in states if rng.random() < 0.4],
                         "transitions": {s: {x: rng.choice(states) for x in AB} for s in states}})
        m1, m2 = dfas
        got = left_quotient(DFA(**m1), DFA(**m2))
        got_d = {"alphabet": AB, "start": got.start, "accepting": set(got.accepting), "trans": got.transitions}
        pairs = {(m1["start"], m2["start"])}
        todo = deque(pairs)
        while todo:
            p, r = todo.popleft()
            for x in AB:
                nxt = (m1["transitions"][p][x], m2["transitions"][r][x])
                if nxt not in pairs:
                    pairs.add(nxt)
                    todo.append(nxt)
        s = frozenset(p for p, r in pairs if r in m2["accepting"])
        mine = build_dfa(AB, s, lambda T, x: frozenset(m1["transitions"][q][x] for q in T),
                         lambda T: bool(T & set(m1["accepting"])))
        bad += shortest_difference(got_d, mine) is not None
    return bad == 0, f"automata.nfa.left_quotient exactly equivalent to the own construction on 300 random DFA pairs ({bad} differ)"


def check_harness_guard() -> Result:
    before = {f: (ROOT / "results" / f).read_bytes() for f in ("summary.md", "scorecard.json")}
    r = subprocess.run([sys.executable, "run_eval.py", "--regrade", "pilot_v1/transcripts"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    after = {f: (ROOT / "results" / f).read_bytes() for f in before}
    text = r.stdout + r.stderr
    ok = r.returncode != 0 and "different version of their task" in text and before == after
    first = next((line for line in text.splitlines() if "different version of their task" in line), text.strip()[:120])
    return ok, f"--regrade pilot_v1/transcripts exits {r.returncode}, results/ unchanged: {before == after}; says: {first[:150]}"


def check_manual_import() -> Result:
    from harness.manual import import_manual
    from harness.prompts import tasks_by_id
    tasks = tasks_by_id()
    wrong = json.loads(json.dumps(REF["task_01"]))
    wrong["accepting"] = wrong["accepting"][1:]
    with tempfile.TemporaryDirectory() as tmp:
        manual, out = Path(tmp) / "manual", Path(tmp) / "transcripts"
        info = ('app: "test app"\nmodel_shown: "test"\ndate: "2026-11-01"\nreasoning_mode: "default"\n'
                'no_tools_confirmed: true\nnew_chat_per_trial: true\n')
        for name, confirmed in (("good-setup", True), ("bad-setup", False)):
            (manual / name / "task_01").mkdir(parents=True)
            (manual / name / "info.yaml").write_text(info if confirmed else info.replace("no_tools_confirmed: true", "no_tools_confirmed: false"), encoding="utf-8")
            (manual / name / "task_01" / "trial_1.txt").write_text("```json\n" + json.dumps(REF["task_01"]) + "\n```", encoding="utf-8")
            (manual / name / "task_01" / "trial_2.txt").write_text(json.dumps(wrong), encoding="utf-8")
        written, problems = import_manual(manual, out, tasks)
    scores = sorted((t["model"], t["trial"], t["grade"]["score"]) for t in written)
    ok = scores == [("good-setup", 1, 1.0), ("good-setup", 2, 0.0)] and any("bad-setup" in p for p in problems)
    return ok, f"imported {scores}; the setup without the no-tools confirmation was refused: {any('bad-setup' in p for p in problems)}"


def check_parser() -> Result:
    from harness.runner import evaluate_output
    text = "I end with one ```json block.\n\n```json\n" + json.dumps(REF["task_01"]) + "\n```\n"
    _, g = evaluate_output(TASKS["task_01"], text, "stop")
    return g.score == 1.0, f"a reply that mentions ```json in a sentence before the real block scores {g.score}"


def check_explainer() -> Result:
    """ChatGPT's T06 trial 2: the named arrow is wrong and is the first wrong one, by the
    access-word reading (each model state stands for the class of its shortest access word)."""
    t = load("transcripts/chatgpt-free/task_06/trial_2.json")
    model, oracle = answer_dfa(t["parsed_answer"], AB), t06_dfa()
    blocks = moore_blocks(oracle)
    access, todo = {model["start"]: ""}, deque([model["start"]])
    while todo:
        q = todo.popleft()
        for x in AB:
            r = model["trans"][q][x]
            if r not in access:
                access[r] = access[q] + x
                todo.append(r)
    cls = lambda w: blocks[run(oracle, w)]
    faulty = [(q, x) for q in access for x in AB if cls(access[q] + x) != cls(access[model["trans"][q][x]])]
    flags = [q for q in access if (q in model["accepting"]) != (run(oracle, access[q]) in oracle["accepting"])]
    agree = sum(accepts(model, w) == accepts(oracle, w) for w in words(AB, 10))
    ok = (faulty == [("JL", "a")] and not flags and run(model, "aabb") == "JL" and model["trans"]["JL"]["a"] == "JL"
          and accepts(model, "aabbabaab") and not accepts(oracle, "aabbabaab") and agree == 2041)
    return ok, (f"faulty arrows {faulty}, faulty flags {flags}; accepts aabbabaab (not in L); agrees with L on "
                f"{agree} of {2 ** 11 - 1} words up to length 10")


OPEN_MODELS = ["nemotron-3-ultra-free", "dots-3-note-free"]


def scorecard_numbers() -> dict:
    card = load("results/scorecard.json")["models"]
    models = [m for m in card if card[m]["valid_trials"] == 24]  # complete settings; a partial one is reported apart
    partial = [m for m in card if 0 < card[m]["valid_trials"] < 24]
    per_task = {m: [card[m]["tasks"][f"task_0{i}"]["passes"] for i in range(1, 9)] for m in models}
    answered = {"passes": 0, "answered": 0, "graded": 0}
    for p in sorted((ROOT / "transcripts").glob("*/*/*.json")):
        t = json.loads(p.read_text(encoding="utf-8"))
        answered["graded"] += t["parsed_answer"] is not None
        if p.parts[-3] in OPEN_MODELS and t["parsed_answer"] is not None:
            answered["answered"] += 1
            answered["passes"] += t["grade"]["score"] == 1.0
    def examples(model: str) -> tuple[int, int]:
        """(wrong answers that break a prompt example, wrong answers on tasks that list examples)."""
        wrong = [f for f in card[model]["failures"] if f["listed_examples_missed"] is not None]
        return sum(bool(f["listed_examples_missed"]) for f in wrong), len(wrong)
    return {"card": card, "models": models, "partial": partial, "per_task": per_task, **answered,
            "valid": sum(card[m]["valid_trials"] for m in models), "pass": sum(sum(v) for v in per_task.values()),
            "truncated": sum(card[m]["truncated"] for m in models),
            "chatgpt_examples": examples("chatgpt-free"), "gemini_examples": examples("gemini-free"),
            "codes": sum((Counter(card[m]["failure_code_histogram"]) for m in models), Counter())}


NUMBER_WORDS = {6: "Six", 7: "Seven", 9: "Nine", 11: "Eleven"}


def check_readme() -> Result:
    s, text = scorecard_numbers(), (ROOT / "README.md").read_text(encoding="utf-8")
    card = s["card"]
    by_task, per_col = [sum(c) for c in zip(*s["per_task"].values())], 3 * len(s["models"])
    claims = [f"Of {s['valid']} graded trials", f"{s['pass']} ({round(100 * s['pass'] / s['valid'])}%) were exactly right",
              f"solved {sum(s['per_task']['nemotron-3-ultra-free'])} of 24",
              f"solved {sum(s['per_task']['chatgpt-free'])} of 24",
              f"solved {sum(s['per_task']['chatgpt-think'])} of 24",
              f"solved {sum(s['per_task']['gemini-free'])} of 24",
              f"on only {round(8 * card['chatgpt-think']['pass_hat_k'])} of the 8 tasks",
              f"on only {round(8 * card['nemotron-3-ultra-free']['pass_hat_k'])} of the 8 tasks",
              f"misses {24 - sum(s['per_task']['chatgpt-think'])} of 24",
              f"In {s['truncated']} of their 48 trials", f"In the {s['answered']} trials where",
              f"exactly right {s['passes']} times",
              f"{NUMBER_WORDS[s['chatgpt_examples'][1]]} of the Think-off wrong answers",
              f"{NUMBER_WORDS[s['chatgpt_examples'][0]]} of the {NUMBER_WORDS[s['chatgpt_examples'][1]].lower()}",
              f"{NUMBER_WORDS[s['gemini_examples'][1]].lower()} of the Fast-mode ones",
              f"{NUMBER_WORDS[s['gemini_examples'][0]].lower()} of the {NUMBER_WORDS[s['gemini_examples'][1]].lower()}",
              f"The {s['valid'] - s['pass']} failures by code",
              f"T{by_task.index(max(by_task)) + 1:02d} ({max(by_task)} of {per_col}; the easiest)",
              f"T04 ({by_task[3]} of {per_col})", f"solved in {by_task[3]} of {per_col} trials",
              f"each solved {by_task[0]} times in {per_col} trials", f"solved only {by_task[7]} times in {per_col} trials",
              f"| **All (of {per_col})** | " + " | ".join(f"**{n}**" for n in by_task) + " |",
              "2,041 of the 2,047", f"all {s['graded']} graded answers"]
    claims += [f"| `{m}` | " + " | ".join(map(str, s["per_task"][m])) + " |" for m in s["models"]]
    claims += [f"{n} `{code}`" for code, n in s["codes"].items() if code != "PASS"]
    for m in s["partial"]:
        c = card[m]
        passes = sum(t["passes"] for t in c["tasks"].values())
        cells = " | ".join(f"{t['passes']}/{t['trials']}" for _, t in sorted(c["tasks"].items()))
        claims += [f"{passes} of its first {c['valid_trials']} replies", f"{c['valid_trials']} of 24) | {c['valid_trials']} | {round(100 * c['pass_rate'])}% | – | – | {c['mean_score']:.2f} |",
                   f"not in the totals) | {cells} |"]
    for m in s["models"]:
        c = card[m]
        claims.append(f"| {c['valid_trials']} | {round(100 * c['pass_rate'])}% | {round(100 * c['pass_at_k'])}% | "
                      f"{round(100 * c['pass_hat_k'])}% | {c['mean_score']:.2f} |")
    missing = [c for c in claims if c not in text]
    return not missing, f"{len(claims) - len(missing)} of {len(claims)} README numbers found as computed from results/scorecard.json" + (
        f"; MISSING {missing}" if missing else "")


def check_manual_replies() -> Result:
    """No chat-app reply was saved under two different tasks (a copy from the wrong chat)."""
    seen: dict[tuple[str, str], str] = {}
    bad = []
    for p in sorted((ROOT / "manual").glob("*/task_*/trial_*.txt")):
        text = p.read_text(encoding="utf-8").strip()
        if text and seen.setdefault((p.parts[-3], text), p.parts[-2]) != p.parts[-2]:
            bad.append("/".join(p.parts[-3:]))
    return not bad, f"{len(seen)} different chat-app replies, none saved under two tasks" + (f"; SAME TEXT {bad}" if bad else "")


def check_submission_texts() -> Result:
    s = scorecard_numbers()
    sub = (ROOT / "docs" / "SUBMISSION.md").read_text(encoding="utf-8")
    video = (ROOT / "docs" / "VIDEO_SCRIPT.md").read_text(encoding="utf-8")
    nemo, chat = sum(s["per_task"]["nemotron-3-ultra-free"]), sum(s["per_task"]["chatgpt-free"])
    think, gemini = sum(s["per_task"]["chatgpt-think"]), sum(s["per_task"]["gemini-free"])
    claims = [(sub, f"{s['pass']} of {s['valid']} trials"), (sub, f"solved {nemo} of 24"), (sub, f"solved {chat} of 24"),
              (sub, f"solved {think} of 24"), (video, f"solved {think} of 24"),
              (sub, f"solved {gemini} of 24"), (video, f"{gemini} of 24"),
              (sub, f"{s['truncated']} of 48 trials"), (video, f"{s['pass']} exactly right"), (video, f"solved {nemo} of 24"),
              (video, f"solved {chat} of 24"), (video, f"{s['truncated']} of the 48"),
              (video, f"right {s['passes']} of the {s['answered']} times"),
              (video, f"{NUMBER_WORDS[s['chatgpt_examples'][0]].lower()} of ChatGPT's {NUMBER_WORDS[s['chatgpt_examples'][1]].lower()}")]
    missing = [c for d, c in claims if c not in d]
    return not missing, f"{len(claims) - len(missing)} of {len(claims)} numbers in SUBMISSION.md / VIDEO_SCRIPT.md match" + (
        f"; MISSING {missing}" if missing else "")


def all_checks() -> list[tuple[str, list[Result]]]:
    """(review row, results) in the order of docs/REVIEW_LOG.md."""
    as_list = lambda r: r if isinstance(r, list) else [r]
    rows = [
        ("Decision: v1 → v2", check_decision),
        ("T01 task + prompt", lambda: examples_agree("task_01")),
        ("T01 reference", lambda: [oracle_matches_definition("task_01", 14)] + check_t01_reference()),
        ("T02 task + prompt", check_t02_task),
        ("T02 reference", lambda: [oracle_matches_definition("task_02", 9), reference_is_exact("task_02", 16)]),
        ("T03 task + instance", check_t03_task),
        ("T03 reference", check_t03_reference),
        ("T04 task + prompt", check_t04_task),
        ("T04 reference", lambda: [oracle_matches_definition("task_04", 8)] + check_t04_reference()),
        ("T05 task + regex pair", lambda: check_t05()[0]),
        ("T05 reference", lambda: check_t05()[1]),
        ("T06 task + instance", lambda: check_t06()[:2]),
        ("T06 reference", lambda: check_t06()[2:]),
        ("T07 task + prompt", check_t07_task),
        ("T07 reference", lambda: check_cfg_reference("task_07", 16, ["([][])", "[[][]][]"], ["[[]]"])),
        ("T08 task + prompt", check_t08_task),
        ("T08 reference", lambda: check_cfg_reference("task_08", 36, ["aba", "aabbaa", "aaabbbaaa"], [])),
        ("Original T08 non-CF proof", check_noncf),
        ("DFA grader", check_dfa_grader),
        ("Witness grader", check_witness_grader),
        ("CFG grader (bounded)", check_cfg_grader),
        ("Every stored model grade", check_stored_grades),
        ("Left quotient engine", check_left_quotient),
        ("Harness", check_harness_guard),
        ("Chat-app import", check_manual_import),
        ("Chat-app replies", check_manual_replies),
        ("Parser fix (2026-11-01)", check_parser),
        ("Failure explainer", check_explainer),
        ("README analysis", check_readme),
        ("Submission texts", check_submission_texts),
    ]
    return [(name, as_list(fn())) for name, fn in rows]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    failed = 0
    for name, results in all_checks():
        for ok, detail in results:
            failed += not ok
            print(f"{'OK  ' if ok else 'FAIL'} {name}: {detail}")
    print(f"review_checks: {'all OK' if not failed else f'{failed} FAILED'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
