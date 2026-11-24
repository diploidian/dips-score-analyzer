"""The finished 15-day slices of the profile, saved once and never rewritten: %APPDATA%/dips-score/
profile_history.json (beside fights.jsonl), {character guid: [slice, ...] oldest first}, each slice
{"from", "to" (ISO times, the window (from, to]), "fights", "label", "title", "traits" ({key: score}), "figures"
(profile.figures)}; one saved before 0.18 has no title and no traits.

file(paths) is the path; load(path) -> dict ({} when missing), or None when it can't be read now (locked, or broken
and set aside): nothing may be saved over it then; update(saved, fights, char, book, runs, now, types=None) adds the
slices that have finished for the newest fight's character and returns them; save(path, saved) writes atomically. A
block is saved once its end is 15 days back, so it has left Now. A slice with fewer than MIN_FIGHTS fights is skipped,
and so is one with a fight that lacks profile.CURRENT (summed up before 0.18.0: its title would be from stale data) until
a replay has summed it up again. One already saved by 0.16 or 0.17 stays as it is. While nothing is saved the first-run fill-in is tried again each time, so a replay fills everything in; once
a slice exists, the incomplete blocks before it stay unsaved for good.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .history import write_file
from .profile import CURRENT, SLICE, figures

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
    write_file(path, json.dumps(saved))


def _slice(mine, char, book, runs, lo: datetime, hi: datetime, types=None) -> dict | None:
    if any(CURRENT not in f for f in mine if lo < datetime.fromisoformat(f["start"]) <= hi):
        return None
    fig = figures(mine, char, book, runs, lo, hi, types)
    if fig["fights"] < MIN_FIGHTS:
        return None
    return {"from": lo.isoformat(), "to": hi.isoformat(), "fights": fig["fights"], "label": fig["label"],
            "title": fig["title"], "traits": {t["key"]: t["score"] for t in fig["traits"]}, "figures": fig}


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
