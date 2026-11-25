"""What your own hits say a stat is worth, and how your swings land. Pure data, from the fights' saved "power" cells
([name, spell id (0: a swing), attack power, spell power, hits, sum of base damage, sum of its squares]; the log's
numbers, before armor, crits and glancing) and swing counts. A slope that is not clear of its own error is never shown.

The log's attack power is another number than the game's, but rises and falls with it while the weapon is the same, so
a slope over it holds; a level of it means nothing."""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timedelta
from math import sqrt

MIN_HITS, MIN_AT_ONE = 100, 30      # hits a slope needs, and hits at each of two spell powers
CLEAR = 4                           # a slope is at least this many times its own error
ROLL = 0.06                         # a day's spread this near the weapon's own roll: nothing else moved its swings
NONE_SEEN = 0.05                    # "none seen": 10 points can't be worth more than this share of the hit


def _at(record: list[tuple] | None, when: datetime):
    """what the add-on's record [(time(), what)] says it was then; None before it"""
    order = sorted(record or [])
    at = bisect_right([t for t, _ in order], when.timestamp())
    return order[at - 1][1] if at else None


def level_at(levels: list[tuple[int, int]] | None, iso: str) -> int | None:
    """the character's level at that time, by the add-on's record of them; None before it"""
    return _at(levels, datetime.fromisoformat(iso))


def _with(f: dict, weapon: tuple | None, weapons: list[tuple] | None) -> bool:
    """whether the fight was fought with that weapon (item id, enchant id or None: not read), start to end; a fight from
    before the record may have been"""
    start = datetime.fromisoformat(f["start"])
    held = {_at(weapons, start), _at(weapons, start + timedelta(seconds=f.get("duration") or 0))}
    held |= {w for t, w in weapons or [] if start.timestamp() < t <= start.timestamp() + (f.get("duration") or 0)}
    if None in held:
        return held == {None}
    return weapon is not None and all(w[0] == weapon[0] and weapon[1] in (None, w[1]) for w in held)


def leveled(fights: list[dict], char: dict | None) -> list[dict]:
    """the fights with the level each was fought at, where the add-on recorded it"""
    levels = (char or {}).get("levels")
    return [{**f, "level": level_at(levels, f["start"])} for f in fights] if levels else fights


def _sums(cells) -> list[float]:
    """n, then the sums of products about the group's means xx, xa, aa, xy, ay, yy; cells: (x, a, hits, sum, squares)"""
    n = sum(c[2] for c in cells)
    mx, ma = sum(c[0] * c[2] for c in cells) / n, sum(c[1] * c[2] for c in cells) / n
    my = sum(c[3] for c in cells) / n
    return [n, sum(c[2] * (c[0] - mx) ** 2 for c in cells), sum(c[2] * (c[0] - mx) * (c[1] - ma) for c in cells),
            sum(c[2] * (c[1] - ma) ** 2 for c in cells), sum((c[0] - mx) * c[3] for c in cells),
            sum((c[1] - ma) * c[3] for c in cells), sum(c[4] for c in cells) - n * my * my]


def _slope(groups: list[list[float]]) -> tuple[float, float, int] | None:
    """(what one more x adds with a held still, its standard error, hits), each group about its own mean"""
    if not groups:
        return None
    n, xx, xa, aa, xy, ay, yy = (sum(g) for g in zip(*groups))
    if aa > 0:
        xx, xy, yy = xx - xa * xa / aa, xy - xa * ay / aa, yy - ay * ay / aa
    free = n - len(groups) - 2
    if xx <= 1e-6 * n or free < 1:
        return None
    b = xy / xx
    return b, sqrt(max(0.0, yy - b * xy) / free / xx), n


def swing(win: list[dict], low: float | None, high: float | None, weapon: tuple | None = None,
          weapons: list[tuple] | None = None) -> dict | None:
    """what one attack power adds to a swing: {"value", "error", "n"}. low, high: the damage the game says a swing does with
    weapon (item id, enchant id); weapons: the add-on's record of the main hand, only fights with that weapon once it begins.
    And only the days whose swings spread as that weapon's roll does: another weapon or a buff on swings spreads them more"""
    if not low or not high or high <= low:
        return None
    roll = (high - low) / sqrt(12)
    days = defaultdict(list)
    for f in win:
        if _with(f, weapon, weapons):
            days[f["start"][:10]] += [(c[2], 0, *c[4:7]) for c in f.get("power") or [] if not c[1]]
    good = []
    for cells in days.values():
        if sum(c[2] for c in cells) >= MIN_AT_ONE and (s := _sums(cells))[1] > 0:
            spread = sqrt(max(0.0, s[6] - s[4] ** 2 / s[1]) / (s[0] - 2))
            if abs(spread - roll) <= min(ROLL, 1.5 / sqrt(s[0])) * roll:      # the more swings, the nearer it must be
                good.append(s)
    got = _slope(good)
    if not got or got[2] < MIN_HITS or got[0] < CLEAR * got[1]:
        return None
    return {"value": got[0], "error": got[1], "n": got[2]}


def spells(win: list[dict], levels: list[tuple[int, int]] | None) -> list[dict]:
    """what one spell power adds to a hit of each spell, attack power held still, most first: {"name", "value" (0.0: none
    seen), "error", "n"}; compared only within one rank, at one character level, on one day (gear changes over days)"""
    by: dict[tuple, dict] = defaultdict(lambda: defaultdict(list))
    for f in win:
        level = level_at(levels, f["start"])
        for c in f.get("power") or [] if level else ():
            if c[1]:
                by[c[0], c[1]][level, f["start"][:10]].append((c[3], c[2], *c[4:7]))
    best: dict[str, dict] = {}
    for (name, _), groups in by.items():
        kept = []
        for cells in groups.values():
            at = defaultdict(int)
            for c in cells:
                at[c[0]] += c[2]
            if sum(n >= MIN_AT_ONE for n in at.values()) >= 2:
                kept.append(cells)
        got = _slope([_sums(c) for c in kept])
        if not got or got[2] < MIN_HITS:
            continue
        b, err, n = got
        mean = sum(c[3] for cells in kept for c in cells) / n
        none = abs(b) <= 2 * err and 10 * (abs(b) + 2 * err) <= NONE_SEEN * mean
        if (none or (b > 0 and b >= CLEAR * err)) and n > best.get(name, {"n": 0})["n"]:     # of its ranks, the most cast
            best[name] = {"name": name, "value": 0.0 if none else b, "error": err, "n": n}
    return sorted(best.values(), key=lambda s: (-s["value"], s["name"]))


def hits(win: list[dict]) -> dict | None:
    """how your swings landed: {"n" (all of them), "miss", "dodge", "parry", "block", "glancing", "crit" (counts),
    "glancing_cost" (the share of a plain hit on the same enemy a glancing one loses, None when too few)}; None under MIN_HITS"""
    auto = [f["auto"] for f in win if (f.get("auto") or {}).get("misses") is not None]
    missed = {k: sum(a["misses"].get(k, 0) for a in auto) for k in ("miss", "dodge", "parry", "block")}
    n = sum(a["landed"] + sum(a["misses"].values()) for a in auto)
    if n < MIN_HITS:
        return None
    glanced, did, plain = (sum(v) for v in zip(*(a.get("glance") or (0, 0, 0) for a in auto)))
    cost = 1 - did / plain if glanced >= MIN_AT_ONE and plain else None
    return {"n": n, **missed, "glancing": sum(a["glancing"] for a in auto), "crit": sum(a["crits"] for a in auto),
            "glancing_cost": cost}
