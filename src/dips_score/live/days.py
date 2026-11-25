"""Where your time goes, from what the add-on (Life.lua) counted per day, and the Player Type it makes. Pure data.

figures(time, lo, hi, fights=()) -> None when the window has no day, else {"seconds" (played, away left out), "away", "turnins",
"since" (the first day counted, ISO, when that is later than the window's first: the rest is not known; else None),
"parts" {part: share of seconds, 0..1, those with any}, "type", "lead" (its part), "second" (a part, or None)}. time is
{"2026-11-24": {column: seconds}}; a day belongs to the window (lo, hi] by its date, so each day is in one of two
neighbouring windows. "type" and what follows are None under MIN_SECONDS. fights: the character's; those against players outside
an instance are the least a day's "skirmish" can be, since the add-on sees an enemy player only while you target one: what is missing is
taken from what it took the time for. Not on the first day counted, which it may have joined halfway.

trade(time, lo, hi) -> None when the window has no auction house time and no auction money, else {"auction" (seconds with it
open), "spent", "came" (copper: spent while it was open, in from auction mails), "sales" (sale mails), "sold" (their items),
"unread" (sale mails that did not say how many), "blind" (mails whose money could not be read), "seconds" (played, as figures), "since" (the first day the add-on counted trade,
when later than the window's first)}.

The type is the part furthest over its own bar. The bars differ because the parts do: an hour at the auction house is a
lot, an hour of travel is not. Both they and the names are fixed by hand, as the traits' ends are.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

MIN_SECONDS = 5 * 3600
SECOND = 0.20
# part: (its columns, its bar, the type)
PARTS = {"quest": (("quest",), .35, "Errant"),
         "hunt": (("hunt",), .30, "Huntmaster"),
         "dungeon": (("dungeon",), .30, "Delver"),
         "raid": (("raid",), .25, "Siegebreaker"),
         "pvp": (("pvp", "skirmish"), .25, "Warmonger"),
         "craft": (("craft", "gather"), .20, "Artisan"),
         "trade": (("trade",), .15, "Merchant Prince"),
         "travel": (("taxi", "roam"), .35, "Wayfarer"),
         "town": (("town",), .35, "Hearthkeeper")}
NONE = "Adventurer"
TRADE = ("auction", "spent", "mailin", "sales", "sold", "unread", "blind")       # the add-on's trade columns (0.7.0)
TAKEN_AS = ("hunt", "quest", "gather", "roam", "town")      # what a fight with a player counted as when it was not seen


def _skirmishes(day: dict[str, float], least: float) -> dict[str, float]:
    day = dict(day)
    missing = least - (day.get("skirmish") or 0)
    for col in TAKEN_AS:
        took = min(day.get(col) or 0, max(0.0, missing))
        if took:
            day[col] -= took
            day["skirmish"] = (day.get("skirmish") or 0) + took
            missing -= took
    return day


def figures(time: dict[str, dict[str, float]] | None, lo: datetime, hi: datetime, fights=()) -> dict | None:
    least: Counter = Counter()
    for f in fights:
        if f.get("kind") == "PvP" and not f.get("instance"):
            least[f["start"][:10]] += f.get("duration") or 0
    days = [_skirmishes(d, least[day] if day != min(time) else 0) for day, d in (time or {}).items() if lo.date() < datetime.fromisoformat(day).date() <= hi.date()]
    if not days:
        return None
    first = min(time)
    total = lambda *cols: sum(d.get(c) or 0 for d in days for c in cols)  # noqa: E731
    each = {p: total(*cols) for p, (cols, _, _) in PARTS.items()}
    seconds = sum(each.values())
    parts = {p: s / seconds for p, s in each.items() if s}
    out = {"seconds": seconds, "away": total("away"), "turnins": round(total("turnins")), "parts": parts,
           "since": first if datetime.fromisoformat(first).date() > lo.date() + timedelta(days=1) else None,
           "type": None, "lead": None, "second": None}
    if seconds < MIN_SECONDS:
        return out
    over = {p: s / PARTS[p][1] for p, s in parts.items() if s >= PARTS[p][1]}
    out["lead"] = max(over, key=over.get, default=None)
    out["type"] = PARTS[out["lead"]][2] if over else NONE
    rest = {p: s for p, s in parts.items() if p != out["lead"] and (s >= SECOND or p in over)}
    out["second"] = max(rest, key=rest.get, default=None)
    return out


def trade(time: dict[str, dict[str, float]] | None, lo: datetime, hi: datetime) -> dict | None:
    days = {day: d for day, d in (time or {}).items() if lo.date() < datetime.fromisoformat(day).date() <= hi.date()}
    total = lambda col: sum(d.get(col) or 0 for d in days.values())  # noqa: E731
    if not (total("auction") or total("mailin") or total("spent")):
        return None
    first = min((day for day, d in (time or {}).items() if any(c in d for c in TRADE)), default=None)
    return {"auction": total("auction"), "spent": round(total("spent")), "came": round(total("mailin")), "sales": round(total("sales")),
            "sold": round(total("sold")), "unread": round(total("unread")), "blind": round(total("blind")),
            "seconds": sum(total(c) for cols, _, _ in PARTS.values() for c in cols),
            "since": first if first and datetime.fromisoformat(first).date() > lo.date() + timedelta(days=1) else None}
