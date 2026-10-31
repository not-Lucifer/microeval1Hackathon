"""Free chat-app route: folder skeleton, import, identical grading, and the honesty checks."""
import json

import pytest
import yaml

import run_eval
from graders.grader import load_reference
from harness.manual import SOURCE, import_manual, new_manual_model
from harness.metrics import load_transcripts, render_markdown, summarize
from harness.prompts import SYSTEM_PROMPT, load_tasks, tasks_by_id

GOOD_INFO = {
    "app": "Example chat app, free plan, web",
    "model_shown": "Example-Model",
    "date": "2026-11-01",
    "reasoning_mode": "default",
    "no_tools_confirmed": True,
    "new_chat_per_trial": True,
    "notes": "",
}


def fenced(obj) -> str:
    return "```json\n" + json.dumps(obj) + "\n```"


def make(tmp_path, info=GOOD_INFO, name="chat-free"):
    manual = tmp_path / "manual"
    root = new_manual_model(manual, name, load_tasks(), 2)
    if info is not None:
        (root / "info.yaml").write_text(yaml.safe_dump(info), encoding="utf-8")
    return manual, root


def paste(root, task_id, trial, text):
    (root / task_id / f"trial_{trial}.txt").write_text(text, encoding="utf-8")


def test_skeleton_and_prompts(tmp_path):
    manual, root = make(tmp_path, info=None)
    assert (root / "task_08" / "trial_2.txt").read_text(encoding="utf-8") == ""
    assert "no_tools_confirmed: false" in (root / "info.yaml").read_text(encoding="utf-8")
    prompt = (manual / "prompts" / "task_05.txt").read_text(encoding="utf-8")
    assert prompt.startswith(SYSTEM_PROMPT) and prompt.endswith(tasks_by_id()["task_05"]["prompt"])
    paste(root, "task_01", 1, "my reply")
    new_manual_model(manual, "chat-free", load_tasks(), 2)  # re-running never overwrites replies
    assert (root / "task_01" / "trial_1.txt").read_text(encoding="utf-8") == "my reply"


def test_import_grades_exactly_like_api_answers(tmp_path):
    manual, root = make(tmp_path)
    paste(root, "task_05", 1, "Let me think...\n" + fenced(load_reference("task_05")["answer"]))
    paste(root, "task_05", 2, fenced({"witness": "babababaa"}))
    paste(root, "task_01", 1, "Sorry, I could not finish this.")
    written, problems = import_manual(manual, tmp_path / "transcripts", tasks_by_id())
    assert problems == [] and len(written) == 3  # the other (empty) files are not done yet
    grades = {(t["task_id"], t["trial"]): (t["grade"]["score"], t["grade"]["failure_code"]) for t in written}
    assert grades == {
        ("task_01", 1): (0.0, "PARSE_ERROR"),
        ("task_05", 1): (1.0, None),
        ("task_05", 2): (0.0, "WITNESS_NOT_DISTINGUISHING"),
    }
    assert all(t["settings"]["source"] == SOURCE and t["usage"]["cost_usd"] == 0.0 for t in written)
    assert "pasted by hand" in render_markdown(summarize(load_transcripts(tmp_path / "transcripts")))
    assert run_eval.regrade(tmp_path / "transcripts", write=False, results_dir=tmp_path / "results") == 0


@pytest.mark.parametrize(
    "change, message",
    [
        ({"model_shown": ""}, "'model_shown' is empty"),
        ({"date": "1 Nov"}, "'date' must look like"),
        ({"no_tools_confirmed": False}, "'no_tools_confirmed' must be true"),
        ({"new_chat_per_trial": "yes"}, "'new_chat_per_trial' must be true"),
    ],
)
def test_incomplete_or_unconfirmed_info_is_refused(tmp_path, change, message):
    manual, root = make(tmp_path, info={**GOOD_INFO, **change})
    paste(root, "task_05", 1, fenced({"witness": "ab"}))
    written, problems = import_manual(manual, tmp_path / "transcripts", tasks_by_id())
    assert written == [] and any(message in p for p in problems)


def test_unquoted_yaml_date_is_accepted(tmp_path):
    manual, root = make(tmp_path, info=None)
    template = (root / "info.yaml").read_text(encoding="utf-8")
    filled = (template.replace('app: ""', 'app: "Example app"').replace('model_shown: ""', 'model_shown: "M"')
              .replace('date: ""', "date: 2026-11-01").replace('reasoning_mode: ""', 'reasoning_mode: "default"')
              .replace("no_tools_confirmed: false", "no_tools_confirmed: true")
              .replace("new_chat_per_trial: false", "new_chat_per_trial: true"))
    (root / "info.yaml").write_text(filled, encoding="utf-8")
    paste(root, "task_05", 1, fenced({"witness": "ab"}))
    written, problems = import_manual(manual, tmp_path / "transcripts", tasks_by_id())
    assert problems == [] and written[0]["date"] == "2026-11-01"


def test_manual_import_never_overwrites_api_transcripts(tmp_path):
    existing = tmp_path / "transcripts" / "chat-free" / "task_05" / "trial_1.json"
    existing.parent.mkdir(parents=True)
    existing.write_text(json.dumps({"settings": {"openrouter_id": "lab/m"}}), encoding="utf-8")
    manual, root = make(tmp_path)
    paste(root, "task_05", 1, fenced({"witness": "ab"}))
    written, problems = import_manual(manual, tmp_path / "transcripts", tasks_by_id())
    assert written == [] and "API transcript" in problems[0]


def test_missing_manual_folder_is_reported(tmp_path):
    assert import_manual(tmp_path / "nope", tmp_path / "t", tasks_by_id()) == ([], [f"{tmp_path / 'nope'}: no such folder"])


def test_bad_model_folder_name_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        new_manual_model(tmp_path, "my model!", load_tasks(), 1)
