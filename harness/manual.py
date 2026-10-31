"""Manual runs through free chat apps (ChatGPT, Claude.ai, Gemini, ...).

The author pastes each prompt into a fresh chat, pastes the reply into a text file, and the
import turns every reply into a normal transcript graded by exactly the same code as API
answers. Layout (created by ``new_manual_model``):

    manual/prompts/task_01.txt ...              text to paste (system prompt + task prompt)
    manual/<model-name>/info.yaml               which app/model/settings were used (required)
    manual/<model-name>/task_01/trial_1.txt     the model's full reply, pasted as-is

Empty reply files are skipped (not done yet), so a model can be imported in several sittings.
Differences from API runs are recorded in every transcript: the system prompt is delivered
inside the single pasted message, and sampling/reasoning settings are whatever the app uses.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from harness.prompts import SYSTEM_PROMPT
from harness.runner import evaluate_output, transcript_path, write_json

SOURCE = "manual chat app"
TEXT_FIELDS = ("app", "model_shown", "date", "reasoning_mode")
CONFIRMATIONS = ("no_tools_confirmed", "new_chat_per_trial")
INFO_TEMPLATE = """\
# Fill in every field before importing (python run_eval.py --import-manual manual/).
app: ""                     # e.g. "ChatGPT, free plan, web"
model_shown: ""             # exactly the model name the app shows for these chats
date: ""                    # YYYY-MM-DD of the chats
reasoning_mode: ""          # e.g. "default" or "Think/Reasoning on" -- use the same for every trial
no_tools_confirmed: false   # true only if code execution, web search and file tools were OFF and no reply used them
new_chat_per_trial: false   # true only if every trial was a brand-new chat (memory/personalization off)
notes: ""
"""


def chat_prompt(task: dict) -> str:
    """What to paste into the chat app: the API system prompt followed by the task prompt."""
    return f"{SYSTEM_PROMPT}\n\n---\n\n{task['prompt']}"


def write_prompts(tasks: list[dict], manual_dir: Path) -> list[Path]:
    out = []
    for task in tasks:
        path = manual_dir / "prompts" / f"{task['id']}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(chat_prompt(task), encoding="utf-8", newline="\n")
        out.append(path)
    return out


def new_manual_model(manual_dir: Path, name: str, tasks: list[dict], trials: int) -> Path:
    """Create the folder skeleton for one chat-app model (never overwrites existing replies)."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise ValueError("model name may only use letters, digits, '.', '_' and '-'")
    root = manual_dir / name
    root.mkdir(parents=True, exist_ok=True)
    info = root / "info.yaml"
    if not info.exists():
        info.write_text(INFO_TEMPLATE, encoding="utf-8", newline="\n")
    for task in tasks:
        for k in range(1, trials + 1):
            reply = root / task["id"] / f"trial_{k}.txt"
            reply.parent.mkdir(parents=True, exist_ok=True)
            if not reply.exists():
                reply.write_text("", encoding="utf-8")
    write_prompts(tasks, manual_dir)
    return root


def read_info(root: Path) -> tuple[Optional[dict], list[str]]:
    """(info, problems). Every text field must be filled and both confirmations true."""
    path = root / "info.yaml"
    if not path.exists():
        return None, [f"{path}: missing (create it with --new-manual {root.name})"]
    info = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    problems = [f"{path}: '{k}' is empty" for k in TEXT_FIELDS if not str(info.get(k) or "").strip()]
    if info.get("date") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(info["date"])):
        problems.append(f"{path}: 'date' must look like 2026-11-01")
    problems += [f"{path}: '{k}' must be true (see docs/RUNNING_FOR_FREE.md)" for k in CONFIRMATIONS
                 if info.get(k) is not True]
    return info, problems


def import_manual(manual_dir: Path, transcripts_dir: Path, tasks: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """Grade every non-empty reply file and write it as a transcript.
    Returns (transcripts written, problems). A model folder with problems is skipped whole."""
    written: list[dict] = []
    problems: list[str] = []
    if not manual_dir.is_dir():
        return written, [f"{manual_dir}: no such folder"]
    for root in sorted(p for p in manual_dir.iterdir() if p.is_dir() and p.name != "prompts"):
        info, info_problems = read_info(root)
        if info is None or info_problems:
            problems += info_problems
            continue
        replies = sorted(root.glob("task_*/trial_*.txt"))
        for reply in replies:
            task_id, match = reply.parent.name, re.fullmatch(r"trial_(\d+)\.txt", reply.name)
            if task_id not in tasks or not match:
                problems.append(f"{reply}: unknown task folder or file name")
                continue
            text = reply.read_text(encoding="utf-8")
            if not text.strip():
                continue  # not done yet
            out = transcript_path(transcripts_dir, root.name, task_id, int(match.group(1)))
            if out.exists() and _source(out) != SOURCE:
                problems.append(f"{reply}: {out} already holds an API transcript; rename the manual folder")
                continue
            transcript = build_manual_transcript(tasks[task_id], root.name, int(match.group(1)), text, info)
            write_json(out, transcript)
            written.append(transcript)
    return written, problems


def _source(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")).get("settings", {}).get("source")


def build_manual_transcript(task: dict, model: str, trial: int, text: str, info: dict) -> dict:
    parsed, grade = evaluate_output(task, text, "stop")
    return {
        "task_id": task["id"],
        "model": model,
        "settings": {
            "source": SOURCE,
            "app": info["app"],
            "model_shown": info["model_shown"],
            "reasoning": info["reasoning_mode"],
            "openrouter_id": None,
            "temperature": None,
            "max_tokens": None,
            "provider": None,
            "seed": None,
            "no_tools_confirmed": True,
            "new_chat_per_trial": True,
            "notes": info.get("notes") or "",
        },
        "trial": trial,
        "date": str(info["date"]),
        "system_prompt": SYSTEM_PROMPT,
        "prompt": task["prompt"],
        "delivered_as": "one pasted message: system prompt + '---' + task prompt",
        "raw_output": text,
        "reasoning_excerpt": None,
        "parsed_answer": parsed,
        "grade": grade.model_dump(mode="json"),
        "usage": {"cost_usd": 0.0},
        "latency_s": None,
        "finish_reason": "stop",
        "model_returned": info["model_shown"],
        "api_attempts": 0,
    }
