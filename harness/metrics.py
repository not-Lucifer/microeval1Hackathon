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
from typing import Optional

from automata.cfg import Grammar, cyk
from automata.dfa import DFA, accepts
from harness.prompts import tasks_by_id

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


def _word(w: str) -> str:
    return "`ε`" if w == "" else f"`{w}`"


def failure_note(t: dict) -> str:
    """One plain sentence saying what was wrong with a failed trial, built only from the facts
    its grader stored (L is the task's target language)."""
    g = t["grade"]
    code, d, cex = g["failure_code"], g.get("details") or {}, g.get("counterexample")
    if code == TRUNCATED:
        return f"no final answer within {(t.get('usage') or {}).get('completion_tokens') or '?'} output tokens"
    if code == "NON_MINIMAL_STATE_BLOAT":
        return f"right language, but {d['states_given']} states (minimal: {d['states_minimal']})"
    if code == "NOT_EQUIVALENT":
        if d["model_accepts"]:
            return f"accepts {_word(cex)}, which is not in L"
        return f"rejects {_word(cex)}, which is in L"
    if code == "INCOMPLETE_DFA":
        wrong = f"; even with a trap state added it is wrong on {_word(cex)}" if cex is not None else ""
        n = d["n_missing_transitions"]
        return f"{n} missing transition{'' if n == 1 else 's'}" + wrong
    if code == "WITNESS_NOT_DISTINGUISHING":
        return f"{_word(d['witness'])} is in {'both languages' if d['accepted_by_both'] else 'neither language'}"
    if code == "WITNESS_NOT_SHORTEST":
        return f"distinguishes, but has length {d['witness_length']} (shortest: {d['shortest_length']})"
    if code == "INVALID_WITNESS":
        return f"{_word(d['witness'])} uses symbols outside the alphabet: {d['invalid_symbols']}"
    if code == "OVERGENERATES":
        return f"generates {_word(cex)}, which is not in L"
    if code == "UNDERGENERATES":
        return f"cannot generate {_word(cex)}, which is in L"
    if code == "CNF_VIOLATION":
        return f"not in CNF: {(d.get('violations') or ['?'])[0]}"
    return str(d.get("error") or code)[:120]


LANGUAGE_WRONG = ("NOT_EQUIVALENT", "INCOMPLETE_DFA", "OVERGENERATES", "UNDERGENERATES")


def listed_examples_missed(t: dict, task: Optional[dict]) -> Optional[list[str]]:
    """The in/out examples printed in the task prompt that a wrong-language answer gets wrong
    (None when the task lists no examples or the answer's language was not wrong).

    Diagnostic only, never part of a grade: it shows mistakes the model could have caught by
    checking its own answer against its own prompt. Cost: one DFA run or one CYK parse per example."""
    if task is None or t["grade"]["failure_code"] not in LANGUAGE_WRONG:
        return None
    examples, answer = task["examples"], t["parsed_answer"]
    if not examples["in"] and not examples["out"]:
        return None
    alphabet = task["grader"]["params"]["alphabet"]
    if task["grader"]["type"] == "dfa_exact":
        dfa = DFA(states=answer["states"], alphabet=alphabet, start=answer["start"],
                  accepting=answer["accepting"], transitions=answer["transitions"])
        member = lambda w: accepts(dfa, w)  # noqa: E731  (a missing transition rejects)
    else:
        grammar = Grammar.model_validate(answer)
        member = lambda w: cyk(grammar, alphabet, w)  # noqa: E731
    return ([f"{_word(w)} (listed in L)" for w in examples["in"] if not member(w)]
            + [f"{_word(w)} (listed not in L)" for w in examples["out"] if member(w)])


def summarize(transcripts: list[dict], tasks: Optional[dict[str, dict]] = None) -> dict:
    """``tasks`` (default: the current tasks/) supplies the prompt examples for the diagnostic
    column; callers have already left out transcripts of other task versions."""
    tasks = tasks_by_id() if tasks is None else tasks
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
            "mean_score_by_trial": {str(k): round(mean(v), 4) for k, v in sorted(trial_means.items())},
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
            "failures": [
                {"task_id": t["task_id"], "trial": t["trial"], "score": t["grade"]["score"],
                 "failure_code": t["grade"]["failure_code"], "note": failure_note(t),
                 "listed_examples_missed": listed_examples_missed(t, tasks.get(t["task_id"]))}
                for t in sorted(valid, key=lambda t: (t["task_id"], t["trial"])) if t["grade"]["score"] < 1.0
            ],
        }
    return {"n_transcripts": len(transcripts), "models": models}


def _fmt(x) -> str:
    return "–" if x is None else (f"{100 * x:.0f}%" if isinstance(x, float) and x <= 1 else str(x))


def render_markdown(card: dict) -> str:
    lines = ["# Results summary", "", "Generated by `scripts/report.py` (or `run_eval.py --regrade`) from `transcripts/`. Do not edit by hand.", ""]
    if not card["models"]:
        return "\n".join(lines + ["_No transcripts yet._", ""])
    lines += [
        "| Model (settings) | Trials/task | Pass rate | pass@k | pass^k | Mean score | Mean score by trial | Truncated | API errors (excluded) | Cost (USD) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, m in card["models"].items():
        s = m["settings"]
        if s.get("source") == "manual chat app":
            setting = f"{s['app']}: {s['model_shown']}, reasoning={s['reasoning']}, pasted by hand"
        else:
            setting = f"`{s['openrouter_id']}`, T={s['temperature']}, reasoning={s['reasoning']}"
        cost = f"{m['cost_usd']:.2f}" + (f" (+{m['calls_with_unknown_cost']} unknown)" if m["calls_with_unknown_cost"] else "")
        by_trial = " / ".join(f"{v:.2f}" for v in m["mean_score_by_trial"].values()) or "–"
        lines.append(
            f"| {name} ({setting}) | {m['trials_per_task']} | {_fmt(m['pass_rate'])} | {_fmt(m['pass_at_k'])} | "
            f"{_fmt(m['pass_hat_k'])} | {'–' if m['mean_score'] is None else m['mean_score']} | {by_trial} | "
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
    lines += ["", "## Every failed trial (API errors excluded)", "",
              "What the grader found, in words. L is the task's target language. For automata and "
              "grammars the quoted word is a shortest word the answer gets wrong in the way stated; for "
              "task_05 it is the model's own witness. The last column (diagnostic, not part of the grade) "
              "lists the examples printed in the prompt that a wrong-language answer already gets wrong; "
              "it is empty for tasks whose prompt lists no examples.", "",
              "| Model | Task | Trial | Score | Code | What was wrong | Prompt examples it gets wrong |",
              "|---|---|---|---|---|---|---|"]
    for name, m in card["models"].items():
        for f in m["failures"]:
            note = f["note"].replace("|", "\\|")
            missed = f["listed_examples_missed"]
            missed = "" if missed is None else (", ".join(missed) or "none")
            lines.append(f"| {name} | {f['task_id']} | {f['trial']} | {f['score']} | {f['failure_code']} | {note} | {missed} |")
    lines.append("")
    return "\n".join(lines)


def write_reports(card: dict, results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    # newline="\n": identical bytes on every OS, so regenerated results never show spurious diffs
    (results_dir / "scorecard.json").write_text(
        json.dumps(card, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (results_dir / "summary.md").write_text(render_markdown(card), encoding="utf-8", newline="\n")
