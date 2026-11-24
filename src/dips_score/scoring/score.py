"""The score: measurements judged into categories, a 0-100 total and a grade, and the things
most worth working on. Each role has its own categories and weights (defaults below; you can
change them in the window, saved in weights.json):

    healer   Group health 35, Response 35, Efficiency 20, Casting 10, Pacing 5, Movement 0, Input 0
             + a hybrid bonus of up to 10 for the damage you also did
    dps      Damage 20, Activity 15, Cooldowns 10, Interrupts 10, Casting 10, Movement 10, Survival 10,
             Upkeep 5, Input 5, Resource 5, Pacing 5
    tank     Holding mobs 25, Pickups 25, Survival 20, Activity 10, Upkeep 10, Casting 5, Input 5,
             Pacing 5, Movement 0, Interrupts 0, Cooldowns 0, Resource 0

A category weighted 0 is info only: still shown with its numbers, but it doesn't count toward the
total and gives no tips. For a healer, mashing and casts cut by moving are info only by default,
and Casting only counts refusals that mean something went wrong (out of range, wrong target, no
mana), not ones from pressing early. For rage and energy users, "Not enough rage/energy" refusals
don't count either (that's pooling), and for melee Movement is info only.

Resource (rage and energy users, needs Advanced Combat Logging): the share of combat your power sat
at its maximum, so more coming in was wasted. Cooldowns: damage cooldowns that sat ready while you
were free to use them, as a share of your damage (cooldowns.py).

Damage (dps): your damage (your pets' included) as a share of an even split of the group's, the same
measure the group card uses. Solo there's nothing to compare with, so it isn't judged. Interrupts:
how many of the enemy casts you could have stopped you did, and how fast (interrupts.py; dispels are
folded in when you dispelled anyone this run). Both need the combat log: without one the dps card is
the add-on categories only.

Upkeep (dps, tank): the buffs and DoTs your class keeps up (classes.py), as the share of combat they
were up, for the ones you applied this run (upkeep.py). Nothing applied, no row.

Positioning (every role, info only by default): melee players by how often you stood behind your target,
everyone else by how often you took hits far from the tank (positioning.py). Needs Advanced Combat Logging.

Pacing (every role, run card only): the share of pulls you went into safely (health 50%+, and mana 30%+ for
mana users) and on time (first press within 3 s of your combat beginning, or you pulled it) (pacing.py). Needs
Advanced Combat Logging.

Hybrid bonus (healer): your damage, as a share of an even split of the group's damage (damage
done while everyone was above 80% health counts fully, the rest half), times how well you healed
(Group health x Response). So damage only adds to your score when the healing held up.

The thresholds are a first guess. They live in one table (TUNING) so they're easy to adjust as
real runs come in.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .healer import DIP_HP, RESPONSE_CAP, SAFE_HP, HealerMetrics
from .cooldowns import CooldownMetrics
from .interrupts import InterruptMetrics
from .metrics import Metrics
from .pacing import PacingMetrics
from .positioning import FAR, PositionMetrics
from .tank import PICKUP_CAP, TankMetrics
from .upkeep import UpkeepMetrics

ROLES = ("healer", "dps", "tank")

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
    # holding mobs (tank): share of mobs whose first hit went to the tank
    "hold_zero": 0.4, "hold_full": 0.9,
    # pickups (tank): median seconds until a mob that left is back on the tank, and share never back
    "pickup_full": 1.5, "pickup_zero": PICKUP_CAP, "pickup_missed_zero": 0.5,
    # survival (tank, group card): each death
    "tank_death_cost": 40,
    # melee (dps, tank): at least this many swings, and more swings than hard casts; then Movement
    # is info only (melee has no cast to cut)
    "melee_swings": 10,
    # damage (dps, group card): your damage against an even split of the group's
    "damage_zero": 0.5, "damage_full": 1.3,
    # interrupts: share of chances let through, and median seconds to stop the ones you got (a cast
    # is short, so getting it matters more than speed); dispels the same, a little slower
    "kick_missed_zero": 0.6, "kick_resp_zero": 2.5, "kick_resp_full": 0.8,
    "dispel_resp_zero": 5.0, "dispel_resp_full": 1.5,
    # resource (rage, energy): share of combat spent at full power
    "capped_zero": 0.20, "capped_full": 0.02,
    # cooldowns: damage lost to unused cooldowns, as a share of your damage plus that
    "cd_lost_zero": 0.15, "cd_lost_full": 0.0,
    # upkeep: mean uptime of the buffs and DoTs you applied
    "upkeep_zero": 0.40, "upkeep_full": 0.90,
    # positioning: share of swings from behind (melee), share of hits taken far from the tank (others)
    "behind_zero": 0.2, "behind_full": 0.8, "far_zero": 0.5, "far_full": 0.05, "min_judged": 10,
    # pacing: a pull is safe with health and (mana users) mana at least this, on time with your first press
    # within pace_late_s of your combat beginning; then the share of pulls that were both
    "pace_hp": 0.5, "pace_mana": 0.3, "pace_late_s": 3.0, "pace_zero": 0.5, "pace_full": 0.95,
}
POWER_WORD = {1: "rage", 3: "energy"}   # Metrics.power_type

BONUS = "Hybrid bonus"   # not a category: its "weight" is the most points it can add
DEFAULT_WEIGHTS = {
    "healer": {"Group health": 35, "Response": 35, "Efficiency": 20, "Casting": 10, "Movement": 0, "Input": 0,
               "Positioning": 0, "Pacing": 5, BONUS: 10},
    "dps": {"Damage": 20, "Activity": 15, "Cooldowns": 10, "Interrupts": 10, "Casting": 10, "Movement": 10,
            "Survival": 10, "Upkeep": 5, "Input": 5, "Resource": 5, "Positioning": 0, "Pacing": 5},
    "tank": {"Holding mobs": 25, "Pickups": 25, "Survival": 20, "Activity": 10, "Upkeep": 10, "Casting": 5,
             "Input": 5, "Movement": 0, "Interrupts": 0, "Cooldowns": 0, "Resource": 0,
             "Positioning": 0, "Pacing": 5},
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

    def points_lost(self) -> list[tuple[Category, float]]:
        """counted categories' share of the points missing from 100, largest first (bonus not netted)"""
        counted = [c for c in self.categories if not c.info_only]
        weight = sum(c.weight for c in counted)
        lost = [(c, c.weight * (100 - c.score) / weight) for c in counted] if weight else []
        return sorted(((c, p) for c, p in lost if round(p, 1) != 0), key=lambda cp: -cp[1])

    @property
    def tips(self) -> list[str]:
        worst = [c for c, _ in self.points_lost() if c.tip and c.score < 85]
        return [c.tip for c in worst[:3]]


