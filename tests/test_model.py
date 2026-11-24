"""Tests for the roster, visits, deaths and pulls, on small made-up logs."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.analysis import dungeons, merge_visits, run_key  # noqa: E402
from dips_score.model.deaths import find_deaths  # noqa: E402
from dips_score.model.pulls import build_pulls  # noqa: E402
from dips_score.model.roster import Overrides, Player, build_roster, clean_name  # noqa: E402
from dips_score.model.run import Fight, RunData  # noqa: E402
from dips_score.scoring.group import ordinal  # noqa: E402
from dips_score.sources.combatlog import Event  # noqa: E402
from dips_score.sources.savedvars import Line, Run, Segment  # noqa: E402

T0 = datetime(2026, 11, 16, 21, 0, 0)
ME, TANK, HUNTER = "Player-1-A", "Player-1-B", "Player-1-C"
MOB1, MOB2, MOB3 = ("Creature-0-1-1-1-100-%d" % i for i in (1, 2, 3))
NAMES = {ME: "Nikana-Diploidian-PvP-US", TANK: "Priime-Tiime-PvP-US", HUNTER: "The-Kommando-PvP-US",
         MOB1: "Grunt", MOB2: "Grunt", MOB3: "Outrider"}
FLAGS = {ME: 0x511, TANK: 0x512, HUNTER: 0x512, MOB1: 0xa48, MOB2: 0xa48, MOB3: 0xa48}


def ev(sec, event, src="", dst="", spell="", amount=0, raid_dst=0):
    return Event(T0 + timedelta(seconds=sec), event, src, NAMES.get(src, ""), FLAGS.get(src, 0),
                 dst, NAMES.get(dst, ""), FLAGS.get(dst, 0), 0, raid_dst, 1 if spell else None, spell,
                 amount=amount)


def rundata(events, fights):
    run = Run("1", "Nikana - X", "Somewhere", "party", 1, 1, int(T0.timestamp()), None)
    rd = RunData(run, T0, T0 + timedelta(seconds=300), [], events, ME, [])
    rd.fights = fights
    return rd


class Names(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(clean_name("Priime-Tiime-PvP-US"), "Priime Tiime")
        self.assertEqual(clean_name("Bob-Stormrage"), "Bob")
        self.assertEqual(clean_name("Solo"), "Solo")


class TalentRole(unittest.TestCase):
    events = [ev(1, "SPELL_DAMAGE", ME, MOB1, "Smite", 100), ev(1, "SPELL_DAMAGE", TANK, MOB1, "Smite", 100)]
    holy = {"guid": ME, "class": "PALADIN", "talents": [("Holy", 31), ("Protection", 5), ("Retribution", 0)]}

    def role(self, char, p_role=None, pick=None, guid=ME):
        lines = [Line(0, "P", [ME, "Nikana", "PALADIN", p_role, ""])] if p_role else []
        picks = Overrides(None)
        if pick:
            picks.set(ME, role=pick)
        p = build_roster(self.events, lines, ME, picks, char)[guid]
        return p.role, p.role_from

    def test_order(self):
        self.assertEqual(self.role(self.holy), ("HEALER", "talents"))                   # talents beat the guess
        self.assertEqual(self.role(None), ("DPS", "spells"))
        self.assertEqual(self.role(self.holy, "NONE"), ("HEALER", "talents"))
        self.assertEqual(self.role(self.holy, "TANK"), ("TANK", "addon"))               # the P line beats talents
        self.assertEqual(self.role(self.holy, "TANK", "DPS"), ("DPS", "you"))           # your pick beats the P line

    def test_falls_through(self):
        tie = {**self.holy, "talents": [("Holy", 10), ("Retribution", 10)]}
        feral = {"guid": ME, "class": "DRUID", "talents": [("Balance", 0), ("Feral Combat", 30)]}
        self.assertEqual(self.role(tie), ("DPS", "spells"))
        self.assertEqual(self.role(feral), ("DPS", "spells"))
        self.assertEqual(self.role({**self.holy, "talents": []}), ("DPS", "spells"))

    def test_only_yours(self):
        self.assertEqual(self.role(self.holy, guid=TANK), ("DPS", "spells"))
        self.assertEqual(self.role({**self.holy, "guid": TANK}), ("DPS", "spells"))      # someone else's snapshot


class Visits(unittest.TestCase):
    def test_merges_close_pieces_of_same_place(self):
        def run(i, start, zone="Krol", inst=3039, ended=None):
            return Run(str(i), "x", zone, "party", 1, inst, start, ended, [Segment(0, [], [Line(60000, "X", [])])])
        out = merge_visits([run(1, 1000, ended=1100), run(2, 1200, ended=1300), run(3, 9000), run(4, 9100, "SM", 2)])
        self.assertEqual([r.parts for r in out], [["1", "2"], ["3"], ["4"]])
        self.assertEqual(len(out[0].segments), 2)

    def test_a_deleted_piece_is_skipped_before_merging(self):
        """the piece after a deleted one is a visit of its own, not merged into it"""
        from unittest import mock
        from dips_score import removed
        from dips_score.analysis import load_saved
        from dips_score.config import Paths
        self.addCleanup(removed.IDS.clear)
        seg = lambda: [Segment(0, [], [Line(0, "X", []), Line(60000, "X", [])])]     # noqa: E731
        runs = [Run("1", "x", "Krol", "party", 1, 3039, 1000, 1100, seg()),
                Run("2", "x", "Krol", "party", 1, 3039, 1200, 1300, seg())]
        removed.IDS.add("1")
        with mock.patch("dips_score.analysis.load_runs", return_value=runs):
            _, out = load_saved(Paths(Path("no game")), saved=Path("dips-Score.lua"))
        self.assertEqual([r.parts for r in out], [["2"]])

    def test_dungeons_and_raids_apart(self):
        """raids go under Raids; dungeons and the open world under Dungeons"""
        runs = [Run("1", "x", "SM", "party", 1, 2, 1000, None), Run("2", "x", "Molten Core", "raid", 1, 4, 2000, None),
                Run("3", "x", "Kalimdor", "world", 1, 1, 3000, None)]
        self.assertEqual(list(dungeons(runs)), ["Open world", "SM"])
        self.assertEqual(list(dungeons(runs, raid=True)), ["Molten Core"])

    def test_ordinal_for_raid_sizes(self):
        self.assertEqual([ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 40)],
                         ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "23rd", "40th"])

    def test_run_key_ignores_writes_after_the_run_is_on_disk(self):
        """the game writing its log after a run is over doesn't make the run look new (nor drop its rail score);
        a write while the run's part of the log may still be arriving does"""
        import os
        import tempfile
        run = Run("1", "x", "Krol", "party", 1, 3039, 1_000_000, 1_000_600)          # ended at 1,000,600
        with tempfile.TemporaryDirectory() as tmp:
            log, old = Path(tmp) / "WoWCombatLog.txt", Path(tmp) / "WoWCombatLog-old.txt"
            log.write_text("x")
            old.write_text("x")
            os.utime(old, (900_000, 900_000))                       # finished long before the run
            key = lambda: run_key(run, [old, log], 0)              # noqa: E731
            os.utime(log, (1_000_650, 1_000_650))                   # 50 s after the end: may still be arriving
            first = key()
            os.utime(log, (1_000_700, 1_000_700))
            self.assertNotEqual(key(), first)
            os.utime(log, (1_000_900, 1_000_900))                   # past the settle time: the run's part is final
            settled = key()
            os.utime(log, (1_005_000, 1_005_000))                   # the game keeps writing
            self.assertEqual(key(), settled)
            self.assertEqual(settled[2][0], ("WoWCombatLog-old.txt", 900_000))
            self.assertNotEqual(run_key(run, [old, log], 5.0), settled)       # a role pick still counts
            grown = Run("1", "x", "Krol", "party", 1, 3039, 1_000_000, 1_000_600,
                        [Segment(0, [], [Line(60000, "X", [])])])
            self.assertNotEqual(run_key(grown, [old, log], 0), settled)        # the game saved more of the run


