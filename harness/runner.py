"""Run trials (async, bounded concurrency), grade them, write transcripts.

Each trial is a fresh two-message conversation (system + task prompt). Order of grading:
API error -> API_ERROR (excluded from denominators); finish_reason == "length" -> TRUNCATED
(a failure); otherwise extract the final JSON and hand it to the grader.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

from graders.failure_codes import FailureCode
from graders.grader import grade_answer
from graders.result import GradeResult
from harness.cache import ResponseCache
from harness.client import CompletionResult, ModelSpec
from harness.cost import CostTracker, call_cost
from harness.parsing import extract_final_json
from harness.prompts import SYSTEM_PROMPT, build_messages


class ChatClient(Protocol):
    async def complete(self, spec: ModelSpec, messages: list[dict]) -> CompletionResult: ...


def evaluate_output(task: dict, raw_output: str, finish_reason: Optional[str]) -> tuple[Any, GradeResult]:
    """(parsed answer or None, grade) for one model reply. Used live and by --regrade."""
    if finish_reason == "length":
        return None, GradeResult.fail(FailureCode.TRUNCATED, finish_reason=finish_reason)
    parsed, error = extract_final_json(raw_output)
    if error is not None:
        return None, GradeResult.fail(FailureCode.PARSE_ERROR, error=error)
    return parsed, grade_answer(task, parsed)


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def transcript_path(root: Path, model_name: str, task_id: str, trial: int) -> Path:
    return root / safe_name(model_name) / task_id / f"trial_{trial}.json"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


def build_transcript(task: dict, spec: ModelSpec, trial: int, result: CompletionResult, cost: Optional[float]) -> dict:
    if result.error is not None:
        parsed, grade = None, GradeResult.fail(FailureCode.API_ERROR, error=result.error)
    else:
        parsed, grade = evaluate_output(task, result.text, result.finish_reason)
    return {
        "task_id": task["id"],
        "model": spec.name,
        "settings": spec.settings(),
        "trial": trial,
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "system_prompt": SYSTEM_PROMPT,
        "prompt": task["prompt"],
        "raw_output": result.text,
        "reasoning_excerpt": result.reasoning,
        "parsed_answer": parsed,
        "grade": grade.model_dump(mode="json"),
        "usage": {**result.usage, "cost_usd": cost},
        "latency_s": result.latency_s,
        "finish_reason": result.finish_reason,
        "model_returned": result.model_returned,
        "api_attempts": result.attempts,
    }


async def run_trials(
    tasks: list[dict],
    specs: list[ModelSpec],
    trials: int,
    client: ChatClient,
    transcripts_dir: Path,
    cache: ResponseCache,
    cost: CostTracker,
    concurrency: int = 4,
    log=print,
) -> list[dict]:
    """Run every (model, task, trial); returns the transcripts that were produced.
    New (uncached) calls stop being made once --max-cost or --max-requests is reached, or
    OpenRouter reports that no further call can succeed (no credits, free daily quota used
    up); skipped trials leave no transcript and run next time."""
    semaphore = asyncio.Semaphore(concurrency)
    produced: list[dict] = []
    halted: list[str] = []  # reason the run stopped making paid calls, if any

    async def one(spec: ModelSpec, task: dict, trial: int) -> None:
        async with semaphore:
            messages = build_messages(task)
            key = ResponseCache.key(spec.settings(), messages, trial)
            cached = cache.get(key)
            if cached is not None:
                known = CompletionResult.__dataclass_fields__  # tolerate entries from older versions
                result = CompletionResult(**{k: v for k, v in cached.items() if k in known})
            else:
                if not halted and cost.exhausted():
                    halted.append("--max-cost reached")
                if not halted and cost.requests_exhausted():
                    halted.append("--max-requests reached")
                if halted:
                    log(f"skip {spec.name}/{task['id']}/trial {trial}: {halted[0]}")
                    return
                result = await client.complete(spec, messages)
                cost.add_requests(max(result.attempts, 1))  # a call that was sent is at least one request
                if result.stop_run and not halted:
                    halted.append(result.stop_run)
                    log(f"STOPPING: {halted[0]}")
                if result.error is None:
                    cache.put(key, result.__dict__)
            price = call_cost(result.usage, spec) if result.error is None else None
            if cached is None:
                cost.add(price)
            transcript = build_transcript(task, spec, trial, result, price)
            write_json(transcript_path(transcripts_dir, spec.name, task["id"], trial), transcript)
            produced.append(transcript)
            g = transcript["grade"]
            log(f"{spec.name:28} {task['id']} trial {trial}: score {g['score']} {g['failure_code'] or ''}")

    await asyncio.gather(*(one(s, t, k) for s in specs for t in tasks for k in range(1, trials + 1)))
    return produced
