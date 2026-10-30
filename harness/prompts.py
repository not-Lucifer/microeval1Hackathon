"""System prompt (identical for every model and task) and task loading.

Prompts are built ONLY from tasks/*.json. This module never touches reference/.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "tasks"

SYSTEM_PROMPT = """\
You are a careful formal-methods engineer answering one exam-style question about finite automata, regular expressions or context-free grammars.
- No tools are available. You cannot run code, and no code will be run for you. Work everything out yourself.
- You may reason step by step, at any length, before giving your answer.
- End your reply with exactly one fenced code block that starts with ```json and contains only the final answer: a single JSON object in the schema given in the question. If your reply contains several ```json blocks, only the last one is graded.
- Do not put comments or trailing commas inside the JSON."""


def load_tasks(only: list[str] | None = None) -> list[dict]:
    """All task files in id order; ``only`` filters by task id (e.g. ["task_01"])."""
    tasks = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(TASKS_DIR.glob("task_*.json"))]
    if only:
        tasks = [t for t in tasks if t["id"] in only]
    return tasks


def tasks_by_id() -> dict[str, dict]:
    return {t["id"]: t for t in load_tasks()}


def build_messages(task: dict) -> list[dict[str, str]]:
    """Fresh conversation for one trial: system prompt + the task prompt. No history."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task["prompt"]},
    ]
