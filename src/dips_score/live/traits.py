"""How a character plays, as traits: one table (TRAITS), each trait a figure of one window's fights, scored 0..1 between
its low and high anchor, with a tier (0 to 3, from TIERS) and an epithet per tier. Pure data.

scores(win, fig, book) -> {key: None (unknown: too small a sample, no data, or not this role's trait) or {"figure",
"kind" (how it is written, see shown), "score", "tier", "caption", "n" (the figure's sample), "parts" ([kind, figure] of every known figure),
"names" (Range, Focus and Scourge: [[name, share of it], ...]), "next": None at the top tier, else {"epithet",
"needs": [(kind, figure), ...]} for the next tier}}. win: the window's fights; fig: its profile.figures so far
(main_role, efficiency, judged, temperament, hands, overheal); book: the spell book. pick() the traits that name a
character; named() the two-trait title.

What the figures count, where the saved fields need care:
  result     "killed": every enemy of the fight died and you lived. "they got away" is all the rest you lived through,
             an enemy you ran past included, so Hound leaves out fights you did no damage in (unless a group fought)
  foes       every enemy of one whole combat, the next ones that joined it included: never "at once". With a group they
             are the group's, so Crowd counts fights alone (a tank's too: there they are on you)
  group      None also when nobody else did anything in the fight
  helped     others than your group did some of the damage, or players outside it healed you; a fight without it counts
             as alone by its group (see alone)
  abilities  a row with no casts is a proc or item, unless a longer name of a cast spell ("Judgement of Command" belongs
             to Judgement); pet rows end with " (pet)"
  pull.own   the buffs you cast on yourself that the log has seen go up; one kept through a login is not in it
  since_last seconds since the fight before, None for a log's first; a gap of SESSION_GAP or more is a new sitting
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median

from .habits import SESSION_GAP, _damage_fights

TIERS = (0.35, 0.60, 0.85)          # the score each tier begins at
LOW = 0.35                          # health share under which a won fight was on the edge
BRINK = 0.10
WORTH = 0.05                        # of your ability damage, an ability is a main one
USUAL_BUFF = 0.60                   # a buff up at this share of pulls is a usual one
CAST_TIME = 0.50                    # of your casts must have a cast time before Planted says anything
AUTOS = ("Auto Shot", "Shoot")      # the shots fired by themselves; "Melee" is the same for a swing
NO_ZONE = ("", "UNKNOWN AREA")
FIGHTERS = ("damage", "tank")
ALL = ("damage", "healer", "tank")


@dataclass(frozen=True)
class Part:
    low: float
    high: float
    minimum: int                    # sample needed
    kind: str                       # see shown()
    caption: str                    # what the figure is, after it


@dataclass(frozen=True)
class Trait:
    key: str
    family: str
    name: str                       # its row's name
    parts: tuple[Part, ...]
    epithets: tuple[str, str, str]
    words: str                      # for the second line
    roles: tuple[str, ...] = ALL
    weaker: bool = True             # of two parts the weaker scores (and all must be known), else the better known one


def _t(key, family, name, low, high, minimum, kind, caption, epithets, words, roles=ALL) -> Trait:
    return Trait(key, family, name, (Part(low, high, minimum, kind, caption),), tuple(epithets.split(", ")), words, roles)


# role-only traits first: on a tie the earlier row wins
TRAITS: tuple[Trait, ...] = (
    _t("Thrift", "Healing", "Overheal", .45, .10, 20, "%", "of your healing cast on full health",
       "Sparing, Measured, Unwasting", "wastes little healing", ("healer",)),
    _t("Lifeline", "Healing", "Fights nobody died", .70, .98, 20, "%", "of group fights with nobody dead",
       "Reassuring, Faithful, Saving", "keeps the group alive", ("healer",)),
    _t("Wall", "Tanking", "Hits avoided", .10, .35, 200, "%", "of swings at you missed, dodged, parried or blocked",
       "Braced, Immovable, Impregnable", "turns blows aside", ("tank",)),

    _t("Tempo", "Pace", "Time between fights", 120, 15, 30, "s", "between one fight and the next",
       "Steady, Tireless, Relentless", "fights without pause"),
    _t("Swift", "Pace", "Wins under 15 seconds", .10, .45, 30, "%", "of your wins took under 15 seconds",
       "Quick, Swift, Lightning", "ends fights in seconds"),
    _t("Endure", "Pace", "Fight length", 45, 120, 30, "s", "is your usual fight",
       "Patient, Enduring, Everlasting", "wears enemies down"),
    _t("Marathon", "Pace", "Longest sitting", 40, 200, 30, "n", "fights in your longest sitting",
       "Dogged, Unresting, Unwearied", "plays long sittings"),
    _t("Streak", "Pace", "Longest run without a death", 15, 200, 30, "n", "fights in a row survived",
       "Surviving, Unfallen, Deathless", "survives fight after fight"),

    _t("Edge", "Nerve", "Wins on the edge", .05, .25, 30, "%", "of your wins came after dropping under 35% health",
       "Daring, Fearless, Unyielding", "wins on the edge"),
    _t("Brink", "Nerve", "Wins under 10% health", .2, 1.7, 100, "n1", "wins under 10% health per 100 wins",
       "Lucky, Defiant, Death-Cheating", "comes back from the brink"),
    Trait("Guard", "Nerve", "Deaths and lowest health", (
        Part(8, 0, 30, "n1", "deaths per 100 fights"), Part(.50, .85, 30, "%", "is your average lowest health")),
        ("Guarded", "Unbroken", "Untouchable"), "stays out of danger"),
    _t("Wary", "Nerve", "Close calls answered", .30, .90, 10, "%", "of close calls answered with a defensive",
       "Wary, Cool-Headed, Unshaken", "answers danger"),
    _t("Crowd", "Nerve", "Wins against three or more", .08, .40, 30, "%", "of your wins alone were against three or more",
       "Bold, Overrunning, Unstoppable", "takes on crowds"),
    _t("Duel", "Nerve", "Wins one on one", .70, .97, 20, "%", "of fights one on one won",
       "Sure, Deadly, Peerless", "wins one on one"),

    _t("Finish", "Victory", "Fights won", .70, .97, 30, "%", "of your fights end with the kill",
       "Proven, Victorious, Conquering", "finishes the kill"),
    _t("Hound", "Victory", "Nobody got away", .80, .99, 30, "%", "of fights end with nobody getting away",
       "Dogging, Hunting, Inescapable", "lets few get away"),
    _t("Boss", "Victory", "Boss kills", 3, 25, 10, "n", "bosses beaten",
       "Giant-Felling, Throne-Toppling, Mountain-Breaking", "brings down bosses"),
    _t("War", "Victory", "Player fights won", .35, .75, 10, "%", "of fights against players won",
       "Feared, Dreaded, Warlike", "wins against players"),
    _t("Scourge", "Victory", "Most beaten enemy", .08, .30, 30, "%", "of the enemies you beat are of one kind",
       "Vengeful, Merciless, Exterminating", "hunts one enemy above all"),

    _t("Blade", "Weapon", "Melee share", .30, .65, 30, "%", "of your damage is your weapon's own swing",
       "Iron, Steel, Blade-Sworn", "leans on weapon swings", FIGHTERS),
    _t("Shot", "Weapon", "Auto shot share", .25, .60, 30, "%", "of your damage is automatic shots",
       "Keen, Far-Sighted, True-Shot", "leans on automatic shots", FIGHTERS),
    _t("Craft", "Weapon", "Ability share", .60, .95, 30, "%", "of your damage is your abilities",
       "Gifted, Fierce, Spellforged", "leans on abilities", FIGHTERS),
    _t("Focus", "Weapon", "Top ability's share", .35, .75, 30, "%", "of your ability damage is one ability",
       "Devoted, Single-Minded, Masterful", "leans on one ability", FIGHTERS),
    _t("Range", "Weapon", "Main damage abilities", 2, 8, 30, "n", "abilities with 5% or more of your ability damage",
       "Adaptable, Cunning, Many-Handed", "draws on many abilities", FIGHTERS),
    _t("Crit", "Weapon", "Critical hits", .08, .30, 500, "%", "of your hits crit",
       "Fortunate, Savage, Fatebound", "crits often", FIGHTERS),
    _t("Proc", "Weapon", "Proc and item share", .08, .30, 30, "%", "of your damage is procs and items",
       "Charged, Crackling, Storm-Touched", "strikes with procs and items", FIGHTERS),

    _t("Edgewise", "Craft of play", "Possible damage reached", .75, .95, 30, "%", "of possible damage reached",
       "Honed, Precise, Flawless", "reaches most of its damage", FIGHTERS),
    _t("Ready", "Craft of play", "Cooldowns used", .50, .90, 50, "%", "of possible cooldowns used",
       "Prompt, Eager, Unsparing", "uses cooldowns as they come", FIGHTERS),
    _t("Planted", "Craft of play", "Casts not cut short", .97, 1, 200, "%", "of casts not cut short by moving",
       "Grounded, Unmoved, Rooted", "stands still to cast"),
    _t("Primed", "Craft of play", "Pulled with your usual buffs", .70, .98, 30, "%", "of fights pulled with your usual buffs",
       "Ready-Armed, Blessed, Oathbound", "pulls with its usual buffs"),
    _t("Break", "Craft of play", "Interrupts", 5, 40, 20, "n1", "interrupts per 100 group fights",
       "Watchful, Silencing, Spellbreaking", "interrupts often"),

    _t("Lone", "Company", "Fights alone", .55, .97, 30, "%", "of your fights are alone",
       "Wandering, Lone, Sovereign", "fights alone"),
    _t("Bond", "Company", "Fights in a group", .50, .97, 30, "%", "of fights in a group",
       "Loyal, Stalwart, Sworn", "fights in a group"),
    _t("Lead", "Company", "Groupmates out-damaged", .30, .90, 20, "%", "of your groupmates out-damaged, on average",
       "Rising, Leading, Commanding", "out-damages the group", FIGHTERS),
    Trait("Mercy", "Company", "Help for the group", (
        Part(3, 25, 30, "n1", "dispels on others per 100 group fights"),
        Part(.10, .35, 20, "%", "of the group's healing on others is yours")),
        ("Merciful", "Guarding", "Selfless"), "looks after others", weaker=False),
    _t("Benefactor", "Company", "Benefactor", 5, 75, 5, "n", "strangers buffed, healed or cleansed",
       "Kind, Generous, Great-Hearted", "helps strangers on the road"),
    _t("Lifegiver", "Company", "Lifegiver", 2, 25, 3, "n", "revives cast",
       "Rousing, Rekindling, Life-Giving", "raises the fallen"),

    _t("Travel", "Road", "Zones fought in", 5, 22, 30, "n", "zones with five fights or more",
       "Roaming, Far-Travelled, Worldly", "fights all over the map"),
    _t("Menagerie", "Road", "Different enemies beaten", 80, 500, 30, "n", "different enemies beaten",
       "Curious, Seasoned, All-Seeing", "beats enemies of every kind"),
)
BY_KEY = {t.key: t for t in TRAITS}

# both at tier 2 or better; the first that applies
NAMED: tuple[tuple[str, str, str], ...] = (
    ("Edge", "Crowd", "the Cornered Lion"), ("Edge", "Streak", "the One Who Walks Away"),
    ("Lifegiver", "Benefactor", "the Open Heart"), ("Lifegiver", "Mercy", "the Second Dawn"),
    ("Lifegiver", "Bond", "the Last Hope"), ("Benefactor", "Travel", "the Wayside Saint"), ("Benefactor", "Lone", "the Stranger's Friend"),
    ("Guard", "Streak", "the Unfelled"), ("Brink", "Lone", "the Last One Standing"), ("Lone", "Tempo", "the Lone Storm"),
    ("Lone", "Travel", "the Long Walker"), ("Tempo", "Finish", "the Reaping Wind"), ("Swift", "Crit", "the Sudden End"),
    ("Blade", "Endure", "the Grinding Wheel"), ("Blade", "Duel", "the First Blade"),
    ("Crowd", "Proc", "the Gathering Thunder"), ("Hound", "Scourge", "the Old Grudge"),
    ("Boss", "Lead", "the Crownbreaker"), ("War", "Edge", "the Nerveless"), ("War", "Duel", "the Arena's Answer"),
    ("Focus", "Edgewise", "the Perfectionist"), ("Range", "Ready", "the Full Quiver"),
    ("Travel", "Menagerie", "the Walking Atlas"), ("Bond", "Mercy", "the Open Hand"), ("Break", "Wary", "the Cold Eye"),
    ("Lifeline", "Thrift", "the Quiet Miracle"), ("Lifeline", "Bond", "the Reason They Lived"),
    ("Wall", "Guard", "the Door That Holds"), ("Crowd", "Wall", "the Breakwater"),
)


def shown(kind: str, v: float, fine: bool = False) -> tuple[str, str]:
    """a figure as text and its unit: "%" a share, "s" seconds, "n" a count, "n1" a rate; fine: one decimal more"""
    scaled = v * 100 if kind == "%" else v
    return f"{scaled:,.{(kind == 'n1') + fine}f}", {"%": "%", "s": "s"}.get(kind, "")


def written(value: str, unit: str) -> str:
    """a figure with its unit: 86%, 25 s, 47% auto attack"""
    return f"{value}{unit}" if unit[:1] in ("", "%") else f"{value} {unit}"


def foes(f: dict) -> list:
    return f.get("foes") or []


def foe_count(f: dict) -> int:
    return sum(c for _, c in foes(f))


def beaten(win: list[dict]) -> Counter:
    """enemy name -> how many fell in the fights won, players' fights left out (their names are people)"""
    out: Counter = Counter()
    for f in win:
        if f.get("result") == "killed" and f.get("kind") != "PvP":
            for name, n in foes(f):
                out[name] += n
    return out


