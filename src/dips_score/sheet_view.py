"""What the Character sheet drawer shows, as plain data (no Qt), from live.sheet.sheet(): four tabs of grouped rows (Gear,
Stats, Abilities, Talents and Legacy). It is what the character carries, as the last /reload or logout saved it. A figure
is as measured in your own fights, or the game's, or an estimate, and its row says which; unknown reads "–"."""
from dataclasses import dataclass, field
from datetime import datetime

NA = "–"
HIDDEN = "hidden by the game"
NONE = "Your character sheet fills in after you /reload with the add-on from 0.21 or newer."
RESIST = ("holy", "fire", "nature", "frost", "shadow", "arcane")
QUALITY = {0: "poor", 1: "common", 2: "uncommon", 3: "rare", 4: "epic", 5: "legendary"}


@dataclass
class SheetRow:
    name: str
    value: str = NA
    note: str = ""              # what the figure rests on, or is made of
    flag: str = ""              # a plain fact worth a look: "not enchanted"
    quiet: bool = False         # muted: known and never cast
    estimate: bool = False


@dataclass
class SheetTab:
    title: str
    groups: list[tuple[str, list[SheetRow]]] = field(default_factory=list)


@dataclass
class SheetView:
    taken: str = ""             # "As of 24 Nov 19:09, your last /reload or logout."
    need: str = NONE            # shown instead of the tabs when there is no sheet
    tabs: list[SheetTab] = field(default_factory=list)


def _n(v, decimals=0) -> str:
    return f"{v:,.{decimals}f}"


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def _when(taken) -> str:
    if not taken:
        return ""
    d = datetime.fromtimestamp(taken)
    return f"As of {d.day} {d:%b %H:%M}, your last /reload or logout."


def _gear(s: dict, broken: int | None) -> SheetTab:
    rows = []
    for g in s["gear"]:
        kind = QUALITY.get(g["quality"], "")
        note = ", ".join(x for x in (kind, "enchanted" if g["enchant"] else "") if x)
        rows.append(SheetRow(g["label"], _n(g["level"]) if g["level"] else NA,
                             " · ".join(x for x in (g["name"] or "", note) if x), ", ".join(g["flags"])))
    groups = [("Equipped, with item level", rows)]
    if broken:
        groups.append(("Wear", [SheetRow("Broken at your last pull", str(broken), "repair it", "broken")]))
    return SheetTab("Gear", groups)


# (key, name, decimals, unit); a unit of "%" follows the number
PRIMARY = (("str", "Strength"), ("agi", "Agility"), ("sta", "Stamina"), ("int", "Intellect"), ("spi", "Spirit"))
ATTACK = (("ap", "Attack power", 0, ""), ("rap", "Ranged attack power", 0, ""), ("crit", "Critical hits", 1, "%"),
          ("hit", "Hit", 1, "%"), ("haste", "Haste", 1, "%"))
SPELL = (("spellpower", "Spell power", 0, ""), ("healing", "Healing power", 0, ""), ("spellcrit", "Spell critical hits", 1, "%"),
         ("spellhit", "Spell hit", 1, "%"), ("regen", "Mana per second, out of combat", 1, ""))
DEFENSE = (("armor", "Armor", 0, ""), ("dodge", "Dodge", 1, "%"), ("parry", "Parry", 1, "%"), ("block", "Block", 1, "%"))


def _stat(s: dict, key: str, name: str, decimals: int = 0, unit: str = "") -> SheetRow | None:
    got = s["stats"].get(key)
    if got is None:
        return None
    if got["value"] is None:
        return SheetRow(name, NA, HIDDEN)
    note = f"{_n(got['gear'])} from gear" if got["gear"] else ""
    return SheetRow(name, _n(got["value"], decimals) + unit, note)


def _rows(s: dict, specs) -> list[SheetRow]:
    return [r for spec in specs if (r := _stat(s, *spec))]


