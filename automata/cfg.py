"""Context-free grammars in Chomsky normal form: validation, CYK, and bounded checking.

Symbol convention (stated in the Task 07/08 prompts): an item of a right-hand side that is
exactly one alphabet symbol is a terminal; every other name is a nonterminal.

CFG equivalence is undecidable in general, so ``check_upto`` is exact only for strings of
length <= N. It also checks that the grammar's language is infinite (both task languages
are infinite), which stops a finite list of all strings up to N from passing.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Callable, Optional

from pydantic import BaseModel


class Production(BaseModel):
    lhs: str
    rhs: list[str]


class Grammar(BaseModel):
    start: str
    productions: list[Production]


# --------------------------------------------------------------------------- CNF form


def cnf_violations(grammar: Grammar, alphabet: list[str]) -> list[str]:
    """Every reason the grammar is not in CNF (empty list = valid CNF).

    Allowed forms: ``A -> B C`` (two nonterminals) and ``A -> t`` (one terminal). No ε,
    no unit productions, no longer or mixed right-hand sides; lhs and start must be
    nonterminals; names must be non-empty and whitespace-free."""
    terminals = set(alphabet)
    problems = []

    def bad_name(name: str) -> bool:
        return name == "" or any(ch.isspace() for ch in name)

    if grammar.start in terminals or bad_name(grammar.start):
        problems.append(f"start symbol {grammar.start!r} must be a nonterminal name")
    for i, p in enumerate(grammar.productions):
        shown = f"production {i}: {p.lhs} -> {' '.join(p.rhs) or 'ε'}"
        if p.lhs in terminals or bad_name(p.lhs):
            problems.append(f"{shown}: left-hand side must be a nonterminal name")
        if any(bad_name(s) for s in p.rhs):
            problems.append(f"{shown}: empty or whitespace-containing symbol name")
        elif len(p.rhs) == 1 and p.rhs[0] not in terminals:
            problems.append(f"{shown}: unit production (single nonterminal on the right)")
        elif len(p.rhs) == 2 and any(s in terminals for s in p.rhs):
            problems.append(f"{shown}: a two-symbol right-hand side must be two nonterminals")
        elif len(p.rhs) not in (1, 2):
            problems.append(f"{shown}: right-hand side must have length 1 or 2")
    return problems


def _split(grammar: Grammar, alphabet: list[str]):
    """(terminal rules {A: {t}}, binary rules [(A, B, C)]) for a CNF grammar."""
    terminals = set(alphabet)
    term_rules: dict[str, set[str]] = {}
    bin_rules: list[tuple[str, str, str]] = []
    for p in grammar.productions:
        if len(p.rhs) == 1 and p.rhs[0] in terminals:
            term_rules.setdefault(p.lhs, set()).add(p.rhs[0])
        elif len(p.rhs) == 2:
            bin_rules.append((p.lhs, p.rhs[0], p.rhs[1]))
    return term_rules, bin_rules


# --------------------------------------------------------------------------- CYK


def cyk(grammar: Grammar, alphabet: list[str], word: str) -> bool:
    """CYK membership for a CNF grammar. ε is never derivable. O(|w|³·|G|)."""
    n = len(word)
    if n == 0:
        return False
    term_rules, bin_rules = _split(grammar, alphabet)
    # table[i][l] = nonterminals deriving word[i:i+l]
    table = [[set() for _ in range(n + 1)] for _ in range(n)]
    for i, ch in enumerate(word):
        table[i][1] = {a for a, ts in term_rules.items() if ch in ts}
    for length in range(2, n + 1):
        for i in range(n - length + 1):
            cell = table[i][length]
            for k in range(1, length):
                left, right = table[i][k], table[i + k][length - k]
                if left and right:
                    cell.update(a for a, b, c in bin_rules if b in left and c in right)
    return grammar.start in table[0][n]


# --------------------------------------------------------------------------- enumeration


def enumerate_upto(
    grammar: Grammar, alphabet: list[str], max_len: int, cap: int = 200_000
) -> tuple[dict[int, set[str]], bool]:
    """Strings derivable from the start symbol, grouped by length 1..max_len, by dynamic
    programming over (nonterminal, length). Returns ``(by_length, capped)``; ``capped`` is
    True if some (nonterminal, length) set exceeded ``cap`` and was truncated (the result is
    then incomplete). Used for diagnostics and tests; grading uses ``check_upto``."""
    term_rules, bin_rules = _split(grammar, alphabet)
    nts = {grammar.start} | set(term_rules) | {x for r in bin_rules for x in r}
    sets: dict[tuple[str, int], set[str]] = {}
    capped = False
    for length in range(1, max_len + 1):
        for a in nts:
            out = set(term_rules.get(a, ())) if length == 1 else set()
            for lhs, b, c in bin_rules:
                if lhs != a:
                    continue
                for k in range(1, length):
                    for u in sets.get((b, k), ()):
                        for v in sets.get((c, length - k), ()):
                            out.add(u + v)
            if len(out) > cap:
                capped = True
                out = set(sorted(out)[:cap])
            sets[(a, length)] = out
    return {n: sets.get((grammar.start, n), set()) for n in range(1, max_len + 1)}, capped


# --------------------------------------------------------------------------- exact check


MAX_COUNTEREXAMPLE_LEN = 10_000  # longer missing words of a finite grammar are not materialized


@dataclass
class BoundedCheck:
    """Result of ``check_upto``. ``kind`` is None (agrees up to N), "over" or "under"."""

    kind: Optional[str] = None
    counterexample: Optional[str] = None
    checked_upto: int = 0  # every length <= this was fully compared
    generated_by_length: dict[int, int] = field(default_factory=dict)
    finite_language: bool = False
    notes: list[str] = field(default_factory=list)


def _productive(term_rules, bin_rules) -> set[str]:
    prod = set(term_rules)
    changed = True
    while changed:
        changed = False
        for a, b, c in bin_rules:
            if a not in prod and b in prod and c in prod:
                prod.add(a)
                changed = True
    return prod


def _shortest_strings(term_rules, bin_rules, max_len: int) -> dict[str, str]:
    """For each nonterminal whose shortest derivable string has length <= max_len, its
    shortlex-least such string (fixpoint). Longer strings are never built: a doubling chain
    A_k -> A_(k-1) A_(k-1) would otherwise need 2^k characters of memory."""
    best = {a: min(ts) for a, ts in term_rules.items()}
    key = lambda s: (len(s), s)  # noqa: E731
    changed = True
    while changed:
        changed = False
        for a, b, c in bin_rules:
            if b in best and c in best and len(best[b]) + len(best[c]) <= max_len:
                cand = best[b] + best[c]
                if a not in best or key(cand) < key(best[a]):
                    best[a] = cand
                    changed = True
    return best


def _reachable(start: str, bin_rules) -> set[str]:
    """Nonterminals reachable from the start symbol through the given rules."""
    seen, stack = {start}, [start]
    while stack:
        a = stack.pop()
        for lhs, b, c in bin_rules:
            if lhs == a:
                for child in (b, c):
                    if child not in seen:
                        seen.add(child)
                        stack.append(child)
    return seen


def _contexts(start, bin_rules, shortest, max_len: int) -> dict[str, tuple[str, str]]:
    """For each nonterminal X that can occur inside a derivable string of length <= max_len,
    a pair (x, y) of minimal total length with start =>* x X y (Dijkstra over context
    length). Contexts longer than max_len are pruned: such an X cannot contribute to any
    string of length <= max_len."""
    by_lhs: dict[str, list[tuple[str, str]]] = {}
    for lhs, b, c in bin_rules:
        by_lhs.setdefault(lhs, []).append((b, c))
    ctx: dict[str, tuple[str, str]] = {}
    heap = [(0, "", "", start)]
    while heap:
        _, x, y, a = heapq.heappop(heap)
        if a in ctx:
            continue
        ctx[a] = (x, y)
        for b, c in by_lhs.get(a, ()):
            if b not in shortest or c not in shortest:
                continue  # a sibling's shortest string is longer than max_len
            # In A -> B C, B sits before a shortest C-string and C after a shortest B-string.
            for child, cx, cy in ((b, x, shortest[c] + y), (c, x + shortest[b], y)):
                if child not in ctx and len(cx) + len(cy) <= max_len:
                    heapq.heappush(heap, (len(cx) + len(cy), cx, cy, child))
    return ctx


def _has_cycle(nodes: set[str], bin_rules) -> bool:
    """True if the 'A uses B' graph restricted to ``nodes`` has a cycle (=> infinite language,
    because every symbol in ``nodes`` is productive and reachable)."""
    succ = {a: set() for a in nodes}
    for a, b, c in bin_rules:
        if a in nodes:
            succ[a].update(x for x in (b, c) if x in nodes)
    color = {a: 0 for a in nodes}  # 0 new, 1 on stack, 2 done
    for root in sorted(nodes):
        if color[root]:
            continue
        stack = [(root, iter(sorted(succ[root])))]
        color[root] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                color[node] = 2
                stack.pop()
            elif color[nxt] == 1:
                return True
            elif color[nxt] == 0:
                color[nxt] = 1
                stack.append((nxt, iter(sorted(succ[nxt]))))
    return False


def _longest_lengths(nodes: set[str], term_rules, bin_rules) -> dict[str, int]:
    """Longest derivable string length per nonterminal of an acyclic (finite) grammar.
    Fixpoint iteration (no recursion); an acyclic grammar settles within |nodes| rounds."""
    longest = {a: (1 if a in term_rules else 0) for a in nodes}
    rules = [(a, b, c) for a, b, c in bin_rules if a in nodes and b in nodes and c in nodes]
    for _ in range(len(nodes) + 1):
        changed = False
        for a, b, c in rules:
            if longest[b] and longest[c] and longest[b] + longest[c] > longest[a]:
                longest[a] = longest[b] + longest[c]
                changed = True
        if not changed:
            break
    return longest


def check_upto(
    grammar: Grammar,
    alphabet: list[str],
    max_len: int,
    in_language: Callable[[str], bool],
    truth_by_length: dict[int, set[str]],
    shortest_longer_than: Callable[[int], Optional[str]],
) -> BoundedCheck:
    """Compare L(grammar) with the target language L on every string of length <= N
    (= ``max_len``), exactly, and check that L(grammar) is infinite like L.

    Method ("wrapped enumeration"):
      1. Keep only productive nonterminals reachable from the start.
      2. Give each remaining nonterminal X that can occur inside a string of length <= N a
         fixed shortest context (x, y) with start =>* x X y, and let c(X) = |x| + |y|.
         No string longer than N is ever built, so memory does not depend on how long the
         grammar's other strings are.
      3. Compute, by dynamic programming, the set X_l of strings X derives, for every
         l <= N - c(X) (longer strings of X can never occur inside a string of length <= N).
         Each new u in X_l is checked as x+u+y against L. x+u+y is derivable and has length
         <= N, so a failure is a genuine over-generation witness. Processing (X, l) in order
         of l + c(X) makes the first failure a *shortest* over-generated string.
         Because every stored u passes this check, |X_l| <= |L_(l + c(X))|, so the sets stay
         as small as the target language itself and no cap is needed.
      4. With no over-generation, start's sets are exactly L(G) by length; any string of
         L missing from them is an under-generation witness (shortest one reported).
    """
    result = BoundedCheck()
    term_rules, bin_rules = _split(grammar, alphabet)
    productive = _productive(term_rules, bin_rules)
    bin_rules = [r for r in bin_rules if r[0] in productive and r[1] in productive and r[2] in productive]
    if grammar.start not in productive:
        result.notes.append("start symbol derives no terminal string (empty language)")
        result.finite_language = True
        for n in range(1, max_len + 1):
            if truth_by_length.get(n):
                result.kind, result.counterexample = "under", min(truth_by_length[n])
                return result
        result.counterexample = shortest_longer_than(0)
        result.kind = "under" if result.counterexample is not None else None
        return result

    reachable = _reachable(grammar.start, bin_rules)
    bin_rules = [r for r in bin_rules if r[0] in reachable]
    shortest = _shortest_strings(term_rules, bin_rules, max_len)
    ctx = _contexts(grammar.start, bin_rules, shortest, max_len)
    order = sorted(
        ((a, n) for a in ctx for n in range(1, max_len - sum(map(len, ctx[a])) + 1)),
        key=lambda an: (an[1] + len(ctx[an[0]][0]) + len(ctx[an[0]][1]), an[1], an[0]),
    )
    rules_by_lhs: dict[str, list[tuple[str, str]]] = {}
    for a, b, c in bin_rules:
        if a in ctx:
            rules_by_lhs.setdefault(a, []).append((b, c))

    sets: dict[tuple[str, int], set[str]] = {}
    over: Optional[str] = None
    for a, n in order:
        out = set(term_rules.get(a, ())) if n == 1 else set()
        for b, c in rules_by_lhs.get(a, ()):
            for k in range(1, n):
                left, right = sets.get((b, k)), sets.get((c, n - k))
                if left and right:
                    out.update(u + v for u in left for v in right)
        x, y = ctx[a]
        for u in sorted(out):
            if not in_language(x + u + y):
                over = x + u + y
                break
        if over is not None:
            break
        sets[(a, n)] = out

    generated = {n: sets.get((grammar.start, n), set()) for n in range(1, max_len + 1)}
    complete_upto = max_len if over is None else len(over) - 1
    result.checked_upto = complete_upto
    result.generated_by_length = {n: len(generated[n]) for n in range(1, complete_upto + 1)}

    for n in range(1, complete_upto + 1):
        missing = truth_by_length.get(n, set()) - generated[n]
        if missing:
            result.kind, result.counterexample = "under", min(missing)
            return result
    if over is not None:
        result.kind, result.counterexample = "over", over
        return result

    # Finiteness: a trimmed grammar has an infinite language iff its graph has a cycle.
    # (Uses every productive reachable nonterminal, not only those that fit inside length N.)
    if not _has_cycle(reachable, bin_rules) and shortest_longer_than(max_len) is not None:
        result.finite_language = True
        result.kind = "under"
        longest = _longest_lengths(reachable, term_rules, bin_rules)[grammar.start]
        if longest <= MAX_COUNTEREXAMPLE_LEN:
            result.counterexample = shortest_longer_than(max(longest, max_len))
        result.notes.append(
            f"grammar generates a finite language (longest string has length {longest}); "
            "the target language is infinite"
            + ("" if result.counterexample else "; the missing word is too long to store")
        )
    return result