class Deaths(unittest.TestCase):
    def test_real_death_and_feign(self):
        events = [
            ev(10, "SWING_DAMAGE", MOB1, TANK, amount=500),
            ev(11, "UNIT_DIED", "", TANK),                          # real: does nothing after
            ev(20, "UNIT_DIED", "", HUNTER),                        # feign: shoots 3 s later
            ev(23, "RANGE_DAMAGE", HUNTER, MOB1, "Auto Shot", 100),
        ]
        roster = {g: Player(g, clean_name(NAMES[g])) for g in (ME, TANK, HUNTER)}
        deaths, wipes = find_deaths(rundata(events, []), roster)
        self.assertEqual([d.name for d in deaths], ["Priime Tiime"])
        self.assertEqual(deaths[0].killed_by, "Melee (Grunt)")
        self.assertEqual(wipes, [])

    def test_wipe_when_everyone_is_dead(self):
        events = [ev(5, "UNIT_DIED", "", g) for g in (ME, TANK, HUNTER)]
        roster = {g: Player(g, NAMES[g]) for g in (ME, TANK, HUNTER)}
        _, wipes = find_deaths(rundata(events, [Fight(0, 10)]), roster)
        self.assertEqual(len(wipes), 1)
        self.assertEqual(len(wipes[0].deaths), 3)


class Pulls(unittest.TestCase):
    def test_packs_puller_marker_and_kills(self):
        events = [
            ev(100, "SPELL_CAST_SUCCESS", TANK, MOB1, "Charge", raid_dst=0x80),
            ev(101, "SPELL_DAMAGE", TANK, MOB2, "Thunder Clap", 50),
            ev(110, "SWING_DAMAGE", MOB3, HUNTER, amount=80),        # a second pack, body pulled
            ev(120, "SPELL_DAMAGE", ME, MOB1, "Mind Blast", 400),
            ev(120, "PARTY_KILL", ME, MOB1),
            ev(120.01, "UNIT_DIED", "", MOB1),
        ]
        roster = build_roster(events, [], ME)
        pulls, loose = build_pulls(rundata(events, [Fight(102, 140)]), roster)
        packs = pulls[0].packs
        self.assertEqual(len(packs), 2)
        self.assertEqual((packs[0].puller, packs[0].how, packs[0].extra), (TANK, "Charge", False))
        self.assertEqual((packs[1].puller, packs[1].how, packs[1].extra), (HUNTER, "body pull", True))
        mob1 = packs[0].enemies[0]
        self.assertEqual(mob1.marker, "Skull")
        self.assertEqual((mob1.killer, mob1.killing_blow), (ME, "Mind Blast"))
        self.assertEqual(loose, [])


