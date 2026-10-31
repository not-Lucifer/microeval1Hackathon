# Automata-Synth-Eval

> **Status: draft, not yet submittable.** Task set v2, references, graders, tests and the harness exist. The v1 calibration pilot is in `pilot_v1/`; v2 runs are pending.
> Sections marked **AUTHOR TO WRITE** are deliberately left to the author.

**What it tests.** Whether frontier LLMs, reasoning *without tools*, can synthesize, determinize, minimize and check finite automata, regular expressions and context-free grammars. Every answer is graded by exact formal-language algorithms (product-BFS equivalence, partition-refinement minimization, shortest-witness search, bounded CFG checking). There is no LLM judge.

## Who it's for and why it matters

**AUTHOR TO WRITE**: who relies on hand-reasoned state machines (lexers, protocol FSMs, regex rule migrations, hardware controllers, students and tutors), what a subtly wrong automaton costs, and the honest caveat that a model *with* a code interpreter could solve these tasks.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q                            # ~1 min
python scripts/verify_specs.py       # recomputes every number quoted below
python run_eval.py --regrade transcripts/   # offline re-grade, no API key needed
```

Everything above is free: no model is called. Only a live run spends money. It refuses to start without `--max-cost`, and it stops when OpenRouter reports the account is out of credits. Fill in verified ids in `models.yaml` and `OPENROUTER_API_KEY` in `.env` first:

```bash
python run_eval.py --models models.yaml --trials 3 --dry-run          # free cost estimate
python run_eval.py --models models.yaml --trials 3 --max-cost 5       # paid
```

**Running for free:** `models.free.yaml` lists OpenRouter `:free` models (`--max-cost 0` refuses anything else). Frontier models can be tested through free chat apps, with replies pasted in by hand and graded by the same code. Step-by-step guide: [docs/RUNNING_FOR_FREE.md](docs/RUNNING_FOR_FREE.md).

OpenRouter reserves credit for each request's full `max_tokens` before it starts. A low balance therefore makes every request fail with HTTP 402 (recorded as `API_ERROR`, excluded from scores, never charged).

## Tasks

All numbers come from `python scripts/verify_specs.py`.

| ID | Task | Answer | Reference facts | Grader |
|---|---|---|---|---|
| 01 | `#0(w) ≡ 1 (mod 3)` ∧ no `0101` ∧ third-to-last symbol is 1, over {0,1} | minimal complete DFA | 21 states (naive product 30) | exact |
| 02 | Two obligations: every `a` (not right after `b`) needs a `c` within 4 symbols; every `b` needs an `a` within 3 | minimal complete DFA | 16 states | exact |
| 03 | Left quotient {y : xy ∈ L(M1) for some x ∈ L(M2)} of a given 5-state and 3-state DFA | minimal complete DFA | 3 start states → 14 subsets → 13 states | exact |
| 04 | Base-3 value, **least significant digit first**, ≡ 4 (mod 7) ∧ even number of 2s | minimal complete DFA | 14 states (obvious construction: 84) | exact |
| 05 | `(ab)*a+b(ab)+a+(ba)+(ba)+a` vs `(ab)?a+b(ab)+a+(ba)+(ba)+a`: shortest word in the symmetric difference | witness | unique shortest witness, length 16 | exact |
| 06 | 7-state ε-NFA → minimal DFA | minimal complete DFA | 17 reachable subsets → 16 states | exact |
| 07 | Two-bracket words of any depth: a `[`-group holds no `(`-group; every `(`-group, and the word, has an even number of `[`-children | CNF grammar | not regular; 13,778 words of length 16 | bounded, N = 16 |
| 08 | `{aⁱbʲaᵏ : i,k ≥ 1, 2i + k = 3j}` | CNF grammar | 92 words up to length 36 | bounded, N = 36 |

**AUTHOR TO WRITE**: one paragraph per task saying why it is hard, in your own words.

### Calibration: why these are the second version of the tasks

A first version (v1) of the same eight task families was piloted on 2026-10-31 with paid and free API models and with ChatGPT's free web app (`pilot_v1/results/summary.md`). The API models passed almost every v1 task they reached; the only failures were Task 08 truncations and ChatGPT with Think off. An eval of what AI cannot do yet needs headroom, so every instance was replaced by a harder one in the same family, with the same answer format and grader. The difficulty comes from structure (interacting deadlines, a reversed digit order whose obvious DFA is 6 times too big, a determinization step, counting inside a grammar), not only size. v1 and its transcripts are kept at git tag `pilot-v1` (`git checkout pilot-v1 && python run_eval.py --regrade transcripts/` reproduces every pilot grade). The current code refuses to grade a transcript whose prompt differs from the current task.

