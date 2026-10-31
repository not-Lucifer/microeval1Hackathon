"""ε-NFAs: ε-closure, subset construction, direct simulation, and the quotient constructions.

ε-moves are stored under the symbol ``""`` (the empty word), e.g.
``transitions["q0"][""] == ["q1"]`` means q0 --ε--> q1.
"""
from __future__ import annotations

from collections import deque
from typing import Iterable

from pydantic import BaseModel, model_validator

from automata.dfa import DFA, complete

EPS = ""


class ENFA(BaseModel):
    """Nondeterministic finite automaton with ε-moves and a single start state."""

    states: list[str]
    alphabet: list[str]
    start: str
    accepting: list[str]
    transitions: dict[str, dict[str, list[str]]]

    @model_validator(mode="after")
    def _check_structure(self) -> "ENFA":
        known, symbols = set(self.states), set(self.alphabet) | {EPS}
        errors = []
        if len(known) != len(self.states):
            errors.append("duplicate state names")
        if any(len(a) != 1 for a in self.alphabet):
            errors.append("alphabet symbols must be single characters")
        if self.start not in known:
            errors.append("start state unknown")
        errors += [f"accepting state {q!r} unknown" for q in self.accepting if q not in known]
        for q, row in self.transitions.items():
            if q not in known:
                errors.append(f"transitions for unknown state {q!r}")
            for a, targets in row.items():
                if a not in symbols:
                    errors.append(f"symbol {a!r} not in alphabet")
                errors += [f"target {r!r} unknown" for r in targets if r not in known]
        if errors:
            raise ValueError("; ".join(errors))
        return self

    def targets(self, state: str, symbol: str) -> list[str]:
        return self.transitions.get(state, {}).get(symbol, [])


def epsilon_closure(nfa: ENFA, states: Iterable[str]) -> frozenset[str]:
    """All states reachable from ``states`` using only ε-moves (DFS). O(|Q| + |δ|)."""
    closure = set(states)
    stack = list(closure)
    while stack:
        q = stack.pop()
        for r in nfa.targets(q, EPS):
            if r not in closure:
                closure.add(r)
                stack.append(r)
    return frozenset(closure)


def move_closed(nfa: ENFA, states: frozenset[str], symbol: str) -> frozenset[str]:
    """ε-closure of the set of states reachable from ``states`` by one ``symbol`` step."""
    return epsilon_closure(nfa, (r for q in states for r in nfa.targets(q, symbol)))


def accepts(nfa: ENFA, word: str) -> bool:
    """Direct simulation (set of current states). Independent of the subset construction,
    so tests use it as an oracle. O(|word|·|δ|)."""
    current = epsilon_closure(nfa, [nfa.start])
    for symbol in word:
        current = move_closed(nfa, current, symbol)
    return bool(current & set(nfa.accepting))


def subset_name(nfa: ENFA, subset: frozenset[str]) -> str:
    """Readable name like ``{q0,q2}`` (members in the NFA's state order; ``{}`` for ∅)."""
    return "{" + ",".join(q for q in nfa.states if q in subset) + "}"


def subset_construction(nfa: ENFA) -> tuple[DFA, int]:
    """Determinize with ε-closures; returns ``(complete DFA, number of reachable subsets)``.

    DFA start = ε-closure({start}); a subset is accepting iff it contains an accepting NFA
    state. The empty subset is included (as a trap) when it is reachable, and it is counted
    in the returned number. Exploration is BFS in alphabet order. O(2^|Q|·|Σ|·|δ|) worst."""
    start = epsilon_closure(nfa, [nfa.start])
    names = {start: subset_name(nfa, start)}
    queue = deque([start])
    transitions: dict[str, dict[str, str]] = {}
    accepting = []
    acc = set(nfa.accepting)
    while queue:
        subset = queue.popleft()
        if subset & acc:
            accepting.append(names[subset])
        row = {}
        for a in nfa.alphabet:
            nxt = move_closed(nfa, subset, a)
            if nxt not in names:
                names[nxt] = subset_name(nfa, nxt)
                queue.append(nxt)
            row[a] = names[nxt]
        transitions[names[subset]] = row
    dfa = DFA(
        states=list(names.values()),
        alphabet=list(nfa.alphabet),
        start=names[start],
        accepting=accepting,
        transitions=transitions,
    )
    return dfa, len(names)


