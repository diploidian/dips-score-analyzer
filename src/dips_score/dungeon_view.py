"""What the dungeon page shows, as plain data (no Qt). History: every visit, newest first, with your score; the best
and the last; the trend; the measure that keeps costing you points; and each counted measure's score visit by visit."""
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from .debrief import display_name

MINUS = "−"
JUDGED_FROM = 60.0          # seconds in combat: a visit with less isn't compared (trend, best, recurring fix, line)
TOO_SHORT = "too short to compare"      # under JUDGED_FROM with a card score: the score shows, muted, not counted
UNJUDGED = "too short to judge"         # under JUDGED_FROM with no card score at all
TREND_OF = 5                # the trend: the last score against the mean of up to this many before it


@dataclass
class Visit:
    when: datetime
    run_id: str
    length: float | None        # seconds (None: the visit couldn't be analysed)
    combat: float | None        # seconds in combat
    score: float | None         # None: not compared; note says why
    grade: str                  # the card's ("-": no card score at all)
    bosses: str                 # "6 of 6"; "—" without bosses
    deaths: int | None          # yours
    wipes: int | None
    categories: dict[str, float] = field(default_factory=dict)  # each counted category's score
    lost: dict[str, float] = field(default_factory=dict)        # the points each lost, most first
    note: str = ""              # why it isn't scored
    pieces: int = 1             # saved runs joined into this visit
    role: str = ""              # what the card scored you as
    card_score: float | None = None     # too short to compare: its card's score, shown but not counted


@dataclass
class HistoryView:
    visits: list[Visit] = field(default_factory=list)          # newest first
    best: Visit | None = None
    last: Visit | None = None                                   # the newest scored visit
    trend: float | None = None
    recurring: tuple[str, int, int, float] | None = None       # (category, lost in N, of M scored, average lost)
    series: dict[str, list[float | None]] = field(default_factory=dict)   # scored visits, oldest first


def visits(pairs) -> list[Visit]:
    """a Visit for each (Run, Analysis or None), newest first"""
    out = []
    for run, a in pairs:
        pieces = max(1, len(run.parts))
        if a is None:
            out.append(Visit(run.start_time, run.id, None, None, None, "-", "—", None, None,
                             note="couldn't be analysed", pieces=pieces))
            continue
        c, s, combat = a.card, a.summary, a.metrics.combat_time
        judged = not c.empty and c.grade != "-"
        scored = judged and combat >= JUDGED_FROM
        note = "" if scored else TOO_SHORT if judged else UNJUDGED if combat < JUDGED_FROM else "couldn't be judged"
        out.append(Visit(run.start_time, run.id, a.data.duration, combat, c.total if scored else None,
                         c.grade if judged else "-", f"{s.bosses_killed} of {s.bosses}" if s and s.bosses else "—",
                         sum(d.guid == a.data.player_guid for d in a.deaths), len(a.wipes),
                         {k.name: k.score for k in c.categories if not k.info_only} if scored else {},
                         {k.name: p for k, p in c.points_lost()} if scored else {},
                         note, pieces, c.role, c.total if judged and not scored else None))
    return sorted(out, key=lambda v: v.when, reverse=True)


def build_history(vs: list[Visit]) -> HistoryView:
    """vs: newest first, as visits() gives them"""
    scored = [v for v in vs if v.score is not None]
    h = HistoryView(vs, max(reversed(scored), key=lambda v: v.score, default=None), scored[0] if scored else None)
    if len(scored) < 2:
        h.series = {n: [scored[0].categories[n]] for n in scored[0].categories} if scored else {}
        return h
    before = [v.score for v in scored[1:1 + TREND_OF]]
    h.trend = scored[0].score - sum(before) / len(before)
    lost = Counter(n for v in scored for n in v.lost)
    if lost:
        avg = {n: sum(v.lost.get(n, 0.0) for v in scored) / k for n, k in lost.items()}
        name = max(lost, key=lambda n: (lost[n], avg[n]))
        h.recurring = (name, lost[name], len(scored), round(avg[name], 1))
    names = dict.fromkeys(n for v in scored for n in v.categories)     # the newest card's order first
    h.series = {n: [v.categories.get(n) for v in reversed(scored)] for n in names}
    return h


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def history_meta(h: HistoryView) -> str:
    """the page's meta line: "8 visits · 6 scored · best 82 A · last 75 B · as DPS\""""
    n = sum(v.score is not None for v in h.visits)
    if not n:
        return f"{_plural(len(h.visits), 'visit')} · none scored"
    role = "DPS" if h.last.role == "dps" else h.last.role
    return (f"{_plural(len(h.visits), 'visit')} · {n} scored · best {h.best.score:.0f} {h.best.grade} · "
            f"last {h.last.score:.0f} {h.last.grade} · as {role}")


def trend_note(h: HistoryView) -> str | None:
    """"+2 vs the 5 before" (None: under two scored visits)"""
    if h.trend is None:
        return None
    k = min(TREND_OF, sum(v.score is not None for v in h.visits) - 1)
    d = round(h.trend)
    return f"{'+' if d > 0 else MINUS if d < 0 else '±'}{abs(d)} vs {'the visit' if k == 1 else f'the {k}'} before"


def plate_text(h: HistoryView) -> tuple[str, str | None]:
    """the Recurring fix plate's title and paragraph"""
    if h.recurring:
        name, n, m, avg = h.recurring
        return f"{display_name(name)} cost you points in {n} of {m} visits", f"Average {MINUS}{avg:.1f} points a visit."
    n = sum(v.score is not None for v in h.visits)
    if n >= 2:
        return "No measure cost you points on any visit", None
    why = f"Visits with under {JUDGED_FROM:.0f} s in combat are too short to compare." \
        if any(v.note == TOO_SHORT for v in h.visits) else None
    if n == 1:
        return f"One {'' if len(h.visits) == 1 else 'scored '}visit so far — come back to compare", why
    return "No scored visit yet — come back after a full run", why
