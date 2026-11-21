"""Loading runs from disk and analyzing them - shared by the command line and the window.

Saved runs that are pieces of one visit (a /reload, or stopping and starting the recording) are
merged first: same dungeon, the next piece starting within MERGE_GAP of the last one ending.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from .config import Paths
from .model.casts import CastEvent, pets_of, player_casts
from .model.deaths import Death, Wipe, find_deaths
from .model.pulls import Enemy, Pull, build_pulls
from .model.roster import Overrides, Player, build_roster
from .model.run import Fight, RunData, build
from .model.summary import Summary, summarize
from .live.history import History
from .scoring.cooldowns import CooldownMetrics, measure_cooldowns
from .scoring.group import damage_share, group_data, rank_group
from .scoring.radar import radars
from .scoring.healer import HealerMetrics, healer_base, measure_healer
from .scoring.interrupts import InterruptMetrics, interrupt_base, measure_interrupts
from .scoring.metrics import Metrics, measure
from .scoring.pacing import PacingMetrics, measure_pacing
from .scoring.positioning import PositionMetrics, measure_positioning, position_base
from .scoring.score import Scorecard, score
from .scoring.upkeep import UpkeepMetrics, measure_upkeep, upkeep_base
from .scoring.tank import TankMetrics, measure_tank, tank_base
from .sources import combatlog
from .sources.savedvars import Run, load_char, load_runs

DEFAULT_ROLE = "healer"
MERGE_GAP = 15 * 60


@dataclass
class FightResult:
    fight: Fight
    metrics: Metrics
    healer: HealerMetrics
    card: Scorecard
    tank: TankMetrics | None = None   # only when scored as a tank
    damage: tuple[int, float] | None = None       # dps/tank: yours, and its share of an even split (None: solo)
    interrupts: InterruptMetrics | None = None    # dps/tank
    cooldowns: CooldownMetrics | None = None      # dps/tank
    upkeep: UpkeepMetrics | None = None           # dps/tank
    positioning: PositionMetrics | None = None


@dataclass
class Analysis:
    data: RunData
    role: str
    metrics: Metrics
    healer: HealerMetrics
    card: Scorecard
    fights: list[FightResult]
    roster: dict[str, Player] = field(default_factory=dict)
    pulls: list[Pull] = field(default_factory=list)
    loose_enemies: list[Enemy] = field(default_factory=list)
    deaths: list[Death] = field(default_factory=list)
    wipes: list[Wipe] = field(default_factory=list)
    casts: dict[str, list[CastEvent]] = field(default_factory=dict)
    pets: dict[str, set[str]] = field(default_factory=dict)
    summary: Summary | None = None
    group: object = None             # scoring.group.GroupData
    ranking: list = field(default_factory=list)   # scoring.group.Placing, best first
    radars: dict = field(default_factory=dict)    # guid -> scoring.radar.Radar
    tank: TankMetrics | None = None               # only when scored as a tank
    damage: tuple[int, float] | None = None       # dps/tank: yours, and its share of an even split (None: solo)
    interrupts: InterruptMetrics | None = None    # dps/tank
    cooldowns: CooldownMetrics | None = None      # dps/tank
    upkeep: UpkeepMetrics | None = None           # dps/tank
    positioning: PositionMetrics | None = None
    pacing: PacingMetrics | None = None

    @property
    def me(self) -> Player | None:
        g = self.data.player_guid
        return self.roster.get(g) if g else None


# A run reads the log from its start to its end (plus 10 s). A log written to this long after the run ended already
# holds all of that on disk, so the game's later writes to it can't change the run.
SETTLED_S = 120


def run_key(run: Run, logs: list[Path], picks: float) -> tuple:
    """what a run's analysis depends on: the run as saved, the combat logs (each by its last write, until the run's
    part of it is final) and your role picks"""
    done = run.end_estimate + SETTLED_S
    files = tuple((p.name, t if (t := p.stat().st_mtime) <= done else "settled") for p in logs)
    return (run.id, run.line_count, files, picks)


def merge_visits(runs: list[Run]) -> list[Run]:
    """Pieces of the same visit, joined. Oldest first."""
    out: list[Run] = []
    for r in sorted(runs, key=lambda r: r.started):
        prev = out[-1] if out else None
        if (prev and r.kind != "world" and prev.kind == r.kind and prev.instance_id == r.instance_id
                and prev.zone == r.zone and 0 <= r.started - prev.end_estimate <= MERGE_GAP):
            out[-1] = replace(prev, segments=prev.segments + r.segments, ended=r.ended,
                              parts=prev.parts + [r.id])
        else:
            out.append(replace(r, segments=list(r.segments), parts=[r.id]))
    return out


def dungeons(runs: list[Run]) -> dict[str, list[Run]]:
    """zone -> its visits, newest first; zones by their latest visit"""
    by: dict[str, list[Run]] = {}
    for r in runs:
        by.setdefault(r.zone if r.kind != "world" else "Open world", []).append(r)
    for v in by.values():
        v.sort(key=lambda r: r.started, reverse=True)
    return dict(sorted(by.items(), key=lambda kv: kv[1][0].started, reverse=True))


def load_saved(paths: Paths, saved: Path | None = None, merge: bool = True) -> tuple[Path | None, list[Run]]:
    files = [saved] if saved else paths.saved_files()
    if not files:
        return None, []
    runs = [r for r in load_runs(files[0]) if r.line_count > 1]
    return files[0], (merge_visits(runs) if merge else runs)


def rescore(a: Analysis):
    """Score again with the weights in use now (after they were changed): the measuring stays."""
    a.card = score(a.metrics, a.role, a.healer, a.tank, a.damage, a.interrupts, a.cooldowns, a.upkeep, a.positioning,
                   a.pacing)
    for fr in a.fights:   # no Pacing: one pull per fight would score only 0 or 100
        fr.card = score(fr.metrics, a.role, fr.healer, fr.tank, fr.damage, fr.interrupts, fr.cooldowns, fr.upkeep, fr.positioning)
    if a.group is not None:
        a.ranking = rank_group(a)


def role_of(p: Player | None) -> str:
    if p is None or p.role is None:
        return DEFAULT_ROLE      # no combat log to tell from
    return {"HEALER": "healer", "TANK": "tank"}.get(p.role, "dps")


def your_char(paths: Paths, me: str | None) -> dict | None:
    """the add-on's character snapshot for `me`, from whichever saved file holds it"""
    for path in paths.saved_files() if me else []:
        try:
            char = load_char(path)
        except (OSError, ValueError):       # a half-written file
            continue
        if char and char["guid"] == me:
            return char
    return None


