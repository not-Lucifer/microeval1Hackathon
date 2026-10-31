"""Reference solutions, built by *construction code* (never typed in by hand), plus the
seeded instance generators for Tasks 03, 05 and 06 with their asserted constraints.

This is task set v2 (see docs/PROJECT_GUIDE.md §5). The v1 tasks were easier versions of
the same eight families; they are kept, with their pilot transcripts, at git tag pilot-v1.

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
from automata.nfa import (
    EPS,
    ENFA,
    epsilon_closure,
    left_quotient,
    right_quotient,
    states_reached_by_language,
    subset_construction,
)
from automata.regex import to_min_dfa

# =========================================================================== Task 01

T01_FORBIDDEN = "0101"


def t01_member(w: str, modulus: int = 3, target: int = 1) -> bool:
    """Direct reading of the prompt: #0(w) = 1 (mod 3), no 0101, third-to-last symbol is 1."""
    return (
        w.count("0") % modulus == target
        and T01_FORBIDDEN not in w
        and len(w) >= 3 and w[-3] == "1"
    )


def t01_construction(modulus: int = 3, target: int = 1) -> DFA:
    """Product construction for L = { #0(w) = 1 (mod 3), no '0101' substring, |w| >= 3 and
    the third symbol from the end is 1 }.

    State = (c, s): c = number of 0s mod 3, s = last (up to) three symbols; plus DEAD,
    entered as soon as '0101' has appeared (s + next symbol ends with '0101'; three remembered
    symbols are exactly enough to see that). Accepting: c == target and s is three symbols
    long and starts with 1. Built by BFS, so only reachable states appear.
    (modulus=1, target=0 gives the pattern and suffix conditions alone.)"""
    alphabet = ["0", "1"]

    def name(c: int, s: str) -> str:
        return f"c{c}_{s or 'e'}"

    start = (0, "")
    seen, queue, transitions, accepting = {start}, [start], {}, []
    while queue:
        c, s = queue.pop(0)
        if c == target and len(s) == 3 and s[0] == "1":
            accepting.append(name(c, s))
        row = {}
        for x in alphabet:
            if (s + x).endswith(T01_FORBIDDEN):
                row[x] = "DEAD"
                continue
            nxt = ((c + (x == "0")) % modulus, (s + x)[-3:])
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
    """Reachable states of (mod-3 counter) x (minimal DFA for 'no 0101 and third-to-last
    symbol is 1'), i.e. the product a careful human would build before minimizing."""
    suffix_min = minimize(t01_construction(modulus=1, target=0))
    counter = DFA(
        states=["k0", "k1", "k2"], alphabet=["0", "1"], start="k0", accepting=["k1"],
        transitions={f"k{i}": {"0": f"k{(i + 1) % 3}", "1": f"k{i}"} for i in range(3)},
    )
    return len(intersect(counter, suffix_min).states)


# =========================================================================== Task 02

T02_WINDOW_A, T02_WINDOW_B = 4, 3


def t02_member(w: str, window_a: int = T02_WINDOW_A, window_b: int = T02_WINDOW_B) -> bool:
    """Direct reading of the prompt's definition (independent of the DFA construction):
    every a not directly after a b needs a c among the next window_a symbols, and every b
    needs an a among the next window_b symbols (both windows cut off by the end of w)."""
    for i, ch in enumerate(w):
        if ch == "a" and not (i > 0 and w[i - 1] == "b") and "c" not in w[i + 1 : i + 1 + window_a]:
            return False
        if ch == "b" and "a" not in w[i + 1 : i + 1 + window_b]:
            return False
    return True


