"""What the Spells page shows, as plain data (no Qt): a player's abilities merged by name, ranked by damage and by
healing, the cooldown that cost you most, the damage abilities the game refused, and the verdict (led by the healing
for a healer, else by the damage)."""
from dataclasses import dataclass, field

from .model.casts import SpellRow, spell_table
from .scoring.cooldowns import CooldownRow
from .scoring.usable import across

REFUSED = 0.25      # refused on more than this share of presses: worth a look
SUMS = ("casts", "failed", "damage", "healing", "overheal", "hits", "crits")


@dataclass
class Merged(SpellRow):
    note: str | None = None     # where its damage came from, when another row's was folded in


@dataclass
class AbilityRow:
    name: str
    note: str | None
    casts: int
    refused: int
    refused_share: float | None     # of the presses; None: none, or not in the log (only yours are)
    damage: int
    share: float                    # of the damage
    per_min: float | None           # casts per combat minute; None: never cast
    crit: float | None              # of the hits; None: no hits
    healing: int
    overheal_share: float


@dataclass
class SpellsView:
    total_damage: int = 0
    dps: float = 0.0
    total_healing: int = 0
    hps: float = 0.0
    healer: bool = False                                 # scored as a healer: the healing leads
    verdict: str = ""
    fix: tuple[str, str, str] | None = None             # (title, price, caption)
    next_rows: list[tuple[str, str]] = field(default_factory=list)
    damage_rows: list[AbilityRow] = field(default_factory=list)
    healing_rows: list[AbilityRow] = field(default_factory=list)
    buff_rows: list[AbilityRow] = field(default_factory=list)
    all_rows: list[AbilityRow] = field(default_factory=list)
    show: tuple[float, float, str] | None = None         # "Show on the timeline": (start, end, spell)
    refused_most: str | None = None                      # the damage ability refused most, over REFUSED


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def merge_by_name(rows: list[SpellRow]) -> list[SpellRow]:
    """rows of one name summed; a damage-only "<X> of <Y>" folded into a pressed-only X (Judgement of Command into
    Judgement), noted; first seen first. The rows given are left as they were."""
    by: dict[str, Merged] = {}
    for r in rows:
        m = by.setdefault(r.spell, Merged(r.spell_id, r.spell))
        for k in SUMS:
            setattr(m, k, getattr(m, k) + getattr(r, k))
    pressed = {n for n, m in by.items() if (m.casts or m.failed) and not (m.damage or m.healing)}
    out, folded = [], {}
    for name, m in by.items():
        x, of, _ = name.partition(" of ")
        if of and x in pressed and m.damage and not (m.casts or m.failed or m.healing):
            for k in SUMS:
                setattr(by[x], k, getattr(by[x], k) + getattr(m, k))
            folded.setdefault(x, []).append(name)
        else:
            out.append(m)
    for x, names in folded.items():
        by[x].note = f"damage from {_and(names)}"
    return out


def _casts(n: float) -> str:
    k = round(n)
    return "under one more cast" if k < 1 else f"about {k} more cast{'' if k == 1 else 's'}"


