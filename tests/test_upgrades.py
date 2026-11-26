"""Upgrades: what in the last auction house scan beats what you wear, against which worn piece, at what price, and how the
drawer says it."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.config import Paths  # noqa: E402
from dips_score.live.gearworth import AP, DPS, STR  # noqa: E402
from dips_score.live.upgrades import FILE, pick, remember, upgrades  # noqa: E402
from dips_score.upgrades_view import NEED, build_upgrades  # noqa: E402

T0 = datetime(2026, 11, 25, 12)
TAKEN = int((T0 - timedelta(hours=2)).timestamp())
S = {"gear_role": "melee", "measured": {}, "class": "WARRIOR"}


def row(n, kind, stats, price=10000, name=None, iid=None, unique=False, base=None):
    name = name or f"Item {n}"
    return {"n": n, "kind": kind, "id": iid or 1000 + n, "level": 30, "quality": 3, "price": price, "count": 1, "unique": unique,
            "name": name, "base": base or name, "stats": stats, "tips": [(True, name, ""), (True, f"+{n} Strength", "")], "link": None}


def char(rows, worn=None, tips=None, money=1000000):
    worn = worn or {}
    return {"class": "WARRIOR", "items": {s: {"id": i} for s, (i, _) in worn.items()}, "itemstats": {s: st for s, (_, st) in worn.items() if st is not None},
            "tips": tips or {}, "market": {"taken": TAKEN, "money": money, "rows": rows}}


def got(c, s=S, **kw):
    return upgrades(c, s, now=T0, **kw)


class Compare(unittest.TestCase):
    def test_the_weaker_ring(self):
        worn = {11: (1, {STR: 10}), 12: (2, {STR: 2})}
        u = got(char([row(1, 11, {STR: 6}), row(2, 11, {STR: 1})], worn))
        r, = u["rows"]                                     # the second is no better than the weaker ring
        self.assertEqual((r["slot"], r["gain"]["rank"], r["source"], r["age"]), ("Ring", 8, "scan", 7200))
        self.assertEqual(got(char([row(1, 12, {STR: 2})], {13: (1, {STR: 5})}))["rows"][0]["gain"]["rank"], 4)    # an empty trinket slot

    def test_a_two_hander_against_main_and_off_hand(self):
        worn = {16: (1, {STR: 10}), 17: (2, {STR: 5})}
        u = got(char([row(1, 17, {STR: 20}), row(2, 13, {STR: 12})], worn))
        self.assertEqual([(r["slot"], r["gain"]["rank"]) for r in u["rows"]], [("Two-hand", 10), ("One-hand", 4)])

    def test_a_one_hander_while_a_two_hander_is_worn(self):
        tips = {16: [(True, "Big Sword", ""), (True, "Two-Hand", "Sword")]}
        u = got(char([row(1, 13, {STR: 50}), row(2, 22, {STR: 50}), row(3, 1, {STR: 3})], {16: (1, {STR: 20})}, tips))
        self.assertEqual([(r["n"], r["gain"] is None) for r in u["rows"]], [(3, False), (1, True), (2, True)])     # not compared, last
        self.assertEqual(u["rows"][1]["why"], "you wear a two-hander")

    def test_a_unique_clash_is_dropped(self):
        worn = {11: (4567, {STR: 10}), 12: (2, {STR: 2})}
        u = got(char([row(1, 11, {STR: 20}, iid=4567, unique=True), row(2, 11, {STR: 20}, iid=4567)], worn))
        self.assertEqual([r["n"] for r in u["rows"]], [2])

    def test_what_is_not_known(self):
        bare = row(1, 1, {})
        bare["tips"] = []
        u = got(char([bare, row(2, 1, {STR: 5}), row(3, 99, {STR: 5})], {1: (7, None)}))
        self.assertEqual(u["unread"], 1)                   # not looked at closely: no stats
        r, = u["rows"]                                     # an unknown kind of slot is left out
        self.assertEqual((r["gain"], r["why"]), (None, "the stats of what you wear there were not read"))
        self.assertIsNone(got(char([])))
        self.assertIsNone(upgrades(None, S))

    def test_measured_and_a_weapon(self):
        s = S | {"measured": {AP: {"value": .07, "n": 600, "of": "swing"}}}
        u = got(char([row(1, 1, {AP: 30, STR: 2}), row(2, 13, {AP: 30, DPS: 12})], {1: (7, {AP: 10}), 16: (8, {DPS: 10})}), s)
        head, sword = sorted(u["rows"], key=lambda r: r["n"])
        self.assertEqual((round(head["gain"]["dps"], 2), head["gain"]["points"], head["gain"]["rank"]), (1.4, 4, 24))
        self.assertEqual((sword["gain"]["dps"], sword["gain"]["points"]), (None, 58))     # a weapon is always standard

    def test_gain_per_gold(self):
        u = got(char([row(1, 1, {STR: 10}, price=100000), row(2, 3, {STR: 5}, price=10000)]))
        big, cheap = u["rows"]
        self.assertEqual((big["n"], big["per_gold"], big["gold_rank"], cheap["per_gold"], cheap["gold_rank"]), (1, 2, 2, 10, 1))


class Prices(unittest.TestCase):
    def history(self, key, price, days=3):
        return {key: {(T0.date() - timedelta(days=d)).isoformat(): price for d in range(days)}}

    def test_cap_and_overpriced(self):
        c = char([row(1, 1, {STR: 10}, price=5000), row(2, 3, {STR: 10}, price=3000)])
        rows = got(c, history=self.history("1001:Item 1", 1000))["rows"]
        self.assertEqual([(r["n"], r["usual"]) for r in rows], [(2, None), (1, 1000)])     # as much gain: the cheaper first
        self.assertEqual([r["n"] for r in pick(rows, None, 2)], [2])           # five times its usual price
        self.assertEqual([r["n"] for r in pick(rows, None, 10)], [2, 1])
        self.assertEqual([r["n"] for r in pick(rows, 4000, None)], [2])         # over the gold
        v = build_upgrades(got(c, history=self.history("1001:Item 1", 1000)), gold=1, times=2)
        self.assertEqual(v.hidden, "1 costs over 2 times its usual price.")
        v = build_upgrades(got(c), gold=1, times=2)
        self.assertEqual((len(v.rows), v.hidden), (2, ""))

    def test_web_prices_only_for_an_item_under_its_own_name(self):
        web = {1001: {"min": 600, "median": 777, "seen": "2026-11-24T12:00:00", "source": "wowauctions"}, "1002": {"min": 500, "source": "undermine"}}
        c = char([row(1, 1, {STR: 10}), row(2, 3, {STR: 10}, name="Cap of the Monkey", iid=1002, base="Cap")])
        by = {r["n"]: r for r in got(c, web=web)["rows"]}
        self.assertEqual((by[1]["usual"], by[1]["usual_from"], by[1]["usual_min"]), (777, "wowauctions", False))
        self.assertEqual((by[2]["usual"], by[2]["usual_from"]), (None, None))         # the sites blend random-stat variants
        own = got(c, web=web, history=self.history("1001:Item 1", 900))["rows"]
        self.assertEqual((own[0]["usual"], own[0]["usual_from"]), (900, "your scans"))     # enough days of your own
        v = build_upgrades(got(c, web=web), times=20, now=T0)
        self.assertEqual(v.rows[0].source, "From your scan 2 h ago. Usually 7s 77c on wowauctions.net, 24 h ago.")

    def test_remember(self):
        with tempfile.TemporaryDirectory() as d, patch.dict("os.environ", {"APPDATA": d}):
            paths = Paths(Path(d))
            old = (T0.date() - timedelta(days=40)).isoformat()
            (paths.data_dir).mkdir(parents=True)
            (paths.data_dir / FILE).write_text(json.dumps({"days": {"5:Gone": {old: 10}, "1001:Item 1": {old: 1, "2026-11-24": 800}}}), encoding="utf-8")
            m = char([row(1, 1, {}, price=900), row(9, 1, {}, price=700, iid=1001, name="Item 1")])["market"]
            days = remember(paths, m, T0)
            self.assertEqual(days, {"1001:Item 1": {"2026-11-24": 800, "2026-11-25": 700}})     # the lowest of the day; 30 days kept
            self.assertEqual(json.loads((paths.data_dir / FILE).read_text(encoding="utf-8"))["days"], days)
            (paths.data_dir / FILE).write_text("broken", encoding="utf-8")
            self.assertEqual(remember(paths, None, T0), {})


class View(unittest.TestCase):
    def test_the_drawer(self):
        self.assertEqual(build_upgrades(None).need, NEED)
        s = S | {"measured": {AP: {"value": .05, "n": 600, "of": "swing"}}}
        c = char([row(1, 1, {AP: 20, STR: 5}, price=25000, name="Helm, Shiny"), row(2, 3, {STR: 2}, price=500)], money=400000)
        v = build_upgrades(got(c, s), now=T0)
        self.assertEqual((v.gold, v.most), (20, 40))                           # half of what you had, at first
        self.assertEqual(v.say, "Helm, Shiny is your biggest upgrade, for 2g 50s. Item 2 gives the most for your gold.")
        helm = v.rows[0]
        self.assertEqual((helm.ink, helm.slot, helm.price, helm.gain, helm.points, helm.per_gold),
                         ("q-rare", "Head", "2g 50s", "+1 damage per second, measured", "+10 points, standard", "12.0 points per gold"))
        self.assertEqual(helm.tip, "Helm, Shiny\n+1 Strength")
        self.assertTrue(v.cap.startswith("From your scan at the auction house 2 h ago, with 40g on you. Points are standard estimates"))
        v = build_upgrades(got(c, s), gold=1, now=T0)
        self.assertEqual(([r.name for r in v.rows], v.hidden), (["Item 2"], "1 more costs over 1g."))
        v = build_upgrades(got(char([row(1, 1, {STR: 1})], {1: (7, {STR: 9})})), now=T0)
        self.assertEqual((v.rows, v.say), ([], "Nothing in your scan beats what you wear."))


if __name__ == "__main__":
    unittest.main()
