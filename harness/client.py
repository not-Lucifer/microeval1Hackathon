"""OpenRouter client (OpenAI-compatible API via the ``openai`` SDK) with retries.

API failures are never model failures: after ``max_attempts`` the result carries
``error`` and the trial is recorded as API_ERROR (excluded from pass-rate denominators).
Client errors that retrying cannot fix (400/401/403/404, e.g. a wrong model id) fail fast,
and 402 (not enough OpenRouter credits) also tells the runner to stop the whole run.
OpenRouter reserves credit for the full max_tokens of a request before it starts, so a low
balance makes every request fail with 402 even if the answer would have been short.
A reply with finish_reason "error" (OpenRouter: the provider failed mid-generation) is an
API error too, not a model answer.
Free (":free") models: 429 "free-models-per-day" stops the run (the daily quota is gone);
other 429s wait out the per-minute window. Failed attempts count toward the daily quota,
so free runs should use few attempts (--max-attempts).
"""
from __future__ import annotations

import asyncio
import random
import re
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
    stop_run: Optional[str] = None  # set when every further call would fail too (no credits, daily quota)


STOP_NO_CREDITS = "OpenRouter account is out of credits (HTTP 402); top up and rerun"
STOP_FREE_DAILY = (
    "OpenRouter free-model daily limit reached (HTTP 429); rerun tomorrow - finished answers are cached"
)
FREE_DAILY_LIMIT = re.compile(r"per[-_ ]?day", re.IGNORECASE)  # "free-models-per-day"; per-minute is retryable
RATE_LIMIT_WAIT_S = 30.0  # the free per-minute window; every failed attempt also counts toward the daily cap


def describe_error(exc: Exception) -> str:
    """Error text for transcripts, with account identifiers redacted. OpenRouter's 402 message
    links to the key's dashboard page (keys/<id>); key-like strings are masked as well."""
    text = f"{type(exc).__name__}: {exc}"
    text = re.sub(r"(keys/)[A-Za-z0-9_\-]+", r"\1<redacted>", text)
    return re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-<redacted>", text)


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
    def __init__(self, api_key: str, max_attempts: int = 5, timeout_s: float = 1800.0):
        self._client = openai.AsyncOpenAI(
            base_url=OPENROUTER_BASE_URL, api_key=api_key, max_retries=0, timeout=timeout_s
        )
        self.max_attempts = max_attempts

    async def aclose(self) -> None:
        await self._client.close()

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
            rate_limited = False
            try:
                resp = await self._client.chat.completions.create(**kwargs, extra_body=extra_body)
                if not resp.choices:
                    raise RuntimeError(f"response has no choices: {getattr(resp, 'model_extra', None)}")
                choice = resp.choices[0]
                if choice.finish_reason == "error":  # OpenRouter: provider failed mid-generation
                    raise RuntimeError(f"provider error mid-generation: {getattr(choice, 'model_extra', None)}")
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
                return CompletionResult(error=describe_error(exc), attempts=attempt)
            except openai.APIStatusError as exc:
                if exc.status_code == 402:  # not enough credits: retrying cannot help
                    return CompletionResult(error=describe_error(exc), attempts=attempt, stop_run=STOP_NO_CREDITS)
                if exc.status_code == 429 and FREE_DAILY_LIMIT.search(str(exc)):
                    return CompletionResult(error=describe_error(exc), attempts=attempt, stop_run=STOP_FREE_DAILY)
                last_error, rate_limited = describe_error(exc), exc.status_code == 429
            except Exception as exc:  # 5xx, timeouts, network, odd responses: retry
                last_error = describe_error(exc)
            if attempt < self.max_attempts:
                backoff = RATE_LIMIT_WAIT_S if rate_limited else min(60.0, 2.0**attempt)
                await asyncio.sleep(backoff + random.uniform(0, 1))
        return CompletionResult(error=last_error, attempts=self.max_attempts)
