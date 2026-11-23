"""The player profile's figures and label, and its saved 15-day slices, from hand-made fight dicts."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.live import profile_history as ph  # noqa: E402
from dips_score.live.profile import label, profile  # noqa: E402

T0 = datetime(2026, 11, 23, 12, 0, 0)
DAY = timedelta(days=1)


def fight(days_ago=1.0, me="A", **kw):
    start = T0 - days_ago * DAY
    f = {"me": me, "me_name": me, "start": start.isoformat(), "duration": 60, "kind": "World", "more": 0,
         "result": "killed", "healing_role": False, "lowest_hp": 50, "cooldowns": [],
         "abilities": [{"name": "Smite", "casts": 3, "damage": 300, "share": 1.0}]}
    f.update(kw)
    return f


def run(days_ago=1.0, **kw):
    r = {"start": T0 - days_ago * DAY, "role": "damage", "score": 85.0, "grade": "A", "presses": 100,
         "by_key": 90, "by_click": 10, "failed": 5, "casts": 95, "combat_time": 600, "moving_time": 60}
    r.update(kw)
    return r


def figs(**kw):
    """minimal figures for label()"""
    base = {"roles": {"damage": 1.0, "healer": 0.0, "tank": 0.0}, "places": {"Dungeon": 0.0, "World": 1.0, "PvP": 0.0},
            "temperament": {"deaths_per_hour": 2, "median_pull": 2, "cooldowns_share": 0.8}, "hands": None}
    for k, v in kw.items():
        base[k] = {**base[k], **v} if isinstance(v, dict) and base.get(k) else v
    return base


class Windows(unittest.TestCase):
    def test_edges(self):
        p = profile([fight(30), fight(29.999), fight(15), fight(14.999), fight(0)], None, {}, [], T0)
        self.assertEqual(p["now"]["fights"], 2)          # (now - 15 days, now]: a fight at now counts
        self.assertEqual(p["before"]["fights"], 2)       # exactly 15 days back is Before; exactly 30 is out

    def test_before_none(self):
        p = profile([fight(1)], None, {}, [], T0)
        self.assertIsNone(p["before"])
        self.assertIsNone(p["now"]["hands"])

    def test_newest_character_only(self):
        p = profile([fight(2, me="B"), fight(1, me="A")], None, {}, [], T0)
        self.assertEqual((p["name"], p["now"]["fights"]), ("A", 1))

    def test_no_fights(self):
        self.assertIsNone(profile([], None, {}, [], T0)["now"])


class Figures(unittest.TestCase):
    def test_role_from_healing_role_and_spec(self):
        char = {"class": "PALADIN"}
        fs = [fight(1, healing_role=True, duration=30), fight(1, spec="Protection", duration=60),
              fight(1, spec="Retribution", duration=10), fight(1, duration=0)]
        roles = profile(fs, char, {}, [], T0)["now"]["roles"]
        self.assertEqual(roles, {"healer": 0.3, "tank": 0.6, "damage": 0.1})

    def test_places_boss_is_dungeon(self):
        fs = [fight(1, kind="Boss"), fight(1, kind="Dungeon"), fight(1, kind="World"), fight(1, kind="PvP")]
        self.assertEqual(profile(fs, None, {}, [], T0)["now"]["places"], {"Dungeon": 0.5, "World": 0.25, "PvP": 0.25})

    def test_opener(self):
        o = ["A", "B", "C"]
        fs = [fight(1, opener=o), fight(1, opener=o), fight(1, opener=["X", "B", "C"]), fight(1, opener=["A"]),
              fight(1)]
        self.assertEqual(profile(fs, None, {}, [], T0)["now"]["opener"], {"casts": o, "count": 2, "of": 3})
        self.assertIsNone(profile([fight(1)], None, {}, [], T0)["now"]["opener"])

    def test_hands_grades_and_temperament(self):
        fs = [fight(1, result="you died", more=2, cooldowns=[{"possible": 4, "missed": 1}]), fight(1)]
        n = profile(fs, None, {}, [run(1), run(1, score=None), run(20)], T0)["now"]
        self.assertEqual(n["hands"]["runs"], 2)
        self.assertAlmostEqual(n["hands"]["click_share"], 0.1)
        self.assertAlmostEqual(n["hands"]["per_minute"], 10)
        self.assertAlmostEqual(n["hands"]["refused_share"], 0.05)
        self.assertEqual(n["grades"]["damage"], {"runs": 1, "score": 85.0, "grade": "A"})
        self.assertIsNone(n["grades"]["healer"])
        t = n["temperament"]
        self.assertEqual((t["deaths"], t["deaths_per_hour"], t["median_pull"], t["cooldowns_share"]), (1, 30, 2, 0.75))

    def test_healer_signature_by_casts(self):
        fs = [fight(1, healing_role=True, abilities=[{"name": "Heal", "casts": 9, "damage": 0},
                                                     {"name": "Smite", "casts": 1, "damage": 500}])]
        sig = profile(fs, None, {}, [], T0)["now"]["signature"]
        self.assertEqual((sig["basis"], sig["top"][0]["name"], sig["top"][0]["share"]), ("casts", "Heal", 0.9))

    def test_unused(self):
        char = {"spells": {"Exorcism": {"harm": True}, "Smite": {"harm": True}, "Heal": {"harm": False}}}
        book = {"Smite": {"last": (T0 - DAY).isoformat()}}
        self.assertEqual(profile([fight(2)], char, book, [], T0)["now"]["unused"], ["Exorcism"])


class Label(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(label(figs()), "World damage dealer.")
        self.assertEqual(label(figs(temperament={"deaths_per_hour": 1, "median_pull": 2})), "Careful world damage dealer.")
        self.assertEqual(label(figs(temperament={"deaths_per_hour": 4, "median_pull": 3})), "Reckless world damage dealer.")
        self.assertEqual(label(figs(temperament={"cooldowns_share": 0.4})), "Hoarding world damage dealer.")
        self.assertEqual(label(figs(roles={"damage": 0.5, "healer": 0.5})), "World hybrid.")
        self.assertEqual(label(figs(places={"World": 0.4, "Dungeon": 0.3, "PvP": 0.3})), "Damage dealer.")
        self.assertEqual(label(figs(roles={"damage": 0, "healer": 1}, places={"World": 0, "Dungeon": 1},
                                    temperament={"deaths_per_hour": 0, "median_pull": 1}, hands={"click_share": 0.3})),
                         "Careful dungeon healer who clicks.")
        self.assertEqual(label(figs(hands={"click_share": 0.04})), "World damage dealer who keybinds.")
        self.assertEqual(label(figs(hands={"click_share": 0.1})), "World damage dealer.")

    def test_from_profile(self):
        self.assertEqual(profile([fight(1)], None, {}, [], T0)["now"]["label"], "Careful world damage dealer.")


class History(unittest.TestCase):
    def fights(self, *blocks):
        """n fights per 15-day block counted back from T0 (block 0 is Now)"""
        return sorted((fight(15 * b + 1 + i * 0.1) for b, n in enumerate(blocks) for i in range(n)),
                      key=lambda f: f["start"])

    def test_first_run_fill_in_and_floor(self):
        saved = {}
        added = ph.update(saved, self.fights(12, 10, 9, 11), None, {}, [], T0)
        self.assertEqual([s["fights"] for s in saved["A"]], [11, 10])        # oldest first; 9 is under the floor
        self.assertEqual(added, saved["A"])
        self.assertEqual(saved["A"][-1]["to"], (T0 - 15 * DAY).isoformat())  # Now is not saved
        self.assertIsInstance(saved["A"][0]["label"], str)

    def test_nothing_saved_under_floor(self):
        saved = {}
        ph.update(saved, self.fights(12, 9), None, {}, [], T0)
        self.assertEqual(saved, {})

    def test_slice_added_after_15_days_and_not_rewritten(self):
        fs = self.fights(12, 10)
        saved = {}
        ph.update(saved, fs, None, {}, [], T0)
        first = json.dumps(saved["A"][0])
        self.assertEqual(ph.update(saved, fs, None, {}, [], T0), [])          # the block ending at now is Now
        fs2 = fs + [fight(-0.5 - i * 0.1) for i in range(3)]                  # fights after T0 stay out of the slice
        added = ph.update(saved, fs2, None, {}, [], T0 + DAY)                 # 15 days since the last slice's end
        self.assertEqual(len(added), 1)
        self.assertEqual((added[0]["fights"], added[0]["to"]), (12, T0.isoformat()))
        self.assertEqual(json.dumps(saved["A"][0]), first)
        self.assertEqual(len(saved["A"]), 2)

    def test_save_and_load(self):
        saved = {}
        ph.update(saved, self.fights(0, 10), None, {}, [], T0)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "profile_history.json"
            self.assertEqual(ph.load(path), {})
            ph.save(path, saved)
            self.assertEqual(ph.load(path), saved)
            self.assertEqual(list(Path(d).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
