"""What the Habits page shows, as plain data (no Qt), from live.habits.habits(): your efficiency over the last 20
fights against the ones before them, the habit to fix (the fix card that cost the most damage), this sitting's key
figures, the trend, and every habit card grouped Fix · Build · Keep."""
import re
from dataclasses import dataclass, field

from .live.habits import TREND_MIN

MINUS = "−"
RECENT = 20                 # the fights in "last 20"; the ones before them are compared with them
GROUPS = (("fix", "Fix"), ("build", "Build"), ("keep", "Keep"))
NO_FIGHTS = "Fights appear here once you have some."
PLAY = re.compile(r"About (\d+)% from playing worse .*the rest \(([+-]\d+)%\)")    # the DPS card's split


@dataclass
class HabitsView:
    title: str = "Habits"           # the character's name
    meta: str = ""                  # "level 30 Undead Paladin · gear 27 · last 40 fights"
    recent: float | None = None     # mean efficiency (%) over the last 20 fights that did damage
    before: float | None = None     # over up to 20 before them; None under TREND_MIN, as the efficiency card
    caption: str = "efficiency"
    chip: str | None = None         # "−10 pts vs the 18 before"
    verdict: str = ""
    fix: tuple[str, str | None, str] | None = None      # the plate: (title, price, caption)
    figures: list[tuple[str, str]] = field(default_factory=list)
    trend: list[float] = field(default_factory=list)    # efficiency (%) per fight, oldest first
    split_at: int | None = None     # where the last-20 window starts in trend; None without a before
    levels: list[tuple[int, int]] = field(default_factory=list)     # (the first fight at a new level, that level)
    gear_changes: list[int] = field(default_factory=list)           # the first fight at a new gear level
    groups: list[tuple[str, list[tuple[str, str, bool]]]] = field(default_factory=list)  # (title, detail, is plate)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _meta(h: dict) -> str:
    c = h.get("char")
    if c:
        kind = " ".join(x.title() for x in (c.get("race"), c.get("class")) if x)
        who = [" ".join(x for x in (f"level {c['level']}" if c.get("level") else "", kind) if x),
               c.get("spec"), f"gear {c['gear']}" if c.get("gear") else ""]
    else:
        who = [f"level {h['level']}" if h.get("level") else ""]
    return " · ".join([x for x in who if x] + [f"last {_plural(h['fights'], 'fight')}"])


def _figures(s: dict | None) -> list[tuple[str, str]]:
    """this sitting's numbers (live.habits._session)"""
    if not s:
        return []

    def num(v, unit=""):
        return "–" if v is None else f"{v:.0f}{unit}"
    hp, mana = num(s["avg_start_hp"] and s["avg_start_hp"] * 100, "%"), s["avg_start_mana"]
    return [(str(s["fights"]), f"{'fight' if s['fights'] == 1 else 'fights'} · {_plural(s['kills'], 'kill')}"),
            (num(s["kills_per_hour"]), "kills / hour"), (num(s["avg_gap"], "s"), "avg gap"),
            (num(s["avg_rest"], "s"), "avg rest"),
            (hp, "start health") if mana is None else (f"{hp} / {num(mana * 100, '%')}", "start health / mana")]


def _play_not_gear(cards: list[dict]) -> bool:
    """the DPS card says DPS fell mostly from your play: playing worse by more than gear, level and foes moved it"""
    for c in cards:
        if c["title"].startswith("DPS down") and (m := PLAY.match(c["detail"])):
            return int(m[2]) >= 0 or int(m[1]) > -int(m[2])
    return False


def build_habits(h: dict) -> HabitsView:
    """the page for live.habits.habits(...)'s result"""
    v = HabitsView(title=h.get("name") or "Habits", meta=_meta(h) if h.get("fights") else "",
                   figures=_figures(h.get("session")))
    cards = h.get("cards") or []
    pts = [p for p in h.get("trend") or [] if p["efficiency"] is not None]     # older saves may lack it
    if not h.get("fights"):
        v.verdict = NO_FIGHTS
        return v
    plate = None
    if len(pts) < TREND_MIN:
        v.verdict = f"Efficiency shows here after {TREND_MIN} fights where you did damage ({len(pts)} so far)."
    else:
        v.trend = [p["efficiency"] * 100 for p in pts]
        cur, prev = v.trend[-RECENT:], v.trend[-2 * RECENT:-RECENT]
        v.recent, v.caption = sum(cur) / len(cur), f"efficiency, last {len(cur)} fights"
        if len(prev) >= TREND_MIN:
            v.before, v.split_at = sum(prev) / len(prev), len(v.trend) - len(cur)
            d = round(v.recent - v.before)
            v.chip = f"{MINUS if d < 0 else '+' if d > 0 else ''}{abs(d)} pts vs the {len(prev)} before"
        for key, out in (("level", v.levels), ("gear", v.gear_changes)):
            for i in range(1, len(pts)):
                a, b = pts[i - 1][key], pts[i][key]
                if a is not None and b is not None and a != b:
                    out.append((i, b) if key == "level" else i)
        # the plate: the fix that cost the most damage, else the first fix (not the efficiency card: that is the hero)
        fixes = [c for c in cards if c["kind"] == "fix" and not c["title"].startswith("Efficiency ")]
        plate = max((c for c in fixes if c.get("cost") is not None), key=lambda c: c["cost"], default=None) or \
            (fixes[0] if fixes else None)
        eff = next((c["title"] for c in cards if c["title"].startswith("Efficiency ")), "Efficiency")
        drop = eff == "Efficiency is dropping" and _play_not_gear(cards)     # what the DPS card's split says
        head = eff + (", and most of it is play, not gear" if drop else "")
        if plate is None:
            v.verdict = head + "."
        elif plate.get("cost") is not None:
            price = f"about {plate['cost']:,.0f} damage"
            caption = plate["detail"].removeprefix(f"About {plate['cost']:,.0f} damage lost").lstrip(", ")
            v.fix = (plate["title"], price, caption)
            where = re.search(r"in (\d+ fights?)$", caption)
            v.verdict = f"{head}: {plate['title']} cost {price}{f' across {where[1]}' if where else ''}."
        else:
            v.fix = (plate["title"], None, plate["detail"])
            d = plate["detail"].rstrip(".")
            v.verdict = f"{head}. {plate['title']}: {d[:1].lower()}{d[1:]}."
    for kind, name in GROUPS:
        rows = [(c["title"], c["detail"], c is plate) for c in cards if c["kind"] == kind]
        if rows:
            v.groups.append((name, rows))
    return v
