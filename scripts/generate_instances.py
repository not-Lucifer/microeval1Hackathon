"""Build every task file (tasks/*.json: prompt + metadata, NO answers) and every reference
file (reference/*.ref.json: answers), deterministically from fixed seeds.

    python scripts/generate_instances.py          # (re)write all files
    python scripts/generate_instances.py --check  # exit 1 if files on disk are stale

Prompt texts live here so that every condition the grader checks is visibly stated in
the prompt (CLAUDE.md rule 3). tests/test_tasks_wellformed.py checks this mechanically.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from automata.dfa import DFA, minimize  # noqa: E402
from automata.nfa import EPS, ENFA  # noqa: E402
from reference import build  # noqa: E402

TASKS_DIR = ROOT / "tasks"
REFERENCE_DIR = ROOT / "reference"
DRAFT_NOTE = "DRAFTED BY CLAUDE CODE at the author's request; not rewritten by the author (see docs/AI_USE.md)"

# --------------------------------------------------------------------------- shared text

DFA_ANSWER_SPEC = """\
WHAT TO SUBMIT
A deterministic finite automaton (DFA) for L, written as one JSON object with these keys:
  "states"      : list of distinct state names (strings)
  "start"       : the start state (one of "states")
  "accepting"   : list of accepting states (a subset of "states"; may be empty)
  "transitions" : object mapping EVERY state to an object that maps EVERY symbol of <ALPHABET> to exactly one next state

HOW IT IS GRADED (exactly, by algorithms; nothing is sampled)
1. Complete: every state must have exactly one transition for every symbol of <ALPHABET>. If some inputs can never lead to acceptance, include an explicit trap (dead) state.
2. Correct: the DFA must accept exactly the words of L, including the right decision for the empty word ε (checked by an exact equivalence algorithm).
3. Minimal: it must have the fewest states of any complete DFA that accepts L. Every state you list counts, including unreachable states and the trap state.
State names and the order of states do not matter.
Score: 1.0 if complete, correct and minimal; 0.5 if complete and correct but with more states than necessary; 0 otherwise.

FORMAT EXAMPLE (for an unrelated language over {x, y}: words with an odd number of x)
```json
{"states": ["even", "odd"], "start": "even", "accepting": ["odd"],
 "transitions": {"even": {"x": "odd", "y": "even"}, "odd": {"x": "even", "y": "odd"}}}
```"""

CFG_ANSWER_SPEC = """\
WHAT TO SUBMIT
A context-free grammar in Chomsky normal form (CNF), as one JSON object with these keys:
  "start"       : the start nonterminal
  "productions" : list of objects {"lhs": <nonterminal>, "rhs": [<symbol>, ...]}, one object per alternative
Symbols: an rhs entry that is exactly one of the terminal symbols <TERMINALS> is a terminal; every other name is a nonterminal. Use names without spaces; uppercase names such as S, A1, X_2 are recommended.
CNF means every production has exactly one of these two forms:
  A -> B C   (rhs is a list of two nonterminals), or
  A -> t     (rhs is a list containing exactly one terminal).
Not allowed: ε-productions (empty rhs), unit productions A -> B, right-hand sides with three or more symbols, and mixed right-hand sides such as A -> t B. The start symbol may also appear on right-hand sides. A CNF grammar cannot generate ε, which is why L excludes ε.

HOW IT IS GRADED
1. The grammar must be in CNF exactly as defined above (otherwise score 0).
2. For EVERY word w over the alphabet with 1 <= |w| <= <N>: the grammar must generate w if and only if w is in L. This is checked exhaustively by an exact algorithm, not by sampling.
3. The grammar must generate infinitely many words, because L is infinite.
Score: 1.0 if all three checks pass, otherwise 0. Equivalence of context-free grammars is undecidable in general, so the check is exact only for words up to length <N>; your grammar should nevertheless generate exactly L.