def sittings(win: list[dict]) -> list[int]:
    """fights in each sitting, oldest first: SESSION_GAP or more between two fights starts another"""
    out, end = [], None
    for f in sorted(win, key=lambda f: f["start"]):
        start = datetime.fromisoformat(f["start"])
        if end is None or (start - end).total_seconds() >= SESSION_GAP:
            out.append(0)
        out[-1] += 1
        end = datetime.fromisoformat(f["end"]) if f.get("end") else start + timedelta(seconds=f.get("duration") or 0)
    return out


def streak(win: list[dict]) -> int:
    best = run = 0
    for f in win:
        run = 0 if f.get("result") == "you died" else run + 1
        best = max(best, run)
    return best


def abilities(win: list[dict], main=lambda f: True) -> dict:
    """the fights' ability rows added up in one scan: {"all", "main" (the fights main() picks)} -> {name: [casts, hits, crits,
    damage, swings (Melee's, of the fights that saved a count)]}, "split" (damage_split)"""
    damaging = {id(f) for f in _damage_fights(win)}
    by: dict[tuple[bool, bool], dict[str, list]] = {}
    for f in win:
        rows = by.setdefault((id(f) in damaging, bool(main(f))), {})
        for a in f.get("abilities") or []:
            r = rows.get(n := a["name"])
            if r is None:
                r = rows[n] = [0, 0, 0, 0, 0]
            r[0] += a.get("casts") or 0
            r[1] += a.get("hits") or 0
            r[2] += a.get("crits") or 0
            r[3] += a.get("damage") or 0
            if n == "Melee":
                r[4] += (f.get("auto") or {}).get("swings") or 0

    def added(picked) -> dict[str, list]:
        out: dict[str, list] = {}
        for k, rows in by.items():
            if picked(*k):
                for n, r in rows.items():
                    out[n] = [x + y for x, y in zip(out[n], r)] if n in out else r
        return out

    return {"all": added(lambda dmg, main: True), "main": added(lambda dmg, main: main),
            "split": damage_split(added(lambda dmg, main: dmg), len(damaging))}


