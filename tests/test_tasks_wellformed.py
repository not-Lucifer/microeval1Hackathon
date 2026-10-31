"""Every prompt states what the grader checks (CLAUDE.md rule 3), and every example in a
prompt is consistent with the real grader/reference."""
import json
import re

import pytest
from helpers import load_task_files

import generate_instances
from automata.cfg import cnf_violations, enumerate_upto
from automata.dfa import DFA, accepts, is_complete
from automata.regex import parse
from graders.answers import ANSWER_MODELS, GrammarAnswer
from graders.grader import reference_dfa
from graders.oracles import ORACLES
from reference.build import t01_member, t02_member, t04_member

TASKS = load_task_files()
REQUIRED_KEYS = {"id", "family", "title", "prompt", "answer_schema", "grader", "examples", "metadata"}
INDEPENDENT_MEMBERS = {
    "task_01": t01_member,
    "task_02": t02_member,
    "task_04": t04_member,
}


def test_there_are_eight_tasks():
    assert [t["id"] for t in TASKS] == [f"task_0{i}" for i in range(1, 9)]


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t["id"])
def test_common_contract(task):
    assert REQUIRED_KEYS <= task.keys()
    p = task["prompt"]
    for symbol in task["grader"]["params"]["alphabet"]:
        assert symbol in p
    for phrase in ("WHAT TO SUBMIT", "HOW IT IS GRADED", "```json", "ε"):
        assert phrase in p
    for key in ("why_hard", "real_world", "expected_failure_modes"):
        assert task["metadata"][key]


@pytest.mark.parametrize("task", [t for t in TASKS if t["answer_schema"] == "dfa"], ids=lambda t: t["id"])
def test_dfa_prompts_state_the_rules(task):
    p = task["prompt"]
    for phrase in ("Complete", "Minimal", "fewest states", "unreachable", "trap", "0.5"):
        assert phrase in p, phrase


@pytest.mark.parametrize("task", [t for t in TASKS if t["answer_schema"] == "cnf_grammar"], ids=lambda t: t["id"])
def test_cfg_prompts_state_the_rules(task):
    p, n = task["prompt"], task["grader"]["params"]["max_len"]
    for phrase in ("Chomsky normal form", f"1 <= |w| <= {n}", "infinitely many", "unit productions", "undecidable"):
        assert phrase in p, phrase


def test_witness_prompt_states_the_rules():
    task = next(t for t in TASKS if t["answer_schema"] == "witness")
    p, params = task["prompt"], task["grader"]["params"]
    for phrase in ("SHORTEST", "any one of them is accepted", "WHOLE word", "0.5", params["r1"], params["r2"]):
        assert phrase in p
    parse(params["r1"], params["alphabet"])
    parse(params["r2"], params["alphabet"])


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t["id"])
def test_prompt_examples_agree_with_grader(task):
    kind = task["grader"]["type"]
    if kind == "dfa_exact":
        member = lambda w: accepts(reference_dfa(task), w)  # noqa: E731
    elif kind == "cfg_bounded":
        member = ORACLES[task["grader"]["params"]["language"]][0]
    else:
        return
    for w in task["examples"]["in"]:
        assert member(w), w
    for w in task["examples"]["out"]:
        assert not member(w), w
    other = INDEPENDENT_MEMBERS.get(task["id"])
    if other:
        assert all(other(w) for w in task["examples"]["in"])
        assert not any(other(w) for w in task["examples"]["out"])


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t["id"])
def test_format_examples_in_prompts_are_valid(task):
    blocks = re.findall(r"```json\n(.*?)```", task["prompt"], re.DOTALL)
    assert len(blocks) == 1
    example = json.loads(blocks[0])
    ANSWER_MODELS[task["answer_schema"]].model_validate(example)
    if task["answer_schema"] == "dfa":
        assert is_complete(DFA(alphabet=["x", "y"], **example))
    if task["answer_schema"] == "cnf_grammar":
        g = GrammarAnswer.model_validate(example)
        assert cnf_violations(g, ["x", "y"]) == []
        by_len, _ = enumerate_upto(g, ["x", "y"], 10)
        assert {w for s in by_len.values() for w in s} == {"x" * n + "y" * n for n in range(1, 6)}


def test_generated_files_are_up_to_date():
    for path, text in generate_instances.render_all().items():
        assert path.read_text(encoding="utf-8") == text, f"{path.name} is stale: run scripts/generate_instances.py"
