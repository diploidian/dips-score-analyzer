"""What the debrief page shows, as plain data (no Qt)."""
import re
from dataclasses import dataclass, field

from .scoring.score import Category, Scorecard
from .ui.tokens import ink_for


@dataclass
class FightCell:
    index: int
    at: str
    label: str
    score: int | None
    grade: str
    boss: bool
    died: bool
    start: float
    end: float


@dataclass
class Measure:
    name: str
    score: float | None
    ink: str
    reason: str
    on_target: bool


@dataclass
class Lost:
    name: str
    points: float
    ink: str


@dataclass
class Fix:
    title: str
    points: float
    category: str
    damage: str | None


@dataclass
class DebriefView:
    total: str = "–"
    grade: str = "-"
    role: str = ""
    note: str = ""
    verdict: str = ""
    fix: Fix | None = None
    next_fixes: list[Fix] = field(default_factory=list)
    measures: list[Measure] = field(default_factory=list)
    lost: list[Lost] = field(default_factory=list)
    earned: int = 0
    fights: list[FightCell] = field(default_factory=list)
    review: list[int] = field(default_factory=list)
    categories: list[Category] = field(default_factory=list)   # all of the card's, for the All categories drawer
    bonus: float = 0.0          # hybrid bonus points, on top of the categories
    bonus_note: str = ""


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, round(x, 9)))      # rounded so p = 1 lands on exactly 1.0


def bar_fraction(p: float, i: int) -> float:
    """the entrance (p, 0..1): how much of bar i is drawn, each bar 0.06 behind the one above
    (from the 7th on they share its start, so p = 1 always finishes every bar)"""
    return _clamp((p - min(i, 6) * 0.06) / 0.6)


def ticker(total: str, p: float) -> str:
    """the hero number climbing to total over the first 0.78 of p; the last frame is total itself, and a
    non-number ("-") never ticks"""
    t = _clamp(p / 0.78)
    return str(round(int(total) * t)) if t < 1 and total.isdigit() else total


def circle_fraction(p: float, j: int) -> float:
    """how much of review circle j is drawn: in order from p = 0.55, each starting 0.07 after the last"""
    return _clamp((p - 0.55 - j * 0.07) / 0.2)


def route_alpha(p: float) -> float:
    """the route and the death crosses, once the circles are down"""
    return _clamp((p - 0.9) / 0.1)


def note_alpha(p: float) -> float:
    return _clamp((p - 0.8) / 0.2)


def display_name(category: str) -> str:
    return "Abilities on time" if category == "Cooldowns" else category


def _fix(cat, points: float) -> Fix:
    title = re.split(r" \(|\. ", cat.tip, maxsplit=1)[0].rstrip(".")
    m = re.search(r"~[\d,]+ damage", cat.tip)
    return Fix(title, round(points, 1), cat.name, m.group(0) if m else None)


def _review(fights: list[FightCell]) -> list[int]:
    low = sorted((f for f in fights if f.score is not None and f.score < 90),
                 key=lambda f: (f.score, f.index))[:4]
    return sorted(f.index for f in low)


def build_view(card: Scorecard, fights: list[FightCell], damage_share: float | None, deaths: int) -> DebriefView:
    if card.empty or card.grade == "-":  # nothing scored, or nothing judgeable: its categories and fights still shown
        return DebriefView(note=card.note, fights=fights, review=_review(fights), categories=card.categories,
                           bonus=round(card.bonus, 1), bonus_note=card.bonus_note)
    counted = [c for c in card.categories if not c.info_only]
    top = sorted(counted, key=lambda c: -c.weight)[:4]  # stable: ties keep card order
    measures = [Measure(display_name(c.name), c.score, ink_for(c.name),
                        c.summary.split(";")[0], c.score >= 90) for c in top]
    lost = card.points_lost()
    fixes = [_fix(c, p) for c, p in lost if c.tip and c.score < 85]  # same filter as Scorecard.tips
    fix = fixes[0] if fixes else None
    if fix is None:
        verdict = "Nothing stands out — nice run."
    else:
        dmg = next((c for c in counted if c.name == "Damage"), None)
        if damage_share is not None and dmg and dmg.score >= 85:
            verdict = f"Strong damage — {damage_share:.0%} of an even share — but {fix.title}"
        else:
            verdict = fix.title
        if deaths > 0 and fix.category != "Survival":
            verdict += " and you died once" if deaths == 1 else f" and you died {deaths} times"
        verdict += "."
    return DebriefView(
        total=f"{card.total:.0f}", grade=card.grade, role=card.role, note=card.note, verdict=verdict,
        fix=fix, next_fixes=fixes[1:3], measures=measures,
        lost=[Lost(c.name, p, ink_for(c.name)) for c, p in lost],
        earned=round(card.total), fights=fights, review=_review(fights), categories=card.categories,
        bonus=round(card.bonus, 1), bonus_note=card.bonus_note)


def fmt_time(s: float) -> str:
    s = int(max(0, s))
    return f"{s // 60}:{s % 60:02d}"


def fight_of(deaths, fights) -> dict[int, list]:
    """which fight each death fell in (first match), as fight index -> deaths"""
    out: dict[int, list] = {}
    for d in deaths:
        for i, f in enumerate(fights):
            if f.start - 2 <= d.t <= f.end + 5:
                out.setdefault(i, []).append(d)
                break
    return out


def worst_fight(cards: list[Scorecard], category: str) -> int | None:
    """the fight whose own card lost the most points in `category` (the earliest on a tie; None: none lost any)"""
    lost = [next((p for c, p in card.points_lost() if c.name == category), 0.0) for card in cards]
    i = max(range(len(lost)), key=lost.__getitem__, default=None)
    return i if i is not None and lost[i] > 0 else None


def fight_cells(a, guid: str | None = None, cards: list[Scorecard] | None = None) -> list[FightCell]:
    """a cell per fight, scored from `cards` (default: your own) with `guid`'s deaths (default: yours)"""
    guid = guid or a.data.player_guid
    cards = cards if cards is not None else [fr.card for fr in a.fights]
    mine = fight_of([d for d in a.deaths if d.guid == guid], a.data.fights)
    cells = []
    for i, (fr, c) in enumerate(zip(a.fights, cards)):
        f = fr.fight
        none = c.empty or c.grade == "-"
        cells.append(FightCell(i, fmt_time(f.start), f.label, None if none else round(c.total),
                               "-" if none else c.grade, f.boss is not None, i in mine, f.start, f.end))
    return cells
