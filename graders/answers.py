"""Pydantic schemas for the final JSON answer of each task type (what the model must output).

Extra keys are ignored: only the fields below are graded."""
from __future__ import annotations

from pydantic import BaseModel, StrictStr

from automata.cfg import Grammar


class DFAAnswer(BaseModel):
    states: list[StrictStr]
    start: StrictStr
    accepting: list[StrictStr]
    transitions: dict[StrictStr, dict[StrictStr, StrictStr]]


class WitnessAnswer(BaseModel):
    witness: StrictStr


class GrammarAnswer(Grammar):
    pass


ANSWER_MODELS: dict[str, type[BaseModel]] = {
    "dfa": DFAAnswer,
    "witness": WitnessAnswer,
    "cnf_grammar": GrammarAnswer,
}