def grade(total: float) -> str:
    for g, lo in (("S", 90), ("A", 80), ("B", 70), ("C", 60), ("D", 45)):
        if total >= lo:
            return g
    return "F"


# ----------------------------------------------------------------------------- shared categories
def _casting(m: Metrics, w: float, ignore: set[str] = frozenset(), why: str = "pressing early doesn't") -> Category:
    """refused presses; `ignore`: reasons that don't count (they're still listed), `why` says which"""
    counted = sum(n for r, n in m.fail_reasons.items() if r not in ignore)
    rate = counted / (m.casts + counted) if m.casts + counted else 0.0
    s = ramp(rate, TUNING["fail_zero"], TUNING["fail_full"])
    top = ", ".join(f"{r} x{n}" for r, n in m.fail_reasons.most_common(3))
    if ignore:
        summary = (f"{m.casts} casts, {m.failed} refused" + (f" ({top})" if top else "")
                   + f"; {counted} count ({rate:.0%}) - {why}")
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


def _melee(m: Metrics) -> bool:
    """you fight in melee: a fair number of swings, and more swings than hard casts"""
    return m.swings >= TUNING["melee_swings"] and m.swings > m.hard_casts


def _shooter(m: Metrics) -> bool:
    """you fight with ranged auto shots (a hunter, or a wand user): a fair number of shots, more than hard casts,
    and not a melee fighter"""
    return m.shots >= TUNING["melee_swings"] and m.shots > m.hard_casts and not _melee(m)


