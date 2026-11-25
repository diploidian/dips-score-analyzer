"""Where your time goes: reading what the add-on counted, the shares, the Player Type, and what it says."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.live.days import NONE, PARTS, figures  # noqa: E402
from dips_score.live.titles import PLAIN  # noqa: E402
from dips_score.live.traits import TRAITS  # noqa: E402
from dips_score.sources.savedvars import load_char  # noqa: E402
from dips_score.time_view import NEED, SHOWN, build_time  # noqa: E402
from dips_score.ui.tokens import TOKENS  # noqa: E402

T0 = datetime(2026, 11, 25, 12)
DAY = timedelta(days=1)
SAVED = """dipsScoreLog = { ["version"] = 1, ["char"] = { ["guid"] = "Player-1-A" }, ["time"] = {
["cols"] = "away,trade,quest,hunt,turnins", ["now"] = { ["day"] = "2026-11-25", ["quest"] = 310.25, ["away"] = -4, ["hunt"] = "x" },
["days"] = { "2026-11-24,60,120,3600,7200,5,99", "2026-11-23,1", "nonsense,1,2", "2026-13-40,1,2" }, },
["levels"] = { "1795594976,39", "x,1", "1795594976" },
["weapons"] = { "1795594976,267369:0", "1795594990,0:0", "x,1:2", "1795594999,267369", "1795594999,a:1" } }"""


def load(text):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "dips-Score.lua"
        p.write_text(text, encoding="utf-8")
        return load_char(p)


def of(hours: dict, day="2026-11-25"):
    first = (T0 - 14 * DAY).date().isoformat()         # counted all through the window
    return figures({first: {}, day: {k: v * 3600 for k, v in hours.items()}}, T0 - 15 * DAY, T0)


class Days(unittest.TestCase):
    def test_load(self):
        c = load(SAVED)
        self.assertEqual(c["time"], {"2026-11-24": {"away": 60, "trade": 120, "quest": 3600, "hunt": 7200, "turnins": 5},
                                     "2026-11-23": {"away": 1}, "2026-11-25": {"quest": 310.25}})
        self.assertEqual(c["levels"], [(1795594976, 39)])
        self.assertEqual(c["weapons"], [(1795594976, (267369, 0)), (1795594990, (0, 0))])
        for odd in ("", '["time"] = 3, ["levels"] = 4', '["time"] = { ["now"] = 1, ["days"] = { } }'):
            c = load('dipsScoreLog = { ["version"] = 1, ["char"] = { ["guid"] = "A" }, ' + odd + " }")
            self.assertEqual((c["time"], c["levels"]), ({}, []))

    def test_the_columns_are_the_add_ons(self):
        lua = (Path(__file__).resolve().parents[1] / "addon/dips-Score/Life.lua").read_text(encoding="utf-8")
        cols = [x.strip(' "') for x in lua.split("local COLS = {")[1].split("}")[0].split(",")]
        self.assertEqual({c for parts, _, _ in PARTS.values() for c in parts} | {"away", "turnins"}, set(cols))

    def test_a_day_twice_and_when_counting_began(self):
        c = load(SAVED.replace('"2026-11-23,1"', '"2026-11-24,40,0,400"'))          # the clock was set back
        self.assertEqual(c["time"]["2026-11-24"], {"away": 100, "trade": 120, "quest": 4000, "hunt": 7200, "turnins": 5})
        begun = lambda n: figures({(T0 - n * DAY).date().isoformat(): {"hunt": 1}}, T0 - 15 * DAY, T0)["since"]  # noqa: E731
        self.assertEqual((begun(14), begun(2)), (None, "2026-11-23"))

    def test_fights_with_players(self):
        """what the log saw of them is the least; the rest of the day makes room, and no second is added"""
        days = {(T0 - n * DAY).date().isoformat(): {"hunt": 600, "quest": 300, "skirmish": 60} for n in (0, 1, 9)}
        at = lambda n, s, **kw: {"start": (T0 - n * DAY).isoformat(), "duration": s, "kind": "PvP", "instance": 0} | kw  # noqa: E731
        share = lambda *fs: figures(days, T0 - 15 * DAY, T0, fs)  # noqa: E731
        secs = lambda f: {p: round(s * f["seconds"]) for p, s in f["parts"].items()}  # noqa: E731
        self.assertEqual(secs(share()), {"hunt": 1800, "quest": 900, "pvp": 180})
        self.assertEqual(secs(share(at(0, 200), at(0, 560))), {"hunt": 1200, "quest": 800, "pvp": 880})     # 700 more than was seen
        self.assertEqual(secs(share(at(0, 50), at(9, 500), at(1, 500, instance=30), at(1, 500, kind="World"))), secs(share()))
        self.assertEqual(share(at(0, 9999))["seconds"], share()["seconds"])
        self.assertEqual(days[T0.date().isoformat()], {"hunt": 600, "quest": 300, "skirmish": 60})

    def test_windows_do_not_share_a_day(self):
        time = {(T0 - n * DAY).date().isoformat(): {"hunt": 1} for n in range(40)}
        now, before = figures(time, T0 - 15 * DAY, T0), figures(time, T0 - 30 * DAY, T0 - 15 * DAY)
        self.assertEqual((now["seconds"], before["seconds"]), (15, 15))
        self.assertIsNone(figures(time, T0 + DAY, T0 + 2 * DAY))
        self.assertIsNone(figures(None, T0 - DAY, T0))

    def test_type(self):
        self.assertEqual((of({"hunt": 4.9})["type"], of({"hunt": 5})["type"]), (None, "Huntmaster"))
        f = of({"quest": 6, "hunt": 3, "town": 1, "away": 50})       # away is in no share
        self.assertEqual((f["seconds"], f["type"], f["second"], f["parts"]["quest"]), (36000, "Errant", "hunt", .6))
        self.assertEqual(of({"hunt": 3.5, "trade": 3, "town": 3.5})["type"], "Merchant Prince")       # twice its bar
        self.assertEqual(of({"quest": 6, "trade": 2, "town": 2})["type"], "Errant")                   # most of the bar leads
        self.assertEqual(of({"hunt": 2.5, "quest": 2.5, "town": 2.5, "dungeon": 2.5})["type"], NONE)
        self.assertIsNone(of({"hunt": 8, "town": 1.9, "quest": .1})["second"])
        self.assertEqual(of({"taxi": 3, "roam": 3})["type"], "Wayfarer")
        for p, (cols, _, name) in PARTS.items():
            self.assertEqual((of({cols[0]: 9})["type"], of({cols[0]: 9})["lead"]), (name, p))

    def test_types_are_their_own(self):
        """no type is an epithet, a class noun or a plain title already"""
        names = [name for _, _, name in PARTS.values()] + [NONE]
        self.assertEqual(len(set(names)), len(names))
        taken = {e for t in TRAITS for e in t.epithets} | set(PLAIN.values())
        self.assertFalse(set(names) & taken)


class View(unittest.TestCase):
    def test_need(self):
        self.assertEqual(build_time(None, None).need, NEED)
        self.assertEqual(build_time(of({"hunt": 3.5}), None).need, "Your time bar needs 5 hours of play with the add-on (3 h 30 min so far).")

    def test_bar(self):
        now = of({"hunt": 5, "quest": 3, "town": 1.98, "pvp": .02, "away": 2, "turnins": 12 / 3600})
        v = build_time(now, of({"hunt": 4, "quest": 6}))
        self.assertEqual((v.need, v.type), ("", "Huntmaster, and part Errant"))
        self.assertEqual(v.meta, "10 h 0 min played in the last 15 days, as of your last /reload or logout.")
        self.assertEqual([(p.name, p.time, p.share, p.chip) for p in v.parts], [
            ("Hunting", "5 h 0 min", "50%", "+10 pts vs the 15 days before"), ("Questing", "3 h 0 min", "30%", "−30 pts vs the 15 days before"),
            ("In town", "1 h 59 min", "20%", "+20 pts vs the 15 days before"), ("PvP", "1 min", "under 1%", "")])
        self.assertAlmostEqual(sum(p.width for p in v.parts), 1)
        self.assertEqual(v.note, "12 quests handed in. 2 h 0 min away left out.")
        self.assertFalse(any(p.chip for p in build_time(now, of({"hunt": 4})).parts))        # too little before to compare
        part = {**of({"hunt": 4, "quest": 6}), "since": "2026-11-09"}
        self.assertFalse(any(p.chip for p in build_time(now, part).parts))                   # not all of it was counted
        self.assertTrue(build_time({**now, "since": "2026-11-23"}, None).meta.startswith("10 h 0 min played since 23 Nov, when counting began, as"))

    def test_inks(self):
        self.assertEqual(set(SHOWN), set(PARTS))
        for look in TOKENS.values():
            self.assertEqual(len({look[ink] for _, ink in SHOWN.values()}), len(SHOWN))


if __name__ == "__main__":
    unittest.main()
