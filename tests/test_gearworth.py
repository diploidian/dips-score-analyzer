"""What a point of a stat is worth: the role's table, what is measured and what is standard, and how the sheet says it."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.live.gearworth import AGI, AP, DPS, HEAL, SP, STA, STR, role, score, worth, measured  # noqa: E402
from dips_score.sheet_view import WORTH, _point_worth  # noqa: E402

MEASURED_AP = {"ap10": {"value": .5, "source": "measured", "n": 600}}


def did(**damage):
    return [{"abilities": [{"name": n.replace("_", " "), "damage": d} for n, d in damage.items()]}]


class Role(unittest.TestCase):
    def test_by_main_role_then_by_the_fights(self):
        self.assertEqual((role("healer", did(Melee=900), "PALADIN"), role("tank", [], None)), ("healer", "tank"))
        self.assertEqual(role("damage", did(Melee=500, Judgement=500), "PALADIN"), "melee")
        self.assertEqual(role("damage", did(Auto_Shot=300, Melee=50, Arcane_Shot=650), "HUNTER"), "ranged")
        self.assertEqual(role("damage", did(Shoot=300, Melee=50, Fireball=650), "MAGE"), "caster")      # a wand is no Auto Shot

    def test_by_class_before_any_fight(self):
        self.assertEqual([role(None, [], c) for c in ("HUNTER", "PRIEST", "WARRIOR", None)], ["ranged", "caster", "melee", "melee"])


class Measured(unittest.TestCase):
    def test_only_what_the_fights_measured(self):
        self.assertEqual(measured("melee", MEASURED_AP, []), {AP: {"value": .05, "n": 600, "of": "swing"}})
        self.assertEqual(measured("melee", {"ap10": {"value": .7, "source": "estimate", "n": 0}}, []), {})     # no slope: nothing
        self.assertEqual(measured("melee", {}, []), {})
        got = measured("caster", {}, [{"name": "Fireball", "value": .05, "n": 200}, {"name": "Frostbolt", "value": .03, "n": 150}])
        self.assertEqual((round(got[SP]["value"], 3), got[SP]["n"], got[SP]["of"]), (.08, 350, "hit"))
        self.assertEqual(measured("caster", MEASURED_AP, []), {})
        for r in ("healer", "tank", "ranged"):
            self.assertEqual(measured(r, MEASURED_AP, [{"name": "Heal", "value": .05, "n": 200}]), {})


class Score(unittest.TestCase):
    M = {AP: {"value": .07, "n": 600, "of": "swing"}}

    def test_anchored_on_attack_power(self):
        got = score({STR: 10, AP: 20, STA: 5}, "melee")
        self.assertEqual((got["dps"], got["points"], got["rank"]), (None, 40, 40))       # 1 Strength is 2 attack power
        self.assertEqual({p["source"] for p in got["parts"]}, {"standard"})
        self.assertNotIn(STA, [p["key"] for p in got["parts"]])                          # worth nothing to a melee damage dealer
        self.assertEqual(score({SP: 30}, "caster")["points"], 30)

    def test_measured_and_standard_apart(self):
        got = score({STR: 10, AP: 20}, "melee", self.M)
        self.assertEqual((round(got["dps"], 3), got["points"], got["rank"]), (1.4, 20, 40))
        self.assertEqual({p["key"]: p["source"] for p in got["parts"]}, {STR: "standard", AP: "measured"})

    def test_a_weapon_is_always_standard(self):
        for stats, slot in (({AP: 20}, 16), ({AP: 20, DPS: 10.0}, None)):
            got = score(stats, "melee", self.M, slot)
            self.assertIsNone(got["dps"])
            self.assertEqual({p["source"] for p in got["parts"]}, {"standard"})
        self.assertEqual(score({DPS: 10.0}, "melee", slot=16)["points"], 140)
        self.assertEqual(score({DPS: 10.0}, "ranged", slot=16)["points"], 0)             # a hunter fights with the ranged slot
        self.assertEqual(score({DPS: 10.0}, "ranged", slot=18)["points"], 140)

    def test_healer_and_tank_standard_only(self):
        for r in ("healer", "tank"):
            got = score({AP: 20, HEAL: 20, SP: 20}, r, {AP: self.M[AP], SP: self.M[AP]})
            self.assertIsNone(got["dps"])
            self.assertEqual({p["source"] for p in got["parts"]}, {"standard"})

    def test_a_rogue(self):
        self.assertEqual((score({STR: 10, AGI: 10}, "melee", cls="ROGUE")["points"], score({STR: 10, AGI: 10}, "melee")["points"]), (27, 30))


class Worth(unittest.TestCase):
    def test_a_point(self):
        rows = {r["key"]: r for r in worth("melee", Score.M)}
        self.assertEqual((rows[STR]["points"], rows[STR]["dps"]), (2, None))
        self.assertEqual((rows[AP]["dps"], rows[AP]["n"]), (.07, 600))
        self.assertEqual(worth(None), [])
        self.assertTrue(all(r["dps"] is None for r in worth("tank", Score.M)))
        first = worth("melee")
        self.assertEqual(first, sorted(first, key=lambda r: (-r["points"], r["name"])))

    def test_on_the_sheet(self):
        rows, note = _point_worth({"gear_role": "melee", "measured": Score.M, "class": "WARRIOR"})
        by = {f.name: f for f in rows}
        self.assertEqual((by["Attack power"].value, by["Attack power"].note), ("0.070", "damage per second, measured over 600 swings"))
        self.assertEqual((by["Strength"].value, by["Strength"].note), ("2", "points, standard"))
        self.assertIn("a point is what 1 attack power adds. Standard values are classic rules of thumb, estimates", note)
        rows, note = _point_worth({"gear_role": "healer", "measured": {}, "class": "PRIEST"})
        self.assertTrue(note.endswith("For healers every value is standard."))
        self.assertEqual(_point_worth({}), ([], ""))
        self.assertEqual(WORTH, "What a point is worth")


if __name__ == "__main__":
    unittest.main()
