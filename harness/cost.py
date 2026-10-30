"""Cost accounting, the --max-cost guard and --dry-run estimates."""
from __future__ import annotations

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
    def __init__(self, max_usd: Optional[float] = None):
        self.max_usd, self.total_usd, self.unknown_calls = max_usd, 0.0, 0

    def add(self, cost: Optional[float]) -> None:
        if cost is None:
            self.unknown_calls += 1
        else:
            self.total_usd += cost

    def exhausted(self) -> bool:
        return self.max_usd is not None and self.total_usd >= self.max_usd


def estimate(specs: list[ModelSpec], tasks: list[dict], trials: int, completion_tokens: int) -> list[dict]:
    """Rough per-model cost estimate for --dry-run (prompt size from characters;
    completion size is an assumption the user passes in, ideally from a pilot run)."""
    rows = []
    for spec in specs:
        prompt_tokens = sum(len(t["prompt"]) // CHARS_PER_TOKEN + 300 for t in tasks) * trials
        out_tokens = completion_tokens * len(tasks) * trials
        cost = call_cost({"prompt_tokens": prompt_tokens, "completion_tokens": out_tokens}, spec)
        rows.append({"model": spec.name, "calls": len(tasks) * trials, "prompt_tokens": prompt_tokens,
                     "completion_tokens": out_tokens, "estimated_usd": cost})
    return rows
