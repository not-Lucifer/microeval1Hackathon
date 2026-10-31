"""Reproducible search that found the Task 05 regex pair (seeded; prints candidates).

Family: R1 = X* Y and R2 = X? Y (or X+ Y vs X Y), where X is a short block and Y a random
concatenation of small atoms. Kept: pairs whose shortest distinguishing word has length
--min-len..--max-len AND whose "obvious" witness (two copies of X followed by Y's shortest
word) does NOT distinguish them, so a solver must reason about re-parsing rather than
pattern-match. Each line also gives the number of shortest witnesses (1 = unique).

The chosen pair is then proved by hand (see reference/build.py, T05_PAIR). Task set v2
uses the defaults below (it prints the length-16 pair and the length-14 alternative).

    python scripts/search_t05_pairs.py [--trials 60000] [--seed 23] [--min-len 14]
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automata.dfa import accepts, all_words, equivalent, shortest_accepted  # noqa: E402
from automata.regex import to_min_dfa  # noqa: E402

ALPHABET = ["a", "b"]
ATOMS = ["a", "b", "(a|b)", "(ab|b)", "(bb|a)", "(ba|a)", "(ab|ba)", "a?", "b?", "b+", "a+",
         "(ab)*", "(ba)+", "(aa|b)", "(ab)+", "(ba)*", "(aab|b)", "(abb|a)"]
BLOCKS = ["ab", "ba", "aab", "abb", "bab", "aba"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=60000)
    ap.add_argument("--seed", type=int, default=23)
    ap.add_argument("--max-regex-len", type=int, default=26)
    ap.add_argument("--min-len", type=int, default=14)
    ap.add_argument("--max-len", type=int, default=16)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    seen = set()
    for _ in range(args.trials):
        x = rng.choice(BLOCKS)
        y = "".join(rng.choice(ATOMS) for _ in range(rng.randint(4, 8)))
        group = f"({x})" if len(x) > 1 else x
        for op1, op2 in (("*", "?"), ("+", "")):
            r1, r2 = group + op1 + y, group + op2 + y
            if (r1, r2) in seen or len(r1) > args.max_regex_len:
                continue
            seen.add((r1, r2))
            d1, d2 = to_min_dfa(r1, ALPHABET), to_min_dfa(r2, ALPHABET)
            same, w = equivalent(d1, d2)
            if same or not args.min_len <= len(w) <= args.max_len:
                continue
            naive = shortest_accepted(to_min_dfa(x, ALPHABET)) * 2 + shortest_accepted(to_min_dfa(y, ALPHABET))
            if accepts(d1, naive) == accepts(d2, naive):
                n_shortest = sum(accepts(d1, u) != accepts(d2, u) for u in all_words(ALPHABET, len(w)) if len(u) == len(w))
                print(f"{len(w)}\t{n_shortest}\t{r1}\t{r2}\tshortest={w}\tnaive={naive}")


if __name__ == "__main__":
    main()
