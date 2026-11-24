"""When an ability can be used (scoring/usable.py): its chances per fight, the ready time excused outside them, and
how each page words them."""
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.fight_view import build_fight  # noqa: E402
from dips_score.live import readiness  # noqa: E402
from dips_score.live.summary import learn_cooldowns, summarize  # noqa: E402
from dips_score.scoring import usable  # noqa: E402
from dips_score.scoring.cooldowns import _sum  # noqa: E402
from dips_score.spells_view import spells_view  # noqa: E402
from test_fight_view import ORACLE  # noqa: E402
from test_live import ME, MOB, bites, cast, dmg, entry, line, one_fight  # noqa: E402

R = usable.RULES


class Chances(unittest.TestCase):
    def test_unknown_spell_is_always_usable(self):
        self.assertIsNone(usable.rule("Mind Blast"))
        self.assertTrue(usable.has_chance("Mind Blast", [], None))
        self.assertIsNone(usable.window_chances("Mind Blast", [{"foes": [["Imp", 1]]}], {"Imp": "Demon"}))

    def test_type(self):
        foes = [("Imp", 0.0, 10.0, []), ("Wolf", 5.0, None, []), ("Stranger", 12.0, 14.0, [])]
        self.assertEqual(usable.fight_chances(R["Exorcism"], 20, foes, {}, {}), (None, None))     # no types: unknown
        can, n = usable.fight_chances(R["Exorcism"], 20, foes, {"Imp": "Demon", "Wolf": "Beast"}, {})
        self.assertEqual((can, n), ([(0.0, 10.0), (12.0, 14.0)], 1))      # an enemy of unknown type stays usable
        self.assertEqual(usable.fight_chances(R["Turn Undead"], 20, foes, {"Imp": "Demon", "Wolf": "Beast",
                                                                           "Stranger": "Beast"}, {}), ([], 0))

    def test_health(self):
        foes = [("Wolf", 0.0, 9.0, [(1, 0.8), (4, 0.15), (6, 0.25), (7, 0.1)]), ("Bear", 0.0, None, [(2, 0.9)])]
        self.assertEqual(usable.fight_chances(R["Execute"], 20, foes, None, {}), ([(4, 6), (7, 9.0)], 1))
        no_hp = [("Wolf", 0.0, 9.0, [])]
        self.assertEqual(usable.fight_chances(R["Hammer of Wrath"], 20, no_hp, None, {}), (None, None))
        self.assertEqual(usable.reason(R["Execute"]), "no enemy under 20%")

    def test_health_foe_never_read_stays_usable(self):
        foes = [("Wolf", 0.0, None, [(1, 0.9), (10, 0.8)]), ("Bear", 4.0, 12.0, [])]
        can, n = usable.fight_chances(R["Execute"], 20, foes, None, {})
        self.assertEqual((can, n), ([(4.0, 12.0)], 0))            # the Bear's time, not counted as a chance
        ctx = readiness.Context(dur=20, foes=[(0, None, [])])
        free, why = readiness.judge([(0, 20)], ctx, False, 0, can, usable.reason(R["Execute"]))
        self.assertAlmostEqual(free, 7.0, delta=0.15)             # 4-12 less the second to react: not excused
        self.assertAlmostEqual(why["no enemy under 20%"], 11.0, delta=0.25)   # 1-4 and 12-20

    def test_reactive(self):
        avoided = {("target", "dodge"): [3.0, 5.0], ("you", "parry"): [10.0], ("you", "block"): [18.0]}
        self.assertEqual(usable.fight_chances(R["Mongoose Bite"], 20, [], None, avoided), ([(3.0, 10.0)], 2))
        self.assertEqual(usable.fight_chances(R["Riposte"], 20, [], None, avoided), ([(10.0, 15.0)], 1))
        on = {"Defensive Stance": [(0.0, 20)]}
        self.assertEqual(usable.fight_chances(R["Revenge"], 20, [], None, avoided, on),
                         ([(10.0, 15.0), (18.0, 20)], 2))
        self.assertEqual(usable.fight_chances(R["Counterattack"], 20, [], None, {}), ([], 0))    # none: known, 0

    def test_stance(self):
        avoided = {("target", "dodge"): [3.0, 12.0]}
        over = lambda stances: usable.fight_chances(R["Overpower"], 20, [], None, avoided, stances)  # noqa: E731
        self.assertEqual(over({}), (None, None))                              # no stance seen: unknown
        self.assertEqual(over({"Berserker Stance": [(0.0, 20)]}), ([], 0))
        self.assertEqual(over({"Battle Stance": [(5.0, 10.0)]}), ([(5.0, 8.0)], 1))     # danced in at 5 s

    def test_creature_types(self):
        foes = [("Wolf", 0.0, None, []), ("Imp", 0.0, None, [])]
        types = {"Wolf": "Beast", "Imp": "Demon"}
        for name in ("Scare Beast", "Soothe Animal", "Tame Beast", "Enslave Demon"):
            self.assertEqual(usable.fight_chances(R[name], 20, foes, types, {})[1], 1, name)

    def test_counted(self):
        self.assertEqual([usable.counted(n, R["Revenge"]) for n in (1, 2)],
                         ["1 block, dodge or parry", "2 blocks, dodges and parries"])
        self.assertEqual(usable.counted(1, R["Execute"]), "1 enemy under 20% health")
        self.assertEqual(usable.counted(1, R["Exorcism"]), "1 undead or demon")

    def test_window_over_saved_fights(self):
        fs = [{"foes": [["Imp", 2], ["Wolf", 1]], "chances": {"Execute": 3}}, {"foes": [["Bandit", 4]]},
              {"foes": [["Ghoul", 1]], "chances": {"Execute": 0}}]
        types = {"Imp": "Demon", "Wolf": "Beast", "Ghoul": "Undead"}
        self.assertEqual(usable.window_chances("Exorcism", fs, types), {"chances": 3, "fights": 2})
        self.assertEqual(usable.window_chances("Execute", fs, types), {"chances": 3, "fights": 1})
        self.assertIsNone(usable.window_chances("Exorcism", fs, {}))              # no types loaded: no data
        self.assertIsNone(usable.window_chances("Overpower", fs, types))          # fights saved without chances
        self.assertFalse(usable.has_chance("Overpower", fs, types))

    def test_judge_excuses_outside_chances(self):
        ctx = readiness.Context(dur=20, foes=[(0, None, [])])
        free, why = readiness.judge([(0, 20)], ctx, False, 0, [(10, 15)], "nothing to answer")
        self.assertAlmostEqual(free, 4.0, delta=0.15)             # 10-15, less the second to react
        self.assertAlmostEqual(why["nothing to answer"], 14.0, delta=0.15)
        free_any, _ = readiness.judge([(0, 20)], ctx, False, 0)
        self.assertAlmostEqual(free_any, 17.0, delta=0.15)          # today: only the first second and the end


