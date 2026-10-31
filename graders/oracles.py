"""Truth oracles for the CFG tasks: membership predicate, enumeration by length, and the
shortest member longer than a given length. These encode the *language definition* stated
in the prompt (not a reference answer), so the grader may use them freely.

Task set v2 (the v1 languages are kept at git tag pilot-v1).
"""
from __future__ import annotations

from typing import Callable, Optional

OPEN_TO_CLOSE = {"(": ")", "[": "]"}
CLOSE_TO_OPEN = {")": "(", "]": "["}

# --------------------------------------------------------------------------- Task 07
# Non-empty, well-nested words over ( ) [ ] such that a [-group has no (-children, and every
# (-group, and the word itself (its top-level groups), has an even number of [-children.
# A frame is [kind, parity]: kind is "(" or "[" ("(" for the whole word, which obeys the
# same rule as the inside of a (-group), parity = number of [-children so far, mod 2.


def _open(stack: list[list], symbol: str) -> bool:
    """Push a group opened by ``symbol``; False if the parent may not contain it."""
    parent = stack[-1]
    if parent[0] == "[" and symbol == "(":
        return False
    if symbol == "[":
        parent[1] ^= 1
    stack.append([symbol, 0])
    return True


def t07_member(w: str) -> bool:
    """Single left-to-right pass with a stack of frames. O(|w|)."""
    if not w:
        return False
    stack: list[list] = [["(", 0]]
    for ch in w:
        if ch in OPEN_TO_CLOSE:
            if not _open(stack, ch):
                return False
        elif ch in CLOSE_TO_OPEN:
            if len(stack) == 1 or stack[-1][0] != CLOSE_TO_OPEN[ch]:
                return False
            kind, parity = stack.pop()
            if kind == "(" and parity:
                return False
        else:
            return False
    return len(stack) == 1 and stack[0][1] == 0


def t07_enumerate(max_len: int) -> dict[int, set[str]]:
    """All members of length 1..max_len, by DFS over prefixes that respect the rules so far
    (stack-pruned: the open groups must still be able to close within max_len)."""
    out: dict[int, set[str]] = {n: set() for n in range(1, max_len + 1)}

    def extend(prefix: str, stack: list[list]) -> None:
        if len(stack) == 1:
            if prefix and stack[0][1] == 0:
                out[len(prefix)].add(prefix)
        else:  # close the innermost open group, if its rule allows
            kind, parity = stack[-1]
            if not (kind == "(" and parity):
                stack.pop()
                extend(prefix + OPEN_TO_CLOSE[kind], stack)
                stack.append([kind, parity])
        if len(prefix) + (len(stack) - 1) + 2 <= max_len:
            for op in "([":
                saved = [frame[:] for frame in stack]
                if _open(stack, op):
                    extend(prefix + op, stack)
                stack[:] = saved

    extend("", [["(", 0]])
    return out


def t07_shortest_longer_than(n: int) -> Optional[str]:
    """Shortest member of length > n: '()' repeated (every even length >= 2 is possible)."""
    length = n + 1 if (n + 1) % 2 == 0 else n + 2
    return "()" * max(1, length // 2)


# --------------------------------------------------------------------------- Task 08
# { a^i b^j a^k : i >= 1, k >= 1, 2i + k = 3j }. A member has length i + j + k = 4j - i,
# so for each j >= 1 the choices are 1 <= i with k = 3j - 2i >= 1.


def t08_member(w: str) -> bool:
    i = len(w) - len(w.lstrip("a"))
    rest = w[i:]
    j = len(rest) - len(rest.lstrip("b"))
    tail = rest[j:]
    k = len(tail)
    return i >= 1 and k >= 1 and tail == "a" * k and 2 * i + k == 3 * j


def t08_enumerate(max_len: int) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {n: set() for n in range(1, max_len + 1)}
    for j in range(1, max_len + 1):
        for i in range(1, (3 * j - 1) // 2 + 1):
            k = 3 * j - 2 * i
            if i + j + k <= max_len:
                out[i + j + k].add("a" * i + "b" * j + "a" * k)
    return out


def t08_shortest_longer_than(n: int) -> Optional[str]:
    """The shortlex-least member of the smallest length > n (members exist at every length
    >= 6, and lengths 3 and 6 occur below that)."""
    length = n + 1
    while True:
        words = t08_enumerate(length)[length]
        if words:
            return min(words)
        length += 1


# --------------------------------------------------------------------------- registry

Oracle = tuple[
    Callable[[str], bool], Callable[[int], dict[int, set[str]]], Callable[[int], Optional[str]]
]

ORACLES: dict[str, Oracle] = {
    "parity_dyck": (t07_member, t07_enumerate, t07_shortest_longer_than),
    "ratio_2i_k_3j": (t08_member, t08_enumerate, t08_shortest_longer_than),
}
