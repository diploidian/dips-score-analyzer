"""A character's title from its traits (traits.py), the line under it, its deeds, and the rows of How you fight. Pure data.

crest(win, fig, sc, cls, spec, types) -> {"title", "second", "deeds", "lead" (the title's trait, None when no trait
reaches tier 1), "epithet"}. rows(win, fig, sc) -> {key: row}, pack(win, fig, rows, sc, lead) -> the keys shown.
"""
from __future__ import annotations

from collections import Counter
from statistics import median

from . import traits
from .traits import BY_KEY

MIXED = 0.60                # the main role under this share of fight time: mixed roles
NOUNS = {                   # class -> talent tree -> noun
    "WARRIOR": {"Arms": "Warblade", "Fury": "Reaver", "Protection": "Ironwall"},
    "PALADIN": {"Holy": "Lightmender", "Protection": "Shieldsworn", "Retribution": "Crusader"},
    "HUNTER": {"Beast Mastery": "Packleader", "Marksmanship": "Deadeye", "Survival": "Trailstalker"},
    "ROGUE": {"Assassination": "Nightblade", "Combat": "Swashblade", "Subtlety": "Shadowstep"},
    "PRIEST": {"Discipline": "Oathkeeper", "Holy": "Dawnkeeper", "Shadow": "Duskcaller"},
    "SHAMAN": {"Elemental": "Stormcaller", "Enhancement": "Thunderfist", "Restoration": "Tidemender"},
    "MAGE": {"Arcane": "Spellweaver", "Fire": "Emberwright", "Frost": "Rimecaller"},
    "WARLOCK": {"Affliction": "Hexbinder", "Demonology": "Pactkeeper", "Destruction": "Cinderlord"},
    "DRUID": {"Balance": "Starcaller", "Feral": "Wildfang", "Feral Combat": "Wildfang", "Restoration": "Grovekeeper"},
}
FERAL_TANK = "Thornhide"
ROLE_NOUN = {               # spec unknown: class -> role -> noun
    "WARRIOR": {"damage": "Warblade", "tank": "Ironwall"},
    "PALADIN": {"damage": "Crusader", "healer": "Lightmender", "tank": "Shieldsworn"},
    "HUNTER": {"damage": "Deadeye"}, "ROGUE": {"damage": "Nightblade"},
    "PRIEST": {"damage": "Duskcaller", "healer": "Dawnkeeper"},
    "SHAMAN": {"damage": "Stormcaller", "healer": "Tidemender"},
    "MAGE": {"damage": "Spellweaver"}, "WARLOCK": {"damage": "Hexbinder"},
    "DRUID": {"damage": "Starcaller", "healer": "Grovekeeper", "tank": FERAL_TANK},
}
PLAIN = {"damage": "Slayer", "healer": "Mender", "tank": "Bulwark"}
CHAMPION = "Champion"

BANE = {"Undead": "the Undead", "Beast": "Beasts", "Demon": "Demons", "Dragonkin": "Dragonkin",
        "Elemental": "Elementals", "Giant": "Giants"}
BANE_MIN = 0.40             # one type's share of the foes with a known type
BANE_KNOWN = 0.50           # of the foes must have one
NEMESIS_MIN = 0.15
NEMESIS_KILLS = 30
# first words (or two) of enemy names that are a people or an order, and how it is called. Only these: the
# first word may as well be a place or a look ("Highland Strider", "Young Wolf")
PEOPLES = {w: w for w in (
    "Amani Atal'ai Blackrock Bloodsail Bloodscalp Boulderfist Bristleback Crushridge Daggerspine Darkspear Deadwood "
    "Defias Dragonmaw Drywhisker Dunemaul Dustbelcher Fallenroot Felmusk Foulweald Frostmane Galak Gelkis Gordok Gordunni Grimtotem "
    "Hakkari Haldarr Kolkar Kurzen Magram Maraudine Mirefin Mosh'Ogg Mosshide Palemane Razorfen Riverpaw Sandfury Saltscale "
    "Shadowforge Skullsplitter Smolderthorn Spitelash Stonesplinter Syndicate Thistlefur Timbermaw Vilebranch Wastewander "
    "Windshear Winterfall Witherbark Wrathtail").split()} | {
    "Dark Iron": "Dark Iron", "Scarlet": "Scarlet Crusade", "Twilight": "Twilight's Hammer", "Venture": "Venture Company"}
