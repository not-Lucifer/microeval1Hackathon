# Open questions and spec decisions

Every spec ambiguity or deviation is logged here instead of being silently resolved
(CLAUDE.md). **Status**: `resolved` (decision taken, stated in the prompt where it matters),
`open` (needs the author), `pending-pilot` (decide after the calibration run).
Numbers quoted here come from `python scripts/verify_specs.py`.

## A. Findings carried over from PROJECT_GUIDE §2 (review of the original idea doc)

| # | Issue | Status | Resolution / evidence |
|---|---|---|---|
| 1 | Original T08 `{aⁱbʲaᵏ : i+k=2j, i>k≥1}` is not context-free | resolved | Replaced by `i,k ≥ 1, i+k = 2j`. `scripts/check_task08_noncf.py`: every decomposition of `a^(N+2) b^(N+1) a^N` fails the pumping property for N = 2..8; hand proof in its docstring. |
| 2 | T01 claimed 12 minimal states | resolved | Computed **10** (naive product counter × minimal suffix DFA = 14). |
| 3 | T02 "within 3 steps … unless preceded by b" ambiguous | resolved | Formal definition (0-indexed positions, window `i+1..i+W`, end-of-word cut-off, exemption only for an `a` directly after `b`) written into the prompt with 11 examples. |
| 4 | T05 tie-breaking not stated | resolved | Grader accepts **any** shortest word of the symmetric difference; the prompt says so. |
| 5 | CNF cannot derive ε but Dyck includes ε | resolved | T07/T08 exclude ε; the prompts say so. |
| 6 | T07 described as non-regular | resolved | It is regular (12-state minimal truth DFA, ε excluded). Kept as "regular language, CFG answer required" (task metadata says so). |
| 7 | Exhaustive corpus for T07 up to 14 infeasible; "zero false positives" overclaimed | resolved | CFG grader is **exact up to length N only** (see C3 for the method). Never claimed beyond N. |
| 8 | Contradictory dependency list | resolved | One pinned `requirements.txt`. |
| 9 | 0.5 partial credit undocumented; unreachable states unspecified | resolved | Scoring table in every prompt; unreachable states count (stated in the prompt). |
| 10 | Failure assumed without evidence | pending-pilot | Pilot run + difficulty knobs before the full run. |
| 11 | Missing reference/, transcripts/, mutants, offline regrade | resolved | All present; `run_eval.py --regrade`. |
| 12 | Missing no-tools condition, settings logging, cost, AI-use, review log | resolved | System prompt says no tools; every transcript stores settings/date/usage/cost; `docs/AI_USE.md`, `docs/REVIEW_LOG.md`. |

## B. Decisions taken while building (author: please confirm or overrule)

