"""Every fight summed up, kept on disk: %APPDATA%/dips-score/fights.jsonl (one fight per line, newest
last), and the cooldowns learned from your casts (cooldowns.json).

`Live` puts it together: follow the log, tell fights apart, sum each one up, save it, and hand it on (to
the overlay and the Fights page). `replay()` does the same for log files already on disk.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..config import Paths
from .summary import learn_cooldowns, summarize
from .tail import LogTail
from .tracker import Tracker

KEEP = 5000      # fights kept in the file


class History:
    def __init__(self, paths: Paths):
        self.file = paths.data_dir / "fights.jsonl"
        self.cd_file = paths.data_dir / "cooldowns.json"
        self.fights: list[dict] = []
        self.cooldowns: dict[int, float] = {}
        self.load()

    def load(self):
        self.fights = []
        if self.file.exists():
            for line in self.file.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    self.fights.append(json.loads(line))
                except ValueError:
                    continue
        if self.cd_file.exists():
            try:
                self.cooldowns = {int(k): float(v) for k, v in json.loads(self.cd_file.read_text()).items()}
            except (ValueError, OSError):
                self.cooldowns = {}

    def ids(self) -> set[str]:
        return {f.get("id") for f in self.fights}

    def add(self, fight: dict) -> bool:
        """save a fight; one with the same id (a combat that carried on) replaces it. True if it replaced."""
        self.file.parent.mkdir(parents=True, exist_ok=True)
        for i, old in enumerate(self.fights):
            if old.get("id") == fight["id"]:
                self.fights[i] = fight
                self._rewrite()
                return True
        self.fights.append(fight)
        if len(self.fights) > KEEP:
            self.fights = self.fights[-KEEP:]
            self._rewrite()
        else:
            with open(self.file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(fight) + "\n")
        return False

    def _rewrite(self):
        self.file.write_text("".join(json.dumps(f) + "\n" for f in self.fights), encoding="utf-8")

    def save_cooldowns(self):
        self.cd_file.parent.mkdir(parents=True, exist_ok=True)
        self.cd_file.write_text(json.dumps({str(k): v for k, v in self.cooldowns.items()}, indent=0))


class Live:
    """call poll() every half second or so; it returns the fights that just finished (summed up)"""

    def __init__(self, paths: Paths, history: History | None = None, from_start: bool = False):
        self.tail = LogTail(paths.logs, from_start=from_start)
        self.tracker = Tracker()
        self.history = history or History(paths)
        self.lag: float | None = None      # seconds between the game's last log line and now

    def poll(self) -> list[dict]:
        lines = self.tail.poll()
        done = self.tracker.feed_lines(lines)
        if lines and self.tracker.log_now:
            self.lag = (datetime.now() - self.tracker.log_now).total_seconds()
        late = self.tracker.tick()
        if late:
            done.append(late)
        return [s for s in (self._finish(f) for f in done) if s]

    def _finish(self, f) -> dict | None:
        me = self.tracker.me
        if not me:
            return None
        if learn_cooldowns(f, me, self.history.cooldowns):
            self.history.save_cooldowns()
        earlier = [h for h in self.history.fights if h.get("id") != _fight_id(f)]
        s = summarize(f, me, self.tracker.me_name, self.history.cooldowns, earlier)
        if s:
            s["updated"] = self.history.add(s)       # a carried-on combat: its card is updated
            return s
        return None


def replay(paths: Paths, files: list[Path]) -> int:
    """sum up every fight in log files already on disk (oldest first) into the history; returns how many"""
    h = History(paths)
    n = 0
    for path in files:
        tr = Tracker()
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                for f in tr.feed_lines([line]):
                    n += _keep(h, tr, f)
        last = tr.flush()
        if last:
            n += _keep(h, tr, last)
    return n


def _keep(h: History, tr: Tracker, f) -> int:
    if not tr.me:
        return 0
    if learn_cooldowns(f, tr.me, h.cooldowns):
        h.save_cooldowns()
    known = _fight_id(f) in h.ids()
    s = summarize(f, tr.me, tr.me_name, h.cooldowns, [x for x in h.fights if x.get("id") != _fight_id(f)])
    if s:
        h.add(s)
        return 0 if known else 1
    return 0


def _fight_id(f) -> str:
    return f"{f.start:%Y%m%d%H%M%S%f}"