def analyze(run: Run, paths: Paths, role: str | None = None) -> Analysis:
    rd = build(run, combatlog.find_logs(paths.logs))
    roster = build_roster(rd.events, [ln for ln in rd.lines if ln.code == "P"], rd.player_guid,
                          Overrides(paths.roster_file), your_char(paths, rd.player_guid))
    role = role or role_of(roster.get(rd.player_guid or ""))
    deaths, wipes = find_deaths(rd, roster)
    base = healer_base(rd, [(d.t, d.name) for d in deaths])
    pulls, loose = build_pulls(rd, roster)
    tb = tank_base(rd, pulls, [d.t for d in deaths if d.guid == rd.player_guid]) if role == "tank" else None
    m, hm = measure(rd), measure_healer(rd, base=base)
    tm = measure_tank(rd, base=tb) if tb else None
    fights = []
    for f in rd.fights:
        w = [(f.start, f.end)]
        fm, fh = measure(rd, w), measure_healer(rd, w, base)
        ft = measure_tank(rd, w, tb) if tb else None
        fights.append(FightResult(f, fm, fh, score(fm, role, fh, ft), ft))
    pets = pets_of(rd, roster)
    a = Analysis(rd, role, m, hm, score(m, role, hm, tm), fights, roster, pulls, loose, deaths, wipes,
                 player_casts(rd, roster), pets, summarize(rd, roster, pulls, deaths, pets, len(wipes)), tank=tm)
    a.group = group_data(a)
    me = rd.player_guid
    if role in ("dps", "tank") and rd.has_combat_log:   # these need the group data, so they come last
        ib = interrupt_base(rd, {me, *pets.get(me, ())})
        solo = len(roster) < 2 or me not in roster

        def extras(w):
            return (None if solo else damage_share(a.group, roster, me, w)), measure_interrupts(rd, w, ib)
        a.damage, a.interrupts = extras([(f.start, f.end) for f in rd.fights])
        for fr in fights:
            fr.damage, fr.interrupts = extras([(fr.fight.start, fr.fight.end)])
        # your spell book the live view learned (spells.json); History also reads the fights file
        ub = upkeep_base(rd, roster[me].cls if me in roster else None)
        a.upkeep = measure_upkeep(rd, base=ub)
        for fr in fights:
            fr.upkeep = measure_upkeep(rd, [(fr.fight.start, fr.fight.end)], ub)
        a.cooldowns, per_fight = measure_cooldowns(rd, History(paths).book(me))
        for fr, cm in zip(fights, per_fight):
            fr.cooldowns = cm
    if rd.has_combat_log:   # every role
        pb = position_base(rd, next((g for g, p in roster.items() if p.role == "TANK" and g != me), None))
        a.positioning = measure_positioning(rd, base=pb)
        for fr in fights:
            fr.positioning = measure_positioning(rd, [(fr.fight.start, fr.fight.end)], pb)
        a.pacing = measure_pacing(rd, pulls, me)
    rescore(a)   # with the extras (also ranks the group)
    a.radars = radars(a)
    return a
