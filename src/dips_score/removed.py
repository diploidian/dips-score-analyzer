"""Runs and fights you deleted (removed.json): skipped on load, as the game rewrites its saved file and a replay
would bring a fight back."""
from __future__ import annotations

import json
from pathlib import Path

IDS: set[str] = set()     # in use (load fills it): deleted run and fight ids


def load(path: Path | None):
    IDS.clear()
    if path and path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return
        if isinstance(saved, list):
            IDS.update(x for x in saved if isinstance(x, str))


def add(path: Path, ids):
    IDS.update(ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(IDS), indent=0), encoding="utf-8")
