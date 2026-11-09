# Submission texts and checklist

Drafted by Claude Code at the author's request (see `docs/AI_USE.md`). Every number is copied from
`results/summary.md` (2026-11-09, final). If a result changes, regenerate it with
`python run_eval.py --regrade transcripts/` and update this file and the README together.

## Short written description (paste into the HackerRank form)

**Automata-Synth-Eval.** Domain: formal languages and automata, the theory behind lexers,
protocol monitors with timeouts, regex rules and configuration grammars.
**Limitation:** without tools, LLMs cannot reliably build, determinize and minimize state
machines or write context-free grammars. They know the constructions but get the bookkeeping
wrong, and their wrong answers often fail the examples printed in the prompt.
**Tasks:** 8, all synthetic:
- five minimal-DFA tasks (a three-way product, two interacting deadlines, a left quotient,
  least-significant-digit-first arithmetic, and determinizing an ε-NFA);
- one shortest word on which two regexes differ;
- two grammars in Chomsky normal form.

Every answer is graded by exact algorithms, with no LLM judge. The grammar tasks are exact
up to a stated length.
**Models:** NVIDIA Nemotron 3 Ultra and Dots 3 Note (free OpenRouter endpoints, high reasoning,
64,000 output tokens), ChatGPT's free web app with Think off and with Think on, and Gemini's free
web app in Fast mode, 3 trials per task; Claude.ai's free plan, 2 trials per task. Gemma 4 31B's
free endpoint refused every call.
**Headline:** 54 of 120 trials exactly right.
- The best setting, ChatGPT with Think on, solved 18 of 24 and every task at least once, but
  only 2 of the 8 tasks three times out of three.
- The same app with Think off solved 6 of 24, and Gemini in Fast mode solved 4 of 24. Neither
  solved any task three times out of three.
- The best open model solved 16 of 24.
- Two bookkeeping-heavy tasks were solved 3 times in 15 trials.
- The open reasoning models ran out of budget in 18 of 48 trials.
- Claude.ai (Sonnet 5.5, thinking off, 2 trials per task) did best: 14 of 16, not counted above.
  Both misses are near misses: a witness both regexes match, and one wrong arrow.

## Pre-submission checklist (HACKATHON_BRIEF §11 and PROJECT_GUIDE §15)

Status as of 2026-11-09. "Author" means only the author can do or attest to it.

| Item | Status |
|---|---|
| Every task has a reference solution that passes its grader | verified: `pytest`, `python scripts/verify_specs.py` |
| Deliberately wrong answers fail the grader | verified: mutant tests in `tests/test_graders.py`, brute-force cross-checks |
| Everything the grader checks is stated in the task | partly machine-checked: every prompt example agrees with an independent reading of the definition (`scripts/review_checks.py`, `tests/test_tasks_wellformed.py`). That each grading rule is written in its prompt was checked by Claude Code reading the prompts, not by a script |
| ≥ 1 frontier model tested, multiple trials per task | partly: free chat apps only. ChatGPT with Think off and with Think on and Gemini in Fast mode, 3 trials per task each; Claude.ai with 2 trials per task. No paid frontier API model (no budget); stated in README "Limitations" |
| I've read the failing transcripts and can explain why models fail | **author**: read the failing transcripts on 2026-11-01. The trial 2-3 failures of the open models arrived later that day, the 6 ChatGPT Think-on failures on 2026-11-02, and the Gemini and Claude.ai failures on 2026-11-05 and 2026-11-09; all are summarized in README "Per-task notes" |
| README explains run/reproduce, including versions, cost and runtime | done: README "Quick start", "Reproducing", "Cost and runtime", `requirements-lock.txt` |
| ZIP opens, < 50 MB, no videos | verified by `bash scripts/make_zip.sh` and by unpacking it into an empty folder (see below) |
| No API keys, passwords, confidential or private data in the ZIP | verified: `python scripts/check_secrets.py`, run again by `make_zip.sh` |
| Prior work clearly disclosed | done: README "Provenance" |
| Video link opens without permission and plays with audio | **author**: record from `docs/VIDEO_SCRIPT.md`, upload, open the link in a private window |
| Description filled in | **author**: paste the text above |
| Representative transcripts included for every model reported | done: every transcript is in `transcripts/` (Gemma: its three API-error records) |
| I've scored my own project against the rubric | **author**: a critic's draft is below |
| I've reviewed every task, reference answer and grading rule myself | **author**: all 29 rows of `docs/REVIEW_LOG.md` ticked by hand (2026-11-01); every row was also re-done by `scripts/review_checks.py` (all OK) |
| `verify_specs.py` passes; README numbers match its output | verified |
| `pytest` green in a fresh venv | verified on the unpacked zip with `requirements-lock.txt` (see below) |
| `--regrade transcripts/` reproduces the README table exactly | verified: 139 transcripts, 0 grades differ |
| One live smoke test works from the README commands | verified: the free trials were run with the README's free-model command |
| `REVIEW_LOG.md` fully ticked by the author; `AI_USE.md` honest and complete | done: all 29 rows ticked by the author, and all 29 re-done by `scripts/review_checks.py`. `AI_USE.md` says so |
| Prior-art check done; overlaps disclosed | done (2026-11-01) |

## A critic's view against the rubric (draft for the author's own scoring)

Not a score, just where a skeptical judge is likely to push.

- **Relevance (15).** The practical framing (lexers, monitors, regex review) is concrete. The
  weak point: the frontier products are free chat apps only, Gemini ran only in its default Fast
  mode, and ChatGPT and Gemini do not show which model version answered.
- **Task design (20).** Eight tasks in four families, hard by structure, recalibrated after a
  pilot with the pilot kept as evidence. Weak point: one instance per task.
- **Grader reliability (20).** The strongest part: exact decision procedures, mutants, brute
  force, and an independent re-check of every model grade. The bounded CFG check and its known
  gaming path are stated openly.
- **Evidence of limitations (15).** 54 of 120 trials pass and pass^3 is at most 38%. A judge may
  say 18 of the 66 failures are truncations at a fixed budget, and that the best setting
  (ChatGPT, Think on) passes 75%. The README reports truncations separately, and its claim for
  the best setting is reliability (2 of 8 tasks right every time), not inability. Claude.ai
  (14 of 16 with extended thinking off) goes against the "no thinking step" point, and the README
  says so; its two misses are the near misses the README describes.
- **Reproducibility (15).** Offline regrade in seconds, a lock file, seeded generators,
  transcripts with settings and dates.
- **Human expertise and review (10).** The author ticked all 29 review rows by hand,
  next to an independent machine re-check of all 29. A judge may still ask the author to
  explain one: the "Suggested hand check" column lists what each row expects the author to be
  able to do (e.g. explain why T04's 84 obvious states collapse to 14). Showing one of these
  in the video makes the review visible. Also the author's: the project idea and task
  families, every calibration decision (v1 → v2), collecting the chat-app replies.
- **Insight (5).** "Bookkeeping, not insight, breaks" is backed by the per-task counts. The
  tool-use conjecture is labelled as not measured.