FORMAT EXAMPLE (for an unrelated language { x^n y^n : n >= 1 } over {x, y})
```json
{"start": "S", "productions": [
  {"lhs": "S", "rhs": ["X", "Y"]}, {"lhs": "S", "rhs": ["X", "T"]},
  {"lhs": "T", "rhs": ["S", "Y"]},
  {"lhs": "X", "rhs": ["x"]}, {"lhs": "Y", "rhs": ["y"]}]}
```"""

WITNESS_ANSWER_SPEC = """\
WHAT TO SUBMIT
One JSON object {"witness": "<word>"} where <word> is a string over {a, b} (use "" for the empty word ε).

HOW IT IS GRADED (exactly; the true minimum length is computed with automata)
Score 1.0 if the word is matched by exactly one of R1 and R2 AND no shorter word has that property; 0.5 if it is matched by exactly one of them but is longer than necessary; 0 otherwise (also 0 if it contains symbols other than a and b).

FORMAT EXAMPLE (for an unrelated problem over {x, y})
```json
{"witness": "xxy"}
```"""


def fmt_set(symbols: list[str]) -> str:
    return "{" + ", ".join(symbols) + "}"


def fmt_word(w: str) -> str:
    return w if w else "ε"


def examples_text(ins: list[str], outs: list[tuple[str, str]]) -> str:
    return (
        "Examples in L: " + ", ".join(fmt_word(w) for w in ins) + "\n"
        "Examples not in L: " + ", ".join(f"{fmt_word(w)} ({why})" for w, why in outs)
    )


def table(header: list[str], rows: list[list[str]]) -> str:
    """Plain-text table with aligned columns (no trailing spaces)."""
    widths = [max(len(r[i]) for r in rows + [header]) for i in range(len(header))]
    render = lambda r: ("  " + " | ".join(c.ljust(w) for c, w in zip(r, widths))).rstrip()  # noqa: E731
    return "\n".join([render(header)] + [render(r) for r in rows])


def dfa_table(dfa: DFA) -> str:
    rows = [[q] + [dfa.transitions[q][a] for a in dfa.alphabet] for q in dfa.states]
    return table(["state"] + dfa.alphabet, rows)


def enfa_table(nfa: ENFA) -> str:
    def cell(q: str, a: str) -> str:
        targets = nfa.transitions.get(q, {}).get(a, [])
        return fmt_set(targets) if targets else "-"

    rows = [[q] + [cell(q, a) for a in nfa.alphabet + [EPS]] for q in nfa.states]
    return table(["state"] + nfa.alphabet + ["ε"], rows)


def dfa_answer(dfa: DFA) -> dict:
    d = minimize(dfa)
    return {"states": d.states, "start": d.start, "accepting": d.accepting, "transitions": d.transitions}


# --------------------------------------------------------------------------- tasks (set v2)
# v1 (easier instances of the same eight families) is kept at git tag pilot-v1; the pilot
# that motivated v2 is in pilot_v1/.

TASK_SET = "v2"


def task_01() -> tuple[dict, dict]:
    alphabet = ["0", "1"]
    ins = ["101", "110", "1101", "00100"]
    outs = [("10", "shorter than 3, so C3 fails"), ("100", "two 0s, so only C1 fails"),
            ("011", "third-to-last symbol is 0, so only C3 fails"), ("0101100", "contains 0101, so only C2 fails")]
    prompt = f"""\
TASK: minimal DFA for a combined lexical rule

Alphabet: Σ = {fmt_set(alphabet)}. Words are finite strings over Σ; ε denotes the empty word.
For a word w, #0(w) denotes the number of occurrences of the symbol 0 in w.

L is the set of words w over Σ that satisfy ALL three conditions:
  (C1) #0(w) ≡ 1 (mod 3), i.e. the number of 0s is 1, 4, 7, 10, ...
  (C2) w does not contain 0101 as a contiguous substring (occurrences may overlap: 010101 contains it twice).
  (C3) w has length at least 3 and its third symbol from the end is 1 (for w = x1 x2 ... xn this is x(n-2)).

