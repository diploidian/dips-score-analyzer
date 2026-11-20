"""What the Fight page shows, as plain data (no Qt), from a live fight (live/summary.py's dict): how much of the damage
you could have done you did, the biggest gap and where the rest went, what went well, your share of the group's; and
the fight list's row. Old saved fights lack some keys (free, auto, group, potential): their parts are empty."""
from dataclasses import dataclass, field
from datetime import datetime

from .debrief import fmt_time
from .scoring.group import ordinal

CLEAN, LOW = 0.90, 0.60      # efficiency from which a fight is clean (gS), and under which it's poor (gD)
SWINGS, IDLE = "Swings lost", "Idle with resource"


@dataclass
class FightView:
    name: str = ""                  # the page's title: "Blackfathom Oracle +3 more"
    when: str = ""
    zone: str = ""
    kind: str = ""
    efficiency: float | None = None     # None: not measured (an older fight), or no damage done
    big: str = "–"                  # the hero's figure, its unit and the caption under it
    unit: str | None = None
    caption: str = ""
    verdict: str = ""
    duration: str = ""
    result: str = ""
    figures: list[tuple[str, str]] = field(default_factory=list)
    gap: tuple[str, str] | None = None                  # (title, price): the top row
    rows: list[tuple[str, str, float]] = field(default_factory=list)    # (label, detail, damage), most first
    left_on_table: float | None = None
    went_well: list[str] = field(default_factory=list)
    also: list[str] = field(default_factory=list)       # a close call, then what to improve that isn't a row
    group: list[tuple[str, int, int, bool]] | None = None   # (name, damage, healing, is you), most damage first
    group_line: str | None = None
    abilities: list[dict] = field(default_factory=list)


def _n(v: float) -> str:
    return f"{v:,.0f}"


def _losses(d: dict) -> tuple[list[tuple[str, str, float, str]], tuple[str, ...]]:
    """the damage lost, as (label, detail, damage, the plate's title) most first, and the start of each one's own line
    in d["improve"]; none for a healing fight, whose losses aren't counted"""
    if d.get("healing_role"):
        return [], ()
    out, own = [], []
    auto = d.get("auto") or {}
    if auto.get("damage_lost", 0) > 0:
        n = auto.get("lost_other", auto.get("lost", 0))     # the swings the damage is for (not those lost casting)
        out.append((SWINGS, f"×{n}", auto["damage_lost"], f"{n} swing{'s' if n != 1 else ''} lost while you weren't "
                                                          "attacking"))
        own.append(f"{n} swing")
    for c in d.get("cooldowns") or []:
        if c.get("lost", 0) > 0 and not c.get("held"):
            free = c.get("free")      # None: saved before ready time was measured
            s = "" if free is None else f"{free:.1f} s"
            out.append((f"{c['name']} sat ready", s, c["lost"], f"{c['name']} sat ready {s}".rstrip()))
            own.append(f"{c['name']} sat ready ")
    idle = d.get("idle") or {}
    if idle.get("lost", 0) > 0:       # in the potential too, so the rows add up to what was left on the table
        s = f"{idle['with_resource']:.1f} s"
        out.append((IDLE, s, idle["lost"], f"{s} idle with resource to spare"))
        own.append(f"{s} idle")
    return sorted(out, key=lambda r: -r[2]), tuple(own)


def _group(d: dict) -> tuple[list[tuple[str, int, int, bool]] | None, str | None]:
    """members plus you, most damage first (you first of a tie, as your rank counts only those above you), and the
    line of your shares over them; None with nobody else"""
    g = d.get("group")
    if not g or g.get("size", 1) <= 1:
        return None, None
    rows = [(m["name"], round(m["damage"]), round(m["healing"]), False) for m in g.get("members", [])]
    you = ("You", round(d["damage"]), round(d["healing"]), True)
    rows = sorted(rows + [you], key=lambda r: (-r[1], not r[3], -r[2]))
    dmg, heal = sum(r[1] for r in rows), sum(r[2] for r in rows)
    rank = 1 + sum(r[1] > you[1] for r in rows)
    line = (f"You did {you[1] / dmg if dmg else 0:.0%} of the damage ({ordinal(rank)} of {len(rows)}) and "
            f"{you[2] / heal if heal else 0:.0%} of the healing.")
    if g.get("deaths"):
        line += " Died: " + ", ".join(g["deaths"]) + "."
    return rows, line


