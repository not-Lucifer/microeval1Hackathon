"""Grader for Task 05: a shortest string in the symmetric difference of two regexes. Exact.

Both regexes are compiled to minimal DFAs; BFS over their product gives the true minimum
length m of a distinguishing string. Any distinguishing string of length m scores 1.0 (the
prompt says any shortest one is accepted); a longer distinguishing string scores 0.5.
For failures, ``counterexample`` holds one correct shortest witness for comparison.
"""
from __future__ import annotations

from automata.dfa import accepts, equivalent
from automata.regex import to_min_dfa
from graders.answers import WitnessAnswer
from graders.failure_codes import FailureCode
from graders.result import GradeResult


def grade_witness(answer: WitnessAnswer, r1: str, r2: str, alphabet: list[str]) -> GradeResult:
    d1, d2 = to_min_dfa(r1, alphabet), to_min_dfa(r2, alphabet)
    same, shortest = equivalent(d1, d2)
    if same or shortest is None:
        raise ValueError("task is broken: the two regexes are equivalent")
    w, m = answer.witness, len(shortest)

    bad = sorted({ch for ch in w if ch not in alphabet})
    if bad:
        return GradeResult.fail(
            FailureCode.INVALID_WITNESS, counterexample=shortest, witness=w, invalid_symbols=bad
        )
    in1, in2 = accepts(d1, w), accepts(d2, w)
    if in1 == in2:
        return GradeResult.fail(
            FailureCode.WITNESS_NOT_DISTINGUISHING,
            counterexample=shortest,
            witness=w,
            accepted_by_both=in1,
            shortest_length=m,
        )
    facts = {"witness": w, "witness_length": len(w), "shortest_length": m, "in_R1": in1, "in_R2": in2}
    if len(w) > m:
        return GradeResult.fail(
            FailureCode.WITNESS_NOT_SHORTEST, score=0.5, counterexample=shortest, **facts
        )
    return GradeResult.ok(**facts)
