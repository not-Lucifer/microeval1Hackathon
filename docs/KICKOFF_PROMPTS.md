# Claude Code Prompts — Automata-Synth-Eval

Paste these into Claude Code **in order**. Repo root must already contain `CLAUDE.md`; `docs/` must contain `PROJECT_GUIDE.md`, `HACKATHON_BRIEF.md`, `KICKOFF_PROMPTS.md`.

**Setup once**
```bash
mkdir automata-synth-eval && cd automata-synth-eval && git init
mkdir docs && # copy the 4 files: CLAUDE.md to root; the other three into docs/
claude        # start Claude Code here; use plan mode (Shift+Tab) for Phase 0
```

**Habits that protect your score**
- After each phase, *you* run `pytest -q` and `python scripts/verify_specs.py` and read the diff. Don't trust a summary.
- When the phase ends, open `docs/REVIEW_LOG.md` and only tick a row after you have personally verified it (draw the DFA, re-derive the number).
- If Claude Code disagrees with a number in the docs, the **computed** number wins (the original idea doc said Task 01 = 12 states; it is 10).

---

## MASTER PROMPT (paste first, once)

```
You are my pair-programmer on "Automata-Synth-Eval", my submission to the micro1 Eval Hackathon
(deadline Nov 9 2026, 10:45 AM IST). Before doing anything:

1. Read CLAUDE.md, docs/PROJECT_GUIDE.md and docs/HACKATHON_BRIEF.md completely.
2. Summarize back to me in <= 15 lines: what we are building, the 8 frozen tasks, how each is graded,
   and the three biggest risks. Explicitly list every place where PROJECT_GUIDE.md corrects the original
   idea (Task 08 replaced, Task 01 = 10 states, etc.) so I know you understood the corrections.
3. Then enter plan mode and propose the Phase 0 plan. Do not write code until I approve the plan.

Ground rules (also in CLAUDE.md): exact formal graders only (no LLM judge); no hardcoded expected
numbers without a script that computes them; grader tests before harness; the harness never reads
reference/; log any spec ambiguity in docs/OPEN_QUESTIONS.md instead of silently deciding; keep
docs/REVIEW_LOG.md and docs/AI_USE.md current; I must be able to explain every line, so prefer
simple readable code. If something in the docs looks wrong or contradicts computed output, stop and
tell me.
```

---

## PHASE 0 — Scaffold (Fri Oct 30 evening)

```
Phase 0: scaffold the repository exactly per PROJECT_GUIDE.md §4.

- Create the directory tree, empty modules with docstrings stating each module's responsibility,
  .gitignore (.env, .venv, __pycache__, .cache/, video/), LICENSE (MIT), .env.example (names only),
  models.yaml (placeholder entries marked "VERIFY ID ON OPENROUTER", no guessed slugs),
  requirements.txt (openai, pydantic, rich, pytest, python-dotenv, pyyaml) and install in a venv, then
  pin exact installed versions.
- Create docs/OPEN_QUESTIONS.md seeded with the 12 findings from PROJECT_GUIDE.md §2 (status: resolved/
  open), docs/REVIEW_LOG.md (table: item | what was produced | how the author verified it by hand | date |
  ticked), and docs/AI_USE.md (skeleton).
- Write scripts/verify_specs.py as a stub that will later recompute: T01/T02/T04/T07 minimal DFA sizes,
  T08 reference grammar vs brute force, T07 length counts. Make `pytest -q` run (even if 0 tests) and
  `python scripts/verify_specs.py` exit 0.
- Commit. Show me `tree -L 2` and the pinned requirements.
```

---

## PHASE 1 — Core automata + DFA grader (Sat Oct 31)

```
Phase 1: implement automata/dfa.py and automata/nfa.py and the DFA grader, test-first.

automata/dfa.py: pydantic DFA model {states, alphabet, start, accepting, transitions}; validate();
accepts(); remove_unreachable(); complete(); equivalent(d1, d2) -> (bool, shortest_counterexample)
using BFS over the reachable product with deterministic alphabet ordering; minimize() by partition
refinement (or Hopcroft) returning the minimal complete DFA; complement/intersect/product helpers.
automata/nfa.py: epsilon-NFA, epsilon_closure, subset_construction (return the number of reachable
subset states), to_dfa, right-quotient accepting-set computation (accepting set = states q of M1 such
that L(M1 from q) ∩ L(M2) != empty, via product reachability).

Tests (tests/test_dfa.py, test_nfa.py, test_bruteforce_crosscheck.py):
- hand-made small cases; random DFAs where equivalent()/minimize() are cross-checked against exhaustive
  string enumeration up to length 10; minimize() idempotent; renaming states changes nothing.

Then build the DFA tasks:
- reference constructions for T01 (counter x suffix-tracker with trap), T02 (precise definition in
  PROJECT_GUIDE §5, window W as a parameter), T04 (base-3 mod 7 x parity). References are built by
  *construction code*, then minimized; the expected size is whatever minimize() returns.
- graders/dfa_grader.py + graders/failure_codes.py + graders/grader.py implementing the scoring table
  in §7.1 (INCOMPLETE_DFA, NOT_EQUIVALENT with shortest counterexample, NON_MINIMAL_STATE_BLOAT = 0.5,
  etc.).
- tests/test_graders.py with a mutant generator: flip one accepting state, redirect one transition,
  delete one transition, add a duplicate equivalent state (0.5), add an unreachable state (0.5), rename
  all states (1.0). Every mutant must produce the expected code.
- scripts/verify_specs.py: now prints minimal sizes for T01, T02 (W=3..6) and T04. Expected from my own
  check: T01=10, T02(W=3)=6, T04=14. If your computed numbers differ, STOP and tell me which is right
  and why; do not "fix" the code to match.

Also write the T01/T02/T04 task JSON files (prompt text per §6 with schema + worked example on an
unrelated language), and add a REVIEW_LOG row per task/grader. Finish with a summary of what I should
personally double-check (e.g. draw the T01 DFA on paper and compare with the reference).
```

