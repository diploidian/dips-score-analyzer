"""Who you are as a player: the newest fight's character over the last 15 days (Now) against days 16 to 30
(Before). Pure data, plain JSON-able values; a figure that cannot be known is None, never a guess.

profile(fights, char, book, runs, now, types=None, acts=None) -> {"name", "char" (habits.char_block), "level" (the newest fight's), "now": figures (None only when
there are no fights at all), "before": figures or None when it has no fights}. Now is fights with start in (now - 15 days, now], Before (now - 30, now - 15].

runs are plain dicts from the recorded runs: start (datetime), role ("tank"/"healer"/"damage"/None), score, grade,
presses, by_key, by_click, failed, casts, combat_time (seconds), move_interrupts (casts the game cut because you
started to move) and wasted_cast_time (seconds lost to them); runs without both move keys are left out of those.
A run counts for a window when its start is inside it; the caller passes only this character's runs.
types is {enemy name: creature type} (the add-on's dipsScoreDB.types) or None; with the fights' saved chances it
decides whether a spell that needs a chance (scoring/usable.py: an enemy type, a low target, an avoided attack)
can count as unused.

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
                   casts. swings: Melee's swings summed over the fights that saved a count (a one-swing fight saves
                   none), None when that sum is 0
  opener           {"casts": [three names], "count": fights that opened so, "of": fights with three opening
                   casts}, or None
  hands            None without runs in the window; else {"runs", "presses", "by_key", "by_click", "key_share",
                   "click_share" (of keyed + clicked presses), "combat_seconds", "per_minute", "failed", "casts", "refused_share",
                   "move_runs" (runs carrying both move keys), "move_casts" (their casts), "move_interrupts",
                   "wasted_cast_time", "cut_share" (cut casts of move_casts); the last four None when move_runs is 0}
  temperament      {"deaths", "deaths_per_hour", "median_pull", "mean_pull", "alone" (fights against one enemy),
                   "lowest_hp" (mean, same scale as the fight's lowest_hp), "cooldowns_used", "cooldowns_possible",
                   "cooldowns_share"}
  unused           harmful spells known but not cast since the window's first fight (habits.idle_spells),
                   None without a snapshot or its harm flag; a spell in usable.RULES only with a known chance
  restricted       {spell: {"chances", "fights" (fights with one)}} (usable.window_chances) for the spells in
                   unused that need a chance
  damage           damage done in the fights Habits judges (not healing, some damage done), None when it adds to 0
  efficiency       damage over potential across those of them that saved both; judged: how many did
  losses           the cooldowns that sat ready in those that saved their damage, most damage first (habits.cooldown_losses, under 1 damage left
                   out, equal losses by name): {"name", "lost", "fights", "missed", "chances"}; a spell in
                   usable.RULES only from fights with a known chance (its ready time elsewhere may be time it
                   could not be used)
  close_calls      {"fights" (your health got low, in fights that say whether you answered it), "unused" (of them, a
                   defensive sat ready), "spell" (the one that did most often, by name on a tie), "count" (fights it did)}, the last two
                   None when unused is 0
  overheal         {"fights", "healing", "overheal"} of the healer fights, None when they healed nothing
  helping          helping.figures of acts (this character's only): strangers helped, revives, buffs for the group;
                   None without any act known
  label            label(figures), None without fights (shown for slices saved without a title)
  traits           [{"key", "family", "epithet" (None under tier 1) and traits.scores' entry}], the known ones, in the
                   table's order
  title, second, deeds, lead, epithet     titles.crest; title None without fights
  hero             {"figure" (text), "unit", "caption", "key"} of the title's trait, None without one
  rows, pack       titles.rows and the keys of How you fight's rows, in order
  outdated         fewer than half of the fights carry CURRENT, a key every fight summed up now has
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from statistics import median

from ..scoring import usable
from ..scoring.classes import talent_role
from ..scoring.score import grade
from . import helping, titles, traits
from .habits import _damage_fights, char_block, cooldown_losses, idle_spells

SLICE = timedelta(days=15)
ROLES = ("damage", "healer", "tank")
PLACES = ("Dungeon", "Raid", "World", "PvP")
OLD_PLACE = {"Dungeon": "Dungeon", "Boss": "Dungeon", "World": "World"}     # fights saved without a difficulty
# WoW difficulty ids of raids; any other difficulty inside an instance is a dungeon
RAID_DIFFICULTIES = {3, 4, 5, 6, 7, 9, 14, 15, 16, 17, 33, 148, 151, 175, 176, 185, 186, 193, 198, 215, 226}
TALENT = {"TANK": "tank", "HEALER": "healer", "DPS": "damage"}
TOP = 5
CURRENT = "helped"          # a fight summed up before 0.18.0 has none

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


def _signature(rows: dict[str, list], healer: bool) -> dict:
    """rows: traits.abilities' of the main role's fights"""
    total = sum(r[0 if healer else 3] for r in rows.values())
    spells = [{"name": n, "casts": r[0], "damage": r[3], "share": _share(r[0 if healer else 3], total),
               "swings": r[4] or None} for n, r in rows.items()]
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
    combat = s("combat_time")
    moved = [r for r in runs if r.get("move_interrupts") is not None and r.get("wasted_cast_time") is not None]
    m = lambda k: sum(r.get(k) or 0 for r in moved) if moved else None  # noqa: E731
    cut, move_casts = m("move_interrupts"), m("casts")
    return {"runs": len(runs), "presses": presses, "by_key": key, "by_click": click,
            "key_share": _share(key, key + click), "click_share": _share(click, key + click),   # "?" sources left out
            "combat_seconds": combat, "per_minute": _share(presses * 60, combat),
            "failed": failed, "casts": casts, "refused_share": _share(failed, casts + failed),
            "move_runs": len(moved), "move_casts": move_casts, "move_interrupts": cut,
            "wasted_cast_time": m("wasted_cast_time"), "cut_share": None if cut is None else _share(cut, move_casts)}


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


def _losses(dmg: list[dict]) -> list[dict]:
    """what each cooldown that sat ready cost over fights that did damage (see figures)"""
    rows = [c for f in dmg for c in f.get("cooldowns") or [] if c.get("chances") or not usable.rule(c.get("name"))]
    return sorted((s for s in cooldown_losses(rows) if s["lost"] >= 1), key=lambda s: (-s["lost"], s["name"]))


def _close_calls(win: list[dict]) -> dict:
    # "answered": without it the fight was summed up when a defensive pressed at the low moment still counted as unused
    danger = [f["danger"]["unused"] for f in win if "answered" in (f.get("danger") or {})]
    seen = Counter(n for names in danger for n in set(names or ()))
    spell = min(seen, key=lambda n: (-seen[n], n), default=None)
    return {"fights": len(danger), "unused": sum(map(bool, danger)), "spell": spell, "count": seen.get(spell)}


def _overheal(healing: list[dict]) -> dict | None:
    done, over = (sum(f.get(k) or 0 for f in healing) for k in ("healing", "overheal"))
    return {"fights": len(healing), "healing": done, "overheal": over} if done + over else None


def _restricted(win: list[dict], unused: list[str] | None, types: dict | None) -> dict:
    """the chances of the spells in unused that need one (idle_spells kept only those with a known chance)"""
    return {n: usable.window_chances(n, win, types) for n in unused or [] if usable.rule(n)}


def figures(mine: list[dict], char: dict | None, book: dict, runs: list[dict], lo: datetime, hi: datetime,
            types: dict | None = None, acts: list[dict] | None = None) -> dict:
    """the figures of one window (lo, hi] of one character's fights (see the module docstring)"""
    win = [f for f in mine if lo < datetime.fromisoformat(f["start"]) <= hi]
    runs = [r for r in runs if lo < r["start"] <= hi]
    cls = (char or {}).get("class")
    seconds = sum(f.get("duration") or 0 for f in win)
    by_role, by_place = Counter(), Counter()
    role = {id(f): _role(f, cls) for f in win}
    for f in win:
        by_role[role[id(f)]] += f.get("duration") or 0
        if place := _place(f):
            by_place[place] += f.get("duration") or 0
    roles = {r: _share(by_role[r], seconds) for r in ROLES}
    main = max(ROLES, key=lambda r: roles[r] or 0) if seconds else None
    unused = idle_spells(win, char, book, types) if win and char else None
    restricted = _restricted(win, unused, types)
    ab = traits.abilities(win, lambda f: main in (None, role[id(f)]))
    dmg = _damage_fights(win)
    both = [f for f in dmg if f.get("damage") and f.get("potential")]
    out = {"fights": len(win), "seconds": seconds, "roles": roles, "main_role": main,
           "places": {p: _share(by_place[p], seconds) for p in PLACES},
           "grades": _grades(runs),
           "signature": _signature(ab["main"], main == "healer"),
           "opener": _opener(win), "hands": _hands(runs), "temperament": _temperament(win, seconds),
           "unused": unused, "restricted": restricted,
           "damage": sum(f.get("damage") or 0 for f in dmg) or None,
           "efficiency": _share(sum(f["damage"] for f in both), sum(f["potential"] for f in both)),
           "judged": len(both), "losses": _losses([f for f in dmg if f.get("damage")]), "close_calls": _close_calls(win),
           "overheal": _overheal([f for f in win if role[id(f)] == "healer"]),
           "helping": helping.figures(acts, lo, hi)}
    out["label"] = label(out) if win else None
    sc = traits.scores(win, out, book, ab)
    specs = Counter(f["spec"] for f in win if f.get("spec"))
    spec = min(specs, key=lambda s: (-specs[s], s)) if specs else (char or {}).get("spec")
    out["traits"] = [{"key": k, "family": traits.BY_KEY[k].family, "epithet": traits.epithet(sc, k), **s}
                     for k, s in sc.items() if s]
    out |= titles.crest(win, out, sc, cls, spec, types)
    if not win:
        out["title"] = None
    out["hero"] = None
    if lead := out["lead"]:
        text, unit = traits.shown(sc[lead]["kind"], sc[lead]["figure"])
        out["hero"] = {"figure": text, "unit": unit, "caption": sc[lead]["caption"], "key": lead}
    out["rows"] = titles.rows(win, out, sc, ab["split"])
    out["pack"] = titles.pack(win, out, out["rows"], sc, out["lead"])
    out["outdated"] = bool(win) and sum(CURRENT in f for f in win) * 2 < len(win)
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
            now: datetime, types: dict | None = None, acts: list[dict] | None = None) -> dict:
    if not fights:
        return {"name": "", "char": None, "level": None, "now": None, "before": None}
    me = fights[-1]["me"]
    mine = [f for f in fights if f["me"] == me]
    book, runs = book or {}, runs or []
    before = figures(mine, char, book, runs, now - 2 * SLICE, now - SLICE, types, acts)
    return {"name": fights[-1].get("me_name", ""), "char": char_block(char), "level": fights[-1].get("level"),
            "now": figures(mine, char, book, runs, now - SLICE, now, types, acts),
            "before": before if before["fights"] else None}