Edge cases: ε is not in L. No word of length 0, 1 or 2 is in L, because of (C3).
{examples_text(ins, outs)}

Give the minimal complete DFA for L.

{DFA_ANSWER_SPEC.replace("<ALPHABET>", fmt_set(alphabet))}"""
    task = {
        "id": "task_01",
        "task_set": TASK_SET,
        "family": "product_dfa",
        "title": "Triple-product DFA: mod-3 counter, forbidden 0101, third-to-last symbol is 1",
        "prompt": prompt,
        "answer_schema": "dfa",
        "grader": {"type": "dfa_exact", "params": {"alphabet": alphabet, "require_complete": True, "require_minimal": True}},
        "examples": {"in": ins, "out": [w for w, _ in outs]},
        "difficulty_knobs": {"modulus": 3, "forbidden_pattern": build.T01_FORBIDDEN, "suffix_window": 3},
        "metadata": {
            "why_hard": "Three invariants in one product automaton: a counter mod 3, a self-overlapping forbidden pattern (0101 overlaps itself in 01, so after 010 a 1 is fatal but a 0 falls back), and a 3-symbol window for the third-to-last symbol. The careful product has more states than the minimal DFA (verify_specs.py gives both numbers); the equivalent ones must be merged, and a trap state is needed.",
            "real_world": "Lexer/validator rules that combine a counting constraint with forbidden substrings and a fixed-position suffix condition.",
            "expected_failure_modes": ["wrong fallback after a partial 0101 match", "third-to-last window off by one", "unmerged equivalent product states (non-minimal)", "missing trap state", "wrong counter update"],
            "seed": None,
            "status": DRAFT_NOTE,
        },
    }
    ref = {"task_id": "task_01", "answer": dfa_answer(build.t01_construction()),
           "how_built": "reference.build.t01_construction (counter x last-three-symbols x DEAD), then automata.dfa.minimize"}
    return task, ref


def task_02() -> tuple[dict, dict]:
    alphabet = ["a", "b", "c"]
    wa, wb = build.T02_WINDOW_A, build.T02_WINDOW_B
    ins = ["", "c", "ba", "acba", "abcba", "aaaac"]
    outs = [("a", "the a at 0 never sees a c"), ("b", "the b at 0 never sees an a"),
            ("bca", "the a at 2 is not directly after b and never sees a c"),
            ("abbc", "the b at 1 sees no a among the next 3 symbols"),
            ("abca", "the a at 3 is not directly after b and never sees a c")]
    prompt = f"""\
TASK: minimal DFA for two interacting deadline ("lookahead obligation") rules

Alphabet: Σ = {fmt_set(alphabet)}. Words are finite strings over Σ; ε denotes the empty word.
Positions in a word w are numbered from 0: w = w[0] w[1] ... w[n-1], where n = |w|.

Rule A (every a needs a c). Every position i with w[i] = a creates an A-obligation, EXCEPT when i > 0 and w[i-1] = b (an a immediately preceded by b creates no A-obligation). An a at position 0 always creates one.
An A-obligation created at position i is satisfied if and only if there is a position j with i+1 <= j <= i+{wa} and j < n such that w[j] = c.

Rule B (every b needs an a). Every position i with w[i] = b creates a B-obligation (no exceptions).
A B-obligation created at position i is satisfied if and only if there is a position j with i+1 <= j <= i+{wb} and j < n such that w[j] = a.

L is the set of words in which every obligation (of both kinds) is satisfied. In particular ε is in L. The windows are cut off by the end of the word: an obligation must be satisfied inside the word.

Notes: a single c can satisfy several pending A-obligations at once, and a single a can satisfy several pending B-obligations at once. Only the symbol immediately before an a decides whether that a creates an A-obligation.
{examples_text(ins, outs)}

Give the minimal complete DFA for L.

