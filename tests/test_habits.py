"""Habit cards and session numbers, from hand-made fight dicts."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.live.habits import habits  # noqa: E402

T0 = datetime(2026, 11, 17, 12, 0, 0)


def fight(i, me="A", eff=0.8, own=("Fort",), ptype=1, mana=0.9, **kw):
    start = T0 + timedelta(minutes=2 * i)
    f = {"me": me, "me_name": me, "start": start.isoformat(), "end": (start + timedelta(seconds=30)).isoformat(),
         "duration": 30, "result": "killed", "efficiency": eff, "healing_role": False, "cooldowns": [], "failed": [],
         "pull": {"since_last": 90, "buffs": list(own), "own": list(own), "rest": 0},
         "resource": {"start": mana, "start_hp": 1.0, "type": ptype}}
    f.update(kw)
    return f


def titles(h):
    return {c["title"]: c["kind"] for c in h["cards"]}


class Habits(unittest.TestCase):
    def test_trend_up_is_keep_and_down_is_fix(self):
        up = habits([fight(i, eff=0.6 if i < 20 else 0.8) for i in range(40)])
        self.assertEqual(titles(up)["Efficiency is improving"], "keep")
        down = habits([fight(i, eff=0.9 if i < 20 else 0.7) for i in range(40)])
        self.assertEqual(titles(down)["Efficiency is dropping"], "fix")

    def test_pull_buff_missed_sometimes(self):
        fs = [fight(i, own=() if i == 3 else ("Fort",)) for i in range(10)]
        h = habits(fs)
        self.assertEqual(titles(h)["Pulling without Fort"], "fix")
        self.assertEqual(h["cards"][0]["kind"], "fix")           # fixes come first

    def test_old_and_new_pull_buffs_mixed(self):
        old = [fight(i, pull={"since_last": 1, "buffs": ["Fort", "Party Buff"]}) for i in range(6)]
        new = [fight(6 + i) for i in range(6)]
        self.assertNotIn("Pulling without Party Buff", titles(habits(old + new)))

    def test_mana_card_only_for_mana(self):
        self.assertNotIn("Start fights with more mana", titles(habits([fight(i, ptype=1, mana=0.2) for i in range(5)])))
        self.assertEqual(titles(habits([fight(i, ptype=0, mana=0.2) for i in range(5)]))
                         ["Start fights with more mana"], "build")

    def test_only_the_newest_character(self):
        fs = [fight(0, me="B", ptype=0, mana=0.1), fight(1, me="A"), fight(2, me="A")]
        h = habits(fs)
        self.assertEqual((h["name"], h["fights"], h["session"]["fights"]), ("A", 2, 2))

    def test_missed_casts_in_the_cooldown_card(self):
        row = {"name": "Judgement", "cd": 10, "lost": 200, "missed": 3, "counted": 2}    # one miss excused
        fs = [fight(i, cooldowns=[row]) for i in range(2)] + [fight(2, cooldowns=[{"name": "Judgement", "cd": 10, "lost": 100}])]
        card = next(c for c in habits(fs)["cards"] if c["title"] == "Judgement left unused")
        self.assertEqual(card["detail"], "About 500 damage lost, 4 casts missed in 3 fights")

    def test_empty(self):
        h = habits([])
        self.assertEqual((h["cards"], h["session"]), ([], None))


if __name__ == "__main__":
    unittest.main()