def t02_construction(window_a: int = T02_WINDOW_A, window_b: int = T02_WINDOW_B) -> DFA:
    """Two interacting obligation rules over {a,b,c}.

    State = (ra, rb, prev_b): ra = symbols left before the *earliest* pending a-obligation
    expires (0 = none pending), rb = the same for b-obligations, prev_b = last symbol was b;
    plus DEAD. Reading x:
      * a c clears every pending a-obligation; any other symbol decrements ra, and if ra was
        1 the earliest a-obligation's window has ended without a c -> DEAD;
      * an a clears every pending b-obligation; any other symbol decrements rb (1 -> DEAD);
      * then x creates its own obligation: an a (unless prev_b) one with window_a, a b one
        with window_b. If one of the same kind is already pending it is earlier and keeps
        governing (a symbol inside its window is also inside the new one's window).
    Accepting: nothing pending (ra == rb == 0). Built by BFS from (0, 0, False)."""
    alphabet = ["a", "b", "c"]

    def name(ra: int, rb: int, prev_b: bool) -> str:
        return f"a{ra}b{rb}{'_afterb' if prev_b else ''}"

    start = (0, 0, False)
    seen, queue, transitions, accepting = {start}, [start], {}, []
    while queue:
        ra, rb, prev_b = queue.pop(0)
        if ra == 0 and rb == 0:
            accepting.append(name(ra, rb, prev_b))
        row = {}
        for x in alphabet:
            if (x != "c" and ra == 1) or (x != "a" and rb == 1):
                row[x] = "DEAD"
                continue
            na = 0 if x == "c" else max(ra - 1, 0)
            nb = 0 if x == "a" else max(rb - 1, 0)
            if x == "a" and not prev_b and na == 0:
                na = window_a
            if x == "b" and nb == 0:
                nb = window_b
            nxt = (na, nb, x == "b")
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
            row[x] = name(*nxt)
        transitions[name(ra, rb, prev_b)] = row
    transitions["DEAD"] = {x: "DEAD" for x in alphabet}
    return DFA(
        states=list(transitions), alphabet=alphabet, start=name(*start), accepting=accepting,
        transitions=transitions,
    )


# =========================================================================== Task 04


def t04_member(w: str, modulus: int = 7, target: int = 4) -> bool:
    """Least significant digit first: value(w) = sum of w[i] * 3^i."""
    value = sum(int(d) * 3**i for i, d in enumerate(w))
    return value % modulus == target and w.count("2") % 2 == 0


def t04_construction(modulus: int = 7, target: int = 4) -> DFA:
    """Base-3, LEAST significant digit first, value = target (mod m), even number of 2s.

    Insight: after reading the low digits u (k of them), w is in L iff the digits still to
    come, read as their own number v, satisfy value(u) + 3^k * v = target (mod m). So keep
    s = the residue that v must have. Start: s = target (nothing read). Reading digit d means
    v = d + 3 * v', so the rest v' must be (s - d) * 3^-1 (mod m). Accept when s = 0 (no
    digits left, v = 0) and the parity of 2s is even. Needs gcd(3, m) = 1. This gives
    m x 2 states, the same count as the most-significant-first DFA, instead of the obvious
    (value mod m) x (3^k mod m) x parity construction (t04_naive_size)."""
    inverse = pow(3, -1, modulus)
    alphabet = ["0", "1", "2"]
    transitions = {}
    for s in range(modulus):
        for p in (0, 1):
            transitions[f"need{s}p{p}"] = {
                d: f"need{((s - int(d)) * inverse) % modulus}p{p ^ (d == '2')}" for d in alphabet
            }
    return DFA(
        states=list(transitions), alphabet=alphabet, start=f"need{target}p0", accepting=["need0p0"],
        transitions=transitions,
    )


def t04_naive_construction(modulus: int = 7, target: int = 4) -> DFA:
    """The obvious construction: state = (value so far mod m, 3^k mod m, parity of 2s),
    built by BFS from (0, 1, even). Correct but far from minimal."""
    alphabet = ["0", "1", "2"]
    start = (0, 1 % modulus, 0)
    seen, queue, transitions, accepting = {start}, [start], {}, []
    while queue:
        r, e, p = queue.pop(0)
        if r == target and p == 0:
            accepting.append(f"r{r}e{e}p{p}")
        row = {}
        for d in alphabet:
            nxt = ((r + int(d) * e) % modulus, (3 * e) % modulus, p ^ (d == "2"))
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
            row[d] = "r{}e{}p{}".format(*nxt)
        transitions[f"r{r}e{e}p{p}"] = row
    return DFA(states=list(transitions), alphabet=alphabet, start="r{}e{}p{}".format(*start),
               accepting=accepting, transitions=transitions)


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