---

## PHASE 2 — Remaining engines and tasks (Sun Nov 1)

```
Phase 2: implement T03, T05, T06 (generators + references) and T07, T08 (CFG engine + references).

(a) T03: scripts/generate_instances.py seeded generator for two 5-state minimal complete DFAs over {a,b}
    satisfying the constraints in PROJECT_GUIDE §5/T03; reference = quotient via the nfa.py helper, then
    minimize. Test that quotient answers are checked against brute force: w in quotient iff exists y in
    L(M2) (|y| <= 8) with wy in L(M1) -- as a sanity oracle on small strings.
(b) T06: generator for a 5-state epsilon-NFA whose subset construction has exactly 11 reachable subset
    states; reference = minimal DFA; record the computed minimal size.
(c) T05: automata/regex.py parser for the exact grammar in §5/T05 (literals a,b; | ; juxtaposition; *,+,?;
    parentheses; "()" = epsilon) -> Thompson NFA -> DFA. Build regex pairs from hand-designed families
    whose shortest symmetric-difference string has length >= 9 (target 9-12), verified by product BFS.
    graders/witness_grader.py per §7.1 (WITNESS_NOT_DISTINGUISHING, WITNESS_NOT_SHORTEST=0.5). Cross-check
    the true minimal length against brute-force enumeration for lengths <= 12.
(d) automata/cfg.py: CNF validator, CYK, and enumerate_upto(grammar, N, cap) per §7.3 with early exit on
    the first string failing the truth predicate. graders/cfg_grader.py with OVERGENERATES /
    UNDERGENERATES / CNF_VIOLATION and a diagnostic F1 over strings <= N.
(e) T07: truth predicate and a 12-state truth DFA; unit-test oracle counts of valid strings by even
    length 2,4,6,8,10 = 2,7,29,126,558; test all the prompt examples from §5/T07; write a reference CNF
    grammar (depth-indexed nonterminals) and verify it with the grader and brute force. Choose N (14-16)
    and justify it in a comment/doc.
(f) T08: use the REPLACEMENT language {a^i b^j a^k : i>=1, k>=1, i+k=2j}. Convert the reference grammar
    in §5/T08 to CNF, verify against brute force up to length 24-30. Also write
    scripts/check_task08_noncf.py that demonstrates the ORIGINAL language (i>k) fails the pumping lemma on
    a^(N+2) b^(N+1) a^N for N=2..8 by exhaustive decomposition search, with a short docstring explaining
    the argument.
(g) Mutant suites for witness and CFG graders (§7.5). Update verify_specs.py. Update REVIEW_LOG/AI_USE.

Report any spec ambiguity in OPEN_QUESTIONS.md. List what I must verify by hand.
```

---

## PHASE 3 — Harness + pilot (Mon Nov 2)

```
Phase 3: build the harness (PROJECT_GUIDE §8) and run a cheap pilot.

- harness/client.py (openai SDK -> OpenRouter, retries/backoff, usage+cost capture), prompts.py (system
  prompt: no tools available; exactly one final ```json block), parsing.py (last fenced JSON block ->
  pydantic answer model; failure -> PARSE_ERROR), runner.py (async, concurrency limit, fresh state per
  trial), cache.py, cost.py (--max-cost guard, --dry-run estimate).
- run_eval.py: live mode, --task/--models/--trials filters, and --regrade <dir> offline mode that
  re-parses and re-grades saved transcripts with no API key and rebuilds results.
- Transcript schema per §8. API_ERROR excluded from denominators; TRUNCATED counted as failure and
  reported separately.
- tests/test_no_leak.py: assert no reference content appears in any task prompt and that harness code
  never opens reference/. tests/test_tasks_wellformed.py: every prompt states alphabet, schema, completeness
  rule, epsilon rule, tie-breaks; all prompt examples are accepted/rejected by the real grader.
