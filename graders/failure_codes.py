"""Failure codes recorded with every graded trial, with one-line descriptions."""
from __future__ import annotations

from enum import Enum


class FailureCode(str, Enum):
    PARSE_ERROR = "PARSE_ERROR"
    INVALID_DFA = "INVALID_DFA"
    INCOMPLETE_DFA = "INCOMPLETE_DFA"
    NOT_EQUIVALENT = "NOT_EQUIVALENT"
    NON_MINIMAL_STATE_BLOAT = "NON_MINIMAL_STATE_BLOAT"
    INVALID_WITNESS = "INVALID_WITNESS"
    WITNESS_NOT_DISTINGUISHING = "WITNESS_NOT_DISTINGUISHING"
    WITNESS_NOT_SHORTEST = "WITNESS_NOT_SHORTEST"
    CNF_VIOLATION = "CNF_VIOLATION"
    OVERGENERATES = "OVERGENERATES"
    UNDERGENERATES = "UNDERGENERATES"
    TRUNCATED = "TRUNCATED"
    API_ERROR = "API_ERROR"


DESCRIPTIONS: dict[FailureCode, str] = {
    FailureCode.PARSE_ERROR: "No final ```json block, invalid JSON, or JSON not in the required schema.",
    FailureCode.INVALID_DFA: "DFA references unknown states/symbols, has duplicate states, or an unknown start state.",
    FailureCode.INCOMPLETE_DFA: "DFA is missing at least one transition (the prompt requires a complete DFA).",
    FailureCode.NOT_EQUIVALENT: "DFA accepts a different language; a shortest counterexample is recorded.",
    FailureCode.NON_MINIMAL_STATE_BLOAT: "DFA accepts the right language but has more states than the minimum (score 0.5).",
    FailureCode.INVALID_WITNESS: "Witness contains symbols outside the alphabet.",
    FailureCode.WITNESS_NOT_DISTINGUISHING: "Witness is accepted by both regexes or by neither.",
    FailureCode.WITNESS_NOT_SHORTEST: "Witness distinguishes the regexes but is longer than the minimum (score 0.5).",
    FailureCode.CNF_VIOLATION: "Grammar is not in Chomsky normal form.",
    FailureCode.OVERGENERATES: "Grammar derives a string outside the language (shortest such string recorded).",
    FailureCode.UNDERGENERATES: "Grammar misses a string of the language (shortest such string recorded).",
    FailureCode.TRUNCATED: "The model hit its output-token limit (finish_reason=length); counted as a failure.",
    FailureCode.API_ERROR: "The API call failed after retries; excluded from pass-rate denominators.",
}