T03_SIZES = (5, 3)  # states of M1, M2
T03_MINIMAL_RANGE = (12, 16)


def t03_constraint_failures(m1: DFA, m2: DFA) -> list[str]:
    """Every generator constraint for the v2 instance that the pair violates."""
    fails = []
    for name, m, n in (("M1", m1, T03_SIZES[0]), ("M2", m2, T03_SIZES[1])):
        if len(m.states) != n or minimal_size(m) != n:
            fails.append(f"{name} is not a minimal complete {n}-state DFA")
    if shortest_accepted(m2) is None:
        fails.append("L(M2) is empty")
    start_set = states_reached_by_language(m1, m2)
    if len(start_set) < 2:
        fails.append("fewer than 2 start states: no determinization needed")
    if len(start_set) == len(m1.states):
        fails.append("every M1 state is reachable by L(M2): M2 would not matter")
    q = left_quotient(m1, m2)
    if equivalent(q, m1)[0]:
        fails.append("quotient equals L(M1)")
    if equivalent(q, right_quotient(m1, m2))[0]:
        fails.append("left quotient equals the right quotient (confusing them would pass)")
    if shortest_accepted(q) is None:
        fails.append("quotient is empty")
    if shortest_accepted(complement(q)) is None:
        fails.append("quotient is Sigma*")
    m = minimal_size(q)
    lo, hi = T03_MINIMAL_RANGE
    if not lo <= m <= hi:
        fails.append(f"minimal quotient DFA has {m} states; need {lo}..{hi}")
    if m >= len(q.states):
        fails.append("minimization merges nothing")
    return fails


def t03_generate(base_seed: int = 3003) -> tuple[DFA, DFA, int]:
    """First seed >= base_seed whose random pair satisfies every constraint."""
    seed = base_seed
    while True:
        rng = random.Random(seed)
        m1 = random_complete_dfa(rng, T03_SIZES[0], ["a", "b"], "p")
        m2 = random_complete_dfa(rng, T03_SIZES[1], ["a", "b"], "r")
        if not t03_constraint_failures(m1, m2):
            return m1, m2, seed
        seed += 1


def t03_reference(m1: DFA, m2: DFA) -> DFA:
    return minimize(left_quotient(m1, m2))


# =========================================================================== Task 06

T06_NFA_STATES = 7
T06_SUBSET_RANGE = (16, 20)
T06_MINIMAL_MIN = 12


def random_enfa(rng: random.Random, n: int = 5, p_sym: float = 0.25, p_eps: float = 0.12) -> ENFA:
    states = [f"q{i}" for i in range(n)]
    transitions: dict[str, dict[str, list[str]]] = {}
    for q in states:
        row = {}
        for a in ("a", "b"):
            targets = [r for r in states if rng.random() < p_sym]
            if targets:
                row[a] = targets
        eps = [r for r in states if r != q and rng.random() < p_eps]
        if eps:
            row[EPS] = eps
        transitions[q] = row
    accepting = [q for q in states if rng.random() < 0.3] or [states[-1]]
    return ENFA(states=states, alphabet=["a", "b"], start="q0", accepting=accepting, transitions=transitions)


def t06_constraint_failures(nfa: ENFA) -> list[str]:
    """v2 constraints: 7 NFA states; 16..20 reachable subsets (the empty subset counts when
    reachable); ε-moves must matter (>= 3 of them, start's ε-closure has >= 2 states); the
    minimal DFA has >= 12 states and fewer than the subsets (minimization merges something)."""
    fails = []
    if len(nfa.states) != T06_NFA_STATES:
        fails.append(f"NFA has {len(nfa.states)} states, need {T06_NFA_STATES}")
    dfa, n_subsets = subset_construction(nfa)
    lo, hi = T06_SUBSET_RANGE
    if not lo <= n_subsets <= hi:
        fails.append(f"{n_subsets} reachable subsets, need {lo}..{hi}")
    n_eps = sum(len(row.get(EPS, [])) for row in nfa.transitions.values())
    if n_eps < 3:
        fails.append("fewer than 3 ε-moves")
    if len(epsilon_closure(nfa, [nfa.start])) < 2:
        fails.append("start state's ε-closure is trivial")
    m = minimal_size(dfa)
    if not T06_MINIMAL_MIN <= m < n_subsets:
        fails.append(f"minimal DFA has {m} states; need {T06_MINIMAL_MIN} <= size < {n_subsets}")
    return fails


