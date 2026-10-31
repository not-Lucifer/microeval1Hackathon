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
| Repo hygiene | `.gitignore`, `.githooks/pre-commit`, `scripts/check_secrets.py`, `scripts/make_zip.sh` | `tests/test_repo_hygiene.py` |
| Docs | `docs/OPEN_QUESTIONS.md`, `docs/REVIEW_LOG.md`, this file, README draft | Author review pending |

Task `why_hard` / `real_world` texts are marked *"DRAFTED BY CLAUDE CODE"* in the task files
until the author rewrites them.

## What the author must write or verify personally

- Tick every row of `docs/REVIEW_LOG.md` after checking it by hand.
- Write the README sections marked **AUTHOR TO WRITE** (who relies on this, failure analysis,
  hot take) from the transcripts they have read.
- Rewrite the task rationales in their own words.
- Verify model ids on OpenRouter; run the pilot and full runs; read every failing transcript.

## Where AI is NOT used

- **No LLM judge.** Every grade is computed by exact algorithms (bounded for the CFG tasks).
- No model output is used to construct tasks or reference answers.