{DFA_ANSWER_SPEC.replace("<ALPHABET>", fmt_set(alphabet))}"""
    task = {
        "id": "task_02",
        "task_set": TASK_SET,
        "family": "lookahead_dfa",
        "title": f"Two interacting lookahead obligations (a needs c within {wa}, b needs a within {wb})",
        "prompt": prompt,
        "answer_schema": "dfa",
        "grader": {"type": "dfa_exact", "params": {"alphabet": alphabet, "require_complete": True, "require_minimal": True}},
        "examples": {"in": ins, "out": [w for w, _ in outs]},
        "difficulty_knobs": {"window_A": wa, "window_B": wb},
        "metadata": {
            "why_hard": "Two deadlines must be tracked at the same time (the earliest pending A-deadline and the earliest pending B-deadline), plus whether the last symbol was b. The rules feed each other: a b demands an a soon, and an a directly after b is exempt from rule A, while an a later in the window is not. Obligations still open at the end of the word reject.",
            "real_world": "Runtime monitors for protocols with several timeouts ('every request is acknowledged within 4 steps, every retry is followed by a request within 3 steps').",
            "expected_failure_modes": ["tracking the latest instead of the earliest deadline", "one shared deadline for both rules", "exemption applied to an a that is not directly after b", "accepting words that end with an open obligation", "unmerged states (non-minimal)"],
            "seed": None,
            "status": DRAFT_NOTE,
        },
    }
    ref = {"task_id": "task_02", "answer": dfa_answer(build.t02_construction()),
           "how_built": "reference.build.t02_construction (earliest A-deadline x earliest B-deadline x previous-symbol-was-b x DEAD), then minimize"}
    return task, ref


def task_03() -> tuple[dict, dict]:
    m1, m2, seed = build.t03_generate()
    prompt = f"""\
TASK: minimal DFA for a left quotient

Alphabet: Σ = {{a, b}}. Two complete DFAs M1 and M2 over Σ are given below.
The LEFT quotient of L(M1) by L(M2) is
  L = {{ y in Σ* : there exists x in L(M2) such that the concatenation xy is in L(M1) }}.
So x is a PREFIX taken from L(M2), and y is the rest of a word of L(M1). Both x and y may be the empty word ε.

M1: start state {m1.start}; accepting states {fmt_set(m1.accepting)}
{dfa_table(m1)}

M2: start state {m2.start}; accepting states {fmt_set(m2.accepting)}
{dfa_table(m2)}

(Each table row gives the next state on a and on b.)

Give the minimal complete DFA for L.

{DFA_ANSWER_SPEC.replace("<ALPHABET>", "{a, b}")}"""
    task = {
        "id": "task_03",
        "task_set": TASK_SET,
        "family": "left_quotient",
        "title": f"Left quotient of L(M1) by L(M2) for a given {build.T03_SIZES[0]}-state and {build.T03_SIZES[1]}-state DFA",
        "prompt": prompt,
        "answer_schema": "dfa",
        "grader": {"type": "dfa_exact", "params": {"alphabet": ["a", "b"], "require_complete": True, "require_minimal": True}},
        "instance": {"m1": m1.model_dump(), "m2": m2.model_dump()},
        "examples": {"in": [], "out": []},
        "difficulty_knobs": {"m1_states": build.T03_SIZES[0], "m2_states": build.T03_SIZES[1]},
        "metadata": {
            "why_hard": "Two steps, both by hand: (1) find the set S of M1 states that words of L(M2) can lead to (reachability in the product of M1 and M2); (2) L is M1 started in ANY state of S, so it must be determinized by subsets of M1's states and then minimized. The generator guarantees that S has several states but not all, that the left and right quotients differ, and that minimization merges states.",
            "real_world": "'After any valid header, which bodies are acceptable?': residual languages in parsers, protocol analysis and input validation.",
            "expected_failure_modes": ["computing the right quotient instead", "starting from M1's start state instead of the set S", "missing x = ε", "no determinization (treating S as one state)", "not minimizing"],
            "seed": seed,
            "status": DRAFT_NOTE,
        },
    }
    ref = {"task_id": "task_03", "answer": dfa_answer(build.t03_reference(m1, m2)),
           "how_built": "automata.nfa.left_quotient (forward product reachability for the start set, then subsets of M1's states), then minimize"}
    return task, ref


def task_04(modulus: int = 7, target: int = 4) -> tuple[dict, dict]:
    alphabet = ["0", "1", "2"]
    ins = ["11", "1100", "122"]
    outs = [("", "value 0"), ("1", "value 1"), ("201", "value 2 + 0 + 9 = 11 ≡ 4, but one 2"),
            ("22", "value 2 + 6 = 8 ≡ 1"), ("221", "value 2 + 6 + 9 = 17 ≡ 3")]
    prompt = f"""\
