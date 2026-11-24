"""The character snapshot: reading it, feeding the spell book, and the habit cards it adds."""
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.config import Paths  # noqa: E402
from dips_score.live.habits import habits  # noqa: E402
from dips_score.live.history import History  # noqa: E402
from dips_score.live.summary import cooldown, learn_cooldowns, summarize  # noqa: E402
from dips_score.sources import luadata  # noqa: E402
from dips_score.sources.combatlog import UnitInfo  # noqa: E402
from dips_score.sources.savedvars import load_char, load_types  # noqa: E402
from test_habits import T0, fight, titles  # noqa: E402
from test_live import ME, MOB, bites, cast, dmg, entry, one_fight  # noqa: E402

SAVED = r'''
dipsScoreLog = {
["version"] = 1,
["runs"] = {},
["char"] = {
["guid"] = "Player-1-A",
["name"] = "Mapomimi",
["class"] = "PRIEST",
["race"] = "Undead",
["level"] = 33,
["taken"] = 1794891447,
["spells"] = {
"589,,1,Shadow Word: Pain",
"8092,8000,1,Mind Blast",
"8102,8500,1,Mind Blast",
"1243,0,0,Power Word: Fortitude",
},
["gear"] = {
"1,100,30",
"4,200,",
"19,300,40",
},
["talents"] = {
"1,Discipline,3",
"2,Holy,0",
"3,Shadow,12",
},
},
}
'''


def load(text=SAVED):
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "dips-Score.lua"
        path.write_text(text, encoding="utf-8")
        return load_char(path)


class LoadChar(unittest.TestCase):
    def test_reads_everything(self):
        c = load()
        self.assertEqual((c["guid"], c["name"], c["class"], c["race"], c["level"]),
                         ("Player-1-A", "Mapomimi", "PRIEST", "Undead", 33))
        sp = c["spells"]
        self.assertEqual(sp["Shadow Word: Pain"], {"cd": None, "harm": True})      # empty: unknown
        self.assertEqual(sp["Power Word: Fortitude"], {"cd": 0, "harm": False})    # 0: the game says none
        self.assertEqual(sp["Mind Blast"], {"cd": 8.5, "harm": True})              # two ranks: the longest
        self.assertEqual(c["gear"], {1: 30, 4: None, 19: 40})
        self.assertEqual((c["talents"], c["spec"]), ([("Discipline", 3), ("Holy", 0), ("Shadow", 12)], "Shadow"))

    def test_no_char_table_or_a_broken_one(self):
        self.assertIsNone(load('dipsScoreLog = {["version"] = 1, ["runs"] = {}}'))
        c = load('dipsScoreLog = {["char"] = {["guid"] = "G", ["spells"] = {"junk", 5}, ["gear"] = "x", '
                 '["talents"] = {"1,Holy,0"}}}')
        self.assertEqual((c["spells"], c["gear"], c["spec"], c["level"]), ({}, {}, None, None))


def char(**kw):
    return {"guid": "Player-1-A", "class": "PRIEST", "race": "Undead", "level": 33, "spec": "Shadow",
            "spells": {}, "gear": {}, "talents": [], **kw}