def t06_generate(base_seed: int = 6006) -> tuple[ENFA, int]:
    seed = base_seed
    while True:
        nfa = random_enfa(random.Random(seed), n=T06_NFA_STATES, p_sym=0.15, p_eps=0.08)
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


T05_MIN_WITNESS_LEN = 14  # the regexes must agree on every string of length <= 13

# Family: a one-character quantifier edit X* -> X? in front of a tail that can re-absorb
# copies of X. Found by a seeded search over this family (scripts/search_t05_pairs.py
# --min-len 14), keeping only pairs whose "obvious" witness XX + shortest(tail) does NOT
# distinguish them. Hand proof for the chosen pair:
#   Every word of R1 or R2 is a b c ... where each b stands alone between runs of a's, so a
#   word is fixed by its sequence of a-run lengths. R1 = (ab)^m a^p b (ab)^q a^r (ba)^u a has
#   run sequence 1^m, p, 1^q, r, 1^(u-1), 2 with m >= 0, p, q, r >= 1, u >= 2; R2 is the same
#   with m <= 1, so R2 is a subset of R1 and the difference is R1 minus R2. A run sequence
#   s_1 .. s_n (s_n = 2) is in R1 iff positions i < j < n can be chosen with j - i >= 2,
#   n - j >= 2 and every other s_t = 1 (then p = s_i, r = s_j, m = i - 1). It is in R2 iff
#   this is possible with i <= 2. If at most one run other than the last exceeds 1, a choice
#   with i = 1 or i = 2 always exists whenever any choice does, so the word is in both.
#   So a word in R1 minus R2 has two runs > 1 (besides the last), which pins i and j, at
#   positions i >= 3 and j >= i + 2, n >= j + 2. The cheapest is 1,1,2,1,2,1,2: the word
#   ab ab aab ab aab ab aa = ababaababaababaa (length 16, the unique shortest witness).
T05_PAIR = RegexPair(
    r1="(ab)*a+b(ab)+a+(ba)+(ba)+a",
    r2="(ab)?a+b(ab)+a+(ba)+(ba)+a",
    family="quantifier edit X* -> X? before a tail that can re-absorb copies of X",
    rationale="Re-parsing: extra 'ab' copies are absorbed by the tail unless two long a-runs pin the parse.",
)
# Alternative of the same family kept as a knob (unique shortest witness, length 14):
T05_ALT_PAIR = RegexPair(
    r1="(aab)*a(ab)*a+bbab",
    r2="(aab)?a(ab)*a+bbab",
    family=T05_PAIR.family,
    rationale="Same family, simpler regexes, shorter forced witness.",
)


def t05_shortest_witness(pair: RegexPair) -> str:
    same, w = equivalent(to_min_dfa(pair.r1, ["a", "b"]), to_min_dfa(pair.r2, ["a", "b"]))
    if same or w is None:
        raise ValueError("regexes are equivalent")
    return w


# =========================================================================== Task 07