def to_dfa(nfa: ENFA) -> DFA:
    return subset_construction(nfa)[0]


def right_quotient(m1: DFA, m2: DFA) -> DFA:
    """DFA for L(M1)/L(M2) = { x : there is y in L(M2) with xy in L(M1) }.

    Construction: keep M1's states and transitions; make q accepting iff some word y takes
    q into F1 *and* M2's start into F2. That holds iff the pair (q, start2) can reach a pair
    in F1 x F2 in the product graph, which we find by backward BFS from F1 x F2 over all
    |Q1|·|Q2| pairs. y = ε is included (pairs already in F1 x F2). O(|Q1|·|Q2|·|Σ|)."""
    a, b = complete(m1), complete(m2)
    if set(a.alphabet) != set(b.alphabet):
        raise ValueError("alphabets differ")
    predecessors: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for p in a.states:
        for r in b.states:
            for s in a.alphabet:
                target = (a.transitions[p][s], b.transitions[r][s])
                predecessors.setdefault(target, []).append((p, r))
    good = {(p, r) for p in a.accepting for r in b.accepting}
    queue = deque(good)
    while queue:
        pair = queue.popleft()
        for prev in predecessors.get(pair, []):
            if prev not in good:
                good.add(prev)
                queue.append(prev)
    return a.model_copy(update={"accepting": [q for q in a.states if (q, b.start) in good]})


def states_reached_by_language(m1: DFA, m2: DFA) -> frozenset[str]:
    """The M1 states q such that some word x of L(M2) (x = ε included) leads M1's start to q:
    the pairs (q, r) with r accepting in M2 that are reachable from (start1, start2) in the
    product graph, by forward BFS. O(|Q1|·|Q2|·|Σ|)."""
    a, b = complete(m1), complete(m2)
    if set(a.alphabet) != set(b.alphabet):
        raise ValueError("alphabets differ")
    seen = {(a.start, b.start)}
    queue = deque(seen)
    while queue:
        p, r = queue.popleft()
        for s in a.alphabet:
            pair = (a.transitions[p][s], b.transitions[r][s])
            if pair not in seen:
                seen.add(pair)
                queue.append(pair)
    return frozenset(p for p, r in seen if r in b.accepting)


def left_quotient(m1: DFA, m2: DFA) -> DFA:
    """DFA for the left quotient { y : there is x in L(M2) with xy in L(M1) }.

    Construction: S = states_reached_by_language(m1, m2). L is the language of M1 started
    in ANY state of S, so determinize by subsets of M1's states starting from S; a subset is
    accepting iff it contains an accepting state of M1. The empty subset (S empty, i.e.
    L(M2) is empty) is a trap. O(|Q1|·|Q2|·|Σ|) for S, then O(2^|Q1|·|Q1|·|Σ|) worst case."""
    a = complete(m1)
    start = states_reached_by_language(m1, m2)

    def name(subset: frozenset[str]) -> str:
        return "{" + ",".join(q for q in a.states if q in subset) + "}"

    names = {start: name(start)}
    queue_sets = deque([start])
    transitions: dict[str, dict[str, str]] = {}
    accepting = []
    while queue_sets:
        subset = queue_sets.popleft()
        if subset & set(a.accepting):
            accepting.append(names[subset])
        row = {}
        for s in a.alphabet:
            nxt = frozenset(a.transitions[q][s] for q in subset)
            if nxt not in names:
                names[nxt] = name(nxt)
                queue_sets.append(nxt)
            row[s] = names[nxt]
        transitions[names[subset]] = row
    return DFA(states=list(names.values()), alphabet=list(a.alphabet), start=names[start],
               accepting=accepting, transitions=transitions)
