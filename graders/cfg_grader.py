"""Grader for CNF-grammar answers (Tasks 07, 08).

Guarantee: BOUNDED, not exact. A pass means the grammar is in CNF, generates exactly the
target language on every string of length <= N, and generates an infinite language (as
the target does). CFG equivalence is undecidable in general, so nothing is claimed beyond
length N. Over- and under-generation witnesses are shortest ones (see automata.cfg.check_upto).
"""
from __future__ import annotations

from automata.cfg import check_upto, cnf_violations
from graders.answers import GrammarAnswer
from graders.failure_codes import FailureCode
from graders.oracles import ORACLES
from graders.result import GradeResult


def grade_cfg(answer: GrammarAnswer, alphabet: list[str], max_len: int, language: str) -> GradeResult:
    violations = cnf_violations(answer, alphabet)
    if violations:
        return GradeResult.fail(
            FailureCode.CNF_VIOLATION, n_violations=len(violations), violations=violations[:20]
        )

    member, enumerate_language, shortest_longer_than = ORACLES[language]
    truth = enumerate_language(max_len)
    res = check_upto(answer, alphabet, max_len, member, truth, shortest_longer_than)

    upto = res.checked_upto
    truth_count = sum(len(truth[n]) for n in range(1, upto + 1))
    found = sum(res.generated_by_length.get(n, 0) for n in range(1, upto + 1))
    details = {
        "bound_N": max_len,
        "guarantee": "exact for strings of length <= N only (CFG equivalence is undecidable)",
        "fully_compared_upto_len": upto,
        "diagnostic_recall_upto_len": round(found / truth_count, 6) if truth_count else None,
        "finite_language": res.finite_language,
        "notes": res.notes,
    }
    if res.kind == "over":
        return GradeResult.fail(FailureCode.OVERGENERATES, counterexample=res.counterexample, **details)
    if res.kind == "under":
        return GradeResult.fail(FailureCode.UNDERGENERATES, counterexample=res.counterexample, **details)
    return GradeResult.ok(**details)
