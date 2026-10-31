# Human review log

One row per task, reference solution, grader and generator. Claude Code adds rows; **only
the author ticks them**, after personally verifying the item by hand (rubric: "human
expertise & review", 10 pts). Write *how* you checked it, e.g. "drew the 21-state DFA,
matched the script's state classes".

Rows are for task set **v2** (the current `tasks/`). The v1 rows were never ticked; v1 is
kept at git tag `pilot-v1` and in `pilot_v1/`.

| Item | What was produced | How the author verified it by hand | Date | ✔ |
|---|---|---|---|---|
| Decision: v1 → v2 | `pilot_v1/results/summary.md`, `docs/OPEN_QUESTIONS.md` #35, #39 | e.g. read the pilot table and two passing transcripts; can say in one sentence why each task was made harder | | ☐ |
| T01 task + prompt | `#0 ≡ 1 (mod 3)`, no `0101`, third-to-last is 1 | e.g. check the 4 in / 4 out examples by hand | | ☐ |
| T01 reference | 21-state minimal DFA (naive product 30) | e.g. explain the fallback after `010`, and why the counter copies of the trap merge | | ☐ |
| T02 task + prompt | rule A (window 4) + rule B (window 3), 6 in / 5 out examples | e.g. check `abcba` (in) and `abca` (out) position by position | | ☐ |
| T02 reference | 16-state minimal DFA (earliest A-deadline × earliest B-deadline × after-b) | e.g. trace `bacba` through `reference.build.t02_construction` | | ☐ |
| T03 task + instance | left quotient, seeded M1 (5) and M2 (3), seed 3126 | e.g. find the 3 states of S by hand (words of M2 run through M1) | | ☐ |
| T03 reference | 13-state minimal DFA from 14 subsets | e.g. compute the first few subsets from S on paper | | ☐ |
| T04 task + prompt | base 3, least significant digit first, ≡ 4 (mod 7), even 2s | e.g. evaluate `122` and `221` by hand | | ☐ |
| T04 reference | 14 states: "residue the rest must have", s → (s − d)·5 mod 7 | e.g. explain why 84 obvious states collapse to 14 (this is the hot-take candidate) | | ☐ |
| T05 task + regex pair | `(ab)*a+b(ab)+a+(ba)+(ba)+a` vs `(ab)?…` | e.g. check that `ababababababaa` is matched by both | | ☐ |
| T05 reference | unique shortest witness `ababaababaababaa` (16) | e.g. redo the a-run-sequence proof in `reference/build.py` without notes | | ☐ |
| T06 task + instance | seeded 7-state ε-NFA, seed 7577 | e.g. compute the start state's ε-closure and its a/b successors | | ☐ |
| T06 reference | 16-state minimal DFA from 17 subsets | e.g. find the one pair of subsets that merges | | ☐ |
| T07 task + prompt | parity Dyck variant, unbounded depth, N = 16 | e.g. check the 5 in / 6 out examples against rules (1)-(4) | | ☐ |
| T07 reference | 21-rule CNF grammar (P, B, Bs, Ev, Od) | e.g. derive `([][])` and `[[][]][]`; explain why `[[]]` is impossible | | ☐ |
| T08 task + prompt | `aⁱbʲaᵏ, 2i + k = 3j`, N = 36 | e.g. check every example's equation | | ☐ |
| T08 reference | three-case grammar by i mod 3, 30 CNF rules | e.g. derive `aba`, `aabbaa`, `aaabbbaaa` and say which case each uses | | ☐ |
| Original T08 non-CF proof | `scripts/check_task08_noncf.py` | be able to give the pumping argument without notes | | ☐ |
| DFA grader | `graders/dfa_grader.py` + mutants | | | ☐ |
| Witness grader | `graders/witness_grader.py` + mutants | | | ☐ |
| CFG grader (bounded) | `graders/cfg_grader.py`, `automata/cfg.py::check_upto` | e.g. explain the "wrapped enumeration" argument and why it is exact up to N | | ☐ |
| Left quotient engine | `automata/nfa.py::left_quotient` (+ brute-force tests) | e.g. compare with `right_quotient`: which one needs subsets, and why | | ☐ |
| Harness | `harness/`, `run_eval.py` (fake-client tests), stale-transcript guard | e.g. run `--regrade pilot_v1/transcripts` and read the refusal | | ☐ |
| Chat-app import | `harness/manual.py`; paste one reply you know is right and one you know is wrong, import, and check the grades | | | ☐ |
