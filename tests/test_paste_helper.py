"""scripts/paste_helper.py: which files it fills, in what order, and what it refuses to save."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import paste_helper as ph  # noqa: E402

REPLY = "Working...\r\n```json\r\n{\"witness\": \"ab\"}\r\n```\r\n"


def make_manual(tmp_path: Path) -> Path:
    manual = tmp_path / "manual"
    (manual / "prompts").mkdir(parents=True)
    for task in ("task_01", "task_02"):
        (manual / "prompts" / f"{task}.txt").write_text(f"PROMPT {task} " + "x" * 300, encoding="utf-8")
        (manual / "m" / task).mkdir(parents=True)
        for trial in (1, 2):
            (manual / "m" / task / f"trial_{trial}.txt").write_text("", encoding="utf-8")
    (manual / "m" / "task_01" / "trial_2.txt").write_text("already pasted", encoding="utf-8")
    return manual


def run(manual: Path, answers: list[str], clips: list[str], trial=None):
    copied, answers, clips = [], iter(answers), iter(clips)
    saved = ph.collect(manual, "m", trial, lambda: next(clips), copied.append, lambda _: next(answers))
    return saved, copied


def test_pending_takes_trial_1_of_every_task_first_and_skips_filled_files(tmp_path):
    manual = make_manual(tmp_path)
    assert [p.relative_to(manual / "m").as_posix() for p in ph.pending(manual, "m")] == [
        "task_01/trial_1.txt", "task_02/trial_1.txt", "task_02/trial_2.txt"]
    assert len(ph.pending(manual, "m", trial=2)) == 1


def test_saves_the_copied_reply_unchanged_except_line_endings(tmp_path):
    manual = make_manual(tmp_path)
    saved, copied = run(manual, ["", "s", "q"], [REPLY], trial=None)
    assert saved == 1
    assert copied[0].startswith("PROMPT task_01")
    assert (manual / "m" / "task_01" / "trial_1.txt").read_text(encoding="utf-8") == REPLY.replace("\r\n", "\n")
    assert (manual / "m" / "task_02" / "trial_1.txt").read_text(encoding="utf-8") == ""


def test_refuses_an_empty_clipboard_or_the_prompt_itself(tmp_path):
    manual = make_manual(tmp_path)
    prompt = (manual / "prompts" / "task_01.txt").read_text(encoding="utf-8")
    saved, _ = run(manual, ["", "", "q"], ["", prompt], trial=1)
    assert saved == 0
    assert (manual / "m" / "task_01" / "trial_1.txt").read_text(encoding="utf-8") == ""


def test_a_reply_identical_to_a_saved_one_is_saved_only_when_confirmed(tmp_path):
    manual = make_manual(tmp_path)
    (manual / "m" / "task_01" / "trial_1.txt").write_text(REPLY.replace("\r\n", "\n"), encoding="utf-8")
    target = manual / "m" / "task_02" / "trial_1.txt"
    saved, _ = run(manual, ["", "n", "q"], [REPLY])
    assert saved == 0 and target.read_text(encoding="utf-8") == ""
    saved, _ = run(manual, ["", "y", "q"], [REPLY])
    assert saved == 1 and target.read_text(encoding="utf-8") == REPLY.replace("\r\n", "\n")


def test_a_reply_without_a_json_block_is_saved_only_when_confirmed(tmp_path):
    manual = make_manual(tmp_path)
    saved, _ = run(manual, ["", "n", "", "y", "q"], ["no block here", "no block here"], trial=1)
    assert saved == 1
    assert (manual / "m" / "task_01" / "trial_1.txt").read_text(encoding="utf-8") == "no block here"
