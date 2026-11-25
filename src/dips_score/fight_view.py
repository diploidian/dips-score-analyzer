"""What the Fight page shows, as plain data (no Qt), from a live fight (live/summary.py's dict): how much of the damage
you could have done you did, the biggest gap and where the rest went, what went well, the pull, the danger, your share
of the group's; and the fight list's row. Old saved fights lack some keys (free, auto, group, potential, pull, foes):
their parts are empty."""
from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import datetime

from .debrief import auto_share, fmt_time
from .live.summary import idle_words
from .scoring.group import ordinal
from .scoring.usable import across

CLEAN, LOW = 0.90, 0.60      # efficiency from which a fight is clean (gS), and under which it's poor (gD)
SWINGS, SHOTS, IDLE = "Swings lost", "Shots lost", "Idle with resource"
CLIPPED, NO_ABILITY = "Shots clipped by casts", "No ability"


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
    also: list[str] = field(default_factory=list)       # what to improve that isn't a row
    pull: list[tuple[str, str]] = field(default_factory=list)       # (label, text)
    danger: list[tuple[str, str]] = field(default_factory=list)     # (label, text); "" carries on the label above
    group: list[tuple[str, int, int, bool]] | None = None   # (name, damage, healing, is you), most damage first
    group_line: str | None = None
    auto_share: tuple[str, float] | None = None     # ("Melee 46% of your damage", share) over the losses



def _n(v: float) -> str:
    return f"{v:,.0f}"


def _foes(f: dict) -> str:
    """every enemy in the fight, most damaged first ("" for a lone enemy or an older fight)"""
    foes = f.get("foes") or []
    if sum(c for _, c in foes) < 2:
        return ""
    return ", ".join(n + (f" ×{c}" if c > 1 else "") for n, c in foes)


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
    rng = d.get("ranged") or {}
    if rng.get("damage_lost", 0) > 0:
        n = rng["shots_lost"]
        out.append((SHOTS, f"×{n}", rng["damage_lost"], f"{n} shot{'s' if n != 1 else ''} lost while you weren't "
                                                        "shooting"))
        own.append(f"{n} shot")
    for c in d.get("cooldowns") or []:
        if c.get("lost", 0) > 0 and not c.get("held"):
            free = c.get("free")      # None: saved before ready time was measured
            s = "" if free is None else f"{free:.1f} s"
            title = f"{c['name']} sat ready {s}".rstrip() + across(c.get("chances"))
            out.append((f"{c['name']} sat ready", s, c["lost"], title))
            own.append(f"{c['name']} sat ready ")
    idle = d.get("idle") or {}
    if idle.get("lost", 0) > 0:       # in the potential too, so the rows add up to what was left on the table
        free, auto_t = idle["with_resource"], idle.get("swinging_free") or 0.0
        s = f"{free:.1f} s"
        label, detail = IDLE, s
        if auto_t >= 0.05:            # M2's split: no ability used while swinging is not idle
            word = "shooting" if idle.get("shooting") else "swinging"
            label, detail = NO_ABILITY, f"{auto_t:.1f} s {word}" + (f", {free - auto_t:.1f} s idle"
                                                                     if free - auto_t >= 0.05 else "")
        out.append((label, detail, idle["lost"], idle_words(free, idle.get("swinging_free"),
                                                            idle.get("shooting", False)) + " with resource to spare"))
        own += (f"{s} idle", "No ability used for ")
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
    """d["improve"] less the lines that are rows already, and less summary's "Dropped to" lines when there was danger:
    the Danger section says it"""
    lines = [s for s in d.get("improve") or [] if not s.startswith(own)]
    return [s for s in lines if not s.startswith("Dropped to ")] if d.get("danger") else lines


def _pull(d: dict) -> list[tuple[str, str]]:
    """the time since the last fight, every enemy, the buffs you pulled with; none of it said when not kept"""
    pull, out = d.get("pull"), []
    if pull is not None:
        since = pull.get("since_last")
        out.append(("Since the last fight", "first fight since the log started" if since is None else f"{since:.0f} s"))
    if foes := _foes(d):
        out.append(("Enemies", foes))
    if buffs := (pull or {}).get("buffs"):
        out.append(("Buffs", ", ".join(buffs[:8])))
    return out


def _danger(d: dict) -> list[tuple[str, str]]:
    """your lowest health and when, the hits that put you there (a row per attacker, in summary's order), the
    defensives that sat ready; none without danger"""
    danger = d.get("danger")
    if not danger:
        return []
    by: dict[str, list[str]] = {}
    for h in danger.get("hits") or []:
        by.setdefault(h["who"], []).append(f"{h['spell']} {_n(h['amount'])}")
    out = [("Lowest health", f"{danger['hp']:.0%} at {fmt_time(danger['t'])}")]
    out += [("" if k else "Hits", f"{who}: {', '.join(hits)}") for k, (who, hits) in enumerate(by.items())]
    # without "answered" it was summed up when a defensive pressed at the low moment still counted as unused
    if "answered" in danger and (unused := danger.get("unused")):
        out.append(("Ready, not used", ", ".join(unused)))
    return out


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
        rows=[(label, detail, dmg) for label, detail, dmg, _ in losses] + _clipped(d),
        went_well=list(d.get("good") or []),
        also=_also(d, own), pull=_pull(d), danger=_danger(d))
    v.big, v.unit, v.caption = _hero(d, eff)
    if losses:
        v.gap = (losses[0][3], f"≈ {_n(losses[0][2])}")
    if d.get("potential") is not None and d["potential"] - d["damage"] >= 1:      # under 1: nothing left
        v.left_on_table = d["potential"] - d["damage"]
    v.group, v.group_line = _group(d)
    if not d.get("healing_role"):
        v.auto_share = auto_share((d.get("auto") or {}).get("damage"), (d.get("ranged") or {}).get("damage"),
                                  d["damage"])
    return v


