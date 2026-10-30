"""Build results/scorecard.json and results/summary.md from the grades stored in transcripts/.

    python scripts/report.py [--transcripts transcripts/]

(Use ``python run_eval.py --regrade transcripts/`` to recompute the grades first.)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.metrics import load_transcripts, summarize, write_reports  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcripts", default=str(ROOT / "transcripts"))
    args = ap.parse_args()
    card = summarize(load_transcripts(Path(args.transcripts)))
    write_reports(card, ROOT / "results")
    print(f"{card['n_transcripts']} transcripts -> results/scorecard.json, results/summary.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
