"""Every fight summed up, kept on disk: %APPDATA%/dips-score/fights.jsonl (one fight per line, newest
last), and a spell book per character learned from your casts (spells.json: character -> spell name ->
the shortest gaps between two casts, damage per cast, cast time, cost; see summary.py). The old shared
cooldowns.json is no longer read: `replay` learns the books again from the logs.

`Live` puts it together: follow the log, tell fights apart, sum each one up, save it, and hand it on (to
the overlay and the Fights page). `replay()` does the same for log files already on disk.
What you did for other players (helping.py) goes into help.jsonl beside them, one act per line.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from .. import removed, store
from ..config import Paths
from ..sources.savedvars import load_types
from .summary import gear_level, learn_cooldowns, new_entry, summarize
from .tail import LogTail
from .tracker import Tracker

KEEP = 5000      # fights kept in the file
KEEP_ACTS = 20000


def write_file(path: Path, text: str):
    """on disk before it takes the old file's place, so a half-written file is never read"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _start(f: dict) -> str:
    return f.get("start") or ""


class History:
    def __init__(self, paths: Paths):
        self.file = paths.data_dir / "fights.jsonl"
        self.spells_file = paths.data_dir / "spells.json"
        self.help_file = paths.data_dir / "help.jsonl"
        self.fights: list[dict] = []
        self.acts: dict[str, dict] = {}        # what you did for others, by id (every character's)
        self.books: dict[str, dict[str, dict]] = {}
        self.chars: dict[str, dict] = {}       # character snapshots from the add-on, by guid (not saved here)
        self.types: dict[str, str] = {}        # enemy name -> creature type, from the add-on (not saved here)
        self.load()

    def load(self):
        self.fights = []
        if self.file.exists():
            for line in self.file.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    f = json.loads(line)
                    if "ilvl" not in f:         # before 0.22 the log's average item level was saved as the level
                        f["ilvl"] = f.pop("level", None)
                    self.fights.append(f)
                except (ValueError, AttributeError, TypeError):
                    continue
        self.fights.sort(key=_start)       # a replay adds the older ones it finds last
        self.acts = {}
        if self.help_file.exists():
            for line in self.help_file.read_text(encoding="utf-8", errors="replace").splitlines()[-KEEP_ACTS:]:
                try:
                    act = json.loads(line)
                    self.acts[act["id"]] = act
                except (ValueError, KeyError, TypeError):
                    continue
        if self.spells_file.exists():
            try:
                self.books = json.loads(self.spells_file.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                self.books = {}

    def book(self, me: str) -> dict[str, dict]:
        """your spell book (spell name -> what's been learned about it)"""
        return self.books.setdefault(me, {})

    def set_char(self, char: dict):
        """take a character snapshot; its spells' base cooldowns go into that character's spell book"""
        self.chars[char["guid"]] = char
        book = self.book(char["guid"])
        for name, sp in char["spells"].items():
            book.setdefault(name, new_entry())["game_cd"] = sp["cd"]

    def load_types(self, files):
        """the enemies' creature types in the account-wide saved files (Paths.account_saved_files), merged"""
        for path in files:
            self.types.update(load_types(path))

    def tag(self, s: dict, me: str):
        """put the character's spec and gear level on a fight summary, when there is a snapshot"""
        char = self.chars.get(me)
        if char:
            s["spec"], s["gear"] = char.get("spec"), gear_level(char)

    def ids(self) -> set[str]:
        return {f.get("id") for f in self.fights}

    def add(self, fight: dict, save: bool = True) -> bool:
        """save a fight; one with the same id (a combat that carried on) replaces it. True if it replaced.
        save=False: only in memory (a replay writes the file once, at its end)"""
        if fight["id"] in removed.IDS:      # deleted: a replay or a carried-on combat doesn't bring it back
            return False
        self.file.parent.mkdir(parents=True, exist_ok=True)
        for i, old in enumerate(self.fights):
            if old.get("id") == fight["id"]:
                self.fights[i] = fight
                if save:
                    self._rewrite()
                return True
        self.fights.append(fight)
        if len(self.fights) > KEEP:
            self.fights = sorted(self.fights, key=_start)[-KEEP:]
            if save:
                self._rewrite()
        elif save:
            with open(self.file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(fight) + "\n")
        return False

    def helped(self, me: str) -> list[dict]:
        return [a for a in self.acts.values() if a["me"] == me]

    def add_acts(self, acts: list[dict]):
        """save the acts not known yet (a replay finds the live ones again)"""
        new = {a["id"]: a for a in acts if a["id"] not in self.acts}
        if not new:
            return
        self.acts |= new
        self.help_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.help_file, "a", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(a) + "\n" for a in new.values()))

    def remove(self, ids):
        self.fights = [f for f in self.fights if f.get("id") not in ids]
        self._rewrite()

    def _rewrite(self):
        write_file(self.file, "".join(json.dumps(f) + "\n" for f in self.fights))

    def save_books(self):
        self.spells_file.parent.mkdir(parents=True, exist_ok=True)
        self.spells_file.write_text(json.dumps(self.books, indent=0), encoding="utf-8")


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
        self.history.add_acts(self.tracker.take_acts())
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
        if learn_cooldowns(f, me, self.history.book(me)):
            self.history.save_books()
        earlier = [h for h in self.history.fights if h.get("id") != _fight_id(f)]
        s = summarize(f, me, self.tracker.me_name, self.history.book(me), earlier, self.history.types)
        if s and s["id"] not in removed.IDS:      # a deleted fight carrying on isn't shown again
            self.history.tag(s, me)
            s["updated"] = self.history.add(s)       # a carried-on combat: its card is updated
            return s
        return None


def replay(paths: Paths, files: list[Path]) -> tuple[int, int]:
    """sum up every fight in log files already on disk (oldest first) into the history; returns how many were added and
    how many saved ones were summed up again. The analysed runs are dropped: they were made with the old spell books."""
    h = History(paths)
    h.load_types(paths.account_saved_files())
    before, done = h.ids(), set()
    for path in files:
        tr = Tracker()
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                for f in tr.feed_lines([line]):
                    done.add(_keep(h, tr, f))
        last = tr.flush()
        if last:
            done.add(_keep(h, tr, last))
        h.add_acts(tr.take_acts())
    if done:
        h.save_books()
        h._rewrite()
        store.clear(paths.analysis_dir)
    return len(done & (h.ids() - before)), len(done & before)


def _keep(h: History, tr: Tracker, f) -> str | None:
    """the id of the fight summed up, if it was"""
    if not tr.me:
        return None
    learn_cooldowns(f, tr.me, h.book(tr.me))     # saved once, at the end of the replay
    s = summarize(f, tr.me, tr.me_name, h.book(tr.me), [x for x in h.fights if x.get("id") != _fight_id(f)], h.types)
    if s:
        h.tag(s, tr.me)
        old = next((x for x in h.fights if x.get("id") == s["id"]), {})
        for k in ("spec", "gear"):      # a replay has no snapshots: keep what the live fight was tagged with
            if s.get(k) is None and old.get(k) is not None:
                s[k] = old[k]
        h.add(s, save=False)
        return s["id"]
    return None


def _fight_id(f) -> str:
    return f"{f.start:%Y%m%d%H%M%S%f}"