def damage_split(rows: dict[str, list], fights: int) -> dict | None:
    """{"melee", "shot", "ability", "proc" (shares of all damage), "top" (of ability damage), "worth" (abilities of 5%
    of it or more), "names" ([[ability, share of it], ...], biggest first), "fights"} of the ability rows of the fights that did damage; None without any"""
    casts, damage = Counter({n: r[0] for n, r in rows.items()}), Counter({n: r[3] for n, r in rows.items()})
    total = damage.total()
    if not total:
        return None
    cast = {n for n, c in casts.items() if c and n != "Melee" and n not in AUTOS}
    ability, proc = Counter(), 0
    for n, d in damage.items():
        if n == "Melee" or n in AUTOS or n.endswith(" (pet)"):
            continue
        owner = n if n in cast else max((c for c in cast if n.startswith(c + " ")), key=len, default=None)
        if owner:
            ability[owner] += d
        else:
            proc += d
    used = sum(ability.values())
    return {"melee": damage["Melee"] / total, "shot": sum(damage[n] for n in AUTOS) / total, "ability": used / total,
            "proc": proc / total, "top": max(ability.values()) / used if used else None,
            "worth": sum(d >= WORTH * used for d in ability.values() if d),
            "names": [[n, d / used] for n, d in ability.most_common() if d], "fights": fights}


