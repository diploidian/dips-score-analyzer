"""The projectArthas addon's saved log (dipsScoreLog), as runs, segments, anchors and lines.

The line format is defined at the top of dips-Score/Log.lua; times in Clock.lua.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import luadata

SUPPORTED_VERSION = 1


@dataclass(slots=True)
class Line:
    t: int            # ms since the segment's t0
    code: str         # "A", "M", "CK", ...
    fields: list[str]

    def f(self, i: int, default: str = "") -> str:
        return self.fields[i] if i < len(self.fields) else default

    def num(self, i: int) -> int | None:
        v = self.f(i)
        try:
            return int(v)
        except ValueError:
            return None


@dataclass(slots=True)
class Anchor:
    epoch: int        # time() just after the tick
    wall: datetime    # that second, local time (naive, like the combat log)
    ms: float         # ms since the segment's t0 when that second began
    err: float        # +/- ms


@dataclass
class Segment:
    t0: float
    anchors: list[Anchor]
    lines: list[Line]
    full: bool = False


@dataclass
class Run:
    id: str
    char: str
    zone: str
    kind: str
    difficulty: int | None
    instance_id: int | None
    started: int
    ended: int | None
    segments: list[Segment] = field(default_factory=list)
    parts: list[str] = field(default_factory=list)   # ids of the saved runs merged into this one

    @property
    def end_estimate(self) -> int:
        """when it ended (time()): saved, or worked out from its longest segment"""
        if self.ended:
            return int(self.ended)
        longest = max((s.lines[-1].t for s in self.segments if s.lines), default=0)
        return self.started + int(longest / 1000)

    @property
    def player_name(self) -> str:
        return self.char.split(" - ")[0]

    @property
    def start_time(self) -> datetime:
        return datetime.fromtimestamp(self.started)

    @property
    def line_count(self) -> int:
        return sum(len(s.lines) for s in self.segments)


def _parse_line(s: str) -> Line | None:
    parts = s.split(",")
    if len(parts) < 2 or not parts[0].isdigit():
        return None
    return Line(int(parts[0]), parts[1], parts[2:])


def _parse_anchor(s: str) -> Anchor | None:
    try:
        epoch, wall, ms, err = s.split(",")
        return Anchor(int(epoch), datetime.strptime(wall, "%Y-%m-%d %H:%M:%S"), float(ms), float(err))
    except ValueError:
        return None


def _as_list(v) -> list:
    if isinstance(v, list):
        return v
    if isinstance(v, dict):  # a sparse table: keep the numbered entries in order
        return [v[k] for k in sorted(k for k in v if isinstance(k, int))]
    return []


def parse_runs(data: dict) -> list[Run]:
    log = data.get("dipsScoreLog")
    if not isinstance(log, dict):
        return []
    if log.get("version") != SUPPORTED_VERSION:
        raise ValueError(f"dipsScoreLog version {log.get('version')} (this reads {SUPPORTED_VERSION})")
    runs = []
    for r in _as_list(log.get("runs")):
        if not isinstance(r, dict):
            continue
        run = Run(
            id=str(r.get("id", "?")), char=str(r.get("char", "?")), zone=str(r.get("zone", "?")),
            kind=str(r.get("kind", "?")), difficulty=r.get("difficulty"), instance_id=r.get("instanceID"),
            started=int(r.get("started", 0)), ended=r.get("ended"),
        )
        for s in _as_list(r.get("segments")):
            if not isinstance(s, dict):
                continue
            anchors = [a for a in map(_parse_anchor, _as_list(s.get("anchors"))) if a]
            lines = [ln for ln in map(_parse_line, _as_list(s.get("lines"))) if ln]
            run.segments.append(Segment(float(s.get("t0", 0)), anchors, lines, bool(s.get("full"))))
        runs.append(run)
    return runs


def load_runs(path: str | Path) -> list[Run]:
    return parse_runs(luadata.load(path))


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _spells(lines: list) -> dict[str, dict]:
    """"spellID,cooldownMs,harm,name" -> name: {cd seconds | None, harm}; ranks of a spell share a name"""
    out: dict[str, dict] = {}
    for s in lines:
        parts = str(s).split(",", 3)
        if len(parts) < 4 or not parts[3]:
            continue
        ms, harm = _int(parts[1]), {"1": True, "0": False}.get(parts[2])
        cd = None if ms is None else ms / 1000
        old = out.setdefault(parts[3], {"cd": cd, "harm": harm})
        if cd is not None and (old["cd"] is None or cd > old["cd"]):
            old["cd"] = cd
        if harm is not None:
            old["harm"] = bool(old["harm"]) or harm
    return out


def _pulls(lines: list) -> list[tuple[datetime, int, int]]:
    """"time(),lowestPercent,brokenCount" at each pull -> (local time, lowest durability %, broken items)"""
    out = []
    for s in lines:
        parts = [_int(x) for x in str(s).split(",")]
        if len(parts) == 3 and None not in parts:
            out.append((datetime.fromtimestamp(parts[0]), parts[1], parts[2]))
    return out


def load_char(path: str | Path) -> dict | None:
    """the character snapshot (Char.lua) in one saved file, or None; parts that are missing or odd come out empty.
    "pulls" is the gear wear at each pull, kept beside the snapshot (dipsScoreLog.pulls)."""
    log = luadata.load(path).get("dipsScoreLog")
    c = log.get("char") if isinstance(log, dict) else None
    if not isinstance(c, dict) or not c.get("guid"):
        return None
    gear = {}
    for s in _as_list(c.get("gear")):
        slot, _, rest = str(s).partition(",")
        if _int(slot) is not None:
            gear[_int(slot)] = _int(rest.partition(",")[2])
    talents = []
    for s in _as_list(c.get("talents")):
        parts = str(s).split(",")
        if len(parts) >= 3 and _int(parts[-1]) is not None:
            talents.append((",".join(parts[1:-1]), _int(parts[-1])))
    points = [t for t in talents if t[1] > 0]
    sheet = _sheet(c)
    return {"guid": str(c["guid"]), "name": c.get("name"), "class": c.get("class"), "race": c.get("race"),
            "level": _int(c.get("level")), "taken": _int(c.get("taken")),
            "geartaken": _int(c.get("geartaken")) or _int(c.get("taken")),     # when what is worn was read
            "spells": _spells(_as_list(c.get("spells"))), "gear": gear, "talents": talents,
            "pulls": _pulls(_as_list(log.get("pulls"))), **sheet,
            "spec": max(points, key=lambda t: t[1])[0] or None if points else None}


def _float(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _sheet(c: dict) -> dict:
    """the character sheet's lists (Sheet.lua), each empty when missing or odd: "spell_ids" {id: name}, "stats" {key: value, or None when the game
    hides it}, "items" {slot: {"id", "quality", "enchant", "name"}}, "itemstats" {slot: {KEY: value}}, "wear" {slot: (durability, most)}, "tips" {slot: [(active, left, right)]}
    the item's whole tooltip (a slot whose lines are another item's is left out), "ranks" {spell id:
    rank}, "points" [{"kind", "tree", "node", "rank", "max", "name"}], "trees" [{"kind", "tree", "nodes", "with", "left"}],
    "skills" [{"name", "level", "max"}]"""
    rows = lambda key, n: [p for s in _as_list(c.get(key)) if len(p := str(s).split(",", n - 1)) == n]  # noqa: E731
    stats = {k: None if v == "?" else _float(v) for k, v in rows("stats", 2) if v == "?" or _float(v) is not None}
    items, itemstats = {}, {}
    for slot, iid, quality, enchant, name in rows("items", 5):
        if _int(slot) is not None:
            items[_int(slot)] = {"id": _int(iid), "quality": _int(quality), "enchant": _int(enchant), "name": name}
    for slot, key, v in rows("itemstats", 3):
        if _int(slot) is not None and _float(v) is not None:
            itemstats.setdefault(_int(slot), {})[key] = _float(v)
    ranks = {_int(i): r for i, r in rows("ranks", 2) if _int(i) is not None and r}
    if stats.get("str") == 0:           # read at a real logout, where the game answers 0 to everything
        stats = {}
    wear = {_int(s): (_int(left), _int(most)) for s, left, most in rows("wear", 3) if None not in (_int(s), _int(left), _int(most))}
    tips: dict[int, list[tuple[bool, str, str]]] = {}
    for slot, iid, kind, line in rows("tips", 4):
        if _int(slot) not in items or items[_int(slot)]["id"] != _int(iid):
            continue
        lines = tips.setdefault(_int(slot), [])
        if kind == "R" and lines:
            lines[-1] = (*lines[-1][:2], line.strip())
        elif kind != "R":
            lines.append((not kind.endswith("!"), line.rstrip(), ""))     # a leading space is a set's piece
    points = [{"kind": k, "tree": _int(t), "node": _int(n), "rank": _int(r), "max": _int(m), "name": name}
              for k, t, n, r, m, name in rows("points", 6) if _int(r) is not None]
    trees = [{"kind": k, "tree": _int(t), "nodes": _int(n), "with": _int(w), "left": _int(left)}
             for k, t, n, w, left in rows("trees", 5)]
    skills = [{"name": n, "level": _int(lv), "max": _int(m)} for lv, m, n in rows("skills", 3) if _int(lv) is not None and n]
    ids = {_int(i): name for i, _, _, name in rows("spells", 4) if _int(i) is not None and name}
    return {"spell_ids": ids, "stats": stats, "items": items, "itemstats": itemstats, "tips": tips, "wear": wear, "ranks": ranks, "points": points, "trees": trees,
            "skills": skills}


def load_types(path: str | Path) -> dict[str, str]:
    """enemy name -> creature type ("Undead", "Demon", ...) from the account-wide saved file's dipsScoreDB.types
    (Types.lua); {} when the file or the table is missing or broken. Paths.account_saved_files() lists the files.
    History.load_types merges it over every account, for the spells that need a creature type (usable.py)."""
    try:
        db = luadata.load(path).get("dipsScoreDB")
    except (OSError, ValueError):
        return {}
    types = db.get("types") if isinstance(db, dict) else None
    if not isinstance(types, dict):
        return {}
    return {k: v for k, v in types.items() if isinstance(k, str) and isinstance(v, str) and k and v}
