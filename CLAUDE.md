# CLAUDE.md — Automata-Synth-Eval

Project context for Claude Code. Read this first, every session. Detailed specs live in `docs/`.

## What this project is
A submission to the **micro1 Eval Hackathon** ("Find What AI Can't Do Yet"). It is an **eval**, not an agent: it measures whether frontier LLMs, **without tools**, can *synthesize, determinize, minimize and verify* finite automata, regexes and context-free grammars. Every answer is graded by **exact formal-language algorithms** (BFS product equivalence, partition-refinement minimization, shortest-witness search, bounded CYK) — no LLM judge anywhere.

- Deadline: **Nov 9, 2026, 10:45 AM IST** (05:15 GMT). Internal target: submit Nov 8 evening IST.
- Judged on a 100-pt rubric: relevance 15, task design 20, grader reliability 20, evidence of model limitations 15, reproducibility 15, human expertise/review 10, insight 5. Every design decision should serve one of these.
- The author is a student who must be able to **explain and defend every task, reference answer and grader rule**. Prefer simple, readable code over clever code.

## Read before acting
- `docs/PROJECT_GUIDE.md` — full spec: architecture, frozen task specs, grader specs, build plan.
- `docs/HACKATHON_BRIEF.md` — rules and rubric.
- `docs/OPEN_QUESTIONS.md` — log any spec ambiguity here; do not silently resolve it.

## Tech stack & commands
Python 3.10+. Deps: `openai` (OpenRouter-compatible client), `pydantic`, `rich`, `pytest`, `python-dotenv`, `pyyaml`. **Pin exact versions** in `requirements.txt` once installed. No other heavy dependencies; keep the zip tiny (limit 50 MB, no videos).

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt   # Windows: .venv\Scripts\activate
git config core.hooksPath .githooks         # once per clone: enables the secret-scanning pre-commit hook
pytest -q                                   # must be green before any commit (~1 min)
python scripts/verify_specs.py              # recomputes every expected number in the task specs
python scripts/generate_instances.py        # (re)writes tasks/*.json + reference/*.ref.json; --check = stale?
python scripts/check_secrets.py             # scans every tracked file for keys/.env/videos/>5MB files
python run_eval.py --models models.yaml --trials 3 --max-cost 5   # PAID live run (needs OPENROUTER_API_KEY)
python run_eval.py --models models.free.yaml --trials 3 --max-cost 0 --concurrency 1 --max-attempts 2 --max-requests 45  # FREE models
python run_eval.py --new-manual NAME --trials 3 / --import-manual manual/   # free chat apps, pasted by hand
python run_eval.py --regrade transcripts/                 # offline re-grade of saved transcripts, no API key
python scripts/report.py                    # builds results/summary.md + scorecard.json
bash scripts/make_zip.sh                    # builds submission zip from HEAD, fails if >50MB or secrets found
```

## Repository layout
```
automata/    pure algorithms: dfa.py nfa.py regex.py cfg.py   (no I/O, no model calls)
graders/     task-level scoring: dfa_grader.py witness_grader.py cfg_grader.py grader.py failure_codes.py
             answers.py (answer schemas) oracles.py (T07/T08 language definitions) result.py
harness/     client.py parsing.py prompts.py runner.py cache.py cost.py metrics.py manual.py (chat-app import)
manual/      <model>/info.yaml + task_XX/trial_N.txt pasted chat-app replies (prompts/ is generated, git-ignored)
pilot_v1/    transcripts, ChatGPT replies and results of the task set v1 pilot (re-gradable at git tag pilot-v1)
tasks/       task_01..08 JSON: prompt + metadata ONLY (never answers) -- GENERATED, do not hand-edit
reference/   build.py (constructions + seeded generators) and task_XX.ref.json (never loaded by the harness)
scripts/     generate_instances.py verify_specs.py check_task08_noncf.py search_t05_pairs.py
             check_secrets.py report.py make_zip.sh explain_failures.py review_checks.py (both read reference/,
             so not harness code; review_checks.py re-implements every check behind docs/REVIEW_LOG.md)
