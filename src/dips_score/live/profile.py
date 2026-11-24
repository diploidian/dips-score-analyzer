"""Who you are as a player: the newest fight's character over the last 15 days (Now) against days 16 to 30
(Before). Pure data, plain JSON-able values; a figure that cannot be known is None, never a guess.

profile(fights, char, book, runs, now, types=None) -> {"name", "char" (habits.char_block), "level" (the newest fight's), "now": figures (None only when
there are no fights at all), "before": figures or None when it has no fights}. Now is fights with start in (now - 15 days, now], Before (now - 30, now - 15].

runs are plain dicts from the recorded runs: start (datetime), role ("tank"/"healer"/"damage"/None), score, grade,
presses, by_key, by_click, failed, casts, combat_time (seconds), move_interrupts (casts the game cut because you
started to move) and wasted_cast_time (seconds lost to them); a run without a move key leaves that figure None.
A run counts for a window when its start is inside it; the caller passes only this character's runs.
types is {enemy name: creature type} (the add-on's dipsScoreDB.types) or None; it decides whether a spell that
only works on some enemy types (RESTRICTED) can count as unused.

figures(...) keys (shares are fractions 0..1; None when there is nothing to divide by):
  fights           fights in the window
  seconds          their summed duration
  roles            {"damage", "healer", "tank"} -> share of fight seconds
  main_role        the role with the largest share (None without fights)
  places           {"Dungeon", "Raid", "World", "PvP"} -> share of fight seconds (see _place)
  grades           role -> {"runs": graded runs, "score": mean score, "grade": letter of that mean}, or None
  signature        {"basis": "damage" | "casts", "top": first 5 spells, "spells": every spell}, each spell
                   {"name", "casts", "damage", "share", "swings"}: every row of the fights' abilities, Melee
                   (auto attack) and procs included, so the shares add to 1; ranked by share of damage, or for a
                   healer by casts (saved fights carry no healing per spell), share then being the share of
                   casts. swings: Melee's swings when every fight with Melee saved a count, else None
  opener           {"casts": [three names], "count": fights that opened so, "of": fights with three opening
                   casts}, or None
  hands            None without runs in the window; else {"runs", "presses", "by_key", "by_click", "key_share",
                   "click_share" (of keyed + clicked presses), "combat_seconds", "per_minute", "failed", "casts", "refused_share",
                   "move_interrupts", "wasted_cast_time", "cut_share" (cut casts of all casts)}
  temperament      {"deaths", "deaths_per_hour", "median_pull", "mean_pull", "alone" (fights against one enemy),
                   "lowest_hp" (mean, same scale as the fight's lowest_hp), "cooldowns_used", "cooldowns_possible",
                   "cooldowns_share"}
  unused           harmful spells known but not cast since the window's first fight (habits.idle_spells),
                   None without a snapshot or its harm flag; a RESTRICTED spell only when you met its types
  restricted       {spell: {"types": [creature types], "foes": enemies of those types met, "fights": fights they
                   were in}} for the RESTRICTED spells in unused
  label            label(figures), None without fights
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from statistics import median

from ..scoring.classes import talent_role
from ..scoring.score import grade
from .habits import char_block, idle_spells

SLICE = timedelta(days=15)
ROLES = ("damage", "healer", "tank")
PLACES = ("Dungeon", "Raid", "World", "PvP")
OLD_PLACE = {"Dungeon": "Dungeon", "Boss": "Dungeon", "World": "World"}     # fights saved without a difficulty
# WoW difficulty ids of raids; any other difficulty inside an instance is a dungeon
RAID_DIFFICULTIES = {3, 4, 5, 6, 7, 9, 14, 15, 16, 17, 33, 148, 151, 175, 176, 185, 186, 193, 198, 215, 226}
# spells that only work on some creature types, by name: never unused unless you met enemies of those types
RESTRICTED = {"Exorcism": ("Undead", "Demon"), "Holy Wrath": ("Undead", "Demon"), "Turn Undead": ("Undead",)}
TALENT = {"TANK": "tank", "HEALER": "healer", "DPS": "damage"}
TOP = 5

# the label rule table: <temperament> <place> <role>
ROLE_WORD = {"damage": "damage dealer", "healer": "healer", "tank": "tank"}
PLACE_WORD = {"Dungeon": "dungeon", "Raid": "raid", "World": "world", "PvP": "PvP"}
ROLE_MIN = 0.60              # under this no role is the main one: "hybrid"
PLACE_MIN = 0.50             # under this the place is left out
CAREFUL = (1, 2)             # deaths per hour at most, median pull at most
RECKLESS = (4, 3)            # deaths per hour at least, median pull at least
HOARDING = 0.50              # cooldowns used under this share of possible


def _role(f: dict, cls: str | None) -> str:
    if f.get("healing_role"):
        return "healer"
    return TALENT.get(talent_role(cls, [(f.get("spec"), 1)]), "damage")


def _place(f: dict) -> str | None:
    """PvP; inside an instance Raid by its difficulty, else Dungeon; outside one World, a world boss too"""
    if f.get("kind") == "PvP":
        return "PvP"
    if "difficulty" not in f:
        return OLD_PLACE.get(f.get("kind"))
    if f.get("instance") or f["difficulty"]:
        return "Raid" if f["difficulty"] in RAID_DIFFICULTIES else "Dungeon"
    return "World"


def _share(part, whole):
    return part / whole if whole else None


def _signature(win: list[dict], healer: bool) -> dict:
    casts, damage, swings, counted = Counter(), Counter(), 0, True
    for f in win:
        for a in f.get("abilities") or []:
            casts[a["name"]] += a.get("casts", 0)
            damage[a["name"]] += a.get("damage", 0)
            if a["name"] == "Melee":
                n = (f.get("auto") or {}).get("swings")
                counted, swings = counted and n is not None, swings + (n or 0)
    total = sum(casts.values() if healer else damage.values())
    spells = [{"name": n, "casts": casts[n], "damage": damage[n],
               "share": _share(casts[n] if healer else damage[n], total),
               "swings": swings if n == "Melee" and counted else None} for n in casts]
    spells.sort(key=lambda s: (-(s["casts"] if healer else s["damage"]), -s["casts"], s["name"]))
    return {"basis": "casts" if healer else "damage", "top": spells[:TOP], "spells": spells}


def _opener(win: list[dict]) -> dict | None:
    seen = Counter(tuple(o) for f in win if len(o := f.get("opener") or []) == 3)
    if not seen:
        return None
    casts, count = seen.most_common(1)[0]
    return {"casts": list(casts), "count": count, "of": sum(seen.values())}


def _hands(runs: list[dict]) -> dict | None:
    if not runs:
        return None
    s = lambda k: sum(r.get(k) or 0 for r in runs)  # noqa: E731
    known = lambda k: s(k) if all(r.get(k) is not None for r in runs) else None  # noqa: E731
    presses, key, click, failed, casts = s("presses"), s("by_key"), s("by_click"), s("failed"), s("casts")
    combat, cut = s("combat_time"), known("move_interrupts")
    return {"runs": len(runs), "presses": presses, "by_key": key, "by_click": click,
            "key_share": _share(key, key + click), "click_share": _share(click, key + click),   # "?" sources left out
            "combat_seconds": combat, "per_minute": _share(presses * 60, combat),
            "failed": failed, "casts": casts, "refused_share": _share(failed, casts + failed),
            "move_interrupts": cut, "wasted_cast_time": known("wasted_cast_time"),
            "cut_share": None if cut is None else _share(cut, casts)}


def _grades(runs: list[dict]) -> dict:
    out = {}
    for role in ROLES:
        scores = [r["score"] for r in runs if r.get("role") == role and r.get("score") is not None]
        mean = sum(scores) / len(scores) if scores else None
        out[role] = None if mean is None else {"runs": len(scores), "score": mean, "grade": grade(mean)}
    return out


def _temperament(win: list[dict], seconds: float) -> dict:
    deaths = sum(f.get("result") == "you died" for f in win)
    pulls = [1 + f["more"] for f in win if f.get("more") is not None]
    low = [f["lowest_hp"] for f in win if f.get("lowest_hp") is not None]
    rows = [c for f in win for c in f.get("cooldowns") or [] if not c.get("held") and "possible" in c]
    possible = sum(c["possible"] for c in rows)
    used = possible - sum(c.get("missed", 0) for c in rows)
    return {"deaths": deaths, "deaths_per_hour": _share(deaths * 3600, seconds),
            "median_pull": median(pulls) if pulls else None, "mean_pull": _share(sum(pulls), len(pulls)),
            "alone": sum(p == 1 for p in pulls), "lowest_hp": _share(sum(low), len(low)),
            "cooldowns_used": used if rows else None, "cooldowns_possible": possible if rows else None,
            "cooldowns_share": _share(used, possible)}


def _restricted(win: list[dict], unused: list[str] | None, types: dict | None) -> tuple[list[str] | None, dict]:
    """unused less the RESTRICTED spells whose enemy types you did not meet (or that cannot be known), and the
    met ones' counts"""
    if unused is None:
        return None, {}
    keep, met = [], {}
    for name in unused:
        kinds = RESTRICTED.get(name)
        if kinds is None:
            keep.append(name)
            continue
        per = [sum(c for foe, c in f.get("foes") or [] if (types or {}).get(foe) in kinds) for f in win]
        if sum(per):
            keep.append(name)
            met[name] = {"types": list(kinds), "foes": sum(per), "fights": sum(n > 0 for n in per)}
    return keep, met


