"""What the Pulls page shows, as plain data (no Qt): every pull with who pulled it, its mobs and packs, and your
health and mana as you went in; then the one pull to fix, the mana slide, the breaks and the verdict."""
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta

from .debrief import fmt_time

BREAK_S = 300       # a gap this long between pulls is a break
QUICK_S = 30        # pulls closer than this follow each other with no time to rest
LOW = 0.5           # entering under half health or mana is risky
LEAD = 0.5          # health and mana are read this long before a pull starts
WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")


@dataclass
class PullRow:
    n: int
    at: str
    start: float
    end: float
    label: str
    boss: bool
    mobs: int
    packs: int
    extra_packs: int                # packs that joined the fight already going
    pulled_by: str | None
    you_pulled: bool
    how: str
    length_s: int
    gap_before_s: int | None        # since the previous fight ended
    you_died: bool
    hp: float | None                # yours as you went in, 0..1; None: not in the log
    mana: float | None


@dataclass
class PullsView:
    rows: list[PullRow] = field(default_factory=list)
    total: int = 0
    verdict: str = ""
    fix: PullRow | None = None
    under_half_hp: int = 0
    lowest_hp: tuple[float, str] | None = None
    under_half_mana: list[str] = field(default_factory=list)
    joined: int = 0                 # pulls a pack joined mid-fight
    you_pulled: list[str] = field(default_factory=list)
    pullers: list[tuple[str | None, int]] = field(default_factory=list)     # most first; None: unknown
    breaks: list[tuple[str, str, int]] = field(default_factory=list)         # (from, to, minutes)
    slide: tuple[float, float, int, str, str] | None = None                  # (from mana, to mana, pulls, first, last)


def pct(x: float) -> str:
    return f"{x:.0%}"


def count(n: int) -> str:
    return WORDS[n] if 0 <= n < len(WORDS) else str(n)


def _s(n: int) -> str:
    return "" if n == 1 else "s"


def resource_at(events, guid, t) -> tuple[float | None, float | None]:
    """(health, mana) fractions from guid's last samples at or before t (events in time order, t on their clock);
    None where there is none. Mana counts only from a mana bar (power type 0)."""
    hp = mana = None
    for e in events:
        if e.ts > t:
            break
        i = e.info
        if i is None or i.guid != guid or not i.max_hp:
            continue
        hp = i.hp_pct
        if i.power_type == 0 and i.max_power > 0:
            mana = i.power / i.max_power
    return hp, mana


def pull_rows(a) -> list[PullRow]:
    """every pull of the analysis a, in order"""
    rd, me = a.data, a.data.player_guid
    mine = [e for e in rd.events if e.info and e.info.guid == me]     # one pass, not one per pull
    my_deaths = [d.t for d in a.deaths if d.guid == me]
    rows, prev_end = [], None
    for p in a.pulls:
        f = p.fight
        pullers = [pk.puller for pk in p.packs if pk.puller]
        hp, mana = resource_at(mine, me, rd.start + timedelta(seconds=p.start - LEAD))
        rows.append(PullRow(
            n=len(rows) + 1, at=fmt_time(p.start), start=p.start, end=f.end, label=f.label, boss=f.boss is not None,
            mobs=len(p.enemies), packs=len(p.packs), extra_packs=sum(1 for pk in p.packs if pk.extra),
            pulled_by=a.roster[pullers[0]].name if pullers and pullers[0] in a.roster else None,
            you_pulled=bool(pullers) and pullers[0] == me, how=p.packs[0].how if p.packs else "",
            length_s=round(f.duration), gap_before_s=None if prev_end is None else round(p.start - prev_end),
            you_died=any(f.start - 2 <= t <= f.end + 5 for t in my_deaths), hp=hp, mana=mana))
        prev_end = f.end
    return rows


def _lower(a: PullRow, b: PullRow) -> bool:
    """b came quickly after a, with less mana (in whole percent, as shown)"""
    return (a.mana is not None and b.mana is not None and round(b.mana * 100) < round(a.mana * 100)
            and b.gap_before_s is not None and b.gap_before_s < QUICK_S)


def slide_rows(rows: list[PullRow]) -> list[PullRow]:
    """the mana slide: the longest run of 3 or more quick pulls, each entered with less mana than the one before;
    [] when there is none"""
    best, start = [], 0
    for j in range(1, len(rows) + 1):
        if j < len(rows) and _lower(rows[j - 1], rows[j]):
            continue
        if j - start > len(best):
            best = rows[start:j]
        start = j
    return best if len(best) >= 3 else []


def slide_note(run: list[PullRow]) -> str:
    """the slide's note on the mana line: "15:24 to 17:10: four pulls, gaps of 5–10 s, mana 90% to 44%" """
    gaps = [r.gap_before_s for r in run[1:]]
    g = f"{min(gaps)}–{max(gaps)}" if min(gaps) != max(gaps) else str(gaps[0])
    return (f"{run[0].at} to {run[-1].at}: {count(len(run))} pulls, gaps of {g} s, "
            f"mana {pct(run[0].mana)} to {pct(run[-1].mana)}")


def _and(ats: list[str]) -> str:
    """"a", "a and b", "a, b and c"; past four, "a, b and 7 more" """
    if len(ats) > 4:
        ats = ats[:2] + [f"{len(ats) - 2} more"]
    return ats[0] if len(ats) == 1 else ", ".join(ats[:-1]) + " and " + ats[-1]