def stance(sec, name, on=True):
    return line(sec, f"SPELL_AURA_{'APPLIED' if on else 'REMOVED'},{ME},{ME},2457,\"{name}\",0x1,BUFF")


class InTheFight(unittest.TestCase):
    """a 30 s fight against a Wolf with Mind Blast cast once and another spell in the book never cast"""

    def fight(self, spell, *extra, types=None):
        tr, f = one_fight([cast(0, 8092, "Mind Blast"), dmg(0.1, ME, MOB, 8092, "Mind Blast", 300), *extra, *bites()])
        book = {spell: entry(5.0)}
        book[spell]["last"] = (f.start - timedelta(minutes=5)).isoformat()
        learn_cooldowns(f, tr.me, book)
        s = summarize(f, tr.me, tr.me_name, book, [], types)
        return s, next(r for r in s["cooldowns"] if r["name"] == spell)

    def test_type(self):
        s, row = self.fight("Exorcism", types={"Wolf": "Beast"})
        self.assertEqual((row["free"], row["lost"], row["chances"], row["missed"]), (0, 0, 0, 0))
        self.assertGreater(row["excused"]["no valid target"], 20)
        _, undead = self.fight("Exorcism", types={"Wolf": "Undead"})
        self.assertEqual(undead["chances"], 1)
        self.assertGreater(undead["free"], 20)

    def test_no_data_keeps_todays_behaviour(self):
        _, row = self.fight("Exorcism")
        self.assertNotIn("chances", row)
        self.assertGreater(row["free"], 20)
        s, row = self.fight("Hammer of Wrath")                    # no Advanced Combat Logging: no foe health
        self.assertNotIn("chances", row)
        self.assertNotIn("Hammer of Wrath", s["chances"])

    def test_reactive(self):
        s, row = self.fight("Overpower", stance(0, "Battle Stance"), line(10, f"SWING_MISSED,{ME},{MOB},DODGE,nil"))
        self.assertEqual((row["chances"], s["chances"]["Overpower"]), (1, 1))
        self.assertAlmostEqual(row["free"], 4.0, delta=0.15)
        self.assertEqual(row["possible"], 1)
        self.assertIn("Overpower sat ready 4.0 s across 1 chance while you were free ≈ ", s["improve"][0])
        s, _ = self.fight("Revenge", stance(0, "Defensive Stance"), line(4, f"SWING_MISSED,{MOB},{ME},PARRY,nil"),
                          line(6, f"SWING_DAMAGE,{MOB},{ME},20,20,-1,1,0,8,0,nil,nil,nil"))     # a partial block
        self.assertEqual(s["chances"]["Revenge"], 2)

    def test_stance(self):
        dodge, parry = line(10, f"SWING_MISSED,{ME},{MOB},DODGE,nil"), line(4, f"SWING_MISSED,{MOB},{ME},PARRY,nil")
        for spell in ("Overpower", "Revenge"):            # Fury, all in Berserker Stance: nothing to answer
            s, row = self.fight(spell, stance(0, "Berserker Stance"), dodge, parry)
            self.assertEqual((row["chances"], row["free"], s["chances"][spell]), (0, 0, 0))
            s, row = self.fight(spell, dodge, parry)              # no stance in the log: unknown, as today
            self.assertNotIn("chances", row)
            self.assertNotIn(spell, s["chances"])
            self.assertGreater(row["free"], 20)
        # first seen leaving: it was on from the pull, so the dodge at 10 s counts, the one at 20 s doesn't
        s, _ = self.fight("Overpower", dodge, stance(15, "Battle Stance", False), stance(15, "Berserker Stance"),
                          line(20, f"SWING_MISSED,{ME},{MOB},DODGE,nil"))
        self.assertEqual(s["chances"]["Overpower"], 1)

    def test_run_rows_sum_chances(self):
        rows = lambda n: {"damage": 10, "cooldowns": [{"name": "Overpower", "free": 4, "cd": 5, "lost": 9,  # noqa: E731
                                                       **({"chances": n} if n is not None else {})}]}
        self.assertEqual(_sum([rows(2), rows(3), rows(None)]).rows[0].chances, 5)
        self.assertIsNone(_sum([rows(None)]).rows[0].chances)


