"""Reference answers never reach the model (CLAUDE.md rule 5)."""
import ast
import json
from pathlib import Path

import pytest

from graders.grader import load_reference
from harness.prompts import SYSTEM_PROMPT, build_messages, load_tasks

ROOT = Path(__file__).resolve().parents[1]
TASKS = load_tasks()
HARNESS_FILES = sorted((ROOT / "harness").glob("*.py")) + [ROOT / "run_eval.py"]


def leak_strings(answer: dict) -> list[str]:
    """Serialisations of a reference answer that must not appear in any prompt."""
    out = [json.dumps(answer), json.dumps(answer, sort_keys=True), json.dumps(answer, indent=2)]
    if "witness" in answer:
        out.append(answer["witness"])
    if "transitions" in answer:
        out += [json.dumps(row) for row in answer["transitions"].values() if len(row) > 1]
        out.append(json.dumps(answer["transitions"]))
    if "productions" in answer:
        out.append(json.dumps(answer["productions"]))
    return out


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t["id"])
def test_reference_answer_not_in_prompt(task):
    messages = build_messages(task)
    assert [m["content"] for m in messages] == [SYSTEM_PROMPT, task["prompt"]]
    text = "\n".join(m["content"] for m in messages)
    for leak in leak_strings(load_reference(task["id"])["answer"]):
        assert leak not in text


def test_task_files_contain_no_answers():
    for task in TASKS:
        dumped = json.dumps(task)
        ref = load_reference(task["id"])["answer"]
        if "witness" in ref:
            assert ref["witness"] not in dumped
        if "productions" in ref:
            assert json.dumps(ref["productions"]) not in dumped
        if "transitions" in ref:
            assert json.dumps(ref["transitions"]) not in dumped


@pytest.mark.parametrize("path", HARNESS_FILES, ids=lambda p: p.name)
def test_harness_code_never_touches_reference(path):
    """No import of the reference package and no string literal mentioning 'reference'
    (docstrings excluded) in harness code or run_eval.py."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "reference" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "reference"
            assert not any("reference" in a.name for a in node.names)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            assert "reference" not in node.value.lower(), node.value
        if isinstance(node, ast.Name):
            assert "reference" not in node.id.lower()
