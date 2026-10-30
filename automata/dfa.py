"""Deterministic finite automata: model, simulation, products, equivalence, minimization.

Conventions used throughout the project:
  * every alphabet symbol is a single character, so a word is a plain ``str``;
  * the empty word ε is ``""``;
  * "alphabet order" means the order of ``dfa.alphabet``; all searches expand symbols in
    that order so results (counterexamples, state names) are deterministic.

A DFA may be *partial* (missing transitions). When simulating, a missing transition sends
the run to an implicit dead state. The task prompts require complete DFAs, so the grader
reports missing transitions as ``INCOMPLETE_DFA`` before ever comparing languages.
"""
from __future__ import annotations

from collections import deque
from itertools import product as cartesian
from typing import Callable, Iterator, Optional

from pydantic import BaseModel, model_validator

State = str
Pair = tuple[Optional[State], Optional[State]]


class DFA(BaseModel):
    """A (possibly partial) DFA. Construction fails with ``ValueError`` if it references
    unknown states or symbols, so a ``DFA`` object is always structurally valid."""

    states: list[State]
    alphabet: list[str]
    start: State
    accepting: list[State]
    transitions: dict[State, dict[str, State]]

    @model_validator(mode="after")
    def _check_structure(self) -> "DFA":
        errors = []
        if not self.states:
            errors.append("states is empty")
        if len(set(self.states)) != len(self.states):
            errors.append("states contains duplicate names")
        if not self.alphabet or len(set(self.alphabet)) != len(self.alphabet):
            errors.append("alphabet must be non-empty and duplicate-free")
        if any(len(a) != 1 for a in self.alphabet):
            errors.append("every alphabet symbol must be a single character")
        known, symbols = set(self.states), set(self.alphabet)
        if self.start not in known:
            errors.append(f"start state {self.start!r} is not in states")
        for q in self.accepting:
            if q not in known:
                errors.append(f"accepting state {q!r} is not in states")
        for q, row in self.transitions.items():
            if q not in known:
                errors.append(f"transitions given for unknown state {q!r}")
            for a, r in row.items():
                if a not in symbols:
                    errors.append(f"transition {q!r} --{a!r}--> uses a symbol outside the alphabet")
                if r not in known:
                    errors.append(f"transition {q!r} --{a!r}--> goes to unknown state {r!r}")
        if errors:
            raise ValueError("; ".join(errors))
        return self


# --------------------------------------------------------------------------- basics


def step(dfa: DFA, state: Optional[State], symbol: str) -> Optional[State]:
    """One transition; ``None`` stands for the implicit dead state of a partial DFA."""
    if state is None:
        return None
    return dfa.transitions.get(state, {}).get(symbol)


def run(dfa: DFA, word: str) -> Optional[State]:
    """State reached after reading ``word`` from the start (``None`` = implicit dead)."""
    state: Optional[State] = dfa.start
    for symbol in word:
        state = step(dfa, state, symbol)
    return state


def accepts(dfa: DFA, word: str) -> bool:
    """Membership test, O(|word|)."""
    return run(dfa, word) in set(dfa.accepting)


def missing_transitions(dfa: DFA) -> list[tuple[State, str]]:
    """All (state, symbol) pairs without a transition, in state/alphabet order."""
    return [
        (q, a) for q in dfa.states for a in dfa.alphabet if a not in dfa.transitions.get(q, {})
    ]


def is_complete(dfa: DFA) -> bool:
    return not missing_transitions(dfa)


def all_words(alphabet: list[str], max_len: int) -> Iterator[str]:
    """Every word of length 0..max_len in shortlex order (used by brute-force checks)."""
    for n in range(max_len + 1):
        for letters in cartesian(alphabet, repeat=n):
            yield "".join(letters)


# --------------------------------------------------------------------------- structure


