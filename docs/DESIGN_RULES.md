# Design rules

The rules every task, grader and result in this repository follows. Code and docs refer to them
as "rule N" (for example, rule 8 for truncation).

1. **No unverified numbers.** Never hardcode an expected state count or answer in code or docs
   without a computing script behind it. `scripts/verify_specs.py` recomputes them, and the docs
   quote its output. (The original idea document claimed Task 01 needs 12 states; it was 10.)
2. **Grader before harness.** Every grader is built test-first and must accept its reference
   solution (score 1.0), reject mutants (wrong answers), and agree with a brute-force
   cross-check on small cases.
3. **Everything the grader checks is stated in the task prompt:** the alphabet, the
   completeness requirement, the definition of "minimal", the output schema, tie-breaks, and edge
   cases such as ε.
4. **Grade the outcome, not the path.** State names, the order of states, extra prose and
   reasoning are irrelevant; only the final JSON answer is graded.
5. **No leaks.** The harness never reads `reference/`, and prompts never contain reference
   answers. `tests/test_no_leak.py` enforces this.
6. **No LLM judge.**
7. **No tools for the models** in the primary condition: single-turn, no code execution. A
   tool-enabled run would be reported separately.
8. **API errors are not model failures.** Calls are retried with backoff; a call that still
   fails is marked `API_ERROR`, listed, and excluded from pass-rate denominators. Truncation
   (`finish_reason = length`) is a failure, coded `TRUNCATED`, and reported separately.
9. **Honest guarantees.** The DFA and regex-witness graders are exact (complete decision
   procedures). The CFG graders (Tasks 07–08) are bounded: exact up to length N, because CFG
   equivalence is undecidable in general.
10. **No secrets in the repository.** `.env` is never committed, `.env.example` lists variable
    names only, and a pre-commit hook (`scripts/check_secrets.py`) blocks keys.
11. **Reproducibility:** deterministic generators (fixed seeds), pinned dependencies, saved
    transcripts, and an offline `--regrade` mode, so anyone can reproduce the scores without
    spending money.
12. **No result that was not run.** README numbers come from `results/` via `scripts/report.py`.

## Scoring convention

`1.0` = exactly correct (and minimal where required) · `0.5` = language-correct but non-minimal
(DFA tasks) or a distinguishing but non-shortest witness (Task 05) · `0.0` otherwise. A pass, for
pass@k and pass^k, means a score of 1.0. Failure codes are in `graders/failure_codes.py`; every
failure stores a shortest counterexample string when one exists.
