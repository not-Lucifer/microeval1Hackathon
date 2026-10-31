"""Cost accounting, the --max-cost guard and --dry-run estimates."""
from __future__ import annotations

import json
from typing import Optional

from harness.client import ModelSpec

CHARS_PER_TOKEN = 4  # rough estimate for prompt sizes


def call_cost(usage: dict, spec: ModelSpec) -> Optional[float]:
    """Cost of one call: OpenRouter's reported cost if present, else computed from the
    optional prices in models.yaml, else None (unknown)."""
    if usage.get("cost_usd") is not None:
        return float(usage["cost_usd"])
    price_in, price_out = spec.price_per_mtok.get("input"), spec.price_per_mtok.get("output")
    if price_in is None or price_out is None or not usage:
        return None
    return (usage.get("prompt_tokens", 0) * price_in + usage.get("completion_tokens", 0) * price_out) / 1e6


class CostTracker:
    """Spend and request accounting behind --max-cost and --max-requests."""

    def __init__(self, max_usd: Optional[float] = None, max_requests: Optional[int] = None):
        self.max_usd, self.max_requests = max_usd, max_requests
        self.total_usd, self.unknown_calls, self.requests = 0.0, 0, 0

    def add(self, cost: Optional[float]) -> None:
        if cost is None:
            self.unknown_calls += 1
        else:
            self.total_usd += cost

    def add_requests(self, n: int) -> None:
        """Every attempt is a request (and counts toward OpenRouter's free daily quota)."""
        self.requests += n

    def exhausted(self) -> bool:
        """True once spending reached --max-cost. Free calls cost $0, so with --max-cost 0
        this only becomes True if something was actually charged."""
        return self.max_usd is not None and self.total_usd > 0 and self.total_usd >= self.max_usd

    def requests_exhausted(self) -> bool:
        return self.max_requests is not None and self.requests >= self.max_requests


def settings_key(settings: dict) -> str:
    """Model id + reasoning setting: what mostly determines the cost of a call."""
    return json.dumps({"id": settings.get("openrouter_id"), "reasoning": settings.get("reasoning")}, sort_keys=True)


def observed_cost_per_call(transcripts: list[dict]) -> dict[str, tuple[float, int]]:
    """settings_key -> (average recorded cost of an answered call, number of calls).
    API errors are skipped: rejected requests are not charged."""
    sums: dict[str, tuple[float, int]] = {}
    for t in transcripts:
        cost = t["usage"].get("cost_usd")
        if t["grade"]["failure_code"] == "API_ERROR" or cost is None:
            continue
        total, n = sums.get(settings_key(t["settings"]), (0.0, 0))
        sums[settings_key(t["settings"])] = (total + cost, n + 1)
    return {k: (total / n, n) for k, (total, n) in sums.items()}


def estimate(
    specs: list[ModelSpec],
    tasks: list[dict],
    trials: int,
    completion_tokens: int,
    observed: Optional[dict[str, tuple[float, int]]] = None,
) -> list[dict]:
    """Per-model cost estimate for --dry-run. Prefers the average cost actually recorded for
    the same model and reasoning setting in earlier transcripts; otherwise uses the optional
    prices in models.yaml with an assumed completion length; otherwise 'unknown'."""
    rows = []
    for spec in specs:
        calls = len(tasks) * trials
        seen = (observed or {}).get(settings_key(spec.settings()))
        if spec.openrouter_id.endswith(":free"):
            cost, basis = 0.0, f"free model: uses {calls} of your daily free requests"
        elif seen:
            cost, basis = seen[0] * calls, f"avg ${seen[0]:.4f}/call over {seen[1]} earlier answered calls"
        else:
            prompt_tokens = sum(len(t["prompt"]) // CHARS_PER_TOKEN + 300 for t in tasks) * trials
            usage = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens * calls}
            cost = call_cost(usage, spec)
            basis = "models.yaml prices" if cost is not None else "no earlier calls and no price_per_mtok"
        rows.append({"model": spec.name, "calls": calls, "estimated_usd": cost, "basis": basis})
    return rows