def reachable_states(dfa: DFA) -> list[State]:
    """States reachable from the start, in BFS order (alphabet order). O(|Q|·|Σ|)."""
    seen, order, queue = {dfa.start}, [dfa.start], deque([dfa.start])
    while queue:
        q = queue.popleft()
        for a in dfa.alphabet:
            r = step(dfa, q, a)
            if r is not None and r not in seen:
                seen.add(r)
                order.append(r)
                queue.append(r)
    return order


def remove_unreachable(dfa: DFA) -> DFA:
    keep = reachable_states(dfa)
    kept = set(keep)
    return DFA(
        states=keep,
        alphabet=list(dfa.alphabet),
        start=dfa.start,
        accepting=[q for q in dfa.accepting if q in kept],
        transitions={q: dict(dfa.transitions.get(q, {})) for q in keep},
    )


def complete(dfa: DFA, trap: str = "TRAP") -> DFA:
    """Return an equivalent complete DFA, adding a fresh trap state only if needed."""
    if is_complete(dfa):
        return dfa
    while trap in dfa.states:
        trap += "_"
    states = list(dfa.states) + [trap]
    transitions = {
        q: {a: dfa.transitions.get(q, {}).get(a, trap) for a in dfa.alphabet} for q in dfa.states
    }
    transitions[trap] = {a: trap for a in dfa.alphabet}
    return DFA(
        states=states,
        alphabet=list(dfa.alphabet),
        start=dfa.start,
        accepting=list(dfa.accepting),
        transitions=transitions,
    )


def complement(dfa: DFA) -> DFA:
    """Complement with respect to Σ* (completes the DFA first)."""
    d = complete(dfa)
    acc = set(d.accepting)
    return d.model_copy(update={"accepting": [q for q in d.states if q not in acc]})


# --------------------------------------------------------------------------- products


def _check_same_alphabet(d1: DFA, d2: DFA) -> None:
    if set(d1.alphabet) != set(d2.alphabet):
        raise ValueError(f"alphabets differ: {d1.alphabet} vs {d2.alphabet}")


def product(d1: DFA, d2: DFA, accept: Callable[[bool, bool], bool]) -> DFA:
    """Reachable part of the product automaton; a pair is accepting iff
    ``accept(pair[0] accepting in d1, pair[1] accepting in d2)``.

    Missing transitions are treated as the implicit dead state, so partial inputs work.
    States of the result are named p0, p1, ... in BFS order. O(|Q1|·|Q2|·|Σ|)."""
    _check_same_alphabet(d1, d2)
    acc1, acc2 = set(d1.accepting), set(d2.accepting)
    start: Pair = (d1.start, d2.start)
    names: dict[Pair, str] = {start: "p0"}
    queue: deque[Pair] = deque([start])
    transitions: dict[str, dict[str, str]] = {}
    accepting = []
    while queue:
        pair = queue.popleft()
        name = names[pair]
        if accept(pair[0] in acc1, pair[1] in acc2):
            accepting.append(name)
        transitions[name] = {}
        for a in d1.alphabet:
            nxt = (step(d1, pair[0], a), step(d2, pair[1], a))
            if nxt not in names:
                names[nxt] = f"p{len(names)}"
                queue.append(nxt)
            transitions[name][a] = names[nxt]
    return DFA(
        states=list(names.values()),
        alphabet=list(d1.alphabet),
        start="p0",
        accepting=accepting,
        transitions=transitions,
    )


def intersect(d1: DFA, d2: DFA) -> DFA:
    return product(d1, d2, lambda x, y: x and y)


def union(d1: DFA, d2: DFA) -> DFA:
    return product(d1, d2, lambda x, y: x or y)


def symmetric_difference(d1: DFA, d2: DFA) -> DFA:
    return product(d1, d2, lambda x, y: x != y)


# --------------------------------------------------------------------------- searches