class AdvancedLogging(unittest.TestCase):
    """a healer run with and without the Advanced Combat Logging block"""
    def card(self, advanced):
        from dips_score.scoring.healer import measure_healer
        from dips_score.scoring.score import _card, healer_categories, hybrid_bonus
        from dips_score.sources.combatlog import UnitInfo
        hit = ev(10, "SWING_DAMAGE", MOB1, TANK, amount=500)
        if advanced:
            hit.info = UnitInfo(TANK, 400, 1000, 0, 0, 0, 0.0, 0.0, 0, 0.0, 60)   # tank dips to 40%
        events = [hit, ev(10.5, "SPELL_CAST_START", ME, TANK, "Flash Heal"),
                  ev(12, "SPELL_HEAL", ME, TANK, "Flash Heal", 300),
                  ev(15, "SPELL_DAMAGE", ME, MOB1, "Smite", 400)]
        rd = rundata(events, [Fight(0, 30)])
        self.assertEqual(rd.has_advanced, advanced)
        hm = measure_healer(rd)
        cats = healer_categories(hm)
        bonus, note = hybrid_bonus(hm, cats)
        return {c.name: c for c in cats}, bonus, _card(cats, "healer", bonus, note)

    def test_without_advanced(self):
        cats, bonus, card = self.card(False)
        self.assertTrue(cats["Group health"].unavailable and cats["Response"].unavailable)
        self.assertTrue(cats["Response"].info_only)
        self.assertEqual(bonus, 0)
        self.assertFalse(cats["Efficiency"].unavailable)
        self.assertEqual(card.total, cats["Efficiency"].score)   # only Efficiency counted

    def test_with_advanced(self):
        cats, bonus, card = self.card(True)
        self.assertFalse(cats["Group health"].unavailable or cats["Response"].unavailable)
        self.assertTrue(cats["Response"].summary.startswith("1 dips"))
        self.assertEqual(cats["Response"].score, 100)
        self.assertGreater(bonus, 0)


class Pickups(unittest.TestCase):
    """a tank run: a mob turns to the healer (ME) and comes back, or doesn't"""
    def tank(self, *events):
        from dips_score.scoring.tank import measure_tank, tank_base
        rd = rundata([ev(10, "SWING_DAMAGE", MOB1, TANK, amount=100), *events], [Fight(0, 60)])
        return measure_tank(rd, base=tank_base(rd, [], [], TANK))

    def test_picked_up(self):
        tm = self.tank(ev(12, "SWING_DAMAGE", MOB1, ME, amount=100), ev(14, "SWING_MISSED", MOB1, TANK))
        self.assertEqual(len(tm.judged), 1)
        self.assertAlmostEqual(tm.judged[0].response, 2.0)
        self.assertEqual(tm.missed, 0)

    def test_never_back_is_a_miss(self):
        tm = self.tank(ev(12, "SWING_DAMAGE", MOB1, ME, amount=100), ev(25, "SWING_DAMAGE", MOB1, TANK, amount=100))
        self.assertEqual((len(tm.judged), tm.missed), (1, 1))

    def test_spell_on_someone_else_is_not_a_loss(self):
        tm = self.tank(ev(12, "SPELL_DAMAGE", MOB1, ME, "Fire Nova", 100))
        self.assertEqual(tm.losses, [])

    def test_mob_died_first_is_left_out(self):
        tm = self.tank(ev(12, "SWING_DAMAGE", MOB1, ME, amount=100), ev(14, "UNIT_DIED", "", MOB1))
        self.assertEqual((len(tm.losses), len(tm.judged), tm.missed), (1, 0, 0))

    def test_tank_card(self):
        from dips_score.scoring.metrics import Metrics
        from dips_score.scoring.score import score
        tm = self.tank(ev(12, "SWING_DAMAGE", MOB1, ME, amount=100), ev(14, "SWING_DAMAGE", MOB1, TANK, amount=100))
        card = score(Metrics(combat_time=60, has_log=True), "tank", tm=tm)
        self.assertEqual(card.role, "tank")
        self.assertEqual([c.name for c in card.categories],
                         ["Holding mobs", "Pickups", "Survival", "Activity", "Casting", "Input", "Movement",
                          "Interrupts"])
        self.assertTrue(card.categories[-1].info_only)   # weight 0 for a tank

    def test_weights_without_tank_key(self):
        import json
        import tempfile
        from dips_score.scoring import score
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "weights.json"
            path.write_text(json.dumps({"healer": {"Response": 50}, "dps": {}}), encoding="utf-8")
            score.load_weights(path)
        try:
            self.assertEqual(score.WEIGHTS["healer"]["Response"], 50)
            self.assertEqual(score.WEIGHTS["tank"], score.DEFAULT_WEIGHTS["tank"])
        finally:
            score.reset_weights()


