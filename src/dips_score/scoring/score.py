"""The score: measurements judged into categories, a 0-100 total and a grade, and the things
most worth working on. Each role has its own categories and weights (defaults below; you can
change them in the window, saved in weights.json):

    healer   Group health 35, Response 35, Efficiency 20, Casting 10, Movement 0, Input 0
             + a hybrid bonus of up to 10 for the damage you also did
    dps      Activity 30, Casting 20, Movement 15, Survival 20, Input 15

A category weighted 0 is info only: still shown with its numbers, but it doesn't count toward the
total and gives no tips. For a healer, mashing and casts cut by moving are info only by default,
and Casting only counts refusals that mean something went wrong (out of range, wrong target, no
mana), not ones from pressing early.

Hybrid bonus (healer): your damage, as a share of an even split of the group's damage (damage
done while everyone was above 80% health counts fully, the rest half), times how well you healed
(Group health x Response). So damage only adds to your score when the healing held up.

The thresholds are a first guess. They live in one table (TUNING) so they're easy to adjust as
real runs come in.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .healer import DIP_HP, RESPONSE_CAP, SAFE_HP, HealerMetrics
from .metrics import Metrics

ROLES = ("healer", "dps")

TUNING = {
    # activity (dps): share of combat time casting, channeling, on the GCD or wanding
    "uptime_zero": 0.55, "uptime_full": 0.90,
    # casting: share of presses the game refused
    "fail_full": 0.10, "fail_zero": 0.55,
    # movement: casts cut by moving, per minute of combat
    "moveint_zero": 3.0,
    # survival (dps): your own deaths and time under 35%
    "death_cost": 45, "lowhp_share_zero": 0.25,
    # input: presses per successful cast, and share of presses made with the mouse
    "ppc_full": 1.3, "ppc_zero": 2.6,
    "click_full": 0.10, "click_zero": 0.60,
    # group health (healer): each death in the group, and share of combat with someone under 35%
    "group_death_cost": 35, "danger_share_zero": 0.10,
    # response (healer): median seconds from a dip to starting a heal on them, and share missed
    "resp_full": 1.0, "resp_zero": RESPONSE_CAP,
    "missed_zero": 0.5,
    # efficiency (healer): overhealing on your cast heals and HoTs; running out of mana
    "overheal_full": 0.15, "overheal_zero": 0.50,
    "oom_cost": 25, "low_mana": 0.05, "low_mana_cost": 30,
}

BONUS = "Hybrid bonus"   # not a category: its "weight" is the most points it can add
DEFAULT_WEIGHTS = {
    "healer": {"Group health": 35, "Response": 35, "Efficiency": 20, "Casting": 10, "Movement": 0, "Input": 0,
               BONUS: 10},
    "dps": {"Activity": 30, "Casting": 20, "Movement": 15, "Survival": 20, "Input": 15},
}
WEIGHTS = {role: dict(w) for role, w in DEFAULT_WEIGHTS.items()}   # in use (load_weights fills it)

# refusals from pressing early or while busy: mashing, not a mistake that cost anything (healer)
MASHING = {"Not yet recovered", "Another action is in progress", "Interrupted", "Can't do that while moving",
           "Spell not ready yet", "Item is not ready yet"}


def load_weights(path: Path | None):
    """Your weights from weights.json, over the defaults."""
    for role, w in DEFAULT_WEIGHTS.items():
        WEIGHTS[role] = dict(w)
    if path and path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return
        for role, w in saved.items():
            if role in WEIGHTS and isinstance(w, dict):
                for k, v in w.items():
                    if k in WEIGHTS[role] and isinstance(v, (int, float)) and 0 <= v <= 100:
                        WEIGHTS[role][k] = v


def save_weights(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(WEIGHTS, indent=1), encoding="utf-8")


def reset_weights():
    for role, w in DEFAULT_WEIGHTS.items():
        WEIGHTS[role] = dict(w)


def ramp(v: float, zero: float, full: float) -> float:
    """0..100: `zero` scores 0, `full` scores 100, straight line between (either direction)."""
    if zero == full:
        return 100.0
    x = (v - zero) / (full - zero)
    return max(0.0, min(100.0, x * 100))


@dataclass
class Category:
    name: str
    score: float
    weight: int
    summary: str             # the numbers behind it
    tip: str | None = None   # what to do about it, if there's something
    unavailable: str = ""    # why it can't be judged from this log (then it doesn't count)

    @property
    def info_only(self) -> bool:
        return self.weight <= 0 or bool(self.unavailable)


@dataclass
class Scorecard:
    total: float
    grade: str
    role: str = "dps"
    categories: list[Category] = field(default_factory=list)
    note: str = ""           # why nothing was scored, when nothing was
    bonus: float = 0.0       # hybrid bonus points added on top
    bonus_note: str = ""

    @property
    def empty(self) -> bool:
        """no combat: nothing was scored"""
        return not self.categories

    @property
    def tips(self) -> list[str]:
        worst = sorted((c for c in self.categories if c.tip and not c.info_only), key=lambda c: c.score)
        return [c.tip for c in worst[:3] if c.score < 85]


def grade(total: float) -> str:
    for g, lo in (("S", 90), ("A", 80), ("B", 70), ("C", 60), ("D", 45)):
        if total >= lo:
            return g
    return "F"


# ----------------------------------------------------------------------------- shared categories
def _casting(m: Metrics, w: float, ignore: set[str] = frozenset()) -> Category:
    """refused presses; `ignore`: reasons that don't count (they're still listed)"""
    counted = sum(n for r, n in m.fail_reasons.items() if r not in ignore)
    rate = counted / (m.casts + counted) if m.casts + counted else 0.0
    s = ramp(rate, TUNING["fail_zero"], TUNING["fail_full"])
    top = ", ".join(f"{r} x{n}" for r, n in m.fail_reasons.most_common(3))
    if ignore:
        summary = (f"{m.casts} casts, {m.failed} refused" + (f" ({top})" if top else "")
                   + f"; {counted} count ({rate:.0%}) - pressing early doesn't")
    else:
        summary = f"{m.casts} casts, {m.failed} refused ({rate:.0%})" + (f": {top}" if top else "")
    return Category("Casting", s, w, summary, _fail_tip(m, ignore) if s < 85 else None)


def _movement(m: Metrics, w: int) -> Category:
    per_min = m.move_interrupts * m.per_min
    s = ramp(per_min, TUNING["moveint_zero"], 0.0)
    return Category(
        "Movement", s, w,
        f"{m.move_interrupts} casts cut by moving ({per_min:.1f}/min), {m.wasted_cast_time:.1f}s of cast time lost; "
        f"moving {m.moving_share:.0%} of combat",
        f"{m.move_interrupts} casts were cut short by moving ({m.wasted_cast_time:.1f}s thrown away). "
        f"Finish the cast or move first, and use instants while you move." if s < 85 and m.move_interrupts else None)


def _input(m: Metrics, w: int) -> Category:
    s_ppc = ramp(m.presses_per_cast, TUNING["ppc_zero"], TUNING["ppc_full"]) if m.casts else 100
    s_click = ramp(m.click_share, TUNING["click_zero"], TUNING["click_full"])
    s = 0.6 * s_ppc + 0.4 * s_click
    hold = f", median key hold {m.median_hold_ms:.0f}ms" if m.median_hold_ms else ""
    tip = None
    if s < 85:
        if s_ppc <= s_click:
            tip = (f"{m.presses_per_cast:.1f} presses per cast ({m.spam_bursts} bursts of mashing). "
                   f"One press near the end of the GCD is enough.")
        else:
            tip = f"{m.click_share:.0%} of your presses were mouse clicks. Bind those buttons to keys."
    return Category("Input", s, w, f"{m.presses} presses, {m.presses_per_cast:.2f} per cast, {m.spam_bursts} mash bursts; "
                                   f"{m.click_share:.0%} clicks{hold}", tip)


def _card(cats: list[Category], role: str, bonus: float = 0.0, bonus_note: str = "") -> Scorecard:
    weight = sum(c.weight for c in cats if not c.info_only)
    base = sum(c.score * c.weight for c in cats if not c.info_only) / weight if weight else 0.0
    if not weight and any(c.unavailable for c in cats):
        return Scorecard(0.0, "-", role, cats, note="nothing counted could be judged: turn on Advanced Combat Logging")
    total = min(100.0, base + bonus)
    return Scorecard(total, grade(total), role, cats, bonus=bonus, bonus_note=bonus_note)


# ----------------------------------------------------------------------------- healer
def healer_categories(hm: HealerMetrics, you: bool = True) -> list[Category]:
    """Group health, Response and Efficiency: what any healer can be judged on from the combat log.
    you=False words the tips about someone else."""
    T, W = TUNING, WEIGHTS["healer"]
    them = "you" if you else "they"
    cats: list[Category] = []

    n_dead = len(hm.deaths)
    s = max(0.0, 100 - T["group_death_cost"] * n_dead - (100 - ramp(hm.danger_share, T["danger_share_zero"], 0)) * 0.4)
    who = ", ".join(n for _, n in hm.deaths)
    tip = None
    if s < 85:
        tip = (f"{who} died. Check the timeline for the seconds before it: were {them} casting on someone else, "
               f"or moving?" if n_dead else
               f"Someone was under 35% health for {hm.danger_time:.0f}s. Shield or Renew the tank before big pulls.")
    cats.append(Category("Group health", s, W["Group health"],
                         f"{n_dead} deaths" + (f" ({who})" if who else "") +
                         f"; someone under 35% for {hm.danger_time:.0f}s ({hm.danger_share:.0%} of combat)", tip))

    j = hm.judged
    if j:
        med = hm.median_response
        s = 0.6 * ramp(med, T["resp_zero"], T["resp_full"]) + 0.4 * ramp(hm.missed_share, T["missed_zero"], 0)
        summary = (f"{len(j)} dips under {DIP_HP:.0%}: median {med:.1f}s to start a heal, "
                   f"{hm.missed} with no heal from {'you' if you else 'them'} in {RESPONSE_CAP:.0f}s")
        slow = sorted((d for d in j if d.response is None or d.response > 3), key=lambda d: d.start)
        tip = None
        if s < 85:
            names = {}
            for d in slow:
                names[d.name] = names.get(d.name, 0) + 1
            worst = max(names, key=names.get) if names else None
            tip = (f"Heals were slow to start: median {med:.1f}s after someone dropped under {DIP_HP:.0%}"
                   + (f", mostly on {worst} ({names[worst]} times)" if worst else "")
                   + ". Watch the party frames, not just the tank.")
    else:
        s, summary, tip = 100.0, "nobody dropped under 60% in the fights covered", None
    cats.append(Category("Response", s, W["Response"], summary, tip))

    s_over = ramp(hm.overheal_share, T["overheal_zero"], T["overheal_full"])
    mana_pen = T["oom_cost"] * hm.oom_refusals + (T["low_mana_cost"] if (hm.lowest_mana or 1) < T["low_mana"] else 0)
    s_mana = max(0.0, 100 - mana_pen)
    s = 0.7 * s_over + 0.3 * s_mana
    mana_txt = f"lowest mana {hm.lowest_mana:.0%}" if hm.lowest_mana is not None else "mana unknown"
    tip = None
    if s < 85:
        tip = (f"{hm.overheal_share:.0%} of the cast healing was overhealing. Use a smaller heal or a lower rank "
               f"when they're only a little hurt." if s_over < s_mana else
               f"Ran low on mana ({mana_txt}, {hm.oom_refusals} casts refused for mana). Wand between pulls "
               f"and use lower ranks on small damage.")
    cats.append(Category("Efficiency", s, W["Efficiency"],
                         f"{hm.cast_heal:,} cast healing, {hm.overheal_share:.0%} overheal; {hm.passive_heal:,} passive; "
                         f"{mana_txt}, {hm.oom_refusals} refused for mana", tip))
    if not hm.has_advanced:   # no health readings: dips and danger can't be seen, don't score them 100
        need = "needs Advanced Combat Logging"
        cats[0] = Category("Group health", 0.0, W["Group health"], need, unavailable=need)
        cats[1] = Category("Response", 0.0, W["Response"], need, unavailable=need)
    return cats


def hybrid_bonus(hm: HealerMetrics, cats: list[Category]) -> tuple[float, str]:
    """damage, as a share of an even split, scaled by how well the healing went (cats from healer_categories)"""
    W = WEIGHTS["healer"]
    if W.get(BONUS, 0) <= 0 or hm.even_share <= 0 or hm.my_damage <= 0 or cats[0].unavailable or cats[1].unavailable:
        return 0.0, ""
    quality = (cats[0].score / 100) * (cats[1].score / 100)
    credit = hm.free_damage + 0.5 * (hm.my_damage - hm.free_damage)
    share = min(1.0, credit / hm.even_share)
    note = (f"{hm.my_damage:,} damage ({hm.free_damage / hm.my_damage:.0%} while everyone was above "
            f"{SAFE_HP:.0%}) = {share:.0%} of an even share, at {quality:.0%} healing quality")
    return W[BONUS] * share * quality, note


def score_healer(m: Metrics, hm: HealerMetrics) -> Scorecard:
    if m.combat_time <= 0:
        return Scorecard(0.0, "-", "healer", note="no combat in this run, nothing to score")
    if not m.has_log:
        return Scorecard(0.0, "-", "healer", note="no combat log covers this run, so healing can't be judged")
    W = WEIGHTS["healer"]
    cats = healer_categories(hm)
    cats.append(_casting(m, W["Casting"], MASHING))
    cats.append(_movement(m, W["Movement"]))
    cats.append(_input(m, W["Input"]))
    bonus, note = hybrid_bonus(hm, cats)
    return _card(cats, "healer", bonus, note)


# ----------------------------------------------------------------------------- dps
def score_dps(m: Metrics) -> Scorecard:
    if m.combat_time <= 0:
        return Scorecard(0.0, "-", "dps", note="no combat in this run, nothing to score")
    T, W = TUNING, WEIGHTS["dps"]
    cats: list[Category] = []

    s = ramp(m.uptime, T["uptime_zero"], T["uptime_full"])
    longest = max((b - a for a, b in m.idle_gaps), default=0)
    cats.append(Category(
        "Activity", s, W["Activity"],
        f"busy {m.uptime:.0%} of {m.combat_time:.0f}s in combat; {len(m.idle_gaps)} gaps of 2.5s+"
        + (f", longest {longest:.1f}s" if m.idle_gaps else ""),
        f"Always be casting: you were doing nothing {1 - m.uptime:.0%} of combat. "
        f"Fill gaps with an instant, a DoT refresh or your wand." if s < 85 else None))

    cats.append(_casting(m, W["Casting"]))
    cats.append(_movement(m, W["Movement"]))

    lowhp_share = m.low_hp_time / m.combat_time if m.combat_time else 0
    s = max(0.0, 100 - T["death_cost"] * m.deaths - (100 - ramp(lowhp_share, T["lowhp_share_zero"], 0)) * 0.4)
    hp_txt = f"lowest health {m.lowest_hp:.0%}, {m.low_hp_time:.0f}s under 35%" if m.lowest_hp is not None \
        else "no health data (needs Advanced Combat Logging)"
    cats.append(Category(
        "Survival", s, W["Survival"], f"{m.deaths} deaths; {hp_txt}",
        ("You died - look at what hit you in the seconds before it." if m.deaths else
         "You spent a lot of time low on health. Step out of hits and use your shield earlier.")
        if s < 85 else None))

    cats.append(_input(m, W["Input"]))
    return _card(cats, "dps")


def score(m: Metrics, role: str = "healer", hm: HealerMetrics | None = None) -> Scorecard:
    if role == "healer" and hm is not None:
        return score_healer(m, hm)
    return score_dps(m)


def _fail_tip(m: Metrics, ignore: set[str] = frozenset()) -> str:
    counted = [(r, n) for r, n in m.fail_reasons.most_common() if r not in ignore]
    reason, n = (counted or [("unknown", m.failed)])[0]
    advice = {
        "Not yet recovered": "you're pressing before the cooldown or GCD is back - that's mashing",
        "Invalid target": "check your target before pressing",
        "Out of range": "you're pressing while out of range",
        "Not enough mana": "you ran out of mana - wand more, cast cheaper ranks",
        "Can't do that while moving": "stop before you cast",
        "Another action is in progress": "you're pressing while already casting",
        "Interrupted": "you're starting casts that get stopped",
    }.get(reason, "look at what's refusing them")
    total = sum(n for _, n in counted) if ignore else m.failed
    return f"{total} presses were refused, most often \"{reason}\" (x{n}): {advice}."