TASK: minimal DFA for base-3 divisibility, digits read least significant first

Alphabet: Σ = {fmt_set(alphabet)} (base-3 digits). A word w = d0 d1 ... d(n-1) is read as a base-3 number with the LEAST significant digit FIRST:
  value(w) = d0 + d1·3 + d2·3^2 + ... + d(n-1)·3^(n-1).
Trailing zeros are allowed and do not change the value (2100 has value 2 + 1·3 = 5). The empty word ε has value 0.

L is the set of words w such that BOTH
  (C1) value(w) ≡ {target} (mod {modulus}), and
  (C2) the number of occurrences of the symbol 2 in w is even (zero counts as even).

{examples_text(ins, outs)}

Give the minimal complete DFA for L (it reads w from left to right, i.e. starting with d0).

{DFA_ANSWER_SPEC.replace("<ALPHABET>", fmt_set(alphabet))}"""
    task = {
        "id": "task_04",
        "task_set": TASK_SET,
        "family": "base3_lsb_mod7",
        "title": f"Base-3 value ≡ {target} (mod {modulus}), least significant digit first, and an even number of 2s",
        "prompt": prompt,
        "answer_schema": "dfa",
        "grader": {"type": "dfa_exact", "params": {"alphabet": alphabet, "require_complete": True, "require_minimal": True}},
        "examples": {"in": ins, "out": [w for w, _ in outs]},
        "difficulty_knobs": {"modulus": modulus, "target_residue": target, "digit_order": "least significant first"},
        "metadata": {
            "why_hard": "The obvious construction tracks (value so far mod 7, 3^k mod 7, parity of 2s); it is correct but far from minimal (verify_specs.py gives its size). The minimal DFA needs an insight: track the residue that the digits still to come must have; reading digit d turns s into (s - d)·5 mod 7 (5 is the inverse of 3), and the word is accepted when s = 0 and the parity is even. The obvious answer therefore scores only 0.5.",
            "real_world": "Streaming checks on numbers that arrive least significant digit first (serial arithmetic, little-endian data), where the state budget of a hardware controller matters.",
            "expected_failure_modes": ["most-significant-first arithmetic (r' = 3r + d)", "correct but non-minimal (value x power x parity) construction", "wrong start or accepting state in the reversed construction", "parity not flipped on 2"],
            "seed": None,
            "status": DRAFT_NOTE,
        },
    }
    ref = {"task_id": "task_04", "answer": dfa_answer(build.t04_construction(modulus, target)),
           "how_built": "reference.build.t04_construction (residue the remaining digits must have x parity), then minimize"}
    return task, ref


def task_05() -> tuple[dict, dict]:
    pair = build.T05_PAIR
    prompt = f"""\
TASK: shortest word on which two regular expressions disagree

Alphabet: Σ = {{a, b}}. Regular expressions use exactly this syntax and nothing else:
  a, b     the single symbols
  ()       the empty word ε
  RS       concatenation (written by juxtaposition)
  R|S      union
  R*       zero or more repetitions of R
  R+       one or more repetitions of R
  R?       zero or one occurrence of R
  (R)      grouping
Precedence: the postfix operators *, +, ? bind tightest, then concatenation, then |. There is no whitespace. A regular expression matches a word only if it matches the WHOLE word.

  R1 = {pair.r1}
  R2 = {pair.r2}

