"""What the Profile page shows, as plain data (no Qt), from live.profile.profile() and the saved 15-day slices
(live.profile_history): the crest (title, second line, deeds), the hero (the title's trait, or the main role's share
without one) and the label, the "Before:" line, the Worth changing plate, How you fight, every trait, Signature (no per-row note but "no damage of its own" for a "–" share), Hands (no chip, never marked; no rows without a recorded run), Role mix, Where you fight, the chips and the one highlighter mark (Now against
Before: a trait's tier that Before had not reached, else the largest move, on a tie the increase, then page order), the
Earlier rows and every empty state. A
value that cannot be known renders "–", never a guess.

Inks are token names: Signature bars "m-dmg" (a share of casts "m-cast"), traits and How you fight _ink, Role mix bars ROLE_INK, Where you fight bars PLACE_INK, other
figures "tx". A Role mix grade letter and
score take theme.grade_color(letter), which the painter applies (there is no token per grade)."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .dungeon_view import visits
from .fight_view import CLEAN
from .habits_view import MINUS, _meta, _plural
from .live.profile_history import MIN_FIGHTS
from .live.traits import BY_KEY, TIERS, needs, shown, written
from .scoring import usable
from .scoring.score import RULES
from .debrief import combat_span
from .sheet_view import SheetView, build_sheet
from .time_view import TimeBar, build_time
from .trait_words import words

NA = "–"
CHIP_MIN = 5                # percentage points a share row must move against Before to get a chip
# the plate rule table: first that applies (see _plate)
PLATE_DEATHS = 0.15         # dying in this share or more of fights
PLATE_LOST = 0.01           # the ability's damage lost, this share or more of your damage
PLATE_CLOSE = 5             # fights with a close call and a defensive ready, at least
PLATE_OVERHEAL = 0.40       # a healer's overheal, this share or more of the healing cast
PLATE_COOLDOWNS = 0.50      # cooldowns used under this share of possible
PLATE_CLICKS = 0.60         # clicking this share or more of keyed + clicked presses,
PLATE_REFUSED = 0.40        # or this share or more of casts tried refused,
PLATE_PRESSES = 500         # with this many of them or more (and see _badly)
DOING = {"damage": "dealing damage", "healer": "healing", "tank": "tanking"}
ROLE_MOVE = {"damage": "damage dealing", "healer": "healing", "tank": "tanking"}    # "more healing"
GRADED_AS = {"damage": "damage dealer", "healer": "healer", "tank": "tank"}
ROLE_NAME = {"damage": "Damage", "healer": "Healer", "tank": "Tank"}
ROLE_INK = {"damage": "role-dmg", "healer": "role-heal", "tank": "role-tank"}
PLACE_INK = {"Dungeon": "place-dungeon", "Raid": "place-raid", "World": "place-world", "PvP": "place-pvp"}
PLACE_MOVE = {"Dungeon": ("more dungeons", "fewer dungeons"), "Raid": ("more raids", "fewer raids"),
              "World": ("more open world", "less open world"), "PvP": ("more PvP", "less PvP")}
MELEE = "Melee (auto attack)"
OUTDATED = "Based on older fight records. Import your combat logs in Settings for the full picture."
WORTH, WELL = "Worth changing", "Going well"     # the plate's tab: a fix, or nothing to fix
# one ink per trait or How you fight row, wherever its figure shows; the rest (Victory, Company, Break) take the main role's
FAMILY_INK = {"Pace": "m-pace", "Nerve": "m-surv", "Weapon": "m-dmg", "Healing": "role-heal", "Tanking": "role-tank",
              "Road": "place-world"}
KEY_INK = {"Edgewise": "m-dmg", "split": "m-dmg", "Ready": "m-cd", "Planted": "m-cast", "cut": "m-cast", "Primed": "m-upk",
           "Mercy": "role-heal", "Benefactor": "role-heal", "Lifegiver": "role-heal", "overheal": "role-heal", "heal_share": "role-heal", "dispels": "role-heal",
           "pull": "role-tank", "taken": "m-surv", "lowest": "m-surv", "War": "place-pvp", "broken_off": "place-pvp",
           "length": "place-pvp", "pvp_deaths": "place-pvp"}
# a trait of two figures, by the one that scores it
GUARD_NAME = {"%": "Average lowest health", "n1": "Deaths per 100 fights"}
MERCY_NAME = {"%": "Share of group healing", "n1": "Dispels on others"}
# How you fight rows whose caption only says their name again
RESTATED = {"Tempo", "Swift", "Marathon", "Streak", "Guard", "lowest", "Duel", "Finish", "Hound", "Boss", "War",
            "Edgewise", "Ready", "Primed", "Lone", "Bond", "Menagerie", "Crit", "pvp_deaths"}


@dataclass
class Row:
    name: str
    value: str = NA             # "98", "4.2", "–"
    unit: str = ""              # small text after the value: "%", "% keys", "enemy"
    note: str = ""              # the line under the row
    ink: str = "tx"             # the value's (and bar's) colour token
    bar: float | None = None    # bar length 0..1; None for a figure row or a share that cannot be known
    chip: str | None = None     # "+12 pts vs the 15 days before"
    mark: str | None = None     # the highlighter's note; on one row of the page at most
    casts: str = ""             # Signature: "1,665", "–" with none (a proc)
    grade: str = ""             # Role mix: mean score "72", or "–"
    letter: str = ""            # Role mix: grade letter "B"


@dataclass
class Plate:
    title: str
    figure: str
    caption: str
    why: str = ""               # one plain sentence from real figures; "" when there is nothing real to say
    button: str = "Open Habits"
    next: list[tuple[str, str]] = field(default_factory=list)       # the next two abilities: (name, "51,884 damage")
    tab: str = WORTH


@dataclass
class Crest:
    who: str                    # "Undead Paladin, level 37"
    title: str                  # "Relentless Crusader of the Arathi Highlands"
    second: str = ""            # "Wins one on one, lets few get away."
    deeds: list[str] = field(default_factory=list)      # two at most


@dataclass
class TraitRow:
    key: str
    name: str                   # "Time between fights"
    value: str                  # "25"
    unit: str                   # "s"
    line: str                   # what it is, under its name: "usual wait between fights"
    bar: float                  # its score 0..1
    tier: str = ""              # its epithet "Relentless", "" under the first tier
    ends: tuple[str, str] = ("", "")    # the figures the bar begins and ends at: "120 s", "15 s"
    tip: str = ""               # the hover: how it is worked out, your figures, where each tier begins (one line each)
    ink: str = "tx"             # its figure's and bar's


@dataclass
class EarlierRow:
    dates: str                  # "25 Oct to 8 Nov"
    label: str                  # its title, or its label when it was saved without one
    role: str                   # main role and its share "Damage 96%"
    deaths: str                 # deaths per hour "3.1"
    cooldowns: str              # cooldowns used "49%"
    stats: str = ""             # "gear 31 · 14 spell power · 940 armor", the Player Type, then what the middle fight had; "stats not recorded"


@dataclass
class ProfileView:
    title: str = "Profile"      # the character's name
    meta: str = ""              # "gear 31 · last 15 days · 396 fights", with no crest also "level 36 Undead Paladin"
    need: str | None = None     # under MIN_FIGHTS: the headline; the page then shows only it, need_line and Earlier
    need_line: str = ""
    crest: Crest | None = None
    outdated: str = ""          # the line under the crest when most fights were summed up by an older version
    ring: str | None = None     # a new tier's note, "new: Relentless", and its trait: then no other row is marked, but
    ring_key: str | None = None     # the How you fight row of that trait, for the page to ring with All traits shut
    card: list[Row] = field(default_factory=list)       # How you fight, the title's own row first
    traits_title: str = "All traits (0)"
    traits: list[tuple[str, list[TraitRow]]] = field(default_factory=list)      # by family, those that score
    hero: str = NA              # the title's trait "25", or the main role's share "98"
    hero_unit: str = "%"
    hero_ink: str = "tx"
    caption: str = ""           # "between one fight and the next"
    chip: str | None = None     # the hero figure's change, when it is a share; chip_ink its box
    chip_ink: str = "ln"
    label: str = ""             # "Careful world damage dealer."
    before: str | None = None   # "Before: Tireless Crusader of Stranglethorn Vale"
    plate: Plate | None = None
    sig_header: str = ""        # "share of your damage" / "share of your casts"
    signature: list[Row] = field(default_factory=list)
    opener: str = NA            # "Judgement, Holy Strike, Consecration"
    opener_note: str = ""
    spells_title: str = ""      # "All spells (24)"
    spells_header: str = ""     # "share of damage"
    spells: list[tuple[str, str, str]] = field(default_factory=list)    # (name, casts, share "13.4%" or "–")
    hands: list[Row] = field(default_factory=list)
    roles: list[Row] = field(default_factory=list)
    places: list[Row] = field(default_factory=list)
    time: TimeBar = field(default_factory=TimeBar)          # Where your time goes
    sheet: SheetView = field(default_factory=SheetView)     # the Character sheet drawer
    earlier_title: str = "Earlier (0)"
    earlier: list[EarlierRow] = field(default_factory=list)            # newest first


def _pct(v) -> str:
    return NA if v is None else f"{v * 100:.0f}"


def _hm(seconds) -> str:
    h, m = divmod(round((seconds or 0) / 60), 60)
    return f"{h} h {m} min" if h else f"{m} min"


def _day(iso: str, shift=timedelta()) -> str:
    d = datetime.fromisoformat(iso) + shift
    return f"{d.day} {d:%b}"


def _had(f: dict) -> str:
    s = f.get("stats") or {}
    parts = [kind] if (kind := (f.get("time") or {}).get("type")) else []
    parts += [f"gear {s['gear']:.0f}"] if "gear" in s else []
    parts += [f"{s[k]:,.0f} {name}" for k, name in (("sp", "spell power"), ("armor", "armor"), ("hp", "health"), ("mana", "mana"))
              if s.get(k)]
    return " · ".join(parts if s else [*parts, "stats not recorded"])


def _earlier(earlier: list[dict]) -> list[EarlierRow]:
    out = []
    for s in sorted(earlier, key=lambda s: s["to"], reverse=True):
        f = s.get("figures") or {}
        main, t = f.get("main_role"), f.get("temperament") or {}
        dph, sh = t.get("deaths_per_hour"), (f.get("roles") or {}).get(main)
        out.append(EarlierRow(
            # the window is (from, to]: its first day is the day after from
            dates=f"{_day(s['from'], timedelta(days=1))} to {_day(s['to'])}",
            label=(s.get("title") or s.get("label") or NA).rstrip("."),
            role=NA if sh is None else f"{ROLE_NAME.get(main, str(main).title())} {_pct(sh)}%",
            deaths=NA if dph is None else f"{dph:.1f}",
            cooldowns=NA if t.get("cooldowns_share") is None else _pct(t["cooldowns_share"]) + "%", stats=_had(f)))
    return out


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _works(name: str, c: dict) -> str:
    """"Exorcism works on undead and demons. You fought 37 of them in 12 fights and cast it 0 times." """
    r = usable.RULES[name]
    had = f"You had {usable.counted(c['chances'], r)}" if "after" in r else f"You fought {c['chances']:,} of them"
    return f"{name} works {r['works']}. {had} in {_plural(c['fights'], 'fight')} and cast it 0 times."


def _count(n: int, word: str) -> str:
    """_plural with thousands separated"""
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def _sat_ready(losses: list[dict], gain: float) -> Plate:
    """the ability whose ready time lost the most damage, and the next two"""
    top = losses[0]
    missed = f"{_count(top['missed'], 'cast')} missed " if top["missed"] else ""
    chances = f"in {_count(top['chances'], 'chance')}, " if top["chances"] else ""
    rule = usable.rule(top["name"])
    why = (f"It works {rule['works']}. " if rule else "") + \
        f"Press it when it comes up: that is about {_pct(gain)}% more damage over these 15 days."
    return Plate(f"{top['name']} sat ready", f"about {top['lost']:,.0f} damage",
                 f"{missed}{chances}in {_count(top['fights'], 'fight')}", why,
                 next=[(s["name"], f"{s['lost']:,.0f} damage") for s in losses[1:3]])


def _plate(now: dict, before: dict | None) -> Plate | None:
    """the first rule that applies: deaths, the ability that lost the most damage (not for a healer, nor in a window
    that reads CLEAN or better), close calls with a defensive ready, spells never cast, a healer's overheal, cooldowns, input when it is
    badly wrong. Else, under its own tab, what goes well: a healer's overheal, a clean window from
    MIN_FIGHTS judged fights; None under CLEAN or without a figure"""
    n, h, t = now["fights"], now.get("hands") or {}, now["temperament"]
    fights = f"in your last {_plural(n, 'fight')}"
    cds, unused = t.get("cooldowns_share"), now.get("unused")
    dying = t["deaths"] / n if n else None
    if dying is not None and dying >= PLATE_DEATHS:
        return Plate(f"You die in {_pct(dying)}% of your fights", _plural(t["deaths"], "death"), fights,
                     f"{t['deaths']} of your last {n} fights ended with you dead.")
    eff, losses = now.get("efficiency"), now.get("losses") or []
    clean = eff is not None and int(_pct(eff)) >= round(CLEAN * 100)        # as the plate would show it
    gain = losses[0]["lost"] / now["damage"] if losses else 0
    if gain >= PLATE_LOST and not clean and now["main_role"] != "healer":
        return _sat_ready(losses, gain)
    close = now.get("close_calls") or {}
    if close.get("unused", 0) >= PLATE_CLOSE:
        return Plate(f"{close['spell']} sat ready in {_count(close['count'], 'close call')}",
                     f"{close['count']:,} of {close['unused']:,}", f"close calls with a defensive ready, {fights}",
                     "Press it when your health runs low.")
    if unused:
        names, one = unused[:3], len(unused[:3]) == 1
        top = [s["name"] for s in sorted(now["signature"]["spells"], key=lambda s: -s["casts"])[:3]]
        carry = f"{_and(top)} {'carries' if len(top) == 1 else 'carry'} your casts. " if top else ""
        met = now.get("restricted") or {}
        free = [x for x in names if x not in met]
        bench = (f"{_and(free)} {'is the harmful spell' if len(free) == 1 else 'are the harmful spells'} left on "
                 "the bench." if free else "")
        works = " ".join(_works(x, met[x]) for x in names if x in met)
        return Plate(f"You know {_and(names)} and have not cast {'it' if one else 'them'}", "0 casts", fights,
                     " ".join(w.strip() for w in (carry, bench, works) if w))
    o = now.get("overheal")
    cast = o and o["healing"] + o["overheal"]
    if now.get("main_role") == "healer" and cast and o["overheal"] / cast >= PLATE_OVERHEAL:
        return Plate("Much of your healing lands on full health", f"{_pct(o['overheal'] / cast)}% overheal",
                     f"{o['overheal']:,} of {cast:,} healing, in {_count(o['fights'], 'healing fight')}",
                     "Wait for the health to drop, or cast a smaller heal.")
    if cds is not None and cds < PLATE_COOLDOWNS:
        left = t["cooldowns_possible"] - t["cooldowns_used"]
        return Plate("You leave your cooldowns unused", f"{_pct(cds)}% used",
                     f"{t['cooldowns_used']:,} of {t['cooldowns_possible']:,} possible, {fights}",
                     f"{_plural(left, 'use')} of a ready cooldown went unspent.")
    runs = _plural(h.get("runs") or 0, "recorded run")
    if _badly(now, before, "click_share", PLATE_CLICKS, ("by_key", "by_click")):
        return Plate("You click instead of pressing keys", f"{_pct(h['click_share'])}% clicks",
                     f"{h['by_click']:,} of {h['by_key'] + h['by_click']:,} presses, in {runs}",
                     "Bind the spells you click most to keys.")
    if _badly(now, before, "refused_share", PLATE_REFUSED, ("casts", "failed")):
        return Plate("The game turns down your presses", f"{_pct(h['refused_share'])}% refused",
                     f"{h['failed']:,} of {h['casts'] + h['failed']:,} casts tried, in {runs}")
    if now.get("main_role") == "healer" and cast:
        return Plate("Your healing lands", f"{_pct(o['overheal'] / cast)}% overheal",
                     f"{o['overheal']:,} of {cast:,} healing, in {_count(o['fights'], 'healing fight')}", tab=WELL)
    if not clean or now["judged"] < MIN_FIGHTS:        # under 90% or no figure there is a gap to look at, not a plate
        return None
    return Plate("Your last 15 days were clean", f"{_pct(eff)}% of possible damage",
                 f"in {_count(now['judged'], 'fight')} where you did damage", tab=WELL)


def _badly(now: dict, before: dict | None, key: str, limit: float, of: tuple[str, str]) -> bool:
    """input badly wrong: the share at its limit or over it, of enough (the counts it is a share of), and not already
    so in the window before at the same displayed figure or a worse one"""
    def wrong(f):
        h = (f or {}).get("hands") or {}
        return h[key] if h.get(key) is not None and h[key] >= limit and sum(h[k] for k in of) >= PLATE_PRESSES else None
    a, b = wrong(now), wrong(before)
    return a is not None and (b is None or int(_pct(a)) > int(_pct(b)))


def run_row(a) -> dict:
    """what live.profile needs of a recorded run, from its analysis: the dungeon page's score for it (None: not
    compared), the role it was scored as (None: nothing to tell it from), its presses and its casts"""
    run, m, visit = a.data.run, a.metrics, visits([(a.data.run, a)])[0]
    known = visit.score is not None and a.me and a.me.role
    return {"me": a.data.player_guid, "parts": list(run.parts) or [run.id], "name": run.player_name,
            "start": run.start_time, "role": {"dps": "damage"}.get(a.role, a.role) if known else None,
            "score": visit.score, "grade": visit.grade, "rules": RULES,
            "in_combat": (lambda s: s and s[0] / s[1])(combat_span(a)), "presses": m.presses, "by_key": m.by_key, "by_click": m.by_click,
            "failed": m.failed, "casts": m.casts, "combat_time": m.combat_time, "moving_time": m.moving_time,
            "move_interrupts": m.move_interrupts, "wasted_cast_time": m.wasted_cast_time}


def combat_shares(rows: dict[str, dict | None], me: str | None, start) -> list[float]:
    """the share in combat of your runs up to the one that started at start, oldest first"""
    mine_ = sorted((r for r in rows.values() if r and r["me"] == me and r.get("in_combat") is not None
                    and r["start"] <= start), key=lambda r: r["start"])
    return [r["in_combat"] for r in mine_]


def mine(rows: dict[str, dict | None], me: str, name: str) -> dict[str, dict]:
    """the run rows of one character: by guid, by name for a run without a combat log (its guid unknown)"""
    return {rid: r for rid, r in rows.items() if r and (r["me"] == me or (r["me"] is None and r["name"] == name))}


def _who(p: dict) -> str:
    c = p.get("char") or {}
    kind = " ".join(x.title() for x in (c.get("race"), c.get("class")) if x)
    level = c.get("level") or p.get("level")
    return ", ".join(x for x in (kind, f"level {level}" if level else "") if x)


def _ink(key: str, main: str | None) -> str:
    return KEY_INK.get(key) or FAMILY_INK.get(BY_KEY[key].family) or ROLE_INK.get(main, "tx")


def _given(key: str, h: dict) -> str:
    """what a helping trait's figure is made of, or what goes with it"""
    if key == "Lifegiver":
        return f"{h['group_revives']:,} in your group, {_count(h['revives'] - h['group_revives'], 'stranger')}"
    return _count(h["group_buffs"], "buff")


