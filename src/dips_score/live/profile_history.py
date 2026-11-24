"""The finished 15-day slices of the profile, saved once and never rewritten: %APPDATA%/dips-score/
profile_history.json (beside fights.jsonl), {character guid: [slice, ...] oldest first}, each slice
{"from", "to" (ISO times, the window (from, to]), "fights", "label", "figures" (profile.figures)}.

file(paths) is the path; load(path) -> dict ({} when missing), or None when it can't be read now (locked, or broken
and set aside): nothing may be saved over it then; update(saved, fights, char, book, runs, now, types=None) adds the
slices that have finished for the newest fight's character and returns them; save(path, saved) writes atomically. A
block is saved once its end is 15 days back, so it has left Now. A slice with fewer than MIN_FIGHTS fights is skipped.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from .profile import SLICE, figures

MIN_FIGHTS = 10


def file(paths) -> Path:
    return paths.data_dir / "profile_history.json"


def load(path: Path) -> dict | None:
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            return saved
    except FileNotFoundError:
        return {}
    except OSError:                # locked: read again next time
        return None
    except ValueError:
        pass
    try:                           # broken: kept aside, and the next time starts a new one
        path.rename(path.with_name(f"{path.stem}.bad-{datetime.now():%Y%m%d-%H%M%S}.json"))
    except OSError:
        pass
    return None


def save(path: Path, saved: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(saved), encoding="utf-8")
    os.replace(tmp, path)          # a half-written file is never read


def _slice(mine, char, book, runs, lo: datetime, hi: datetime, types=None) -> dict | None:
    fig = figures(mine, char, book, runs, lo, hi, types)
    if fig["fights"] < MIN_FIGHTS:
        return None
    return {"from": lo.isoformat(), "to": hi.isoformat(), "fights": fig["fights"], "label": fig["label"],
            "figures": fig}


def update(saved: dict, fights: list[dict], char: dict | None, book: dict | None, runs: list[dict] | None,
           now: datetime, types: dict | None = None) -> list[dict]:
    """add the finished slices of the newest fight's character to saved (in place); returns the ones added"""
    if not fights:
        return []
    me = fights[-1]["me"]
    mine = [f for f in fights if f["me"] == me]
    book, runs = book or {}, runs or []
    slices = saved.setdefault(me, [])
    added = []
    if slices:          # carry on from the last saved slice's end, one block at a time, while a block has finished
        hi = datetime.fromisoformat(slices[-1]["to"]) + SLICE
        while hi <= now - SLICE:            # it has left Now
            if s := _slice(mine, char, book, runs, hi - SLICE, hi, types):
                added.append(s)
            hi += SLICE
        slices.extend(added)
    else:               # first run: blocks counted back from now, back past the oldest fight
        oldest = min(datetime.fromisoformat(f["start"]) for f in mine)
        hi = now - SLICE
        while hi >= oldest:
            if s := _slice(mine, char, book, runs, hi - SLICE, hi, types):
                added.insert(0, s)
            hi -= SLICE
        slices.extend(added)
    if not slices:
        del saved[me]
    return added