ZONE_MIN = 0.25
THE = {"Arathi Highlands", "Alterac Mountains", "Hillsbrad Foothills", "Badlands", "Barrens", "Blasted Lands",
       "Burning Steppes", "Deadmines", "Eastern Plaguelands", "Western Plaguelands", "Hinterlands", "Redridge Mountains",
       "Scarlet Monastery", "Searing Gorge", "Stockade", "Stockades", "Stonetalon Mountains", "Swamp of Sorrows",
       "Temple of Atal'Hakkar", "Wailing Caverns", "Wetlands", "Riverglades"}
PLACE_MIN = 0.50
PLACE_OF = {"World": "the Wilds", "Dungeon": "the Depths", "Raid": "the Great Halls", "PvP": "the Battlefield"}

DEED_MIN = 0.10             # how good a feat must be, 0..1 between its anchors below
PVP_PACK = 0.25             # this share of fights against players: the PvP rows
PACKS = {
    "damage": ("Tempo", "Edge", "Crowd", "split", "Edgewise", "cut"),
    "healer": ("overheal", "heal_share", "Lifeline", "dispels", "cut"),
    "tank": ("Wall", "taken", "pull", "lowest", "Break"),
    "pvp": ("War", "broken_off", "length", "Edge", "pvp_deaths"),
}
PACK_SIZE = 5
NUMBERS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")


def noun(cls: str | None, spec: str | None, role: str | None, share: float | None) -> str:
    """the class noun: by talent tree, then the main role (mixed roles: Champion), then plain"""
    cls = (cls or "").upper()
    if tree := NOUNS.get(cls, {}).get(spec):
        return FERAL_TANK if tree == "Wildfang" and role == "tank" else tree
    if role is None or (share or 0) < MIXED:
        return CHAMPION
    return ROLE_NOUN.get(cls, {}).get(role) or PLAIN[role]


def _bane(win: list[dict], types: dict | None) -> str | None:
    seen = Counter()
    for f in win:
        if f.get("kind") != "PvP":
            for name, n in traits.foes(f):
                seen[(types or {}).get(name)] += n
    known = seen.total() - seen[None]
    if not known or known / seen.total() < BANE_KNOWN:
        return None
    best = max(BANE, key=lambda t: seen[t])
    return f"Bane of {BANE[best]}" if seen[best] / known >= BANE_MIN else None


def _nemesis(win: list[dict]) -> str | None:
    fallen = traits.beaten(win)
    words, names = Counter(), Counter()
    for name, n in fallen.items():
        two = name.split(" ")[:2]
        word = " ".join(two) if " ".join(two) in PEOPLES else two[0]
        words[word] += n
        names[word] += 1
    for word, n in sorted(words.items(), key=lambda w: (-w[1], w[0])):
        if word in PEOPLES and names[word] >= 2 and n >= NEMESIS_KILLS and n / fallen.total() >= NEMESIS_MIN:
            return f"Scourge of the {PEOPLES[word]}"
    return None


def _zone(win: list[dict]) -> str | None:
    zones = Counter(z for f in win if (z := f.get("zone") or "") not in traits.NO_ZONE)
    if not zones:
        return None
    z, n = min(zones.items(), key=lambda c: (-c[1], c[0]))
    if n / len(win) < ZONE_MIN:
        return None
    if z.startswith("The "):
        return "the " + z[4:]
    return f"the {z}" if z in THE else z


def where(win: list[dict], fig: dict, sc: dict, types: dict | None) -> tuple[str, bool] | None:
    """the last part of the title, and whether it stands alone ("Bane of Beasts"), not after "of"; None: nothing known"""
    if who := _bane(win, types) or _nemesis(win):
        return who, True
    if z := _zone(win):
        return z, False
    places = fig.get("places") or {}
    top = max(places, key=lambda p: places[p] or 0, default=None)
    if top and (places[top] or 0) >= PLACE_MIN:
        return PLACE_OF[top], False
    if top and any(places.values()) and sc.get("Travel") and sc["Travel"]["tier"] >= 2:
        return "the Long Road", False
    return None