def _you(t: dict, helping: dict | None) -> str | None:
    """"You: 681 of 1,209 fights.", None when a figure it needs is unknown (an entry saved before 0.20)"""
    tr, kind, v, n = BY_KEY[t["key"]], t["kind"], t["figure"], t.get("n")
    if n is None:
        return None
    need = needs(t["next"], tr) if t["next"] else []
    fine = lambda k, x: written(*shown(k, x, fine=shown(k, x) in need))  # noqa: E731  (one decimal more where it reads as reached)
    part = dict(map(tuple, t["parts"]))
    names, extra = t.get("names") or [], ""
    if tr.key in ("Benefactor", "Lifegiver"):
        if not helping:
            return None
        extra = _given(tr.key, helping)
    named = [x for x, _ in names] if tr.key == "Scourge" else [f"{x} {_pct(s)}%" for x, s in names]
    return "You: " + words(tr.key, kind).you.format(
        v=fine(kind, v), n=f"{n:,}", hits=f"{round(v * n / (100 if kind == 'n1' else 1)):,}", extra=extra,
        names=_and(named) if named else NA, v1=fine("n1", part.get("n1", 0)), v2=fine("%", part.get("%", 0))) + "."


def _marks(tr, kind: str) -> str:
    """"Tiers: Wandering from 70%, Lone from 81%, Sovereign from 91%." """
    parts = [p for p in tr.parts if tr.weaker or p.kind == kind]
    rising = all(p.high > p.low for p in parts)

    def at(p, score):
        text = written(*needs({"needs": [[p.kind, p.low + score * (p.high - p.low)]]}, tr)[0])
        if p.high > p.low:
            return text + (" health" if tr.key == "Guard" else "")
        return f"{text} {'deaths ' if tr.key == 'Guard' else ''}or {'fewer' if p.kind[0] == 'n' else 'under'}"
    # shortcut: a mark rounds toward its tier and the row's figure to the nearest, so a figure just over a mark can read under it
    return "Tiers: " + ", ".join(f"{e} {'from' if rising else 'at'} {_and([at(p, s) for p in parts])}"
                     for e, s in zip(tr.epithets, TIERS)) + "."


