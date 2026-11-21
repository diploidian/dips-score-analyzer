"""Pacing (dips_score/scoring/pacing.py): going into pulls safely and on time, on stubs; and its category."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.scoring.healer import HealerMetrics  # noqa: E402
from dips_score.scoring.metrics import Metrics  # noqa: E402
from dips_score.scoring.pacing import PacingMetrics, measure_pacing  # noqa: E402
from dips_score.scoring.score import DEFAULT_WEIGHTS, ROLES, _pacing, score  # noqa: E402
from dips_score.scoring.tank import TankMetrics  # noqa: E402

T0 = datetime(2026, 11, 20, 21, 0, 0)


def reading(sec, hp, mana=None, guid="me"):
    """a health (and mana, or rage when mana is None) sample of guid at sec"""
    info = SimpleNamespace(guid=guid, max_hp=100, hp_pct=hp, power_type=1 if mana is None else 0,
                           power=0 if mana is None else mana * 100, max_power=100)
    return SimpleNamespace(ts=T0 + timedelta(seconds=sec), info=info)


def press(t, code="A"):
    return SimpleNamespace(t=t, code=code)


def pull(start, end, puller="tank", combat=None):
    """combat: when your own combat began (default: as the pull started)"""
    return SimpleNamespace(start=start, packs=[SimpleNamespace(puller=puller)],
                           fight=SimpleNamespace(start=start if combat is None else combat, end=end))


def run(events, lines):
    return SimpleNamespace(events=events, lines=lines, start=T0)


class MeasureTests(unittest.TestCase):
    def test_safe_on_time(self):
        pc = measure_pacing(run([reading(5, 0.9, 0.8)], [press(11.0)]), [pull(10, 30)], "me")
        self.assertEqual((pc.pulls, pc.judged, pc.unsafe, pc.late, pc.good), (1, 1, [], [], 1))

    def test_unsafe_health(self):
        pc = measure_pacing(run([reading(5, 0.4, 0.2)], [press(11.0)]), [pull(10, 30)], "me")
        self.assertEqual((pc.unsafe, pc.good), ([(10, "health")], 0))     # one entry, health first

    def test_unsafe_mana(self):
        pc = measure_pacing(run([reading(5, 0.9, 0.2)], [press(11.0)]), [pull(10, 30)], "me")
        self.assertEqual(pc.unsafe, [(10, "mana")])

    def test_no_mana_isnt_unsafe(self):
        pc = measure_pacing(run([reading(5, 0.9)], [press(11.0)]), [pull(10, 30)], "me")    # a rage user
        self.assertEqual((pc.unsafe, pc.good), ([], 1))

    def test_reading_is_before_the_pull(self):
        events = [reading(5, 0.9, 0.8), reading(9.8, 0.2, 0.1)]     # inside the 0.5 s before: not read
        self.assertEqual(measure_pacing(run(events, [press(11.0)]), [pull(10, 30)], "me").unsafe, [])

    def test_late(self):
        pc = measure_pacing(run([reading(5, 0.9, 0.8)], [press(14.0, "CS")]), [pull(10, 30)], "me")
        self.assertEqual((pc.late, pc.good), ([(10, 4.0)], 0))

    def test_late_counts_from_your_combat(self):
        """mobs pulled from range take a while to reach you: the clock starts when your own combat does"""
        lines = [press(18.0)]       # 8 s after the pull, 2 s into your combat
        pc = measure_pacing(run([reading(5, 0.9, 0.8)], lines), [pull(10, 30, combat=16)], "me")
        self.assertEqual((pc.late, pc.good), ([], 1))
        pc = measure_pacing(run([reading(5, 0.9, 0.8)], [press(20.5)]), [pull(10, 30, combat=16)], "me")
        self.assertEqual(pc.late, [(10, 4.5)])

    def test_you_pulled_is_on_time(self):
        pc = measure_pacing(run([reading(5, 0.9, 0.8)], [press(14.0)]), [pull(10, 30, puller="me")], "me")
        self.assertEqual((pc.late, pc.good), ([], 1))

    def test_no_press_isnt_late(self):
        lines = [press(9.0), press(31.0), press(12.0, "CK")]      # before, after, and not a press
        pc = measure_pacing(run([reading(5, 0.9, 0.8)], lines), [pull(10, 30)], "me")
        self.assertEqual((pc.judged, pc.late, pc.good), (1, [], 1))

    def test_not_judged(self):
        events = [reading(5, 0.9, 0.8, guid="tank"), reading(40, 0.0, 0.0)]   # someone else; you dead going in
        pc = measure_pacing(run(events, [press(11.0)]), [pull(10, 30), pull(50, 60)], "me")
        self.assertEqual((pc.pulls, pc.judged, pc.good), (2, 0, 0))

    def test_both_counted_once(self):
        pc = measure_pacing(run([reading(5, 0.4, 0.8)], [press(14.0)]), [pull(10, 30)], "me")
        self.assertEqual((len(pc.unsafe), len(pc.late), pc.good), (1, 1, 0))


class CategoryTests(unittest.TestCase):
    def test_none(self):
        self.assertIsNone(_pacing(None, 5))
        self.assertIsNone(_pacing(PacingMetrics(), 5))

    def test_unavailable(self):
        c = _pacing(PacingMetrics(pulls=3), 5)
        self.assertEqual((c.name, c.unavailable), ("Pacing", "needs Advanced Combat Logging"))
        self.assertTrue(c.info_only)

    def test_summary_and_tip(self):
        pc = PacingMetrics(pulls=64, judged=64, unsafe=[(1.0, "health"), (2.0, "health"), (3.0, "mana")],
                           late=[(float(t), 4.0) for t in range(10, 20)])
        c = _pacing(pc, 5)
        self.assertEqual(c.summary, "51 of 64 pulls entered safely and on time; 2 under 50% health, "
                                    "1 under 30% mana, 10 late")
        self.assertEqual(c.tip, "You were late into 10 pulls (no press for over 3 s after your combat began). "
                                "Be ready when the tank pulls.")
        self.assertAlmostEqual(c.score, (51 / 64 - 0.5) / 0.45 * 100)
        self.assertIsNone(_pacing(pc, 0).tip)       # info only: no tip

    def test_tip_mana(self):
        c = _pacing(PacingMetrics(pulls=4, judged=4, unsafe=[(1.0, "mana"), (2.0, "mana"), (3.0, "mana")]), 5)
        self.assertEqual(c.summary, "1 of 4 pulls entered safely and on time; 3 under 30% mana")
        self.assertEqual(c.tip, "You went into 3 pulls under 30% mana. Drink before the next pull.")

    def test_tip_health(self):
        c = _pacing(PacingMetrics(pulls=2, judged=2, unsafe=[(1.0, "health")]), 5)
        self.assertEqual(c.tip, "You went into 1 pull under 50% health. Eat or bandage first.")

    def test_all_good(self):
        c = _pacing(PacingMetrics(pulls=5, judged=5), 5)
        self.assertEqual((c.score, c.summary, c.tip), (100.0, "5 of 5 pulls entered safely and on time", None))

    def test_weights(self):
        for role in ROLES:
            self.assertEqual(DEFAULT_WEIGHTS[role]["Pacing"], 5, role)

    def test_score_without_pacing_unchanged(self):
        m = Metrics(combat_time=60, has_log=True, has_advanced=True)
        hm, tm = HealerMetrics(combat_time=60), TankMetrics(mobs=3, held=3)
        pc = PacingMetrics(pulls=2, judged=2, late=[(1.0, 5.0)])
        for role in ROLES:
            a, b = score(m, role, hm, tm), score(m, role, hm, tm, pc=pc)
            self.assertNotIn("Pacing", [c.name for c in a.categories], role)
            self.assertEqual(b.categories[-1].name, "Pacing", role)
            self.assertEqual([c.name for c in b.categories[:-1]], [c.name for c in a.categories], role)
            self.assertLess(b.total, a.total, role)

    def test_rescore_run_card_only(self):
        from dips_score.analysis import Analysis, FightResult, rescore
        m, hm = Metrics(combat_time=60, has_log=True, has_advanced=True), HealerMetrics(combat_time=60)
        a = Analysis(None, "healer", m, hm, None, [FightResult(None, m, hm, None)])
        a.pacing = PacingMetrics(pulls=1, judged=1)
        rescore(a)
        self.assertEqual(a.card.categories[-1].name, "Pacing")
        self.assertNotIn("Pacing", [c.name for c in a.fights[0].card.categories])


if __name__ == "__main__":
    unittest.main()
