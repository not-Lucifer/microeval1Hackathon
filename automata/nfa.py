"""ε-NFAs: ε-closure, subset construction, direct simulation, and the right-quotient helper.

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
