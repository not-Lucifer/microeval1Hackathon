"""Secrets and repo hygiene: the scanner works, and the repository itself is clean."""
from pathlib import Path

import check_secrets

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", ".cache", "__pycache__", ".pytest_cache", "dist"}


def fake_key() -> str:
    # built at runtime so no literal key-shaped string exists in the repository
    return "sk-" + "or-v1-" + "0123456789abcdef" * 3


def test_scanner_detects_keys_and_env_files():
    assert check_secrets.scan_text("x.py", f'API = "{fake_key()}"')
    assert check_secrets.scan_text(".env", "OPENROUTER_API_KEY=" + "A1b2C3d4E5f6G7h8I9j0")
    assert check_secrets.scan_blob(".env", b"OPENROUTER_API_KEY=\n")
    assert check_secrets.scan_blob("clip.mp4", b"\x00\x01")
    assert not check_secrets.scan_text(".env.example", "OPENROUTER_API_KEY=")
    assert not check_secrets.scan_text("README.md", "set OPENROUTER_API_KEY=your_key_here in .env")
    assert check_secrets.is_forbidden_env_file("config/.env.local")
    assert not check_secrets.is_forbidden_env_file(".env.example")


def test_repository_files_are_clean():
    findings = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if path.is_dir() or SKIP_DIRS & set(rel.parts) or rel.suffix == ".pdf" or rel.name == ".env":
            continue
        findings += check_secrets.scan_blob(str(rel), path.read_bytes())
    assert findings == []


def test_gitignore_protects_secrets_and_bulk():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in (".env", ".venv/", ".cache/", "video/", "*.mp4"):
        assert entry in ignored
    assert (ROOT / ".env.example").read_text(encoding="utf-8").strip().endswith("OPENROUTER_API_KEY=")
