"""What the Timeline tab says about the stretch of the run it shows, as plain data (no Qt): the fight it shows, the
idle moments in it, longest first, and the verdict.

The idle intervals are the Activity score's own (the timeline's Data.idle is the run's metrics.idle_gaps), so the tab
and the scorecard count the same gaps."""
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field

from .debrief import fmt_time
from .model.pulls import LEAD_IN
from .scoring.metrics import IDLE_GAP

NONE = f"No idle moments of {IDLE_GAP:g} s or more"     # idle is only measured in combat
TIMES = {1: "once", 2: "twice"}


def idle_moments(idle: list[tuple[float, float]], window: tuple[float, float],
                 min_s: float = IDLE_GAP) -> list[tuple[float, float]]:
    """the idle intervals cut to window (start, end) that still last min_s or more, longest first (on a tie, the
    earlier first)"""
    a, b = window
    cut = [(max(s, a), min(e, b)) for s, e in idle]
    return sorted(((s, e) for s, e in cut if e - s >= min_s), key=lambda m: (m[0] - m[1], m[0]))


def fight_verdict(moments: list[tuple[float, float]]) -> str:
    """"Idle 3 times for 2.5 s or more — longest 10.9 s at 6:58." (moments: longest first)"""
    if not moments:
        return f"{NONE} in combat."
    s, e = moments[0]
    n = len(moments)
    if n == 1:
        return f"Idle once for {IDLE_GAP:g} s or more: {e - s:.1f} s at {fmt_time(s)}."
    return f"Idle {TIMES.get(n, f'{n} times')} for {IDLE_GAP:g} s or more — longest {e - s:.1f} s at {fmt_time(s)}."


@dataclass
class IdleView:
    moments: list[tuple[float, float]] = field(default_factory=list)     # longest first
    big: str = "0"                     # the seconds idle in them, the hero's figure
    verdict: str = ""
    gaps: str = ""                     # what the count counts: "gaps of 2.5 s or more" ("gap" for one)
    plate: tuple[str, str | None, str | None] = ("", None, None)           # title, price, caption
    rows: list[tuple[str, str, float]] = field(default_factory=list)       # when, how long, share of the longest


def idle_view(idle: list[tuple[float, float]], window: tuple[float, float]) -> IdleView:
    """the idle moments in window, for the hero, the plate and the list"""
    m = idle_moments(idle, window)
    gaps = f"gap{'' if len(m) == 1 else 's'} of {IDLE_GAP:g} s or more"
    if not m:
        return IdleView(m, "0", fight_verdict(m), gaps, (NONE, None, None))
    s0, e0 = m[0]
    total = f"{sum(e - s for s, e in m):.0f}"
    return IdleView(m, total, fight_verdict(m), gaps,
                    (f"Longest idle: {e0 - s0:.1f} s at {fmt_time(s0)}", f"{total} s idle", f"{len(m)} {gaps}"),
                    [(fmt_time(s), f"{e - s:.1f} s", (e - s) / (e0 - s0)) for s, e in m])


def with_fight(idle: list[tuple[float, float]], span: tuple[float, float],
               own: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """the run's idle gaps with the ones that start inside span (a fight) swapped for own, that fight's card's gaps"""
    s, e = span
    return [g for g in idle if not s <= g[0] <= e] + own


def _pad(start: float, end: float) -> float:
    return max(3.0, (end - start) * 0.08)


def fight_window(start: float, end: float) -> tuple[float, float]:
    """the view a fight is shown in: the fight with max(3 s, 8% of it) either side, as the Debrief zooms to it"""
    return start - _pad(start, end), end + _pad(start, end)


def scope_for(spans: list[tuple[float, float]], duration: float,
              window: tuple[float, float]) -> int | tuple[float, float] | None:
    """what a view shows: None for the whole run (the view covers it); a fight's index when the view holds that fight
    alone (to a second), with no more than its pad and a pull's lead-in either side; else the view (a custom view)"""
    a, b = window
    if a <= 0 and b >= duration:
        return None
    hits = [i for i, (s, e) in enumerate(spans)
            if a - 1 <= s and e <= b + 1 and max(s - a, b - e) <= _pad(s, e) + LEAD_IN + 1]
    return hits[0] if len(hits) == 1 else (a, b)


def step(starts: list[float], scope, d: int) -> int | None:
    """the fight before (d = -1) or after (d = 1) the scope: from the whole run, the first or the last; from a custom
    view, the first to start after its left edge, or the last to start before it; None past either end"""
    if isinstance(scope, int):
        i = scope + d
    elif scope is None:
        i = 0 if d > 0 else len(starts) - 1
    else:
        i = bisect_right(starts, scope[0]) if d > 0 else bisect_left(starts, scope[0]) - 1
    return i if 0 <= i < len(starts) else None


def option_text(cell) -> str:
    """a fight (a debrief.FightCell) in the picker: "6:25 Trash · 90 s · 70 C", the score only when it has one"""
    s = f"{cell.at} {cell.label} · {cell.end - cell.start:.0f} s"
    return s if cell.score is None else f"{s} · {cell.score} {cell.grade}"