It is guaranteed that R1 and R2 do not match the same set of words.
Find a SHORTEST word w over Σ that is matched by exactly one of R1 and R2 (w is in the symmetric difference of the two languages, and no shorter word is). If several shortest words exist, any one of them is accepted.

{WITNESS_ANSWER_SPEC}"""
    task = {
        "id": "task_05",
        "task_set": TASK_SET,
        "family": "regex_witness",
        "title": "Regex pair agreeing on all short words: shortest distinguishing word",
        "prompt": prompt,
        "answer_schema": "witness",
        "grader": {"type": "witness_exact", "params": {"alphabet": ["a", "b"], "r1": pair.r1, "r2": pair.r2}},
        "examples": {"in": [], "out": []},
        "difficulty_knobs": {
            "shortest_witness_length": "computed by verify_specs.py",
            "alternative": {"r1": build.T05_ALT_PAIR.r1, "r2": build.T05_ALT_PAIR.r2},
        },
        "metadata": {
            "why_hard": "R1 and R2 differ by a one-character edit (* to ?) and agree on every word shorter than the witness (verify_specs.py computes the exact length). Extra 'ab' copies at the front are re-absorbed by the tail, so the obvious guesses are matched by both; only a word with two long a-runs in the right places pins the parse. Testing short words mentally finds nothing.",
            "real_world": "Reviewing a regex change in a firewall, log-filter or input-validation rule: 'is this edit behaviour-preserving, and if not, on which input does it differ?'",
            "expected_failure_modes": ["claims or implies equivalence after testing short words", "names a word matched by both", "distinguishing but not shortest", "symbols other than a and b in the answer"],
            "seed": None,
            "family": pair.family,
            "status": DRAFT_NOTE,
        },
    }
    ref = {"task_id": "task_05", "answer": {"witness": build.t05_shortest_witness(pair)},
           "how_built": "shortlex-least word of the symmetric difference via BFS on the product of the two minimal DFAs"}
    return task, ref


def task_06() -> tuple[dict, dict]:
    nfa, seed = build.t06_generate()
    prompt = f"""\
TASK: determinize and minimize an ε-NFA

Alphabet: Σ = {{a, b}}. N is the nondeterministic finite automaton with ε-moves given below.
N accepts a word w if and only if some computation of N starts in the start state, reads all of w (taking any number of ε-moves before, between and after reading symbols) and ends in an accepting state. ε-moves consume no input.

States: {", ".join(nfa.states)}; start state {nfa.start}; accepting states {fmt_set(nfa.accepting)}.
Transitions (each entry is the set of possible next states; "-" means no transition):
{enfa_table(nfa)}

Let L = L(N). Give the minimal complete DFA for L.

{DFA_ANSWER_SPEC.replace("<ALPHABET>", "{a, b}")}"""
    task = {
        "id": "task_06",
        "task_set": TASK_SET,
        "family": "enfa_minimal_dfa",
        "title": f"{build.T06_NFA_STATES}-state ε-NFA → minimal DFA",
        "prompt": prompt,
        "answer_schema": "dfa",
        "grader": {"type": "dfa_exact", "params": {"alphabet": ["a", "b"], "require_complete": True, "require_minimal": True}},
        "instance": {"nfa": nfa.model_dump()},
        "examples": {"in": [], "out": []},
        "difficulty_knobs": {"nfa_states": build.T06_NFA_STATES, "reachable_subsets": "computed by verify_specs.py"},
        "metadata": {
            "why_hard": "The subset construction with ε-closures reaches many subsets (verify_specs.py gives the number; the empty set would count, but here it is never reached); every step needs a correct ε-closure, the start state is the closure of q0 (not q0), and the few indistinguishable subsets must then be found and merged.",
            "real_world": "Compiling regex/lexer specifications and protocol models (NFA -> DFA) by hand or in review.",
            "expected_failure_modes": ["ε-closure errors", "start state taken as {q0} instead of its closure", "a subset missed or duplicated", "no merging of equivalent subsets", "missing empty-set trap"],
            "seed": seed,
            "status": DRAFT_NOTE,
        },
    }
    ref = {"task_id": "task_06", "answer": dfa_answer(build.t06_reference(nfa)),
           "how_built": "automata.nfa.subset_construction (with ε-closures), then minimize"}
    return task, ref


def task_07(max_len: int = 16) -> tuple[dict, dict]:
    terminals = ["(", ")", "[", "]"]
    ins = ["()", "[][]", "([][])", "[[][]][]", "(()())[][]"]
    outs = [("", "empty"), ("(]", "not well-nested"), ("[]", "one top-level [-group, rule 4"),
            ("([])", "a (-group with one [-child, rule 3"), ("[()][]", "a (-group as the child of a [-group, rule 2"),
            ("[[]]", "one top-level [-group, rule 4")]
    prompt = f"""\
