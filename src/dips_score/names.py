"""Your names for runs and fights (names.json): one file for both, as run ids and fight ids can't collide."""
from __future__ import annotations

import json
from pathlib import Path

from . import store

NAMES: dict[str, str] = {}     # in use (load fills it): run or fight id -> your name for it


def load(path: Path | None):
    NAMES.clear()
    if path and path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return
        if isinstance(saved, dict):
            NAMES.update({k: v for k, v in saved.items() if isinstance(v, str) and v})


def rename(path: Path, id: str, text: str):
    """name it text; empty text takes the name off"""
    text = text.strip()
    if text:
        NAMES[id] = text
    else:
        NAMES.pop(id, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    store.write_file(path, json.dumps(NAMES, indent=1, ensure_ascii=False))


def get(id: str) -> str:
    return NAMES.get(id, "")


def titled(id: str, original: str) -> str:
    """the original beside your name for it ("Scarlet Monastery — guild run with Anna")"""
    return f"{original} — {NAMES[id]}" if id in NAMES else original
