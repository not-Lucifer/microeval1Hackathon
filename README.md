# Automata-Synth-Eval

**What it tests.** Whether LLMs, reasoning *without tools*, can build, determinize, minimize and check finite automata, regular expressions and context-free grammars. There are eight tasks a formal-methods practitioner would recognise. Every answer is graded by exact formal-language algorithms: product-BFS equivalence, partition-refinement minimization, shortest-witness search, and a bounded grammar check that is exact up to a stated length. **There is no LLM judge.**

**Headline.** Of 120 graded trials (5 model settings × 8 tasks × 3 trials, free routes only), 54 (45%) were exactly right. The best setting, ChatGPT's free web app with Think on, solved 18 of 24 and every task at least once, but was right in all three trials on only 2 of the 8 tasks. The same app with Think off solved 6 of 24, and Gemini's free web app in its default Fast mode solved 4 of 24. The best open model, NVIDIA Nemotron 3 Ultra (free endpoint, high reasoning effort), solved 16 of 24, right in all three trials on only 3 of the 8 tasks. Two tasks were solved only 3 times in 15 trials: a DFA for three simple conditions at once (T01) and a grammar with three remainder cases (T08). The two open reasoning models never finished a Task 08 grammar within 64,000 output tokens (0 of 6). A sixth setting, Claude.ai's free plan (Sonnet 5.5, extended thinking off), was run for only 2 trials per task and is not in these totals. It did best of all: 14 of 16 right, and every task at least once; both of its misses are near misses of the kind described below.