def me_info(event, power_type, power, cost=0):
    """event with your Advanced Combat Logging block on it"""
    from dips_score.sources.combatlog import UnitInfo
    event.info = UnitInfo(ME, 1000, 1000, power_type, power, 100, 0.0, 0.0, 0, 0.0, 60, cost)
    return event


class Activity(unittest.TestCase):
    """melee swings, the energy GCD, waiting for rage, and casters left as they were"""
    def measure(self, events, lines=()):
        from dips_score.model.run import TLine
        from dips_score.scoring.metrics import measure
        rd = rundata(events, [Fight(0, 60)])
        rd.lines = [TLine(t, code, [str(sid)], 0) for t, code, sid in lines]
        return measure(rd)

    def swings(self, skip=lambda t: False):
        return [ev(t, "SWING_DAMAGE", ME, MOB1, amount=50) for t in range(0, 60, 2) if not skip(t)]

    def test_melee_swings_are_busy(self):
        from dips_score.scoring.score import score_dps
        m = self.measure(self.swings())
        self.assertAlmostEqual(m.uptime, 1.0)
        self.assertEqual((m.swings, m.swings_lost, m.swing_speed), (30, 0, 2.0))
        cats = {c.name: c for c in score_dps(m).categories}
        self.assertTrue(cats["Movement"].info_only)    # melee: no cast to cut
        self.assertIn("30 swings, 0 lost", cats["Activity"].summary)

    def test_melee_hit_table(self):
        miss = ev(59, "SWING_MISSED", ME, MOB1)
        miss.miss_type = "PARRY"
        taken = ev(5, "SWING_DAMAGE", MOB1, ME, amount=30)
        extra = ev(7, "SPELL_EXTRA_ATTACKS", ME, ME, "Windfury Attack")
        extra.extra_count = 1
        m = self.measure(self.swings() + [miss, taken, extra])
        self.assertEqual((m.melee["landed"], m.melee["misses"]), (30, {"parry": 1}))
        self.assertEqual((m.swings_taken["landed"], m.extra_attacks), (1, {"Windfury Attack": 1}))
        self.assertEqual(m.ranged["landed"], 0)

    def test_hole_in_swings(self):
        m = self.measure(self.swings(lambda t: 20 < t < 30))   # 20 then 30: a 10 s hole
        self.assertEqual(m.swings_lost, 4)
        self.assertEqual(m.idle_gaps, [(22.0, 30.0)])

    def test_energy_gcd(self):
        info = [me_info(ev(5, "SPELL_ENERGIZE", ME, ME), 3, 50)]
        self.assertAlmostEqual(self.measure(info, [(10, "CK", 9)]).busy_time, 1.0)
        self.assertAlmostEqual(self.measure([], [(10, "CK", 9)]).busy_time, 1.5)

    def test_waiting_for_rage(self):
        events = [me_info(ev(5, "SPELL_CAST_SUCCESS", ME, MOB1, "Heroic Strike"), 1, 30, cost=10),
                  me_info(ev(20, "SPELL_ENERGIZE", ME, ME), 1, 2),
                  me_info(ev(24, "SPELL_ENERGIZE", ME, ME), 1, 5),
                  me_info(ev(28, "SPELL_ENERGIZE", ME, ME), 1, 40)]
        m = self.measure(events)
        self.assertEqual(m.power_type, 1)
        self.assertAlmostEqual(m.starved_time, 8.0)
        self.assertAlmostEqual(m.uptime, 8 / 60)
        self.assertEqual(m.idle_gaps, [(0.0, 20.0), (28.0, 60.0)])

    def test_mana_caster_unchanged(self):
        # an instant at 2 (1.5 s GCD) and a 2.5 s cast from 5: 4 s busy of 60, even out of mana
        events = [me_info(ev(1, "SPELL_CAST_SUCCESS", ME, MOB1, "Smite"), 0, 0, cost=100)]
        m = self.measure(events, [(2, "CK", 9), (5, "CB", 7), (7.5, "CK", 7)])
        self.assertEqual((m.power_type, m.starved_time, m.swings), (0, 0.0, 0))
        self.assertAlmostEqual(m.uptime, 4.0 / 60)

    def test_pooling_refusals(self):
        from collections import Counter
        from dips_score.scoring.metrics import Metrics
        from dips_score.scoring.score import score_dps

        def casting(power_type):
            m = Metrics(combat_time=60, casts=20, failed=5, fail_reasons=Counter({"Not enough energy": 5}),
                        power_type=power_type)
            return next(c for c in score_dps(m).categories if c.name == "Casting")
        energy = casting(3)
        self.assertEqual(energy.score, 100)
        self.assertIn("Not enough energy x5", energy.summary)
        self.assertLess(casting(0).score, 100)


class SpellTable(unittest.TestCase):
    def test_damage_counts_enemies_only(self):
        """as the Group and the summary count damage: a hit on a friend or a neutral creature isn't yours"""
        from dips_score.model.casts import spell_table
        neutral = "Creature-0-1-1-1-100-9"          # no flags: not hostile
        rd = rundata([ev(10, "SPELL_DAMAGE", ME, MOB1, "Consecration", 100),
                      ev(11, "SPELL_DAMAGE", ME, TANK, "Consecration", 30),
                      ev(12, "SPELL_DAMAGE", ME, neutral, "Consecration", 50)], [])
        self.assertEqual([(r.spell, r.damage, r.hits) for r in spell_table(rd, ME)], [("Consecration", 100, 1)])


