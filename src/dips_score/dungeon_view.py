"""What the dungeon page shows, as plain data (no Qt). History: every visit, newest first, with your score; the best
and the last; the trend; the measure that keeps costing you points; and each counted measure's score visit by visit.
Bosses: each boss on the last visit, the weakest, and its score visit by visit. Records: your bests here, against the
last visit, and whether its top fix would have beaten your best score. Bosses and Records count only scored visits."""
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

from .debrief import display_name, fmt_time
from .scoring.score import grade

MINUS = "−"
ORDER = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth")
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


@dataclass
class BossRow:
    name: str
    today: float | None             # its score on the last visit (None: a wipe, not reached or not scored)
    grade: str                      # "-" with no score
    kill_s: float | None
    dps: float | None               # yours on it
    share: float | None             # your damage against an even split
    lost: list[tuple[str, float]]   # the points its card lost, most first
    history: list[float | None]     # its score on each scored visit, oldest first: the last is today's
    best: tuple[float, str] | None  # its best score, and when ("11 Nov", "today")
    missed: list[str] = field(default_factory=list)     # why each history score is missing ("" when it isn't)
    fight: tuple[float, float] | None = None            # its fight on the last visit, in that run's seconds
    killed: bool = False        # killed on the last visit (the log said so: unknown is not killed)


@dataclass
class Record:
    name: str
    value: str          # the record: a figure, then its unit or grade ("82 A", "85 DPS", "2 of 6"); "–": none
    when: str           # the visit that holds it ("11 Nov", "today")
    today: str          # the last visit's
    status: str         # the last visit against it; after the first " · ", an aside
    new_today: bool     # the last visit set it
    note: str = ""      # under the name: what counts, or where it was set


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


# ---------------------------------------------------------------------------- Bosses and Records
def day(d) -> str:
    return f"{d.day} {d:%b}"


def last_word(when: datetime, today: date | None = None) -> str:
    """"today" for a visit today, else its day ("18 Nov")"""
    return "today" if when.date() == (today or date.today()) else day(when)


def _scored(pairs) -> list[tuple[Visit, object]]:
    """each scored visit and its analysis, oldest first: a visit too short to compare never counts (R10)"""
    by = {r.id: a for r, a in pairs}
    return [(v, by[v.run_id]) for v in reversed(visits(pairs)) if v.score is not None]


def _boss_fights(a) -> dict:
    """each boss's fight on a visit, in the order you met them: its kill, else its last try"""
    out = {}
    for fr in a.fights:
        b = fr.fight.boss
        if b and not (b in out and out[b].fight.killed):
            out[b] = fr
    return out


def _boss_score(fr) -> float | None:
    c = fr.card
    return None if fr.fight.killed is False or c.empty or c.grade == "-" else c.total


def _missed(fr) -> str:
    """why a boss has no score on a visit ("" when it has; fr: its fight there, None for none)"""
    if fr is None:
        return "not reached"
    return "" if _boss_score(fr) is not None else "wipe" if fr.fight.killed is False else "not scored"


def _route(per: list[dict]) -> list[str]:
    """the bosses in the order you met them on the last visit; one met only before slots in after the boss you met
    just before it, on the latest visit you met it (first, when none was)"""
    order = list(per[-1]) if per else []
    for b in reversed(per[:-1]):
        prev = None
        for name in b:
            if name not in order:
                order.insert(order.index(prev) + 1 if prev else 0, name)
            prev = name
    return order


def build_bosses(pairs, today: date | None = None) -> tuple[list[BossRow], BossRow | None, float | None]:
    """a row per boss in the order you met them (_route); the weakest on the last scored visit, and its average boss
    score (None: no boss scored on it)"""
    sv = _scored(pairs)
    per = [_boss_fights(a) for _, a in sv]
    rows = []
    for name in _route(per):
        hist = [_boss_score(b[name]) if name in b else None for b in per]
        best = max(((s, v.when) for s, (v, _) in zip(hist, sv) if s is not None), key=lambda t: t[0], default=None)
        fr = per[-1].get(name)
        on = fr if hist[-1] is not None else None       # the fight it scored on the last visit
        rows.append(BossRow(
            name, hist[-1], on.card.grade if on else "-", on.fight.duration if on else None,
            on.damage[0] / on.fight.duration if on and on.damage and on.fight.duration else None,
            on.damage[1] if on and on.damage else None, [(c.name, p) for c, p in on.card.points_lost()] if on else [],
            hist, None if best is None else (best[0], last_word(best[1], today)), [_missed(b.get(name)) for b in per],
            (fr.fight.start, fr.fight.end) if fr else None, bool(fr) and fr.fight.killed is True))
    scored = [r for r in rows if r.today is not None]
    weakest = min(scored, key=lambda r: r.today, default=None)      # the first met, on a tie
    return rows, weakest, sum(r.today for r in scored) / len(scored) if scored else None


