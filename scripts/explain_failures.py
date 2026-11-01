"""Where exactly is a wrong DFA answer wrong? For every NOT_EQUIVALENT transcript, report the
first faulty entry of the model's table on the stored shortest counterexample, and how many
entries of the whole table are faulty.

    python scripts/explain_failures.py [--transcripts transcripts/]

Method. Read every reachable model state q as meaning what its shortest access word a(q)
means: the reference state ref(a(q)) (the reference is the minimal DFA, so equal reference
states = equivalent words). Then
  * a transition q --x--> q' is faulty if ref(a(q)·x) != ref(a(q'));
  * an accepting flag is faulty if q is accepting but ref(a(q)) is not, or vice versa.
Walking the counterexample w from the start (a(start) = ε): if no transition on the path is
faulty, then by induction ref(a(q_i)) = ref(w[:i]) for every i, so the final state's flag must
be faulty (the model and the reference disagree on w). So the walk always ends at a faulty
entry, and it is the first one the counterexample uses. Every reported entry is a genuine
inconsistency, but the blame depends on this reading of the states: a model that meant a
state differently may have its bug one transition earlier (e.g. a wrong arrow into a state
whose flag is then reported).

This is a diagnostic for reading failures, not part of any grade. It reads reference/, so it
lives in scripts/ (the harness never reads reference/). Cost: one BFS over the model DFA plus
one reference run per transition, O(|Q| · |Σ| · |Q|) for the access words.
"""
from __future__ import annotations

import argparse
import io
import sys
from collections import deque
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from automata.dfa import DFA, accepts, run  # noqa: E402
from graders.grader import reference_dfa  # noqa: E402
from harness.metrics import load_transcripts, split_stale  # noqa: E402
from harness.prompts import tasks_by_id  # noqa: E402


def access_words(dfa: DFA) -> dict[str, str]:
    """Shortlex-least word reaching each reachable state (BFS, symbols in alphabet order)."""
    words, queue = {dfa.start: ""}, deque([dfa.start])
    while queue:
        q = queue.popleft()
        for symbol in dfa.alphabet:
            nxt = dfa.transitions.get(q, {}).get(symbol)
            if nxt is not None and nxt not in words:
                words[nxt] = words[q] + symbol
                queue.append(nxt)
    return words


def faults(model: DFA, reference: DFA) -> tuple[set[tuple[str, str]], set[str]]:
    """(faulty transitions as (state, symbol), states with a faulty accepting flag)."""
    a = access_words(model)
    bad_moves = set()
    for q, w in a.items():
        for symbol in model.alphabet:
            nxt = model.transitions.get(q, {}).get(symbol)
            if nxt is None or run(reference, w + symbol) != run(reference, a[nxt]):
                bad_moves.add((q, symbol))
    bad_flags = {q for q, w in a.items() if (q in model.accepting) != accepts(reference, w)}
    return bad_moves, bad_flags


def first_fault_on(model: DFA, word: str, bad_moves: set, bad_flags: set) -> tuple[str, Optional[str], str]:
    """(prefix read before the fault, faulty symbol or None for the final flag, model state)."""
    q = model.start
    for i, symbol in enumerate(word):
        if (q, symbol) in bad_moves:
            return word[:i], symbol, q
        q = model.transitions[q][symbol]
    assert q in bad_flags, "a counterexample always reaches a faulty entry (see module docstring)"
    return word, None, q


def explain(transcript: dict, task: dict) -> str:
    answer = transcript["parsed_answer"]
    model = DFA(alphabet=task["grader"]["params"]["alphabet"], states=answer["states"], start=answer["start"],
                accepting=answer["accepting"], transitions=answer["transitions"])
    reference = reference_dfa(task)
    word = transcript["grade"]["counterexample"]
    bad_moves, bad_flags = faults(model, reference)
    prefix, symbol, q = first_fault_on(model, word, bad_moves, bad_flags)
    shown = lambda w: f"'{w}'" if w else "ε"  # noqa: E731
    access = access_words(model)[q]
    if symbol is None:
        fault = f"state {q!r} (first reached by {shown(access)}) should be {'non-' if q in model.accepting else ''}accepting"
    else:
        target = model.transitions[q][symbol]
        fault = (f"after {shown(prefix)}, {q!r} --{symbol}--> {target!r} treats {shown(access + symbol)} like "
                 f"{shown(access_words(model)[target])}, which is not equivalent")
    n_moves = len(access_words(model)) * len(model.alphabet)
    return (f"{'accepts' if accepts(model, word) else 'rejects'} {shown(word)}; first fault: {fault}; "
            f"{len(bad_moves)} of {n_moves} transitions and {len(bad_flags)} accepting flags are faulty")


def main() -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcripts", default=str(ROOT / "transcripts"))
    args = ap.parse_args()
    tasks = tasks_by_id()
    current, _ = split_stale(load_transcripts(Path(args.transcripts)), tasks)
    for t in sorted(current, key=lambda t: (t["task_id"], t["model"], t["trial"])):
        if t["grade"]["failure_code"] == "NOT_EQUIVALENT":
            print(f"{t['task_id']} {t['model']} trial {t['trial']}: {explain(t, tasks[t['task_id']])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
