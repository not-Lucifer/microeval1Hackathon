# AI use disclosure

This eval is **AI-assisted**. The author designed the project (idea doc, task families,
rubric mapping in `docs/PROJECT_GUIDE.md`) and is responsible for every task, reference
answer and grading rule. Claude Code (Anthropic) was used as a pair programmer.

## What Claude Code drafted (2026-10-30, Phases 0-3 of `docs/KICKOFF_PROMPTS.md`)

| Area | Files | How it was verified |
|---|---|---|
| Automata algorithms | `automata/dfa.py`, `nfa.py`, `regex.py`, `cfg.py` | Unit tests plus brute-force cross-checks on hundreds of random instances: equivalence vs exhaustive enumeration, minimization vs a brute-force Myhill-Nerode count, subset construction vs direct NFA simulation, three independent regex matchers (automaton, AST matcher, Python `re`), CFG checker vs CYK over all short words |
| Graders | `graders/*.py` | Every reference scores 1.0; every mutant gets the expected failure code (`tests/test_graders.py`); grader verdicts match brute force (`tests/test_bruteforce_crosscheck.py`) |
| Reference constructions + generators | `reference/build.py`, `scripts/generate_instances.py`, `scripts/search_t05_pairs.py` | `scripts/verify_specs.py` recomputes every quoted number and re-asserts all generator constraints; the numbers in the idea doc that the author had checked (T01 = 10, T02 = 6, T04 = 14, T07 counts) were reproduced, not copied |
| Task prompts | `tasks/*.json` (generated) | `tests/test_tasks_wellformed.py`: required statements present, every example agrees with the reference, format examples valid |
| Non-CF proof script | `scripts/check_task08_noncf.py` | Exhaustive decomposition search for N = 2..8 agrees with the hand proof in its docstring |
| Harness | `harness/*.py`, `run_eval.py`, `scripts/report.py` | End-to-end tests with a fake client (`tests/test_harness.py`); no-leak tests (`tests/test_no_leak.py`) |
| Free-run support (2026-10-31) | `models.free.yaml`, `harness/manual.py` (chat-app import), `docs/RUNNING_FOR_FREE.md` | `tests/test_manual.py` (import grades exactly like API answers, refuses incomplete or unconfirmed setups, never overwrites API transcripts); `tests/test_harness.py` (daily-quota stop, request cap, free-only guard) |
| Task set v2 (2026-10-31, after the author chose to replace the v1 tasks) | candidate designs (minimal sizes computed for many variants before choosing), `reference/build.py` constructions and generators, `automata/nfa.py::left_quotient`, `graders/oracles.py` (T07/T08 definitions), prompts in `scripts/generate_instances.py`, the T05 hand proof, the stale-transcript guard | every construction checked against a direct reading of the definition by brute force (`verify_specs.py`); left quotient and oracles against brute force (`tests/test_nfa.py`, `verify_specs.py`); every reference scores 1.0 and is minimal; mutants re-derived for v2 (`tests/test_graders.py`); v1 pilot re-graded unchanged at tag `pilot-v1` |
| Failure table (2026-11-01) | `harness/metrics.py::failure_note`, `listed_examples_missed`; the "Every failed trial" section of `results/summary.md` | `tests/test_harness.py` (one case per failure code; an accept-everything DFA and an overgenerating grammar mutant against the prompt examples). The v2 grades it describes were also re-checked outside the graders: each model answer run on every word up to length 8-13 against a direct reading of the task definition (T03 by brute force over prefixes, T06 by direct NFA simulation, T05 by Python `re`, T07/T08 by CYK); all 33 graded answers agreed, and again all 54 after trials 2-3 (with each stored counterexample, the state count of each passing DFA, and each passing grammar up to length 18 (T07) / 60 (T08)) |
| Failure explainer (2026-11-01) | `scripts/explain_failures.py`: first faulty table entry of each wrong DFA | `tests/test_explain_failures.py`: no faults on the reference, a planted flipped flag or redirected transition is found exactly |
| README analysis sections and submission texts (2026-11-01, at the author's request: "fill in those sections as a proper critic") | README: who relies on this, why each task is hard, per-task notes, main failure mode and hot take, limitations, provenance and prior-art search; task `why_hard` / `real_world` texts; `docs/SUBMISSION.md` (form description, checklist); `docs/VIDEO_SCRIPT.md` | every number in them is copied from `results/summary.md`, `scripts/verify_specs.py`, `scripts/explain_failures.py` or a transcript; claims about prior work were checked against the papers' abstracts; an independent Claude Code review session acted as a skeptical judge (findings in `docs/OPEN_QUESTIONS.md`) |
| Repo hygiene | `.gitignore`, `.githooks/pre-commit`, `scripts/check_secrets.py`, `scripts/make_zip.sh` | `tests/test_repo_hygiene.py` |
| Docs | `docs/OPEN_QUESTIONS.md`, `docs/REVIEW_LOG.md`, this file, README draft | Author review pending |

Task `why_hard` / `real_world` texts are marked *"DRAFTED BY CLAUDE CODE"* in the task files;
the author decided not to rewrite them (2026-11-01).

## What the author did

- Designed the project and the task families (idea document, `docs/PROJECT_GUIDE.md`).
- Chose every calibration decision (e.g. replacing task set v1 by v2, `OPEN_QUESTIONS.md` #39).
- Ran the first free API run (trial 1) and collected every ChatGPT reply by hand, confirming the
  no-tools and new-chat setup (`manual/chatgpt-free/info.yaml`). Free trials 2-3 were started by
  Claude Code at the author's request, with the README's free-model command.
- Read the failing transcripts (author's statement, 2026-11-01).

## What is still the author's to verify personally

- `docs/REVIEW_LOG.md`: a row is ticked only after the author has checked that item by hand.
  Claude Code never ticks a row.

## Where AI is NOT used

- **No LLM judge.** Every grade is computed by exact algorithms (bounded for the CFG tasks).
- No model output is used to construct tasks or reference answers.
