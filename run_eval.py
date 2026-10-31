"""Automata-Synth-Eval command line.

Live run -- SPENDS MONEY on OpenRouter (needs OPENROUTER_API_KEY in .env and --max-cost):
    python run_eval.py --models models.yaml --trials 3 --max-cost 5 [--task task_01 ...]
                       [--model NAME ...] [--concurrency 4] [--no-cache]
Cost estimate only (free, no API calls):
    python run_eval.py --models models.yaml --trials 3 --dry-run
Free OpenRouter models only (no money; uses the daily free-request quota):
    python run_eval.py --models models.free.yaml --trials 3 --max-cost 0 --concurrency 1
                       --max-attempts 2 --max-requests 45
Free chat apps, pasted by hand (see docs/RUNNING_FOR_FREE.md):
    python run_eval.py --new-manual chatgpt-free --trials 3
    python run_eval.py --import-manual manual/
Offline re-grade of saved transcripts (free, no API key, no network):
    python run_eval.py --regrade transcripts/ [--write]

pytest, scripts/verify_specs.py and --regrade never call a model and cost nothing.

Both modes rebuild results/scorecard.json and results/summary.md from transcripts/.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
TRANSCRIPTS_DIR = ROOT / "transcripts"
MANUAL_DIR = ROOT / "manual"
RESULTS_DIR = ROOT / "results"


def load_model_specs(path: Path, only: list[str] | None):
    from harness.client import ModelSpec

    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    defaults = config.get("defaults", {})
    names = [entry.get("name") for entry in config["models"]]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:  # transcripts are stored per model name, so duplicates would overwrite each other
        raise SystemExit(f"{path}: duplicate model names {duplicates}")
    specs, skipped = [], []
    for entry in config["models"]:
        merged = {**defaults, **entry}
        unknown = sorted(set(merged) - set(ModelSpec.__dataclass_fields__))
        if unknown:  # a typo such as "reasonning" must not silently change the settings
            raise SystemExit(f"{path}: model {merged.get('name')!r} has unknown keys {unknown}")
        if only and merged["name"] not in only:
            continue
        if not merged.get("openrouter_id"):
            skipped.append(merged["name"])
            continue
        specs.append(ModelSpec(**merged))
    if skipped:
        print(f"skipping models without a verified openrouter_id: {', '.join(skipped)}")
    return specs


def regrade(transcripts_dir: Path, write: bool, results_dir: Path = RESULTS_DIR) -> int:
    """Re-parse and re-grade every transcript; report any grade that changed.
    Returns the number of grades that changed or could not be recomputed because the
    transcript answers another version of its task (0 = stored grades reproduced exactly)."""
    from harness.metrics import STALE_NOTE, load_transcripts, split_stale, summarize, write_reports
    from harness.prompts import tasks_by_id
    from harness.runner import evaluate_output, transcript_path, write_json

    tasks = tasks_by_id()
    transcripts, stale = split_stale(load_transcripts(transcripts_dir), tasks)
    if stale:
        print(f"NOT GRADED: {len(stale)} transcript(s) {STALE_NOTE}")
    changed = 0
    for t in transcripts:
        if t["grade"]["failure_code"] == "API_ERROR":
            continue
        parsed, grade = evaluate_output(tasks[t["task_id"]], t["raw_output"], t["finish_reason"])
        new = grade.model_dump(mode="json")
        old = t["grade"]
        if (new["score"], new["failure_code"], new["counterexample"]) != (
            old["score"], old["failure_code"], old["counterexample"]
        ):
            changed += 1
            print(f"changed: {t['model']}/{t['task_id']}/trial_{t['trial']}: "
                  f"{old['score']} {old['failure_code']} -> {new['score']} {new['failure_code']}")
        t["grade"], t["parsed_answer"] = new, parsed
        if write:
            write_json(transcript_path(transcripts_dir, t["model"], t["task_id"], t["trial"]), t)
    card = summarize(transcripts)
    write_reports(card, results_dir)
    print(f"regraded {len(transcripts)} transcripts; {changed} grade(s) differ from the stored ones")
    print(f"wrote {results_dir / 'scorecard.json'} and {results_dir / 'summary.md'}")
    return changed + len(stale)


def live(args) -> int:
    from dotenv import load_dotenv

    from harness.cache import ResponseCache
    from harness.client import OpenRouterClient
    from harness.cost import CostTracker, estimate, observed_cost_per_call
    from harness.metrics import load_current_transcripts, load_transcripts, summarize, write_reports
    from harness.prompts import load_tasks, tasks_by_id
    from harness.runner import run_trials

    tasks = load_tasks(args.task)
    specs = load_model_specs(Path(args.models), args.model)
    if not tasks or not specs:
        print("nothing to run (check --task/--model filters and openrouter_id values in models.yaml)")
        return 1
    n_calls = len(specs) * len(tasks) * args.trials
    if args.dry_run:
        rows = estimate(specs, tasks, args.trials, args.assume_completion_tokens,
                        observed_cost_per_call(load_transcripts(TRANSCRIPTS_DIR)))
        for row in rows:
            usd = "unknown" if row["estimated_usd"] is None else f"${row['estimated_usd']:.2f}"
            print(f"{row['model']:28} calls={row['calls']:4} cost~{usd:>9}  ({row['basis']})")
        known = [r["estimated_usd"] for r in rows if r["estimated_usd"] is not None]
        any_paid = any(not s.openrouter_id.endswith(":free") for s in specs)
        print(f"total ~${sum(known):.2f} for {n_calls} calls"
              + (f" (+{len(rows) - len(known)} models unknown)" if len(known) < len(rows) else "")
              + ". Cached answers are free."
              + (" OpenRouter also needs enough balance to reserve max_tokens for every paid request "
                 "in flight, or it answers 402." if any_paid else ""))
        return 0
    if args.max_cost is None:
        print(f"Refusing to start: a live run makes up to {n_calls} API calls, which cost money unless "
              "every model is ':free'. Pass --max-cost USD (--max-cost 0 = free models only), "
              "or use --dry-run for a free estimate.")
        return 1
    paid = [s.name for s in specs if not s.openrouter_id.endswith(":free")]
    if args.max_cost == 0 and paid:
        print(f"Refusing to start: --max-cost 0 only runs ':free' models, but these are paid: {', '.join(paid)}")
        return 1

    if args.max_cost == 0:
        print(f"FREE RUN: up to {n_calls} calls = {len(specs)} models x {len(tasks)} tasks x {args.trials} "
              f"trials, ':free' models only. Each attempt uses one of your daily free requests"
              + (f"; at most {args.max_requests} this run." if args.max_requests else "."))
    else:
        print(f"LIVE RUN (spends money): up to {n_calls} calls = {len(specs)} models x {len(tasks)} tasks x "
              f"{args.trials} trials; no new calls after ${args.max_cost:.2f}. Cached answers are free.")
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY is not set (copy .env.example to .env and fill it in)")
        return 1
    client = OpenRouterClient(api_key, max_attempts=args.max_attempts)
    cost = CostTracker(args.max_cost, args.max_requests)

    async def run_all() -> None:
        try:
            await run_trials(tasks, specs, args.trials, client, TRANSCRIPTS_DIR,
                             ResponseCache(enabled=not args.no_cache), cost, args.concurrency)
        finally:
            await client.aclose()  # avoids "event loop is closed" noise on Windows

    asyncio.run(run_all())
    write_reports(summarize(load_current_transcripts(TRANSCRIPTS_DIR, tasks_by_id())), RESULTS_DIR)
    print(f"spent ${cost.total_usd:.2f} (+{cost.unknown_calls} calls with unknown cost) in {cost.requests} "
          f"requests; wrote {RESULTS_DIR / 'summary.md'}")
    return 0


def manual(args) -> int:
    """--new-manual NAME and --import-manual DIR (free chat-app route, see docs/RUNNING_FOR_FREE.md)."""
    from harness.manual import import_manual, new_manual_model
    from harness.metrics import load_current_transcripts, summarize, write_reports
    from harness.prompts import load_tasks, tasks_by_id

    if args.new_manual:
        root = new_manual_model(MANUAL_DIR, args.new_manual, load_tasks(args.task), args.trials)
        print(f"created {root} (fill in info.yaml; paste replies into the empty trial files) and "
              f"{MANUAL_DIR / 'prompts'} (the text to paste into each new chat)")
        return 0
    written, problems = import_manual(Path(args.import_manual), TRANSCRIPTS_DIR, tasks_by_id())
    for p in problems:
        print(f"NOT IMPORTED: {p}")
    for t in written:
        g = t["grade"]
        print(f"{t['model']:28} {t['task_id']} trial {t['trial']}: score {g['score']} {g['failure_code'] or ''}")
    write_reports(summarize(load_current_transcripts(TRANSCRIPTS_DIR, tasks_by_id())), RESULTS_DIR)
    print(f"imported {len(written)} replies; wrote {RESULTS_DIR / 'summary.md'}")
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):  # Windows consoles default to cp1252 (no ε)
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regrade", metavar="DIR", help="offline re-grade of saved transcripts")
    ap.add_argument("--write", action="store_true", help="with --regrade: store new grades in the transcripts")
    ap.add_argument("--models", default="models.yaml")
    ap.add_argument("--model", nargs="*", help="only these model names from models.yaml")
    ap.add_argument("--task", nargs="*", help="only these task ids, e.g. task_01 task_05")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--max-cost", type=float, default=None,
                    help="required for live runs: stop starting new calls after this many USD")
    ap.add_argument("--max-requests", type=int, default=None,
                    help="stop starting new calls after this many API requests (free daily quota)")
    ap.add_argument("--max-attempts", type=int, default=5, help="attempts per call before API_ERROR")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--assume-completion-tokens", type=int, default=8000)
    ap.add_argument("--new-manual", metavar="NAME", help="create manual/NAME/ to paste chat-app replies into")
    ap.add_argument("--import-manual", metavar="DIR", help="grade pasted chat-app replies (e.g. manual/)")
    args = ap.parse_args(argv)
    if args.regrade:
        return 1 if regrade(Path(args.regrade), args.write) else 0
    if args.new_manual or args.import_manual:
        return manual(args)
    return live(args)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main(sys.argv[1:]))
