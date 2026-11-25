"""What the Group page shows, as plain data (no Qt): where you placed and how far off the next place, what would
move you up, the podium, everyone's card (placing, strengths and weaknesses, awards, map) and the awards list."""
import re
from dataclasses import dataclass, field

from .scoring.group import ordinal, placing_reason
from .scoring.radar import average

ROLE_WORD = {"TANK": "Tank", "HEALER": "Healer"}
MINUS = "−"
KIND = {True: "Award, +2", False: f"Roast, {MINUS}2"}       # a chip's tooltip starts with it


def _times(n: int) -> str:
    return "once" if n == 1 else f"{n} times"


# your first weakness in plain words: its line (as scoring/group.py and score.py write it), and the plate's sentence
PHRASES = [
    (r"Survival: (\d+) deaths?; took ([\d,]+) damage \(([\d.]+)x the damage dealers' middle\)",
     lambda deaths, taken, x: f"You took {taken} damage — {float(x):g}× the other damage dealers." if float(x) > 1
     else f"You died {_times(int(deaths))}."),
    (r"Damage: ([\d,]+) damage \((\d+%) of an even share",
     lambda dmg, share: f"You did {dmg} damage — {share} of an even share."),
    (r"Utility: 0 interrupts and dispels", lambda: "You never interrupted or dispelled."),
    (r"Utility: (\d+) interrupts and dispels \(([\d.]+) per 10 min\)",
     lambda n, per10: f"You interrupted or dispelled {_times(int(n))} — {per10} per 10 min."),
]


@dataclass
class PlayerCard:
    rank: int
    name: str
    role: str                       # "Tank", "Healer", "DPS"
    you: bool
    mvp: bool
    reason: str                     # the placing reason, without its "3rd: "
    plus: list[tuple[str, str]]     # (category, evidence)
    minus: list[tuple[str, str]]
    awards: list[tuple[str, bool, str]]     # (title, good, tooltip)
    radar: list[float] | None       # the map's six values (scoring.radar.AXES); None: no map
    details: list[str] | None       # what's behind each value
    points: float
    score: float
    grade: str
    breakdown: str = ""             # the score's hover help: each category, the bonus, the awards
    cls: str | None = None          # the game's class token ("PALADIN"); None: not known
    who: str = ""                   # "Paladin 39", "Warrior" (level not recorded), "" (class not known)
    who_tip: str = ""               # where that comes from, when it's less than certain


@dataclass
class GroupView:
    place: int | None = None        # your rank; None: you aren't in the standings
    of: int = 0
    behind_next: float | None = None    # points to the place above yours; None: you're 1st (or not placed)
    behind_mvp: float | None = None
    reason: str = ""
    move_up: tuple[str, str] | None = None      # the plate: (title, caption); None: you're 1st (or not placed)
    death_at: float | None = None   # your first death
    podium: list[PlayerCard] = field(default_factory=list)      # the top three, 1st first
    cards: list[PlayerCard] = field(default_factory=list)       # everyone, 1st first
    average: list[float] | None = None
    awards: list[tuple[str, str, str, str, bool]] = field(default_factory=list)   # (title, blurb, holder, stat, good)


def _typeset(s: str) -> str:
    """placing_reason's hyphens as the page sets them: a dash between clauses, a minus before a number"""
    return s.replace(" - ", " — ").replace(", -", f", {MINUS}")


def _split(lines: list[str]) -> list[tuple[str, str]]:
    return [tuple(s.split(": ", 1)) if ": " in s else (s, "") for s in lines]


def move_up_title(weakness: str | None) -> str:
    """your first weakness as the plate's sentence: a known line in plain words (with its multiplier), any other as it
    is"""
    if weakness is None:
        return "No one category held you back."
    for pattern, phrase in PHRASES:
        if m := re.match(pattern, weakness):
            return phrase(*m.groups())
    evidence = weakness.split(": ", 1)[-1]
    return evidence[:1].upper() + evidence[1:] + ("" if evidence.endswith(".") else ".")