def figures(mine: list[dict], char: dict | None, book: dict, runs: list[dict], lo: datetime, hi: datetime,
            types: dict | None = None) -> dict:
    """the figures of one window (lo, hi] of one character's fights (see the module docstring)"""
    win = [f for f in mine if lo < datetime.fromisoformat(f["start"]) <= hi]
    runs = [r for r in runs if lo < r["start"] <= hi]
    cls = (char or {}).get("class")
    seconds = sum(f.get("duration") or 0 for f in win)
    by_role, by_place = Counter(), Counter()
    for f in win:
        by_role[_role(f, cls)] += f.get("duration") or 0
        if place := _place(f):
            by_place[place] += f.get("duration") or 0
    roles = {r: _share(by_role[r], seconds) for r in ROLES}
    main = max(ROLES, key=lambda r: roles[r] or 0) if seconds else None
    unused, restricted = _restricted(win, idle_spells(win, char, book) if win and char else None, types)
    out = {"fights": len(win), "seconds": seconds, "roles": roles, "main_role": main,
           "places": {p: _share(by_place[p], seconds) for p in PLACES},
           "grades": _grades(runs),
           "signature": _signature([f for f in win if _role(f, cls) == main] or win, main == "healer"),
           "opener": _opener(win), "hands": _hands(runs), "temperament": _temperament(win, seconds),
           "unused": unused, "restricted": restricted}
    out["label"] = label(out) if win else None
    return out