def deeds(win: list[dict], fig: dict) -> list[str]:
    """up to two feats of the window, best first; a fight with a group or with help says so, one that may have had help
    (saved before that was known) is not called alone"""
    out: list[tuple[float, str]] = []

    def add(v, low, high, text):
        out.append(((v - low) / (high - low), text))

    def foe(f, word="against "):
        t = f.get("target")
        return f" {word}{t}" if t and t != "?" else ""

    def company(f):
        size = (f.get("group") or {}).get("size")
        return f", in a group of {size}" if size else ", with help" if f.get("helped") else \
            ", alone" if "helped" in f else ", without a group"

    wins = [f for f in win if f.get("result") == "killed" and "group" in f]      # alone or not must be known
    known = [f for f in wins if f.get("lowest_hp") is not None and f["lowest_hp"] > 0.005]   # up to it reads "0%"
    if known:
        f = min(known, key=lambda f: f["lowest_hp"])
        add(f["lowest_hp"], .20, .01, f"won after dropping to {f['lowest_hp'] * 100:.0f}% health{foe(f)}"
            + (company(f) if f["group"] or f.get("helped") else ""))
    each = lambda f: traits.foe_count(f) / ((f["group"] or {}).get("size") or 1)  # noqa: E731
    own = [f for f in wins if f["group"] or not f.get("helped")]
    if own and (n := traits.foe_count(f := max(own, key=each))) >= 4:
        many = NUMBERS[n] if n < len(NUMBERS) else str(n)
        add(each(f), 3, 10, f"beat {many} in one fight{company(f)}" + (f", {foe(f, '').strip()} among them"
                                                                             if foe(f) else ""))
    if run := traits.streak(win):
        p = BY_KEY["Streak"].parts[0]
        add(run, p.low, p.high, f"{run} fights in a row survived")
    bosses = [f for f in wins if f.get("kind") == "Boss"]
    if len(bosses) >= 3:
        add(len(bosses), 3, 25, f"{len(bosses)} bosses beaten" + (" with a group" if any(f.get("group") for f in bosses)
                                                                 else ""))
    best = max((f for f in traits._damage_fights(win) if f.get("dps") and (f.get("duration") or 0) >= 10),
               key=lambda f: f["dps"], default=None)
    if best:        # no anchor fits every level: it fills in when little else stands out
        out.append((DEED_MIN, f"{best['dps']:,.0f} damage per second{foe(best)}"))
    pvp = [f for f in wins if f.get("kind") == "PvP"]
    if len(pvp) >= 3:
        solo = [f for f in pvp if not f["group"]]
        alone = sum("helped" in f and not f["helped"] for f in solo)
        add(len(pvp), 2, 25, f"{len(pvp)} fights won against players" + (
            f", {alone} of them alone" if alone else f", {len(solo)} of them without a group" if solo else " in a group"))
    levels = [f["level"] for f in win if f.get("level")]
    if levels and (up := max(levels) - min(levels)):
        add(up, 0, 10, f"gained {up} level{'' if up == 1 else 's'}")
    if sits := traits.sittings(win):
        add(max(sits), 40, 200, f"{max(sits)} fights in one sitting")
    return [text for v, text in sorted(out, key=lambda d: -min(1, d[0])) if v >= DEED_MIN][:2]


def crest(win: list[dict], fig: dict, sc: dict, cls: str | None, spec: str | None, types: dict | None) -> dict:
    special = traits.named(sc)
    picked = traits.pick(sc, 3, special[1] if special else None)
    lead = picked[0] if picked else None
    role = fig.get("main_role")
    base = noun(cls, spec, role, (fig.get("roles") or {}).get(role))
    eps = traits.epithet(sc, lead) if lead else None
    if w := where(win, fig, sc, types):
        base += f", {w[0]}" if w[1] else f" of {w[0]}"
    title = f"{special[0]}, {base}" if special else f"{eps} {base}" if eps else base
    second = ", ".join(BY_KEY[k].words for k in picked[1:3])
    return {"title": title, "second": second[:1].upper() + second[1:] + "." if second else "", "deeds": deeds(win, fig),
            "lead": lead, "epithet": eps}