def _pooling_casting(m: Metrics, w: float) -> Category:
    """Casting for dps and tanks: a rage or energy user pressing before the power is there is
    pooling, not a mistake"""
    word = POWER_WORD.get(m.power_type)
    if word:
        return _casting(m, w, {f"Not enough {word}"}, f"waiting for {word} doesn't")
    return _casting(m, w)


def _activity(m: Metrics, w: int) -> Category:
    T = TUNING
    s = ramp(m.uptime, T["uptime_zero"], T["uptime_full"])
    longest = max((b - a for a, b in m.idle_gaps), default=0)
    word = POWER_WORD.get(m.power_type)
    if _melee(m):
        tip = (f"Always be attacking: you were doing nothing {1 - m.uptime:.0%} of combat and lost "
               f"{m.swings_lost} swings while not casting. Stay in reach of your target and fill gaps "
               f"with an ability.")
    elif _shooter(m):
        tip = (f"Always be shooting: you were doing nothing {1 - m.uptime:.0%} of combat and lost "
               f"{m.shots_lost or 0} shots while not casting or moving. Stand still in range and keep your "
               f"auto shot going between abilities.")
    else:
        tip = (f"Always be casting: you were doing nothing {1 - m.uptime:.0%} of combat. "
               f"Fill gaps with an instant, a DoT refresh or your wand.")
    return Category(
        "Activity", s, w,
        f"busy {m.uptime:.0%} of {m.combat_time:.0f}s in combat; {len(m.idle_gaps)} gaps of 2.5s+"
        + (f", longest {longest:.1f}s" if m.idle_gaps else "")
        + (f"; {m.swings} swings, {m.swings_lost} lost while not casting" if m.swings else "")
        + (f"; {m.shots} shots, {m.shots_lost} lost, {m.shots_clipped} clipped by casts"
           if m.shots and m.shots_lost is not None else "")
        + (f"; {m.swinging_time:.0f}s of it auto-attack with no ability" if m.swinging_time and m.swinging_time >= 0.5
           else "")
        + (f"; waiting for {word} {m.starved_time:.0f}s" if word and m.starved_time >= 0.5 else ""),
        tip if s < 85 else None)


def _resource(m: Metrics, w: int) -> Category | None:
    """time at full rage or energy; None for anyone else (mana users, or no power readings)"""
    word = POWER_WORD.get(m.power_type)
    if not word or not m.has_advanced:
        return None
    share = m.capped_time / m.combat_time if m.combat_time else 0.0
    s = ramp(share, TUNING["capped_zero"], TUNING["capped_full"])
    return Category("Resource", s, w,
                    f"at full {word} {m.capped_time:.0f}s ({share:.0%} of combat); waiting for {word} "
                    f"{m.starved_time:.0f}s",
                    f"You sat at full {word} for {m.capped_time:.0f}s, so {word} was wasted. Spend it "
                    f"before you cap." if s < 85 else None)


def _cooldowns(cm: CooldownMetrics, w: int) -> Category:
    """damage cooldowns that sat ready with no excuse (live/readiness.py says what excuses)"""
    if not cm.rows:
        return Category("Cooldowns", 100.0, w, "no cooldowns to judge")
    s = ramp(cm.lost_share, TUNING["cd_lost_zero"], TUNING["cd_lost_full"])
    top = [r for r in cm.rows if r.lost > 0][:2]
    summary = ("; ".join(f"{r.name} ready {r.free:.0f}s, ~{r.lost:,.0f} damage" for r in top)
               or "every cooldown was used as it came up")
    worst = top[0] if top else None
    return Category("Cooldowns", s, w, summary,
                    f"{worst.name} sat ready {worst.free:.0f}s while you were free to use it (about "
                    f"{worst.missed:.1f} casts, ~{worst.lost:,.0f} damage). Cast it as soon as it comes up."
                    if worst and s < 85 else None)