def _trait_row(t: dict, main: str | None, helping: dict | None = None) -> TraitRow:
    tr, w = BY_KEY[t["key"]], words(t["key"], t["kind"])
    value, unit = shown(t["kind"], t["figure"])
    name = MERCY_NAME[t["kind"]] if tr.key == "Mercy" else tr.name
    if tr.key == "Guard" and len(t.get("parts") or []) == 2:     # both, so the figure left out is not a surprise
        value, unit = " · ".join(written(*shown(k, v)) for k, v in t["parts"]), ""
    elif tr.key == "Guard":
        name = GUARD_NAME[t["kind"]]
    p = next(p for p in tr.parts if p.kind == t["kind"])
    return TraitRow(tr.key, name, value, unit, w.line, t["score"], t["epithet"] or "",
                    tuple(written(*shown(p.kind, x)) for x in (p.low, p.high)),
                    "\n".join(x for x in (w.how, _you(t, helping), _marks(tr, t["kind"])) if x), _ink(tr.key, main))


def _new_tier(now: dict, before: dict | None) -> dict | None:
    """the trait whose tier Before, where its score is known, had not reached: the title's, else one of How you fight,
    else the highest"""
    had = {t["key"]: t["tier"] for t in before["traits"]} if before else {}
    return max((t for t in now["traits"] if t["key"] in had and t["tier"] > had[t["key"]]), default=None,
               key=lambda t: (t["key"] == now["lead"], t["key"] in now["pack"], t["tier"], t["score"]))