def _stats(s: dict) -> SheetTab:
    p = s["projections"]
    tab = SheetTab("Stats")
    tab.groups.append(("From your fights", _projections(p)))
    resist = [r for r in (_stat(s, f"res_{k}", k.title() + " resistance") for k in RESIST) if r and r.value not in ("0", NA)]
    for title, rows in (("Primary", _rows(s, PRIMARY)), ("Attack", _rows(s, ATTACK)), ("Spells", _rows(s, SPELL)),
                        ("Defense", _rows(s, DEFENSE) + _rows(s, (("health", "Health"), ("mana", "Mana")))),
                        ("Resistances", resist),
                        ("Professions", [SheetRow(k["name"], f"{k['level']:,}" + (f" of {k['max']:,}" if k["max"] else ""))
                                         for k in s["skills"]])):
        if rows:
            tab.groups.append((title, rows))
    return tab


def _projections(p: dict) -> list[SheetRow]:
    def measured(key, name, text, need, what="fight"):
        got = p[key]
        if got["value"] is None:
            return SheetRow(name, NA, need)
        how = {"measured": f"measured in {_plural(got['n'], what)}", "game": "the game's own figure"}[got["source"]]
        return SheetRow(name, text(got["value"]), how)
    swing = measured("swing", "Swing speed", lambda v: f"{_n(v, 2)} s", "needs 10 fights with swings")
    if p["swing"].get("game"):
        swing.note += f"; the game says {_n(p['swing']['game'], 2)} s"
    rows = [measured("dps", "Damage per second", lambda v: _n(v), "needs 10 fights with damage"),
            measured("hps", "Healing per second", lambda v: _n(v), "needs 5 fights where you healed"),
            swing]
    hit = p["hit"]
    row = measured("hit", "Average swing", lambda v: _n(v), "needs 10 swings", "hit")
    if hit["value"] is not None:
        row.note += ", crits included"
    if hit["value"] is not None and hit["game_low"] and hit["game_high"]:
        row.note += f"; the game says {_n(hit['game_low'])} to {_n(hit['game_high'])} before armor"
    rows.append(row)
    ap = p["ap10"]
    rows.append(SheetRow("10 attack power", NA, {"weapon": "needs your weapon's stats", "fit": "the classic formula doesn't fit the game's figures"}
                         [ap["why"]]) if ap["value"] is None else
                SheetRow("10 attack power", f"+{_n(ap['value'], 2)} per second",
                         "estimate from the classic formula, before armor", estimate=True))
    return rows


def _abilities(s: dict) -> SheetTab:
    used, idle = [], []
    for a in s["abilities"]:
        name = a["name"] + (f" ({a['rank'][0].lower() + a['rank'][1:]})" if a["rank"] else "")
        row = SheetRow(name, _n(a["casts"]) if a["casts"] else "", f"{a['share'] * 100:.1f}% of your damage" if a["share"] else "",
                       "a higher rank is known" if a["lower"] else "", quiet=not a["casts"])
        (used if a["casts"] else idle).append(row)
    tab = SheetTab("Abilities")
    for title, rows in (("Casts in fights, last 15 days", used), ("Known, not cast in a fight", sorted(idle, key=lambda r: r.name))):
        if rows:
            tab.groups.append((title, rows))
    return tab


def _points(s: dict) -> SheetTab:
    tab = SheetTab("Talents and Legacy")
    for kind, title in (("talent", "Talents"), ("legacy", "Legacy")):
        rows = [SheetRow(p["name"] or f"Node {p['node']}", f"{p['rank']}" + (f" of {p['max']}" if p["max"] else ""))
                for p in sorted((x for x in s["points"] if x["kind"] == kind), key=lambda x: (x["tree"] or 0, x["name"]))]
        trees = [t for t in s["trees"] if t["kind"] == kind]
        left = [t["left"] for t in trees if t["left"] is not None]
        if trees:
            with_points = sum(t["with"] or 0 for t in trees)
            of = sum(t["nodes"] or 0 for t in trees)
            note = f"in {_plural(len(trees), 'tree')}" + (f", {_plural(sum(left), 'point')} left to spend" if left else "")
            rows.insert(0, SheetRow("Points spent in", f"{with_points} of {of}", note))
        if rows:
            tab.groups.append((title, rows))
    return tab


def build_sheet(s: dict | None, broken: int | None = None) -> SheetView:
    if s is None:
        return SheetView()
    tabs = [t for t in (_gear(s, broken), _stats(s), _abilities(s), _points(s)) if any(rows for _, rows in t.groups)]
    return SheetView(_when(s["taken"]), "" if tabs else NONE, tabs)