def _upkeep(um: UpkeepMetrics | None, w: int) -> Category | None:
    """buffs and DoTs you applied, by how much of combat they were up; None when there's nothing to judge"""
    if um is None or not um.rows:
        return None
    mean = um.mean_uptime
    s = ramp(mean, TUNING["upkeep_zero"], TUNING["upkeep_full"])
    rows = sorted(um.rows, key=lambda r: r.uptime)
    return Category("Upkeep", s, w, ", ".join(f"{r.name} {r.uptime:.0%}" for r in rows[:4]),
                    f"{rows[0].name} was up only {rows[0].uptime:.0%} of combat. Refresh it before it "
                    f"falls off." if s < 85 else None)


def _positioning(pm: PositionMetrics, m: Metrics, w: int) -> Category:
    """where you stood: behind your target (melee) or near the tank (others); info only unless weighted"""
    T = TUNING
    if not m.has_advanced:
        need = "needs Advanced Combat Logging"
        return Category("Positioning", 0.0, w, need, unavailable=need)
    parts = []
    if pm.behind_judged:
        parts.append(f"behind the target for {pm.behind_share:.0%} of swings ({pm.behind_judged} of {pm.swings} judged)")
    if pm.range_dists:
        parts.append(f"median {pm.median_range:.0f} yd from the nearest enemy when out of range "
                     f"({len(pm.range_dists)} of {pm.refused} judged)")
    if pm.tank_dists:
        parts.append(f"hits taken median {pm.median_tank:.0f} yd from the tank, {pm.far_share:.0%} beyond "
                     f"{FAR:.0f} yd ({len(pm.tank_dists)} of {pm.hits} judged)")
    summary = "; ".join(parts)
    melee = _melee(m)
    if (pm.behind_judged if melee else len(pm.tank_dists)) < T["min_judged"]:
        why = "too few position readings to judge"
        return Category("Positioning", 0.0, w, summary or why, unavailable=why)
    s = (ramp(pm.behind_share, T["behind_zero"], T["behind_full"]) if melee
         else ramp(pm.far_share, T["far_zero"], T["far_full"]))
    tip = None
    if s < 85 and w > 0:
        tip = ("Get behind your target: hits from behind can't be parried or blocked." if melee else
               f"{pm.far_share:.0%} of the hits you took landed more than {FAR:.0f} yd from the tank. "
               f"Stay close to the tank.")
    return Category("Positioning", s, w, summary, tip)


def _pacing(pc: PacingMetrics | None, w: int) -> Category | None:
    """pulls you went into safely and on time; None when there were no pulls to judge"""
    T = TUNING
    if pc is None or not pc.pulls:
        return None
    if not pc.judged:
        need = "needs Advanced Combat Logging"
        return Category("Pacing", 0.0, w, need, unavailable=need)
    s = ramp(pc.good / pc.judged, T["pace_zero"], T["pace_full"])
    hp = sum(1 for _, why in pc.unsafe if why == "health")
    mana, late = len(pc.unsafe) - hp, len(pc.late)
    hp_s, mana_s = f"under {T['pace_hp']:.0%} health", f"under {T['pace_mana']:.0%} mana"

    def pulls(n):
        return f"{n} pull{'s' if n != 1 else ''}"
    causes = [c for c in (
        (hp, f"{hp} {hp_s}", f"You went into {pulls(hp)} {hp_s}. Eat or bandage first."),
        (mana, f"{mana} {mana_s}", f"You went into {pulls(mana)} {mana_s}. Drink before the next pull."),
        (late, f"{late} late", f"You were late into {pulls(late)} (no press for over {T['pace_late_s']:g} s "
                               f"after your combat began). Be ready when the tank pulls.")) if c[0]]
    summary = (f"{pc.good} of {pc.judged} pulls entered safely and on time"
               + ("; " + ", ".join(c[1] for c in causes) if causes else ""))
    worst = max(causes, key=lambda c: c[0], default=None)   # ties: health, then mana, then late
    return Category("Pacing", s, w, summary, worst[2] if worst and s < 85 and w > 0 else None)