def spells_view(rows: list[SpellRow], combat_s: float, cooldowns=None, who: str | None = None,
                where: dict[str, tuple[float, float]] | None = None, role: str = "dps") -> SpellsView:
    """rows: spell_table's; cooldowns: your CooldownRows (name, free, missed, lost), None when not measured;
    who: another player's name (None: you); where: the (start, end) of the fight each cooldown cost most in;
    role: what they're scored as ("healer", "tank", "dps")"""
    merged = [r for r in merge_by_name(rows) if r.casts or r.failed or r.damage or r.healing]
    total = sum(r.damage for r in merged)
    minutes = combat_s / 60
    abilities = [AbilityRow(
        name=r.spell, note=r.note, casts=r.casts, refused=r.failed,
        refused_share=r.failed / (r.casts + r.failed) if who is None and r.casts + r.failed else None,
        damage=r.damage, share=r.damage / total if total else 0.0,
        per_min=r.casts / minutes if r.casts and minutes else None, crit=r.crits / r.hits if r.hits else None,
        healing=r.healing, overheal_share=r.overheal_share) for r in merged]
    healed = sum(r.healing for r in merged)
    v = SpellsView(total_damage=total, dps=total / combat_s if combat_s else 0.0, total_healing=healed,
                   hps=healed / combat_s if combat_s else 0.0, healer=role == "healer")
    v.all_rows = sorted(abilities, key=lambda r: (r.damage, r.healing, r.casts), reverse=True)
    v.damage_rows = sorted((r for r in abilities if r.damage), key=lambda r: r.damage, reverse=True)
    v.healing_rows = sorted((r for r in abilities if r.healing), key=lambda r: r.healing, reverse=True)
    v.buff_rows = sorted((r for r in abilities if r.casts and not (r.damage or r.healing)), key=lambda r: r.casts,
                         reverse=True)
    # refusals only among the damage abilities, the table they're shown in (a heal's or a lone press's aren't)
    refused = sorted((r for r in v.damage_rows if r.refused_share is not None and r.refused_share > REFUSED),
                     key=lambda r: r.refused, reverse=True)
    known = cooldowns if who is None and cooldowns else []       # only yours are measured
    cds = sorted((c for c in known if c.lost >= 1), key=lambda c: c.lost, reverse=True)
    fix = cds[0] if cds else None
    if fix:
        chances = across(getattr(fix, "chances", None))
        v.fix = (f"{fix.name} sat ready {fix.free:.0f} s{chances}", f"~{fix.lost:,.0f} damage", _casts(fix.missed))
        if where and fix.name in where:
            v.show = (*where[fix.name], fix.name)
    v.next_rows = [(f"{r.name} refused on {r.refused} of {r.casts + r.refused} presses",
                    f"{r.refused_share:.0%} refused") for r in refused]
    v.next_rows += [(f"{c.name} sat ready {c.free:.0f} s{across(getattr(c, 'chances', None))}",
                     f"~{c.lost:,.0f} damage") for c in cds[1:2]]
    v.refused_most = refused[0].name if refused else None
    v.verdict = _verdict(v, refused[0] if refused else None, fix, "your" if who is None else f"{who}'s")
    return v


def _verdict(v: SpellsView, refused: AbilityRow | None, fix, whose: str) -> str:
    """the top two abilities' share (a healer's healing, else the damage; the other when there's none), then the
    worst refusal and the cooldown to fix"""
    lead = {"damage": v.damage_rows, "healing": v.healing_rows}
    what = next((w for w in (("healing", "damage") if v.healer else ("damage", "healing")) if lead[w]), None)
    if what is None:
        return "No damage or healing logged."
    top = lead[what][:2]
    part, total = (sum(getattr(r, what) for r in rs) for rs in (top, lead[what]))
    out = [f"{_and([r.name for r in top])} did {part / total:.0%} of {whose} {what}."]
    chances = across(getattr(fix, "chances", None))
    bits = ([f"{refused.name} was refused on {refused.refused} of {refused.casts + refused.refused} presses"]
            if refused else []) + ([f"{fix.name} sat ready for {fix.free:.0f} s{chances}"] if fix else [])
    if bits:
        out.append(", and ".join(bits) + ".")
    return " ".join(out)


def _cooldowns(fights) -> tuple[list[CooldownRow], dict[str, tuple[float, float]]]:
    """the fights' cooldown rows summed by name, and the fight each cost most in, as a timeline window"""
    rows, worst = {}, {}
    for fr in fights:
        for r in fr.cooldowns.rows if fr.cooldowns else []:
            x = rows.setdefault(r.name, CooldownRow(r.name, 0.0, 0.0, 0.0))
            x.free, x.missed, x.lost = x.free + r.free, x.missed + r.missed, x.lost + r.lost
            if getattr(r, "chances", None) is not None:      # rows saved before chances have none
                x.chances = (x.chances or 0) + r.chances
            if r.lost > worst.get(r.name, (-1.0, None))[0]:
                worst[r.name] = (r.lost, (fr.fight.start - 3, fr.fight.end + 3))
    return list(rows.values()), {n: w for n, (_, w) in worst.items()}


def build_spells(a, guid: str, scope: str = "all") -> SpellsView:
    """guid's spells in the analysis a, over scope: "all" (the whole run), "boss" or "trash" fights"""
    def kept(f) -> bool:
        return scope == "all" or (f.boss is not None) == (scope == "boss")
    windows = None if scope == "all" else [(f.start - 2, f.end + 2) for f in a.data.fights if kept(f)]
    rows = spell_table(a.data, guid, windows, a.pets.get(guid))
    combat = sum(b - c for c, b in windows) if windows else a.metrics.combat_time or 0.0
    me = guid == a.data.player_guid
    cds, where = _cooldowns(fr for fr in a.fights if kept(fr.fight)) if me and a.cooldowns else (None, None)
    role = a.role if me else (a.roster[guid].role or "dps").lower()     # as the Debrief and Group score them
    return spells_view(rows, combat, cds, None if me else a.roster[guid].name, where, role)
