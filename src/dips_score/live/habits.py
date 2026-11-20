"""Habits across many fights: what you keep doing right, what keeps costing you, and the pace of this session.

Takes the saved fight summaries (oldest first) and looks at the newest fight's character only. Older saves
lack some keys, so everything is read with .get().

DPS is the damage that was possible per second times efficiency. Efficiency is your play; what was possible
moves with gear, level and what you fought. So when DPS moves between the trend's halves, the change in mean
efficiency is the part from play and the rest is everything else (not only gear).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from .summary import MASHING, gear_level

WINDOW = 40                  # fights looked at; the trend compares the last 20 with the 20 before
TREND_MIN = 5                # fights needed in each half of the trend
MOVE = 3                     # efficiency points between the trend's halves that count as dropping or improving
SESSION_GAP = 30 * 60        # seconds between fights that still count as one sitting
ORDER = {"fix": 0, "build": 1, "keep": 2}
UNUSED_SHOWN = 3             # spells named in the "you know ... but never cast" card
SKILL_MOVE = 0.05            # DPS change between the trend's halves that gets the skill-against-gear card
PULL_MATCH = 10              # seconds between a fight's start and the add-on's pull record that still match
WORN = 20                    # durability percent under which gear is nearly broken
# gear slots worth filling, in the order they are named
SLOTS = [(1, "head"), (2, "neck"), (3, "shoulder"), (5, "chest"), (6, "waist"), (7, "legs"), (8, "feet"),
         (9, "wrist"), (10, "hands"), (11, "ring 1"), (12, "ring 2"), (13, "trinket 1"), (14, "trinket 2"),
         (15, "back"), (16, "main hand")]


def _mean(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _session(fights: list[dict]) -> dict | None:
    run = fights[-1:]
    for f in reversed(fights[:-1]):
        if (_t(run[0]["start"]) - _t(f["end"])).total_seconds() >= SESSION_GAP:
            break
        run.insert(0, f)
    if not run:
        return None
    hours = (_t(run[-1]["end"]) - _t(run[0]["start"])).total_seconds() / 3600
    kills = sum(f.get("result") == "killed" for f in run)
    pull = lambda f: f.get("pull") or {}  # noqa: E731
    res = lambda f: f.get("resource") or {}  # noqa: E731
    return {"fights": len(run), "kills": kills, "kills_per_hour": kills / hours if hours > 0 else None,
            "avg_gap": _mean(pull(f).get("since_last") for f in run[1:]),
            "avg_rest": _mean(pull(f).get("rest") for f in run),
            "avg_start_hp": _mean(res(f).get("start_hp") for f in run),
            "avg_start_mana": _mean(res(f).get("start") for f in run if res(f).get("type") == 0)}


def _damage_fights(win: list[dict]) -> list[dict]:
    """the fights that say how you do damage: not healing, and some damage done (a stray hit you never answered
    has 0% efficiency and says nothing about your play); older saves without "damage" count"""
    return [f for f in win if not f.get("healing_role") and f.get("damage", 1) > 0]


def _damage_cards(win: list[dict]) -> list[tuple]:
    out = []
    dmg = _damage_fights(win)
    eff = [f.get("efficiency", 1.0) for f in dmg]
    if len(eff) >= TREND_MIN:
        cur, prev = eff[-20:], eff[-40:-20]
        a = _mean(cur) * 100
        p = _mean(prev) * 100 if len(prev) >= TREND_MIN else None
        msg = f"Last {len(cur)} fights {a:.1f}% efficiency"
        trend = {"recent": a, "before": p}       # in percent; before None when there's nothing to compare
        if p is not None:
            msg += f" vs {p:.1f}% in the {len(prev)} before"
            if a - p <= -MOVE:
                out.append(("fix", "Efficiency is dropping", msg, trend))
            elif a - p >= MOVE:
                out.append(("keep", "Efficiency is improving", msg, trend))
        if not out:
            out.append(("keep", "Efficiency is steady", msg, trend) if a >= 75 else
                       ("fix", "Efficiency is stuck low", msg, trend))
    lost, seen, missed, rows = Counter(), Counter(), Counter(), False
    for f in dmg:
        for c in f.get("cooldowns") or []:
            rows = True
            lost[c["name"]] += c["lost"]
            seen[c["name"]] += c["lost"] > 0
            missed[c["name"]] += 0 if c.get("held") else c.get("counted", 0)    # older saves have no "counted"
    if lost and lost.most_common(1)[0][1] >= 1:
        name, total = lost.most_common(1)[0]
        casts = f", {missed[name]} casts missed" if missed[name] else ""
        out.append(("fix", f"{name} left unused", f"About {total:,.0f} damage lost{casts} in {seen[name]} fights",
                    {"cost": total, "fights": seen[name], "missed": missed[name]}))     # the one card with a cost
    elif rows:
        out.append(("keep", "Cooldowns used on time", f"No damage lost to idle cooldowns in {len(dmg)} fights"))
    auto = [f["auto"] for f in dmg if f.get("auto")]
    minutes = sum(f["duration"] for f in dmg if f.get("auto")) / 60
    swings = sum(a["lost_other"] for a in auto)
    if minutes and swings / minutes >= 1:
        out.append(("fix", "Swings going missing", f"{swings / minutes:.1f} swings lost per minute ({swings} in {len(auto)} fights)"))
    return out + _skill_card(dmg)


def _change(prev: list[dict], cur: list[dict], key: str, label: str) -> str | None:
    """"gear 28 to 31", or None when unknown in either half or unchanged"""
    a, b = _mean(f.get(key) for f in prev), _mean(f.get(key) for f in cur)
    return f"{label} {a:.0f} to {b:.0f}" if a is not None and b is not None and round(a) != round(b) else None


def _skill_card(dmg: list[dict]) -> list[tuple]:
    """DPS is potential per second times efficiency: the change in efficiency is your play, the rest moved with
    gear, level and what you fought"""
    cur, prev = dmg[-20:], dmg[-40:-20]
    if len(prev) < TREND_MIN:
        return []
    d0, d1 = _mean(f.get("dps") for f in prev), _mean(f.get("dps") for f in cur)
    e0, e1 = _mean(f.get("efficiency") for f in prev), _mean(f.get("efficiency") for f in cur)
    if not d0 or not e0 or d1 is None or e1 is None:
        return []
    dps = d1 / d0 - 1
    if abs(dps) < SKILL_MOVE:
        return []
    play = e1 / e0 - 1
    rest = (1 + dps) / (1 + play) - 1
    known = [c for c in (_change(prev, cur, "gear", "gear"), _change(prev, cur, "level", "level")) if c]
    detail = (f"About {abs(play):.0%} from playing {'better' if play >= 0 else 'worse'} (efficiency {e0:.0%} to "
              f"{e1:.0%}), the rest ({rest:+.0%}) from gear, level and what you fought"
              + (f" ({', '.join(known)})" if known else "") + ".")
    kind = "keep" if play >= 0 else ("fix" if play <= -0.03 else "build")
    return [(kind, f"DPS {'up' if dps > 0 else 'down'} {abs(dps):.0%}", detail,
             {"dps_change": dps, "play": play, "rest": rest})]


def _habit_cards(win: list[dict]) -> list[tuple]:
    out, n = [], len(win)
    fails = Counter()
    for f in win:
        for x in f.get("failed") or []:
            if x["reason"] not in MASHING and not x["reason"].startswith("Can't do that while"):
                fails[x["reason"]] += x["count"]
    if fails and fails.most_common(1)[0][1] >= 5:
        reason, c = fails.most_common(1)[0]
        out.append(("fix", f"Failed casts: {reason}", f"{c} times in {n} fights ({c / n:.1f} per fight)"))
    seen = Counter()
    # old saves only list everyone's buffs on you, so judge by "own" whenever any fight has it
    new = [f for f in win if "own" in (f.get("pull") or {})]
    judged = new or win
    k = len(judged)
    for f in judged:
        pull = f.get("pull") or {}
        seen.update(pull["own"] if new else pull.get("buffs") or [])
    common = [(c, b) for b, c in seen.items() if c / k >= 0.6]
    missed = [(k - c, b) for c, b in common if c < k]
    if missed:
        m, b = max(missed)
        out.append(("fix", f"Pulling without {b}", f"Pulled without {b} in {m} of {k} fights"))
    elif common and k >= 5:
        out.append(("keep", f"Always pulling with {max(common)[1]}", f"Present at pull in all {k} fights"))
    deaths = sum(f.get("result") == "you died" for f in win)
    if deaths:
        out.append(("fix", "Dying in fights", f"Died in {deaths} of {n} fights"))
    elif n >= 5:
        out.append(("keep", "No deaths", f"Survived all {n} fights"))
    mana = [f["resource"]["start"] for f in win if (f.get("resource") or {}).get("type") == 0
            and f["resource"].get("start") is not None]
    if len(mana) >= 3 and _mean(mana) < 0.70:
        out.append(("build", "Start fights with more mana", f"Average {_mean(mana):.0%} mana at pull"))
    close = [f["danger"]["unused"] for f in win if (f.get("danger") or {}).get("unused")]
    if close:
        top = Counter(n for names in close for n in names).most_common(1)[0][0]
        out.append(("build", "Use a defensive when low",
                    f"{len(close)} close call{'s' if len(close) != 1 else ''} with {top} ready"))
    return out


def _wear_cards(win: list[dict], pulls: list[tuple]) -> list[tuple]:
    """gear durability at each pull (the add-on's record), matched to fights by start time"""
    seen = []
    for f in win:
        start = _t(f["start"])
        near = min(pulls, key=lambda p: abs((p[0] - start).total_seconds()), default=None)
        if near and abs((near[0] - start).total_seconds()) <= PULL_MATCH:
            seen.append(near)
    broken = [p for p in seen if p[2] > 0]
    worn = [p for p in seen if p[1] < WORN]
    if broken:
        return [("fix", "Pulling with broken gear", f"Broken gear in {len(broken)} of your last {len(seen)} fights")]
    if worn:
        return [("build", "Gear nearly broken", f"Lowest durability under {WORN}% in {len(worn)} of your last "
                 f"{len(seen)} fights (worst {min(p[1] for p in worn)}%)")]
    return []


def _build_cards(win: list[dict], char: dict, book: dict) -> list[tuple]:
    """what the character snapshot shows: harmful spells never cast in the window, empty gear slots"""
    out = []
    first = _t(win[0]["start"])
    spells = char.get("spells") or {}
    if any(sp["harm"] is not None for sp in spells.values()):         # without the flag nothing can be judged
        idle = [n for n, sp in spells.items() if sp["harm"] and not (
            (last := (book.get(n) or {}).get("last")) and _t(last) >= first)]
        if idle:
            out.append(("build", "Spells you never use", f"You know {', '.join(idle[:UNUSED_SHOWN])} and have not "
                        f"cast {'it' if len(idle) == 1 else 'them'} in your last {len(win)} fights"))
    gear = char.get("gear") or {}
    if gear:                                    # an empty list means the client gave nothing, not a naked character
        empty = [label for slot, label in SLOTS if slot not in gear]
        if empty:
            out.append(("build", "Gear slots to fill", "Empty gear slots: " + ", ".join(empty)))
    return out


def habits(fights: list[dict], char: dict | None = None, book: dict | None = None) -> dict:
    if not fights:
        return {"name": "", "level": None, "fights": 0, "session": None, "cards": [], "char": None, "trend": []}
    me = fights[-1]["me"]
    mine = [f for f in fights if f["me"] == me]
    win = mine[-WINDOW:]
    cards = _damage_cards(win) + _habit_cards(win) + (_build_cards(win, char, book or {}) + _wear_cards(
        win, char.get("pulls") or []) if char else [])
    cards.sort(key=lambda c: ORDER[c[0]])
    trend = [{"efficiency": f.get("efficiency"), "level": f.get("level"), "gear": f.get("gear")}
             for f in _damage_fights(win)]
    return {"name": fights[-1].get("me_name", ""), "level": fights[-1].get("level"), "fights": len(win),
            "trend": trend,
            "session": _session(mine), "char": char and {
                "class": char.get("class"), "race": char.get("race"), "level": char.get("level"),
                "spec": char.get("spec"), "gear": gear_level(char)},
            # a card's figures beside its words: cost on every card (None without one), the rest on their own card
            "cards": [{"kind": k, "title": t, "detail": d, "cost": None, **(more[0] if more else {})}
                      for k, t, d, *more in cards]}
