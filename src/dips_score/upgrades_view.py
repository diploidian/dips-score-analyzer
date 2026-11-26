"""What the Upgrades drawer on the Profile page shows, as plain data (no Qt), from live.upgrades.upgrades: a sentence, when the
scan was, then the gear in your last auction house scan that beats what you wear, the biggest gain first. Each row says what it
adds (damage per second measured in your fights, and standard points, apart), its price, its gain per gold and where its price
is from, and carries its tooltip word for word. Two guardrails pick what is shown: at most so much gold (half of what you had
at the scan, at first) and nothing over so many times its usual price. Inks are token names: an item's by its rarity."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from .live.upgrades import TIMES, pick
from .sheet_view import QUALITY
from .trade_view import coin

NEED = ("Your upgrades fill in after you scan the auction house with /dscore upgrades or its Find upgrades button, then /reload, "
        "with the add-on from 0.8 or newer.")
SITE = {"wowauctions": "wowauctions.net", "undermine": "Undermine Exchange"}


@dataclass
class UpgradeRow:
    name: str
    ink: str                # its rarity's colour token
    slot: str               # "Ring"
    price: str              # "3g 20s"
    gain: str               # "+1.4 damage per second, measured", "" when none is measured, "not compared"
    points: str             # "+12 points, standard", or why it is not compared
    per_gold: str           # "4.1 points per gold"
    source: str             # "From your scan 2 h ago. Usually 3g by your scans."
    tip: str                # its tooltip, a line each, as the game writes it
    compared: bool = True


@dataclass
class UpgradesView:
    need: str = NEED                # shown instead of the rest
    say: str = ""                   # "Wolfsbane is your biggest upgrade, for 3g 20s."
    cap: str = ""                   # when the scan was, and what is measured
    rows: list[UpgradeRow] = field(default_factory=list)
    hidden: str = ""                # "3 more cost over 20g."
    gold: int = 0                   # the first guardrail as it stands, whole gold
    most: int = 0                   # what you had at the scan, whole gold: the guardrail's top
    times: int = TIMES              # the second guardrail
    data: dict | None = None        # live.upgrades' result, picked again when a guardrail moves


def _ago(seconds: float | None) -> str:
    if seconds is None:
        return ""
    m = max(1, round(seconds / 60))
    return f"{m} min ago" if m < 60 else f"{round(m / 60)} h ago" if m < 48 * 60 else f"{round(m / 1440)} days ago"


def _signed(v: float) -> str:
    return f"{'+' if v >= 0 else '−'}{abs(v):,.1f}".removesuffix(".0")


def _source(r: dict, now: datetime) -> str:
    said = f"From your scan {_ago(r['age'])}." if r["age"] is not None else "From your scan."
    if not r["usual"]:
        return said
    if r["usual_from"] == "your scans":
        return f"{said} Usually {coin(r['usual'])} by your scans."
    try:
        at = datetime.fromisoformat(r["usual_seen"])
        seen = f", {_ago((now - (at.astimezone().replace(tzinfo=None) if at.tzinfo else at)).total_seconds())}"
    except (TypeError, ValueError):
        seen = ""
    site = SITE.get(r["usual_from"], r["usual_from"] or "the web")
    return f"{said} {'Lowest' if r['usual_min'] else 'Usually'} {coin(r['usual'])} on {site}{seen}" + (", lowest price only." if r["usual_min"] else ".")


def _row(r: dict, now: datetime) -> UpgradeRow:
    g = r["gain"]
    tip = "\n".join(f"{left}  {right}" if right else left for _, left, right in r["tips"])
    ink = QUALITY.get(r["quality"], ("", "tx"))[1]
    if g is None:
        return UpgradeRow(r["name"] or "name not read yet", ink, r["slot"], coin(r["price"]), "not compared", r["why"], "",
                          _source(r, now), tip, False)
    dps = f"{_signed(g['dps'])} damage per second, measured" if g["dps"] is not None and round(g["dps"], 1) else ""
    points = f"{_signed(g['points'])} points, standard" if round(g["points"], 1) else ""
    per = f"{r['per_gold']:,.1f} points per gold" if r["per_gold"] is not None else ""
    return UpgradeRow(r["name"] or "name not read yet", ink, r["slot"], coin(r["price"]), dps, points, per, _source(r, now), tip)


def build_upgrades(u: dict | None, gold: int | None = None, times: int = TIMES, now: datetime | None = None) -> UpgradesView:
    if not u:
        return UpgradesView()
    now, money = now or datetime.now(), u.get("money") or 0
    most = max(1, math.ceil(money / 10000))
    gold = max(1, round(money / 2 / 10000)) if gold is None else gold        # half of what you had, at first
    shown = pick(u["rows"], gold * 10000, times)
    over_cap = sum(r["price"] > gold * 10000 for r in u["rows"])
    over_usual = len(u["rows"]) - over_cap - len(shown)
    v = UpgradesView("", gold=gold, most=most, times=times, data=u, rows=[_row(r, now) for r in shown])
    best = next((r for r in shown if r["gain"]), None)
    value = min((r for r in shown if r["gold_rank"]), key=lambda r: r["gold_rank"], default=None)
    value = None if value is best else value
    v.say = (f"{best['name']} is your biggest upgrade, for {coin(best['price'])}." + (
        f" {value['name']} gives the most for your gold." if value else "")) if best else \
        f"Nothing in your scan beats what you wear for {gold:,}g or less." if u["rows"] else "Nothing in your scan beats what you wear."
    v.cap = " ".join(x for x in (
        f"From your scan at the auction house {_ago(u['age'])}, with {coin(money)} on you." if u["age"] is not None else "",
        "Points are standard estimates; only damage per second is measured in your fights.",
        f"{u['unread']:,} more listings were not looked at closely and are left out." if u["unread"] else "") if x)
    v.hidden = "; ".join(x for x in (
        f"{over_cap:,} more {'costs' if over_cap == 1 else 'cost'} over {gold:,}g" if over_cap else "",
        f"{over_usual:,} {'costs' if over_usual == 1 else 'cost'} over {times:g} times {'its' if over_usual == 1 else 'their'} usual price"
        if over_usual else "") if x)
    v.hidden = v.hidden[:1].upper() + v.hidden[1:] + "." if v.hidden else ""
    return v