def bosses_text(rows: list[BossRow], weakest: BossRow | None, word: str) -> tuple[str | None, str]:
    """the Bosses hero's caption and verdict (word: the last visit's last_word)"""
    if not rows:
        return None, "No boss fight on a scored visit yet."
    when = "today" if word == "today" else f"on {word}"
    caption = f"average boss score {when} · {sum(r.killed for r in rows)} of {len(rows)} killed"
    if weakest is None:
        return caption, f"No boss was scored {when}."
    s = f"Your weakest boss is {weakest.name} ({weakest.today:.0f} {weakest.grade})"
    i = rows.index(weakest)
    if len(rows) > 1:
        s += ", the last one" if i == len(rows) - 1 else f", the {ORDER[i]} one" if i < len(ORDER) else \
            f", number {i + 1} of {len(rows)}"
    if weakest.lost:
        s += ": it lost " + " and ".join(f"{p:.1f}{' points' if k == 0 else ''} on {display_name(c)}"
                                         for k, (c, p) in enumerate(weakest.lost[:2]))
    others = [r.today for r in rows if r is not weakest and r.today is not None]
    under = sum(x < 90 for x in others)
    if others:
        s += ". Every other boss was 90 or better" if not under else \
            f". {under} more {'was' if under == 1 else 'were'} under 90"
    return caption, s + "."


def _top_dps(a):
    """(your damage a second, the fight) for the fight you did the most in; None without damage"""
    return max(((fr.damage[0] / fr.fight.duration, fr.fight) for fr in a.fights if fr.damage and fr.fight.duration),
               key=lambda t: t[0], default=None)


def _streak(a) -> tuple[int, float, float]:
    """the longest run of fights scoring 90 or more (a fight not scored is skipped): its length, first and last
    start"""
    best, n, first = (0, 0.0, 0.0), 0, 0.0
    for fr in a.fights:
        c = fr.card
        if c.empty or c.grade == "-":
            continue
        if c.total < 90:
            n = 0
            continue
        first = fr.fight.start if n == 0 else first
        n += 1
        if n > best[0]:
            best = (n, first, fr.fight.start)
    return best


def _score(s: float, _short: bool = True) -> str:
    """a score as the Records board shows it ("75 B"): two that read the same tie, on the board and in the hero"""
    return f"{s:.0f} {grade(s)}"


def _record(name, vals, sv, word, show, gap, low=False, note=lambda i: "") -> Record:
    """a record from each scored visit's value (oldest first; None: it has none), the last visit against the best
    before it (the earliest, on a tie). show(v, short): the figure, as the Best column has it (short: the Today
    column); gap(best, last): how far the last falls short; note(i): the line under the name, visit i holding it"""
    n, t = len(vals), vals[-1]
    b = (min if low else max)((i for i in range(n - 1) if vals[i] is not None), key=lambda i: vals[i], default=None)
    new = "new record today" if word == "today" else "new record"
    if n == 1:
        at, status = (None if t is None else 0), "first visit"
    elif t is None:
        at, status = b, "not this visit"
    elif b is None:
        at, status = n - 1, new
    elif show(t, True) == show(vals[b], True):
        at, status = b, "ties your record"
    elif t < vals[b] if low else t > vals[b]:
        at, status = n - 1, f"{new} · was {show(vals[b], True)} · {day(sv[b][0].when)}"
    else:
        at, status = b, gap(vals[b], t)
    return Record(name, "–" if at is None else show(vals[at], False),
                  "–" if at is None else word if at == n - 1 else day(sv[at][0].when),
                  "–" if t is None else show(t, True), status, n > 1 and at == n - 1, note(at))