- Tests for the harness using a fake client that returns canned model outputs (correct, wrong, truncated,
  unparsable) so the whole pipeline is tested without network.
- scripts/report.py -> results/summary.md + scorecard.json with pass rate, pass@k, pass^k, mean score,
  failure-code histogram, cost, runtime.

Then STOP and tell me which model ids I should verify on OpenRouter (do not guess slugs). After I fill
models.yaml, run a pilot: 1 trial x 8 tasks on 2 cheap models + 1 frontier model, --max-cost small. Show
the per-task results and flag: any 0%-everywhere task (read its transcripts to decide model error vs
spec/grader error), any task where the best model is ~100% (propose difficulty-knob changes), and any
case where a smaller model beats a larger one (look for ambiguity).
```

---

## PHASE 4 — Full runs (Nov 3–4)

```
Phase 4: after the calibration decisions are logged in OPEN_QUESTIONS.md and I have approved them,
run the full evaluation: >=3 models x 3-5 trials x 8 tasks (+ a reasoning-effort sweep on one model
if budget allows). Use --max-cost. Save every transcript. Do NOT modify task prompts or graders during
this phase unless a spec/grader bug is found; if so, log it, fix it, and rerun only the affected tasks
for all models (note the change in the README changelog). Produce results/summary.md and scorecard.json
and show me the table plus total cost and runtime.
```

---

## PHASE 5 — Failure analysis (Nov 5)

```
Phase 5: help me analyze failures (I will write the final analysis myself).

For every failing trial, show: task, model, failure code, shortest counterexample, and a 3-line excerpt of
where the reasoning went wrong. Group by mechanism (dropped trap state, wrong modulus transition, missed
epsilon-closure, "tested short strings and concluded equivalent", unminimized, non-CNF, overgenerates at
depth 4, ...). Flag every case where the *grader* might be wrong (a model answer that looks correct but
scored 0): for each, independently re-verify the model's automaton with brute force on strings <= 10 and
report whether the grader or the model was right. Propose candidate "hot takes" supported by the data with
counts; mark clearly which are supported vs speculative. Do not write the README analysis for me.
Optional (only if time): a tool-enabled ablation for one model, reported separately.
```

---

## PHASE 6 — Docs, repro, zip (Nov 6–7)

```
Phase 6: documentation and packaging.

1. Draft README.md following PROJECT_GUIDE §12 with all factual sections filled from results/ (tables,
   costs, versions, dates, commands) and clearly marked "AUTHOR TO WRITE" placeholders for: who relies on
   this, the failure-mode analysis, the hot take. Include the guarantees table (exact vs bounded-to-N)
   and the original-Task-08 case study.
2. Finalize docs/AI_USE.md (what you drafted, how it was verified) and make sure REVIEW_LOG.md lists
   everything I still need to tick.
3. scripts/make_zip.sh: include code, tasks, reference, graders, tests, results, transcripts, docs, README;
   exclude .env, .venv, __pycache__, video, .git; fail if > 50 MB or if any secret-like string
   (sk-..., OPENROUTER_API_KEY=<non-empty>) is found.
4. In a brand-new venv in a temp dir: unzip, pip install -r requirements.txt, run pytest -q, run
   python scripts/verify_specs.py, run python run_eval.py --regrade transcripts/ and diff the regenerated
   table against the README table. Report any mismatch.
5. Produce the pre-submission checklist from PROJECT_GUIDE §15 with each item marked verified/not.
```

---

## UTILITY PROMPTS

**Independent verifier (start a fresh Claude Code session, so it has no memory of the build):**
```
Act as a skeptical judge for the micro1 Eval Hackathon using the rubric in docs/HACKATHON_BRIEF.md.
Without reading the implementation first, read tasks/*.json and try to solve T01 and T04 by hand.
Then check: is any prompt ambiguous? Is anything graded that the prompt does not state? Then read
graders/ and tests/ and try to find a wrong answer that scores 1.0 or a correct answer that scores < 1.
Report findings ranked by rubric impact. Do not fix anything.
```

**Spec-doubt prompt (any time a number or claim looks off):**
```
Recompute <claim> from first principles with a standalone script (do not reuse project code), compare
with what the docs/code say, and tell me which is right and why. If the docs are wrong, list every file
that repeats the wrong claim.
```

**Difficulty calibration prompt:**
```
For task <id>, add a difficulty knob (<modulus|window W|diff length|NFA size>), compute the reference
minimal size for each setting with verify_specs.py, and run 1 trial of the cheapest and the strongest
model across settings. Show a small table: knob value | minimal size | cheap model score | strong model
score. Recommend the setting where the strong model is neither ~0% nor ~100%, with reasoning grounded in
the transcripts.
```

**Explain-it-to-me prompt (so I can defend the work in the video/Q&A):**
```
Explain <algorithm/module> to me as if I must present it to a judge: the idea, why it is correct, its
complexity, one worked example on a 3-state machine, and the two most likely questions a judge would ask
with good answers.
```
