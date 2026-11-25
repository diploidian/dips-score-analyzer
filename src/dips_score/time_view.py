"""What "Where your time goes" on the Profile page shows, as plain data (no Qt), from live.days.figures of the last 15
days and of the 15 before: one bar of parts, the Player Type over it."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .live.days import MIN_SECONDS, PARTS

# part: (name, ink)
SHOWN = {"hunt": ("Hunting", "m-surv"), "quest": ("Questing", "role-tank"), "dungeon": ("Dungeons", "place-dungeon"),
         "raid": ("Raids", "place-raid"), "pvp": ("PvP", "place-pvp"), "craft": ("Gathering and crafting", "m-cd"),
         "trade": ("Auction house and mail", "gold"), "travel": ("Travelling", "place-world"), "town": ("In town", "m-act")}
NEED = "Your time bar fills in after you play and /reload with the add-on from 0.22 or newer."
CHIP_MIN = 5


@dataclass
class TimePart:
    name: str
    time: str       # "12 h 40 min"
    share: str      # "32%"
    width: float    # 0..1 of the bar
    ink: str
    chip: str = ""  # "+6 pts vs the 15 days before"


@dataclass
class TimeBar:
    need: str = NEED            # shown instead of the bar
    type: str = ""              # "Huntmaster, and part Errant"
    meta: str = ""              # "39 h 20 min played in the last 15 days, as of your last /reload or logout."
    parts: list[TimePart] = field(default_factory=list)        # largest first
    note: str = ""              # "31 quests handed in. 2 h 5 min away are left out."


def _hm(seconds: float) -> str:
    h, m = divmod(round(seconds / 60), 60)
    return f"{h} h {m} min" if h else f"{m} min"


def _day(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.day} {d:%b}"


def build_time(now: dict | None, before: dict | None) -> TimeBar:
    if not now:
        return TimeBar()
    if now["seconds"] < MIN_SECONDS:
        return TimeBar(f"Your time bar needs {MIN_SECONDS // 3600} hours of play with the add-on ({_hm(now['seconds'])} so far).")
    v = TimeBar("", now["type"] + (f", and part {PARTS[now['second']][2]}" if now["second"] else ""),
                f"{_hm(now['seconds'])} played {'since ' + _day(now['since']) + ', when counting began' if now['since'] else 'in the last 15 days'}, "
                "as of your last /reload or logout.")
    known = before and before["seconds"] >= MIN_SECONDS and not before["since"]
    for p, share in sorted(now["parts"].items(), key=lambda x: -x[1]):
        name, ink = SHOWN[p]
        part = TimePart(name, _hm(share * now["seconds"]), f"{share * 100:.0f}%" if share >= .005 else "under 1%", share, ink)
        d = round(share * 100) - round(before["parts"].get(p, 0) * 100) if known else 0
        if abs(d) >= CHIP_MIN:
            part.chip = f"{'+' if d > 0 else '−'}{abs(d)} pts vs the 15 days before"
        v.parts.append(part)
    quests = f"{now['turnins']:,} quest{'s' * (now['turnins'] != 1)} handed in." if now["turnins"] else ""
    away = f"{_hm(now['away'])} away left out." if now["away"] >= 60 else ""
    v.note = " ".join(filter(None, (quests, away)))
    return v