def _survival(m: Metrics, w: int) -> Category:
    """your own deaths and time under 35%"""
    T = TUNING
    lowhp_share = m.low_hp_time / m.combat_time if m.combat_time else 0
    s = max(0.0, 100 - T["death_cost"] * m.deaths - (100 - ramp(lowhp_share, T["lowhp_share_zero"], 0)) * 0.4)
    hp_txt = f"lowest health {m.lowest_hp:.0%}, {m.low_hp_time:.0f}s under 35%" if m.lowest_hp is not None \
        else "no health data (needs Advanced Combat Logging)"
    return Category(
        "Survival", s, w, f"{m.deaths} deaths; {hp_txt}",
        ("You died - look at what hit you in the seconds before it." if m.deaths else
         "You spent a lot of time low on health. Step out of hits and use your shield earlier.")
        if s < 85 else None)


def damage_category(mine: int, rel: float, secs: float, w: float) -> Category:
    """your damage; rel: it against an even split of the group's (group.py damage_share). On your own
    card and the group card."""
    return Category("Damage", ramp(rel, TUNING["damage_zero"], TUNING["damage_full"]), w,
                    f"{mine:,} damage ({rel:.0%} of an even share, {mine / secs:.0f}/s)",
                    "Damage was low: keep casting through the whole pull." if rel < 0.9 else None)


def _chances(x: InterruptMetrics, zero: float, full: float, what: str, none: str,
             tip: str) -> tuple[float, str, str | None]:
    """one part of Interrupts: score, summary, tip (`tip` names {spell}, the one most often let through)"""
    j = x.judged
    if not j:
        return 100.0, none, None
    med = x.median_response
    s = (0.5 * ramp(x.missed_share, TUNING["kick_missed_zero"], 0)
         + 0.5 * (ramp(med, zero, full) if med is not None else 0))
    summary = (f"{len(j)} {what}: you got {len(j) - x.missed}" + (f" (median {med:.1f}s)" if med is not None else "")
               + f", {x.missed} let through")
    if s >= 85:
        return s, summary, None
    let = Counter(c.spell for c in j if c.missed)
    if let:
        spell, n = let.most_common(1)[0]
        return s, summary, tip.format(spell=f"{spell} (x{n})")
    return s, summary, f"You got them, but slowly: median {med:.1f}s. React as soon as it starts."


def _interrupts(im: InterruptMetrics | None, w: float) -> Category:
    """stopping enemy casts, and dispels when you dispelled anyone this run (the two averaged)"""
    T = TUNING
    parts = []
    if im is not None and im.used:
        parts.append(_chances(im, T["kick_resp_zero"], T["kick_resp_full"], "enemy casts you could have stopped",
                              "nothing to interrupt", "Enemy casts you could have interrupted went off, most often "
                              "{spell}. Save your interrupt for it and watch their cast bar."))
    if im is not None and im.dispel is not None:
        parts.append(_chances(im.dispel, T["dispel_resp_zero"], T["dispel_resp_full"],
                              "debuffs you could have dispelled", "nothing to dispel",
                              "Debuffs you could have dispelled stayed on, most often {spell}. "
                              "Dispel it as soon as it lands."))
    if not parts:
        why = "no interrupt used this run"
        return Category("Interrupts", 0.0, w, why, unavailable=why)
    worst = min(parts, key=lambda p: p[0])
    return Category("Interrupts", sum(p[0] for p in parts) / len(parts), w, "; ".join(p[1] for p in parts), worst[2])


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
               f"Someone was under 35% health for {hm.danger_time:.0f}s. Get a shield or a heal-over-time on the tank before big pulls.")
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
               f"Ran low on mana ({mana_txt}, {hm.oom_refusals} casts refused for mana). Regenerate between pulls "
               f"and use cheaper heals on small damage.")
    cats.append(Category("Efficiency", s, W["Efficiency"],
                         f"{hm.cast_heal:,} cast healing, {hm.overheal_share:.0%} overheal; {hm.passive_heal:,} passive; "
                         f"{mana_txt}, {hm.oom_refusals} refused for mana" + (f", {hm.dispels} dispels" if hm.dispels else ""), tip))
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