def rows(win: list[dict], fig: dict, sc: dict) -> dict[str, dict]:
    """every row How you fight can show: {"name", "kind", "figure", "unit" (after the figure), "note", "share" (a share:
    it gets a bar, and a chip against Before)}; a row that cannot be known is left out"""
    out: dict[str, dict] = {}

    def row(key, name, kind, figure, note, unit=""):
        if figure is not None:
            out[key] = {"name": name, "kind": kind, "figure": figure, "unit": unit, "note": note, "share": kind == "%"}

    for k, s in sc.items():
        if s:
            row(k, BY_KEY[k].name, s["kind"], s["figure"], s["caption"])
    t, h, over = fig.get("temperament") or {}, fig.get("hands") or {}, fig.get("overheal")
    split = traits.damage_split(win) if fig.get("main_role") != "healer" else None
    if split:
        row("split", "Auto attack or abilities", "%", split["melee"] + split["shot"],
            f"{split['ability'] * 100:.0f}% abilities, {split['proc'] * 100:.0f}% procs and items", "auto attack")
    if h.get("cut_share") is not None:
        row("cut", "Cut short by moving", "%", h["cut_share"],
            f"{h['move_interrupts']:,} of {h['move_casts']:,} casts, in recorded runs")
    if over:
        row("overheal", "Overheal", "%", over["overheal"] / (over["healing"] + over["overheal"]),
            "of your healing cast on full health")
    share, shared = traits.heal_share(win)
    if shared >= 5:
        row("heal_share", "Group healing", "%", share, f"of the group's healing on others is yours, in {shared} fights")
    if helped := traits.helpful(win):
        n = sum(f["dispels_others"] for f in helped)
        row("dispels", "Dispels", "n1", 100 * n / len(helped), f"on others per 100 group fights, {n} in all")
    won = [f for f in win if f.get("result") == "killed" and f.get("taken") is not None and f.get("duration")]
    if won:
        row("taken", "Damage taken", "n", sum(f["taken"] for f in won) / sum(f["duration"] for f in won),
            "a second, in the fights you won")
    row("pull", "Usual pull", "n", t.get("median_pull"), "kinds of enemy in a fight")
    row("lowest", "Average lowest health", "%", t.get("lowest_hp"), "the lowest you dropped in a fight")
    pvp = [f for f in win if f.get("kind") == "PvP"]
    if pvp:
        of = lambda r: sum(f.get("result") == r for f in pvp) / len(pvp)  # noqa: E731
        row("broken_off", "Broken off", "%", of("they got away"), "of player fights end with an enemy standing and you alive")
        row("pvp_deaths", "Deaths", "%", of("you died"), "of player fights end with you dead")
        if lengths := [f["duration"] for f in pvp if f.get("duration") is not None]:
            row("length", "Fight length", "s", median(lengths), "is your usual fight against players")
    return out


def pack(win: list[dict], fig: dict, known: dict[str, dict], sc: dict, lead: str | None) -> list[str]:
    """the keys of How you fight's rows: the title's own, then the role's (or PvP's) that are known, then other traits"""
    pvp = sum(f.get("kind") == "PvP" for f in win)
    rule = PACKS["pvp" if win and pvp / len(win) >= PVP_PACK else fig.get("main_role") or "damage"]
    # rows of one figure, said once
    same = {"Blade": "split", "Shot": "split", "Craft": "split", "Thrift": "overheal", "Planted": "cut", "Bond": "Lone",
            "Mercy": "dispels"}
    if sc.get("Guard") and sc["Guard"]["kind"] == "%":
        same["Guard"] = "lowest"
    rest = sorted((k for k, s in sc.items() if s), key=lambda k: -sc[k]["score"])
    out: dict[str, str] = {}
    for k in [lead] + list(rule) + rest:
        if k in known:
            out.setdefault(same.get(k, k), k)
    return list(out.values())[:PACK_SIZE]
