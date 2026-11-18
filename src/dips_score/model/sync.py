"""Putting the addon's lines on the combat log's clock.

Each segment's anchors pin its millisecond counter to the wall clock (see dips-Score/Clock.lua).
Between anchors the offset is interpolated, so the two clocks drifting apart over a long run is
corrected. Then the addon's own successful casts are matched against the combat log's
SPELL_CAST_SUCCESS lines for the player: the median gap is a final correction, and how tight the
matches are says how good the sync is.
"""
from __future__ import annotations

import bisect
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..sources.savedvars import Segment

MATCH_WINDOW_MS = 1500   # a cast this far from its log line isn't the same cast
MIN_MATCHES = 5          # fewer than this and the correction isn't trusted


@dataclass
class SyncReport:
    casts: int = 0           # the addon's successful casts in the segment
    matched: int = 0         # found in the combat log
    correction_ms: float = 0.0
    p10_ms: float = 0.0      # spread of the matches after correction
    p90_ms: float = 0.0
    anchors: int = 0

    @property
    def ok(self) -> bool:
        return self.matched >= MIN_MATCHES

    def describe(self) -> str:
        if not self.anchors:
            return "no clock anchor: times are a guess"
        if not self.matched:
            return f"{self.anchors} anchors, no casts matched in the combat log"
        if not self.ok:
            return f"{self.anchors} anchors, {self.matched}/{self.casts} casts matched (too few to correct)"
        return (f"{self.matched}/{self.casts} casts matched, corrected {self.correction_ms:+.0f} ms, "
                f"spread {self.p10_ms:+.0f}..{self.p90_ms:+.0f} ms")


class SegmentClock:
    """ms since a segment's t0 -> local wall time."""

    def __init__(self, seg: Segment, fallback: datetime | None = None):
        # offset = wall (as ms since epoch, local) - segment ms, at each anchor
        pts = sorted((a.ms, a.wall.timestamp() * 1000 - a.ms) for a in seg.anchors)
        self._ms = [p[0] for p in pts]
        self._off = [p[1] for p in pts]
        self._fallback = fallback
        self.correction_ms = 0.0

    @property
    def anchored(self) -> bool:
        return bool(self._ms)

    def offset_at(self, t: float) -> float:
        ms, off = self._ms, self._off
        if not ms:
            return (self._fallback.timestamp() * 1000) if self._fallback else 0.0
        if len(ms) == 1 or t <= ms[0]:
            return off[0]
        if t >= ms[-1]:
            return off[-1]
        i = bisect.bisect_right(ms, t)
        f = (t - ms[i - 1]) / (ms[i] - ms[i - 1])
        return off[i - 1] + f * (off[i] - off[i - 1])

    def wall(self, t: float) -> datetime:
        return datetime.fromtimestamp((t + self.offset_at(t) + self.correction_ms) / 1000)


def refine(clock: SegmentClock, seg: Segment, log_casts: dict[int, list[datetime]],
           skip: frozenset[int] = frozenset()) -> SyncReport:
    """Matches the segment's CK lines to the player's SPELL_CAST_SUCCESS times (by spell id) and
    applies the median gap as a correction. log_casts: spell id -> sorted times. skip: spells
    not to match on (wand shots repeat every ~1.5 s, close enough to match the wrong shot)."""
    rep = SyncReport(anchors=len(seg.anchors))
    gaps = []
    for ln in seg.lines:
        if ln.code != "CK":
            continue
        sid = ln.num(0)
        if sid is None or sid in skip:
            continue
        rep.casts += 1
        times = log_casts.get(sid)
        if not times:
            continue
        w = clock.wall(ln.t)
        i = bisect.bisect_left(times, w)
        best = None
        for c in times[max(0, i - 1):i + 1]:
            d = (c - w) / timedelta(milliseconds=1)
            if best is None or abs(d) < abs(best):
                best = d
        if best is not None and abs(best) <= MATCH_WINDOW_MS:
            gaps.append(best)
    rep.matched = len(gaps)
    if len(gaps) >= MIN_MATCHES:
        med = statistics.median(gaps)
        clock.correction_ms += med
        rep.correction_ms = med
        rest = sorted(g - med for g in gaps)
        rep.p10_ms, rep.p90_ms = rest[len(rest) // 10], rest[len(rest) * 9 // 10]
    return rep