## How grading works

Scores: **1.0** correct (and minimal / shortest where required), **0.5** right language but too many states (DFA tasks) or a distinguishing but non-shortest witness (T05), **0** otherwise. Pass (for pass@k and pass^k) means score 1.0. Failure codes and descriptions are in `graders/failure_codes.py`; each failure stores a shortest counterexample string when one exists.

| Tasks | Guarantee |
|---|---|
| 01–04, 06 | **Exact.** Equivalence and minimality are decided, not sampled. |
| 05 | **Exact.** The true minimum length is computed by BFS on the product of the two minimal DFAs. |
| 07–08 | **Exact up to length N only.** CFG equivalence is undecidable in general. A pass means the grammar is in CNF, agrees with the language on every word of length ≤ N, and generates an infinite language. `tests/test_graders.py::test_bounded_guarantee_is_honest` shows an error beyond N that is *not* caught. |

The CFG check enumerates, per nonterminal, every string it derives up to the length where it could still matter, and tests each new string inside a fixed shortest context. So the first bad string found is a shortest over-generated word, and memory stays bounded by the size of the target language (`automata/cfg.py::check_upto`).

## How the grader was validated

- **References:** every reference answer scores 1.0 (`tests/test_graders.py`, `scripts/verify_specs.py`).
- **Mutants:** flipped accepting states, redirected and deleted transitions, duplicate and unreachable states, swapped behaviours, dropped trap states, invalid DFAs, the obvious-but-wrong T05 witness, longer witnesses, off-alphabet witnesses, every dropped production, overgenerating and non-CNF productions, and a finite "list every word up to N" grammar. Each one gets its expected failure code.
- **Brute force:** grader verdicts agree with exhaustive enumeration on hundreds of random small DFAs, regex pairs and mutated grammars (`tests/test_bruteforce_crosscheck.py`).
- **Independent oracles:** three regex matchers (automaton, AST matcher, Python `re`) agree; subset construction agrees with direct NFA simulation; minimization agrees with a brute-force Myhill-Nerode count.
- **Prompt/grader consistency:** every example in every prompt is checked against the reference (`tests/test_tasks_wellformed.py`).

## Results

**AUTHOR TO WRITE / RUN**: `results/summary.md` is generated by `scripts/report.py`. Copy the table here only from that file.

## Main failure mode and hot take

**AUTHOR TO WRITE**, from the transcripts you have read.

## Reproducing

- Offline: `python run_eval.py --regrade transcripts/` re-parses and re-grades every saved transcript and rebuilds `results/`. It exits 1 if any grade differs from the stored one.
- Live: results vary run to run; models, settings and dates are recorded in every transcript.
- Instances are deterministic: `python scripts/generate_instances.py --check` confirms that `tasks/` and `reference/` match the seeded generators.
- The v1 pilot (`pilot_v1/`): `git checkout pilot-v1`, then `python run_eval.py --regrade transcripts/` (0 grades differ), then `git checkout main`.
- Cost and runtime: **TO FILL from the runs.**

## Spec-validation case study: the original Task 08

The first draft of Task 08, `{aⁱbʲaᵏ : i+k = 2j, i > k ≥ 1}`, is **not context-free**, so no reference grammar can exist. The requirement that every task have a reference solution exposed this. `scripts/check_task08_noncf.py` contains the pumping-lemma proof and an exhaustive check of every decomposition for N = 2..8.

## Provenance

All tasks are synthetic, built from classical automata theory and generated from fixed seeds. No external datasets are used. **AUTHOR TO WRITE**: prior-art check, and what existed before the hackathon.

## AI use

See `docs/AI_USE.md`. In short: Claude Code drafted the code, tests and docs; every number is recomputed by scripts and every grader is tested against references, mutants and brute force. The author reviews and signs off each item in `docs/REVIEW_LOG.md`.

## Repository hygiene

- `git config core.hooksPath .githooks` enables a pre-commit hook (`scripts/check_secrets.py`) that blocks API keys, `.env` files, videos and files over 5 MB.
- `bash scripts/make_zip.sh` builds the submission zip from the committed tree and fails on secrets or if the zip exceeds 50 MB.

License: MIT.