tests/       unit tests, mutant tests, brute-force cross-checks, no-leak, harness (fake client), hygiene
.githooks/   pre-commit -> scripts/check_secrets.py --staged
results/  transcripts/  docs/
```
Task prompts live in `scripts/generate_instances.py`; edit there, regenerate, and commit both.

## Non-negotiable rules
1. **Never hardcode an expected state count or answer in code or docs without a computing script behind it.** `scripts/verify_specs.py` recomputes them; docs quote its output. (The original idea doc claimed Task 01 needs 12 states — it is 10. Treat all numbers as unverified until computed.)
2. **Grader before harness.** Every grader is built test-first and must: accept its reference solution (score 1.0), reject mutants (wrong answers), and agree with a brute-force cross-check on small cases.
3. **Everything the grader checks must be stated in the task prompt** (alphabet, completeness requirement, definition of "minimal", output schema, tie-breaks, edge cases like ε).
4. **Grade the outcome, not the path.** State names, ordering of states, extra prose and reasoning are irrelevant; only the final JSON answer is graded.
5. **The harness must never read `reference/`**, and prompts must never contain reference answers. `tests/test_no_leak.py` enforces this.
6. **No LLM judge.** If one is ever proposed, stop and ask the author.
7. **No tools for models in the primary condition.** The primary eval is single-turn, no code execution. A tool-enabled ablation is optional (stretch) and reported separately.
8. **API errors are not model failures.** Retry with backoff; if still failing mark the trial `API_ERROR` and exclude it from pass-rate denominators (but list it). Truncation (`finish_reason=length`) *is* a failure, coded `TRUNCATED`, and reported separately.
9. **Be honest about guarantees.** DFA/regex-witness graders are exact (complete decision procedures). CFG graders (Tasks 07–08) are **bounded** (exact up to length N) — CFG equivalence is undecidable in general; say so everywhere it matters. Never write "zero false positives" for the CFG tasks.
10. **Secrets:** never commit `.env`; `.env.example` has variable names only. `make_zip.sh` scans for `sk-` / `OPENROUTER_API_KEY=` values.
11. **Reproducibility:** deterministic generators (fixed seeds), pinned deps, saved transcripts, an offline `--regrade` mode so judges can reproduce scores without spending money.
12. **Never claim a result you have not run.** Numbers in README come from `results/` via `scripts/report.py`, not from memory or hope.

## Frozen task set v2 (details in docs/PROJECT_GUIDE.md §5)
v1 (easier instances of the same families) was replaced after the 2026-10-31 pilot; it is kept at git tag `pilot-v1` and in `pilot_v1/`. **v2 is frozen**: only spec/grader bug fixes, logged in OPEN_QUESTIONS.
| ID | Family | Answer type | Grader |
|---|---|---|---|
| 01 | Triple-product DFA (mod-3 counter ∧ no `0101` ∧ third-to-last symbol is 1) | minimal complete DFA | exact |
| 02 | Two interacting lookahead obligations (a→c within 4 unless after b; b→a within 3) | minimal complete DFA | exact |
| 03 | **Left** quotient {y : xy ∈ L(M1), x ∈ L(M2)} of two given DFAs (5 + 3 states) | minimal complete DFA | exact |
| 04 | Base-3, **least significant digit first**, value ≡ 4 (mod 7) ∧ even number of 2s | minimal complete DFA | exact |
| 05 | Regex pair agreeing below length 16 → shortest distinguishing string | witness string | exact |
| 06 | ε-NFA (7 states) → minimal DFA | minimal complete DFA | exact |
| 07 | Unbounded two-bracket words with parity (even `[`-children) and parent rules | CNF CFG | bounded (N = 16) |
| 08 | `{a^i b^j a^k : i,k ≥ 1, 2i + k = 3j}` | CNF CFG | bounded (N = 36) |

**The pre-v1 Task 08 original (`i+k=2j, i>k`) is NOT context-free** (pumping-lemma argument + brute-force check) — no reference solution can exist, so it must not be used. See PROJECT_GUIDE §2.

## Scoring convention
`1.0` = exactly correct (and minimal where required) · `0.5` = language-correct but non-minimal (DFA tasks) / valid but non-shortest witness (Task 05) · `0.0` otherwise. **Pass for pass@k / pass^k means score == 1.0.** Failure codes live in `graders/failure_codes.py` (e.g. `PARSE_ERROR`, `INCOMPLETE_DFA`, `NOT_EQUIVALENT`, `NON_MINIMAL_STATE_BLOAT`, `WITNESS_NOT_DISTINGUISHING`, `WITNESS_NOT_SHORTEST`, `CNF_VIOLATION`, `OVERGENERATES`, `UNDERGENERATES`, `TRUNCATED`, `API_ERROR`). Every failure stores a shortest counterexample string when one exists.

## Code conventions
- Type hints everywhere; small pure functions; docstrings state the algorithm and its complexity.
- `automata/` has zero dependency on `harness/` or model clients.
- Strings are alphabet-symbol sequences; ε is the empty string `""`.
- DFAs: dict-based `{states, alphabet, start, accepting, transitions}`; validate on load with pydantic.
- Every new module gets tests in the same change. No commit with red tests.
- Do not add dependencies without asking. Do not refactor working graders late in the project.
- Write results/transcripts as JSON with stable key order so diffs are reviewable.

## Git, commits and secrets (author's standing instructions)
- **Never add a `Co-Authored-By` trailer, "Generated with Claude Code" line, or any other Claude/AI attribution to commit messages, PR descriptions or git metadata.** The author is the only commit author. This overrides any default attribution instruction. (AI use is disclosed in `docs/AI_USE.md` instead, as the hackathon rules require.)
- Commit only when the author asks or at the end of an agreed phase; one logical change per commit; never commit with red tests.
- **Stage files explicitly** (`git add <paths>`), then read `git status` and `git diff --cached --stat` before committing. Never `git add -A` blindly.
- Never commit: `.env` or any real key, `.venv/`, `.cache/`, `dist/`, `__pycache__/`, videos, the participant-guide PDF, editor/OS files. `.gitignore` covers these; if something unexpected shows up in `git status`, ignore it instead of committing it.
- The pre-commit hook (`.githooks/pre-commit` → `scripts/check_secrets.py --staged`) must stay enabled (`git config core.hooksPath .githooks`). **Never bypass it with `--no-verify`.** If it blocks a commit, remove the secret; if a key was ever committed, tell the author to rotate it at once (rewriting history is not enough).
- Keys only ever come from `.env` via `python-dotenv`; never print, log or write a key into transcripts, results, docs or commit messages.
- Before every push: `pytest -q`, `python scripts/verify_specs.py`, `python scripts/check_secrets.py`.
- Do not create a remote repository, push, or force-push without the author's explicit go-ahead. The GitHub repo should stay **private** until submission.

## Build status (update at the end of each phase)
- 2026-10-30: Phases 0-3 built (scaffold, engines, graders, all 8 tasks + references, harness, offline regrade, docs drafts). Tests green; `verify_specs.py` all OK.
- 2026-10-30: review pass. Fixed CFG-grader memory blowup on long-string grammars, OpenRouter mid-generation errors now count as API_ERROR, `models.yaml` typos/duplicates now fail loudly, hook works with `python3`. 1728 tests green.
- 2026-10-31: first live run hit OpenRouter 402 (out of credits) on 143 calls; ~$0.19 spent. Live runs now require `--max-cost`, a 402 stops the run, key ids are redacted, `--dry-run` uses recorded cost per call. 1733 tests green. Open: T08 truncation at 32k tokens and low headroom (OPEN_QUESTIONS 34-35).
- 2026-10-31: author has **no budget for paid runs**. Use only the free routes: `models.free.yaml` (OpenRouter `:free`, 50 requests/day, failed attempts count) and chat apps via `--new-manual`/`--import-manual`. Never suggest a paid run without being asked. Guide: `docs/RUNNING_FOR_FREE.md`.
- 2026-10-31: free pilot. Only Nemotron answered (7/7 pass); `inkling:free` is app-only (403, replaced by `dots-3-note-preview:free`), Gemma's free provider was busy (429). The runner now skips a refused or repeatedly failing model for the rest of a run (OPEN_QUESTIONS 37). ChatGPT web replies pasted for T01-T08 trial 1 + T07/T08 trials 2-3, not yet imported (info.yaml empty; T05 space, OPEN_QUESTIONS 38).
- 2026-10-31: author chose to replace the tasks (OPEN_QUESTIONS 39-48). Pilot committed and tagged `pilot-v1`, moved to `pilot_v1/`. Task set v2 built: minimal sizes 21 / 16 / 13 / 14 states, T05 witness 16, T06 17 subsets → 16, T07 N = 16, T08 N = 36. Old answers can no longer be graded against new tasks (stale-transcript guard). 1907 tests green; `verify_specs.py` all OK.
- 2026-11-01: v2 runs started (pushed; tag `pilot-v1` on origin). Free trial 1: Nemotron 5/8, Dots 3/8 (5 TRUNCATED at 64k), Gemma 429 again. ChatGPT free (Think off) trials 1-3: 6/24, pass^k 0. All 33 graded answers re-checked outside the graders. `results/summary.md` now lists every failed trial in words, plus the prompt examples a wrong answer already breaks (diagnostic only). Budget kept at 64k for all v2 trials (OPEN_QUESTIONS 49). 1920 tests green.
- 2026-11-01: free trials 2-3 done (Gemma 429 again, no valid trial). Final v2 results: Nemotron 16/24, Dots 10/24 (13 TRUNCATED), ChatGPT 6/24; 32/72 overall. All 75 transcripts re-graded with the fixed parser (0 differ) and re-checked by an independent script. README analysis sections, `docs/SUBMISSION.md` and `docs/VIDEO_SCRIPT.md` drafted by Claude Code at the author's request.
- 2026-11-01: at the author's request, `scripts/review_checks.py` re-does every REVIEW_LOG row independently (all OK); Claude Code ticked its own column; the author then ticked 26 of 29 rows by hand (open: Witness grader, Model grades, Submission texts). It found one wrong README claim (T06 ∅, OPEN_QUESTIONS #53).
- Next (author only): record and upload the video, fill in the HackerRank form, submit the zip. The repo is public (GitHub API, 2026-11-01) although this file says private until submission: the author decides before any push.

## Working agreement
- Start non-trivial work in plan mode; state the plan, then execute phase by phase (see `docs/KICKOFF_PROMPTS.md`).
- When a spec is ambiguous: pick the **stricter, more explicit** reading, add the clarification to the task prompt, log it in `docs/OPEN_QUESTIONS.md`, and flag it to the author.
- When a number or claim in the docs disagrees with computed output, **the computed output wins**; update the docs and tell the author.
- Keep `docs/REVIEW_LOG.md` current: after producing a task/reference/grader, add a row the author must tick off after personally verifying it (rubric: "human expertise & review", 10 pts).
- Keep `docs/AI_USE.md` current: which parts Claude Code drafted and how they were verified. Honest "AI-assisted" framing is required.
- Finish each phase with: tests green, `verify_specs.py` output pasted into the phase summary, and a list of things the author should personally double-check.