| # | Question | Status | Decision |
|---|---|---|---|
| 13 | T06 "11 reachable subset-states": does the empty set count? | resolved | **Yes**, ∅ counts when reachable (it is the trap of the complete subset DFA). The number is a generator constraint only, never shown to models. |
| 14 | T06 generator: is any 11-subset NFA acceptable? | resolved (stricter) | Added constraints so the task tests what it claims: ≥ 2 ε-moves, start's ε-closure has ≥ 2 states, and 6 ≤ minimal size < 11 (minimization must merge something). Seed 8618 → minimal DFA **7** states. |
| 15 | T05: how were R1/R2 chosen? | resolved | Family "quantifier edit `X*` → `X?` before a tail that can re-absorb copies of X", searched by `scripts/search_t05_pairs.py` (seed 11), keeping only pairs where the obvious witness (XX + shortest tail) does **not** distinguish. Chosen: `(ba)*b+a(ba)+a` vs `(ba)?b+a(ba)+a`, unique shortest witness of length **10**, hand proof in `reference/build.py`. A length-**12** alternative is recorded as a difficulty knob. |
| 16 | T02 difficulty: minimal size is W+3 (6,7,8,9 for W = 3..6) | pending-pilot | Growth is linear, so W alone is a weak knob. Keep W = 3 for the pilot; if the best model is ~100%, add a second condition rather than only raising W. |
| 17 | T07/T08 bound N | resolved | T07 N = **16**, T08 N = **30** (justifications in the task metadata). Grading T07 at N = 16 takes ~0.2 s. |
| 18 | CFG grader: a finite grammar listing every word up to N would pass a pure "≤ N" check | resolved (stricter) | Grader also requires L(G) to be **infinite** (L is infinite, so this follows from "generate exactly L"); the prompt states it. A finite grammar gets UNDERGENERATES with a concrete missing word longer than its longest word. |
| 19 | CFG nonterminal names | resolved (lenient) | An rhs entry equal to a terminal symbol is a terminal; **any other name** is a nonterminal (prompt says so; uppercase recommended). Avoids false fails on naming. |
| 20 | CFG "diagnostic F1" | resolved (deviation) | Over-generation detection exits early, so full F1 is not available. We report `diagnostic_recall_upto_len` over the fully compared lengths (precision is 1 there by construction). |
| 21 | Truncation vs a parseable answer | resolved | `finish_reason = length` is always TRUNCATED (score 0), even if a JSON block was emitted (CLAUDE.md rule 8). |
| 22 | DFA answers: extra JSON keys / duplicates | resolved | Extra keys ignored; duplicate state names → INVALID_DFA (prompt asks for distinct names); duplicate entries in `accepting` tolerated. |
| 23 | Witness grader `counterexample` field | resolved | For witness failures it stores one correct shortest witness (for diagnosis); never shown to models. |
| 24 | T03 instance | resolved | Seed 3788 satisfies every §5 constraint; minimal quotient DFA has **4** states (spec minimum 3). |
| 25 | T07 reference grammar had unused `B3` productions | resolved | Found by the "drop any production must undergenerate" mutant test; removed. Every production of both reference grammars is now necessary. |
| 26 | `run_eval.py --regrade` exit code | resolved | Exits 1 if any recomputed grade differs from the stored one (a reproducibility alarm for judges). |
| 31 | OpenRouter `finish_reason = "error"` (provider failed mid-generation) | resolved | Treated as an API error (retried, then API_ERROR, excluded from denominators), never graded as a model answer (CLAUDE.md rule 8). |
| 33 | Spending safety (first live run, 2026-10-31, hit OpenRouter 402 "not enough credits" 143 times) | resolved | Live runs refuse to start without `--max-cost` and print how many paid calls they plan; a 402 stops the run instead of producing an API_ERROR for every remaining trial (402s were also retried 5x for nothing); error texts redact the OpenRouter key id; `--dry-run` estimates from the recorded cost per call. |
| 36 | Budget: the author has no budget for paid runs (2026-10-31) | resolved (author's choice) | Two free routes, both graded by the same code: (A) OpenRouter `:free` models in `models.free.yaml`: `nvidia/nemotron-3-ultra-550b-a55b:free`, `thinkingmachines/inkling:free`, `google/gemma-4-31b-it:free`, checked against OpenRouter's live model list on 2026-10-31; `max_tokens` near each model's own output limit (64,000 / 64,000 / 32,000) because free calls reserve no credit; (B) free chat apps pasted by hand (`harness/manual.py`, `docs/RUNNING_FOR_FREE.md`). Route-B differences, recorded in every transcript: system prompt pasted together with the task; temperature, reasoning budget and exact version are whatever the app uses; not re-runnable through an API, but fully re-gradable. The import requires the author to confirm tools were off and each trial was a new chat. |
| 32 | CFG grader memory on grammars with very long strings | resolved (bug fix) | Shortest strings and contexts used to be built literally, so a 30-rule doubling chain needed ~31 GB. Nothing longer than N is built now (~1 MB). For a finite grammar whose missing word would exceed 10,000 symbols, UNDERGENERATES is reported with no stored counterexample (noted in details). |

## C. Open items for the author

| # | Item | Status |
|---|---|---|
| 27 | Verify model ids on OpenRouter and fill `models.yaml` (do not guess slugs); record the run date here | open |
| 28 | Rewrite every `why_hard` / `real_world` field (currently marked as drafted by Claude Code) in your own words | open |
| 29 | Prior-art check (existing automata/regex LLM benchmarks) and disclosure in the README | open |
| 30 | Pilot calibration decisions (T02 knob, T05 harder pair, T04 modulus) | pending-pilot |
| 34 | Task 08 token budget: in the 2026-10-31 run both T08 answers were TRUNCATED. `anthropic/claude-haiku-5.5` (effort high) used 31,999 reasoning tokens and `deepseek/deepseek-v4.1-flash` used 27,042 of the 32,000 max_tokens, with no visible answer. Rule 8 counts this as a model failure; decide whether to raise `max_tokens` (e.g. 64,000, which needs more credit to reserve) so the budget is defensible, and say which in the README | pending-pilot |
| 35 | Headroom: in the same run (mostly 1 trial each, T06–T08 barely reached), small-open passed 21/22 valid trials, frontier-a 7/8, frontier-b 3/3. If a proper pilot confirms pass rates near 100%, raise difficulty (T05 harder pair, T02 extra condition, larger T01/T04 modulus) before the full run | pending-pilot |
