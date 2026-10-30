"""Reference solutions, built by *construction code* (never typed in by hand), plus the
seeded instance generators for Tasks 03, 05 and 06 with their asserted constraints.

Nothing here is imported by the harness. ``scripts/generate_instances.py`` writes the
outputs to ``tasks/*.json`` (inputs/prompts) and ``reference/*.ref.json`` (answers);
``scripts/verify_specs.py`` recomputes every number the docs quote.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from automata.cfg import Grammar, Production
from automata.dfa import (
    DFA,
    complement,
    equivalent,
    intersect,
    minimal_size,
    minimize,
    shortest_accepted,
)
from automata.nfa import EPS, ENFA, epsilon_closure, right_quotient, subset_construction
from automata.regex import to_min_dfa

# =========================================================================== Task 01


def t01_construction(modulus: int = 3, target: int = 1) -> DFA:
    """Product construction for L = { #0(w) = 1 (mod 3), no '010' substring, not ending '11' }.

    State = (c, s): c = number of 0s mod 3, s = last (up to) two symbols read; plus DEAD,
    entered as soon as '010' has appeared (s + next symbol == '010'). Accepting: c == 1 and
    s does not end with '11'. Built by BFS, so only reachable states appear.
    (modulus=1, target=0 gives the suffix conditions alone.)"""
    alphabet = ["0", "1"]

    def name(c: int, s: str) -> str:
        return f"c{c}_{s or 'e'}"

    start = (0, "")
    seen, queue, transitions, accepting = {start}, [start], {}, []
    while queue:
        c, s = queue.pop(0)
        if c == target and not s.endswith("11"):
            accepting.append(name(c, s))
        row = {}
        for x in alphabet:
            if (s + x).endswith("010"):
                row[x] = "DEAD"
                continue
            nxt = ((c + (x == "0")) % modulus, (s + x)[-2:])
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
            row[x] = name(*nxt)
        transitions[name(c, s)] = row
    transitions["DEAD"] = {x: "DEAD" for x in alphabet}
    return DFA(
        states=list(transitions), alphabet=alphabet, start=name(*start), accepting=accepting,
        transitions=transitions,
    )


def t01_naive_product_size() -> int:
    """Reachable states of (mod-3 counter) x (minimal DFA for 'no 010 and not ending 11'),
    i.e. the product a careful human would build before minimizing."""
    suffix_min = minimize(t01_construction(modulus=1, target=0))
    counter = DFA(
        states=["k0", "k1", "k2"], alphabet=["0", "1"], start="k0", accepting=["k1"],
        transitions={f"k{i}": {"0": f"k{(i + 1) % 3}", "1": f"k{i}"} for i in range(3)},
    )
    return len(intersect(counter, suffix_min).states)


# =========================================================================== Task 02


def t02_construction(window: int = 3) -> DFA:
    """Lookahead obligations over {a,b,c} with window W.

    State = (r, prev_b): r = steps left before the *earliest* pending obligation expires
    (0 = nothing pending), prev_b = last symbol was 'b'; plus DEAD. Reading c clears every
    pending obligation. Reading a non-c symbol decrements r; reaching 0 from 1 means the
    earliest obligation's window ended without a c -> DEAD. Reading 'a' when not prev_b
    creates an obligation with W steps; if one is already pending it is earlier, so it
    keeps governing (any c inside its window is also inside the new one's window).
    Accepting: nothing pending."""
    alphabet = ["a", "b", "c"]

    def name(r: int, prev_b: bool) -> str:
        return f"r{r}{'_b' if prev_b else ''}"

    start = (0, False)
    seen, queue, transitions, accepting = {start}, [start], {}, []
    while queue:
        r, prev_b = queue.pop(0)
        if r == 0:
            accepting.append(name(r, prev_b))
        row = {}
        for x in alphabet:
            if x == "c":
                nxt = (0, False)
            else:
                if r == 1:
                    row[x] = "DEAD"
                    continue
                nr = r - 1 if r > 0 else 0
                if x == "a" and not prev_b and nr == 0:
                    nr = window
                nxt = (nr, x == "b")
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
            row[x] = name(*nxt)
        transitions[name(r, prev_b)] = row
    transitions["DEAD"] = {x: "DEAD" for x in alphabet}
    return DFA(
        states=list(transitions), alphabet=alphabet, start=name(*start), accepting=accepting,
        transitions=transitions,
    )


def t02_member(w: str, window: int = 3) -> bool:
    """Direct reading of the prompt's definition (independent of the DFA construction)."""
    for i, ch in enumerate(w):
        if ch == "a" and not (i > 0 and w[i - 1] == "b"):
            if "c" not in w[i + 1 : i + 1 + window]:
                return False
    return True


# =========================================================================== Task 04


def t04_construction(modulus: int = 7, target: int = 4) -> DFA:
    """Base-3, most significant digit first: reading digit d maps value r to (3r + d) mod m.
    State = (r, parity of the number of 2s). Start (0, even) since value(ε) = 0."""
    alphabet = ["0", "1", "2"]
    transitions = {}
    for r in range(modulus):
        for p in (0, 1):
            transitions[f"r{r}p{p}"] = {
                d: f"r{(3 * r + int(d)) % modulus}p{p ^ (d == '2')}" for d in alphabet
            }
    return DFA(
        states=list(transitions), alphabet=alphabet, start="r0p0", accepting=[f"r{target}p0"],
        transitions=transitions,
    )


def t04_member(w: str, modulus: int = 7, target: int = 4) -> bool:
    return int(w or "0", 3) % modulus == target and w.count("2") % 2 == 0


# =========================================================================== Task 03


def random_complete_dfa(rng: random.Random, n: int, alphabet: list[str], prefix: str) -> DFA:
    states = [f"{prefix}{i}" for i in range(n)]
    return DFA(
        states=states,
        alphabet=alphabet,
        start=states[0],
        accepting=[q for q in states if rng.random() < 0.4],
        transitions={q: {a: rng.choice(states) for a in alphabet} for q in states},
    )


def t03_constraint_failures(m1: DFA, m2: DFA) -> list[str]:
    """Every generator constraint from PROJECT_GUIDE §5/T03 that the pair violates."""
    fails = []
    for name, m in (("M1", m1), ("M2", m2)):
        if len(m.states) != 5 or minimal_size(m) != 5:
            fails.append(f"{name} is not a minimal complete 5-state DFA")
    if shortest_accepted(m2) is None:
        fails.append("L(M2) is empty")
    q = right_quotient(m1, m2)
    if equivalent(q, m1)[0]:
        fails.append("quotient equals L(M1)")
    if shortest_accepted(q) is None:
        fails.append("quotient is empty")
    if shortest_accepted(complement(q)) is None:
        fails.append("quotient is Sigma*")
    if minimal_size(q) < 3:
        fails.append("minimal quotient DFA has fewer than 3 states")
    return fails


def t03_generate(base_seed: int = 3003) -> tuple[DFA, DFA, int]:
    """First seed >= base_seed whose random pair satisfies every constraint."""
    seed = base_seed
    while True:
        rng = random.Random(seed)
        m1 = random_complete_dfa(rng, 5, ["a", "b"], "p")
        m2 = random_complete_dfa(rng, 5, ["a", "b"], "r")
        if not t03_constraint_failures(m1, m2):
            return m1, m2, seed
        seed += 1


def t03_reference(m1: DFA, m2: DFA) -> DFA:
    return minimize(right_quotient(m1, m2))


# =========================================================================== Task 06

T06_SUBSETS = 11


def random_enfa(rng: random.Random, n: int = 5) -> ENFA:
    states = [f"q{i}" for i in range(n)]
    transitions: dict[str, dict[str, list[str]]] = {}
    for q in states:
        row = {}
        for a in ("a", "b"):
            targets = [r for r in states if rng.random() < 0.25]
            if targets:
                row[a] = targets
        eps = [r for r in states if r != q and rng.random() < 0.12]
        if eps:
            row[EPS] = eps
        transitions[q] = row
    accepting = [q for q in states if rng.random() < 0.3] or [states[-1]]
    return ENFA(states=states, alphabet=["a", "b"], start="q0", accepting=accepting, transitions=transitions)


def t06_constraint_failures(nfa: ENFA) -> list[str]:
    """Spec constraint (11 reachable subsets, counting the empty subset when reachable)
    plus stricter ones logged in docs/OPEN_QUESTIONS.md: ε-moves must matter (>= 2 of
    them, start's ε-closure has >= 2 states) and minimization must merge something."""
    fails = []
    dfa, n_subsets = subset_construction(nfa)
    if n_subsets != T06_SUBSETS:
        fails.append(f"{n_subsets} reachable subsets, need {T06_SUBSETS}")
    n_eps = sum(len(row.get(EPS, [])) for row in nfa.transitions.values())
    if n_eps < 2:
        fails.append("fewer than 2 ε-moves")
    if len(epsilon_closure(nfa, [nfa.start])) < 2:
        fails.append("start state's ε-closure is trivial")
    m = minimal_size(dfa)
    if not 6 <= m < n_subsets:
        fails.append(f"minimal DFA has {m} states; need 6 <= size < {n_subsets}")
    return fails


def t06_generate(base_seed: int = 6006) -> tuple[ENFA, int]:
    seed = base_seed
    while True:
        nfa = random_enfa(random.Random(seed))
        if not t06_constraint_failures(nfa):
            return nfa, seed
        seed += 1


def t06_reference(nfa: ENFA) -> DFA:
    return minimize(subset_construction(nfa)[0])


# =========================================================================== Task 05


@dataclass(frozen=True)
class RegexPair:
    r1: str
    r2: str
    family: str
    rationale: str


T05_MIN_WITNESS_LEN = 9  # the regexes must agree on every string of length <= 8

# Family: a one-character quantifier edit X* -> X? in front of a tail that can re-absorb
# copies of X. Found by scripts/search_t05_pairs.py (seeded search over this family keeping
# only pairs whose "obvious" witness XX + shortest(tail) does NOT distinguish them), then
# proved by hand:
#   R1 words are (ba)^m b^p a (ba)^q a with m >= 0, p >= 1, q >= 1; R2 is the same with m <= 1.
#   If p = 1 the word is (ba)^(m+1+q) a, which R2 also matches (m=0, p=1, q=m+q), so the
#   obvious guess babababaa fails. If p >= 2, the only run of >= 2 b's in any R1/R2 parse
#   is the b+ block, which pins the parse, so m >= 2 is needed. Shortest: m=2, p=2, q=1,
#   i.e. ba ba bb a ba a = bababbabaa (length 10, the unique shortest witness).
T05_PAIR = RegexPair(
    r1="(ba)*b+a(ba)+a",
    r2="(ba)?b+a(ba)+a",
    family="quantifier edit X* -> X? before a tail that can re-absorb copies of X",
    rationale="Re-parsing: extra 'ba' copies are absorbed by b+a(ba)+ unless a 'bb' pins the parse.",
)
# Harder alternative kept as a difficulty knob (shortest witness length 12):
T05_HARDER_PAIR = RegexPair(
    r1="(ba)*ba?a(ba)+b(aa|b)b",
    r2="(ba)?ba?a(ba)+b(aa|b)b",
    family=T05_PAIR.family,
    rationale="Same family, longer forced witness.",
)


def t05_shortest_witness(pair: RegexPair) -> str:
    same, w = equivalent(to_min_dfa(pair.r1, ["a", "b"]), to_min_dfa(pair.r2, ["a", "b"]))
    if same or w is None:
        raise ValueError("regexes are equivalent")
    return w


# =========================================================================== Task 07


def t07_reference_grammar(max_depth: int = 3) -> Grammar:
    """CNF grammar with depth-indexed nonterminals.

    A_h = non-empty sequence of groups allowed at top level or directly inside '(',
          each group with at most h levels (itself included);
    B_h = the same, but directly inside '[' (so '[' groups only);
    X_h = A_(h-1) ')'   and   Y_h = B_(h-1) ']'   (bodies of non-empty groups).
    Start = A_3. B_3 is never needed (B_h only appears inside a group, so h < 3).
    Every alternative is written out so there are no unit productions."""
    p: list[tuple[str, list[str]]] = [("LP", ["("]), ("RP", [")"]), ("LB", ["["]), ("RB", ["]"])]
    for h in range(1, max_depth + 1):
        a, b = f"A{h}", f"B{h}"
        p += [(a, ["LP", "RP"]), (a, ["LB", "RB"]), (a, [a, a])]
        if h < max_depth:
            p += [(b, ["LB", "RB"]), (b, [b, b])]
        if h >= 2:
            x, y = f"X{h}", f"Y{h}"
            p += [(a, ["LP", x]), (x, [f"A{h - 1}", "RP"])]
            p += [(a, ["LB", y]), (y, [f"B{h - 1}", "RB"])]
            if h < max_depth:
                p.append((b, ["LB", y]))
    return Grammar(
        start=f"A{max_depth}", productions=[Production(lhs=l, rhs=r) for l, r in p]
    )


# =========================================================================== Task 08


def t08_reference_grammar() -> Grammar:
    """CNF conversion of  S -> A1 B1 | a A b B a,  A -> aaAb | ε,  B -> bBaa | ε.

    A1 = (aa)^n b^n (n >= 1) and B1 = b^t (aa)^t (t >= 1). Even case: S -> A1 B1.
    Odd case a A b B a with A, B possibly ε gives four shapes: aba, a A1 b a, a b B1 a,
    a A1 b B1 a, each split into binary rules via helper nonterminals M1..M5."""
    rules = [
        ("S", ["A1", "B1"]),
        ("S", ["TA", "M1"]), ("M1", ["TB", "TA"]),          # a b a
        ("S", ["TA", "M2"]), ("M2", ["A1", "M1"]),          # a A1 b a
        ("S", ["TA", "M3"]), ("M3", ["TB", "M4"]), ("M4", ["B1", "TA"]),  # a b B1 a
        ("S", ["TA", "M5"]), ("M5", ["A1", "M3"]),          # a A1 b B1 a
        ("A1", ["TA", "E1"]), ("E1", ["TA", "TB"]),         # a a b
        ("A1", ["TA", "F1"]), ("F1", ["TA", "G1"]), ("G1", ["A1", "TB"]),  # a a A1 b
        ("B1", ["TB", "AA"]),                               # b a a
        ("B1", ["TB", "I1"]), ("I1", ["B1", "AA"]),         # b B1 a a
        ("AA", ["TA", "TA"]),
        ("TA", ["a"]), ("TB", ["b"]),
    ]
    return Grammar(start="S", productions=[Production(lhs=l, rhs=r) for l, r in rules])


def t08_original_member(w: str) -> bool:
    """The ORIGINAL (rejected) Task 08 language: a^i b^j a^k with i + k = 2j and i > k >= 1."""
    i = len(w) - len(w.lstrip("a"))
    rest = w[i:]
    j = len(rest) - len(rest.lstrip("b"))
    k = len(rest) - j
    return rest[j:] == "a" * k and k >= 1 and i > k and i + k == 2 * j
