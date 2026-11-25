"""What the Character sheet drawer shows, as plain data (no Qt), from live.sheet.sheet(): Gear (the item level ladder, then
every piece), Stats (what your fights show, then what the game says, with how much gear gives), Abilities (casts and share
of damage, the idle ones in one line) and Talents and Legacy (points as pips). It is what the character carries, as the
last reading had it. A figure says whether it is measured in your own fights, the game's, or an estimate;
unknown reads "–". Inks are token names: an item's by its rarity, which its row also says in words."""
from dataclasses import dataclass, field
from datetime import datetime

NA = "–"
HIDDEN = "hidden by the game"
NONE = "Your character sheet fills in after you /reload with the add-on from 0.21 or newer."
RESIST = ("holy", "fire", "nature", "frost", "shadow", "arcane")
PARTLY = "Some items show only their basic stats until you /reload with add-on 0.5.2 or newer."
QUALITY = {0: ("poor", "mu"), 1: ("common", "tx"), 2: ("uncommon", "q-uncommon"), 3: ("rare", "q-rare"),
           4: ("epic", "q-epic"), 5: ("legendary", "q-legendary")}
ROLE_INK = {"damage": "role-dmg", "healer": "role-heal", "tank": "role-tank"}


@dataclass
class Item:
    slot: str                   # "Head"
    name: str                   # "Humbert's Helm", "empty"
    ink: str = "tx"             # its rarity's colour token
    rarity: str = ""            # "uncommon"
    level: str = NA             # "30"
    stats: str = ""             # "88 Armor, +9 Agility, +6 Stamina"
    text: list[str] = field(default_factory=list)       # what it does, a line each
    flags: list[str] = field(default_factory=list)      # "not enchanted", "lowest"
    empty: bool = False


@dataclass
class Ladder:
    """item levels on one line: lo to hi, the mean, and at each level the pieces that have it"""
    mean: str = NA
    verdict: str = ""           # "Average 31, six pieces rare, led by Shoulder at 38. Two slots are empty, and Legs is lowest at 21."
    lo: int = 0
    hi: int = 0
    at: float = 0.0             # the mean's place, 0..1
    marks: list[tuple[int, float, list[tuple[str, str]]]] = field(default_factory=list)    # (level, 0..1, [(slot, ink)])
    rarities: list[tuple[str, str, int]] = field(default_factory=list)      # (word, ink, pieces), best first


@dataclass
class Figure:
    name: str
    value: str = NA
    note: str = ""              # what it rests on
    bar: float | None = None    # 0..1 of the longest in its group
    gear: list[tuple[str, float]] = field(default_factory=list)     # its parts that gear gives: (rarity ink, 0..1 of the same length)
    buffs: float | None = None  # the part buffs and enchants give, like gear; None when it is not known apart
    estimate: bool = False


@dataclass
class Ability:
    name: str
    casts: str
    share: str = ""             # "14.0%", "" without damage of its own
    bar: float | None = None    # its share, 0..1 of all your damage
    flag: str = ""


@dataclass
class Talent:
    name: str
    rank: int
    of: int


@dataclass
class SheetView:
    taken: str = ""             # "As of 24 Nov 19:09, the add-on's last reading."
    need: str = NONE            # shown instead of the tabs when there is no sheet
    ink: str = "tx"             # the main role's, for the gear part of a bar
    ladder: Ladder | None = None
    gear: list[Item] = field(default_factory=list)
    wear: str = ""              # "2 pieces were broken at your last pull."
    stats: list[tuple[str, list[Figure]]] = field(default_factory=list)
    lead: str = ""              # "Judgement leads your abilities with 14.3% of your damage."
    abilities: list[Ability] = field(default_factory=list)
    idle: str = ""              # "Known, not cast in a fight: Concentration Aura, Devotion Aura."
    talents: list[Talent] = field(default_factory=list)
    talents_note: str = ""      # "12 of 51 talents have points."
    legacy: list[Talent] = field(default_factory=list)
    legacy_note: str = ""
    partly: str = ""            # said over the gear when an item is not shown whole


def _n(v, decimals=0) -> str:
    return f"{v:,.{decimals}f}"


def _trim(v) -> str:
    return f"{v:,.1f}".removesuffix(".0")


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def _when(taken) -> str:
    if not taken:
        return ""
    d = datetime.fromtimestamp(taken)
    return f"As of {d.day} {d:%b %H:%M}, the add-on's last reading."


def _item(g: dict) -> Item:
    flags = [f for f in g["flags"] if f != "empty"]
    if "empty" in g["flags"]:
        return Item(g["label"], "", "tx", level="", flags=["empty"], empty=True)
    rarity, ink = QUALITY.get(g["quality"], ("", "tx"))
    return Item(g["label"], g["name"] or "name not read yet", ink if g["name"] else "mu", rarity,
                _n(g["level"]) if g["level"] else NA, ", ".join(g["stats"]), list(g["text"]), flags)


