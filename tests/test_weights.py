"""The add-on's standard weights (Weights.lua, for its in-game Upgrades list) are the app's (live/gearworth.py)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dips_score.live import gearworth  # noqa: E402
from dips_score.sources import luadata  # noqa: E402


class Weights(unittest.TestCase):
    def test_the_same_tables(self):
        w = luadata.load(ROOT / "addon" / "dips-Score" / "Weights.lua")["dipsScoreWeights"]
        self.assertEqual(w["tables"], gearworth.TABLES)
        self.assertEqual({(r, c): t for r, by in w["class"].items() for c, t in by.items()}, gearworth.CLASS)
        self.assertEqual(w["byClass"], gearworth.BY_CLASS)
        self.assertEqual({r: set(s) for r, s in w["weaponSlots"].items()}, gearworth.WEAPON_SLOTS)


if __name__ == "__main__":
    unittest.main()
