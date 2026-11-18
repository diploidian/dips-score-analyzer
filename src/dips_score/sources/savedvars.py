"""The dips-Score addon's saved log (dipsScoreLog), as runs, segments, anchors and lines.

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
