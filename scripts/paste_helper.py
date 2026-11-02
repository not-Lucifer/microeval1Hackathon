"""Collect chat-app replies with less clicking: each prompt goes to the clipboard, each reply
comes back from it.

    python scripts/paste_helper.py chatgpt-think              # every empty trial file, trial 1 of all tasks first
    python scripts/paste_helper.py chatgpt-think --trial 1    # only trial 1

For each empty manual/<name>/task_XX/trial_N.txt:
  1. the script copies manual/prompts/task_XX.txt to the clipboard;
  2. you open a NEW chat in the app, paste it, and wait for the whole reply;
  3. you copy the reply with the app's copy button and press Enter here;
  4. the script saves the clipboard to the trial file exactly as copied (Windows line endings
     become plain newlines; nothing else changes).

You still use the chat app yourself, by hand: the script only moves text between the clipboard
and the files. It never shows a grade, so no reply is kept or redone because of its score.
At the prompt: Enter = save the copied reply, s = skip this one, r = copy the prompt again, q = quit.
Then fill in manual/<name>/info.yaml and run: python run_eval.py --import-manual manual/
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / "manual"


def pending(manual_dir: Path, name: str, trial: Optional[int] = None) -> list[Path]:
    """Empty trial files of one model folder, trial 1 of every task first, then trial 2, ..."""
    files = []
    for path in (manual_dir / name).glob("task_*/trial_*.txt"):
        n = int(re.fullmatch(r"trial_(\d+)\.txt", path.name).group(1))
        if (trial is None or n == trial) and not path.read_text(encoding="utf-8").strip():
            files.append((n, path.parent.name, path))
    return [path for _, _, path in sorted(files)]


def reply_problem(text: str, prompt: str) -> Optional[str]:
    """Why the clipboard cannot be a reply: empty, or still the prompt (the reply was not copied)."""
    if not text.strip():
        return "the clipboard is empty: copy the reply with the app's copy button first"
    if text.strip() == prompt.strip() or prompt.strip()[:200] in text:
        return "the clipboard still holds the prompt: copy the model's reply first"
    return None


def save_reply(path: Path, text: str) -> None:
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def collect(manual_dir: Path, name: str, trial: Optional[int], get_clip: Callable[[], str],
            set_clip: Callable[[str], None], ask: Callable[[str], str] = input) -> int:
    """Walk the empty trial files; returns how many replies were saved."""
    todo = pending(manual_dir, name, trial)
    print(f"{len(todo)} empty trial file(s) in {manual_dir / name}. Every trial needs a NEW chat, "
          "the same model and reasoning setting, and tools/search/memory off.")
    saved = 0
    for path in todo:
        prompt = (manual_dir / "prompts" / f"{path.parent.name}.txt").read_text(encoding="utf-8")
        set_clip(prompt)
        print(f"\n{path.parent.name} {path.stem.replace('_', ' ')}: prompt copied. Paste it into a NEW chat, "
              "copy the whole reply, then press Enter (s = skip, r = copy prompt again, q = quit).")
        while True:
            command = ask("> ").strip().lower()
            if command == "q":
                print(f"stopped; {saved} saved")
                return saved
            if command == "s":
                break
            if command == "r":
                set_clip(prompt)
                print("prompt copied again")
                continue
            text = get_clip()
            problem = reply_problem(text, prompt)
            if problem:
                print(problem)
                continue
            if "```json" not in text.lower() and ask("no ```json block in the copied text; save anyway? [y/N] ").strip().lower() != "y":
                continue
            save_reply(path, text)
            saved += 1
            print(f"saved {path.relative_to(manual_dir.parent)} ({len(text)} characters)")
            break
    print(f"\ndone: {saved} saved. Fill in {manual_dir / name / 'info.yaml'}, then run "
          "python run_eval.py --import-manual manual/")
    return saved


def system_clipboard() -> tuple[Callable[[], str], Callable[[str], None]]:
    """(get, put) for the system clipboard, standard library only. Reading uses tkinter. Writing
    uses PowerShell's Set-Clipboard on Windows and pbcopy on macOS, because text put there by
    tkinter is handed to other apps only while tkinter's event loop runs, not while this script
    waits for Enter (tried and confirmed on Windows)."""
    import subprocess
    import tkinter
    root = tkinter.Tk()
    root.withdraw()

    def get() -> str:
        try:
            return root.clipboard_get()
        except tkinter.TclError:
            return ""

    def put(text: str) -> None:
        if sys.platform == "win32":
            subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::InputEncoding = "
                            "[Text.UTF8Encoding]::new($false); Set-Clipboard -Value ([Console]::In.ReadToEnd())"],
                           input=text.encode("utf-8"), check=True)
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        else:
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
    return get, put


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="model folder under manual/, e.g. chatgpt-think")
    ap.add_argument("--trial", type=int, help="only this trial number")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not (MANUAL / args.name).is_dir() or not (MANUAL / "prompts").is_dir():
        print(f"no manual/{args.name}/ or manual/prompts/: run python run_eval.py --new-manual {args.name} --trials 3 first")
        return 1
    get_clip, set_clip = system_clipboard()
    collect(MANUAL, args.name, args.trial, get_clip, set_clip)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