class Wording(unittest.TestCase):
    def test_fight_and_debrief(self):
        cd = {"name": "Hammer of Wrath", "cd": 6.0, "used": 0, "free": 12.0, "lost": 9e6, "chances": 3}
        v = build_fight(dict(ORACLE, cooldowns=[cd]))
        self.assertIn(("Hammer of Wrath sat ready", "12.0 s", 9e6), v.rows)          # the row title as before
        self.assertEqual(v.gap[0], "Hammer of Wrath sat ready 12.0 s across 3 chances")
        plain = dict(cd, name="Judgement")
        del plain["chances"]
        self.assertEqual(build_fight(dict(ORACLE, cooldowns=[plain])).gap[0], "Judgement sat ready 12.0 s")

    def test_spells_page(self):
        cds = [SimpleNamespace(name="Hammer of Wrath", free=12.0, missed=2.0, lost=900.0, chances=3),
               SimpleNamespace(name="Judgement", free=20.0, missed=2.0, lost=100.0)]
        v = spells_view([], 60.0, cds)
        self.assertEqual(v.fix[0], "Hammer of Wrath sat ready 12 s across 3 chances")
        self.assertEqual(v.next_rows[-1][0], "Judgement sat ready 20 s")


if __name__ == "__main__":
    unittest.main()