def alone(f: dict) -> bool:
    """without a group, and not known to have been helped"""
    return "group" in f and not f["group"] and not f.get("helped")


def helpful(win: list[dict]) -> list[dict]:
    """the group fights that tell help for others from help for yourself"""
    return [f for f in win if f.get("group") and f.get("healing_others") is not None
            and f.get("dispels_others") is not None]


def outdamaged(f: dict) -> float | None:
    """the share of your groupmates with less damage than you, those who mostly healed left out; None without any, or
    when you did none"""
    peers = [d for m in f["group"].get("members") or [] if (d := m.get("damage") or 0) > (m.get("healing") or 0)]
    mine = f.get("damage")
    return sum(d < mine for d in peers) / len(peers) if peers and mine else None


def heal_share(win: list[dict]) -> tuple[float | None, int]:
    """your part of the healing your group gave each other (helpful fights), and how many had any"""
    own = total = n = 0
    for f in helpful(win):
        whole = sum(m.get("healing_others") or 0 for m in f["group"].get("members") or []) + f["healing_others"]
        if whole:
            own, total, n = own + f["healing_others"], total + whole, n + 1
    return (own / total if total else None), n


def _cast_time(rows: dict[str, list], book: dict) -> float | None:
    """the share of your casts that are spells with a cast time"""
    total = sum(r[0] for r in rows.values())
    return sum(r[0] for n, r in rows.items() if (book.get(n) or {}).get("cast")) / total if total else None


