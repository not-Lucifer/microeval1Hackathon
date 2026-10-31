# Automata-Synth-Eval — Project Development Guide

**Hackathon:** micro1 Eval Hackathon · **Submission deadline:** Nov 9, 2026, 10:45 AM IST (internal target: Nov 8 evening IST)
**Place at:** `docs/PROJECT_GUIDE.md` · Companion files: `CLAUDE.md` (repo root), `docs/HACKATHON_BRIEF.md`, `docs/KICKOFF_PROMPTS.md`

---

## 0. How to use this kit
1. Create the repo, put `CLAUDE.md` at the root and the other three files in `docs/`.
2. Open Claude Code in the repo and paste the **Master Prompt** from `docs/KICKOFF_PROMPTS.md`, then run the phase prompts in order.
3. After every phase: run `pytest -q` and `python scripts/verify_specs.py`, then personally review what was built and tick the row in `docs/REVIEW_LOG.md`. The rubric gives 10 points for human review and penalizes unverified reference answers; this is where you earn them.

---

## 1. Project summary

**Name:** Automata-Synth-Eval
**One-line pitch:** Can frontier LLMs, reasoning on their own without code execution, correctly build, determinize, minimize and verify finite automata, regexes and grammars? We check every answer with exact formal-language algorithms.

**Why this is a good hackathon target**
- Answers are *mathematically* checkable: DFA equivalence and minimality are decidable in milliseconds, so graders are deterministic, cheap and fully reproducible (rubric: grader reliability 20, reproducibility 15).
- Failures are explainable by mechanism: dropped transitions, missed ε-closures, mishandled overlapping obligations, unmerged equivalent states. Every failure comes with a *shortest counterexample string* (rubric: evidence 15, insight 5).
- Task difficulty is predictable from theory before any model is run (the guide's "can you explain why it's hard before running a model?" test).

**Honest framing (important for the 15-pt relevance score and for credibility).**
Any model with a code interpreter can solve these tasks by writing ~40 lines of Python. So the claim is *not* "AI can't do automata". The claim is: **when a model must reason about state machines unaided — e.g. reviewing or generating a lexer, protocol state machine, firewall/regex rule, or hardware controller spec inside a chat or review loop — it silently produces automata that are wrong, and it does so confidently.** Who relies on this: engineers writing parsers/lexers/protocol FSMs, people migrating regex rule sets, students and formal-methods practitioners using LLMs as tutors/reviewers. Cost of failure: a state machine that is subtly wrong passes casual review (the counterexample can be a string of length 9+, which no human or model "tries"). The README must state this in the author's own words. An optional tool-enabled ablation (§9.4) turns the caveat into a finding.

---

## 2. Review of the original idea doc (corrections already applied below)

The original plan is strong but contained issues that would have cost points. Findings were **checked by script** (`scripts/verify_specs.py` must reproduce them).
These findings shaped task set **v1**. After the 2026-10-31 pilot every instance was replaced by a harder **v2** of the same family (§5); the numbers in this table describe v1 and are kept as history (v1 is at git tag `pilot-v1`).

| # | Issue in original | Evidence | Resolution in this guide |
|---|---|---|---|
| 1 | **Task 08 language `{aⁱbʲaᵏ : i+k=2j, i>k≥1}` is not context-free**, so no CNF grammar exists and no reference solution is possible. | Pumping lemma on `a^(N+2) b^(N+1) a^N`: brute force over all decompositions found a failing pump index for every N = 2…8; consistent with a hand proof (the strict inequality `i>k` together with `i+k=2j` forces a 3-way coupling). | Replaced by `{aⁱbʲaᵏ : i≥1, k≥1, i+k=2j}` (context-free; reference grammar below, verified equal to the language up to length 14). Re-run `scripts/check_task08_noncf.py` yourself and make sure you can explain the argument. |
| 2 | Task 01 claimed "12 minimal states". | Computed: naive reachable product = 14 states, **minimal = 10**. | Use computed value; never hardcode. |
| 3 | Task 02 spec "followed within at most 3 steps by a c, unless preceded immediately by b" is ambiguous (what counts as "within 3 steps"? end of string? first symbol?). | Violates "two experts agree". | Formalized in §5 (T02). Under that reading the minimal DFA has 6 states, so difficulty must be calibrated with a window knob. |
| 4 | Task 05/06 engine described as "lexicographically shortest string" but task asks for shortest in the symmetric difference, and tie-breaking wasn't prompt-stated. | Spec/grader mismatch. | Grader accepts **any** shortest string in the symmetric difference; prompt says so. |
| 5 | CNF grammars cannot derive ε, but Dyck-style balanced strings include ε. | Language mismatch. | Tasks 07–08 explicitly **exclude ε**. |
| 6 | Task 07 is labelled "PDA/non-regular", but with depth ≤ 3 it is **regular** (computed: 12-state minimal complete DFA, ε excluded). | Computed. | Keep the task (requesting a CFG is legitimate, and the bounded depth + parent constraint is the difficulty) but describe it honestly as "regular language, CFG answer required". "Immediately inside" defined precisely in §5 (T07). |
| 7 | "Exhaustive corpus of strings up to N=14" over a 4-symbol alphabet = ~358M strings; infeasible. And CFG equivalence is undecidable, so "100% decidability / zero false positives" is overclaimed for Tasks 07–08. | Arithmetic; theory. | Grader enumerates *the model grammar's language* up to length N by DP (with a cap and early exit), and checks all ground-truth strings ≤ N. Guarantee is "exact up to length N". The README states this limitation explicitly. |
| 8 | Dependency list contradictory ("zero-dependency… requests, pytest, pydantic" vs requirements with openai, rich). | Internal inconsistency. | One pinned `requirements.txt` (§4). |
| 9 | Pass/partial credit for non-minimal DFAs (0.5) was arbitrary and undocumented; unreachable states unspecified. | — | Documented scoring (§7.1); unreachable states count toward state total (stated in prompt). |
| 10 | Assumed frontier models "fail" for each listed reason without evidence. | The guide warns against assuming failure; 0% or 100% = broken eval. | Pilot run + difficulty knobs (§9.2); report whatever is found honestly. |
| 11 | No `reference/`, `transcripts/`, grader tests or mutants in the layout; no offline regrade. | Hackathon requires reference solutions, wrong-answer tests, transcripts, easy reproduction. | Added to layout (§4). |
| 12 | Missing: no-tools condition, model-settings logging, cost/runtime, AI-use disclosure, human review log. | Rubric items. | Added (§8–§11). |

---

## 3. Rubric → feature map

| Rubric criterion (pts) | Features that earn it |
|---|---|
| Real-world relevance (15) | README "Who relies on this" section; tasks framed as lexer/protocol/rule-migration/controller problems; honest tools-vs-no-tools discussion |
| Task design (20) | Frozen, formal, example-backed prompts; difficulty knobs; reference solution per task; `test_tasks_wellformed.py`; two-expert review log |
| Grader reliability (20) | Exact algorithms; reference + mutant tests; brute-force cross-check; documented guarantees per grader (§7.4) |
| Evidence of limitations (15) | ≥3 models × 3–5 trials; pass@k & pass^k; failure taxonomy with counterexamples; reasoning-effort sweep; transcripts |
| Reproducibility (15) | Pinned deps; seeded generators; single CLI; **offline `--regrade`** of committed transcripts; cost/runtime table; fresh-venv test |
| Human expertise & review (10) | `REVIEW_LOG.md`, `AI_USE.md`, hand-derived reasoning for each task in README |
| Insight (5) | Hot-take section from observed failure modes (e.g. "models track *one* invariant at a time"; "they verify by testing short strings") |

---

## 4. Architecture & directory structure

```
automata-synth-eval/
├── CLAUDE.md
├── README.md                    # written last, by the author (see §12)
├── LICENSE                      # MIT
├── requirements.txt             # pinned: openai, pydantic, rich, pytest, python-dotenv, pyyaml
├── .env.example                 # OPENROUTER_API_KEY=your_key_here   (names only)
├── .gitignore                   # .env, .venv, __pycache__, video/, .cache/
├── models.yaml                  # models + settings under test (IDs must be verified on OpenRouter)
├── run_eval.py                  # CLI: run | --regrade | --task | --models | --trials | --max-cost
├── automata/                    # pure algorithms, zero I/O
│   ├── dfa.py                   # DFA model, validate/complete, simulate, product BFS equivalence + shortest counterexample, partition-refinement/Hopcroft minimization, unreachable-state removal
│   ├── nfa.py                   # ε-NFA, ε-closure, subset construction, NFA→DFA, quotient helper
│   ├── regex.py                 # parser for the stated regex grammar, Thompson construction → NFA → DFA
│   └── cfg.py                   # CFG model, CNF validator, CYK membership, length-bounded language enumeration (DP + cap)
├── graders/
│   ├── dfa_grader.py            # Tasks 01–04, 06
│   ├── witness_grader.py        # Task 05
│   ├── cfg_grader.py            # Tasks 07–08
│   ├── grader.py                # dispatch by task.grader.type, returns GradeResult
│   └── failure_codes.py         # enum + human-readable descriptions
├── harness/
│   ├── client.py                # OpenRouter via openai SDK; retries/backoff; usage+cost capture
│   ├── prompts.py               # system prompt + answer-format contract
│   ├── parsing.py               # last fenced ```json block → pydantic model; failure → PARSE_ERROR
│   ├── runner.py                # async trials, concurrency limit, clean state per trial
│   ├── cache.py                 # content-hash cache so reruns cost nothing
│   └── cost.py                  # token/cost accounting, --max-cost guard
├── tasks/                       # prompt + metadata ONLY
│   ├── task_01_product_dfa.json
│   ├── task_02_lookahead_dfa.json
│   ├── task_03_right_quotient.json
│   ├── task_04_base3_mod7.json
│   ├── task_05_regex_witness.json
│   ├── task_06_enfa_minimal_dfa.json
│   ├── task_07_bounded_dyck_cfg.json
│   └── task_08_ratio_cfg.json
├── reference/                   # task_XX.ref.json (never read by harness)
├── scripts/
│   ├── generate_instances.py    # seeded generators for T03, T05, T06; asserts all spec constraints
│   ├── verify_specs.py          # recomputes every number quoted in docs/prompts; exit 1 on mismatch
│   ├── check_task08_noncf.py    # demonstrates the original T08 language fails the pumping lemma
│   ├── report.py                # results → summary.md + scorecard.json + README table snippet
│   └── make_zip.sh              # builds submission ZIP; fails on >50MB, video files, secrets
├── tests/
│   ├── test_dfa.py  test_nfa.py  test_regex.py  test_cfg.py
│   ├── test_graders.py          # reference passes; mutants fail with the expected code
│   ├── test_bruteforce_crosscheck.py
│   ├── test_tasks_wellformed.py # every prompt states alphabet, format, completeness, ε rule…
│   └── test_no_leak.py          # prompts/harness never contain reference content
├── results/
│   ├── runs/                    # per-run JSONL (one line per trial)
│   ├── scorecard.json
│   └── summary.md
├── transcripts/<model>/<task>/trial_<n>.json   # prompt, raw output, parsed answer, grade, usage
└── docs/
    ├── HACKATHON_BRIEF.md  PROJECT_GUIDE.md  KICKOFF_PROMPTS.md
    ├── OPEN_QUESTIONS.md  REVIEW_LOG.md  AI_USE.md
```

**Data flow:** `tasks/*.json (prompt)` → `harness` (model call, no reference access) → `parsing` → `graders` (reads `reference/` + task params) → `GradeResult{score, passed, failure_code, counterexample, details}` → `transcripts/` + `results/runs/*.jsonl` → `scripts/report.py` → tables.

**Task JSON schema (`tasks/*.json`)**
```json
{
  "id": "task_01",
  "family": "product_dfa",
  "title": "…",
  "prompt": "…full self-contained text incl. examples and output schema…",
  "answer_schema": "dfa",
  "grader": {"type": "dfa_exact", "params": {"alphabet": ["0","1"], "require_complete": true, "require_minimal": true}},
  "difficulty_knobs": {"…": "…"},
  "metadata": {
    "why_hard": "mechanism, written by the author before running models",
    "real_world": "who relies on this",
    "expected_failure_modes": ["…"],
    "seed": 1234
  }
}
```

**Dependencies:** Python 3.10+; `openai`, `pydantic`, `rich`, `pytest`, `python-dotenv`, `pyyaml`. Pin exact versions. `hypothesis` optional for property tests.

---

## 5. Task specifications (frozen unless `OPEN_QUESTIONS.md` says otherwise)

### Common conventions (restate inside every prompt)
- "Minimal DFA" = **complete** DFA (a transition for every state/symbol, including an explicit trap state if needed) with the **fewest possible states**. Unreachable states count as states.
- State names are arbitrary; only the language and the state count matter.
- The final answer is one fenced ```json block, last in the response. Reasoning before it is allowed and not graded.
- ε is the empty string. Languages are over the stated alphabet only.
- Models answer **without tools** (stated in the system prompt; no execution is provided).

**DFA answer schema**
```json
{"states": ["q0","q1"], "start": "q0", "accepting": ["q1"],
 "transitions": {"q0": {"0": "q1", "1": "q0"}, "q1": {"0": "q0", "1": "q1"}}}
```
**Witness answer schema:** `{"witness": "abba"}` (empty string allowed).
**CNF grammar schema:** `{"start": "S", "productions": [{"lhs": "S", "rhs": ["A","B"]}, {"lhs": "A", "rhs": ["a"]}]}`; every rhs is either two nonterminals or one terminal. Nonterminals are uppercase identifiers; terminals are the alphabet symbols.

---

### Task set v2 (current) and why it replaced v1

The first version of the eight tasks (v1, 2026-10-30) was calibrated on 2026-10-31 (§9.2): every model answering through the API passed almost every v1 task it reached, and the only failures were Task 08 truncations and ChatGPT's free plan with Think off (`pilot_v1/results/summary.md`). The author therefore replaced every instance with a harder one in the **same family, answer type and grader** (`docs/OPEN_QUESTIONS.md` #35 and #39-#48). The difficulty comes from added structure an expert recognises as hard (interacting conditions, a reversed reading order, a determinization step, counting inside a grammar), not only from size. v1 is kept at git tag `pilot-v1`. **v2 is frozen**: later changes only fix a spec or grader bug, logged in `OPEN_QUESTIONS.md`.

All numbers below come from `python scripts/verify_specs.py`.

### T01 — Triple-product DFA
- **Alphabet** `{0,1}`. **Language** `L = { w : #₀(w) ≡ 1 (mod 3), w does not contain 0101, |w| ≥ 3 and the third symbol from the end is 1 }`. (ε ∉ L.)
- **Answer:** minimal complete DFA. **Expected size:** **21 states**; the product of the mod-3 counter with the minimal DFA for the pattern and suffix conditions has **30** reachable states, so 9 merge.
- **Why hard:** three invariants at once; `0101` overlaps itself (after `010`, a `0` falls back to `0`, a `1` is fatal); a 3-symbol window for the suffix condition; merging; a trap state.
- **Grader:** `dfa_exact`. (v1: no `010`, not ending `11`, 10 states.)

### T02 — Two interacting lookahead obligations
- **Alphabet** `{a,b,c}`, positions from 0. **Rule A:** every `a` at position i creates an A-obligation unless `i > 0` and `w[i-1] = b`; it is satisfied iff some `j ∈ {i+1,…,i+4}`, `j < |w|`, has `w[j] = c`. **Rule B:** every `b` creates a B-obligation, satisfied iff some `j ∈ {i+1,…,i+3}`, `j < |w|`, has `w[j] = a`. `w ∈ L` iff all obligations are satisfied (ε ∈ L).
- **Expected size:** **16 states**. Reference state = (earliest A-deadline, earliest B-deadline, last symbol was b) + DEAD.
- **Why hard:** two deadlines at once, and the rules feed each other (a `b` demands an `a`; an `a` directly after `b` is exempt from rule A, a later one is not).
- **Grader:** `dfa_exact`. (v1: rule A alone, window 3, 6 states.)

### T03 — Left quotient of two given DFAs
- **Input:** seeded complete minimal DFAs M1 (5 states) and M2 (3 states) over `{a,b}` (seed in the task file).
- **Task:** minimal complete DFA for the left quotient `{ y : ∃ x ∈ L(M2), xy ∈ L(M1) }` (the prompt spells this out and never uses the `\` notation, which could be read as set difference).
- **Construction (reference):** S = M1 states reachable by a word of L(M2) (forward BFS in M1×M2, `automata/nfa.py::states_reached_by_language`); then subsets of M1's states starting from S (`left_quotient`); then minimize. **Instance:** |S| = **3**, **14** reachable subsets, minimal DFA **13** states.
- **Generator constraints (asserted):** M1, M2 minimal and complete; L(M2) ≠ ∅; 2 ≤ |S| < 5 (determinization needed, and M2 matters); quotient ≠ L(M1), ≠ the right quotient, ≠ ∅, ≠ Σ*; minimal size in 12..16 and below the subset count.
- **Why hard:** reachability *and* determinization *and* minimization by hand. (v1: right quotient, 5+5 states, 4-state answer.)

### T04 — Base-3, least significant digit first, with a parity side-condition
- **Alphabet** `{0,1,2}`; `value(d0 d1 … d(n-1)) = d0 + d1·3 + … + d(n-1)·3^(n-1)` (least significant digit first; trailing zeros allowed; value(ε) = 0). **Language:** `value(w) ≡ 4 (mod 7)` and an even number of `2`s. This is exactly the reversal of the v1 language.
- **Expected size:** **14 states**. The obvious construction (value mod 7, 3^k mod 7, parity) has **84** reachable states (it minimizes to the same 14).
- **Reference insight:** state = the residue the digits still to come must have: start 4; digit d maps s to (s − d)·3⁻¹ = (s − d)·5 mod 7; accept at s = 0 with even parity.
- **Why hard:** the correct obvious answer is far from minimal (0.5); the minimal one needs the reversal insight. (v1: most significant first, 14 states.)

### T05 — Regex equivalence trap → shortest witness
- **Input:** `R1 = (ab)*a+b(ab)+a+(ba)+(ba)+a`, `R2 = (ab)?a+b(ab)+a+(ba)+(ba)+a` (same grammar as before).
- **Facts:** they agree on every word shorter than **16**; the shortest witness `ababaababaababaa` is **unique** (brute force over all words up to length 16). Hand proof (a-run sequences) in `reference/build.py`. Alternative of the same family kept as a knob: `(aab)*a(ab)*a+bbab` vs `(aab)?a(ab)*a+bbab` (unique witness, length **14**).
- **Search:** `scripts/search_t05_pairs.py` (seed 23) reproduces both pairs.
- **Scoring:** 1.0 shortest, 0.5 distinguishing but longer, 0 otherwise (also for symbols other than a and b). (v1: witness length 10.)

### T06 — ε-NFA determinization → minimal DFA
- **Input:** a seeded 7-state ε-NFA over `{a,b}`.
- **Generator constraints (asserted):** 16..20 reachable subsets (∅ counts when reachable), ≥ 3 ε-moves, start ε-closure ≥ 2 states, 12 ≤ minimal size < subsets. **Instance:** **17** subsets → **16** states.
- **Why hard:** a longer ε-closure/subset computation, then finding the few equivalent subsets. (v1: 5 states, 11 subsets → 7.)

### T07 — Bracket words with parity and parent rules (CFG answer)
- **Alphabet** `{ ( , ) , [ , ] }`. Non-empty well-nested words such that (2) no `[`-group has a `(`-group as a child; (3) every `(`-group has an even number of `[`-children; (4) the word has an even number of top-level `[`-groups. Only children count; depth is unbounded, so the language is **not regular**.
- **Facts:** counts by length 2, 4, …, 16: **1, 3, 11, 43, 175, 734, 3151, 13778**. The reference CNF grammar (21 rules: groups P/B, child sequences Ev/Od with even/odd numbers of `[`-groups) passes the bounded check at N = 16.
- **Grader:** `cfg_bounded`, **N = 16**. (v1: depth ≤ 3 and the parent rule; regular.)

### T08 — Linear-ratio CFG
- **Alphabet** `{a,b}`. **Language** `L = { aⁱ bʲ aᵏ : i ≥ 1, k ≥ 1, 2i + k = 3j }`. Answer: CNF CFG.
- **Reference grammar (author must be able to explain it):**
  ```
  S → L1 R1 | a L b R a | aa L bb R aa        (by i mod 3: 0, 1, 2)
  L → aaa L bb | ε      R → b R aaa | ε       (L1, R1 = the non-empty versions)
  ```
  Each leading `a` is worth 2, each trailing `a` 1, each `b` costs 3; for i ≡ 1 one `b` is shared by both sides, for i ≡ 2 two are. CNF conversion: 30 rules (`reference/build.py`).
- **Facts:** **63** words up to length 30, **92** up to length 36. **Grader:** `cfg_bounded`, **N = 36**. (v1: i + k = 2j, N = 30.)
- **The pre-v1 original (`i+k=2j, i>k`) is non-CF:** keep `check_task08_noncf.py` and the README case study.

---

## 6. Prompt contract (system + task)

**System prompt (`harness/prompts.py`)** — identical for all models and tasks:
- Role: careful formal-methods engineer. **No tools are available; do not assume you can run code.**
- You may reason at length. End your reply with **exactly one** fenced ```json block containing the final answer in the schema given in the task. Only the last such block is graded.
- Do not include comments inside the JSON.

**Each task prompt must contain:** alphabet; formal definition of the language (with all edge cases: ε, leading zeros, end-of-string); definition of "minimal complete DFA" (where applicable); the exact JSON schema with a tiny worked example on an *unrelated* language; any tie-break rules; (T03/T06/T05) the full input data. `tests/test_tasks_wellformed.py` checks these mechanically (keywords/fields present, examples validated against the real grader).

**Settings (record in `models.yaml` and in every transcript):** model id, provider, temperature (0 unless the model requires otherwise), reasoning-effort/thinking budget, max output tokens (high enough that truncation is rare; truncation is reported as `TRUNCATED`), date, seed if supported.

---

## 7. Grader specification

### 7.1 Scoring
| Condition | Score | Code |
|---|---|---|
| Parse failure / schema violation | 0 | `PARSE_ERROR` |
| DFA missing a transition / unknown state / unknown symbol | 0 | `INCOMPLETE_DFA` / `INVALID_DFA` |
| Not language-equivalent | 0 | `NOT_EQUIVALENT` (+ shortest counterexample `w`, and who accepts it) |
| Equivalent but more states than minimal | 0.5 | `NON_MINIMAL_STATE_BLOAT` (+ states given vs minimal) |
| Equivalent and minimal | 1.0 | — |
| Witness not in symmetric difference | 0 | `WITNESS_NOT_DISTINGUISHING` |
| Witness distinguishing but longer than minimum | 0.5 | `WITNESS_NOT_SHORTEST` |
| Grammar not in CNF | 0 | `CNF_VIOLATION` |
| Grammar derives a string outside L (≤N) | 0 | `OVERGENERATES` (+ string) |
| Grammar misses a string of L (≤N) | 0 | `UNDERGENERATES` (+ string) |
| `finish_reason=length` | 0 | `TRUNCATED` |
| API failure after retries | excluded | `API_ERROR` |

`passed := (score == 1.0)` for pass@k / pass^k. Also compute a **diagnostic** (not part of pass): fraction of strings of length ≤ L (e.g. 10) classified correctly, to show *how far off* wrong automata are.

### 7.2 `automata/dfa.py` (must implement)
`validate(dfa, alphabet)`; `accepts(dfa, w)`; `complete(dfa)`; `remove_unreachable`; **`equivalent(d1, d2) -> (bool, counterexample|None)`** via BFS over the reachable product (shortest counterexample, deterministic tie-break by alphabet order); **`minimize(dfa)`** (partition refinement or Hopcroft; return the minimal complete DFA and its size); `complement`, `intersect`, `product`; `shortest_accepted(dfa)`. Use `minimize` on the *reference* to get the true minimum, never a stored number.

### 7.3 Other engines
- `nfa.py`: ε-closure, subset construction (report reachable subset count), `to_dfa`, right-quotient accepting-set computation.
- `regex.py`: parser for the exact grammar in §5/T05 → Thompson NFA → DFA; reject syntax outside the grammar.
- `cfg.py`: CNF validator; CYK membership; **`enumerate_upto(grammar, N, cap)`**: per-nonterminal, per-length string sets by DP; stops with a counterexample as soon as a generated string fails the truth predicate; if the cap is hit it reports `OVERGENERATES_CAP` with the best-known counterexample (a runaway grammar is wrong by definition).

### 7.4 Guarantees (state these in the README verbatim in spirit)
| Tasks | Guarantee |
|---|---|
| 01–04, 06 | Exact. Equivalence and minimality are decided, not sampled. |
| 05 | Exact. The true shortest distinguishing length is computed by product BFS. |
| 07–08 | **Exact up to length N only.** A pass means the grammar agrees with the truth on all strings of length ≤ N; CFG equivalence is undecidable in general. N is chosen well above the length at which the constraints first interact (justify per task). |

### 7.5 Grader validation protocol (feeds rubric: grader reliability 20)
1. **Reference test:** every `reference/task_XX.ref.json` scores 1.0.
2. **Mutant tests** (`tests/mutants/`, auto-generated + a few hand-written): flip one accepting state; redirect one transition; delete one transition; swap two states' behaviours; add a duplicate (equivalent) state → must score 0.5; add an unreachable state → 0.5; rename all states → still 1.0; for witnesses: a string both accept, a longer valid witness, an off-alphabet string; for grammars: drop one production, add an overgenerating production, add a unit production (CNF violation).
3. **Brute-force cross-check:** for random small automata/regexes/grammars, compare grader verdicts with exhaustive enumeration over all strings ≤ 8–10.
4. **Independent oracle:** an independent implementation path (e.g. brute-force language enumeration vs product BFS) must agree on equivalence/min-length for the T05 generator pairs.
5. **Prompt/grader consistency:** every example inside a prompt is run through the grader.
6. Record results of 1–5 in the README under "How the grader was validated".

---

## 8. Harness specification (`harness/`, `run_eval.py`)

- **Client:** `openai` SDK with `base_url="https://openrouter.ai/api/v1"`, key from `OPENROUTER_API_KEY` (`.env`). Capture `usage` and cost per call. Retries with exponential backoff on 429/5xx/timeouts; trials failing after retries are `API_ERROR` and re-queued once, never counted as model failures.
- **`models.yaml`:** list of `{name, openrouter_id, temperature, reasoning: {effort|max_tokens}, max_tokens}`. **Do not guess model slugs** — verify each on OpenRouter before the run and record the exact id and run date. Cover at minimum: 2–3 frontier reasoning models from different labs, one smaller/open model, and one non-reasoning baseline if affordable. Include a reasoning-effort sweep for one model (low/medium/high) to test "more reasoning helps".
- **Trials:** default 3–5 per task per model; each trial independent (fresh conversation, no shared history/cache across trials; the *response cache* only de-duplicates identical `(model,settings,prompt,trial_index)` for resumability).
- **Parsing:** last ```json fenced block → pydantic; fallback to last balanced JSON object; else `PARSE_ERROR`. Keep the raw text in the transcript.
- **Transcript schema (`transcripts/<model>/<task>/trial_<n>.json`):** `{task_id, model, settings, date, prompt, raw_output, parsed_answer, grade{score,passed,failure_code,counterexample,details}, usage{prompt_tokens,completion_tokens,reasoning_tokens,cost_usd}, latency_s, finish_reason}`. Store visible output; if reasoning traces are huge, store them truncated or omit — keep the zip well under 50 MB (check in `make_zip.sh`).
- **Cost guard:** `--max-cost USD` aborts cleanly; `--dry-run` prints estimated tokens/cost from the pilot averages.
- **Offline reproduction:** `python run_eval.py --regrade transcripts/` re-parses and re-grades every saved transcript and rebuilds the tables with **no API key**. This is how a judge verifies the headline numbers for free.
- **Live reproduction:** `python run_eval.py --models models.yaml --trials 3` (documents expected cost/runtime; results will vary run-to-run, which is why saved transcripts exist).

---

## 9. Experiments & reporting

### 9.1 Metrics
Per model: mean score; pass rate (score==1.0); **pass@k**; **pass^k**; per-task breakdown; failure-code histogram; mean/σ across trials; tokens, cost, runtime per full run.

### 9.2 Calibration (pilot before the full run)
Run 1 trial × 8 tasks on 2 cheap models and 1 frontier model. Check: not 0% everywhere (→ spec/grader bug? read the transcripts), not ~100% for the best model (→ raise difficulty knobs: modulus, window W, regex diff length, NFA size), small < frontier ordering mostly holds (if not, hunt for ambiguity). **Choose tasks because an expert judges them hard, then confirm with models** — don't tune tasks purely to make one model fail. Record what you changed and why in `OPEN_QUESTIONS.md`.

### 9.3 Failure analysis (the 15-pt evidence + 5-pt insight section)
Read every failing transcript for each task. For each, classify: *model error* vs *grader/spec error* (fix the latter and rerun). Tabulate mechanisms: dropped trap state, wrong modulus transition, missed ε-closure, claimed equivalence after testing short strings, unminimized output, non-CNF output, overgeneration at depth 4, etc. Include one task where models came close and say what tripped them. Look for a hot take (hypotheses to test, not to assume): models verify by testing a few short strings; models solve each invariant separately but fail at the product; minimization is skipped even when asked; confidence is uncorrelated with correctness.

### 9.4 Optional ablation (stretch, only after everything else)
One model with a Python tool (local sandboxed loop) on the same tasks. Report separately. Expected finding to *test*, not assume: tool use closes the gap, so the limitation is unaided formal reasoning. This turns the honesty caveat into a result.

### 9.5 Required results table (README)
| Model (version, settings) | Trials/task | Pass rate | pass^k | Mean score | Cost per full run |
|---|---|---|---|---|---|

plus per-task notes: who failed, how, link to a transcript.

---

## 10. Build plan (IST; today is Fri Oct 30)

| When | Phase | Output / exit criteria |
|---|---|---|
| Oct 30 (Fri) eve | **P0 Scaffold** | repo skeleton, docs in place, venv, `pytest` runs, `OPEN_QUESTIONS.md` seeded with §2 items |
| Oct 31 (Sat) | **P1 Core automata + DFA grader** | `dfa.py`, `nfa.py` + tests; brute-force cross-check; T01, T02, T04 references pass; `verify_specs.py` prints 10 / 6 / 14 |
| Nov 1 (Sun) | **P2 Remaining graders & tasks** | regex engine + T05 generator; T03/T06 generators; CFG engine + T07/T08 references; mutant suite green |
| Nov 2 (Mon) | **P3 Harness + pilot** | client, parsing, runner, cache, offline regrade; pilot on cheap models; calibration decisions logged |
| Nov 3–4 | **P4 Full runs** | ≥3 models × 3–5 trials; reasoning sweep; costs recorded |
| Nov 5 | **P5 Failure analysis** | every failing transcript read; failure taxonomy; (optional) tool ablation |
| Nov 6 | **P6 Docs** | README, results tables, `REVIEW_LOG` fully ticked by the author, `AI_USE.md` |
| Nov 7 | **P7 Repro & video** | fresh-venv/Codespace reproduction (live smoke test + offline regrade); record video; build ZIP |
| Nov 8 (Sun) | **Buffer + submit** | final checklist; submit by evening (deadline Nov 9, 10:45 AM IST) |

Cut order if time slips: tool ablation → reasoning sweep → second instance per task → fancy report formatting. Never cut: reference solutions, mutant tests, transcript reading, offline regrade, README honesty.

---

## 11. Human review & AI-use documentation

- **`docs/REVIEW_LOG.md`** — table with one row per task/grader/reference: *what was produced*, *how I verified it by hand* (e.g. "drew the 10-state DFA on paper, matched script"), *date*, *✔*. Claude Code adds rows; the **author** ticks them after genuinely verifying.
- **`docs/AI_USE.md`** — honest statement: which files Claude Code drafted, which the author wrote/rewrote (README analysis, task rationale, video), and how AI output was checked (tests, scripts, hand derivations). Use "AI-assisted" framing; do not overclaim authorship.
- The author must be able to explain, without notes: the product construction and why 14→10 in T01; the quotient construction; Hopcroft/partition refinement; why BFS on the product gives the *shortest* counterexample; why T07 is regular; why original T08 is not CF.

---

## 12. README outline (author writes the analysis sections personally)
1. What it tests (2 sentences) · 2. Who it's for / why it matters (+ tools caveat) · 3. Quick start (3 commands) · 4. Task overview table (task, formal spec, why hard, expected size) · 5. How grading works + guarantees table (§7.4) · 6. How the grader was validated (§7.5) · 7. Results table + per-task notes with transcript links · 8. Main failure mode & hot take · 9. Reproducing (live vs offline), versions, env vars, cost, runtime · 10. Provenance (all synthetic; no external datasets; classical automata theory; no existing benchmark copied — check for prior art before submitting and disclose any overlap; what existed before the hackathon vs built during it) · 11. Spec-validation case study (original T08) · 12. AI use disclosure.

## 13. Video script (≤ 5:00)
0:00–1:00 problem & why it matters (state the unaided-reasoning framing honestly) · 1:00–2:30 one task end-to-end: prompt → model answer → grader output with the counterexample string · 2:30–4:30 results table; walk through 1–2 failure transcripts (show the shortest counterexample that exposes the error) · 4:30–5:00 takeaway / hot take. Host the video with link-sharing set to "anyone with the link" and test in a private window.

## 14. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Spec ambiguity (judges can't agree on the answer) | Formal definitions + examples in prompts; `test_tasks_wellformed`; two-person read (ask a friend to solve one task by hand) |
| Invalid reference (like original T08) | Reference must pass grader *and* brute-force cross-check; `verify_specs.py` |
| 0% / ~100% results | Calibration pilot; difficulty knobs; read transcripts before concluding |
| Truncation / token blow-up | High `max_tokens`, `TRUNCATED` code, report separately, cost guard |
| API nondeterminism hurts reproducibility | Saved transcripts + offline regrade; report spread, not single runs |
| CFG grader overclaim | Say "exact up to N"; justify N; include mutants that differ only beyond small lengths |
| Wrong OpenRouter model ids / pricing | Verify ids on the day; record run date and version |
| Zip too large / leaked key | `make_zip.sh` checks size, excludes video and `.env`, greps for key patterns |
| Looks like unreviewed AI output | Review log, hand-written README analysis, ability to explain every grader |

## 15. Final pre-submission checklist
Copy the checklist from `docs/HACKATHON_BRIEF.md §11` and add:
- [ ] `python scripts/verify_specs.py` passes; numbers in README match its output
- [ ] `pytest -q` green in a **fresh venv**
- [ ] `python run_eval.py --regrade transcripts/` reproduces the README table exactly
- [ ] One live smoke test (1 task, 1 cheap model) works from the README commands
- [ ] `REVIEW_LOG.md` fully ticked by the author; `AI_USE.md` honest and complete
- [ ] Prior-art check done; overlaps disclosed
- [ ] ZIP < 50 MB, no video, no secrets, opens cleanly
