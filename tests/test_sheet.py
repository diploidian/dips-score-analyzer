"""The character sheet: reading it from the snapshot, what it says, and what it refuses to guess."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.live.sheet import sheet  # noqa: E402
from dips_score.sheet_view import NONE, build_sheet  # noqa: E402
from dips_score.sources.savedvars import load_char  # noqa: E402

T0 = datetime(2026, 11, 24, 12)
SAVED = r'''
dipsScoreLog = { ["version"] = 1, ["runs"] = {}, ["char"] = { ["guid"] = "Player-1-A", ["class"] = "PALADIN", ["taken"] = 1795576160,
["spells"] = { "6603,0,0,Attack", "20271,,1,Judgement", "679,10000,1,Holy Strike", "678,10000,1,Holy Strike", "7328,,0,Redemption", },
["gear"] = { "1,4724,30", "5,273035,32", "16,267369,31", },
["stats"] = { "str,93.000", "ap,287.000", "spellpower,?", "speed,3.400", "dmgmin,138.700", "dmgmax,174.700", "dmgbonus,21.000",
  "crit,11.270", "res_fire,0.000", "res_shadow,12.000", "armor,933.000", "broken", "nan,nan", },
["items"] = { "1,4724,2,,Humbert's Helm", "5,273035,3,1234,Mana-Warped, Chain Shirt", "16,267369,3,0,Wolfsbane", "x", },
["itemstats"] = { "1,ITEM_MOD_STAMINA_SHORT,9", "5,ITEM_MOD_STRENGTH_SHORT,12", "16,ITEM_MOD_STRENGTH_SHORT,15",
  "16,ITEM_MOD_DAMAGE_PER_SECOND_SHORT,20.0", "5,RESISTANCE0_NAME,255", },
["itemtext"] = { "16,Chance on hit: Wounds the target, for 12 damage.", "16,\"It howls.\"", "x", },
["ranks"] = { "679,Rank 2", "678,Rank 1", },
["points"] = { "talent,1100,105625,1,1,Conviction, Improved", "talent,1100,105626,5,5,Benediction", },
["trees"] = { "talent,1100,51,12,", "legacy,1187,9,0,3", "legacy,1188,9,0,", },
["skills"] = { "120,150,Mining, Smelting", "bad,1,x", },
} }
'''


def load(text=SAVED):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "dips-Score.lua"
        p.write_text(text, encoding="utf-8")
        return load_char(p)


def fight(i=0, **kw):
    start = T0 - timedelta(days=1, minutes=i)
    return {"me": "A", "start": start.isoformat(), "duration": 10, "kind": "World", "result": "killed", "healing_role": False,
            "damage": 500, "auto": {"speed": 3.4}, "abilities": [{"name": "Melee", "casts": 0, "hits": 2, "damage": 200},
                                                              {"name": "Judgement", "casts": 1, "hits": 1, "damage": 300}]} | kw


def made(win=(), char=None):
    return sheet(char or load(), list(win))


class Load(unittest.TestCase):
    def test_every_list(self):
        c = load()
        self.assertEqual((c["stats"]["str"], c["stats"]["spellpower"], "broken" in c["stats"], "nan" in c["stats"]), (93, None, False, False))
        self.assertEqual(c["items"][5], {"id": 273035, "quality": 3, "enchant": 1234, "name": "Mana-Warped, Chain Shirt"})
        self.assertIsNone(c["items"][1]["enchant"])
        self.assertEqual(c["itemstats"][16]["ITEM_MOD_STRENGTH_SHORT"], 15)
        self.assertEqual(c["spell_ids"], {6603: "Attack", 20271: "Judgement", 679: "Holy Strike", 678: "Holy Strike", 7328: "Redemption"})
        self.assertEqual((c["points"][0]["name"], c["skills"]), ("Conviction, Improved", [{"name": "Mining, Smelting", "level": 120, "max": 150}]))
        self.assertEqual([t["left"] for t in c["trees"]], [None, 3, None])

    def test_an_older_snapshot(self):
        c = load('dipsScoreLog = {["version"] = 1, ["char"] = {["guid"] = "A", ["gear"] = {"1,1,30"}}}')
        self.assertEqual((c["stats"], c["items"], c["ranks"]), ({}, {}, {}))
        self.assertIsNone(sheet(c, []))
        self.assertIsNone(sheet(None, []))
        self.assertEqual(build_sheet(None).need, NONE)


class Sheet(unittest.TestCase):
    def test_gear(self):
        g = {x["label"]: x for x in made()["gear"]}
        self.assertEqual((g["Head"]["flags"], g["Chest"]["flags"]), (["lowest"], []))
        self.assertEqual((g["Main hand"]["flags"], g["Neck"]["flags"]), (["not enchanted"], ["empty"]))
        unread = {x["label"]: x for x in made(char=load(SAVED.replace("3,0,Wolfsbane", "3,,Wolfsbane")))["gear"]}
        self.assertEqual(unread["Main hand"]["flags"], [])         # not read: nothing is said of it
        self.assertFalse({"Off hand", "Ranged"} & set(g))          # may be empty: no row, no flag

    def test_stats_from_gear(self):
        s = made()["stats"]
        self.assertEqual((s["str"], s["armor"]["gear"], s["ap"]["gear"]), ({"value": 93, "gear": 27, "by_quality": {3: 27}}, 255, None))

    def test_abilities(self):
        f = lambda *ids: fight(cast_ids={"Holy Strike": list(ids)}, abilities=[  # noqa: E731
            {"name": "Holy Strike", "casts": 2, "hits": 2, "damage": 100}])
        by = lambda win: {a["name"]: a for a in made(win)["abilities"]}  # noqa: E731
        a = by([f(678)])["Holy Strike"]
        self.assertEqual((a["rank"], a["ranks"], a["casts"], a["share"], a["lower"]), ("Rank 2", 2, 2, 1, True))
        self.assertFalse(by([f(678), f(679)])["Holy Strike"]["lower"])     # the highest was cast too
        self.assertFalse(by([fight()])["Holy Strike"]["lower"])            # fights that don't say which rank
        self.assertEqual(by([])["Redemption"]["casts"], 0)
        self.assertNotIn("Attack", by([]))
        proc = fight(abilities=[{"name": "Melee", "casts": 0, "hits": 1, "damage": 50}, {"name": "Judgement", "casts": 1, "damage": 0},
                                {"name": "Judgement of Command", "casts": 0, "hits": 1, "damage": 50}])
        self.assertEqual(by([proc])["Judgement"]["share"], .5)             # its proc's damage is its own

    def test_measured_first(self):
        p = made([fight(i) for i in range(12)])["projections"]
        self.assertEqual((p["dps"], p["hit"]["value"], p["hit"]["n"]), ({"value": 50, "source": "measured", "n": 12}, 100, 24))
        self.assertEqual((p["swing"]["source"], p["hps"]["value"]), ("measured", None))
        few = made([fight(i) for i in range(3)])["projections"]
        self.assertEqual((few["dps"]["value"], few["swing"]["source"]), (None, "game"))
        heal = [fight(i, healing_role=True, healing=200) for i in range(5)]
        self.assertEqual(made(heal)["projections"]["hps"], {"value": 20, "source": "measured", "n": 5})

    def test_the_estimate_only_while_it_fits(self):
        self.assertEqual(made()["projections"]["ap10"]["source"], "estimate")     # 68 + 69.7 + 21 = 158.7 against 156.7
        c = load(SAVED.replace("DAMAGE_PER_SECOND_SHORT,20.0", "DAMAGE_PER_SECOND_SHORT,27.0"))
        ap = made(char=c)["projections"]["ap10"]
        self.assertEqual((ap["value"], ap["why"]), (None, "fit"))                  # 17% off
        c = load(SAVED.replace('"16,ITEM_MOD_DAMAGE_PER_SECOND_SHORT,20.0", ', ""))
        self.assertEqual(made(char=c)["projections"]["ap10"]["why"], "weapon")


class View(unittest.TestCase):
    def view(self, n=12, broken=2, char=None):
        return build_sheet(made([fight(i) for i in range(n)], char), broken)

    def rows(self, v, group):
        return {f.name: f for f in dict(v.stats)[group]}

    def test_gear(self):
        v = self.view()
        self.assertRegex(v.taken, r"^As of 2\d Nov \d\d:\d\d, your last /reload or logout\.$")
        items = {i.slot: i for i in v.gear}
        head, chest, hand = items["Head"], items["Chest"], items["Main hand"]
        self.assertEqual((head.name, head.rarity, head.ink, head.level, head.flags),
                         ("Humbert's Helm", "uncommon", "q-uncommon", "30", ["lowest"]))
        self.assertEqual((chest.stats, chest.ink), ("255 Armor, +12 Strength", "q-rare"))
        self.assertEqual((hand.stats, hand.flags), ("20.0 damage per second, +15 Strength", ["not enchanted"]))
        self.assertEqual(hand.text, ["Chance on hit: Wounds the target, for 12 damage.", '"It howls."'])
        self.assertEqual((items["Neck"].flags, items["Neck"].empty, items["Neck"].level), (["empty"], True, ""))
        self.assertEqual(v.wear, "2 pieces broken at your last pull.")

    def test_ladder(self):
        l = self.view().ladder
        self.assertEqual((l.mean, l.lo, l.hi, round(l.at, 2)), ("31", 30, 32, .5))
        self.assertEqual(l.verdict, "Average 31, two pieces rare, led by Chest at 32. Twelve slots are empty, and Head is lowest at 30.")
        self.assertEqual(l.marks, [(30, 0, [("Head", "q-uncommon")]), (31, .5, [("Main hand", "q-rare")]), (32, 1, [("Chest", "q-rare")])])
        self.assertEqual(l.rarities, [("rare", "q-rare", 2), ("uncommon", "q-uncommon", 1)])
        same = load(SAVED.replace('"1,4724,30", "5,273035,32"', '"1,4724,31", "5,273035,31"'))
        self.assertEqual(self.view(char=same).ladder.verdict, "Average 31, two pieces rare, every piece at 31. Twelve slots are empty.")
        one = load(SAVED.replace('"1,4724,30", "5,273035,32", ', ""))
        self.assertIsNone(self.view(char=one).ladder)

    def test_stats(self):
        v = self.view()
        primary = self.rows(v, "Primary")["Strength"]
        self.assertEqual((primary.value, primary.note, primary.bar), ("93", "27 from gear", 1))
        self.assertEqual([(i, round(x, 3)) for i, x in primary.gear], [("q-rare", round(27 / 93, 3))])
        power = self.rows(v, "Spells")["Spell power"]
        self.assertEqual((power.value, power.note), ("–", "hidden by the game"))
        self.assertEqual(list(self.rows(v, "Resistances")), ["Shadow resistance"])       # the zero ones are left out
        self.assertEqual(self.rows(v, "Professions")["Mining, Smelting"].value, "120 of 150")
        mine = self.rows(v, "From your fights")
        self.assertEqual((mine["Damage per second"].value, mine["Damage per second"].note), ("50", "measured in 12 fights"))
        self.assertEqual(mine["Average swing"].note, "measured in 24 hits, crits included; the game says 139 to 175, before the enemy's armor takes its part")
        power = self.rows(v, "Attack")["Attack power"]
        self.assertEqual((power.value, power.note, power.estimate), (
            "287", "10 more adds 0.71 damage per second before armor, by the classic formula", True))
        self.assertEqual(list(mine)[-1], "Healing per second")          # unknown: last

    def test_abilities_and_points(self):
        v = self.view()
        a = v.abilities[0]
        self.assertEqual((a.name, a.casts, a.share, round(a.bar, 3)), ("Judgement", "12", "60.0%", .6))
        self.assertEqual([(x.name, x.casts, x.share) for x in v.abilities[1:]], [("Auto attack", "", "40.0%")])      # they add up
        self.assertEqual(v.lead, "Judgement leads your abilities with 60.0% of your damage.")
        self.assertEqual(v.idle, "Known, not cast in a fight: Holy Strike, Redemption.")
        self.assertEqual([(t.name, t.rank, t.of) for t in v.talents], [("Benediction", 5, 5), ("Conviction, Improved", 1, 1)])
        self.assertEqual(v.talents_note, "12 of 51 talents have points.")
        self.assertEqual((v.legacy, v.legacy_note), ([], "0 of 18 Legacy choices have points, 3 points left to spend."))

    def test_inks_are_tokens(self):
        from dips_score.sheet_view import QUALITY, ROLE_INK
        from dips_score.ui.tokens import TOKENS
        for t in TOKENS.values():
            self.assertLessEqual({i for _, i in QUALITY.values()} | set(ROLE_INK.values()), set(t))


if __name__ == "__main__":
    unittest.main()
