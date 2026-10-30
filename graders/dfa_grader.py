"""Grader for minimal-complete-DFA answers (Tasks 01-04, 06). Exact: equivalence and
minimality are decided, not sampled.

Order of checks (first failure wins):
  1. structure  -> INVALID_DFA     (unknown states/symbols, duplicate states, bad start)
  2. complete   -> INCOMPLETE_DFA  (some state lacks a transition on some symbol)
  3. language   -> NOT_EQUIVALENT  (+ shortest counterexample from product BFS)
  4. size       -> NON_MINIMAL_STATE_BLOAT, score 0.5 (every listed state counts,
                   including unreachable ones, as the prompt states)
  5. otherwise score 1.0
"""
from __future__ import annotations

from automata.dfa import (
    DFA,
    accepts,
    agreement_upto,
    equivalent,
    minimal_size,
    missing_transitions,
    reachable_states,
)
from graders.answers import DFAAnswer
from graders.failure_codes import FailureCode
from graders.result import GradeResult

DIAGNOSTIC_MAX_LEN = 10  # "how far off" metric: agreement on all words up to this length


def grade_dfa(answer: DFAAnswer, reference: DFA) -> GradeResult:
    try:
        dfa = DFA(
            states=answer.states,
            alphabet=list(reference.alphabet),
            start=answer.start,
            accepting=answer.accepting,
            transitions=answer.transitions,
        )
    except ValueError as exc:
        return GradeResult.fail(FailureCode.INVALID_DFA, error=str(exc)[:2000])

    same, cex = equivalent(dfa, reference)  # missing transitions behave as a dead state here
    agree, total = agreement_upto(dfa, reference, DIAGNOSTIC_MAX_LEN)
    diagnostics = {
        "diagnostic_agreement_upto_len": DIAGNOSTIC_MAX_LEN,
        "diagnostic_agreement_fraction": round(agree / total, 6),
    }

    missing = missing_transitions(dfa)
    if missing:
        return GradeResult.fail(
            FailureCode.INCOMPLETE_DFA,
            counterexample=cex,
            n_missing_transitions=len(missing),
            missing_transitions=[f"{q} --{a}-->" for q, a in missing[:20]],
            language_correct_if_missing_go_to_trap=same,
            **diagnostics,
        )
    if not same:
        return GradeResult.fail(
            FailureCode.NOT_EQUIVALENT,
            counterexample=cex,
            model_accepts=accepts(dfa, cex),
            reference_accepts=accepts(reference, cex),
            **diagnostics,
        )

    n_given, n_min = len(dfa.states), minimal_size(reference)
    if n_given > n_min:
        return GradeResult.fail(
            FailureCode.NON_MINIMAL_STATE_BLOAT,
            score=0.5,
            states_given=n_given,
            states_minimal=n_min,
            unreachable_states=n_given - len(reachable_states(dfa)),
        )
    return GradeResult.ok(states_given=n_given, states_minimal=n_min)
