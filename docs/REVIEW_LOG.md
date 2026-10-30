# Human review log

One row per task, reference solution, grader and generator. Claude Code adds rows; **only
the author ticks them**, after personally verifying the item by hand (rubric: "human
expertise & review", 10 pts). Write *how* you checked it, e.g. "drew the 10-state DFA,
matched the script's state classes".

| Item | What was produced | How the author verified it by hand | Date | ✔ |
|---|---|---|---|---|
| T01 task + prompt | `tasks/task_01_product_dfa.json` | | | ☐ |
| T01 reference | 10-state minimal DFA (`reference/task_01.ref.json`) | e.g. draw it; explain which 4 product states collapse (14 → 10) | | ☐ |
| T02 task + prompt | formal obligation definition, W = 3, 11 examples | | | ☐ |
| T02 reference | 6-state minimal DFA; size W+3 | e.g. derive the W+3 states by hand | | ☐ |
| T03 task + instance | seeded M1, M2 (seed 3788) | | | ☐ |
| T03 reference | 4-state minimal quotient DFA | e.g. compute the new accepting set of M1 by hand | | ☐ |
| T04 task + prompt | base-3 mod 7 + parity of 2s | | | ☐ |
| T04 reference | 14-state DFA (7 residues × parity) | e.g. check a few transitions r' = (3r+d) mod 7 | | ☐ |
| T05 task + regex pair | `(ba)*b+a(ba)+a` vs `(ba)?b+a(ba)+a` | | | ☐ |
| T05 reference | witness `bababbabaa` (unique shortest) | e.g. redo the hand proof in `reference/build.py` | | ☐ |
| T06 task + instance | seeded 5-state ε-NFA (seed 8618) | | | ☐ |
| T06 reference | 7-state minimal DFA from 11 subsets | e.g. run the subset construction on paper | | ☐ |
| T07 task + prompt | bounded two-bracket Dyck variant, N = 16 | | | ☐ |
| T07 reference | depth-indexed CNF grammar | e.g. derive `(([]))` and explain why `[()]` is impossible | | ☐ |
| T08 task + prompt | `aⁱbʲaᵏ, i+k = 2j`, N = 30 | | | ☐ |
| T08 reference | CNF grammar (parity split) | e.g. derive `aaabba` and `abbaaa` | | ☐ |
| Original T08 non-CF proof | `scripts/check_task08_noncf.py` | be able to give the pumping argument without notes | | ☐ |
| DFA grader | `graders/dfa_grader.py` + mutants | | | ☐ |
| Witness grader | `graders/witness_grader.py` + mutants | | | ☐ |
| CFG grader (bounded) | `graders/cfg_grader.py`, `automata/cfg.py::check_upto` | e.g. explain the "wrapped enumeration" argument and why it is exact up to N | | ☐ |
| Harness | `harness/`, `run_eval.py` (fake-client tests) | | | ☐ |
