"""Grade one parsed answer for one task: schema validation, then dispatch by grader type.

This is the only module that reads ``reference/`` (the harness never does).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from automata.dfa import DFA
from graders.answers import ANSWER_MODELS
from graders.cfg_grader import grade_cfg
from graders.dfa_grader import grade_dfa
from graders.failure_codes import FailureCode
from graders.result import GradeResult
from graders.witness_grader import grade_witness

REFERENCE_DIR = Path(__file__).resolve().parents[1] / "reference"


@lru_cache(maxsize=None)
def load_reference(task_id: str) -> dict:
    return json.loads((REFERENCE_DIR / f"{task_id}.ref.json").read_text(encoding="utf-8"))


def reference_dfa(task: dict) -> DFA:
    ref = load_reference(task["id"])["answer"]
    return DFA(alphabet=task["grader"]["params"]["alphabet"], **ref)


def grade_answer(task: dict, answer_obj: Any) -> GradeResult:
    """``answer_obj`` is the decoded final JSON value from the model's reply."""
    schema = ANSWER_MODELS[task["answer_schema"]]
    try:
        answer = schema.model_validate(answer_obj)
    except ValidationError as exc:
        return GradeResult.fail(FailureCode.PARSE_ERROR, error=f"schema: {exc.errors()[:5]}")

    kind, params = task["grader"]["type"], task["grader"]["params"]
    if kind == "dfa_exact":
        return grade_dfa(answer, reference_dfa(task))
    if kind == "witness_exact":
        return grade_witness(answer, params["r1"], params["r2"], params["alphabet"])
    if kind == "cfg_bounded":
        return grade_cfg(answer, params["alphabet"], params["max_len"], params["language"])
    raise ValueError(f"unknown grader type {kind!r}")
