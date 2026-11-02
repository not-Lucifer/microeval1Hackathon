import random
import re

import pytest
from helpers import AB

from automata.dfa import accepts, all_words, equivalent
from automata.regex import RegexSyntaxError, ast_matches, parse, to_min_dfa, to_python_regex
from reference.build import T05_ALT_PAIR, T05_MIN_WITNESS_LEN, T05_PAIR, t05_shortest_witness


@pytest.mark.parametrize("text", ["a", "()", "a|b", "(ab)*", "a+b?", "(a|())*", "a**", "((a))", "(ba)*b+a(ba)+a"])
def test_parser_accepts_grammar(text):
    parse(text, AB)


@pytest.mark.parametrize("text", ["", "a|", "|a", "(a", "a)", "c", "*a", "a b", "(|a)", "a||b"])
def test_parser_rejects_everything_else(text):
    with pytest.raises(RegexSyntaxError):
        parse(text, AB)


def test_precedence():
    assert to_min_dfa("ab*", AB) == to_min_dfa("a(b*)", AB)
    assert to_min_dfa("ab|b", AB) == to_min_dfa("(ab)|b", AB)
    assert accepts(to_min_dfa("()", AB), "") and not accepts(to_min_dfa("()", AB), "a")


def random_regex(rng: random.Random, depth: int) -> str:
    if depth == 0 or rng.random() < 0.3:
        return rng.choice(["a", "b", "()"])
    k = rng.random()
    if k < 0.4:
        return random_regex(rng, depth - 1) + random_regex(rng, depth - 1)
    if k < 0.7:
        return f"({random_regex(rng, depth - 1)}|{random_regex(rng, depth - 1)})"
    return f"({random_regex(rng, depth - 1)}){rng.choice('*+?')}"


@pytest.mark.parametrize("seed", range(120))
def test_three_independent_matchers_agree(seed):
    text = random_regex(random.Random(seed), 4)
    ast = parse(text, AB)
    dfa = to_min_dfa(text, AB)
    py = re.compile(to_python_regex(ast))
    for w in all_words(AB, 7):
        expected = ast_matches(ast, w)
        assert accepts(dfa, w) == expected, (text, w)
        assert bool(py.fullmatch(w)) == expected, (text, w)


@pytest.mark.parametrize("pair", [T05_PAIR, T05_ALT_PAIR])
def test_task05_pairs_agree_on_short_words(pair):
    w = t05_shortest_witness(pair)
    a1, a2 = parse(pair.r1, AB), parse(pair.r2, AB)
    assert len(w) >= T05_MIN_WITNESS_LEN
    assert ast_matches(a1, w) != ast_matches(a2, w)
    assert all(ast_matches(a1, u) == ast_matches(a2, u) for u in all_words(AB, len(w) - 1))


def test_task05_default_pair_hand_proof():
    """The hand proof in reference/build.py: unique shortest witness ababaababaababaa
    (a-runs 1,1,2,1,2,1,2), and the obvious guess ababababababaa is matched by both."""
    d1, d2 = to_min_dfa(T05_PAIR.r1, AB), to_min_dfa(T05_PAIR.r2, AB)
    assert equivalent(d1, d2) == (False, "ababaababaababaa")
    shortest = [w for w in all_words(AB, 16) if len(w) == 16 and accepts(d1, w) != accepts(d2, w)]
    assert shortest == ["ababaababaababaa"]
    assert accepts(d1, "ababababababaa") and accepts(d2, "ababababababaa")


def test_readme_regex_one_liner_prints_what_the_readme_says():
    """The README's "Reviewing a regex change" command, run as written."""
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    command = next(line.strip() for line in readme.splitlines() if line.strip().startswith('python -c "from automata.regex'))
    code = command[len('python -c "'):-1]
    out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    assert out == "(False, 'ababaababaababaa')"
    assert f"this prints `{out}`" in readme