class DpsDamage(unittest.TestCase):
    def test_share_of_even(self):
        from dips_score.scoring.group import GroupData, damage_share
        from dips_score.scoring.metrics import Metrics
        from dips_score.scoring.score import score_dps
        g = GroupData(damage={ME: [(10, 600)], TANK: [(10, 400)]})
        mine, rel = damage_share(g, {ME: None, TANK: None}, ME, [(0, 60)])
        self.assertEqual((mine, rel), (600, 1.2))
        m = Metrics(combat_time=60, has_log=True)

        def dmg(share):
            return next(c for c in score_dps(m, share).categories if c.name == "Damage")
        self.assertGreater(dmg((600, 1.2)).score, dmg((500, 1.0)).score)

    def test_solo(self):
        from dips_score.scoring.metrics import Metrics
        from dips_score.scoring.score import score_dps
        card = score_dps(Metrics(combat_time=60, has_log=True))
        cats = {c.name: c for c in card.categories}
        self.assertTrue(cats["Damage"].unavailable and cats["Interrupts"].unavailable)
        rest = [c for c in card.categories if not c.info_only]
        self.assertAlmostEqual(card.total, sum(c.score * c.weight for c in rest) / sum(c.weight for c in rest))

    def test_weights_without_new_dps_keys(self):
        import json
        import tempfile
        from dips_score.scoring import score
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "weights.json"
            path.write_text(json.dumps({"dps": {"Activity": 30, "Casting": 20}}), encoding="utf-8")
            score.load_weights(path)
        try:
            self.assertEqual(score.WEIGHTS["dps"]["Activity"], 30)
            self.assertEqual((score.WEIGHTS["dps"]["Damage"], score.WEIGHTS["dps"]["Resource"]), (20, 5))
        finally:
            score.reset_weights()


def sp(sec, event, src, dst, spell, sid, extra=None, aura=""):
    """ev with a spell id (and the spell it stopped or removed, and the aura type)"""
    e = ev(sec, event, src, dst, spell)
    e.spell_id, e.extra_spell_id, e.aura_type = sid, extra, aura
    return e


class Interrupts(unittest.TestCase):
    BOLT, NOVA = 100, 200

    def measure(self, *events):
        from dips_score.scoring.interrupts import interrupt_base, measure_interrupts
        rd = rundata(list(events), [Fight(0, 60)])
        return measure_interrupts(rd, base=interrupt_base(rd, {ME}))

    def kick(self, sec, who=ME):
        return sp(sec, "SPELL_INTERRUPT", who, MOB1, "Kick", 1, self.BOLT)

    def bolt(self, sec, event="SPELL_CAST_START"):
        return sp(sec, event, MOB1, TANK, "Shadow Bolt", self.BOLT)

    def test_you_interrupt(self):
        im = self.measure(self.bolt(10), self.kick(11))
        self.assertEqual(len(im.judged), 1)
        self.assertAlmostEqual(im.median_response, 1.0)

    def test_completed_is_a_miss_and_never_kicked_not_judged(self):
        im = self.measure(self.bolt(10), self.kick(11), self.bolt(20), self.bolt(22, "SPELL_CAST_SUCCESS"),
                          sp(30, "SPELL_CAST_START", MOB2, TANK, "Fire Nova", self.NOVA),
                          sp(32, "SPELL_CAST_SUCCESS", MOB2, TANK, "Fire Nova", self.NOVA))
        self.assertEqual((len(im.judged), im.missed), (2, 1))
        self.assertNotIn("Fire Nova", [x.spell for x in im.chances])

    def test_someone_else_is_left_out(self):
        im = self.measure(self.bolt(10), self.kick(11), self.bolt(20), self.kick(21, TANK))
        self.assertEqual((len(im.chances), len(im.judged), im.missed), (2, 1, 0))

    def test_never_interrupted_is_unavailable(self):
        from dips_score.scoring.score import _interrupts
        im = self.measure(self.bolt(10), self.kick(11, TANK))
        self.assertFalse(im.used)
        self.assertTrue(_interrupts(im, 10).unavailable)

    def test_dispels(self):
        from dips_score.scoring.score import _interrupts
        curse = 300
        im = self.measure(sp(10, "SPELL_AURA_APPLIED", MOB1, TANK, "Curse", curse, aura="DEBUFF"),
                          sp(12, "SPELL_DISPEL", ME, TANK, "Dispel", 2, curse),
                          sp(20, "SPELL_AURA_APPLIED", MOB1, TANK, "Curse", curse, aura="DEBUFF"),
                          sp(40, "SPELL_AURA_REMOVED", MOB1, TANK, "Curse", curse))
        d = im.dispel
        self.assertEqual((len(d.judged), d.missed), (2, 1))
        self.assertAlmostEqual(d.median_response, 2.0)
        cat = _interrupts(im, 10)    # no interrupt used: the dispel part alone
        self.assertFalse(cat.unavailable)
        self.assertIn("Curse", cat.tip)


