"""Shared helpers for tests: random automata/grammars and brute-force oracles."""
from __future__ import annotations

import json
import random
from pathlib import Path

from automata.cfg import Grammar, Production
from automata.dfa import DFA, accepts, all_words, reachable_states

AB = ["a", "b"]
TASKS_DIR = Path(__file__).resolve().parents[1] / "tasks"


def load_task_files() -> list[dict]:
    """Task JSON files in id order (read directly, without the harness)."""
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(TASKS_DIR.glob("task_*.json"))]


def random_dfa(rng: random.Random, n: int, alphabet=AB, prefix: str = "s", p_missing: float = 0.0) -> DFA:
    states = [f"{prefix}{i}" for i in range(n)]
    transitions = {
        q: {a: rng.choice(states) for a in alphabet if rng.random() >= p_missing} for q in states
    }
    return DFA(
        states=states,
        alphabet=list(alphabet),
        start=states[0],
        accepting=[q for q in states if rng.random() < 0.5],
        transitions=transitions,
    )


def brute_first_difference(d1: DFA, d2: DFA, max_len: int):
    """Shortlex-least word on which d1 and d2 disagree, searching words up to max_len."""
    for w in all_words(d1.alphabet, max_len):
        if accepts(d1, w) != accepts(d2, w):
            return w
    return None


def brute_nerode_count(dfa: DFA) -> int:
    """Number of Myhill-Nerode classes of a complete DFA, by brute force: two reachable
    states are equivalent iff they agree on all suffixes of length <= n - 1 (n = #states),
    which is enough for an n-state DFA."""
    n = len(dfa.states)
    suffixes = list(all_words(dfa.alphabet, max(n - 1, 0)))
    signatures = set()
    for q in reachable_states(dfa):
        sub = dfa.model_copy(update={"start": q})
        signatures.add(tuple(accepts(sub, z) for z in suffixes))
    return len(signatures)


def rename_states(dfa: DFA, prefix: str = "renamed_") -> DFA:
    m = {q: f"{prefix}{i}" for i, q in enumerate(reversed(dfa.states))}
    return DFA(
        states=[m[q] for q in reversed(dfa.states)],
        alphabet=dfa.alphabet,
        start=m[dfa.start],
        accepting=[m[q] for q in dfa.accepting],
        transitions={m[q]: {a: m[r] for a, r in row.items()} for q, row in dfa.transitions.items()},
    )


def random_cnf(rng: random.Random, n_nt: int, alphabet=AB, n_bin: int = 6) -> Grammar:
    nts = [f"N{i}" for i in range(n_nt)]
    prods = [Production(lhs=rng.choice(nts), rhs=[a]) for a in alphabet if rng.random() < 0.8]
    prods += [Production(lhs=rng.choice(nts), rhs=[rng.choice(nts), rng.choice(nts)]) for _ in range(n_bin)]
    return Grammar(start="N0", productions=prods)
