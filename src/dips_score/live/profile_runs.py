"""What the Profile takes from each recorded run (profile_view.run_row), kept for 60 days because the add-on keeps only
its last runs: %APPDATA%/dips-score/profile_runs.json, {character guid: {run id: row, its start as ISO time}}.
Loaded and saved as the slices are (profile_history.load and save)."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from .. import removed

KEEP = timedelta(days=60)


def file(paths) -> Path:
    return paths.data_dir / "profile_runs.json"


def merge(stored: dict, current: dict[str, dict]) -> dict[str, dict]:
    """the stored rows with the current ones over them, by run id; without the deleted runs, and without a visit's
    later piece saved alone (the add-on dropped its first) when the whole visit has a row"""
    rows = {rid: {**r, "start": datetime.fromisoformat(r["start"])} for rid, r in stored.items()} | current
    pieces = {p for r in rows.values() for p in r["parts"][1:]}
    return {rid: r for rid, r in rows.items() if rid not in pieces and not removed.IDS.intersection(r["parts"])}


def pack(rows: dict[str, dict], now: datetime) -> dict:
    """rows as they are stored, without those over KEEP old"""
    return {rid: {**r, "start": r["start"].isoformat()} for rid, r in rows.items() if now - r["start"] <= KEEP}
