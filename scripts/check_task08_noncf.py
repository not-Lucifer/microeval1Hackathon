"""Why the ORIGINAL Task 08 language is not context-free (so it had to be replaced).

    L' = { a^i b^j a^k : i + k = 2j and i > k >= 1 }

Pumping-lemma argument. Suppose L' were context-free with pumping length p. Take
s = a^(p+2) b^(p+1) a^p  (i = p+2, j = p+1, k = p: i + k = 2p+2 = 2j and i > k). Any split
s = u v w x y with |vwx| <= p and |vx| >= 1 must keep u v^t w x^t y in L' for every t >= 0.
vwx is too short to touch both a-blocks (the b-block has p+1 > p letters), so:
  * v or x mixes two letters -> pumping up leaves the form a*b*a*.
  * vwx inside one block -> pumping changes only i, only j or only k -> i + k != 2j.
  * v in the first a-block (alpha a's), x in the b-block (beta b's): i + k = 2j survives
    pumping only if alpha = 2*beta, beta >= 1; then t = 0 gives i' = p + 2 - 2*beta <= p = k,
    violating i > k.
  * v in the b-block (beta b's), x in the last a-block (gamma a's): needs gamma = 2*beta;
    then t = 2 gives k' = p + 2*beta >= p + 2 = i, violating i > k.
Every case fails, contradicting the lemma, so L' is not context-free and no CNF reference
grammar can exist. The strict inequality i > k is what breaks it (s sits at the boundary
i = k + 2, the smallest gap compatible with i + k being even).

This script confirms the case analysis by brute force: for N = 2..8 it tries EVERY
decomposition of a^(N+2) b^(N+1) a^N with |vwx| <= N, |vx| >= 1, and checks that some pump
exponent t in {0, 2} leaves L'.

    python scripts/check_task08_noncf.py   # exit 0 if every N fails the pumping property
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reference.build import t08_original_member  # noqa: E402


def pumpable_decompositions(s: str, p: int) -> list[tuple[int, int, int, int]]:
    """All (start of v, |v|, |w|, |x|) with |vwx| <= p, |vx| >= 1 such that pumping with
    t = 0 and t = 2 both stay inside L' (i.e. decompositions the argument fails to kill)."""
    survivors = []
    n = len(s)
    for start in range(n):
        for lv in range(p + 1):
            for lw in range(p + 1 - lv):
                for lx in range(p + 1 - lv - lw):
                    if lv + lx == 0 or start + lv + lw + lx > n:
                        continue
                    u = s[:start]
                    v = s[start : start + lv]
                    w = s[start + lv : start + lv + lw]
                    x = s[start + lv + lw : start + lv + lw + lx]
                    y = s[start + lv + lw + lx :]
                    if all(t08_original_member(u + v * t + w + x * t + y) for t in (0, 2)):
                        survivors.append((start, lv, lw, lx))
    return survivors


def run(n_values: range = range(2, 9)) -> dict[int, int]:
    """N -> number of surviving decompositions (0 means the pumping property fails)."""
    results = {}
    for n in n_values:
        s = "a" * (n + 2) + "b" * (n + 1) + "a" * n
        assert t08_original_member(s), "witness string must be in L'"
        results[n] = len(pumpable_decompositions(s, n))
    return results


def main() -> int:
    results = run()
    for n, survivors in results.items():
        verdict = "every decomposition fails" if survivors == 0 else f"{survivors} decompositions survive"
        print(f"N={n}: s = a^{n + 2} b^{n + 1} a^{n}: {verdict}")
    ok = all(v == 0 for v in results.values())
    print("original Task 08 language fails the pumping lemma for every N tested" if ok else "UNEXPECTED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