**Video walkthrough (under 5 minutes):** [https://youtu.be/uoQBka6VnOU](https://youtu.be/uoQBka6VnOU). It covers the problem, how the eval works, why models fail and what the results show.

**Where to find each part:** short description (above) · [domain and expertise](#domain-and-expertise) · [what it tests and why it matters](#who-relies-on-this-and-why-it-matters) · [setup and run](#quick-start) (more in [Reproducing](#reproducing)) · [models tested and results](#results) · [failure analysis](#main-failure-mode-and-hot-take) · [prior work and sources](#provenance).

## Domain and expertise

**Field:** formal languages and automata theory, the part of the theory of computation behind lexers, regex engines, protocol and runtime monitors, input validators and parsers.

**The expertise the eval draws on:**
- building one automaton for several conditions at once (product constructions) and for timed obligations (T01, T02);
- determinizing an ε-NFA by the subset construction with ε-closures (T06), and left quotients, which need reachability plus subsets (T03);
- minimizing DFAs by partition refinement and proving minimality through Myhill–Nerode classes, the basis of the 0.5 score for a correct but bloated DFA (T01–T04, T06);
- modular arithmetic on numbers read least significant digit first, where the right state is the remainder the rest of the number still owes (T04);
- regex equivalence and the shortest word on which two regexes differ, found by BFS on a product automaton (T05);
- context-free grammars in Chomsky normal form, and the pumping lemma, which showed that a first draft of Task 08 is not context-free and so has no reference answer (T07, T08).

**How it is applied:** each task was chosen because an expert sees a specific trap in it (for example T04's reversal insight, or T05's `X*` versus `X?` edit that no short test reveals). Every reference answer is computed by a script and checked by an independent re-implementation (`scripts/review_checks.py`). The author checked every task, reference answer and grading rule by hand (`docs/REVIEW_LOG.md`).

## Who relies on this, and why it matters

People ask chat assistants to write and review small state machines all the time: a lexer rule, a protocol state machine with timeouts, a firewall or log-filter regex, a validator for a number format, a grammar for a configuration language. Students and tutors use them to check homework DFAs. In all of these the assistant answers in one go, without running code, and the human usually checks the answer by trying a few short inputs.

Some wrong answers here are caught by a 1- to 4-letter word, but others survive any quick test. Three 15-state answers to Task 06, two from ChatGPT (Think off) and one from Claude, agree with the correct DFA on 99.7% of all words up to length 10. Their first error is the 9-letter word `aabbabaab`, and `scripts/explain_failures.py` traces each to a single wrong arrow in a 30-entry transition table. A right answer can also be bloated: four Task 04 answers, from ChatGPT and Gemini, have 84 states where 14 suffice. That is the difference between a controller that fits a hardware budget and one that does not. What a wrong state machine costs depends on where it sits: a lexer that silently mis-tokenizes, a timeout monitor that never fires, a filter that lets one class of inputs through.

**Honest caveat.** A model *with* a code interpreter could likely solve every task here with a short program (subset construction plus minimization). The claim is therefore not "AI cannot do automata". The claim is narrower and practical: **when a model reasons about a state machine unaided, as it does in a chat or a code review, it often produces an automaton that is wrong or not minimal. In a fast mode with no thinking step, its answers often fail the examples they were given; with reasoning, the work often does not fit in a 64,000-token budget, and even the best complete run was right three times out of three on only 2 of the 8 tasks.** The primary condition is single-turn, with no tools; a tool-enabled ablation was not run (see Limitations).

**Using the graders outside this eval.** The checking code is plain Python with no model calls, so it can check a state machine, a regex edit or a grammar, whoever wrote it. These are uses of the code as it is; none was tried with outside users.
- **Reviewing a regex change.** `automata.regex.to_min_dfa` and `automata.dfa.equivalent` either prove that two regexes match the same words or give the shortest word on which they differ. On the Task 05 pair, this prints `(False, 'ababaababaababaa')` in about a third of a second, a difference that no test shorter than 16 letters can find:
  ```bash
  python -c "from automata.regex import to_min_dfa as m; from automata.dfa import equivalent; print(equivalent(m('(ab)*a+b(ab)+a+(ba)+(ba)+a', ['a','b']), m('(ab)?a+b(ab)+a+(ba)+(ba)+a', ['a','b'])))"
  ```
  The regex syntax is the small one stated in the Task 05 prompt: one-character symbols, `|`, `*`, `+`, `?` and parentheses.
- **Checking a generated DFA before it is used.** `equivalent` and `minimal_size` (`automata/dfa.py`) decide whether a DFA has exactly the intended language and how many states it needs. When it is wrong they give a shortest word it gets wrong, and `scripts/explain_failures.py` points to the first faulty transition on that word.
- **Grading automata homework.** The task prompts and graders work as an autograder that answers a wrong DFA with the shortest word it gets wrong, not a bare "incorrect". For grammars the check is exact only up to a length bound.
- **Choosing a model or a policy.** A team that lets an assistant write lexer rules or validators can run these tasks on its candidate models (`models.yaml`) and look at pass^3, not only the pass rate. The results here argue for a checker, or a code tool, behind any model-written state machine.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # direct dependencies, pinned (exact full set: requirements-lock.txt)
pytest -q                            # 1,900+ tests, about 1 minute
python scripts/verify_specs.py       # recomputes every number quoted below (about 10 s)
python run_eval.py --regrade transcripts/   # offline re-grade of every saved answer, no API key (about 2 s)
```

Everything above is free: no model is called. Tested in a brand-new venv on Python 3.13.7 (Windows 11); the code is written for Python 3.10+. To run models yourself, see [Reproducing](#reproducing).

## Tasks

All numbers come from `python scripts/verify_specs.py`. Each prompt states everything the grader checks: the alphabet, that the DFA must be complete and minimal, that every listed state counts (including unreachable ones), that ε is excluded where it is, the output schema, and the tie-break rules.

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

### Why each task is hard (before any model is run)

- **T01. Three invariants in one product.** A counter mod 3, a forbidden pattern that overlaps itself (`0101` ends in `01`, so after `010` a `1` is fatal but a `0` falls back to `0`), and a 3-symbol window for the third-to-last symbol. Building the product carefully gives 30 states, which must be merged down to 21, including one trap state. The difficulty is the interaction: no single invariant is hard.
- **T02. Two deadlines that feed each other.** The DFA must remember the earliest pending `c`-deadline, the earliest pending `a`-deadline and whether the last symbol was `b`. An `a` that pays off a `b`'s obligation is exempt from its own rule only if it comes *directly* after that `b`. Obligations still open at the end of the word reject. This is the shape of a runtime monitor with two timeouts.
- **T03. A quotient that needs a subset construction.** First find the set S of M1-states reachable by words of L(M2) (reachability in a product). Then the answer is M1 started in *any* state of S, which has to be determinized over subsets of M1's states and minimized. The generator guarantees that S is neither one state nor all of them, so neither shortcut works.
- **T04. The same language read backwards.** Reading digits least significant first, the obvious DFA tracks (value so far mod 7, current power of 3 mod 7, parity of 2s): 84 states, correct, and far from minimal. The 14-state DFA needs one insight: track the residue the *remaining* digits must contribute. Digit d turns s into (s − d)·5 mod 7 (5 is the inverse of 3), and the word is accepted at s = 0 with even parity. The obvious answer scores 0.5.
- **T05. A one-character regex edit.** `X*` vs `X?` before a tail that can re-absorb extra copies of `X`. The two expressions agree on every word shorter than 16 letters, and exactly one word of length 16 tells them apart. Testing short words, the usual way to "check" a regex change, finds nothing. The pair was chosen by a seeded search (`scripts/search_t05_pairs.py`) over this family of one-character quantifier edits, keeping a pair whose shortest witness is long. That is deliberate: the edits that matter in a rule review are exactly the ones that short tests miss.
- **T06. Determinization by hand.** The ε-closure of every subset must be right (the start state is the closure of q0, not q0), 17 subsets are reachable (the empty set is not one of them, so no trap state is needed), and the one pair of equivalent subsets must be found and merged. One wrong closure yields a plausible DFA that is wrong.
- **T07. Parity at every level of nesting.** The language is not regular. Each run of children must carry the parity of its `[`-groups; `(`-groups and the word itself need an even count, while `[`-groups may only contain `[`-groups. In Chomsky normal form, every empty-content case (`()`, `[]`, an empty run of children) must be expanded by hand without ε- or unit productions.
- **T08. Counting across a split block.** Each leading `a` is worth 2, each trailing `a` 1, each `b` costs 3, so the `b`-block must be split between the two `a`-blocks, and one or two `b`'s are shared. The split depends on i mod 3: three cases, each of which must survive the CNF conversion.

### Calibration: why these are the second version of the tasks

A first version (v1) of the same eight task families was piloted on 2026-10-31 with paid and free API models and with ChatGPT's free web app (`pilot_v1/results/summary.md`). The API models passed almost every v1 task they reached; the only failures were Task 08 truncations and ChatGPT with Think off. An eval of what AI cannot do yet needs headroom, so every instance was replaced by a harder one in the same family, with the same answer format and grader. The difficulty comes from structure (interacting deadlines, a reversed digit order whose obvious DFA is 6 times too big, a determinization step, counting inside a grammar), not only size. v1 and its transcripts are kept at git tag `pilot-v1` (`git checkout pilot-v1 && python run_eval.py --regrade transcripts/` reproduces every pilot grade). The current code refuses to grade a transcript whose prompt differs from the current task, so no v1 answer is counted here.

## How grading works

Scores: **1.0** correct (and minimal / shortest where required), **0.5** right language but too many states (DFA tasks) or a distinguishing but non-shortest witness (T05), **0** otherwise. Pass (for pass@k and pass^k) means score 1.0. Only the final JSON block is graded; state names, state order and the reasoning before the answer are ignored. A DFA with missing transitions scores 0 (`INCOMPLETE_DFA`) even if a trap state would make it right, because every prompt asks for a *complete* DFA and says that the trap state counts. A complete DFA with the right language but extra states gets 0.5, because it is a correct machine that is only larger than necessary. Failure codes and descriptions are in `graders/failure_codes.py`; each failure stores a shortest counterexample word when one exists.

| Tasks | Guarantee |
|---|---|
| 01–04, 06 | **Exact.** Equivalence and minimality are decided, not sampled. |
| 05 | **Exact.** The true minimum length is computed by BFS on the product of the two minimal DFAs. |
| 07–08 | **Exact up to length N only.** CFG equivalence is undecidable in general. A pass means the grammar is in CNF, agrees with the language on every word of length ≤ N, and generates an infinite language. `tests/test_graders.py::test_bounded_guarantee_is_honest` shows an error beyond N that is *not* caught. |

The CFG check enumerates, per nonterminal, every string it derives up to the length where it could still matter, and tests each new string inside a fixed shortest context (`automata/cfg.py::check_upto`). It reports the overall shortest word on which the grammar is wrong: a missing word if one is shorter than the shortest wrongly generated word, otherwise the wrongly generated word. So a grammar coded `UNDERGENERATES` may also overgenerate, and the other way round (ChatGPT's Task 08 trial 1 does both, with Think off and with Think on).

N is 16 for T07 (13,778 words of length 16 alone) and 36 for T08 (92 words up to that length); grading a grammar still takes well under a second.

**What the bound allows.** A grammar that is right on every word up to N and wrong only beyond N passes. The infinite-language check rules out a plain finite list of the words up to N, but not a list plus an infinite junk branch whose words are all longer than N; an independent review built such a 1,114-production grammar for T08 and it scored 1.0 (`docs/OPEN_QUESTIONS.md` #51). Closing this would need a size limit in the prompt, and the prompts are frozen. None of the grammars that passed here does anything like this: they have 17 to 41 productions, and the review checked each of them with its own code up to length 18 (T07) and 60 (T08).

## How the grader was validated

- **References:** every reference answer scores 1.0 and is minimal (`tests/test_graders.py`, `scripts/verify_specs.py`).
- **Mutants:** flipped accepting states, redirected and deleted transitions, duplicate and unreachable states, swapped behaviours, dropped trap states, invalid DFAs, the obvious-but-wrong T05 witness, longer witnesses, off-alphabet witnesses, every dropped production, overgenerating and non-CNF productions, and a finite "list every word up to N" grammar. Each one gets its expected failure code.
- **Brute force:** grader verdicts agree with exhaustive enumeration on hundreds of random small DFAs, regex pairs and mutated grammars (`tests/test_bruteforce_crosscheck.py`).
- **Independent oracles:** three regex matchers (automaton, AST matcher, Python `re`) agree; subset construction agrees with direct NFA simulation; minimization agrees with a brute-force Myhill-Nerode count.
- **Prompt/grader consistency:** every example in every prompt is checked against the reference (`tests/test_tasks_wellformed.py`).
- **An independent review script:** `python scripts/review_checks.py` (about 15 s) re-implements every language, automaton and grammar with the standard library only. It checks each reference exactly against its own construction, compares the graders with its own scoring on 204 answers (the references and mutants of them), and re-scores every stored model grade. It found one wrong sentence in this README (about Task 06's subsets, now fixed) and no grading error.
- **Every model grade re-checked outside the graders.** Each of the 54 graded answers of the 2026-11-01 runs was run on every word up to length 8–13 and compared with a direct reading of its task's definition (T03 by brute force over prefixes, T06 by simulating the ε-NFA, T05 with Python `re`, T07/T08 with CYK). Each stored counterexample was confirmed, and each passing DFA was confirmed to have the minimal number of states. All 54 agreed with the grader: no false pass and no false fail was found. The 18 truncated and 3 API-error transcripts were confirmed to contain no complete answer. `scripts/review_checks.py` also re-scores every stored grade with its own code (exact for the DFAs and T05, up to length 14 for T07 and 36 for T08); after the last chat-app import (2026-11-09) it re-scored all 118 graded answers, and all 118 agree. It also confirms that no chat-app reply was saved under two tasks.

## Results

Task set v2, trials run on 2026-10-31 and 2026-11-01 (ChatGPT with Think on: 2026-11-02; Gemini: 2026-11-05; Claude.ai: 2026-11-05 and 2026-11-09). A pass is a score of 1.0; pass@3 is the share of tasks solved in at least one of 3 trials, pass^3 the share solved in all 3.

| Model | Valid trials | Pass rate | pass@3 | pass^3 | Mean score | Mean score, trial 1 / 2 / 3 | Truncated | API errors (excluded) | Cost of the full run |
|---|---|---|---|---|---|---|---|---|---|
| `nemotron-3-ultra-free` | 24 | 67% | 88% | 38% | 0.69 | 0.69 / 0.50 / 0.88 | 5 | 0 | $0.00 (free) |
| `dots-3-note-free` | 24 | 42% | 50% | 25% | 0.42 | 0.38 / 0.50 / 0.38 | 13 | 0 | $0.00 (free) |
| `chatgpt-free` (Think off) | 24 | 25% | 50% | 0% | 0.31 | 0.31 / 0.50 / 0.12 | 0 | 0 | $0.00 (free) |
| `chatgpt-think` (Think on) | 24 | 75% | 100% | 25% | 0.81 | 0.69 / 0.88 / 0.88 | 0 | 0 | $0.00 (free) |
| `gemini-free` (Fast mode) | 24 | 17% | 38% | 0% | 0.23 | 0.06 / 0.31 / 0.31 | 0 | 0 | $0.00 (free) |
| `claude-free` (2 trials per task: pass@2 and pass^2) | 16 | 88% | 100% | 75% | 0.88 | 0.75 / 1.00 | 0 | 0 | $0.00 (free) |
| `gemma-4-31b-free` | 0 | – | – | – | – | – | 0 | 3 | $0.00 (free) |

Passes per task (out of 3 trials each):

| Model | T01 | T02 | T03 | T04 | T05 | T06 | T07 | T08 |
|---|---|---|---|---|---|---|---|---|
| `nemotron-3-ultra-free` | 1 | 2 | 2 | 3 | 2 | 3 | 3 | 0 |
| `dots-3-note-free` | 0 | 0 | 2 | 3 | 0 | 3 | 2 | 0 |
| `chatgpt-free` | 0 | 0 | 1 | 2 | 0 | 0 | 2 | 1 |
| `chatgpt-think` | 2 | 3 | 3 | 2 | 2 | 2 | 2 | 2 |
| `gemini-free` | 0 | 0 | 1 | 0 | 0 | 1 | 2 | 0 |
| **All (of 15)** | **3** | **5** | **9** | **10** | **4** | **9** | **11** | **3** |
| `claude-free` (passes of 2, not in the totals) | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 1/2 | 2/2 | 2/2 |

The 66 failures by code: 18 `TRUNCATED` (all from the two open models), 22 `NOT_EQUIVALENT`, 10 `NON_MINIMAL_STATE_BLOAT` (score 0.5), 7 `WITNESS_NOT_DISTINGUISHING`, 5 `UNDERGENERATES`, 3 `OVERGENERATES`, 1 `CNF_VIOLATION`. No answer was a parse error or an incomplete DFA. Claude's two misses (1 `NOT_EQUIVALENT`, 1 `WITNESS_NOT_DISTINGUISHING`) are not in these counts.

The full tables, including every failed trial in words, are in [`results/summary.md`](results/summary.md) (generated by `scripts/report.py`; regenerate with `python run_eval.py --regrade transcripts/`).

**Models and settings.** Free routes only; the author had no budget for paid API calls.
- `nemotron-3-ultra-free`: `nvidia/nemotron-3-ultra-550b-a55b:free` on OpenRouter (NVIDIA, 550B parameters, 55B active), temperature 0, reasoning effort high, `max_tokens` 64,000.
- `dots-3-note-free`: `dots-studio/dots-3-note-preview:free` (280B, 16B active), same settings.
- `gemma-4-31b-free`: `google/gemma-4-31b-it:free`, `max_tokens` 32,000. Its free provider answered HTTP 429 to every call on both days, so it has no valid trial (listed as API errors, excluded from every rate).
- `chatgpt-free`: ChatGPT's free web app on 2026-11-01, default model (the app showed no model name), Think off, code/search/file tools and memory off, a brand-new chat per trial. The system prompt was pasted together with the task, and the reply was pasted back unedited (`manual/chatgpt-free/`). Temperature and model version are whatever the app used, so these rows can be re-graded but not re-run.
- `chatgpt-think`: the same app on 2026-11-02 with Think on (the app showed a "Thinking" label but no model version), otherwise the same setup (`manual/chatgpt-think/`). Each reply was copied with the copy button of its JSON code block, so any text ChatGPT wrote around the block was not saved; only that block is graded in any case (`docs/OPEN_QUESTIONS.md` #54). The app does not show token use, so a truncation cannot be seen; every one of the 24 chats ended with an answer.
- `gemini-free`: Gemini's free web app on 2026-11-05 in its default Fast mode (no model name shown, no thinking mode selected), otherwise the same setup (`manual/gemini-free/`). This row shows that default mode, not the best Gemini can do. Each saved reply is one bare JSON block, so any text around it was not saved. Task 07 trial 3 was collected twice: the first save was a copy from the wrong chat, cleared before anything was graded (`docs/OPEN_QUESTIONS.md` #57).
- `claude-free`: Claude.ai's free plan (the app showed "sonnet 5.5 medium"), with extended thinking off and code execution, Artifacts, web search and memory off (`manual/claude-free/`). Trials 1 and 2 only: 9 replies on 2026-11-05, when the free plan's limit was reached, and 7 on 2026-11-09. Trial 3 was skipped for lack of time before the deadline. Its pass@2 and pass^2 are not comparable with the other rows' pass@3 and pass^3, because "right every time" is easier over two trials than over three. The app does not explain "medium", so how much reasoning happens with thinking off is not visible.

Every transcript records the model id, settings, date, token usage, latency and cost. "Truncated" means the model used its whole output budget (`finish_reason = length`); it counts as a failure and is reported separately, and it is decided before parsing, so a cut-off reply scores 0 even if it already contained an answer. None of the truncated replies here did: most have no visible text at all, and the rest are cut off inside their working or their JSON. API errors are never counted as model failures.

### Per-task notes (with transcripts)

Each note names the failure the grader found; the "first fault" statements come from `python scripts/explain_failures.py`, which names the first wrong table entry on the counterexample.

"ChatGPT, Think off" is `chatgpt-free`; "ChatGPT, Think on" is `chatgpt-think`.

- **T01 (3 of 15; the hardest DFA task).** Nemotron's trial 3 and ChatGPT's (Think on) trials 1 and 2 are right.
  - All three Gemini answers (31 to 46 states) are wrong and break examples printed in their prompts. Its [trial 1](transcripts/gemini-free/task_01/trial_1.json) sends `1101` to the trap state as if it were `0101`.
  - ChatGPT's (Think on) [trial 3](transcripts/chatgpt-think/task_01/trial_3.json) is the right 21-state DFA plus 3 unreachable states left over from its construction. The prompt says every listed state counts, so 24 states score 0.5.
  - ChatGPT's (Think off) [trial 1](transcripts/chatgpt-free/task_01/trial_1.json) has the right language with 28 states instead of 21: 7 of its states duplicate others.
  - ChatGPT's (Think off) [trial 2](transcripts/chatgpt-free/task_01/trial_2.json) and [trial 3](transcripts/chatgpt-free/task_01/trial_3.json) accept `100` and `001`, words with only two 0s. Each breaks 4 or 5 of the 8 examples printed in its prompt.
  - Nemotron's [trial 2](transcripts/nemotron-3-ultra-free/task_01/trial_2.json) (24 states) mishandles the self-overlap of `0101`: after `100`, a `1` sends it to the trap state as if `1001` contained the pattern. Its shortest error is `100100`; 3 of its 48 transitions are wrong.
  - Dots ran out of budget all three times.
- **T02 (5 of 15).** ChatGPT (Think on) is right 3 times out of 3, Nemotron in trials 2 and 3.
  - All three Gemini answers are wrong. Its [trial 3](transcripts/gemini-free/task_02/trial_3.json) has one wrong transition out of 72 and accepts `abbbcac`.
  - Two answers have the right language and one state too many (17 for 16): ChatGPT's (Think off) [trial 1](transcripts/chatgpt-free/task_02/trial_1.json) has two identical dead states, and Nemotron's [trial 1](transcripts/nemotron-3-ultra-free/task_02/trial_1.json) two identical rows.
  - ChatGPT's (Think off) [trial 2](transcripts/chatgpt-free/task_02/trial_2.json) forgets that an `a` directly after a `b` is exempt from its own rule. It rejects `bcba`, and the prompt's own example `abcba`.
  - ChatGPT's (Think off) [trial 3](transcripts/chatgpt-free/task_02/trial_3.json) lets a `b`'s deadline expire without rejecting, and accepts `bcc`.
  - Dots ran out of budget all three times.
- **T03 (9 of 15).** Every model is right at least once, and ChatGPT (Think on) 3 times out of 3. The two wrong open-model answers both have 12 states, one fewer than the minimum, so they cannot be right:
  - Dots' [trial 3](transcripts/dots-3-note-free/task_03/trial_3.json) has a single wrong transition out of 24 and accepts `aabb`.
  - Nemotron's [trial 2](transcripts/nemotron-3-ultra-free/task_03/trial_2.json) has 4 wrong transitions and accepts `ababba`.
  - ChatGPT's (Think off) [trial 3](transcripts/chatgpt-free/task_03/trial_3.json) rejects the one-letter word `a`.
  - Gemini's [trial 1](transcripts/gemini-free/task_03/trial_1.json) also has 12 states and accepts `aabb`, the same first error as Dots. Its [trial 2](transcripts/gemini-free/task_03/trial_2.json) has the right language with 14 states.
- **T04 (10 of 15).** The task built around one insight was solved far more often than the plain-bookkeeping tasks. Every miss is an 84-state machine built the obvious way (power of 3 mod 7, value mod 7, parity of 2s): the first trials of ChatGPT with Think off ([trial 1](transcripts/chatgpt-free/task_04/trial_1.json)) and with Think on ([trial 1](transcripts/chatgpt-think/task_04/trial_1.json)), and all three Gemini trials. Each of the 14 true states appears in that machine 6 times. Done correctly it scores 0.5; Gemini's [trial 2](transcripts/gemini-free/task_04/trial_2.json) gets 138 of its 252 transitions wrong and scores 0. Every other trial found the 14-state DFA.
- **T05 (4 of 15).** Nemotron's trials 1 and 3 and ChatGPT's (Think on) trials 1 and 3 found the unique 16-letter witness `ababaababaababaa`.
  - Nemotron's [trial 2](transcripts/nemotron-3-ultra-free/task_05/trial_2.json) wrote the same word, followed by a question mark, just before the budget ran out.
  - ChatGPT's (Think on) [trial 2](transcripts/chatgpt-think/task_05/trial_2.json) answered the 14-letter `ababaababababa`. ChatGPT (Think off) answered `ε` twice and a 14-letter word once. None of these four answers is in either language.
  - Gemini fell into the trap the pair was built around. Its answers `ababababababaa` (trials 1 and 3) and `ababaababababaa` ([trial 2](transcripts/gemini-free/task_05/trial_2.json)) are matched by both regexes, so they distinguish nothing.
  - Dots ran out of budget all three times.
- **T06 (9 of 15).** Both open models are right 3 times out of 3, ChatGPT with Think on twice, Gemini once, and ChatGPT with Think off never.
  - Gemini's [trial 1](transcripts/gemini-free/task_06/trial_1.json) (13 states) and [trial 3](transcripts/gemini-free/task_06/trial_3.json) (14 states) each have exactly one wrong transition.
  - ChatGPT's (Think on) [trial 3](transcripts/chatgpt-think/task_06/trial_3.json) is the right 16-state DFA plus 2 unreachable states, so it scores 0.5, like T01 above.
  - ChatGPT's (Think off) [trial 2](transcripts/chatgpt-free/task_06/trial_2.json) and [trial 3](transcripts/chatgpt-free/task_06/trial_3.json) are the closest misses in the whole run. Each has 15 states, one fewer than the minimum, and exactly one wrong entry in a 30-entry table. Each agrees with the correct DFA on 2,041 of the 2,047 words up to length 10. The first error is the 9-letter word `aabbabaab`.
- **T07 (11 of 15; the easiest).** Nemotron is right 3 times out of 3; Dots, both ChatGPT settings and Gemini twice each.
  - Gemini's [trial 1](transcripts/gemini-free/task_07/trial_1.json) drops the parity rule for `(`-groups but keeps it for the word: it generates `([])`, listed in its prompt as not in L. Each of the 243 wrong words it generates up to length 10 has a `(`-group with an odd number of `[`-children.
  - ChatGPT's (Think on) [trial 1](transcripts/chatgpt-think/task_07/trial_1.json) has two unit productions, `C → RBR` and `EC → RPAR`, which Chomsky normal form forbids. Its language is right: with the two rules replaced by `C → ]` and `EC → )`, the grader passes it (a diagnostic, not its score).
  - ChatGPT's (Think off) [trial 3](transcripts/chatgpt-free/task_07/trial_3.json) drops the parity rule for the word itself: it generates `[]` and `[[]]`, both listed in its prompt as not in L. Every one of the 109 wrong words it generates up to length 10 has an odd number of top-level `[`-groups.
  - Dots' trial 1 ran out of budget.
- **T08 (3 of 15; tied with T01 as the hardest).** ChatGPT's (Think off) trial 2, with 41 productions, and ChatGPT's (Think on) trials 2 and 3 are right. The two open models never produced a grammar: all 6 of their trials used the whole budget, and Nemotron's three are still working out the grammar where they stop ([trial 1](transcripts/nemotron-3-ultra-free/task_08/trial_1.json)).
  - ChatGPT's (Think on) [trial 1](transcripts/chatgpt-think/task_08/trial_1.json) gets the case of a last block of 1 or 2 `a`s wrong once the first block has 4 or more: it rounds the first block down to a multiple of 3. Up to length 36 it generates 12 words not in L (shortest `aaabbba`, which should be `aaaabbba`) and misses those 12 words of L.
  - ChatGPT's (Think off) [trial 1](transcripts/chatgpt-free/task_08/trial_1.json) misses all 25 words with i ≡ 0 (mod 3) up to length 36 (shortest: `aaabbbaaa`) and also generates 24 words that are not in L.
  - ChatGPT's (Think off) [trial 3](transcripts/chatgpt-free/task_08/trial_3.json) covers only the i ≡ 0 case. It cannot generate `aba`, the first example in its prompt, and generates 61 words that are not in L.
  - Gemini's three grammars have only 8 to 10 productions. Each gets just `aba` right out of the 92 words up to length 36, and each generates words not in L ([trial 1](transcripts/gemini-free/task_08/trial_1.json)).

**Claude.ai (2 trials per task, not in the counts above).** 14 of its 16 answers are exactly right: both trials of T01, T02, T03, T04, T07 and T08, including T08 grammars with 24 and 33 productions, and every task in trial 2. Its [T05 trial 1](transcripts/claude-free/task_05/trial_1.json) answered `ababaababababaa`, the same wrong word as Gemini's trial 2, which both regexes match. Its [T06 trial 1](transcripts/claude-free/task_06/trial_1.json) has 15 states and exactly one wrong transition. It is the same mistake as ChatGPT's (Think off) T06 trials 2 and 3: after `aabb`, an `a` loops back to the same state, so all three accept `aabbabaab`.

## Main failure mode and hot take

**What the results show** (each point is a count from `results/summary.md`):

1. **Bookkeeping breaks, not insight.**
   - T04 is built around one clever idea: track the residue the remaining digits still owe, which shrinks 84 obvious states to 14. It was solved in 10 of 15 trials, and every miss is an 84-state machine built the obvious way.
   - T01 and T08 need only routine steps, applied many times: a product of three simple conditions, and a grammar with three remainder cases. They were the hardest, each solved 3 times in 15 trials.
2. **With no thinking step, little checking.**
   - ChatGPT with Think off and Gemini in Fast mode answer at once. Of their 24 answers each, 18 and 20 are wrong or bloated. The same ChatGPT app with Think on, given the same prompts, misses 6 of 24.
   - Seven of the Think-off wrong answers and eleven of the Fast-mode ones are to tasks whose prompt lists example words. Six of the seven and nine of the eleven get at least one of those examples wrong, such as a Task 08 grammar that cannot derive `aba`, the first word listed.
   - Claude.ai does not fit this pattern: with extended thinking off it got 14 of 16 right. Its label says "medium", so thinking off may not mean no reasoning. The pattern holds for ChatGPT and Gemini, not for every chat app.
3. **With reasoning, open models run out of budget.**
   - In the 30 trials where the two open reasoning models gave an answer, they were exactly right 26 times.
   - In 18 of their 48 trials they used all 64,000 output tokens without giving an answer. That includes every one of their 6 attempts at Task 08.
4. **The best complete run is not reliable, and it slips on the last step.**
   - ChatGPT with Think on solved every task at least once, but all three times on only T02 and T03.
   - Four of its six misses got the language right and the required form wrong. Three DFAs have extra states: two are the minimal DFA plus unreachable leftovers, one is the 84-state obvious machine. One grammar is right except for two unit productions, which CNF forbids.
   - Only two of its misses are wrong in substance: a T05 witness in neither language, and a T08 grammar with one case off by one or two letters.
5. **Near misses are invisible to spot checks.** Seven wrong DFAs have a single wrong arrow each: ChatGPT's (Think off) T06 trials 2 and 3, Dots' T03 trial 3, Gemini's T02 trial 3 and T06 trials 1 and 3, and Claude's T06 trial 1. Three of these, from two vendors, make the same mistake and agree with the correct DFA on 99.7% of words up to length 10.

**Hot take.** These models know the constructions. What they cannot yet do without tools is carry one out reliably: the minimal DFAs here have 13 to 21 states and 26 to 48 transitions, and one wrong arrow is enough. Checking that bookkeeping by hand costs an open reasoning model tens of thousands of tokens, and skipping it gives answers that fail their own examples. The best complete run here did the checking and still finished the job three times out of three on only 2 of 8 tasks, often stumbling on the last, mechanical step (drop the unreachable states, remove the unit rules). Even the best result, Claude.ai at 14 of 16 over two trials, lost both misses to near misses of that kind: a witness that both regexes match, and one wrong arrow that 2,041 of the 2,047 words up to length 10 do not reveal. What this run does not measure, and is only a conjecture: most of these failures would disappear with a code interpreter, since every task is a short program. If so, an answer about a state machine produced without tools is a draft until a program has checked it.

## Reproducing

- **Offline (what a judge needs):** the Quick start above. `python run_eval.py --regrade transcripts/` re-parses and re-grades every saved transcript and rewrites `results/` from them (transcripts themselves change only with `--write`). It exits 1 if any grade differs from the stored one. `python scripts/explain_failures.py` prints, for every wrong DFA, the first faulty entry of its table on the counterexample.
- **Exact environment:** `pip install -r requirements-lock.txt` installs the exact version of every package used for the recorded runs (Python 3.13.7, Windows 11).
- **Instances are deterministic:** `python scripts/generate_instances.py --check` confirms that `tasks/` and `reference/` match the seeded generators.
- **Live, free models:** put `OPENROUTER_API_KEY=...` in `.env` (see `.env.example`) or set it as an environment variable, then
  `python run_eval.py --models models.free.yaml --trials 3 --max-cost 0 --concurrency 1 --max-attempts 2 --max-requests 45`.
  `--max-cost 0` refuses anything that is not a `:free` model. OpenRouter allows 50 free requests per day, and failed attempts count. Finished answers are cached, so the same command continues the next day. Guide: [docs/RUNNING_FOR_FREE.md](docs/RUNNING_FOR_FREE.md).
- **Live, chat apps:** `python run_eval.py --new-manual NAME --trials 3` writes the exact text to paste and empty reply files; `python run_eval.py --import-manual manual/` grades them with the same code.
- **Live, paid models:** fill verified ids in `models.yaml`, then `python run_eval.py --models models.yaml --trials 3 --dry-run` (free estimate) and `--max-cost 5`. A live run refuses to start without `--max-cost` and stops if OpenRouter reports the account is out of credits.
- **Results vary run to run** (sampling, provider changes); the saved transcripts are the evidence, and the offline re-grade reproduces every number in this README exactly.
- **The v1 pilot:** in the git repository (the zip has no git history), `git checkout pilot-v1`, then `python run_eval.py --regrade transcripts/` (0 grades differ), then `git checkout main`. The zip contains the pilot's transcripts and summary in `pilot_v1/` for reading.

**Cost and runtime.** Every model call was free: $0.00 in total (OpenRouter `:free` endpoints and free chat apps). The two open models produced 2.18 million output tokens: 905,574 for Nemotron and 1,274,460 for Dots. Summed API latency was 26,587 s for Nemotron (7.4 h, about 18 minutes per trial) and 13,353 s for Dots (3.7 h, about 9 minutes per trial). Because of the 50-requests-per-day free limit, the runs were spread over two days. Chat-app replies were pasted by hand and not timed. Re-checking everything offline takes about a minute for the tests, about 10 s for `verify_specs.py` and about 2 s for the regrade.

## Spec-validation case study: the original Task 08

The first draft of Task 08, `{aⁱbʲaᵏ : i+k = 2j, i > k ≥ 1}`, is **not context-free**, so no reference grammar can exist. The requirement that every task have a reference solution exposed this. `scripts/check_task08_noncf.py` contains the pumping-lemma proof and an exhaustive check of every decomposition for N = 2..8.

## Limitations

- **Frontier coverage is thin.** With no budget for paid APIs, the frontier products are free chat apps collected by hand: ChatGPT with Think off and with Think on, Gemini in its default Fast mode only, and Claude.ai with 2 trials per task. ChatGPT and Gemini show no model version, so ChatGPT's two settings need not even be the same model. DeepSeek with DeepThink on was started and dropped because it took too long; its 2 replies were deleted ungraded (`docs/OPEN_QUESTIONS.md` #56). The two API models are large open-weight reasoning models on free endpoints.
- **Chat-app runs are not controlled.** Model version, temperature and reasoning budget are whatever the app used, and token use is not shown, so a chat-app reply cannot be marked truncated the way an API reply is. The repository, including its reference answers, was already public when the later chat-app runs took place. Web search was off, but tool use that an app hides cannot be detected.
- **Who built this.** Claude Code, an Anthropic product, drafted the tasks, graders and this analysis, and a Claude model is among those tested and scored best. Grades come from algorithms and can be re-run offline, so scoring cannot favour a model; the choice and wording of the tasks, frozen before any Claude chat-app run, is the remaining place for bias. A paid run of current frontier models with high reasoning effort is the obvious next step; the harness supports it (`models.yaml`).
- **Small samples.** 3 trials per task and model, one instance per task. Pass rates have wide uncertainty; the per-trial means and pass^k show how much they move.
- **A fixed output budget.** API models get 64,000 output tokens (`docs/OPEN_QUESTIONS.md` #49). 18 of the two open models' 22 failures are truncations. Their pass rates therefore measure "right within 64,000 tokens", and a larger budget could turn some truncations into answers, right or wrong. Truncations are reported separately for this reason.
- **Gemma has no data.** Its free provider refused every call (HTTP 429), so only two open models were measured through the API.
- **Bounded CFG grading.** Tasks 07–08 are exact up to length N, not in general (see above).
- **No tool ablation.** The claim "tools would close the gap" is plausible (each task is a short program) but was not measured here.

## Provenance

- **Data:** none. Every task is synthetic, built from classical automata theory; T03 and T06 instances come from seeded generators (`reference/build.py`, seeds 3126 and 7577). No external dataset, benchmark item or licensed material is used.
- **Built during the hackathon:** all code, tasks, reference answers, graders, tests, runs and docs (first commit 2026-10-30, 21:21 IST, after the challenge opened). The starting point was the author's own idea document for the eight task families; its errors, found and corrected while building, are listed in `docs/PROJECT_GUIDE.md` §2 (for example, its original Task 08 is not context-free).
- **Used, not written here:** textbook algorithms (subset construction, Moore/Hopcroft minimization, Thompson's construction, CYK) and the Python packages in `requirements.txt`.
- **Prior art** (searched 2026-11-01). Closest related work found, none of which this eval copies or adapts:
  - Shelat, Raval, Roy and Gaur, [*Beyond Memorization: Testing LLM Reasoning on Unseen Theory of Computation Tasks*](https://arxiv.org/abs/2601.13392) (arXiv, January 2026). Models construct DFAs from language descriptions, and accuracy drops sharply on unseen problems. This eval shares the "can it build a correct DFA" question; it adds exact minimality grading (0.5 for a correct but bloated DFA), tasks that compose operations (products, quotients, ε-NFA determinization), regex witnesses and CNF grammars, and a stored shortest counterexample for every failure.
  - Jin, Hahn and Han, [*RegexPSPACE*](https://arxiv.org/abs/2510.09227) (arXiv, October 2025): regex equivalence decision and regex minimization. Task 05 here asks for a constructive answer instead, the shortest word on which two regexes differ, graded exactly.
  - Grammar inference from examples, e.g. [HyGenar](https://arxiv.org/abs/2505.16978) (2025), and formal-syntax synthesis frameworks such as [∀uto∃val](https://arxiv.org/abs/2403.18327). Tasks 07–08 instead give a precise language definition and grade a CNF grammar against it exactly up to N.

## AI use

See [docs/AI_USE.md](docs/AI_USE.md). The instructions and prompts used to drive Claude Code (`CLAUDE.md`, `docs/KICKOFF_PROMPTS.md`) were removed from the repository after submission and are in the git tag `submission`. In short:
- **Claude Code** drafted the code, tests, task prompts, reference constructions and docs. At the author's request it also drafted this README's analysis sections (who relies on this, why each task is hard, per-task notes, failure analysis and hot take, provenance) and the task rationale texts.
- **How it was checked:** every number is recomputed by scripts, every grader is tested against references, mutants and brute force, and every model grade was re-checked by an independent script. The author read the failing transcripts.
- **Review:** at the author's request, Claude Code re-did every row of `docs/REVIEW_LOG.md` (each task, reference and grader) with an independent script, `python scripts/review_checks.py`, and ticked those rows as machine checks. The author then checked all 29 rows by hand and ticked them in a separate column (2026-11-01). The log keeps the two kinds of check apart.

## Repository hygiene

- `git config core.hooksPath .githooks` enables a pre-commit hook (`scripts/check_secrets.py`) that blocks API keys, `.env` files, videos and files over 5 MB.

License: MIT.