def _primed(win: list[dict]) -> tuple[float | None, int]:
    own = [set(f["pull"]["own"]) for f in win if (f.get("pull") or {}).get("own") is not None]
    seen = Counter(b for o in own for b in o)
    usual = {b for b, c in seen.items() if c / len(own) >= USUAL_BUFF}
    return (sum(usual <= o for o in own) / len(own) if usual else None), len(own)


def raw(win: list[dict], fig: dict, book: dict | None = None,
        ab: dict | None = None) -> dict[str, list[tuple[float | None, int]]]:
    """each trait's figure and its sample, one pair per part; ab: abilities(win)"""
    ab = ab or abilities(win)
    wins = [f for f in win if f.get("result") == "killed"]
    low = [f["lowest_hp"] for f in win if f.get("lowest_hp") is not None]
    won_low = [f["lowest_hp"] for f in wins if f.get("lowest_hp") is not None]
    deaths = sum(f.get("result") == "you died" for f in win)
    gaps = [g for f in win if (g := (f.get("pull") or {}).get("since_last")) is not None and 0 <= g < SESSION_GAP]
    lengths = [f["duration"] for f in win if f.get("duration") is not None]
    quick = [f["duration"] < 15 for f in wins if f.get("duration") is not None]
    calls = [d for f in win if "answered" in (d := f.get("danger") or {}) and (d["answered"] or d.get("unused"))]
    crowd = [foe_count(f) >= 3 for f in wins if foes(f) and (
        alone(f) or fig.get("main_role") == "tank" and not f.get("helped"))]
    duel = [f for f in win if foe_count(f) == 1 and alone(f)]
    fought = [f for f in win if f.get("result") != "you died" and (f.get("damage", 1) or f.get("group"))]
    pvp = [f for f in win if f.get("kind") == "PvP"]
    fallen = beaten(win)
    known = [f for f in win if "group" in f]
    group = [f for f in known if f["group"]]
    beat = [x for f in group if f["group"].get("damage_rank") and not f.get("healing_role") and (x := outdamaged(f)) is not None]
    split = ab["split"] or {}
    own = [r for n, r in ab["all"].items() if not n.endswith(" (pet)")]
    n_hits = sum(r[1] for r in own)
    t, hands, over = fig.get("temperament") or {}, fig.get("hands") or {}, fig.get("overheal") or {}
    healed = (over.get("healing") or 0) + (over.get("overheal") or 0)
    cut, still = hands.get("cut_share"), _cast_time(ab["all"], book or {})
    share, shared = heal_share(win)
    tables = [f["swings_taken"] for f in win if f.get("swings_taken")]
    missed = sum((x.get("misses") or {}).get(k, 0) for x in tables for k in ("miss", "dodge", "parry", "block"))
    swings = sum((x.get("landed") or 0) + sum((x.get("misses") or {}).values()) for x in tables)
    zones = Counter(f.get("zone") or "" for f in win)
    s = lambda flags: (sum(flags) / len(flags) if flags else None, len(flags))  # noqa: E731
    given = fig.get("helping") or {}
    strangers, revives = given.get("strangers"), given.get("revives")
    n, w = len(win), split.get("fights", 0)
    per100 = lambda k, of: (100 * sum(f.get(k) or 0 for f in of) / len(of) if of else None, len(of))  # noqa: E731
    return {
        "Thrift": [(over["overheal"] / healed if healed else None, over.get("fights", 0))],
        "Lifeline": [s([not f["group"].get("deaths") and f.get("result") != "you died" for f in group])],
        "Wall": [(missed / swings if swings else None, swings)],
        "Tempo": [(median(gaps) if gaps else None, len(gaps))],
        "Swift": [s(quick)],
        "Endure": [(median(lengths) if lengths else None, len(lengths))],
        "Marathon": [(max(sittings(win), default=0), n)],
        "Streak": [(streak(win), n)],
        "Edge": [s([v < LOW for v in won_low])],
        "Brink": [(100 * sum(v < BRINK for v in won_low) / len(won_low) if won_low else None, len(won_low))],
        "Guard": [(100 * deaths / n if n else None, n), (sum(low) / len(low) if low else None, len(low))],
        "Wary": [s([bool(d["answered"]) for d in calls])],
        "Crowd": [s(crowd)],
        "Duel": [s([f.get("result") == "killed" for f in duel])],
        "Finish": [s([f.get("result") == "killed" for f in win])],
        "Hound": [s([f.get("result") == "killed" for f in fought])],
        "Boss": [(sum(f.get("kind") == "Boss" for f in wins), n)],
        "War": [s([f.get("result") == "killed" for f in pvp])],
        "Scourge": [(max(fallen.values()) / fallen.total() if fallen else None, fallen.total())],
        "Blade": [(split.get("melee"), w)],
        "Shot": [(split.get("shot"), w)],
        "Craft": [(split.get("ability"), w)],
        "Focus": [(split.get("top"), w)],
        "Range": [(split.get("worth"), w)],
        "Crit": [(sum(r[2] for r in own) / n_hits if n_hits else None, n_hits)],
        "Proc": [(split.get("proc"), w)],
        "Edgewise": [(fig.get("efficiency"), fig.get("judged") or 0)],
        "Ready": [(t.get("cooldowns_share"), t.get("cooldowns_possible") or 0)],
        "Planted": [(None if cut is None or (still or 0) < CAST_TIME else 1 - cut, hands.get("move_casts") or 0)],
        "Primed": [_primed(win)],
        "Break": [per100("interrupts", group)],
        "Lone": [s([alone(f) for f in known])],
        "Bond": [s([bool(f["group"]) for f in known])],
        "Lead": [s(beat)],
        "Mercy": [per100("dispels_others", helpful(win)), (None if fig.get("main_role") == "healer" else share, shared)],
        "Benefactor": [(strangers, strangers or 0)],
        "Lifegiver": [(revives, revives or 0)],
        "Travel": [(sum(c >= 5 for z, c in zones.items() if z not in NO_ZONE), n)],
        "Menagerie": [(len(fallen), n)],
    }