def score_healer(m: Metrics, hm: HealerMetrics, pm: PositionMetrics | None = None,
                 pc: PacingMetrics | None = None) -> Scorecard:
    if m.combat_time <= 0:
        return Scorecard(0.0, "-", "healer", note="no combat in this run, nothing to score")
    if not m.has_log:
        return Scorecard(0.0, "-", "healer", note="no combat log covers this run, so healing can't be judged")
    W = WEIGHTS["healer"]
    cats = healer_categories(hm)
    cats.append(_casting(m, W["Casting"], MASHING))
    cats.append(_movement(m, W["Movement"]))
    cats.append(_input(m, W["Input"]))
    if pm is not None:
        cats.append(_positioning(pm, m, W["Positioning"]))
    if pa := _pacing(pc, W["Pacing"]):
        cats.append(pa)
    bonus, note = hybrid_bonus(hm, cats)
    return _card(cats, "healer", bonus, note)


# ----------------------------------------------------------------------------- dps
def score_dps(m: Metrics, dmg: tuple[int, float] | None = None, im: InterruptMetrics | None = None,
              cm: CooldownMetrics | None = None, um: UpkeepMetrics | None = None,
              pm: PositionMetrics | None = None, pc: PacingMetrics | None = None) -> Scorecard:
    """dmg: your damage and its share of an even split (group.py damage_share; None when solo)"""
    if m.combat_time <= 0:
        return Scorecard(0.0, "-", "dps", note="no combat in this run, nothing to score")
    W = WEIGHTS["dps"]
    cats = [_activity(m, W["Activity"]), _pooling_casting(m, W["Casting"]),
            _movement(m, 0 if _melee(m) else W["Movement"]), _survival(m, W["Survival"]), _input(m, W["Input"])]
    if m.has_log:   # both come from the combat log; without one the card is as it always was
        need = "needs a group to compare with"
        cats.insert(1, _interrupts(im, W["Interrupts"]))
        if cm is not None:
            cats.insert(1, _cooldowns(cm, W["Cooldowns"]))
        cats.insert(0, damage_category(*dmg, m.combat_time, W["Damage"]) if dmg else
                    Category("Damage", 0.0, W["Damage"], need, unavailable=need))
        if up := _upkeep(um, W["Upkeep"]):
            cats.append(up)
    if res := _resource(m, W["Resource"]):
        cats.append(res)
    if pm is not None and m.has_log:
        cats.append(_positioning(pm, m, W["Positioning"]))
    if pa := _pacing(pc, W["Pacing"]):
        cats.append(pa)
    return _card(cats, "dps")