class SetChar(unittest.TestCase):
    def test_game_cooldowns_reach_the_book(self):
        with tempfile.TemporaryDirectory() as d, patch.dict("os.environ", {"APPDATA": d}):
            h = History(Paths(Path(d)))
            book = h.book("Player-1-A")
            book["Judgement"] = entry(10.0)
            book["Judgement"]["gaps"] = [4.0, 12.0, 30.0]          # spread out: no cooldown learned
            h.set_char(char(spells={"Judgement": {"cd": 8.0, "harm": True}, "Holy Light": {"cd": 0, "harm": False},
                                    "Smite": {"cd": None, "harm": True}}))
            self.assertIsNone(cooldown({**book["Judgement"], "game_cd": None}))
            self.assertEqual(cooldown(book["Judgement"]), 8.0)
            self.assertIsNone(cooldown({**book["Holy Light"], "gaps": [5.0] * 3}))   # game_cd 0: none
            for e in book.values():
                self.assertEqual(set(e), set(entry(1)))          # every key learn_cooldowns reads
            tr, f = one_fight([cast(0, 1, "Smite"), dmg(0.1, ME, MOB, 1, "Smite", 50), *bites()])
            learn_cooldowns(f, tr.me, book)                      # an entry made by set_char works there

    def test_fight_tags(self):
        with tempfile.TemporaryDirectory() as d, patch.dict("os.environ", {"APPDATA": d}):
            h = History(Paths(Path(d)))
            h.set_char(char(gear={1: 30, 2: 40, 4: 1, 19: 1}))
            s = {}
            h.tag(s, "Player-1-A")
            self.assertEqual((s["spec"], s["gear"]), ("Shadow", 35))
            s = {}
            h.tag(s, "someone else")
            self.assertEqual(s, {})


class BestBefore(unittest.TestCase):
    def test_ignores_a_fight_three_levels_lower(self):
        tr, f = one_fight([cast(0, 1, "Smite"), dmg(0.1, ME, MOB, 1, "Smite", 50), *bites()])
        f.events[0].info = UnitInfo("Player-1-A", 1000, 1000, 0, 100, 100, 0.0, 0.0, 0, 0.0, 33)
        old = {"target": "Wolf", "kind": "World", "dps": 999.0}
        s = lambda *hist: summarize(f, tr.me, tr.me_name, {}, list(hist))["best_before"]  # noqa: E731
        self.assertEqual(s({**old, "level": 30}), None)
        self.assertEqual(s({**old, "level": 32}), 999.0)
        self.assertEqual(s(old), 999.0)                          # old history has no level


class BuildCards(unittest.TestCase):
    fights = [fight(i, me="Player-1-A") for i in range(5)]
    spells = {"Exorcism": {"cd": None, "harm": True}, "Hammer of Wrath": {"cd": None, "harm": True},
              "Smite": {"cd": None, "harm": True}, "Heal": {"cd": None, "harm": False}}
    book = {"Smite": {"last": (T0 + timedelta(minutes=3)).isoformat()},
            "Exorcism": {"last": (T0 - timedelta(days=1)).isoformat()}}

    def test_unused_spells_and_empty_slots(self):
        gear = {s: 30 for s in (1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16)}    # everything but ring 2 (slot 12)
        h = habits(self.fights, char(spells=self.spells, gear=gear), self.book)
        cards = {c["title"]: c for c in h["cards"]}
        self.assertNotIn("Spells you never use", cards)     # both need a chance, and none is known
        fights = [dict(f, foes=[["Ghoul", 3], ["Imp", 1]] if i < 3 else [["Wolf", 2]], chances={"Hammer of Wrath": i})
                  for i, f in enumerate(self.fights)]
        spells = dict(self.spells, Consecration={"cd": None, "harm": True})
        h = habits(fights, char(spells=spells, gear=gear), self.book, {"Ghoul": "Undead", "Imp": "Demon",
                                                                       "Wolf": "Beast"})
        cards = {c["title"]: c for c in h["cards"]}
        self.assertEqual(cards["Spells you never use"]["detail"],
                         "You know Consecration and have not cast it in your last 5 fights. "
                         "You know Exorcism and used it 0 of 12 chances (12 undead and demons in 3 fights). "
                         "You know Hammer of Wrath and used it 0 of 10 chances (10 enemies under 20% health in 4 "
                         "fights).")
        self.assertEqual(cards["Gear slots to fill"]["detail"], "Empty gear slots: ring 2")
        self.assertEqual(titles(h)["Gear slots to fill"], "build")
        self.assertEqual(h["char"], {"class": "PRIEST", "race": "Undead", "level": 33, "spec": "Shadow", "gear": 30})

    def test_nothing_without_a_snapshot_flags_or_gear(self):
        h = habits(self.fights)
        self.assertIsNone(h["char"])
        self.assertFalse({"Spells you never use", "Gear slots to fill"} & set(titles(h)))
        unknown = {n: {"cd": None, "harm": None} for n in self.spells}
        self.assertEqual(titles(habits(self.fights, char(spells=unknown), self.book)).keys() & {"Spells you never use",
                         "Gear slots to fill"}, set())             # no harm flags, no gear: both cards skipped


