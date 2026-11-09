"""Secret and hygiene scanner, used by the git pre-commit hook.

Usage:
    python scripts/check_secrets.py            # scan every git-tracked file
    python scripts/check_secrets.py --staged   # scan the staged (index) version of staged files
    python scripts/check_secrets.py FILE...    # scan the given files

Exit code 1 (and a list of findings) if any of these are found:
  * API-key-like strings (OpenRouter/OpenAI/Anthropic ``sk-...``, GitHub tokens, AWS keys)
  * a ``*_API_KEY=`` assignment with a real-looking (non-placeholder) value
  * private-key headers
  * any ``.env`` file other than ``.env.example``
  * video files, or any file larger than 5 MB (submission zip limit is 50 MB, no videos)

Only the standard library is used so the hook works before the venv exists.
Fake keys in tests are built by string concatenation so this file and the tests never
contain a literal match.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

MAX_FILE_BYTES = 5 * 1024 * 1024
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("sk- style API key", re.compile(r"sk-(?:or-v1-|proj-|ant-)?[A-Za-z0-9_\-]{20,}")),
    (
        "API key assignment with a real-looking value",
        re.compile(
            r"(?:OPENROUTER|OPENAI|ANTHROPIC)_API_KEY\s*[=:]\s*['\"]?(?!your)[A-Za-z0-9_\-]{16,}"
        ),
    ),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def is_forbidden_env_file(path: str) -> bool:
    """True for ``.env`` and ``.env.<anything>`` except the committed ``.env.example``."""
    name = Path(path).name
    return (name == ".env" or name.startswith(".env.")) and name != ".env.example"


def scan_text(path: str, text: str) -> list[str]:
    """Return one finding per secret-pattern match in ``text`` (line numbers are 1-based)."""
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(f"{path}:{lineno}: {label}")
    return findings


def scan_blob(path: str, data: bytes) -> list[str]:
    """Hygiene + secret checks for one file's bytes."""
    findings = []
    if is_forbidden_env_file(path):
        findings.append(f"{path}: .env files must never be committed (use .env.example)")
    if Path(path).suffix.lower() in VIDEO_SUFFIXES:
        findings.append(f"{path}: video files are not allowed in the repo or the zip")
    if len(data) > MAX_FILE_BYTES:
        findings.append(f"{path}: file is {len(data) / 1e6:.1f} MB (limit 5 MB per file)")
    if b"\x00" not in data[:8192]:  # skip content scan for binary files
        findings.extend(scan_text(path, data.decode("utf-8", errors="replace")))
    return findings


def staged_files() -> list[str]:
    out = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [p for p in out.split("\0") if p]


def main(argv: list[str]) -> int:
    findings: list[str] = []
    if argv[:1] == ["--staged"]:
        for path in staged_files():
            blob = subprocess.run(["git", "show", f":{path}"], check=True, capture_output=True).stdout
            findings.extend(scan_blob(path, blob))
    else:
        paths = argv or [p for p in _git("ls-files", "-z").split("\0") if p]
        for path in paths:
            p = Path(path)
            if p.is_file():
                findings.extend(scan_blob(path, p.read_bytes()))

    if findings:
        print("check_secrets: BLOCKED. Fix these before committing or zipping:", file=sys.stderr)
        for f in findings:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("check_secrets: OK (no secrets, .env files, videos or oversized files found)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