def build_records(pairs, today: date | None = None) -> tuple[list[Record], tuple[str, str] | None]:
    """your records here in the board's order, each against the last scored visit; and, when that visit's top fix
    (its card's most points lost) would have beaten your best score, the best and what it takes (R9)"""
    sv = _scored(pairs)
    if not sv:
        return [], None
    n, last = len(sv), sv[-1][0]
    word = last_word(last.when, today)
    prior = max((v.score for v, _ in sv[:-1]), default=None)
    top = next(iter(last.lost.items()), None)
    within = None
    if prior is not None and prior > last.score and top and last.score + top[1] > prior:
        within = (f"Best {prior:.0f} {grade(prior)}",
                  f"+{math.ceil(prior - last.score)} needed — your {display_name(top[0])} fix is worth {top[1]:.1f}")
    killed = [{fr.fight.boss for fr in a.fights if fr.fight.boss and fr.fight.killed} for _, a in sv]
    clear = [k >= set().union(*killed) for k in killed]     # it killed every boss you have here: left early, no clear
    dps, streak = [_top_dps(a) for _, a in sv], [_streak(a) for _, a in sv]

    def clock(s, _short):
        return fmt_time(s)

    def behind(b, t):
        return f"{fmt_time(t - b)} behind"

    def fewer(b, t):
        return f"{b - t} fewer"

    def dps_at(i):
        f = None if i is None else dps[i][1]
        return "" if f is None else f"{f.label}, {f.duration:.0f}s at {fmt_time(f.start)}"

    def streak_at(i):
        k, a, b = (0, 0, 0) if i is None else streak[i]
        return "fights scoring 90+ in a row" + (f", {fmt_time(a)} to {fmt_time(b)}" if k > 1 else "")

    records = [
        _record("Best score", [v.score for v, _ in sv], sv, word, _score,
                lambda b, t: f"{math.ceil(b - t)} short" + (" · within reach" if within else "")),
        _record("Fastest clear", [a.data.duration if c else None for (_, a), c in zip(sv, clear)], sv, word, clock,
                behind, low=True, note=lambda i: "whole visit, entry to exit"),
        _record("Least time in combat", [v.combat if c else None for (v, _), c in zip(sv, clear)], sv, word, clock,
                behind, low=True),
        _record("Most killing blows", [a.metrics.kills for _, a in sv], sv, word, lambda s, _: str(s), fewer),
        _record("Highest DPS in a fight", [None if d is None else d[0] for d in dps], sv, word,
                lambda s, short: f"{s:.0f}" if short else f"{s:.0f} DPS", lambda b, t: f"{b - t:.0f} DPS short",
                note=dps_at),
        _record("Longest S streak", [k for k, _, _ in streak], sv, word,
                lambda s, short: str(s) if short else _plural(s, "fight") if s else "none yet", fewer, note=streak_at)]
    clean = [i for i, (v, _) in enumerate(sv) if v.deaths == 0]
    d = last.deaths or 0
    records.append(Record("Deathless visits", f"{len(clean)} of {n}",
                          "–" if not clean else word if clean[-1] == n - 1 else f"last {day(sv[clean[-1]][0].when)}",
                          _plural(d, "death") if d else "no deaths",
                          "first visit" if n == 1 else "not this visit" if d else "deathless this visit", False,
                          "visits with no deaths"))
    return records, within


def records_text(h: HistoryView, within: tuple[str, str] | None, word: str) -> tuple[str, str, str | None]:
    """the Records hero's verdict, and the Within reach plate's title and paragraph (word: the last visit's
    last_word)"""
    t, b = h.last, h.best
    why = plate_text(h)[1]
    if t is None:
        return "No scored visit yet, so no records.", "No scored visit yet — come back after a full run", why
    today = word == "today"
    if sum(v.score is not None for v in h.visits) == 1:
        visit = "today's visit" if today else f"the {word} visit"
        return f"Every record here is from {visit}, your only scored one.", "First visit — records start here", why
    whose = f"{'Today' if today else f'The {word} visit'}'s {t.score:.0f} {t.grade}"
    on = "today" if today else f"on {word}"
    alone = ""
    if within:
        cat, x = next(iter(t.lost.items()))
        alone = f" Your {display_name(cat)} fix alone ({MINUS}{x:.1f}) would have beaten it."
    prior = max((v.score for v in h.visits if v.score is not None and v is not t), default=None)
    if prior is not None and _score(prior) == _score(t.score):      # the board's tie test: "ties your record"
        return (f"{whose} ties your best score here.{alone}", ": ".join(within) if within else
                f"Tied best {on}: {t.score:.0f} {t.grade} — come back to beat it", None)
    if b is t:
        new = f"New best {on}: {t.score:.0f} {t.grade} — come back to beat it"
        return f"{whose} is your best score here.", new, None
    need = math.ceil(b.score - t.score)
    short = f"{whose} is {_plural(need, 'point')} short of your best."
    if within:
        return f"{short}{alone}", ": ".join(within), None
    return short, f"Best {b.score:.0f} {b.grade}: +{need} needed — more than any one fix is worth", None
