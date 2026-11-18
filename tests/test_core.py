"""python -m unittest discover -s tests  (from the project folder, with src on the path)"""
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.model.run import TLine  # noqa: E402
from dips_score.model.sync import SegmentClock, refine  # noqa: E402
from dips_score.scoring import metrics  # noqa: E402
from dips_score.scoring.score import ramp  # noqa: E402
from dips_score.sources import combatlog, luadata  # noqa: E402
from dips_score.sources.savedvars import parse_runs  # noqa: E402

SAVED = r'''
dipsScoreLog = {
["version"] = 1,
["runs"] = {
{
["zone"] = "Krol'dok \"Strong\"hold",
["id"] = "1794891447-Nikana",
["kind"] = "party",
["instanceID"] = 3039,
["started"] = 1794891447,
["char"] = "Nikana - Realm",
["segments"] = {
{
["anchors"] = {
"1794891450,2026-11-16 20:57:30,2000.0,8.1", -- [1]
"1794891510,2026-11-16 20:58:30,62000.0,8.0", -- [2]
},
["lines"] = {
"0,X,segment", -- [1]
"2500,CK,589", -- [2]
"3000,A,5,spell,589,K", -- [3]
},
["t0"] = 5521579209.5104,
},
},
},
},
}
'''

ADV_HEAL = ('11/16/2026 21:03:07.081-8  SPELL_HEAL,Player-6924-00187B13,"Nikana-Diploidian-PvP-US",0x511,'
            '0x80000000,Player-6922-0026513B,"Priime-Tiime-PvP-US",0x10512,0x80000000,10915,"Flash Heal",0x2,'
            'Player-6922-0026513B,0000000000000000,1731,2163,288,150,454,0,0,0,0,1565,3667,265,-7484.41,-4067.02,'
            '1415,3.9485,41,500,500,120,0,1')
ADV_DMG = ('11/16/2026 21:02:57.927-8  SPELL_DAMAGE,Player-6924-00187B13,"Nikana-Diploidian-PvP-US",0x511,'
           '0x80000000,Creature-0-7069-3039-73536-258972-00007BD995,"Twilight Commander Zarmok",0x10a48,0x80000001,'
           '8106,"Mind Blast",0x20,Creature-0-7069-3039-73536-258972-00007BD995,0000000000000000,8724,15617,83,0,'
           '1604,0,0,0,1,0,0,0,-7479.62,-4059.88,1415,3.8153,43,400,383,-1,32,0,0,0,nil,nil,nil,ST')
PLAIN_FAIL = ('11/16/2026 20:56:23.269-8  SPELL_CAST_FAILED,Player-6924-00187B13,"Nikana-Diploidian-PvP-US",'
              '0x511,0x80000000,0000000000000000,nil,0x80000000,0x80000000,1309633,"Shadow Word: Death",0x20,'
              '"Not yet recovered"')


class SavedVariables(unittest.TestCase):
    def test_parses_run(self):
        runs = parse_runs(luadata.loads(SAVED))
        self.assertEqual(len(runs), 1)
        r = runs[0]
        self.assertEqual(r.zone, 'Krol\'dok "Strong"hold')
        self.assertEqual(r.player_name, "Nikana")
        seg = r.segments[0]
        self.assertEqual(len(seg.anchors), 2)
        self.assertEqual(seg.lines[2].code, "A")
        self.assertEqual(seg.lines[2].fields, ["5", "spell", "589", "K"])

    def test_lua_values(self):
        d = luadata.loads('x = { 1, -2.5, true, nil, "a\\nb", ["k"] = { }, }')
        self.assertEqual(d["x"][1], 1)
        self.assertEqual(d["x"][2], -2.5)
        self.assertEqual(d["x"][5], "a\nb")


class Roster(unittest.TestCase):
    def test_race_from_p_line(self):
        from dips_score.model.roster import build_roster
        from dips_score.sources.savedvars import Line
        lines = [Line(0, "P", ["Player-1-0000AAAA", "Anna Smith", "PRIEST", "HEALER", "NightElf"]),
                 Line(0, "P", ["Player-2-0000BBBB", "Bo Lee", "WARRIOR", "TANK"])]  # a 4-field line from an older log
        roster = build_roster([], lines, None)
        self.assertEqual(roster["Player-1-0000AAAA"].race, "NightElf")
        self.assertEqual(roster["Player-1-0000AAAA"].cls, "PRIEST")
        self.assertIsNone(roster["Player-2-0000BBBB"].race)
        self.assertEqual(roster["Player-2-0000BBBB"].cls, "WARRIOR")


