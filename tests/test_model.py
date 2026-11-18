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
                         ["Holding mobs", "Pickups", "Survival", "Activity", "Casting", "Input", "Movement"])

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


if __name__ == "__main__":
    unittest.main()