def build_profile(p: dict, earlier: list[dict]) -> ProfileView:
    """the page for live.profile.profile(...)'s result and this character's saved slices"""
    now, before = p.get("now"), p.get("before")
    n = now["fights"] if now else 0
    window = f"last 15 days · {_plural(n, 'fight')}"
    v = ProfileView(title=p.get("name") or "Profile", earlier=_earlier(earlier),
                    meta=_meta({"char": p.get("char"), "level": p.get("level")}, window))
    v.earlier_title = f"Earlier ({len(v.earlier)})"
    v.sheet = build_sheet(p.get("sheet"), p.get("broken"))
    v.time = build_time((now or {}).get("time"), p.get("time_before"))      # days, not fights: an auction house day has none
    if n < MIN_FIGHTS:
        v.need = f"Your profile needs {MIN_FIGHTS} fights from the last 15 days ({n} so far)."
        v.need_line = "Play a few more fights and it fills in." + (
            " Who you were in earlier slices is below." if v.earlier else "")
        return v
    moves = []      # (row, points, highlighter note) for every share row that got a chip, in page order

    def share(row: Row, key, up: str, down: str) -> Row:
        """a share row's chip (and highlighter candidacy): key(figures) is the share, Now against Before; the
        points are the difference of the displayed (rounded) figures"""
        a, b = key(now), key(before) if before else None
        if a is not None and b is not None and abs(d := int(_pct(a)) - int(_pct(b))) >= CHIP_MIN:
            row.chip = f"{'+' if d > 0 else MINUS}{abs(d)} pts vs the 15 days before"
            moves.append((row, d, up if d > 0 else down))
        return row

    main, hero = now["main_role"], now["hero"]
    v.crest = Crest(_who(p), now["title"], now["second"], now["deeds"])
    v.meta = _meta({"char": {"gear": (p.get("char") or {}).get("gear")}}, window)      # the crest says the rest
    v.outdated = OUTDATED if now["outdated"] else ""
    if hero:
        v.hero, v.hero_unit, v.caption = hero["figure"], hero["unit"], hero["caption"]
        v.hero_ink = v.chip_ink = _ink(hero["key"], main)
    elif main:
        v.hero, v.caption, v.hero_ink = _pct(now["roles"][main]), f"of fight time {DOING[main]}", ROLE_INK[main]
    else:
        v.hero_unit, v.caption = "", "no fight time in these fights"
    v.label = now["label"]
    if before and before["title"] != now["title"]:
        v.before = f"Before: {before['title']}"
    v.plate = _plate(now, before)

    # Cut short by moving always shows when it is known, after the pack (Planted is the same figure)
    cut = ["cut"] if "cut" in now["rows"] and not {"cut", "Planted"} & set(now["pack"]) else []
    card = {}
    for k in now["pack"] + cut:
        r = now["rows"][k]
        value, unit = shown(r["kind"], r["figure"])
        row = Row({"Guard": GUARD_NAME, "Mercy": MERCY_NAME}.get(k, {}).get(r["kind"], r["name"]), value, f"{unit} {r['unit']}".strip(),
                  "" if k in RESTATED else r["note"], _ink(k, main), r["figure"] if r["share"] else None)
        if r["share"]:
            # a trait of two figures may be the other one in Before
            share(row, lambda f, k=k: r2["figure"] if (r2 := f["rows"].get(k) or {}).get("share") else None,
                  "higher", "lower")
        if hero and k == hero["key"]:
            v.chip = row.chip
        card[k] = row
    v.card = list(card.values())
    card_moves, moves[:] = moves[:], []      # last in page order: on a tie the older row keeps the mark
    scored = [t for t in now["traits"] if t["score"] > 0]
    for t in scored:
        if not v.traits or v.traits[-1][0] != t["family"]:
            v.traits.append((t["family"], []))
        v.traits[-1][1].append(_trait_row(t, main, now.get("helping")))
    v.traits_title = f"All traits ({len(scored)})"

    sig = now["signature"]
    casts = sig["basis"] == "casts"
    v.sig_header = "share of your casts" if casts else "share of your damage"
    v.spells_header = "share of casts" if casts else "share of damage"
    def name_count(s) -> tuple[str, str]:
        """a row's name and its casts; Melee shows as auto attack with its swings. "–": none (a proc), or no count"""
        if s["name"] != "Melee":
            return s["name"], f"{s['casts']:,}" if s["casts"] else NA
        swings = s.get("swings")
        return MELEE, NA if swings is None else f"{swings:,} swings"

    for s in sig["top"]:
        has = bool(s["share"])
        name, count = name_count(s)
        v.signature.append(Row(name, _pct(s["share"]) if has else NA, "%" if has else "", ink="m-cast" if casts else "m-dmg",
                               bar=s["share"] if has else None, casts=count,
                               note="" if has else "no damage of its own"))
    if not sig["top"]:
        v.signature.append(Row("Spells", note="no spell casts saved in these fights"))
    v.spells_title = f"All spells ({len(sig['spells'])})"
    v.spells = [(*name_count(s), f"{s['share'] * 100:.1f}%" if s["share"] else NA) for s in sig["spells"]]
    if o := now.get("opener"):
        v.opener = ", ".join(o["casts"])
        v.opener_note = f"your usual opening: the first three casts in {o['count']} of {o['of']} fights"
    else:
        v.opener_note = "your usual opening shows once a fight saves its first three casts"

    h = now.get("hands")
    if h:
        runs, combat = _plural(h["runs"], "recorded run"), h["combat_seconds"]
        ks, refused = h["key_share"], h["refused_share"]
        v.hands = [
            Row("Keys or clicks", _pct(ks), "% keys" if ks is not None else "",
                f"{h['by_click']:,} clicks in {h['by_key'] + h['by_click']:,} presses, in {runs}"),
            Row("Presses per minute", NA if h["per_minute"] is None else f"{h['per_minute']:.1f}",
                note=f"over {_hm(combat)} of combat in recorded runs"),
            Row("Refused presses", _pct(refused), "%" if refused is not None else "",
                f"{h['failed']:,} presses the game turned down, in recorded runs")]

    for role in ("damage", "healer", "tank"):
        sh, gr = now["roles"][role], (now.get("grades") or {}).get(role)
        row = Row(ROLE_NAME[role], _pct(sh), "%" if sh is not None else "", ink=ROLE_INK[role], bar=sh)
        if gr:
            # the painter colours the letter and score with theme.grade_color(letter): there is no gF token
            row.grade, row.letter = f"{gr['score']:.0f}", gr["grade"]
            row.note = f"average of {_plural(gr['runs'], 'graded run')}"
        else:
            row.grade, row.note = NA, f"no run graded as {GRADED_AS[role]} yet"
        v.roles.append(share(row, lambda f, r=role: f["roles"][r], f"more {ROLE_MOVE[role]}", f"less {ROLE_MOVE[role]}"))
        if role == main and not hero:
            v.chip, v.chip_ink = row.chip, row.ink

    places = now["places"]
    for place in sorted(places, key=lambda k: -(places[k] or 0)):
        sh = places[place]
        v.places.append(share(Row(place, _pct(sh), "%" if sh is not None else "", ink=PLACE_INK[place], bar=sh),
                              lambda f, k=place: f["places"][k], *PLACE_MOVE[place]))

    if new := _new_tier(now, before):
        v.ring, v.ring_key = f"new: {new['epithet']}", new["key"]
        if new["key"] in card:
            card[new["key"]].mark = v.ring
    elif moves := moves + card_moves:     # the largest move, on a tie the increase, then (max keeps the first) page order
        row, _, note = max(moves, key=lambda m: (abs(m[1]), m[1]))
        row.mark = note
    return v