def _also(d: dict, own: tuple[str, ...]) -> list[str]:
    """d["improve"] less the lines that are rows already; a close call (danger you lived through) on top, in place of
    summary's own "Dropped to" line"""
    lines = [s for s in d.get("improve") or [] if not s.startswith(own)]
    danger = d.get("danger")
    if not danger or d.get("result") == "you died":
        return lines
    close = f"Close call: down to {danger['hp']:.0%} health at {fmt_time(danger['t'])}"
    if unused := danger.get("unused"):
        close += f" — {' and '.join(unused[:2])} {'was' if len(unused) == 1 else 'were'} ready"
    return [close] + [s for s in lines if not s.startswith("Dropped to ")]


def _hero(d: dict, eff: float | None) -> tuple[str, str | None, str]:
    """the big figure, its unit and caption: the efficiency; a healer's healing when there's none"""
    if d.get("healing_role"):
        if eff is None:
            return _n(d["healing"]), None, "healed · mostly healing this fight"
        return f"{eff * 100:.0f}", "%", "mostly healing: damage you didn't do isn't counted"
    if eff is None:
        return "–", None, "no damage done this fight" if not d["damage"] else "not measured in this older fight"
    return f"{eff * 100:.0f}", "%", "of the damage that was possible"


def build_fight(d: dict) -> FightView:
    """the page for one live fight"""
    eff = d.get("efficiency")
    if not d["damage"] and not d.get("healing_role"):
        eff = None                    # 100% of nothing: not a figure
    when = datetime.fromisoformat(d["start"])
    losses, own = _losses(d)
    v = FightView(
        name=d["target"] + (f" +{d['more']} more" if d.get("more") else ""), when=f"{when:%a %d %b %H:%M:%S}",
        zone=d.get("zone") or "", kind=d["kind"], efficiency=eff, verdict=d.get("verdict") or "",
        duration=fmt_time(d["duration"]), result=d["result"],
        figures=[(_n(d["damage"]), "damage"), (f"{d['dps']:.0f}", "DPS"), (_n(d["taken"]), "taken"),
                 (_n(d["healing"]), "healing")],
        rows=[(label, detail, dmg) for label, detail, dmg, _ in losses],
        went_well=list(d.get("good") or []),
        also=_also(d, own),
        abilities=list(d.get("abilities") or []))
    v.big, v.unit, v.caption = _hero(d, eff)
    if losses:
        v.gap = (losses[0][3], f"≈ {_n(losses[0][2])}")
    if d.get("potential") is not None and d["potential"] - d["damage"] >= 1:      # under 1: nothing left
        v.left_on_table = d["potential"] - d["damage"]
    v.group, v.group_line = _group(d)
    return v


def list_row(d: dict) -> tuple[str, list[tuple[str, str]], str]:
    """the fight list's row: the fight's name, its muted line as (text, ink) runs (the efficiency inked gS when clean,
    gD when poor, else tx2), and its kind"""
    name = d["target"] + (f" +{d['more']}" if d.get("more") else "")
    length = f" · {fmt_time(d['duration'])}"
    eff = d.get("efficiency")
    if not d["damage"] and not d.get("healing_role"):
        runs = [(f"no damage{length}", "mu")]
    elif eff is None:
        runs = [(f"{d['dps']:.0f} DPS", "mu"), (length, "mu")]
    else:
        ink = "gS" if eff >= CLEAN else "gD" if eff < LOW else "tx2"
        runs = [(f"{d['dps']:.0f} DPS · ", "mu"), (f"{eff:.0%}", ink), (length, "mu")]
    if d.get("result") == "you died":
        runs.append((" · died", "mu"))
    return name, runs, d["kind"]


def run_window(d: dict, start: datetime, length: float) -> tuple[float, float] | None:
    """the fight on the timeline of a run that began at start and lasted length seconds: in its seconds, 3 s either
    side; None when the fight isn't inside that run"""
    a = (datetime.fromisoformat(d["start"]) - start).total_seconds()
    b = a + d["duration"]
    return (a - 3, b + 3) if a >= 0 and b <= length else None