class Phase5(unittest.TestCase):
    """shields only count if they absorb; dispels show in the healer summary"""
    def healer(self, shield_on, advanced=True, absorb=0, dispel=False, reading=TANK):
        from dips_score.scoring.healer import measure_healer
        from dips_score.sources.combatlog import UnitInfo
        hit = ev(10, "SWING_DAMAGE", MOB1, TANK, amount=500)
        events = [hit, ev(0, "SWING_DAMAGE", MOB1, ME, amount=1),
                  sp(10.5, "SPELL_AURA_APPLIED", ME, shield_on, "Shield", 9)]
        if advanced:
            hit.info = UnitInfo(TANK, 400, 1000, 0, 0, 0, 0.0, 0.0, 0, 0.0, 60)   # tank dips to 40%
            r = ev(11, "SWING_DAMAGE", MOB1, TANK, amount=1)
            r.info = UnitInfo(reading, 400, 1000, 0, 0, 0, 0.0, 0.0, 0, 0.0, 60, 0, absorb)
            events.append(r)
        if dispel:
            events.append(sp(12, "SPELL_DISPEL", ME, TANK, "Dispel", 2, 300))
        return measure_healer(rundata(sorted(events, key=lambda e: e.ts), [Fight(0, 30)]))

    def test_self_buff_is_not_a_response(self):
        hm = self.healer(ME)
        self.assertEqual((len(hm.dips), hm.missed), (1, 1))
        self.assertNotIn("Shield", hm.heal_spells)
        self.assertNotIn("Shield", self.healer(ME, advanced=False).heal_spells)

    def test_absorbing_shield_counts(self):
        hm = self.healer(TANK, absorb=300)
        self.assertEqual((hm.missed, hm.dips[0].spell), (0, "Shield"))
        self.assertEqual(self.healer(TANK, absorb=0).missed, 0)   # on a party member: counts without a reading

    def test_self_shield_needs_an_absorb(self):
        hm = self.healer(ME)
        hm2 = self.healer(ME, absorb=300, reading=ME)
        self.assertEqual((hm.missed, "Shield" in hm.heal_spells), (1, False))
        self.assertIn("Shield", hm2.heal_spells)

    def test_no_advanced_shield_on_other_counts(self):
        self.assertIn("Shield", self.healer(TANK, advanced=False).heal_spells)

    def test_dispels_in_summary(self):
        from dips_score.scoring.score import healer_categories
        eff = {c.name: c for c in healer_categories(self.healer(TANK, dispel=True))}["Efficiency"]
        self.assertTrue(eff.summary.endswith(", 1 dispels"))


class Phase4(unittest.TestCase):
    """capped rage, and cooldowns left ready"""
    def card(self, power_type):
        from dips_score.scoring.metrics import measure
        from dips_score.scoring.score import score_dps
        events = [me_info(ev(t, "SPELL_ENERGIZE", ME, ME), power_type, p) for t, p in ((0, 100), (5, 100), (10, 50))]
        m = measure(rundata(events, [Fight(0, 60)]))
        return m, {c.name: c for c in score_dps(m).categories}

    def test_capped_rage(self):
        m, cats = self.card(1)
        self.assertAlmostEqual(m.capped_time, 10.0)
        self.assertLess(cats["Resource"].score, 100)
        self.assertIn("at full rage 10s", cats["Resource"].summary)

    def test_mana_has_no_resource(self):
        m, cats = self.card(0)
        self.assertEqual(m.capped_time, 0.0)
        self.assertNotIn("Resource", cats)

    def measure(self, *casts, known):
        from dips_score.scoring.cooldowns import measure_cooldowns
        events = [sp(t, "SPELL_CAST_SUCCESS", ME, MOB1, "Mind Blast", 5) for t in casts]
        hit = sp(0.1, "SPELL_DAMAGE", ME, MOB1, "Mind Blast", 5)
        hit.amount = 300
        bites = [ev(t, "SWING_DAMAGE", MOB1, ME, amount=10) for t in range(2, 91, 2)]   # keeps the fight on
        events = sorted([*events, hit, *bites], key=lambda e: e.ts)
        return measure_cooldowns(rundata(events, [Fight(0, 90)]), known)[0]

    def test_cooldown_left_ready(self):
        from dips_score.scoring.score import _cooldowns
        cm = self.measure(0, known={"Mind Blast": {"gaps": [30.0] * 3, "spam": False, "last": None, "avg": 0,
                                                   "cast": False, "cost": 0, "game_cd": None}})
        row = cm.rows[0]
        self.assertEqual(row.name, "Mind Blast")
        self.assertTrue(1.8 < row.missed <= 2.0, row.missed)   # a 30 s cooldown cast once in 90 s: 2 casts missed
        self.assertAlmostEqual(row.lost, row.missed * 300)
        self.assertLess(_cooldowns(cm, 10).score, 100)

    def test_no_cooldowns(self):
        from dips_score.scoring.score import _cooldowns
        cat = _cooldowns(self.measure(0, known={}), 10)   # cast once: no cooldown to learn
        self.assertEqual((cat.score, cat.summary), (100.0, "no cooldowns to judge"))

    def test_old_weights_file(self):
        import json
        import tempfile
        from dips_score.scoring import score
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "weights.json"
            path.write_text(json.dumps({"dps": {"Damage": 25, "Input": 10}}), encoding="utf-8")
            score.load_weights(path)
        try:
            self.assertEqual((score.WEIGHTS["dps"]["Cooldowns"], score.WEIGHTS["dps"]["Resource"]), (10, 5))
        finally:
            score.reset_weights()


