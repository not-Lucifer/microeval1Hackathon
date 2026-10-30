"""OpenRouter client (OpenAI-compatible API via the ``openai`` SDK) with retries.

API failures are never model failures: after ``max_attempts`` the result carries
``error`` and the trial is recorded as API_ERROR (excluded from pass-rate denominators).
Client errors that retrying cannot fix (400/401/403/404, e.g. a wrong model id) fail fast.
"""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import openai

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_REASONING_CHARS = 20_000  # keep transcripts (and the submission zip) small


@dataclass
class ModelSpec:
    """One entry of models.yaml."""

    name: str
    openrouter_id: str
    temperature: Optional[float] = 0.0
    max_tokens: int = 32000
    reasoning: Optional[dict] = None  # OpenRouter "reasoning" object, e.g. {"effort": "high"}
    provider: Optional[dict] = None  # OpenRouter provider routing preferences
    seed: Optional[int] = None
    price_per_mtok: dict = field(default_factory=dict)  # {"input": $, "output": $}, for estimates

    def settings(self) -> dict:
        """Everything that affects the request; stored in every transcript."""
        return {
            "openrouter_id": self.openrouter_id,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "reasoning": self.reasoning,
            "provider": self.provider,
            "seed": self.seed,
        }


@dataclass
class CompletionResult:
    text: str = ""
    finish_reason: Optional[str] = None
    usage: dict = field(default_factory=dict)
    latency_s: float = 0.0
    reasoning: Optional[str] = None
    model_returned: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0


RETRYABLE = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.InternalServerError,
)


def _usage_dict(resp: Any) -> dict:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return {}
    details = getattr(usage, "completion_tokens_details", None)
    extra = getattr(usage, "model_extra", None) or {}
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "reasoning_tokens": getattr(details, "reasoning_tokens", None) if details else None,
        "cost_usd": extra.get("cost"),
    }


class OpenRouterClient:
    def __init__(self, api_key: str, max_attempts: int = 5, timeout_s: float = 900.0):
        self._client = openai.AsyncOpenAI(
            base_url=OPENROUTER_BASE_URL, api_key=api_key, max_retries=0, timeout=timeout_s
        )
        self.max_attempts = max_attempts

    async def complete(self, spec: ModelSpec, messages: list[dict]) -> CompletionResult:
        kwargs: dict[str, Any] = {"model": spec.openrouter_id, "messages": messages, "max_tokens": spec.max_tokens}
        if spec.temperature is not None:
            kwargs["temperature"] = spec.temperature
        if spec.seed is not None:
            kwargs["seed"] = spec.seed
        extra_body: dict[str, Any] = {"usage": {"include": True}}
        if spec.reasoning:
            extra_body["reasoning"] = spec.reasoning
        if spec.provider:
            extra_body["provider"] = spec.provider

        last_error = "unknown error"
        for attempt in range(1, self.max_attempts + 1):
            started = time.monotonic()
            try:
                resp = await self._client.chat.completions.create(**kwargs, extra_body=extra_body)
                if not resp.choices:
                    raise RuntimeError(f"response has no choices: {getattr(resp, 'model_extra', None)}")
                choice = resp.choices[0]
                reasoning = (getattr(choice.message, "model_extra", None) or {}).get("reasoning")
                return CompletionResult(
                    text=choice.message.content or "",
                    finish_reason=choice.finish_reason,
                    usage=_usage_dict(resp),
                    latency_s=round(time.monotonic() - started, 2),
                    reasoning=reasoning[:MAX_REASONING_CHARS] if isinstance(reasoning, str) else None,
                    model_returned=resp.model,
                    attempts=attempt,
                )
            except (openai.BadRequestError, openai.AuthenticationError, openai.PermissionDeniedError,
                    openai.NotFoundError) as exc:
                return CompletionResult(error=f"{type(exc).__name__}: {exc}", attempts=attempt)
            except (*RETRYABLE, openai.APIError, RuntimeError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            if attempt < self.max_attempts:
                await asyncio.sleep(min(60.0, 2.0**attempt) + random.uniform(0, 1))
        return CompletionResult(error=last_error, attempts=self.max_attempts)
