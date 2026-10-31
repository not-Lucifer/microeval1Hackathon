"""Aggregate transcripts into the scorecard (JSON) and summary tables (Markdown).

Definitions (per model):
  * valid trials  = all trials except API_ERROR (those are listed, never counted);
  * pass          = score == 1.0;  pass rate = passes / valid trials;
  * pass@k        = fraction of tasks with at least one pass among its k valid trials;
  * pass^k        = fraction of tasks where ALL k valid trials passed;
  * mean score    = average score (0 / 0.5 / 1) over valid trials.
TRUNCATED trials are failures and are also counted separately.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev

API_ERROR = "API_ERROR"
TRUNCATED = "TRUNCATED"


STALE_NOTE = ("answer a different version of their task (the stored prompt differs from tasks/), so they "
              "are left out; the task set v1 pilot transcripts are graded at git tag pilot-v1")


def load_transcripts(root: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.rglob("trial_*.json"))]


def split_stale(transcripts: list[dict], tasks: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """(transcripts that answer their task's current prompt, the others). An answer to an older
    version of a task must never be graded or counted against the current version."""
    current, stale = [], []
    for t in transcripts:
        task = tasks.get(t["task_id"])
        (current if task is not None and t["prompt"] == task["prompt"] else stale).append(t)
    return current, stale


def load_current_transcripts(root: Path, tasks: dict[str, dict], log=print) -> list[dict]:
    """load_transcripts without stale ones; says how many were left out."""
    current, stale = split_stale(load_transcripts(root), tasks)
    if stale:
        log(f"{len(stale)} transcript(s) {STALE_NOTE}")
    return current


def summarize(transcripts: list[dict]) -> dict:
    by_model: dict[str, list[dict]] = defaultdict(list)
    for t in transcripts:
        by_model[t["model"]].append(t)

    models = {}
    for model, items in sorted(by_model.items()):
        valid = [t for t in items if t["grade"]["failure_code"] != API_ERROR]
        per_task: dict[str, list[dict]] = defaultdict(list)
        for t in valid:
            per_task[t["task_id"]].append(t)
        task_rows = {}
        for task_id, ts in sorted(per_task.items()):
            ts = sorted(ts, key=lambda t: t["trial"])
            scores = [t["grade"]["score"] for t in ts]
            task_rows[task_id] = {
                "trials": len(ts),
                "scores": scores,
                "passes": sum(s == 1.0 for s in scores),
                "mean_score": round(mean(scores), 4),
                "failure_codes": [t["grade"]["failure_code"] for t in ts],
                "counterexamples": [t["grade"]["counterexample"] for t in ts],
            }
        scores = [t["grade"]["score"] for t in valid]
        costs = [t["usage"].get("cost_usd") for t in valid]  # API errors are rejected requests: free
        trial_means = defaultdict(list)  # spread across trial indices
        for t in valid:
            trial_means[t["trial"]].append(t["grade"]["score"])
        models[model] = {
            "settings": items[0]["settings"],
            "dates": sorted({t["date"][:10] for t in items}),
            "valid_trials": len(valid),
            "api_errors": [f"{t['task_id']}/trial_{t['trial']}" for t in items if t["grade"]["failure_code"] == API_ERROR],
            "truncated": sum(t["grade"]["failure_code"] == TRUNCATED for t in valid),
            "trials_per_task": max((r["trials"] for r in task_rows.values()), default=0),
            "pass_rate": round(sum(s == 1.0 for s in scores) / len(scores), 4) if scores else None,
            "mean_score": round(mean(scores), 4) if scores else None,
            "mean_score_sd_across_trial_indices": round(pstdev([mean(v) for v in trial_means.values()]), 4)
            if len(trial_means) > 1 else None,
            # float(): the mean of booleans is an int when they are all equal (e.g. 1, not 1.0)
            "pass_at_k": round(float(mean(r["passes"] > 0 for r in task_rows.values())), 4) if task_rows else None,
            "pass_hat_k": round(float(mean(r["passes"] == r["trials"] for r in task_rows.values())), 4)
            if task_rows else None,
            "failure_code_histogram": dict(Counter(t["grade"]["failure_code"] or "PASS" for t in valid)),
            "cost_usd": round(sum(c for c in costs if c is not None), 4),
            "calls_with_unknown_cost": sum(c is None for c in costs),
            "completion_tokens": sum(t["usage"].get("completion_tokens") or 0 for t in items),
            "total_latency_s": round(sum(t.get("latency_s") or 0 for t in items), 1),
            "tasks": task_rows,
        }
    return {"n_transcripts": len(transcripts), "models": models}


def _fmt(x) -> str:
    return "–" if x is None else (f"{100 * x:.0f}%" if isinstance(x, float) and x <= 1 else str(x))


def render_markdown(card: dict) -> str:
    lines = ["# Results summary", "", "Generated by `scripts/report.py` (or `run_eval.py --regrade`) from `transcripts/`. Do not edit by hand.", ""]
    if not card["models"]:
        return "\n".join(lines + ["_No transcripts yet._", ""])
    lines += [
        "| Model (settings) | Trials/task | Pass rate | pass@k | pass^k | Mean score | Truncated | API errors (excluded) | Cost (USD) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, m in card["models"].items():
        s = m["settings"]
        if s.get("source") == "manual chat app":
            setting = f"{s['app']}: {s['model_shown']}, reasoning={s['reasoning']}, pasted by hand"
        else:
            setting = f"`{s['openrouter_id']}`, T={s['temperature']}, reasoning={s['reasoning']}"
        cost = f"{m['cost_usd']:.2f}" + (f" (+{m['calls_with_unknown_cost']} unknown)" if m["calls_with_unknown_cost"] else "")
        lines.append(
            f"| {name} ({setting}) | {m['trials_per_task']} | {_fmt(m['pass_rate'])} | {_fmt(m['pass_at_k'])} | "
            f"{_fmt(m['pass_hat_k'])} | {'–' if m['mean_score'] is None else m['mean_score']} | "
            f"{m['truncated']} | {len(m['api_errors'])} | {cost} |"
        )
    task_ids = sorted({tid for m in card["models"].values() for tid in m["tasks"]})
    lines += ["", "## Per task (passes / valid trials, failure codes)", "", "| Model | " + " | ".join(task_ids) + " |",
              "|---|" + "---|" * len(task_ids)]
    for name, m in card["models"].items():
        cells = []
        for tid in task_ids:
            r = m["tasks"].get(tid)
            if r is None:
                cells.append("–")
                continue
            codes = ", ".join(sorted({c for c in r["failure_codes"] if c}))
            cells.append(f"{r['passes']}/{r['trials']}" + (f" ({codes})" if codes else ""))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += ["", "## Failure codes (all valid trials)", ""]
    for name, m in card["models"].items():
        hist = ", ".join(f"{k}: {v}" for k, v in sorted(m["failure_code_histogram"].items()))
        lines.append(f"- **{name}**: {hist}")
    lines.append("")
    return "\n".join(lines)


def write_reports(card: dict, results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    # newline="\n": identical bytes on every OS, so regenerated results never show spurious diffs
    (results_dir / "scorecard.json").write_text(
        json.dumps(card, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (results_dir / "summary.md").write_text(render_markdown(card), encoding="utf-8", newline="\n")