class Upkeep(unittest.TestCase):
    def measure(self, cls, *events):
        from dips_score.scoring.upkeep import measure_upkeep, upkeep_base
        rd = rundata(list(events), [Fight(0, 60)])
        return measure_upkeep(rd, base=upkeep_base(rd, cls))

    def test_self_buff(self):
        um = self.measure("ROGUE", sp(10, "SPELL_AURA_APPLIED", ME, ME, "Slice and Dice", 1, aura="BUFF"),
                          sp(40, "SPELL_AURA_REMOVED", ME, ME, "Slice and Dice", 1))
        self.assertEqual([(r.name, r.uptime) for r in um.rows], [("Slice and Dice", 0.5)])

    def test_target_is_union_over_enemies(self):
        def dot(a, b, mob):
            return [sp(a, "SPELL_AURA_APPLIED", ME, mob, "Corruption", 1, aura="DEBUFF"),
                    sp(b, "SPELL_AURA_REMOVED", ME, mob, "Corruption", 1)]
        um = self.measure("WARLOCK", *dot(0, 20, MOB1), *dot(10, 50, MOB2))
        self.assertAlmostEqual(um.rows[0].uptime, 50 / 60)

    def test_enemy_death_ends_aura(self):
        um = self.measure("WARLOCK", sp(0, "SPELL_AURA_APPLIED", ME, MOB1, "Corruption", 1, aura="DEBUFF"),
                          ev(30, "UNIT_DIED", "", MOB1))
        self.assertAlmostEqual(um.rows[0].uptime, 0.5)

    def test_unapplied_and_unknown_class_not_judged(self):
        from dips_score.scoring.metrics import Metrics
        from dips_score.scoring.score import score_dps
        um = self.measure("ROGUE", sp(5, "SPELL_AURA_APPLIED", TANK, ME, "Slice and Dice", 1, aura="BUFF"))
        self.assertEqual(um.rows, [])   # someone else's, and Rupture never applied
        self.assertEqual(self.measure(None, sp(0, "SPELL_AURA_APPLIED", ME, ME, "Slice and Dice", 1)).rows, [])
        m = Metrics(combat_time=60, has_log=True)
        self.assertEqual(score_dps(m, None, None, None, um).total, score_dps(m).total)
        self.assertNotIn("Upkeep", [c.name for c in score_dps(m, None, None, None, um).categories])

    def test_upkeep_row(self):
        from dips_score.scoring.metrics import Metrics
        from dips_score.scoring.score import score_dps
        um = self.measure("ROGUE", sp(0, "SPELL_AURA_APPLIED", ME, ME, "Slice and Dice", 1, aura="BUFF"),
                          sp(15, "SPELL_AURA_REMOVED", ME, ME, "Slice and Dice", 1))
        cat = next(c for c in score_dps(Metrics(combat_time=60, has_log=True), None, None, None, um).categories
                   if c.name == "Upkeep")
        self.assertEqual(cat.summary, "Slice and Dice 25%")
        self.assertIn("Slice and Dice", cat.tip)

    def test_classes_json(self):
        import json
        import tempfile
        from dips_score.scoring import classes
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "classes.json"
            path.write_text(json.dumps({"ROGUE": [["Garrote", "target"]]}), encoding="utf-8")
            classes.load_upkeep(path)
            try:
                self.assertEqual(classes.UPKEEP["ROGUE"], [("Garrote", "target")])
                self.assertEqual(classes.UPKEEP["MAGE"], classes.DEFAULT_UPKEEP["MAGE"])
                path.write_text("{not json", encoding="utf-8")
                classes.load_upkeep(path)
                self.assertEqual(classes.UPKEEP["ROGUE"], classes.DEFAULT_UPKEEP["ROGUE"])
            finally:
                classes.load_upkeep(None)

    def test_classes_json_defensives(self):
        import json
        import tempfile
        from dips_score.scoring import classes
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "classes.json"
            path.write_text(json.dumps({"defensives": {"ROGUE": ["Evasion"]}, "MAGE": [["Living Bomb", "target"]]}),
                            encoding="utf-8")
            classes.load_upkeep(path)
            try:
                self.assertEqual(classes.DEFENSIVES["ROGUE"], ["Evasion"])
                self.assertEqual(classes.DEFENSIVES["MAGE"], classes.DEFAULT_DEFENSIVES["MAGE"])
                self.assertEqual(classes.UPKEEP["MAGE"], [("Living Bomb", "target")])
                path.write_text(json.dumps({"ROGUE": [["Garrote", "target"]]}), encoding="utf-8")   # the old shape
                classes.load_upkeep(path)
                self.assertEqual((classes.UPKEEP["ROGUE"], classes.DEFENSIVES["ROGUE"]),
                                 ([("Garrote", "target")], classes.DEFAULT_DEFENSIVES["ROGUE"]))
            finally:
                classes.load_upkeep(None)

    def test_old_weights_file(self):
        import json
        import tempfile
        from dips_score.scoring import score
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "weights.json"
            path.write_text(json.dumps({"dps": {"Damage": 25}, "tank": {"Pickups": 30}}), encoding="utf-8")
            score.load_weights(path)
        try:
            self.assertEqual((score.WEIGHTS["dps"]["Upkeep"], score.WEIGHTS["tank"]["Upkeep"]), (5, 10))
        finally:
            score.reset_weights()


