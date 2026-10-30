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

### T01 — Triple-product DFA
- **Alphabet** `{0,1}`. **Language** `L = { w : #₀(w) ≡ 1 (mod 3), w does not contain 010 as a substring, w does not end with 11 }`. (ε ∉ L since #₀(ε)=0.)
- **Answer:** minimal complete DFA.
- **Expected size:** **10 states** (computed; the naive product has 14 reachable states and 4 collapse). The author must be able to explain *which* 4 states collapse: the start state ε and the state after a lone `1` are equivalent to (counter=0, suffix `11`) because acceptance needs counter 1 and none of them can start a `010` straddle; and the three counter-copies of the dead state merge into one trap.
- **Why hard (mechanism, to be rewritten by author):** three simultaneous invariants (counter, last-two-symbols window, forbidden pattern/dead state) must be merged, then equivalent product states must be merged; models drop transitions or forget the trap.
- **Grader:** `dfa_exact`.
- **Difficulty knob:** modulus (3→4/5), forbidden pattern length.

### T02 — Lookahead-obligation DFA
- **Alphabet** `{a,b,c}`. **Precise language:** for a string `w` (0-indexed), every position `i` with `w[i]=a` **creates an obligation** unless `i>0` and `w[i-1]=b`. An obligation at `i` is **satisfied** iff some `j ∈ {i+1,…,i+W}` with `j < |w|` has `w[j]=c`. `w ∈ L` iff all obligations are satisfied. (An `a` at position 0 creates an obligation; an obligation unmet at end-of-string rejects; ε ∈ L.) **W = 3 by default.**
- **Expected size:** **6 states at W=3** (computed). May be too easy → **calibrate**: compute minimal sizes for W=3..6 in `verify_specs.py`, choose the W (or add a second condition) so the best pilot model is not ~100%.
- **Why hard:** overlapping obligations — a later `c` satisfies *all* pending `a`s but the *earliest* deadline governs; `ba` suppresses only the immediately following `a`.
- **Grader:** `dfa_exact`.

### T03 — Right quotient of two given DFAs
- **Input in prompt:** two explicit 5-state DFAs `M1, M2` over `{a,b}` as transition tables (generated from a seed; constraints below).
- **Task:** minimal complete DFA for `L(M1)/L(M2) = { x : ∃ y ∈ L(M2) with xy ∈ L(M1) }`.
- **Construction (reference):** keep M1's transitions; new accepting set = `{ q : L(M1 from q) ∩ L(M2) ≠ ∅ }`, computed by reachability in the product `M1_q × M2`. Then minimize.
- **Generator constraints (asserted):** `L(M2) ≠ ∅`, quotient ≠ `L(M1)`, quotient not trivially `∅`/`Σ*`, minimal quotient DFA has ≥ 3 states, M1 and M2 each already minimal and complete.
- **Why hard:** models guess the language in English instead of computing; confuse right quotient with left quotient/complement.
- **Grader:** `dfa_exact`.

### T04 — Base-3 divisibility with a parity side-condition
- **Alphabet** `{0,1,2}` = base-3 digits, **most significant digit first**. Leading zeros allowed. Value of ε is 0. **Language:** `value(w) ≡ 4 (mod 7)` **and** the number of `2` symbols in `w` is even.
- **Expected size:** **14 states** (computed: 7 × 2, all reachable, all distinguishable). No merging possible, so errors are *transition arithmetic* errors (`r' = (3r + d) mod 7`), not minimization errors.
- **Grader:** `dfa_exact`. **Knob:** modulus 7→11/13.

### T05 — Regex equivalence trap → shortest witness
- **Input:** two regexes `R1, R2` over `{a,b}` in the **stated grammar**: literals `a`,`b`; union `|`; concatenation by juxtaposition; postfix `*`, `+`, `?`; parentheses; `()` is ε; full-string match. (Document the grammar precisely in the prompt; parser in `automata/regex.py` must accept exactly it.)
- **Generator constraint (asserted):** `L(R1) Δ L(R2)` is non-empty and its shortest element has length **≥ 9** (so the regexes agree on all strings up to length 8); target lengths 9–12. Construct pairs by hand-designed families (e.g. counters/“every k-th position” conditions) and verify with product BFS.
- **Task:** output **any** shortest string in the symmetric difference.
- **Scoring:** 1.0 = in the symmetric difference and of minimal length; 0.5 = in the symmetric difference but longer; 0.0 otherwise.
- **Why hard:** models test short strings mentally (lengths 1–5), conclude "equivalent", or name a string that both accept. Failure codes: `WITNESS_NOT_DISTINGUISHING`, `WITNESS_NOT_SHORTEST`.
- **Grader:** `witness_grader` (exact: BFS on the product of the two compiled DFAs gives the true minimal length).

### T06 — ε-NFA determinization blow-up → minimal DFA
- **Input:** a 5-state ε-NFA over `{a,b}` (transition table including ε-moves).
- **Generator constraints (asserted):** subset construction (with ε-closures) has exactly **11 reachable subset-states**; record the minimal complete DFA size (computed, not assumed; it is ≤ 11).
- **Task:** minimal complete DFA. **Grader:** `dfa_exact`.
- **Why hard:** ε-closure errors mid-generation; forgetting that start state = closure of start; forgetting to merge indistinguishable subsets afterwards.

### T07 — Bounded-depth two-bracket Dyck variant (CFG answer)
- **Alphabet** `{ ( , ) , [ , ] }`. Strings are well-nested (each `(` closes with `)`, each `[` with `]`), **non-empty**. A *group* is a matched pair with its contents; depth of a group = 1 + number of enclosing groups. **Constraints:** (1) no group has depth > 3; (2) **no `(`-group is the immediate child of a `[`-group** (i.e. the innermost enclosing group of every `(` group is not a `[` group). `[`-groups may be children of anything; top-level `(` groups are fine.
- **Examples to place in the prompt (assert with tests):** valid — `()`, `([])`, `[[[]]]`, `(([]))`, `[]()`; invalid — `[()]` (paren directly in bracket), `[[()]]` (same), `(((())))` (depth 4), `(]`, `` (empty).
- **Answer:** a CFG in **Chomsky normal form** (ε excluded) generating exactly this language.
- **Facts:** the language is regular (depth is bounded); computed minimal complete DFA has **12 states** (ε excluded). Counts of valid strings by even length 2,4,6,8,10: **2, 7, 29, 126, 558** (brute-force verified) — use as unit-test oracle.
- **Grader:** `cfg_grader`, bounded to N=14–16 (enumerate model-grammar language up to N via DP with a cap; compare against the truth DFA; check all ground-truth strings ≤ N derivable).
- **Why hard:** models write the unconstrained Dyck grammar and bolt constraints on informally; CNF needs depth-indexed nonterminals (e.g. `S1,S2,S3` × parent-type).

### T08 — Linear-ratio CFG (**replaces the original T08**)
- **Alphabet** `{a,b}`. **Language** `L = { aⁱ bʲ aᵏ : i ≥ 1, k ≥ 1, i + k = 2j }`. Answer: CNF CFG.
- **Reference grammar (not CNF; author must convert and verify):**
  ```
  S  → A1 B1 | a A b B a
  A1 → a a A b          A → a a A b | ε
  B1 → b B a a          B → b B a a | ε
  ```
  Computed check: generates exactly the language for all strings up to length 14 (16 strings). Even-parity case = `A1 B1` (i=2n, k=2t, n,t≥1); odd-parity case = `a A b B a`.
- **Grader:** `cfg_grader` bounded to N=24–30 (the language is sparse, so larger N is cheap).
- **Why hard:** the model must discover that the ratio constraint decomposes into two independent nested blocks by parity, then CNF-convert without breaking it.
- **Original T08 (`i>k`) is non-CF:** keep `check_task08_noncf.py` and mention in the README as a case study of spec validation ("my first draft of this task was impossible; the grader's reference-solution requirement caught it").

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
