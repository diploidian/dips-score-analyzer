"""What the Profile page shows, as plain data (no Qt), from live.profile.profile() and the saved 15-day slices
(live.profile_history): the hero (main role share and the label), the "Before:" line, the Worth changing plate,
Signature (no per-row note but "no damage of its own" for a "–" share), Hands, Role mix, Where you fight, Temperament, the chips and the one highlighter mark (Now against
Before), the Earlier rows and every empty state. A value that cannot be known renders "–", never a guess.

Inks are token names: Signature bars "m-dmg", Role mix bars ROLE_INK, Where you fight bars PLACE_INK, scored
rows their measure ink ("m-cast", "m-surv", "m-cd", "m-act"), other figures "tx". A Role mix grade letter and
score take theme.grade_color(letter), which the painter applies (there is no token per grade)."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .habits_view import MINUS, _meta, _plural
from .live.profile_history import MIN_FIGHTS
from .scoring import usable

NA = "–"
CHIP_MIN = 5                # percentage points a share row must move against Before to get a chip
# the plate rule table: first that applies (see _plate)
PLATE_CLICKS = 0.30         # clicking this share or more of keyed + clicked presses
PLATE_COOLDOWNS = 0.50      # cooldowns used under this share of possible
PLATE_DEATHS = 0.15         # dying in this share or more of fights
DOING = {"damage": "dealing damage", "healer": "healing", "tank": "tanking"}
ROLE_MOVE = {"damage": "damage dealing", "healer": "healing", "tank": "tanking"}    # "more healing"
GRADED_AS = {"damage": "damage dealer", "healer": "healer", "tank": "tank"}
ROLE_NAME = {"damage": "Damage", "healer": "Healer", "tank": "Tank"}
ROLE_INK = {"damage": "role-dmg", "healer": "role-heal", "tank": "role-tank"}
PLACE_INK = {"Dungeon": "place-dungeon", "Raid": "place-raid", "World": "place-world", "PvP": "place-pvp"}
PLACE_MOVE = {"Dungeon": ("more dungeons", "fewer dungeons"), "Raid": ("more raids", "fewer raids"),
              "World": ("more open world", "less open world"), "PvP": ("more PvP", "less PvP")}
MELEE = "Melee (auto attack)"
NO_HANDS = "Hands needs a recorded run: play with the dips-Score add-on on, then reload."


@dataclass
class Row:
    name: str
    value: str = NA             # "98", "4.2", "–"
    unit: str = ""              # small text after the value: "%", "% keys", "enemy"
    note: str = ""              # the line under the row
    ink: str = "tx"             # the value's (and bar's) colour token
    bar: float | None = None    # bar length 0..1; None for a figure row or a share that cannot be known
    chip: str | None = None     # "+12 vs the 15 days before"
    mark: str | None = None     # the highlighter's note; on one row of the page at most
    casts: str = ""             # Signature: "1,665"
    grade: str = ""             # Role mix: mean score "72", or "–"
    letter: str = ""            # Role mix: grade letter "B"


@dataclass
class Plate:
    title: str
    figure: str
    caption: str
    why: str = ""               # one plain sentence from real figures; "" when there is nothing real to say
    button: str = "Open Habits"


@dataclass
class EarlierRow:
    dates: str                  # "25 Oct to 8 Nov"
    label: str
    role: str                   # main role and its share "Damage 96%"
    deaths: str                 # deaths per hour "3.1"
    cooldowns: str              # cooldowns used "49%"


@dataclass
class ProfileView:
    title: str = "Profile"      # the character's name
    meta: str = ""              # "level 36 Undead Paladin · gear 31 · last 15 days · 396 fights"
    need: str | None = None     # under MIN_FIGHTS: the headline; the page then shows only it, need_line and Earlier
    need_line: str = ""
    hero: str = NA              # main role share, "98"
    hero_unit: str = "%"
    caption: str = ""           # "of fight time dealing damage"
    label: str = ""             # "World damage dealer who keybinds."
    before: str | None = None   # "Before: hoarding dungeon damage dealer."
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
    temperament: list[Row] = field(default_factory=list)
    earlier_title: str = "Earlier (0)"
    earlier: list[EarlierRow] = field(default_factory=list)            # newest first


def _pct(v) -> str:
    return NA if v is None else f"{v * 100:.0f}"


def _hm(seconds) -> str:
    h, m = divmod(round((seconds or 0) / 60), 60)
    return f"{h} h {m} min" if h else f"{m} min"


def _lower(label: str) -> str:
    return label if label.startswith("PvP") else label[:1].lower() + label[1:]


def _day(iso: str, shift=timedelta()) -> str:
    d = datetime.fromisoformat(iso) + shift
    return f"{d.day} {d:%b}"


def _earlier(earlier: list[dict]) -> list[EarlierRow]:
    out = []
    for s in sorted(earlier, key=lambda s: s["to"], reverse=True):
        f = s.get("figures") or {}
        main, t = f.get("main_role"), f.get("temperament") or {}
        dph, sh = t.get("deaths_per_hour"), (f.get("roles") or {}).get(main)
        out.append(EarlierRow(
            # the window is (from, to]: its first day is the day after from
            dates=f"{_day(s['from'], timedelta(days=1))} to {_day(s['to'])}",
            label=(s.get("label") or NA).rstrip("."),
            role=NA if sh is None else f"{ROLE_NAME.get(main, str(main).title())} {_pct(sh)}%",
            deaths=NA if dph is None else f"{dph:.1f}",
            cooldowns=NA if t.get("cooldowns_share") is None else _pct(t["cooldowns_share"]) + "%"))
    return out


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _works(name: str, c: dict) -> str:
    """"Exorcism works on undead and demons. You fought 37 of them in 12 fights and cast it 0 times." """
    r = usable.RULES[name]
    had = f"You had {c['chances']:,} {r['chance']}" if "after" in r else f"You fought {c['chances']:,} of them"
    return f"{name} works {r['works']}. {had} in {_plural(c['fights'], 'fight')} and cast it 0 times."


def _plate(now: dict) -> Plate:
    """the first rule that applies; none: "Nothing stands out" with the strongest trait, the measure furthest on
    the good side of its own plate threshold (keys against PLATE_CLICKS, cooldowns against PLATE_COOLDOWNS,
    deaths per fight against PLATE_DEATHS), first in that order on a tie"""
    n, h, t = now["fights"], now.get("hands") or {}, now["temperament"]
    fights = f"in your last {_plural(n, 'fight')}"
    runs = _plural(h.get("runs") or 0, "recorded run")
    clicks, cds, unused = h.get("click_share"), t.get("cooldowns_share"), now.get("unused")
    dying = t["deaths"] / n if n else None
    if clicks is not None and clicks >= PLATE_CLICKS:
        return Plate("You click instead of pressing keys", f"{_pct(clicks)}% clicks",
                     f"{h['by_click']:,} of {h['by_key'] + h['by_click']:,} presses, in {runs}")
    if cds is not None and cds < PLATE_COOLDOWNS:
        left = t["cooldowns_possible"] - t["cooldowns_used"]
        return Plate("You leave your cooldowns unused", f"{_pct(cds)}% used",
                     f"{t['cooldowns_used']:,} of {t['cooldowns_possible']:,} possible, {fights}",
                     f"{_plural(left, 'use')} of a ready cooldown went unspent.")
    if unused:
        names, one = unused[:3], len(unused[:3]) == 1
        top = [s["name"] for s in sorted(now["signature"]["spells"], key=lambda s: -s["casts"])[:3]]
        carry = f"{_and(top)} {'carries' if len(top) == 1 else 'carry'} your casts. " if top else ""
        met = now.get("restricted") or {}
        free = [x for x in names if x not in met]
        bench = (f"{_and(free)} {'is the harmful spell' if len(free) == 1 else 'are the harmful spells'} left on "
                 "the bench." if free else "")
        works = " ".join(_works(x, met[x]) for x in names if x in met)
        return Plate(f"You know {_and(names)} and have never cast {'it' if one else 'them'}", "0 casts", fights,
                     " ".join(w.strip() for w in (carry, bench, works) if w))
    if dying is not None and dying >= PLATE_DEATHS:
        return Plate(f"You die in {_pct(dying)}% of your fights", _plural(t["deaths"], "death"), fights,
                     f"{t['deaths']} of your last {n} fights ended with you dead.")
    best = []
    if clicks is not None:
        best.append((PLATE_CLICKS - clicks, f"{_pct(h['key_share'])}% keys", f"of your presses, in {runs}"))
    if cds is not None:
        best.append((cds - PLATE_COOLDOWNS, f"{_pct(cds)}% cooldowns used",
                     f"{t['cooldowns_used']:,} of {t['cooldowns_possible']:,} possible"))
    if dying is not None:
        best.append((PLATE_DEATHS - dying, _plural(t["deaths"], "death"), fights))
    _, figure, caption = max(best, key=lambda b: b[0]) if best else (0, NA, fights)
    return Plate("Nothing stands out", figure, caption)


def build_profile(p: dict, earlier: list[dict]) -> ProfileView:
    """the page for live.profile.profile(...)'s result and this character's saved slices"""
    now, before = p.get("now"), p.get("before")
    n = now["fights"] if now else 0
    v = ProfileView(title=p.get("name") or "Profile", earlier=_earlier(earlier),
                    meta=_meta({"char": p.get("char"), "level": p.get("level")}, f"last 15 days · {_plural(n, 'fight')}"))
    v.earlier_title = f"Earlier ({len(v.earlier)})"
    if n < MIN_FIGHTS:
        v.need = f"Your profile needs {MIN_FIGHTS} fights from the last 15 days ({n} so far)."
        v.need_line = "Play a few more fights and it fills in. Who you were in earlier slices is below."
        return v
    moves = []      # (row, points, highlighter note) for every share row that got a chip, in page order

    def share(row: Row, key, up: str, down: str) -> Row:
        """a share row's chip (and highlighter candidacy): key(figures) is the share, Now against Before; the
        points are the difference of the displayed (rounded) figures"""
        a, b = key(now), key(before) if before else None
        if a is not None and b is not None and abs(d := int(_pct(a)) - int(_pct(b))) >= CHIP_MIN:
            row.chip = f"{'+' if d > 0 else MINUS}{abs(d)} vs the 15 days before"
            moves.append((row, d, up if d > 0 else down))
        return row

    main = now["main_role"]
    if main:
        v.hero, v.caption = _pct(now["roles"][main]), f"of fight time {DOING[main]}"
    else:
        v.hero_unit, v.caption = "", "no fight time in these fights"
    v.label = now["label"]
    if before and before["label"] != now["label"]:
        v.before = f"Before: {_lower(before['label'])}"
    v.plate = _plate(now)

    sig = now["signature"]
    casts = sig["basis"] == "casts"
    v.sig_header = "share of your casts" if casts else "share of your damage"
    v.spells_header = "share of casts" if casts else "share of damage"
    def name_count(s) -> tuple[str, str]:
        """Melee shows as auto attack with its swings (none shown when not every fight saved a count)"""
        if s["name"] != "Melee":
            return s["name"], f"{s['casts']:,}"
        swings = s.get("swings")
        return MELEE, "" if swings is None else f"{swings:,} swings"

    for s in sig["top"]:
        has = bool(s["share"])
        name, count = name_count(s)
        v.signature.append(Row(name, _pct(s["share"]) if has else NA, "%" if has else "", ink="m-dmg",
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
        g = lambda k: lambda f: (f.get("hands") or {}).get(k)  # noqa: E731
        ks, cut = h["key_share"], h.get("cut_share")
        v.hands = [
            share(Row("Keys or clicks", _pct(ks), "% keys" if ks is not None else "",
                      f"{h['by_click']:,} clicks in {h['by_key'] + h['by_click']:,} presses, in {runs}"),
                  g("key_share"), "more keys", "more clicks"),
            Row("Presses per minute", NA if h["per_minute"] is None else f"{h['per_minute']:.1f}",
                note=f"over {_hm(combat)} of combat in recorded runs", ink="m-act"),
            share(Row("Refused presses", _pct(h["refused_share"]), "%" if h["refused_share"] is not None else "",
                      f"{h['failed']:,} presses the game turned down, in recorded runs", ink="m-cast"),
                  g("refused_share"), "more refused", "fewer refused"),
            share(Row("Cut short by moving", _pct(cut), "%" if cut is not None else "",
                      "no cut casts saved in these runs" if h.get("move_interrupts") is None else
                      f"{h['move_interrupts']:,} of {h['move_casts']:,} casts cut because you started to move, "
                      f"{h['wasted_cast_time']:.1f} s of cast time lost, in {_plural(h['move_runs'], 'recorded run')}",
                      ink="m-cast"),
                  g("cut_share"), "more cut short", "fewer cut short")]
    else:
        v.hands = [Row("Keys, clicks and presses", note=NO_HANDS)]

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

    places = now["places"]
    for place in sorted(places, key=lambda k: -(places[k] or 0)):
        sh = places[place]
        v.places.append(share(Row(place, _pct(sh), "%" if sh is not None else "", ink=PLACE_INK[place], bar=sh),
                              lambda f, k=place: f["places"][k], *PLACE_MOVE[place]))

    t = now["temperament"]
    dph, pull, low, cds = t["deaths_per_hour"], t["median_pull"], t["lowest_hp"], t["cooldowns_share"]
    v.temperament = [
        Row("Deaths per hour", NA if dph is None else f"{dph:.1f}", ink="m-surv",
            note=f"{_plural(t['deaths'], 'death')} in {_plural(n, 'fight')}, {_hm(now['seconds'])} of fighting"),
        Row("Usual pull", NA, note="no pull size saved in these fights") if pull is None else
        Row("Usual pull", f"{pull:g}", "enemy" if pull == 1 else "enemies",
            f"alone in {t['alone']} of {n} fights, {t['mean_pull']:.1f} on average"),
        Row("Average lowest health", _pct(low), "%" if low is not None else "",
            "the lowest you dropped, over " + _plural(n, "fight") if low is not None else "no health saved",
            ink="m-surv"),
        share(Row("Cooldowns used", NA, ink="m-cd", note="no cooldown with a known count in these fights")
              if cds is None else
              Row("Cooldowns used", _pct(cds), "%", f"{t['cooldowns_used']:,} of {t['cooldowns_possible']:,} "
                  f"possible, in {_plural(n, 'fight')}", ink="m-cd"),
              lambda f: f["temperament"]["cooldowns_share"], "more cooldowns", "fewer cooldowns")]

    if moves:       # the largest move; max keeps the first in page order on a tie
        row, _, note = max(moves, key=lambda m: abs(m[1]))
        row.mark = note
    return v