def _caption(roasts: list[str], behind_next: float | None) -> str:
    """what the data says, no more (ruling R6): the roasts' cost, then the gap to the place above"""
    out = []
    if roasts:
        n = 2 * len(roasts)
        out.append(f"{'Roasts' if len(roasts) > 1 else 'A roast'} cost you {n} points ({', '.join(roasts)})")
    if behind_next is not None:
        out.append(f"one place is {behind_next:.1f} points away")
    s = "; ".join(out)
    return s[:1].upper() + s[1:] + "." if s else ""


def breakdown(pl, a) -> str:
    """a player's placing taken apart, as plain text: each category's score, weight and numbers, then the hybrid
    bonus and the awards (the old Summary tab's card tooltip)"""
    card = pl.card
    out = [f"{a.roster[pl.guid].name} — {ordinal(pl.rank)}, {pl.points:.0f} points",
           _typeset(placing_reason(pl, a).split(": ", 1)[1]).split(" — ")[0]]       # "67 as a …, −2 from awards"
    out += [f"{c.name} {'–' if c.unavailable else f'{c.score:.0f}'} · "
            f"{'info only' if c.info_only else f'weight {c.weight:g}'} · {c.summary}" for c in card.categories]
    if card.bonus:
        out.append(f"Hybrid bonus +{card.bonus:.1f} · {card.bonus_note}")
    out += [f"{aw.title} {KIND[aw.good][-2:]} · {aw.stat}" for aw in pl.awards]
    return "\n".join(out)


def of_line(v: GroupView) -> str:
    """the line beside the placing: "of 5 · 0.4 points behind 2nd · 35 behind the MVP" """
    if not v.of:
        return ""
    if v.place is None:
        return f"{v.of} in the group"
    if v.behind_next is None:
        return f"of {v.of} · MVP"
    above = "the MVP" if v.place == 2 else ordinal(v.place - 1)
    out = f"of {v.of} · {v.behind_next:.1f} points behind {above}"
    return out + (f" · {v.behind_mvp:.0f} behind the MVP" if v.place > 2 else "")


def _who(p) -> dict:
    """the class and level beside a name, and its hover help"""
    if not p.cls:
        return {}
    tips = (["Class guessed from the spells they cast"] if p.cls_from == "spells" else []) + \
        (["Level not recorded: the run is older than add-on 0.6.3"] if p.level is None else [])
    return {"who": " ".join(filter(None, (p.cls.title(), p.level and str(p.level)))), "who_tip": ". ".join(tips)}


def build_group(a) -> GroupView:
    """the Group page for the analysis a"""
    v = GroupView(of=len(a.ranking))
    for pl in a.ranking:
        p, r = a.roster[pl.guid], a.radars.get(pl.guid)
        v.cards.append(PlayerCard(
            rank=pl.rank, name=p.name, role=ROLE_WORD.get(p.role, "DPS"), you=p.is_me, mvp=pl.mvp,
            reason=_typeset(placing_reason(pl, a).split(": ", 1)[1]), plus=_split(pl.strengths),
            minus=_split(pl.weaknesses), awards=[(aw.title, aw.good, f"{KIND[aw.good]}: {aw.blurb} {aw.stat}")
                                                 for aw in pl.awards],
            radar=list(r.values) if r else None, details=list(r.details) if r else None, points=pl.points,
            score=pl.card.total, grade=pl.card.grade, breakdown=breakdown(pl, a), cls=p.cls, **_who(p)))
    v.podium = v.cards[:3]
    v.average = average(a.radars) if a.radars else None
    names = {g: p.name for g, p in a.roster.items()}
    awards = a.summary.awards if a.summary else []
    v.awards = [(aw.title, aw.blurb.rstrip("."), names.get(aw.guid, aw.guid), aw.stat, aw.good)
                for aw in sorted(awards, key=lambda aw: not aw.good)]
    me = next((k for k, c in enumerate(v.cards) if c.you), None)
    if me is None:
        return v
    you, pl = v.cards[me], a.ranking[me]
    v.place, v.reason = you.rank, you.reason
    v.death_at = min((d.t for d in a.deaths if d.guid == pl.guid), default=None)
    if me:
        v.behind_next = v.cards[me - 1].points - you.points
        v.behind_mvp = v.cards[0].points - you.points
        v.move_up = (move_up_title(pl.weaknesses[0] if pl.weaknesses else None),
                     _caption([aw.title for aw in pl.awards if not aw.good], v.behind_next))
    return v
