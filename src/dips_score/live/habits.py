"""Habits across many fights: what you keep doing right, what keeps costing you, and the pace of this session.

Takes the saved fight summaries (oldest first) and looks at the newest fight's character only. Older saves
lack some keys, so everything is read with .get().
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from .summary import MASHING

WINDOW = 40                  # fights looked at; the trend compares the last 20 with the 20 before
TREND_MIN = 5                # fights needed in each half of the trend
SESSION_GAP = 30 * 60        # seconds between fights that still count as one sitting
ORDER = {"fix": 0, "build": 1, "keep": 2}


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


def _damage_cards(win: list[dict]) -> list[tuple]:
    out = []
    dmg = [f for f in win if not f.get("healing_role")]
    eff = [f.get("efficiency", 1.0) for f in dmg]
    if len(eff) >= TREND_MIN:
        cur, prev = eff[-20:], eff[-40:-20]
        a = _mean(cur) * 100
        msg = f"Last {len(cur)} fights {a:.1f}% efficiency"
        if len(prev) >= TREND_MIN:
            p = _mean(prev) * 100
            msg += f" vs {p:.1f}% in the {len(prev)} before"
            if a - p <= -3:
                out.append(("fix", "Efficiency is dropping", msg))
            elif a - p >= 3:
                out.append(("keep", "Efficiency is improving", msg))
        if not out:
            out.append(("keep", "Efficiency is steady", msg) if a >= 75 else ("fix", "Efficiency is stuck low", msg))
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
        out.append(("fix", f"{name} left unused", f"About {total:,.0f} damage lost{casts} in {seen[name]} fights"))
    elif rows:
        out.append(("keep", "Cooldowns used on time", f"No damage lost to idle cooldowns in {len(dmg)} fights"))
    auto = [f["auto"] for f in dmg if f.get("auto")]
    minutes = sum(f["duration"] for f in dmg if f.get("auto")) / 60
    swings = sum(a["lost_other"] for a in auto)
    if minutes and swings / minutes >= 1:
        out.append(("fix", "Swings going missing", f"{swings / minutes:.1f} swings lost per minute ({swings} in {len(auto)} fights)"))
    return out


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
    return out


def habits(fights: list[dict]) -> dict:
    if not fights:
        return {"name": "", "level": None, "fights": 0, "session": None, "cards": []}
    me = fights[-1]["me"]
    mine = [f for f in fights if f["me"] == me]
    win = mine[-WINDOW:]
    cards = sorted(_damage_cards(win) + _habit_cards(win), key=lambda c: ORDER[c[0]])
    return {"name": fights[-1].get("me_name", ""), "level": fights[-1].get("level"), "fights": len(win),
            "session": _session(mine), "cards": [{"kind": k, "title": t, "detail": d} for k, t, d in cards]}