def pulls_view(rows: list[PullRow]) -> PullsView:
    v = PullsView(rows=rows, total=len(rows))
    hps = [r for r in rows if r.hp is not None]
    v.under_half_hp = sum(1 for r in hps if r.hp < LOW)
    low_hp = min(hps, key=lambda r: r.hp, default=None)
    v.lowest_hp = (low_hp.hp, low_hp.at) if low_hp else None
    v.under_half_mana = [r.at for r in rows if r.mana is not None and r.mana < LOW]
    v.joined = sum(1 for r in rows if r.extra_packs)
    v.you_pulled = [r.at for r in rows if r.you_pulled]
    v.pullers = Counter(r.pulled_by for r in rows).most_common()
    v.breaks = [(fmt_time(a.end), b.at, round(b.gap_before_s / 60)) for a, b in zip(rows, rows[1:])
                if b.gap_before_s is not None and b.gap_before_s >= BREAK_S]
    slide = slide_rows(rows)
    if slide:
        v.slide = (slide[0].mana, slide[-1].mana, len(slide), slide[0].at, slide[-1].at)
    died = [r for r in rows if r.you_died]
    low_mana = min((r for r in rows if r.mana is not None), key=lambda r: r.mana, default=None)
    v.fix = (died[0] if died else low_mana if low_mana and low_mana.mana < LOW else
             low_hp if low_hp and low_hp.hp < LOW else None)
    v.verdict = _verdict(v, slide, len(died))
    return v


def build_pulls(a) -> PullsView:
    return pulls_view(pull_rows(a))


def _verdict(v: PullsView, slide: list[PullRow], deaths: int) -> str:
    """health, then the mana slide and where you died"""
    if not v.rows:
        return "No pulls in this run."
    out = []
    if v.under_half_hp:
        out.append(f"You entered {count(v.under_half_hp)} pull{_s(v.under_half_hp)} under 50% health; the lowest "
                   f"was {pct(v.lowest_hp[0])}, at {v.lowest_hp[1]}.")
    elif v.lowest_hp:
        out.append("You never entered a pull under 50% health.")
    s = slide and f"Mana slid from {pct(slide[0].mana)} to {pct(slide[-1].mana)} over {count(len(slide))} quick pulls"
    d, f = None, v.fix
    if f and f.you_died:
        where = "where you first died" if deaths > 1 else "where you died"
        d = (f"the {f.at} pull — {count(f.extra_packs)} pack{_s(f.extra_packs)} joined mid-fight — is {where}"
             if f.extra_packs else f"the {f.at} pull is {where}")
    if s and d:
        out.append(f"{s}, and {d}.")
    elif s or d:
        out.append(f"{(s or d)[0].upper()}{(s or d)[1:]}.")
    return " ".join(out) or "Your health and mana weren't in this log, so pull safety can't be judged."


def fix_plate(fix: PullRow | None) -> tuple[str, str | None, str | None, str | None]:
    """the plate: (title, price, caption, advice); the price is the lower of your mana and health going in"""
    if fix is None:
        return "No risky pulls", None, None, None
    title = f"{fix.at} · {fix.length_s} s"
    if fix.packs:
        title += f" · {fix.packs} pack{_s(fix.packs)}"
        if fix.extra_packs:
            title += f", {fix.extra_packs} joined mid-fight"
    low = min(((x, word) for x, word in ((fix.mana, "mana"), (fix.hp, "health")) if x is not None),
              key=lambda xw: xw[0], default=None)
    caption = " · ".join(s for s in ("when you entered" if low else "", "you died" if fix.you_died else "") if s)
    advice = ("Rest when mana is under 50% before the next pull" if fix.mana is not None and fix.mana < LOW else
              "Eat or bandage when health is under 50% before the next pull" if fix.hp is not None and fix.hp < LOW
              else None)
    return title, f"{pct(low[0])} {low[1]}" if low else None, caption or None, advice


def safety_figures(v: PullsView) -> list[tuple[str, str, str]]:
    """Pull safety: (number, caption, the muted line under it) for health, mana, packs joining, your pulls"""
    out = [("–", "entered under 50% health", "no health in this log") if v.lowest_hp is None else
           (str(v.under_half_hp), "entered under 50% health", f"lowest was {pct(v.lowest_hp[0])}, at {v.lowest_hp[1]}")]
    manas = [r for r in v.rows if r.mana is not None]
    low = [r for r in manas if r.mana < LOW]
    if not manas:
        out.append(("–", "entered under 50% mana", "no mana in this log"))
    elif not low:
        m = min(manas, key=lambda r: r.mana)
        out.append(("0", "entered under 50% mana", f"lowest was {pct(m.mana)}, at {m.at}"))
    else:
        shown = {pct(r.mana) for r in low}
        at = (f"at {pct(low[0].mana)}" if len(low) == 1 else
              f"{'both' if len(low) == 2 else 'all'} at {shown.pop()}" if len(shown) == 1 else
              f"lowest {pct(min(r.mana for r in low))}")
        out.append((str(len(low)), "entered under 50% mana", f"{_and([r.at for r in low])}, {at}"))
    most = v.fix if v.fix and v.fix.extra_packs else max(v.rows, key=lambda r: r.extra_packs, default=None)
    out.append((str(v.joined), "pulls had packs join mid-fight",
                f"{most.extra_packs} joined the {most.at} pull" if most and most.extra_packs else ""))
    n = len(v.you_pulled)
    out.append((str(n), "you pulled", ", ".join(v.you_pulled) if n <= 6 else f"{n / v.total:.0%} of the pulls"))
    return out