NUMBERS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")


def _few(n: int) -> str:
    return NUMBERS[n] if n < len(NUMBERS) else str(n)


def _ladder(gear: list[dict]) -> Ladder | None:
    worn = [g for g in gear if g["level"]]
    if len(worn) < 2:
        return None
    levels = [g["level"] for g in worn]
    lo, hi, mean = min(levels), max(levels), sum(levels) / len(levels)
    place = lambda v: (v - lo) / (hi - lo) if hi > lo else .5  # noqa: E731
    named = lambda v: _and([g["label"] for g in worn if g["level"] == v])  # noqa: E731
    count = {q: sum(g["quality"] == q for g in worn) for q in sorted({g["quality"] for g in worn} - {None}, reverse=True)}
    proud = [f"{_few(n)} {'piece' if n == 1 else 'pieces'} {QUALITY[q][0]}" for q, n in count.items() if q >= 3 and q in QUALITY]
    empty = sum("empty" in g["flags"] for g in gear)
    best = f"Average {round(mean)}" + "".join(f", {x}" for x in proud) + (f", led by {named(hi)} at {hi}." if hi > lo else f", every piece at {hi}.")
    weak = f"{named(lo)} {'is' if levels.count(lo) == 1 else 'are'} lowest at {lo}"
    worst = (f" {_few(empty).capitalize()} {'slot is' if empty == 1 else 'slots are'} empty" + (f", and {weak}." if hi > lo else ".")) if empty \
        else f" {weak}." if hi > lo else ""
    marks: dict[int, list] = {}
    for g in worn:
        marks.setdefault(g["level"], []).append((g["label"], QUALITY.get(g["quality"], ("", ""))[1]))     # "": not read
    return Ladder(str(round(mean)), best + worst, lo, hi, place(mean), [(v, place(v), marks[v]) for v in sorted(marks)],
                  [(*QUALITY[q], n) for q, n in count.items() if q in QUALITY])


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


PRIMARY = (("str", "Strength"), ("agi", "Agility"), ("sta", "Stamina"), ("int", "Intellect"), ("spi", "Spirit"))
ATTACK = (("ap", "Attack power", 0, ""), ("rap", "Ranged attack power", 0, ""), ("crit", "Critical hits", 1, "%"),
          ("hit", "Hit", 1, "%"), ("haste", "Haste", 1, "%"))
SPELL = (("spellpower", "Spell power", 0, ""), ("healing", "Healing power", 0, ""), ("spellcrit", "Spell critical hits", 1, "%"),
         ("spellhit", "Spell hit", 1, "%"), ("regen", "Mana per second, out of combat", 1, ""))
DEFENSE = (("armor", "Armor", 0, ""), ("dodge", "Dodge", 1, "%"), ("parry", "Parry", 1, "%"), ("block", "Block", 1, "%"),
           ("health", "Health", 0, ""), ("mana", "Mana", 0, ""))


def _stat(s: dict, key: str, name: str, decimals: int = 0, unit: str = "") -> Figure | None:
    got = s["stats"].get(key)
    if got is None or got["value"] == 0:            # a class without it (ranged attack power) says nothing by a zero
        return None
    if got["value"] is None:
        return Figure(name, NA, HIDDEN)
    return Figure(name, _n(got["value"], decimals) + unit, f"{_trim(got['gear'])} from gear" if got["gear"] else "")


def _primary(s: dict) -> list[Figure]:
    """as bars on one scale, so the five compare; what gear and buffs give is drawn within, buffs only when all five are known"""
    there = [s["stats"][k] for k, _ in PRIMARY if k in s["stats"] and s["stats"][k]["value"]]
    split = bool(there) and all("own" in x for x in there)
    top = max((s["stats"][k]["value"] or 0 for k, _ in PRIMARY if k in s["stats"]), default=0)
    out = []
    for key, name in PRIMARY:
        f = _stat(s, key, name)
        if f and top and (v := s["stats"][key]["value"]):
            f.bar = v / top
            left = v
            for q, n in sorted(s["stats"][key]["by_quality"].items(), key=lambda x: -(x[0] or 0)):
                n = max(0, min(n, left))        # a set or a debuff can make the items' sum more than what is left of it
                left -= n
                f.gear.append((QUALITY.get(q, ("", ""))[1], n / top))
            if split:
                got = s["stats"][key]
                f.buffs = min(got["buffs"], left) / top
                f.note = f"{_trim(got['own'])} your own" + "".join(f", {_trim(got[k])} {words}" for k, words in (
                    ("gear", "from gear"), ("buffs", "from buffs, enchants and sets"), ("lost", "taken by debuffs")) if got[k])
        if f:
            out.append(f)
    return out