def t07_reference_grammar() -> Grammar:
    """CNF grammar for non-empty bracket words where a [-group has no (-children and every
    (-group, and the word itself, has an even number of [-children.

    Items are groups: P = a (-group, B = a [-group.
      P  = ( )  |  ( Ev )            (the children of a (-group: even number of B items)
      B  = [ ]  |  [ Bs ]            (the children of a [-group: [-groups only)
      Bs = B | B Bs                  (non-empty sequence of B)
      Ev = non-empty item sequence with an EVEN number of B items:  P | P Ev | B Od
      Od = item sequence with an ODD number of B items:            B | B Ev | P Od
    Start = Ev (the word behaves like the inside of a (-group). The unit alternatives
    Ev -> P, Od -> B and Bs -> B are written out through P's and B's own rules, and X, Y
    carry the closing bracket, so every production is in CNF."""
    p: list[tuple[str, list[str]]] = [("LP", ["("]), ("RP", [")"]), ("LB", ["["]), ("RB", ["]"])]
    p += [("P", ["LP", "RP"]), ("P", ["LP", "X"]), ("X", ["Ev", "RP"])]
    p += [("B", ["LB", "RB"]), ("B", ["LB", "Y"]), ("Y", ["Bs", "RB"])]
    p += [("Bs", ["LB", "RB"]), ("Bs", ["LB", "Y"]), ("Bs", ["B", "Bs"])]
    p += [("Ev", ["LP", "RP"]), ("Ev", ["LP", "X"]), ("Ev", ["P", "Ev"]), ("Ev", ["B", "Od"])]
    p += [("Od", ["LB", "RB"]), ("Od", ["LB", "Y"]), ("Od", ["B", "Ev"]), ("Od", ["P", "Od"])]
    return Grammar(start="Ev", productions=[Production(lhs=l, rhs=r) for l, r in p])


# =========================================================================== Task 08


def t08_reference_grammar() -> Grammar:
    """CNF conversion of  S -> L1 R1 | a L b R a | aa L bb R aa,
    L -> aaa L bb | ε,  R -> b R aaa | ε   for { a^i b^j a^k : i, k >= 1, 2i + k = 3j }.

    Each leading a is worth 2, each trailing a 1, each b costs 3. Split by i mod 3:
      i = 3m:     a^3m b^2m  b^t a^3t             = L1 R1   (m, t >= 1, so i, k >= 1)
      i = 3m + 1: a (a^3m b^2m) b (b^t a^3t) a    = a L b R a      (the middle b takes 2 from
                  the left a's and 1 from the right a)
      i = 3m + 2: aa (a^3m b^2m) bb (b^t a^3t) aa = aa L bb R aa   (two shared b's)
    L1 = (aaa)^m (bb)^m and R1 = b^t (aaa)^t (m, t >= 1); L, R may be empty, which gives four
    shapes per shared case, each split into binary rules via helpers C1..C5 and D1..D5."""
    rules = [
        ("TA", ["a"]), ("TB", ["b"]), ("AA", ["TA", "TA"]), ("AAA", ["TA", "AA"]), ("BB", ["TB", "TB"]),
        ("L1", ["AAA", "BB"]), ("L1", ["AAA", "X1"]), ("X1", ["L1", "BB"]),      # aaa L1? bb
        ("R1", ["TB", "AAA"]), ("R1", ["TB", "Y1"]), ("Y1", ["R1", "AAA"]),      # b R1? aaa
        ("S", ["L1", "R1"]),
        ("S", ["TA", "C1"]), ("C1", ["TB", "TA"]),                               # a b a
        ("S", ["TA", "C2"]), ("C2", ["L1", "C1"]),                               # a L1 b a
        ("S", ["TA", "C3"]), ("C3", ["TB", "C4"]), ("C4", ["R1", "TA"]),         # a b R1 a
        ("S", ["TA", "C5"]), ("C5", ["L1", "C3"]),                               # a L1 b R1 a
        ("S", ["AA", "D1"]), ("D1", ["BB", "AA"]),                               # aa bb aa
        ("S", ["AA", "D2"]), ("D2", ["L1", "D1"]),                               # aa L1 bb aa
        ("S", ["AA", "D3"]), ("D3", ["BB", "D4"]), ("D4", ["R1", "AA"]),         # aa bb R1 aa
        ("S", ["AA", "D5"]), ("D5", ["L1", "D3"]),                               # aa L1 bb R1 aa
    ]
    return Grammar(start="S", productions=[Production(lhs=l, rhs=r) for l, r in rules])


def t08_original_member(w: str) -> bool:
    """The ORIGINAL (rejected, pre-v1) Task 08 language: a^i b^j a^k with i + k = 2j and i > k >= 1."""
    i = len(w) - len(w.lstrip("a"))
    rest = w[i:]
    j = len(rest) - len(rest.lstrip("b"))
    k = len(rest) - j
    return rest[j:] == "a" * k and k >= 1 and i > k and i + k == 2 * j
