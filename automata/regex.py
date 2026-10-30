"""Regular expressions in the exact grammar stated in the Task 05 prompt.

Grammar (no whitespace, full-string match)::

    union   := concat ( "|" concat )*
    concat  := postfix postfix*
    postfix := atom ( "*" | "+" | "?" )*
    atom    := SYMBOL | "(" union ")" | "(" ")"        -- "()" denotes ε

Precedence: postfix operators bind tightest, then concatenation, then ``|``. Anything
outside this grammar (empty alternatives such as ``a|``, unknown characters, unbalanced
parentheses) raises ``RegexSyntaxError``.

Pipeline: parse → AST (nested tuples) → Thompson ε-NFA → subset construction → DFA.
``ast_matches`` is a second, automaton-free matcher used as an independent oracle.
"""
from __future__ import annotations

from functools import lru_cache
from itertools import count

from automata.dfa import DFA, minimize
from automata.nfa import EPS, ENFA, to_dfa

Node = tuple  # ("sym", c) | ("eps",) | ("cat", l, r) | ("alt", l, r) | ("star"|"plus"|"opt", x)


class RegexSyntaxError(ValueError):
    pass


class _Parser:
    def __init__(self, text: str, alphabet: list[str]):
        self.text, self.alphabet, self.pos = text, set(alphabet), 0

    def peek(self) -> str | None:
        return self.text[self.pos] if self.pos < len(self.text) else None

    def error(self, msg: str) -> RegexSyntaxError:
        return RegexSyntaxError(f"{msg} at position {self.pos} in {self.text!r}")

    def parse(self) -> Node:
        node = self.union()
        if self.peek() is not None:
            raise self.error(f"unexpected {self.peek()!r}")
        return node

    def union(self) -> Node:
        node = self.concat()
        while self.peek() == "|":
            self.pos += 1
            node = ("alt", node, self.concat())
        return node

    def concat(self) -> Node:
        node = self.postfix()
        while self.peek() is not None and self.peek() not in "|)":
            node = ("cat", node, self.postfix())
        return node

    def postfix(self) -> Node:
        node = self.atom()
        ops = {"*": "star", "+": "plus", "?": "opt"}
        while self.peek() in ops:
            node = (ops[self.text[self.pos]], node)
            self.pos += 1
        return node

    def atom(self) -> Node:
        c = self.peek()
        if c is None:
            raise self.error("expected a symbol or '('")
        if c in self.alphabet:
            self.pos += 1
            return ("sym", c)
        if c == "(":
            self.pos += 1
            if self.peek() == ")":
                self.pos += 1
                return ("eps",)
            node = self.union()
            if self.peek() != ")":
                raise self.error("expected ')'")
            self.pos += 1
            return node
        raise self.error(f"unexpected {c!r}")


def parse(text: str, alphabet: list[str]) -> Node:
    """Parse ``text`` into an AST; raises ``RegexSyntaxError`` outside the grammar."""
    return _Parser(text, alphabet).parse()


# --------------------------------------------------------------------------- Thompson


def to_enfa(ast: Node, alphabet: list[str]) -> ENFA:
    """Thompson construction: each sub-expression becomes a fragment with one entry and
    one exit state, glued together with ε-moves. Size is linear in the regex."""
    fresh = count()
    trans: dict[str, dict[str, list[str]]] = {}

    def new() -> str:
        q = f"t{next(fresh)}"
        trans[q] = {}
        return q

    def edge(p: str, symbol: str, q: str) -> None:
        trans[p].setdefault(symbol, []).append(q)

    def build(node: Node) -> tuple[str, str]:
        kind = node[0]
        if kind in ("sym", "eps"):
            s, f = new(), new()
            edge(s, node[1] if kind == "sym" else EPS, f)
            return s, f
        if kind == "cat":
            s1, f1 = build(node[1])
            s2, f2 = build(node[2])
            edge(f1, EPS, s2)
            return s1, f2
        if kind == "alt":
            s, f = new(), new()
            for child in node[1:]:
                cs, cf = build(child)
                edge(s, EPS, cs)
                edge(cf, EPS, f)
            return s, f
        # star / plus / opt share one shape: s -> inner -> f, plus loop and/or skip edges
        s, f = new(), new()
        cs, cf = build(node[1])
        edge(s, EPS, cs)
        edge(cf, EPS, f)
        if kind in ("star", "plus"):
            edge(cf, EPS, cs)  # repeat
        if kind in ("star", "opt"):
            edge(s, EPS, f)  # skip
        return s, f

    start, final = build(ast)
    return ENFA(
        states=list(trans), alphabet=list(alphabet), start=start, accepting=[final], transitions=trans
    )


def to_min_dfa(text: str, alphabet: list[str]) -> DFA:
    """Regex text → minimal complete DFA."""
    return minimize(to_dfa(to_enfa(parse(text, alphabet), alphabet)))


# --------------------------------------------------------------------------- oracle


def ast_matches(ast: Node, word: str) -> bool:
    """Automaton-free matcher used as an independent oracle in tests and verify_specs.

    ``ends(node, i)`` = set of positions j such that node matches word[i:j]; computed
    recursively with memoisation. Polynomial in |word| for a fixed regex."""

    @lru_cache(maxsize=None)
    def ends(node: Node, i: int) -> frozenset[int]:
        kind = node[0]
        if kind == "eps":
            return frozenset([i])
        if kind == "sym":
            return frozenset([i + 1]) if word[i : i + 1] == node[1] else frozenset()
        if kind == "cat":
            return frozenset(k for j in ends(node[1], i) for k in ends(node[2], j))
        if kind == "alt":
            return ends(node[1], i) | ends(node[2], i)
        if kind == "opt":
            return ends(node[1], i) | {i}
        # star / plus: closure of one-or-more iterations (only progress-making steps matter)
        reached, frontier = set(), {i}
        while frontier:
            nxt = {k for j in frontier for k in ends(node[1], j)} - reached
            reached |= nxt
            frontier = nxt
        return frozenset(reached | ({i} if kind == "star" else set()))

    return len(word) in ends(ast, 0)


def to_python_regex(ast: Node) -> str:
    """Translate to Python ``re`` syntax with explicit non-capturing groups (a third,
    independent implementation used in tests via ``re.fullmatch``)."""
    kind = ast[0]
    if kind == "sym":
        return ast[1]
    if kind == "eps":
        return "(?:)"
    if kind == "cat":
        return to_python_regex(ast[1]) + to_python_regex(ast[2])
    if kind == "alt":
        return f"(?:{to_python_regex(ast[1])}|{to_python_regex(ast[2])})"
    op = {"star": "*", "plus": "+", "opt": "?"}[kind]
    return f"(?:{to_python_regex(ast[1])}){op}"