# ----------------------------------------------------------------------------- tank
def tank_categories(tm: TankMetrics, weights: dict, you: bool = True, m: Metrics | None = None) -> list[Category]:
    """Holding mobs, Pickups and Survival: what any tank can be judged on from the combat log.
    m (your own add-on measurements) gives Survival your time low on health too; without it Survival
    is deaths only. you=False words it about someone else."""
    T = TUNING
    them = "you" if you else "them"
    cats: list[Category] = []

    share = tm.held / tm.mobs if tm.mobs else 1.0
    cats.append(Category("Holding mobs", ramp(share, T["hold_zero"], T["hold_full"]), weights["Holding mobs"],
                         f"{tm.held} of {tm.mobs} mobs went for {them} first ({share:.0%})",
                         "Mobs went for other players first: pick them up faster (taunt, or tag every mob)."
                         if share < 0.8 else None))

    j = tm.judged
    if j:
        med = tm.median_pickup
        s = 0.6 * ramp(med, T["pickup_zero"], T["pickup_full"]) + 0.4 * ramp(tm.missed_share, T["pickup_missed_zero"], 0)
        summary = (f"{len(j)} times a mob left {them}: median {med:.1f}s to get it back, "
                   f"{tm.missed} not back within {PICKUP_CAP:.0f}s")
        tip = None
        if s < 85:
            names: dict[str, int] = {}
            for x in j:
                names[x.to_name] = names.get(x.to_name, 0) + 1
            worst = max(names, key=names.get)
            tip = (f"Mobs got away: median {med:.1f}s to get them back, most often from {worst} "
                   f"({names[worst]} times). Taunt or hit a mob as soon as it turns.")
    else:
        s, summary, tip = 100.0, f"no mob left {them}", None
    cats.append(Category("Pickups", s, weights["Pickups"], summary, tip))

    if m is not None:
        cats.append(_survival(m, weights["Survival"]))
    else:
        txt = f"{tm.deaths} death{'s' if tm.deaths != 1 else ''}"
        cats.append(Category("Survival", max(0.0, 100 - T["tank_death_cost"] * tm.deaths), weights["Survival"], txt,
                             "Died: look at the hits before it, and use cooldowns earlier." if tm.deaths else None))
    return cats


def score_tank(m: Metrics, tm: TankMetrics, im: InterruptMetrics | None = None,
               cm: CooldownMetrics | None = None, um: UpkeepMetrics | None = None,
              pm: PositionMetrics | None = None, pc: PacingMetrics | None = None) -> Scorecard:
    if m.combat_time <= 0:
        return Scorecard(0.0, "-", "tank", note="no combat in this run, nothing to score")
    if not m.has_log:
        return Scorecard(0.0, "-", "tank", note="no combat log covers this run, so tanking can't be judged")
    W = WEIGHTS["tank"]
    cats = tank_categories(tm, W, True, m)
    cats += [_activity(m, W["Activity"]), _pooling_casting(m, W["Casting"]), _input(m, W["Input"]),
             _movement(m, 0 if _melee(m) else W["Movement"]), _interrupts(im, W["Interrupts"])]
    if cm is not None:
        cats.append(_cooldowns(cm, W["Cooldowns"]))
    if up := _upkeep(um, W["Upkeep"]):
        cats.append(up)
    if res := _resource(m, W["Resource"]):
        cats.append(res)
    if pm is not None:
        cats.append(_positioning(pm, m, W["Positioning"]))
    if pa := _pacing(pc, W["Pacing"]):
        cats.append(pa)
    return _card(cats, "tank")


def score(m: Metrics, role: str = "healer", hm: HealerMetrics | None = None,
          tm: TankMetrics | None = None, dmg: tuple[int, float] | None = None,
          im: InterruptMetrics | None = None, cm: CooldownMetrics | None = None,
          um: UpkeepMetrics | None = None, pm: PositionMetrics | None = None,
          pc: PacingMetrics | None = None) -> Scorecard:
    if role == "healer" and hm is not None:
        return score_healer(m, hm, pm, pc)
    if role == "tank" and tm is not None:
        return score_tank(m, tm, im, cm, um, pm, pc)
    return score_dps(m, dmg, im, cm, um, pm, pc)


def _fail_tip(m: Metrics, ignore: set[str] = frozenset()) -> str:
    counted = [(r, n) for r, n in m.fail_reasons.most_common() if r not in ignore]
    reason, n = (counted or [("unknown", m.failed)])[0]
    advice = {
        "Not yet recovered": "you're pressing before the cooldown or GCD is back - that's mashing",
        "Invalid target": "check your target before pressing",
        "Out of range": "you're pressing while out of range",
        "Not enough mana": "you ran out of mana - regenerate more, cast cheaper heals",
        "Can't do that while moving": "stop before you cast",
        "Another action is in progress": "you're pressing while already casting",
        "Interrupted": "you're starting casts that get stopped",
    }.get(reason, "look at what's refusing them")
    total = sum(n for _, n in counted) if ignore else m.failed
    return f"{total} presses were refused, most often \"{reason}\" (x{n}): {advice}."
