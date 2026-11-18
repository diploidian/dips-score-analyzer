"""Tests for the roster, visits, deaths and pulls, on small made-up logs."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.analysis import merge_visits  # noqa: E402
from dips_score.model.deaths import find_deaths  # noqa: E402
from dips_score.model.pulls import build_pulls  # noqa: E402
from dips_score.model.roster import Player, build_roster, clean_name  # noqa: E402
from dips_score.model.run import Fight, RunData  # noqa: E402
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


class Visits(unittest.TestCase):
    def test_merges_close_pieces_of_same_place(self):
        def run(i, start, zone="Krol", inst=3039, ended=None):
            return Run(str(i), "x", zone, "party", 1, inst, start, ended, [Segment(0, [], [Line(60000, "X", [])])])
        out = merge_visits([run(1, 1000, ended=1100), run(2, 1200, ended=1300), run(3, 9000), run(4, 9100, "SM", 2)])
        self.assertEqual([r.parts for r in out], [["1", "2"], ["3"], ["4"]])
        self.assertEqual(len(out[0].segments), 2)


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
        cm = self.measure(0, known={5: 30.0})
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


if __name__ == "__main__":
    unittest.main()