def tier(score: float) -> int:
    return sum(score >= t for t in TIERS)


def score_of(t: Trait, parts: list[tuple[float | None, int]]) -> dict | None:
    """one trait's scores() entry from its parts' (figure, sample)"""
    got = [(round(min(1.0, max(0.0, (v - p.low) / (p.high - p.low))), 6), p, v) for p, (v, n) in zip(t.parts, parts)
           if v is not None and n >= p.minimum]
    if not got or (t.weaker and len(got) < len(t.parts)):
        return None
    score, p, v = (min if t.weaker else max)(got, key=lambda g: g[0])
    k, nxt = tier(score), None
    if k < len(TIERS):
        need = TIERS[k]
        short = [g[1] for g in got if g[0] < need] if t.weaker else [p]
        nxt = {"epithet": t.epithets[k], "needs": [[q.kind, q.low + need * (q.high - q.low)] for q in short]}
    n = next(n for q, (w, n) in zip(t.parts, parts) if q is p)
    return {"figure": v, "kind": p.kind, "score": score, "tier": k, "caption": p.caption, "n": n,
            "parts": [[q.kind, w] for _, q, w in got], "next": nxt}


def scores(win: list[dict], fig: dict, book: dict | None = None, ab: dict | None = None) -> dict[str, dict | None]:
    found = raw(win, fig, book, ab)
    out = {t.key: score_of(t, found[t.key]) if fig.get("main_role") in t.roles else None for t in TRAITS}
    names = ((ab or abilities(win))["split"] or {}).get("names") or []
    for k, own in (("Range", [x for x in names if x[1] >= WORTH]), ("Focus", names[:1]),
                   ("Scourge", [[n, c] for n, c in beaten(win).most_common(1)])):
        if out[k]:
            out[k]["names"] = own
    if out["Crowd"] and fig["main_role"] == "tank":
        out["Crowd"]["caption"] = "of your wins were against three or more"      # with a group too
    return out


