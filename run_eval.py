"""Automata-Synth-Eval command line.

Live run (needs OPENROUTER_API_KEY in .env):
    python run_eval.py --models models.yaml --trials 3 [--task task_01 ...] [--model NAME ...]
                       [--concurrency 4] [--max-cost 10] [--no-cache]
Cost estimate only (no API calls):
    python run_eval.py --models models.yaml --trials 3 --dry-run [--assume-completion-tokens 8000]
Offline re-grade of saved transcripts (no API key, no network):
    python run_eval.py --regrade transcripts/ [--write]

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
    Returns the number of changed grades (0 = stored grades reproduced exactly)."""
    from harness.metrics import load_transcripts, summarize, write_reports
    from harness.prompts import tasks_by_id
    from harness.runner import evaluate_output, transcript_path, write_json

    tasks = tasks_by_id()
    transcripts = load_transcripts(transcripts_dir)
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
    return changed


def live(args) -> int:
    from dotenv import load_dotenv

    from harness.cache import ResponseCache
    from harness.client import OpenRouterClient
    from harness.cost import CostTracker, estimate
    from harness.metrics import load_transcripts, summarize, write_reports
    from harness.prompts import load_tasks
    from harness.runner import run_trials

    tasks = load_tasks(args.task)
    specs = load_model_specs(Path(args.models), args.model)
    if not tasks or not specs:
        print("nothing to run (check --task/--model filters and openrouter_id values in models.yaml)")
        return 1
    if args.dry_run:
        for row in estimate(specs, tasks, args.trials, args.assume_completion_tokens):
            usd = "unknown (set price_per_mtok)" if row["estimated_usd"] is None else f"${row['estimated_usd']:.2f}"
            print(f"{row['model']:28} calls={row['calls']:4} prompt_tok~{row['prompt_tokens']:>8} "
                  f"completion_tok~{row['completion_tokens']:>9} cost~{usd}")
        return 0

    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY is not set (copy .env.example to .env and fill it in)")
        return 1
    client = OpenRouterClient(api_key)
    cost = CostTracker(args.max_cost)

    async def run_all() -> None:
        try:
            await run_trials(tasks, specs, args.trials, client, TRANSCRIPTS_DIR,
                             ResponseCache(enabled=not args.no_cache), cost, args.concurrency)
        finally:
            await client.aclose()  # avoids "event loop is closed" noise on Windows

    asyncio.run(run_all())
    write_reports(summarize(load_transcripts(TRANSCRIPTS_DIR)), RESULTS_DIR)
    print(f"spent ${cost.total_usd:.2f} (+{cost.unknown_calls} calls with unknown cost); "
          f"wrote {RESULTS_DIR / 'summary.md'}")
    return 0


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
    ap.add_argument("--max-cost", type=float, default=None, help="stop starting new calls after this many USD")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--assume-completion-tokens", type=int, default=8000)
    args = ap.parse_args(argv)
    if args.regrade:
        return 1 if regrade(Path(args.regrade), args.write) else 0
    return live(args)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main(sys.argv[1:]))
