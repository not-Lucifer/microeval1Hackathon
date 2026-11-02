# Video script (≤ 5:00)

Drafted by Claude Code at the author's request (see `docs/AI_USE.md`). About 620 words of
narration at ~140 words per minute ≈ 4:24, which leaves time for pauses and screen changes. An AI voice is allowed by the rules. Every number
below is copied from `results/summary.md`, `scripts/explain_failures.py` or a transcript;
re-check them against those files right before recording.

**Before recording:** open VS Code on the repo with a large font (Ctrl + =), a terminal with the
venv active, and these files in tabs: `README.md`, `manual/prompts/task_04.txt`,
`manual/chatgpt-free/task_04/trial_1.txt`, `results/summary.md`.
**Recording:** Windows Game Bar (Win + Alt + R) or OBS. **Hosting:** YouTube "Unlisted" or Google
Drive with "Anyone with the link can view"; open the link in a private window to check that it
plays with sound and asks for no permission.

---

## 1. The problem (0:00 – 0:40)
**Screen:** `README.md`, top of the page.

> People ask chat assistants to write small state machines all the time: a lexer rule, a
> protocol monitor with timeouts, a regex for a firewall, a grammar for a config file. The
> assistant answers in one go, without running code, and we check it by trying a few inputs.
> This eval asks whether that answer is actually right. Eight tasks: build a minimal DFA,
> determinize an epsilon-NFA, find the shortest word where two regexes differ, and write
> grammars in Chomsky normal form. Every answer is graded by exact algorithms. There is no LLM
> judge.

## 2. One task, end to end: Task 04 (0:40 – 1:50)
**Screen:** `manual/prompts/task_04.txt` (scroll to the language definition and the grading rules),
then `manual/chatgpt-free/task_04/trial_1.txt` (scroll fast through the 84 states), then the
row for task_04 trial 1 in the "Every failed trial" table of `results/summary.md`.

> Task 04: base-3 numbers read least significant digit first. Accept a number if it is 4 mod 7
> and has an even number of 2s. The obvious machine remembers the value so far, the current
> power of 3, and the parity: 84 states. It is correct, but the minimal machine has only 14.
> The trick is to remember what the remaining digits still have to add up to. Here is
> ChatGPT's first answer: the obvious 84-state machine. The grader proves it accepts exactly
> the right language, and proves it is six times bigger than necessary: half credit. In two
> other fresh chats, ChatGPT did find the 14-state machine. The same model, the same question,
> different answers. With Think on, its first answer was the same 84-state machine.

## 3. A wrong answer that looks right: Task 06 (1:50 – 2:50)
**Screen:** terminal: `python scripts/explain_failures.py`; highlight the two task_06 trial 2 / 3 lines.

> Task 06: turn a seven-state epsilon-NFA into a minimal DFA. ChatGPT's answer in two separate
> chats had 15 states. That is one fewer than the true minimum, so it must be wrong somewhere,
> but where? On all words up to length 10 it agrees with the right answer 99.7 percent of the
> time. The first word it gets wrong has nine letters. This script walks the counterexample
> and finds the bug: one wrong arrow in a table of thirty. No reviewer trying short inputs
> would ever find it.

## 4. Results (2:50 – 3:50)
**Screen:** the first table of `results/summary.md`, then the per-task table.

> Ninety-six graded trials, all on free routes: 50 exactly right. The best was ChatGPT's free
> tier with Think on: it solved 18 of 24 and every task at least once, but only two tasks
> three times out of three. With Think off, the same app solved 6 of 24. Nemotron, the best
> open reasoning model, solved 16 of 24.
> Three things go wrong again and again. Models run out of budget: 18 of the 48 open-model
> trials used all 64,000 output tokens without an answer, including every attempt at the
> grammar in Task 08. Models skip the last step: correct machines with extra states, a correct
> grammar with two rules that normal form forbids. And models give wrong machines that
> contradict their own prompt.

## 5. Why you can trust the grader (3:50 – 4:20)
**Screen:** terminal: `pytest -q` (cut to the end), `python scripts/verify_specs.py` (last line),
`python run_eval.py --regrade transcripts/` (last two lines).

> Every reference answer scores 1.0. Dozens of hand-made wrong answers get the right failure
> code, and in 550 brute-force tests on random automata, regexes and broken grammars the grader
> agrees with exhaustive checking. Every model grade here was
> also re-checked by an independent script. The grammar tasks are exact only up to a stated
> length, because grammar equivalence is undecidable, and the README says so. A judge can
> re-grade every transcript offline in two seconds, with no API key.

## 6. Hot take (4:20 – 5:00)
**Screen:** the per-task table in the README "Results" section, then the "Every failed trial"
table in `results/summary.md`, last column.

> The surprise: the task built on a clever trick, Task 04, was the easiest, ten of twelve
> right. The hardest were plain bookkeeping, each solved three times in twelve. Without reasoning,
> six of ChatGPT's seven wrong answers on tasks with examples fail an example printed in
> their own prompt. One grammar cannot even produce "aba", the first one. With reasoning,
> the open models were right 26 of the 30 times they answered, but ran out of budget
> 18 times, and ChatGPT with Think on got only two of eight tasks right every time. The missing
> skill is not cleverness. It is reliable bookkeeping.