def label(fig: dict) -> str:
    """"Careful dungeon healer.": temperament, place, role (how you press shows on the plate, not here)"""
    roles = fig["roles"]
    top = max(ROLES, key=lambda r: roles.get(r) or 0)
    role = ROLE_WORD[top] if (roles.get(top) or 0) >= ROLE_MIN else "hybrid"
    places = fig["places"]
    where = max(places, key=lambda p: places[p] or 0, default=None)
    place = PLACE_WORD[where] if where and (places[where] or 0) >= PLACE_MIN else None
    t = fig["temperament"]
    dph, pull, cds = t["deaths_per_hour"], t["median_pull"], t["cooldowns_share"]
    mood = None
    if dph is not None and pull is not None:
        if dph <= CAREFUL[0] and pull <= CAREFUL[1]:
            mood = "careful"
        elif dph >= RECKLESS[0] and pull >= RECKLESS[1]:
            mood = "reckless"
    if mood is None and cds is not None and cds < HOARDING:
        mood = "hoarding"
    s = " ".join(w for w in (mood, place, role) if w)
    return s[0].upper() + s[1:] + "."


def profile(fights: list[dict], char: dict | None, book: dict | None, runs: list[dict] | None,
            now: datetime, types: dict | None = None) -> dict:
    if not fights:
        return {"name": "", "char": None, "level": None, "now": None, "before": None}
    me = fights[-1]["me"]
    mine = [f for f in fights if f["me"] == me]
    book, runs = book or {}, runs or []
    before = figures(mine, char, book, runs, now - 2 * SLICE, now - SLICE, types)
    return {"name": fights[-1].get("me_name", ""), "char": char_block(char), "level": fights[-1].get("level"),
            "now": figures(mine, char, book, runs, now - SLICE, now, types),
            "before": before if before["fights"] else None}