def shortest_accepted(dfa: DFA) -> Optional[str]:
    """Shortlex-least accepted word, or ``None`` if the language is empty.

    BFS from the start expanding symbols in alphabet order visits every state first via
    its shortlex-least access word, so the first accepting state dequeued gives the
    shortlex-least accepted word. O(|Q|·|Σ|)."""
    acc = set(dfa.accepting)
    paths = {dfa.start: ""}
    queue = deque([dfa.start])
    while queue:
        q = queue.popleft()
        if q in acc:
            return paths[q]
        for a in dfa.alphabet:
            r = step(dfa, q, a)
            if r is not None and r not in paths:
                paths[r] = paths[q] + a
                queue.append(r)
    return None


def equivalent(d1: DFA, d2: DFA) -> tuple[bool, Optional[str]]:
    """Decide L(d1) = L(d2). Returns ``(True, None)`` or ``(False, w)`` where ``w`` is the
    shortlex-least word accepted by exactly one of them (a *shortest* counterexample).

    Algorithm: BFS over the reachable product of the two DFAs (missing transitions =
    implicit dead state). Every reachable pair is visited first via its shortest access
    word, so the first pair whose acceptance differs yields a shortest counterexample.
    Complete decision procedure; O(|Q1|·|Q2|·|Σ|)."""
    witness = shortest_accepted(symmetric_difference(d1, d2))
    return witness is None, witness


# --------------------------------------------------------------------------- minimization


def minimize(dfa: DFA) -> DFA:
    """The minimal complete DFA for L(dfa), with canonical state names q0, q1, ...

    Steps: complete the DFA, drop unreachable states, then Moore partition refinement:
    start from the partition {accepting, non-accepting} and repeatedly split blocks whose
    states disagree on which block each symbol leads to, until nothing changes. The final
    blocks are exactly the Myhill-Nerode classes, so the result is the unique minimal DFA
    (up to renaming). States are numbered in BFS order from the start, so two equivalent
    inputs always give identical output. O(|Q|²·|Σ|) worst case, plenty for our sizes."""
    d = remove_unreachable(complete(dfa))
    acc = set(d.accepting)
    block = {q: int(q in acc) for q in d.states}
    while True:
        ids: dict[tuple, int] = {}
        refined = {}
        for q in d.states:
            signature = (block[q], tuple(block[d.transitions[q][a]] for a in d.alphabet))
            refined[q] = ids.setdefault(signature, len(ids))
        if len(ids) == len(set(block.values())):
            break  # no block was split: the partition is stable
        block = refined

    # Build the quotient automaton and name its states in BFS order.
    rep = {}
    for q in d.states:
        rep.setdefault(block[q], q)
    names = {block[d.start]: "q0"}
    queue = deque([block[d.start]])
    transitions: dict[str, dict[str, str]] = {}
    while queue:
        b = queue.popleft()
        row = {}
        for a in d.alphabet:
            nb = block[d.transitions[rep[b]][a]]
            if nb not in names:
                names[nb] = f"q{len(names)}"
                queue.append(nb)
            row[a] = names[nb]
        transitions[names[b]] = row
    return DFA(
        states=list(names.values()),
        alphabet=list(d.alphabet),
        start="q0",
        accepting=[names[b] for b in names if rep[b] in acc],
        transitions=transitions,
    )


def minimal_size(dfa: DFA) -> int:
    """Number of states of the minimal *complete* DFA for L(dfa)."""
    return len(minimize(dfa).states)


# --------------------------------------------------------------------------- diagnostics


def agreement_upto(d1: DFA, d2: DFA, max_len: int) -> tuple[int, int]:
    """(number of words of length <= max_len classified identically, total words).

    Counts paths in the product automaton by dynamic programming instead of enumerating
    words, so it is cheap even for max_len = 12 over a 4-letter alphabet."""
    p = product(d1, d2, lambda x, y: x == y)
    agree_states = set(p.accepting)
    counts = {p.start: 1}
    agree = total = 0
    for _length in range(max_len + 1):
        agree += sum(c for q, c in counts.items() if q in agree_states)
        total += sum(counts.values())
        nxt: dict[str, int] = {}
        for q, c in counts.items():
            for a in p.alphabet:
                r = p.transitions[q][a]
                nxt[r] = nxt.get(r, 0) + c
        counts = nxt
    return agree, total
