"""The grade attached to every trial."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from graders.failure_codes import FailureCode


class GradeResult(BaseModel):
    score: float  # 1.0, 0.5 or 0.0 (see CLAUDE.md "Scoring convention")
    passed: bool  # score == 1.0; used for pass@k and pass^k
    failure_code: Optional[FailureCode] = None
    counterexample: Optional[str] = None  # shortest string exposing the error, when one exists
    details: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def ok(cls, **details: Any) -> "GradeResult":
        return cls(score=1.0, passed=True, details=details)

    @classmethod
    def fail(
        cls,
        code: FailureCode,
        score: float = 0.0,
        counterexample: Optional[str] = None,
        **details: Any,
    ) -> "GradeResult":
        return cls(
            score=score, passed=False, failure_code=code, counterexample=counterexample, details=details
        )