def _clipped(d: dict) -> list[tuple[str, str, float]]:
    """shots a cast cut short: a row of its own under the priced ones (not priced, so no bar)"""
    n = (d.get("ranged") or {}).get("clipped") or 0
    return [(CLIPPED, f"×{n}", 0.0)] if n and not d.get("healing_role") else []


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


FOLLOW = 0.5            # a macro or item press: the spell you sent this soon after is the one it cast
ARRIVES = "Arrives after a /reload or logout: the game only saves your presses then."
NOT_HERE = ("Not recorded here. Turn on \"Everywhere else\" in the add-on's options to record presses outside "
            "dungeons.")
OLDER = "This fight is older than the recordings the add-on keeps."
NOT_RECORDED = "Not recorded: no recording the add-on kept has this fight."
READING = "Reading this fight's recording…"
NONE_PRESSED = "No presses recorded in this fight."


@dataclass
class Presses:
    """What you pressed in a fight, for the Fight page: rows (name, a muted note, the spell ID, by key, by click, not
    told), most pressed first, and the line over them; or no rows and why (ARRIVES, NOT_HERE, ...)"""
    rows: list[tuple[str, str, str, int, int, int]] = field(default_factory=list)
    line: str = ""


def press_reason(start: datetime, saved: float | None, oldest: datetime | None, inside: bool) -> str:
    """why a fight has no presses, when no recorded run has it: saved, when the game last saved the add-on's file
    (time()); oldest, the oldest recording it keeps; inside, the fight was in an instance (recorded by default, so
    "Everywhere else" isn't the reason)"""
    if saved is not None and start.timestamp() > saved:
        return ARRIVES
    if oldest is not None and start < oldest:
        return OLDER
    return NOT_RECORDED if inside else NOT_HERE


def presses(lines, window: tuple[float, float], names: dict[int, str]) -> Presses:
    """the add-on's A lines (a press: slot, kind, id, how) in window, by spell; names: spell id -> name. A macro or an
    item that names no spell this knows is the spell you sent within FOLLOW seconds, if any"""
    a, b = window
    sent = [(ln.t, ln.num(0)) for ln in lines if ln.code == "CS"]
    times = [t for t, _ in sent]
    rows: dict[tuple[str, str, str], list[int]] = {}
    for ln in lines:
        if ln.code != "A" or not a <= ln.t <= b:
            continue
        kind, pid, how = ln.f(1), ln.num(2), ln.f(3)
        spell = pid if kind == "spell" else None
        if spell is None:       # a macro or an item: the spell sent with it, else a macro's own id when it names one
            i = bisect_left(times, ln.t)
            spell = sent[i][1] if i < len(sent) and sent[i][0] <= ln.t + FOLLOW else None
            if spell is None and kind == "macro" and pid in names:
                spell = pid
        note = "" if kind == "spell" else kind
        if spell is not None and spell in names:
            key = (names[spell], note, str(spell))
        elif spell is not None:
            key = (f"Spell {spell}", note, str(spell))
        else:
            key = (f"{kind.title()} {pid if pid is not None else '?'}", f"{note}, no spell followed".lstrip(", "), "–")
        n = rows.setdefault(key, [0, 0, 0])
        n["KC".find(how) if how in ("K", "C") else 2] += 1
    out = sorted(((*k, *n) for k, n in rows.items()), key=lambda r: (-sum(r[3:]), r[0]))
    if not out:
        return Presses([], NONE_PRESSED)
    key, click, other = (sum(r[i] for r in out) for i in (3, 4, 5))
    total = key + click + other
    said = [f"{key} by key" if key else "", f"{click} by click" if click else "",
            f"{other} the game's bars didn't say" if other else ""]
    said = [s for s in said if s]
    how = ("all by key" if key == total else "all by click" if click == total else ", ".join(said))
    return Presses(out, f"{total} press{'es' if total != 1 else ''}, {how}.")


def run_window(d: dict, start: datetime, length: float) -> tuple[float, float] | None:
    """the fight on the timeline of a run that began at start and lasted length seconds: in its seconds, 3 s either
    side; None when the fight isn't inside that run"""
    a = (datetime.fromisoformat(d["start"]) - start).total_seconds()
    b = a + d["duration"]
    return (a - 3, b + 3) if a >= 0 and b <= length else None