class Positioning(unittest.TestCase):
    """behind the target, range when refused, distance from the tank; nothing changes a total"""
    def at(self, e, guid, x, y, facing=0.0):
        from dips_score.sources.combatlog import UnitInfo
        e.info = UnitInfo(guid, 1, 1, 0, 0, 0, x, y, 1, facing, 60)
        return e

    def measure(self, events):
        from dips_score.scoring.positioning import measure_positioning, position_base
        rd = rundata(events, [Fight(0, 60)])
        return measure_positioning(rd, base=position_base(rd, TANK))

    def swings(self, mob_at=0.2, n=12, behind=8):
        out = []
        for i in range(n):
            t = i + 1
            out.append(self.at(ev(t, "SWING_DAMAGE", ME, MOB1, amount=1), ME, -5 if i < behind else 5, 0))
            out.append(self.at(ev(t + mob_at, "SWING_DAMAGE", MOB1, TANK, amount=1), MOB1, 0, 0, 0.0))
        return out

    def test_angle(self):
        from dips_score.scoring.positioning import faces
        self.assertFalse(faces(0, 0, 0.0, -10, 0))   # facing north, you directly south: behind
        self.assertTrue(faces(0, 0, 0.0, 10, 0))     # directly north: in front

    def test_behind_share(self):
        pm = self.measure(self.swings())
        self.assertEqual((pm.behind, pm.behind_judged, pm.swings), (8, 12, 12))
        self.assertAlmostEqual(pm.behind_share, 8 / 12)

    def test_stale_readings_and_too_few(self):
        from dips_score.scoring.metrics import Metrics
        from dips_score.scoring.score import _positioning
        pm = self.measure(self.swings(mob_at=100))   # enemy readings far from every swing
        self.assertEqual((pm.behind_judged, pm.swings), (0, 12))
        m = Metrics(combat_time=60, has_log=True, has_advanced=True, swings=100)
        self.assertEqual(_positioning(pm, m, 0).unavailable, "too few position readings to judge")
        self.assertEqual(_positioning(self.measure(self.swings(n=9, behind=9)), m, 0).unavailable,
                         "too few position readings to judge")
        cat = _positioning(self.measure(self.swings()), m, 5)
        self.assertFalse(cat.unavailable)
        self.assertIn("(12 of 12 judged)", cat.summary)

    def test_far_from_tank_and_range(self):
        events = []
        for i in range(10):
            t = i + 1
            events.append(self.at(ev(t, "SWING_DAMAGE", MOB1, ME, amount=5), ME, 10 if i < 6 else 20, 0))
            events.append(self.at(ev(t + 0.2, "SWING_DAMAGE", MOB1, TANK, amount=5), TANK, 0, 0))
        refused = ev(15, "SPELL_CAST_FAILED", ME, spell="Smite")
        refused.reason = "Out of range"
        events += [self.at(refused, ME, 0, 0), self.at(ev(15.1, "SWING_DAMAGE", MOB1, TANK), MOB1, 30, 0)]
        pm = self.measure(events)
        self.assertEqual((len(pm.tank_dists), pm.hits), (10, 10))
        self.assertEqual((pm.median_tank, pm.far_share), (10, 0.4))
        self.assertEqual((pm.range_dists, pm.refused), ([30.0], 1))

    def test_no_advanced(self):
        from dips_score.scoring.metrics import Metrics
        from dips_score.scoring.positioning import PositionMetrics
        from dips_score.scoring.score import _positioning
        cat = _positioning(PositionMetrics(), Metrics(combat_time=60, has_log=True), 0)
        self.assertEqual(cat.unavailable, "needs Advanced Combat Logging")

    def test_totals_unchanged(self):
        from dips_score.scoring.healer import HealerMetrics
        from dips_score.scoring.metrics import Metrics
        from dips_score.scoring.score import score
        from dips_score.scoring.tank import TankMetrics
        m = Metrics(combat_time=60, has_log=True, has_advanced=True, swings=100)
        pm = self.measure(self.swings())
        hm, tm = HealerMetrics(combat_time=60), TankMetrics(mobs=3, held=3)
        for role in ("dps", "tank", "healer"):
            a, b = score(m, role, hm, tm), score(m, role, hm, tm, pm=pm)
            self.assertEqual(a.total, b.total, role)
            self.assertEqual(b.categories[-1].name, "Positioning")
            self.assertTrue(b.categories[-1].info_only)
            self.assertEqual([c.name for c in b.categories[:-1]], [c.name for c in a.categories])

    def test_old_weights_file(self):
        import json
        import tempfile
        from dips_score.scoring import score
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "weights.json"
            path.write_text(json.dumps({"healer": {"Response": 50}}), encoding="utf-8")
            score.load_weights(path)
        try:
            self.assertEqual([score.WEIGHTS[r]["Positioning"] for r in score.ROLES], [0, 0, 0])
        finally:
            score.reset_weights()


if __name__ == "__main__":
    unittest.main()
