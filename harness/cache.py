"""Content-addressed response cache so an interrupted run can resume without paying twice.

The key covers (model settings, messages, trial index), so different trials of the same
prompt are separate entries: the cache de-duplicates reruns, it never shares answers
between trials. API errors are never cached.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

DEFAULT_DIR = Path(__file__).resolve().parents[1] / ".cache" / "responses"


class ResponseCache:
    def __init__(self, root: Path = DEFAULT_DIR, enabled: bool = True):
        self.root, self.enabled = root, enabled

    @staticmethod
    def key(settings: dict, messages: list[dict], trial: int) -> str:
        blob = json.dumps({"settings": settings, "messages": messages, "trial": trial}, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[dict]:
        path = self.root / f"{key}.json"
        if self.enabled and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def put(self, key: str, value: dict) -> None:
        if not self.enabled:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / f"{key}.json").write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