class CombatLog(unittest.TestCase):
    def test_heal_with_advanced(self):
        e = combatlog.parse_line(ADV_HEAL)
        self.assertEqual(e.spell_name, "Flash Heal")
        self.assertEqual(e.info.guid, "Player-6922-0026513B")
        self.assertEqual((e.info.hp, e.info.max_hp, e.info.power), (1731, 2163, 1565))
        self.assertEqual((e.amount, e.overheal, e.crit), (500, 120, True))

    def test_damage_with_advanced(self):
        e = combatlog.parse_line(ADV_DMG)
        self.assertEqual(e.amount, 400)
        self.assertEqual(e.overkill, -1)
        self.assertEqual(e.info.level, 43)
        self.assertEqual(e.ts, datetime(2026, 11, 16, 21, 2, 57, 927000))

    def test_cast_failed_reason(self):
        e = combatlog.parse_line(PLAIN_FAIL)
        self.assertIsNone(e.info)
        self.assertEqual(e.reason, "Not yet recovered")
        self.assertEqual(e.spell_id, 1309633)

    def test_split_keeps_nested(self):
        self.assertEqual(combatlog.split_fields('a,"b,c",[(1,2),(3)],d'), ["a", "b,c", "[(1,2),(3)]", "d"])


class Sync(unittest.TestCase):
    def test_interpolates_and_corrects(self):
        seg = parse_runs(luadata.loads(SAVED))[0].segments[0]
        clock = SegmentClock(seg)
        # 2000 ms is 20:57:30.000 exactly
        self.assertEqual(clock.wall(2000), datetime(2026, 11, 16, 20, 57, 30))
        self.assertEqual(clock.wall(2500), datetime(2026, 11, 16, 20, 57, 30, 500000))
        # the log says the cast was 40 ms later than the addon thinks: 5 matches move the clock
        seg.lines = [l for l in seg.lines if l.code != "CK"]
        from dips_score.sources.savedvars import Line
        log = {589: []}
        for i in range(6):
            seg.lines.append(Line(3000 + i * 2000, "CK", ["589"]))
            log[589].append(datetime(2026, 11, 16, 20, 57, 31 + i * 2, 40000))
        rep = refine(clock, seg, log)
        self.assertEqual(rep.matched, 6)
        self.assertAlmostEqual(rep.correction_ms, 40, delta=1)


class Metrics(unittest.TestCase):
    def test_intervals(self):
        self.assertEqual(metrics.union([(0, 2), (1, 3), (5, 6)]), [(0, 3), (5, 6)])
        self.assertEqual(metrics.clip([(0, 10)], [(2, 4), (8, 12)]), [(2, 4), (8, 10)])
        self.assertEqual(metrics.gaps([(0, 1), (5, 6)], [(0, 10)], 2.5), [(1, 5), (6, 10)])

    def test_busy_hardcast_instant_and_wand(self):
        L = [TLine(0.0, "CB", ["1"], 0), TLine(2.0, "CK", ["1"], 0),     # 2 s cast
             TLine(3.0, "CK", ["2"], 0),                                  # instant: 1.5 s GCD
             TLine(10.0, "CK", ["5019"], 0), TLine(11.5, "CK", ["5019"], 0)]  # two wand shots
        busy, wasted = metrics.busy_intervals(L)
        self.assertEqual(busy, [(0.0, 2.0), (3.0, 4.5), (10.0, 13.5)])
        self.assertEqual(wasted, [])

    def test_ramp(self):
        self.assertEqual(ramp(0.9, 0.55, 0.9), 100)
        self.assertEqual(ramp(0.5, 0.55, 0.9), 0)
        self.assertEqual(ramp(1.5, 3.0, 0.0), 50)


class Weights(unittest.TestCase):
    def test_info_only_and_bonus(self):
        from dips_score.scoring.score import Category, _card
        cats = [Category("A", 80, 50, ""), Category("B", 60, 50, ""), Category("C", 0, 0, "", tip="x")]
        card = _card(cats, "healer")
        self.assertAlmostEqual(card.total, 70)          # C (weight 0) is info only: left out
        self.assertEqual(card.tips, [])                  # and gives no tips
        self.assertEqual(_card(cats, "healer", bonus=50).total, 100)   # bonus can't go past 100


if __name__ == "__main__":
    unittest.main()
