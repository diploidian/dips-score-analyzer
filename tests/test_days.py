"""Where your time goes: reading what the add-on counted, the shares, the Player Type, and what it says."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.live.days import NONE, PARTS, TRADE, figures, trade  # noqa: E402
from dips_score.live.titles import PLAIN  # noqa: E402
from dips_score.live.traits import TRAITS  # noqa: E402
from dips_score.sources.savedvars import load_char  # noqa: E402
from dips_score.time_view import NEED, SHOWN, build_time  # noqa: E402
from dips_score.trade_view import NEED as TRADE_NEED, build_trade, coin  # noqa: E402
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
        cols = [x.strip(' "\r\n') for x in lua.split("local COLS = {")[1].split("}")[0].split(",")]
        self.assertEqual({c for parts, _, _ in PARTS.values() for c in parts} | {"away", "turnins", *TRADE}, set(cols))
        self.assertEqual(cols[-len(TRADE):], list(TRADE))           # new columns go at the end

    def test_a_day_twice_and_when_counting_began(self):
        c = load(SAVED.replace('"2026-11-23,1"', '"2026-11-24,40,0,400"'))          # the clock was set back
        self.assertEqual(c["time"]["2026-11-24"], {"away": 100, "trade": 120, "quest": 4000, "hunt": 7200, "turnins": 5})
        begun = lambda n: figures({(T0 - n * DAY).date().isoformat(): {"hunt": 1}}, T0 - 15 * DAY, T0)["since"]  # noqa: E731
        self.assertEqual((begun(14), begun(2)), (None, "2026-11-23"))

    def test_trade(self):
        day = lambda n: (T0 - n * DAY).date().isoformat()  # noqa: E731
        t = {day(20): {"hunt": 3600, "sold": 0}, day(9): {"hunt": 7200, "trade": 600, "auction": 0},
             day(1): {"hunt": 3600, "auction": 2280, "spent": 50275, "mailin": 84620, "sales": 14, "sold": 34},
             day(0): {"quest": 3600, "auction": 0, "mailin": 0}}
        got = trade(t, T0 - 15 * DAY, T0)
        self.assertEqual(got, {"auction": 2280, "spent": 50275, "came": 84620, "sales": 14, "sold": 34, "unread": 0, "blind": 0,
                               "seconds": 14400 + 600, "since": None})
        v = build_trade(got)
        self.assertEqual(v.need, "")
        self.assertEqual(v.say, "Your auctions put 3g 43s 45c in your purse.")
        self.assertEqual(v.cap, "In the last 15 days, as of your last /reload or logout.")
        self.assertEqual([(r.name, r.value, r.unit, r.ink) for r in v.rows], [
            ("Time at the auction house", "38 min", "", "gold"), ("Items sold", "34", "", "m-cast"),
            ("Profit or loss", "3g 43s 45c", "ahead", "role-heal")])
        self.assertEqual(v.rows[0].note, "15% of your play, the auction house window only")
        self.assertEqual(v.rows[2].note, "5g 42s 29c ahead per hour at the auction house. Things you bought and kept count as spent.")
        self.assertEqual([(x.value, round(x.width, 3), x.ink) for x in v.ledger],
                         [("8g 46s 20c", 1, "role-heal"), ("5g 2s 75c", .594, "role-dmg")])
        self.assertIsNone(trade({day(1): {"hunt": 60, "trade": 30, "auction": 0}}, T0 - 15 * DAY, T0))     # nothing counted
        self.assertEqual(build_trade(None).need, TRADE_NEED)
        late = trade({day(20): {"hunt": 1}, day(3): {"hunt": 60000, "auction": 0}, day(2): {"spent": 400, "auction": 300}}, T0 - 15 * DAY, T0)
        v = build_trade(late)
        self.assertEqual((v.say, v.cap), ("Your auctions cost you 4s.",
                                          f"Since {(T0 - 3 * DAY).day} Nov, when counting began, as of your last /reload or logout."))
        self.assertEqual([(r.value, r.unit, r.ink) for r in v.rows], [("5 min", "", "gold"), ("0", "", "m-cast"), ("4s", "behind", "role-dmg")])
        self.assertEqual(v.rows[2].note, "Things you bought and kept count as spent.")           # under 10 minutes: no "per hour"
        self.assertEqual(v.rows[0].note, "under 1% of your play, the auction house window only")

    def test_sale_mails_that_say_little(self):
        base = {"auction": 600, "spent": 100, "came": 100, "seconds": 36000, "since": None}
        rows = lambda **kw: [(r.value, r.unit, r.note) for r in build_trade(base | kw).rows[1:]]  # noqa: E731
        self.assertEqual(rows(sales=1, sold=5, unread=0)[0], ("5", "", "from 1 sale mail you collected"))
        self.assertEqual(rows(sales=3, sold=5, unread=1)[0], ("5", "or more", "from 3 sale mails you collected; 1 didn't say how many"))
        self.assertEqual(rows(sales=2, sold=0, unread=2)[0], ("–", "", "the game didn't say how many were in your 2 sale mails"))
        self.assertEqual(rows(sales=1, sold=5, unread=0)[1], ("0c", "", "Things you bought and kept count as spent."))
        self.assertEqual(build_trade(base | {"sales": 0, "sold": 0, "unread": 0}).say, "Your auctions came out even.")
        quiet = build_trade(base | {"spent": 0, "came": 0, "auction": 20, "sales": 0, "sold": 0, "unread": 0})
        self.assertEqual((quiet.say, quiet.rows[0].value), ("You bought and sold nothing.", "under 1 min"))
        self.assertEqual(rows(spent=99, auction=36000, sales=1, sold=1, unread=0)[1][2], "Things you bought and kept count as spent.")      # 0c an hour: not said
        blind = build_trade(base | {"spent": 900, "came": 0, "sales": 0, "sold": 0, "unread": 0, "blind": 2})
        self.assertEqual((blind.say, [(r.value, r.note) for r in blind.rows[1:]], blind.ledger), (
            "Your sale mails can't be read, so only your time is known.",
            [("–", "the game doesn't show the add-on your sale mails"), ("–", "needs the sale mails too")], []))
        self.assertEqual(build_trade(base | {"sales": 1, "sold": 1, "unread": 0, "blind": 1}).say, "Your auctions came out even.")     # one read: shown

    def test_coin(self):
        self.assertEqual([coin(x) for x in (0, 7, 9017, 10000, 50275, 30005, -123456789, 99.6)],
                         ["0c", "7c", "90s 17c", "1g", "5g 2s 75c", "3g 0s 5c", "12,345g 67s 89c", "1s"])

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