TASK: context-free grammar (in Chomsky normal form) for a constrained bracket language

Alphabet: the four symbols ( ) [ ] (round and square brackets).
A word is WELL-NESTED if its symbols can be paired so that every ( is paired with a later ), every [ with a later ], and pairs are properly nested (no crossing, as in ([)]). A paired opening and closing symbol together with everything between them is a GROUP; it is a (-group or a [-group according to its opening symbol. The PARENT of a group is the smallest group that strictly contains it; groups with no parent are TOP-LEVEL groups. The CHILDREN of a group G are the groups whose parent is G.

L is the set of words w such that:
  (1) w is non-empty and well-nested;
  (2) no [-group has a (-group as a child;
  (3) every (-group has an even number of [-groups among its children (zero counts as even);
  (4) the number of top-level [-groups of w is even.
Only children count in (3) and (4): groups nested more deeply do not. There is no limit on the nesting depth.

{examples_text(ins, outs)}

Give a grammar in Chomsky normal form that generates exactly L.

{CFG_ANSWER_SPEC.replace("<TERMINALS>", "( ) [ ]").replace("<N>", str(max_len))}"""
    task = {
        "id": "task_07",
        "task_set": TASK_SET,
        "family": "parity_dyck_cfg",
        "title": "Two-bracket words with parity and parent rules (CNF grammar)",
        "prompt": prompt,
        "answer_schema": "cnf_grammar",
        "grader": {"type": "cfg_bounded", "params": {"alphabet": terminals, "max_len": max_len, "language": "parity_dyck"}},
        "examples": {"in": ins, "out": [w for w, _ in outs]},
        "difficulty_knobs": {"bound_N": max_len},
        "metadata": {
            "why_hard": "The language is not regular (nesting is unbounded), and the rules apply at every level: a sequence of children must carry the parity of its [-groups, (-groups and the word itself follow the parity rule while [-groups may only hold [-groups, and in CNF every empty-content case ((), [], an empty run of children) must be expanded by hand without ε-productions or unit productions.",
            "real_world": "Grammars for nested markup/configuration formats with content models ('this element may only contain these children, and they come in pairs').",
            "expected_failure_modes": ["parity checked only at top level", "parity counted over all descendants instead of children", "( allowed inside [", "lost cases when removing ε (empty groups, odd/even switch)", "non-CNF productions"],
            "seed": None,
            "bound_N_justification": "Every rule already interacts in words of length 4-8 (e.g. ([][]), [[][]][]); N = 16 covers three nesting levels with sibling sequences around them, and the exhaustive check takes well under a second.",
            "status": DRAFT_NOTE,
        },
    }
    ref = {"task_id": "task_07", "answer": build.t07_reference_grammar().model_dump(),
           "how_built": "reference.build.t07_reference_grammar (P/B groups, Ev/Od parity-indexed child sequences)"}
    return task, ref


def task_08(max_len: int = 36) -> tuple[dict, dict]:
    terminals = ["a", "b"]
    ins = ["aba", "aabbaa", "abbaaaa", "aaabbbaaa"]
    outs = [("", "empty"), ("baaa", "i = 0"), ("abba", "2·1 + 1 = 3 but 3j = 6"),
            ("aabbaaa", "2·2 + 3 = 7 but 3j = 6"), ("abab", "not of the form a^i b^j a^k")]
    prompt = f"""\
TASK: context-free grammar (in Chomsky normal form) for a linear-ratio language

Alphabet: {{a, b}}. For an integer n >= 0, a^n denotes the word of n copies of a (similarly b^n); a^0 is the empty word.

L = {{ a^i b^j a^k : i >= 1, k >= 1, j >= 0, and 2i + k = 3j }}.
(So every word in L is a block of a's, then a block of b's, then a block of a's, where both a-blocks are non-empty and twice the length of the first a-block plus the length of the second a-block equals three times the length of the b-block.)

{examples_text(ins, outs)}

Give a grammar in Chomsky normal form that generates exactly L.

{CFG_ANSWER_SPEC.replace("<TERMINALS>", "a b").replace("<N>", str(max_len))}"""
    task = {
        "id": "task_08",
        "task_set": TASK_SET,
        "family": "ratio_cfg",
        "title": "Linear-ratio language a^i b^j a^k with 2i + k = 3j (CNF grammar)",
        "prompt": prompt,
        "answer_schema": "cnf_grammar",
        "grader": {"type": "cfg_bounded", "params": {"alphabet": terminals, "max_len": max_len, "language": "ratio_2i_k_3j"}},
        "examples": {"in": ins, "out": [w for w, _ in outs]},
        "difficulty_knobs": {"bound_N": max_len},
        "metadata": {
            "why_hard": "Each leading a is worth 2, each trailing a 1, each b costs 3, so the b-block must be split between the two a-blocks, and one or two b's are shared by both sides. The split depends on i mod 3 (three cases: L1 R1, a L b R a, aa L bb R aa with L = (aaa)^m (bb)^m and R = b^t (aaa)^t); the CNF conversion must keep every case and every empty/non-empty combination.",
            "real_world": "Grammars for formats with counted, length-linked fields; deciding how a counting constraint can be written as nested matching.",
            "expected_failure_modes": ["i + k = 2j or other wrong ratio", "missing one of the three remainder cases", "wrong residue pairing between the two a-blocks", "overgeneration by independent a-blocks", "non-CNF productions"],
            "seed": None,
            "bound_N_justification": "The language is sparse (verify_specs.py counts the words up to N), so N = 36 is cheap and covers several nesting levels on both sides in each of the three cases.",
            "replaces": "the original pre-v1 T08 {a^i b^j a^k : i + k = 2j, i > k >= 1} is not context-free; see scripts/check_task08_noncf.py",
            "status": DRAFT_NOTE,
        },
    }
    ref = {"task_id": "task_08", "answer": build.t08_reference_grammar().model_dump(),
           "how_built": "reference.build.t08_reference_grammar (hand CNF conversion of the three-case grammar in its docstring)"}
    return task, ref


TASK_BUILDERS = {
    "task_01_product_dfa": task_01,
    "task_02_lookahead_dfa": task_02,
    "task_03_left_quotient": task_03,
    "task_04_base3_lsb_mod7": task_04,
    "task_05_regex_witness": task_05,
    "task_06_enfa_minimal_dfa": task_06,
    "task_07_parity_dyck_cfg": task_07,
    "task_08_ratio_cfg": task_08,
}


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_all() -> dict[Path, str]:
    """Path -> file content for every task and reference file."""
    files = {}
    for stem, builder in TASK_BUILDERS.items():
        task, ref = builder()
        files[TASKS_DIR / f"{stem}.json"] = dump(task)
        files[REFERENCE_DIR / f"{task['id']}.ref.json"] = dump(ref)
    return files


def main(argv: list[str]) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):  # Windows consoles default to cp1252 (no ε)
        sys.stdout.reconfigure(encoding="utf-8")
    files = render_all()
    if "--check" in argv:
        stale = [p for p, text in files.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        for p in stale:
            print(f"stale: {p.relative_to(ROOT)}")
        return 1 if stale else 0
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
