"""When an ability can be used at all, by spell name: one table, the rest of the app asks it.

    types    works only on these creature types (the add-on's dipsScoreDB.types names each enemy's type)
    below    works only on a target under this share of its health (the advanced log's foe health)
    after    works only for `window` seconds after an attack was avoided: "target" the target avoided yours
             (Overpower after a dodge), "you" you avoided an enemy's (Revenge after a block, dodge or parry)
    chance   what one chance is, as the call-outs say it ("0 of 37 chances: 37 undead and demons")
    works    "Exorcism works on undead and demons."

A spell not in the table is always usable. A chance is an enemy of the type met, an enemy that dropped under
the health line, or one avoided attack. None means the chances cannot be known (no creature types loaded, no
foe health in the log, a fight saved before chances were counted): such a spell is never called out as unused.
"""
from __future__ import annotations

RULES: dict[str, dict] = {
    "Exorcism": {"types": ("Undead", "Demon"), "chance": "undead and demons", "works": "on undead and demons"},
    "Holy Wrath": {"types": ("Undead", "Demon"), "chance": "undead and demons", "works": "on undead and demons"},
    "Turn Undead": {"types": ("Undead",), "chance": "undead", "works": "on undead"},
    "Shackle Undead": {"types": ("Undead",), "chance": "undead", "works": "on undead"},
    "Hibernate": {"types": ("Beast", "Dragonkin"), "chance": "beasts and dragonkin",
                  "works": "on beasts and dragonkin"},
    "Banish": {"types": ("Demon", "Elemental"), "chance": "demons and elementals",
               "works": "on demons and elementals"},
    "Polymorph": {"types": ("Beast", "Humanoid", "Critter"), "chance": "beasts, humanoids and critters",
                  "works": "on beasts, humanoids and critters"},
    "Execute": {"below": 0.20, "chance": "enemies under 20% health", "works": "on enemies under 20% health"},
    "Hammer of Wrath": {"below": 0.20, "chance": "enemies under 20% health",
                        "works": "on enemies under 20% health"},
    "Overpower": {"after": ("dodge",), "by": "target", "window": 5.0, "chance": "dodges",
                  "works": "after the target dodges you"},
    "Revenge": {"after": ("block", "dodge", "parry"), "by": "you", "window": 5.0,
                "chance": "blocks, dodges and parries", "works": "after you block, dodge or parry"},
    "Riposte": {"after": ("parry",), "by": "you", "window": 5.0, "chance": "parries", "works": "after you parry"},
    "Counterattack": {"after": ("parry",), "by": "you", "window": 5.0, "chance": "parries",
                      "works": "after you parry"},
}


def across(n: int | None) -> str:
    """" across 3 chances" after a "sat ready" figure; "" when the spell needs no chance or they're unknown"""
    return "" if n is None else f" across {n} chance{'' if n == 1 else 's'}"


def rule(name: str) -> dict | None:
    return RULES.get(name)


def reason(r: dict) -> str:
    """why ready time outside a chance is excused"""
    if "types" in r:
        return "no valid target"
    if "below" in r:
        return f"target above {r['below']:.0%}"
    return "nothing to answer"


def _merge(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def fight_chances(r: dict, dur: float, foes: list[tuple], types: dict | None,
                  avoided: dict[tuple[str, str], list[float]]) -> tuple[list[tuple[float, float]] | None, int | None]:
    """(when it could be used, how many chances) in one fight; (None, None) when that cannot be known.
    foes: (name, first seen, died or None, [(t, health share)]); avoided: ("target"|"you", "dodge"|...) -> times"""
    if "types" in r:
        known = [n for n, *_ in foes if (types or {}).get(n)]
        if not known:
            return None, None
        # an enemy whose type is not known yet may be a valid one: its time stays usable, it is not counted
        ok = [(a, dur if b is None else b) for n, a, b, _ in foes if (types or {}).get(n, r["types"][0]) in r["types"]]
        return _merge(ok), sum(types[n] in r["types"] for n in known)
    if "below" in r:
        if not any(hp for *_, hp in foes):
            return None, None
        spans = []
        for _, _, died, hp in foes:
            low = None     # from a reading under the line to the next one over it (or the enemy's death)
            for t, v in hp + [(dur if died is None else died, 1.0)]:
                if v is None:
                    continue
                if v < r["below"] and low is None:
                    low = t
                elif v >= r["below"] and low is not None:
                    spans.append((low, t))
                    low = None
        n = sum(any(v is not None and v < r["below"] for _, v in hp) for *_, hp in foes)
        return _merge(spans), n
    times = sorted(t for kind in r["after"] for t in avoided.get((r["by"], kind), []))
    return _merge([(t, min(dur, t + r["window"])) for t in times]), len(times)


def window_chances(name: str, fights: list[dict], types: dict | None) -> dict | None:
    """{"chances", "fights" (fights with at least one)} over saved fight summaries, counted where known (types
    from the fight's enemies, the others from the fight's "chances"); None for a spell not in the table or when
    no fight knows"""
    r = RULES.get(name)
    if r is None:
        return None
    per = []
    for f in fights:
        if "types" in r:
            foes = [(n, c) for n, c in f.get("foes") or [] if (types or {}).get(n)]
            if foes:
                per.append(sum(c for n, c in foes if types[n] in r["types"]))
        elif (n := (f.get("chances") or {}).get(name)) is not None:
            per.append(n)
    return {"chances": sum(per), "fights": sum(n > 0 for n in per)} if per else None


def has_chance(name: str, fights: list[dict], types: dict | None) -> bool:
    """not in the table, or at least one known chance in these fights"""
    return name not in RULES or bool((c := window_chances(name, fights, types)) and c["chances"])
