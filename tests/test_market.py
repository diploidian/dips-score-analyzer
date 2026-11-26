"""The add-on's auction house scan (Market.lua) as the app reads it: rows, their stats, tooltips, links and own names."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.sources.savedvars import load_char  # noqa: E402

SAVED = r'''
dipsScoreLog = { ["version"] = 1, ["char"] = { ["guid"] = "Player-1-A" }, ["market"] = {
["taken"] = 1795600000, ["realm"] = "Forever", ["faction"] = "Alliance", ["money"] = 452310, ["level"] = 31, ["filtered"] = true,
["rows"] = { "1,11,4567,30,2,12500,3,1,Band of Kings, Lesser", "2,17,9999,32,3,80000,1,0,Bandit Sword of the Monkey",
  "3,1,1234,,,500,,,", "x,1,1,1,1,1,1,1,Odd", "4,1,1,1,1,price,1,1,No price", "5,1", },
["rowstats"] = { "1,ITEM_MOD_STRENGTH_SHORT,6.000", "2,ITEM_MOD_AGILITY_SHORT,4.000", "2,ITEM_MOD_DAMAGE_PER_SECOND_SHORT,21.5",
  "9,ITEM_MOD_STAMINA_SHORT,3", "1,ITEM_MOD_STAMINA_SHORT,x", },
["rowtips"] = { "1,0,Band of Kings, Lesser", "1,0,Unique", "1,0!,Requires Level 35", "2,0,Bandit Sword of the Monkey", "2,0,Two-Hand",
  "2,R,  Sword  ", "9,0,Not a row", "odd", },
["links"] = { "1,item:4567::::::::31", "2,item:9999:0:0:0:0:0:0:0:31:0:0:1:1730", "3,nothing", },
["bases"] = { "2,Bandit Sword", "7,Not a row", },
} }
'''


def load(text=SAVED):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "dips-Score.lua"
        p.write_text(text, encoding="utf-8")
        return load_char(p)


class Market(unittest.TestCase):
    def test_the_scan(self):
        m = load()["market"]
        self.assertEqual((m["taken"], m["realm"], m["faction"], m["money"], m["level"], m["filtered"]),
                         (1795600000, "Forever", "Alliance", 452310, 31, True))
        self.assertEqual([r["n"] for r in m["rows"]], [1, 2, 3])          # odd and short rows left out
        ring, sword, bare = m["rows"]
        self.assertEqual((ring["kind"], ring["id"], ring["level"], ring["quality"], ring["price"], ring["count"], ring["unique"]),
                         (11, 4567, 30, 2, 12500, 3, True))
        self.assertEqual((ring["name"], ring["base"]), ("Band of Kings, Lesser", "Band of Kings, Lesser"))     # a name with a comma
        self.assertEqual((sword["name"], sword["base"], sword["unique"]), ("Bandit Sword of the Monkey", "Bandit Sword", False))
        self.assertEqual(ring["stats"], {"ITEM_MOD_STRENGTH_SHORT": 6})
        self.assertEqual(sword["stats"], {"ITEM_MOD_AGILITY_SHORT": 4, "ITEM_MOD_DAMAGE_PER_SECOND_SHORT": 21.5})
        self.assertEqual(ring["tips"], [(True, "Band of Kings, Lesser", ""), (True, "Unique", ""), (False, "Requires Level 35", "")])
        self.assertEqual(sword["tips"][1], (True, "Two-Hand", "Sword"))         # the right side of the line before
        self.assertEqual((ring["link"], bare["link"]), ("item:4567::::::::31", None))
        self.assertEqual((bare["level"], bare["quality"], bare["count"], bare["unique"], bare["name"], bare["stats"], bare["tips"]),
                         (None, None, None, None, "", {}, []))

    def test_no_scan(self):
        self.assertIsNone(load('dipsScoreLog = {["version"] = 1, ["char"] = {["guid"] = "A"}}')["market"])
        self.assertIsNone(load('dipsScoreLog = {["version"] = 1, ["char"] = {["guid"] = "A"}, ["market"] = "x"}')["market"])
        m = load('dipsScoreLog = {["version"] = 1, ["char"] = {["guid"] = "A"}, ["market"] = {["taken"] = "soon"}}')["market"]
        self.assertEqual((m["taken"], m["rows"], m["filtered"]), (None, [], False))


if __name__ == "__main__":
    unittest.main()