def _measured(p: dict) -> list[Figure]:
    def of(key, name, text, need, what="fight"):
        got = p[key]
        if got["value"] is None:
            return Figure(name, NA, need)
        how = {"measured": f"measured in {_plural(got['n'], what)}", "game": "the game's own figure"}[got["source"]]
        return Figure(name, text(got["value"]), how)
    swing = of("swing", "Swing speed", lambda v: f"{_n(v, 2)} s", "needs 10 fights with swings")
    if p["swing"].get("game"):
        swing.note += f"; the game says {_n(p['swing']['game'], 2)} s"
    hit, g = of("hit", "Average swing", lambda v: _n(v), "needs 10 swings", "hit"), p["hit"]
    if g["value"] is not None:
        hit.note += ", crits included"
        if g["game_low"] and g["game_high"]:
            hit.note += f"; the game says {_n(g['game_low'])} to {_n(g['game_high'])}, before the enemy's armor takes its part"
    out = [of("dps", "Damage per second", _n, "needs 10 fights with damage"),
           of("hps", "Healing per second", _n, "needs 5 fights where you healed"), swing, hit]
    return sorted(out, key=lambda f: f.value == NA)     # the known first


def _attack(s: dict) -> list[Figure]:
    rows = [f for spec in ATTACK if (f := _stat(s, *spec))]
    ap = s["projections"]["ap10"]
    for f in rows:
        if f.name == "Attack power" and ap["value"] is not None:
            f.note, f.estimate = f"10 more adds {_n(ap['value'], 2)} damage per second before armor, by the classic formula", True
    return rows


def _abilities(s: dict) -> tuple[str, list[Ability], str]:
    cast = [a for a in s["abilities"] if a["casts"]]
    used = [Ability(a["name"] + (f" ({a['rank'][0].lower() + a['rank'][1:]})" if a["rank"] else ""), _n(a["casts"]),
                    f"{a['share'] * 100:.1f}%" if a["share"] else "", a["share"] or None, "a higher rank is known" if a["lower"] else "")
            for a in cast]
    for key, name in (("auto", "Auto attack"), ("proc", "Procs and items")):     # the rest of it, so the shares add up
        if cast and (share := s["auto"].get(key)):
            used.append(Ability(name, "", f"{share * 100:.1f}%", share))
    idle = sorted(a["name"] for a in s["abilities"] if not a["casts"])
    top = max((a for a in cast if a["share"]), key=lambda a: a["share"], default=None)
    lead = f"{top['name']} leads your abilities with {top['share'] * 100:.1f}% of your damage." if top else ""
    return lead, used, f"Known, not cast in a fight: {', '.join(idle)}." if idle else ""


def _points(s: dict, kind: str) -> tuple[list[Talent], str]:
    rows = [Talent(p["name"] or f"Node {p['node']}", p["rank"], max(p["max"] or 0, p["rank"]))
            for p in sorted((x for x in s["points"] if x["kind"] == kind), key=lambda x: (-x["rank"], x["name"]))]
    trees = [t for t in s["trees"] if t["kind"] == kind]
    if not trees:
        return rows, ""
    left = sum(t["left"] or 0 for t in trees)
    of = sum(t["nodes"] or 0 for t in trees)
    word = "talents" if kind == "talent" else "Legacy choices"
    return rows, f"{sum(t['with'] or 0 for t in trees)} of {of} {word} have points" + (
        f", {_plural(left, 'point')} left to spend." if left else ".")


def build_sheet(s: dict | None, broken: int | None = None) -> SheetView:
    if s is None:
        return SheetView()
    v = SheetView(_when(s["taken"]), "", ROLE_INK.get(s["role"], "tx"), _ladder(s["gear"]), [_item(g) for g in s["gear"]])
    v.wear = f"{_plural(broken, 'piece')} broken at your last pull." if broken else ""
    v.partly = PARTLY if any(not g["whole"] for g in s["gear"]) else ""
    rows = lambda specs: [f for spec in specs if (f := _stat(s, *spec))]  # noqa: E731
    resist = rows([(f"res_{k}", f"{k.title()} resistance") for k in RESIST])
    skills = [Figure(k["name"], f"{k['level']:,}" + (f" of {k['max']:,}" if k["max"] else "")) for k in s["skills"]]
    v.stats = [(t, r) for t, r in (("From your fights", _measured(s["projections"])), ("Primary", _primary(s)), ("Attack", _attack(s)),
                                   ("Spells", rows(SPELL)), ("Defense", rows(DEFENSE)), ("Resistances", resist),
                                   ("Professions", skills)) if r]
    v.lead, v.abilities, v.idle = _abilities(s)
    v.talents, v.talents_note = _points(s, "talent")
    v.legacy, v.legacy_note = _points(s, "legacy")
    return v
