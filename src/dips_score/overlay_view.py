"""What the after-fight card shows (docs/design/mockups/fight-card.html), as plain data (no Qt), from a live fight
(live/summary.py's dict): the fight in a line, how much of the damage you could have done you did, the verdict, the
biggest gap (or your death) and what else the dict knows. The Fight page's helpers decide the figure and the gap, so
the card and the page agree. Missing keys (an old saved fight, the stand-in shown while moving the card) leave their
part out."""
from dataclasses import dataclass, field
from datetime import datetime

from .debrief import fmt_time
from .fight_view import CLEAN, _hero, _losses, _n
from .live.profile import place

PANEL_ALPHA = 232      # the card's panel over the game (of 255): its inks are checked on that blend (the tests)


@dataclass
class CardView:
    name: str                   # the head, in capitals: the boss, "Trash" in a dungeon, the zone in the open world
    at: str                     # the clock when the fight began ("" unknown)
    length: str                 # "90 s", "3:03" from two minutes
    kind: str                   # the tag on the right: "Boss kill", "Boss", "PvP"; "" for none
    efficiency: float | None    # None: not measured (an older fight), or no damage done
    clean: bool                 # 90% or more, and alive: no gap box
    verdict: str
    gap: tuple[str, str] | None     # the plate band: (words, emphasis), "Biggest gap" or, when died, "Death"
    chips: list[str] = field(default_factory=list)
    boss: bool = False
    big: str = "–"              # the figure ("80%", "–") and the words beside it
    caption: str = ""
    died: bool = False
    updated: bool = False       # a combat that carried on: this card replaced its first one


def shows(settings: dict, d: dict) -> bool:
    """whether a fight gets a card by itself (Settings, After each fight)"""
    return bool(settings.get("overlay", True)) and (not settings.get("overlay_dungeons") or place(d) in ("Dungeon", "Raid"))


def _name(d: dict) -> str:
    kind = d.get("kind")
    if kind == "Dungeon":
        return "Trash"
    if kind == "World":
        return d.get("zone") or d["target"]
    return d["target"]


def _death(d: dict) -> tuple[str, str]:
    """when you died (fight time; the end when there's no health data) and the defensives that were ready"""
    danger = d.get("danger") or {}
    unused = danger.get("unused") or [] if "answered" in danger else []     # see fight_view._danger
    ready = f"{' and '.join(unused[:2])} {'was' if len(unused) == 1 else 'were'} ready" if unused else ""
    return f"Died at {fmt_time(danger.get('t', d['duration']))}" + (" ·" if ready else ""), ready


def build_card(d: dict) -> CardView:
    """the card for one live fight"""
    eff = d.get("efficiency")
    if not d["damage"] and not d.get("healing_role"):
        eff = None                    # 100% of nothing: not a figure
    died = d.get("result") == "you died"
    boss = d.get("kind") == "Boss"
    tag = ("Boss kill" if d.get("result") == "killed" else "Boss") if boss else "PvP" if d.get("kind") == "PvP" else ""
    big, unit, caption = _hero(d, eff)
    v = CardView(
        name=_name(d), at=f"{datetime.fromisoformat(d['start']):%H:%M}" if d.get("start") else "",
        length=f"{d['duration']:.0f} s" if d["duration"] < 120 else fmt_time(d["duration"]),
        kind=tag, efficiency=eff, clean=eff is not None and eff >= CLEAN and not died,
        verdict=d.get("verdict") or "", gap=None, boss=boss, big=big + (unit or ""), caption=caption, died=died,
        updated=bool(d.get("updated")))
    if died:
        v.gap = _death(d)
    elif not v.clean and (losses := _losses(d)[0]):
        label, detail, lost, _ = losses[0]
        v.gap = (label, " · ".join(s for s in (detail, f"≈ {_n(lost)} damage") if s))
    hp = (d.get("resource") or {}).get("start_hp")
    if hp is not None and round(hp * 100) < 100:      # entering at full is every fight: only a lower one says something
        v.chips.append(f"Entered at {hp:.0%} hp")
    return v
