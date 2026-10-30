"""Truth oracles for the CFG tasks: membership predicate, enumeration by length, and the
shortest member longer than a given length. These encode the *language definition* stated
in the prompt (not a reference answer), so the grader may use them freely.
"""
from __future__ import annotations

from typing import Callable, Optional

from automata.dfa import DFA

OPEN_TO_CLOSE = {"(": ")", "[": "]"}
CLOSE_TO_OPEN = {")": "(", "]": "["}

# --------------------------------------------------------------------------- Task 07


def t07_member(w: str, max_depth: int = 3) -> bool:
    """Bounded two-bracket Dyck variant: non-empty, well nested, depth <= 3, and no
    '('-group whose innermost enclosing group is a '['-group."""
    if not w:
        return False
    stack: list[str] = []
    for ch in w:
        if ch in OPEN_TO_CLOSE:
            if ch == "(" and stack and stack[-1] == "[":
                return False
            stack.append(ch)
            if len(stack) > max_depth:
                return False
        elif ch in CLOSE_TO_OPEN:
            if not stack or stack.pop() != CLOSE_TO_OPEN[ch]:
                return False
        else:
            return False
    return not stack


def t07_enumerate(max_len: int, max_depth: int = 3) -> dict[int, set[str]]:
    """All members of length 1..max_len, by DFS over valid prefixes (stack-pruned)."""
    out: dict[int, set[str]] = {n: set() for n in range(1, max_len + 1)}

    # Invariant: len(prefix) + len(stack) <= max_len, i.e. the open groups can still close.
    def extend(prefix: str, stack: list[str]) -> None:
        if prefix and not stack:
            out[len(prefix)].add(prefix)
        if stack:  # close the innermost open group
            top = stack.pop()
            extend(prefix + OPEN_TO_CLOSE[top], stack)
            stack.append(top)
        if len(stack) < max_depth and len(prefix) + len(stack) + 2 <= max_len:
            for op in "([":
                if op == "(" and stack and stack[-1] == "[":
                    continue
                stack.append(op)
                extend(prefix + op, stack)
                stack.pop()

    extend("", [])
    return out


def t07_shortest_longer_than(n: int) -> Optional[str]:
    """Shortest member of length > n: '()' repeated (every even length >= 2 is possible)."""
    length = n + 1 if (n + 1) % 2 == 0 else n + 2
    return "()" * max(1, length // 2)


def t07_truth_dfa(max_depth: int = 3) -> DFA:
    """Complete DFA for the Task 07 language. State = current stack of open brackets
    (only stacks allowed by the constraints), plus 'START' (nothing read yet, empty stack,
    rejecting), 'DONE' (empty stack after a non-empty word, accepting) and 'DEAD'."""
    stacks = [""]
    frontier = [""]
    while frontier:
        nxt = []
        for s in frontier:
            if len(s) == max_depth:
                continue
            for op in "([":
                if op == "(" and s.endswith("["):
                    continue
                nxt.append(s + op)
        stacks += nxt
        frontier = nxt
    names = {s: ("S" + s if s else "DONE") for s in stacks}
    alphabet = ["(", ")", "[", "]"]

    def target(s: str, ch: str) -> str:
        if ch in OPEN_TO_CLOSE:
            t = s + ch
            return names[t] if t in names else "DEAD"
        if s and s[-1] == CLOSE_TO_OPEN[ch]:
            return names[s[:-1]]
        return "DEAD"

    transitions = {"START": {ch: target("", ch) for ch in alphabet}}
    for s in stacks:
        transitions[names[s]] = {ch: target(s, ch) for ch in alphabet}
    transitions["DEAD"] = {ch: "DEAD" for ch in alphabet}
    return DFA(
        states=["START"] + [names[s] for s in stacks] + ["DEAD"],
        alphabet=alphabet,
        start="START",
        accepting=["DONE"],
        transitions=transitions,
    )


# --------------------------------------------------------------------------- Task 08


def t08_member(w: str) -> bool:
    """{ a^i b^j a^k : i >= 1, k >= 1, i + k = 2j }."""
    i = len(w) - len(w.lstrip("a"))
    rest = w[i:]
    j = len(rest) - len(rest.lstrip("b"))
    tail = rest[j:]
    k = len(tail)
    return i >= 1 and k >= 1 and tail == "a" * k and i + k == 2 * j


def t08_enumerate(max_len: int) -> dict[int, set[str]]:
    """Members have length i + j + k = 3j; for each j there are 2j - 1 choices of i."""
    out: dict[int, set[str]] = {n: set() for n in range(1, max_len + 1)}
    j = 1
    while 3 * j <= max_len:
        for i in range(1, 2 * j):
            out[3 * j].add("a" * i + "b" * j + "a" * (2 * j - i))
        j += 1
    return out


def t08_shortest_longer_than(n: int) -> Optional[str]:
    j = n // 3 + 1
    return "a" + "b" * j + "a" * (2 * j - 1)


# --------------------------------------------------------------------------- registry

Oracle = tuple[
    Callable[[str], bool], Callable[[int], dict[int, set[str]]], Callable[[int], Optional[str]]
]

ORACLES: dict[str, Oracle] = {
    "bounded_dyck": (t07_member, t07_enumerate, t07_shortest_longer_than),
    "ratio_aba": (t08_member, t08_enumerate, t08_shortest_longer_than),
}