class GearWear(unittest.TestCase):
    def test_load_pulls(self):
        at = int(T0.timestamp())
        c = load(SAVED.replace('["runs"] = {},', f'["runs"] = {{}}, ["pulls"] = {{"{at},85,0", "{at + 60},0,2", "junk"}},'))
        self.assertEqual(c["pulls"], [(T0, 85, 0), (T0 + timedelta(seconds=60), 0, 2)])
        self.assertEqual(load()["pulls"], [])

    def cards(self, *pulls):
        fs = [fight(i, me="Player-1-A") for i in range(5)]        # a fight every 2 minutes from T0
        return titles(habits(fs, char(pulls=list(pulls))))

    def test_cards(self):
        at = lambda i, s=3: T0 + timedelta(minutes=2 * i, seconds=s)  # noqa: E731
        h = habits([fight(i, me="Player-1-A") for i in range(5)], char(pulls=[(at(0), 50, 1), (at(1), 10, 0)]))
        card = next(c for c in h["cards"] if c["title"] == "Pulling with broken gear")
        self.assertEqual((card["kind"], card["detail"]), ("fix", "Broken gear in 1 of your last 2 fights"))
        h = habits([fight(i, me="Player-1-A") for i in range(5)],
                   char(pulls=[(at(0), 50, 0), (at(1), 12, 0), (at(2), 18, 0), (at(3, 30), 5, 0)]))   # the last: too far
        card = next(c for c in h["cards"] if c["title"] == "Gear nearly broken")
        self.assertEqual((card["kind"], card["detail"]),
                         ("build", "Lowest durability under 20% in 2 of your last 3 fights (worst 12%)"))
        self.assertFalse({"Pulling with broken gear", "Gear nearly broken"} & set(self.cards()))
        self.assertFalse({"Pulling with broken gear", "Gear nearly broken"} & set(self.cards((at(0), 90, 0))))


class LoadTypes(unittest.TestCase):
    """dipsScoreDB.types in the account-wide file (Types.lua): enemy name -> creature type"""

    def read(self, text):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "dips-Score.lua"
            path.write_text(text, encoding="utf-8")
            return load_types(path)

    def test_reads_types_beside_the_settings(self):
        text = 'dipsScoreDB = {\n["maxRuns"] = 15,\n["types"] = {\n["Risen Ghoul"] = "Undead",\n' \
               '["Felguard, Elite"] = "Demon",\n["Odd"] = 3,\n},\n}\n'
        self.assertEqual(self.read(text), {"Risen Ghoul": "Undead", "Felguard, Elite": "Demon"})

    def test_empty_when_missing_or_broken(self):
        self.assertEqual(self.read('dipsScoreDB = {\n["maxRuns"] = 15,\n}\n'), {})
        self.assertEqual(self.read('dipsScoreDB = {\n["types"] = {},\n}\n'), {})
        self.assertEqual(self.read('dipsScoreDB = {\n["types"] = "x"\n'), {})   # cut off mid-write
        self.assertEqual(load_types(Path(tempfile.gettempdir()) / "no-such-dir" / "dips-Score.lua"), {})

    def test_account_files_sit_beside_the_realms(self):
        with tempfile.TemporaryDirectory() as d:
            acc = Path(d) / "WTF" / "Account" / "ACC"
            for f in (acc / "SavedVariables", acc / "Realm" / "Char" / "SavedVariables"):
                f.mkdir(parents=True)
                (f / "dips-Score.lua").write_text("", encoding="utf-8")
            self.assertEqual(Paths(wow=Path(d)).account_saved_files(), [acc / "SavedVariables" / "dips-Score.lua"])


if __name__ == "__main__":
    unittest.main()
