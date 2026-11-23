"""Who you are as a player: the newest fight's character over the last 15 days (Now) against days 16 to 30
(Before). Pure data, plain JSON-able values; a figure that cannot be known is None, never a guess.

profile(fights, char, book, runs, now) -> {"name", "char" (habits.char_block), "now": figures (None only when
there are no fights at all), "before": figures or None when it has no fights}. Now is fights with start in (now - 15 days, now], Before (now - 30, now - 15].

runs are plain dicts from the recorded runs: start (datetime), role ("tank"/"healer"/"damage"/None), score, grade,
presses, by_key, by_click, failed, casts, combat_time, moving_time (seconds). A run counts for a window when its
start is inside it; the caller passes only this character's runs.

figures(...) keys (shares are fractions 0..1; None when there is nothing to divide by):
  fights           fights in the window
  seconds          their summed duration
  roles            {"damage", "healer", "tank"} -> share of fight seconds
  main_role        the role with the largest share (None without fights)
  places           {"Dungeon" (Dungeon and Boss), "World", "PvP"} -> share of fight seconds
  grades           role -> {"runs": graded runs, "score": mean score, "grade": letter of that mean}, or None
  signature        {"basis": "damage" | "casts", "top": first 5 spells, "spells": every spell}, each spell
                   {"name", "casts", "damage", "share"}; ranked by share of damage, or for a healer by casts
                   (saved fights carry no healing per spell), share then being the share of casts
  opener           {"casts": [three names], "count": fights that opened so, "of": fights with three opening
                   casts}, or None
  hands            None without runs in the window; else {"runs", "presses", "by_key", "by_click", "key_share",
                   "click_share", "combat_seconds", "per_minute", "failed", "casts", "refused_share",
                   "moving_seconds", "moving_share"}
  temperament      {"deaths", "deaths_per_hour", "median_pull", "mean_pull", "alone" (fights against one enemy),
                   "lowest_hp" (mean, same scale as the fight's lowest_hp), "cooldowns_used", "cooldowns_possible",
                   "cooldowns_share"}
  unused           harmful spells known but not cast since the window's first fight (habits.idle_spells),
                   None without a snapshot or its harm flag
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
PLACE = {"Dungeon": "Dungeon", "Boss": "Dungeon", "World": "World", "PvP": "PvP"}
TALENT = {"TANK": "tank", "HEALER": "healer", "DPS": "damage"}
TOP = 5

# the label rule table: <temperament> <place> <role> [who <hands>]
ROLE_WORD = {"damage": "damage dealer", "healer": "healer", "tank": "tank"}
PLACE_WORD = {"Dungeon": "dungeon", "World": "world", "PvP": "PvP"}
ROLE_MIN = 0.60              # under this no role is the main one: "hybrid"
PLACE_MIN = 0.50             # under this the place is left out
CAREFUL = (1, 2)             # deaths per hour at most, median pull at most
RECKLESS = (4, 3)            # deaths per hour at least, median pull at least
HOARDING = 0.50              # cooldowns used under this share of possible
CLICKS, KEYBINDS = 0.30, 0.05


def _role(f: dict, cls: str | None) -> str:
    if f.get("healing_role"):
        return "healer"
    return TALENT.get(talent_role(cls, [(f.get("spec"), 1)]), "damage")


def _share(part, whole):
    return part / whole if whole else None


def _signature(win: list[dict], healer: bool) -> dict:
    casts, damage = Counter(), Counter()
    for f in win:
        for a in f.get("abilities") or []:
            casts[a["name"]] += a.get("casts", 0)
            damage[a["name"]] += a.get("damage", 0)
    total = sum(casts.values() if healer else damage.values())
    spells = [{"name": n, "casts": casts[n], "damage": damage[n],
               "share": _share(casts[n] if healer else damage[n], total)} for n in casts]
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
    presses, key, click, failed, casts = s("presses"), s("by_key"), s("by_click"), s("failed"), s("casts")
    combat, moving = s("combat_time"), s("moving_time")
    return {"runs": len(runs), "presses": presses, "by_key": key, "by_click": click,
            "key_share": _share(key, presses), "click_share": _share(click, presses),
            "combat_seconds": combat, "per_minute": _share(presses * 60, combat),
            "failed": failed, "casts": casts, "refused_share": _share(failed, casts + failed),
            "moving_seconds": moving, "moving_share": _share(moving, combat)}


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


def figures(mine: list[dict], char: dict | None, book: dict, runs: list[dict], lo: datetime, hi: datetime) -> dict:
    """the figures of one window (lo, hi] of one character's fights (see the module docstring)"""
    win = [f for f in mine if lo < datetime.fromisoformat(f["start"]) <= hi]
    runs = [r for r in runs if lo < r["start"] <= hi]
    cls = (char or {}).get("class")
    seconds = sum(f.get("duration") or 0 for f in win)
    by_role, by_place = Counter(), Counter()
    for f in win:
        by_role[_role(f, cls)] += f.get("duration") or 0
        if f.get("kind") in PLACE:
            by_place[PLACE[f["kind"]]] += f.get("duration") or 0
    roles = {r: _share(by_role[r], seconds) for r in ROLES}
    main = max(ROLES, key=lambda r: roles[r] or 0) if win else None
    out = {"fights": len(win), "seconds": seconds, "roles": roles, "main_role": main,
           "places": {p: _share(by_place[p], seconds) for p in ("Dungeon", "World", "PvP")},
           "grades": _grades(runs),
           "signature": _signature([f for f in win if _role(f, cls) == main] or win, main == "healer"),
           "opener": _opener(win), "hands": _hands(runs), "temperament": _temperament(win, seconds),
           "unused": idle_spells(win, char, book) if win and char else None}
    out["label"] = label(out) if win else None
    return out


def label(fig: dict) -> str:
    """"Careful dungeon healer who clicks.": temperament, place, role, and hands when a hands trait is strong"""
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
    hands, who = fig.get("hands"), None
    if hands and hands["click_share"] is not None:
        who = "clicks" if hands["click_share"] >= CLICKS else "keybinds" if hands["click_share"] < KEYBINDS else None
    s = " ".join(w for w in (mood, place, role) if w) + (f" who {who}" if who else "")
    return s[0].upper() + s[1:] + "."


def profile(fights: list[dict], char: dict | None, book: dict | None, runs: list[dict] | None,
            now: datetime) -> dict:
    if not fights:
        return {"name": "", "char": None, "now": None, "before": None}
    me = fights[-1]["me"]
    mine = [f for f in fights if f["me"] == me]
    book, runs = book or {}, runs or []
    before = figures(mine, char, book, runs, now - 2 * SLICE, now - SLICE)
    return {"name": fights[-1].get("me_name", ""), "char": char_block(char),
            "now": figures(mine, char, book, runs, now - SLICE, now),
            "before": before if before["fights"] else None}