def pick(sc: dict[str, dict | None], n: int = 2, first: str | None = None) -> list[str]:
    """the traits that name the character, best first (the table's order on a tie), each of another family and at tier 1
    or better; first: the one to begin with (a named title's)"""
    ranked = sorted((k for k in BY_KEY if sc.get(k) and sc[k]["tier"]), key=lambda k: -sc[k]["score"])
    out: list[str] = []
    for k in ([first] if first else []) + ranked:
        if len(out) < n and BY_KEY[k].family not in {BY_KEY[o].family for o in out}:
            out.append(k)
    return out


def named(sc: dict[str, dict | None]) -> tuple[str, str, str] | None:
    """(title, its better trait, the other) of the first named title that applies"""
    for a, b, title in NAMED:
        if all(sc.get(k) and sc[k]["tier"] >= 2 for k in (a, b)):
            return title, *sorted((a, b), key=lambda k: -sc[k]["score"])
    return None


def epithet(sc: dict[str, dict | None], key: str) -> str | None:
    s = sc.get(key)
    return BY_KEY[key].epithets[s["tier"] - 1] if s and s["tier"] else None


def needs(nxt: dict, trait: Trait) -> list[tuple[str, str]]:
    """the next tier's figures as text, rounded the way that reaches it"""
    out = []
    for kind, v in nxt["needs"]:
        rising = next(p.high > p.low for p in trait.parts if p.kind == kind)
        scale = {"%": 100, "n1": 10}.get(kind, 1)
        out.append(shown(kind, (math.ceil if rising else math.floor)(round(v * scale, 6)) / scale))
    return out
