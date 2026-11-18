"""The live fight tracker and summaries, on a small made-up log."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.live.summary import learn_cooldowns, summarize  # noqa: E402
from dips_score.live.tracker import Tracker  # noqa: E402

ME = 'Player-1-A,"Nikana-Diploidian-PvP-US",0x511,0x80000000'
MOB = 'Creature-0-1-1-1-100-1,"Wolf",0xa48,0x80000000'
MOB2 = 'Creature-0-1-1-1-100-2,"Wolf",0xa48,0x80000000'
NONE = '0000000000000000,nil,0x80000000,0x80000000'


def line(sec: float, rest: str) -> str:
    m, s = divmod(sec, 60)
    return f"11/17/2026 12:{int(m):02d}:{s:06.3f}-8  {rest}"


def dmg(sec, src, dst, spell_id, name, amount):
    return line(sec, f"SPELL_DAMAGE,{src},{dst},{spell_id},\"{name}\",0x20,{amount},{amount},-1,32,0,0,0,nil,nil,nil")


class Live(unittest.TestCase):
    def test_two_fights_and_a_summary(self):
        log = [
            line(0, f"SPELL_CAST_SUCCESS,{ME},{MOB},8092,\"Mind Blast\",0x20"),
            dmg(0.1, ME, MOB, 8092, "Mind Blast", 300),
            # the wolf bites every 2 s, so the fight stays on
            *[line(t, f"SWING_DAMAGE,{MOB},{ME},20,20,-1,1,0,0,0,nil,nil,nil") for t in (2, 4, 6, 8)],
            line(10, f"SPELL_CAST_SUCCESS,{ME},{MOB},8092,\"Mind Blast\",0x20"),
            dmg(10.1, ME, MOB, 8092, "Mind Blast", 320),
            line(12, f"UNIT_DIED,{NONE},{MOB},0"),
            # 30 s later: a second fight, which also shows the first one is over
            dmg(42, ME, MOB2, 8092, "Mind Blast", 310),
            dmg(45, ME, MOB2, 589, "Shadow Word: Pain", 90),
            line(45.5, f"UNIT_DIED,{NONE},{MOB2},0"),
            line(60, f"SPELL_AURA_APPLIED,{ME},{ME},588,\"Inner Fire\",0x2,BUFF"),
        ]
        tr = Tracker()
        fights = tr.feed_lines(log)
        self.assertEqual(len(fights), 2)
        self.assertEqual(tr.me, "Player-1-A")
        first, second = fights
        self.assertAlmostEqual((first.end - first.start).total_seconds(), 10.1, places=1)
        self.assertAlmostEqual(second.since_last, 31.9, places=1)
        cds = {}
        learn_cooldowns(first, tr.me, cds)
        self.assertAlmostEqual(cds[8092], 10.0, places=1)
        s = summarize(first, tr.me, tr.me_name, cds, [])
        self.assertEqual((s["target"], s["kind"], s["result"], s["damage"]), ("Wolf", "World", "killed", 620))
        later = summarize(second, tr.me, tr.me_name, cds, [s])
        self.assertEqual(later["best_before"], s["dps"])


    def test_one_combat_stays_one_fight(self):
        bite = lambda t, mob: line(t, f"SWING_DAMAGE,{mob},{ME},20,20,-1,1,0,0,0,nil,nil,nil")  # noqa: E731
        log = [
            dmg(0, ME, MOB, 8092, "Mind Blast", 300), bite(1, MOB), bite(2, MOB2),
            line(3, f"UNIT_DIED,{NONE},{MOB2},0"),
            # the wolf runs off for 11 s (still alive), then comes back: the same combat
            dmg(14, ME, MOB, 589, "Shadow Word: Pain", 90), bite(15, MOB),
            line(16, f"UNIT_DIED,{NONE},{MOB},0"),
            # a new wolf joins 3 s after the last one died: still the same combat
            dmg(19, ME, 'Creature-0-1-1-1-100-3,"Wolf",0xa48,0x80000000', 8092, "Mind Blast", 280),
            line(20, f"UNIT_DIED,{NONE},Creature-0-1-1-1-100-3,\"Wolf\",0xa48,0x80000000,0"),
            line(40, f"SPELL_AURA_APPLIED,{ME},{ME},588,\"Inner Fire\",0x2,BUFF"),
        ]
        tr = Tracker()
        closings = tr.feed_lines(log)
        fights = {id(f): f for f in closings}.values()
        self.assertEqual(len(fights), 1)
        f = next(iter(fights))
        self.assertEqual(len(f.foes), 3)
        self.assertAlmostEqual((f.end - f.start).total_seconds(), 19, places=0)


if __name__ == "__main__":
    unittest.main()
