"""The live fight tracker and summaries, on a small made-up log."""
import copy
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score import removed  # noqa: E402
from dips_score.live.summary import cooldown, learn_cooldowns, summarize  # noqa: E402
from dips_score.config import Paths  # noqa: E402
from dips_score.live.history import History  # noqa: E402
from dips_score.live.tracker import Tracker  # noqa: E402
from dips_score.sources.combatlog import UnitInfo  # noqa: E402

ME = 'Player-1-A,"Nikana-Diploidian-PvP-US",0x511,0x80000000'
MOB = 'Creature-0-1-1-1-100-1,"Wolf",0xa48,0x80000000'
MOB2 = 'Creature-0-1-1-1-100-2,"Wolf",0xa48,0x80000000'
NONE = '0000000000000000,nil,0x80000000,0x80000000'


def line(sec: float, rest: str) -> str:
    m, s = divmod(sec, 60)
    return f"11/17/2026 12:{int(m):02d}:{s:06.3f}-8  {rest}"


def dmg(sec, src, dst, spell_id, name, amount):
    return line(sec, f"SPELL_DAMAGE,{src},{dst},{spell_id},\"{name}\",0x20,{amount},{amount},-1,32,0,0,0,nil,nil,nil")


class Live(unittest.TestCase):
    def test_two_fights_and_a_summary(self):
        log = [
            line(0, f"SPELL_CAST_SUCCESS,{ME},{MOB},8092,\"Mind Blast\",0x20"),
            dmg(0.1, ME, MOB, 8092, "Mind Blast", 300),
            # the wolf bites every 2 s, so the fight stays on
            *[line(t, f"SWING_DAMAGE,{MOB},{ME},20,20,-1,1,0,0,0,nil,nil,nil") for t in (2, 4, 6, 8)],
            line(10, f"SPELL_CAST_SUCCESS,{ME},{MOB},8092,\"Mind Blast\",0x20"),
            dmg(10.1, ME, MOB, 8092, "Mind Blast", 320),
            line(12, f"UNIT_DIED,{NONE},{MOB},0"),
            # 30 s later: a second fight, which also shows the first one is over
            dmg(42, ME, MOB2, 8092, "Mind Blast", 310),
            dmg(45, ME, MOB2, 589, "Shadow Word: Pain", 90),
            line(45.5, f"UNIT_DIED,{NONE},{MOB2},0"),
            line(60, f"SPELL_AURA_APPLIED,{ME},{ME},588,\"Inner Fire\",0x2,BUFF"),
        ]
        tr = Tracker()
        fights = tr.feed_lines(log)
        self.assertEqual(len(fights), 2)
        self.assertEqual(tr.me, "Player-1-A")
        first, second = fights
        self.assertAlmostEqual((first.end - first.start).total_seconds(), 10.1, places=1)
        self.assertAlmostEqual(second.since_last, 31.9, places=1)
        cds = {}
        learn_cooldowns(first, tr.me, cds)
        self.assertEqual(cds["Mind Blast"]["gaps"], [10.0])
        s = summarize(first, tr.me, tr.me_name, cds, [])
        self.assertEqual((s["target"], s["kind"], s["result"], s["damage"]), ("Wolf", "World", "killed", 620))
        self.assertEqual(s["foes"][0][0], "Wolf")
        later = summarize(second, tr.me, tr.me_name, cds, [s])
        self.assertEqual(later["best_before"], s["dps"])
        self.assertTrue({"own", "rest"} <= set(s["pull"]) and "level" in s)

    def test_a_player_names_the_fight(self):
        rogue = 'Player-2-B,"Jonaallday-Oneshot-PvP-US",0x548,0x80000000'
        log = [
            dmg(0, ME, MOB, 8092, "Mind Blast", 600),
            dmg(1, rogue, ME, 8676, "Ambush", 300),
            dmg(2, ME, rogue, 589, "Shadow Word: Pain", 40),     # the wolf took far more, but the rogue names it
            dmg(3, ME, MOB, 8092, "Mind Blast", 600),
            line(4, f"UNIT_DIED,{NONE},{MOB},0"),
            line(20, f"SPELL_AURA_APPLIED,{ME},{ME},588,\"Inner Fire\",0x2,BUFF"),
        ]
        tr = Tracker()
        s = summarize(tr.feed_lines(log)[0], tr.me, tr.me_name, {}, [])
        self.assertEqual((s["target"], s["more"], s["kind"]), ("Jonaallday Oneshot", 1, "PvP"))
        self.assertEqual([n for n, _ in s["foes"]], ["Jonaallday Oneshot", "Wolf"])


    def test_rest_counts_first_aid_not_the_bandage_debuff(self):
        log = [
            line(0, f"SPELL_AURA_APPLIED,{ME},{ME},746,\"First Aid\",0x1,BUFF"),
            line(1, f"SPELL_AURA_APPLIED,{ME},{ME},11196,\"Recently Bandaged\",0x1,DEBUFF"),
            line(6, f"SPELL_AURA_REMOVED,{ME},{ME},746,\"First Aid\",0x1,BUFF"),
            dmg(8, ME, MOB, 8092, "Mind Blast", 300),
            line(9, f"UNIT_DIED,{NONE},{MOB},0"),
            line(20, f"SPELL_AURA_APPLIED,{ME},{ME},588,\"Inner Fire\",0x2,BUFF"),
        ]
        tr = Tracker()
        f = tr.feed_lines(log)[0]
        self.assertAlmostEqual(f.rest, 6.0, places=1)

    def test_one_combat_stays_one_fight(self):
        bite = lambda t, mob: line(t, f"SWING_DAMAGE,{mob},{ME},20,20,-1,1,0,0,0,nil,nil,nil")  # noqa: E731
        log = [
            dmg(0, ME, MOB, 8092, "Mind Blast", 300), bite(1, MOB), bite(2, MOB2),
            line(3, f"UNIT_DIED,{NONE},{MOB2},0"),
            # the wolf runs off for 11 s (still alive), then comes back: the same combat
            dmg(14, ME, MOB, 589, "Shadow Word: Pain", 90), bite(15, MOB),
            line(16, f"UNIT_DIED,{NONE},{MOB},0"),
            # a new wolf joins 3 s after the last one died: still the same combat
            dmg(19, ME, 'Creature-0-1-1-1-100-3,"Wolf",0xa48,0x80000000', 8092, "Mind Blast", 280),
            line(20, f"UNIT_DIED,{NONE},Creature-0-1-1-1-100-3,\"Wolf\",0xa48,0x80000000,0"),
            line(40, f"SPELL_AURA_APPLIED,{ME},{ME},588,\"Inner Fire\",0x2,BUFF"),
        ]
        tr = Tracker()
        closings = tr.feed_lines(log)
        fights = {id(f): f for f in closings}.values()
        self.assertEqual(len(fights), 1)
        f = next(iter(fights))
        self.assertEqual(len(f.foes), 3)
        self.assertAlmostEqual((f.end - f.start).total_seconds(), 19, places=0)

    def _wall(self, log, *seconds):
        """feed the log at real time 100, then tick() at each later real time; returns what tick() gave"""
        tr = Tracker()
        with patch("dips_score.live.tracker.time.monotonic") as mono:
            mono.return_value = 100.0
            tr.feed_lines(log)
            out = []
            for t in seconds:
                mono.return_value = 100.0 + t
                out.append(tr.tick())
        return tr, out

    def test_a_kill_closes_after_two_seconds_of_real_time(self):
        log = [dmg(0, ME, MOB, 8092, "Mind Blast", 300), line(1, f"UNIT_DIED,{NONE},{MOB},0")]
        tr, (early, late) = self._wall(log, 1.5, 2.5)
        self.assertIsNone(early)
        self.assertTrue(late.closed_by_wall)

    def test_more_fighting_after_a_wall_close_reopens_it(self):
        log = [dmg(0, ME, MOB, 8092, "Mind Blast", 300), line(1, f"UNIT_DIED,{NONE},{MOB},0")]
        tr, (f,) = self._wall(log, 2.5)
        again = tr.feed_lines([dmg(3, ME, MOB2, 8092, "Mind Blast", 300), line(4, f"UNIT_DIED,{NONE},{MOB2},0"),
                               line(30, f"SPELL_AURA_APPLIED,{ME},{ME},588,\"Inner Fire\",0x2,BUFF")])
        self.assertEqual((again[0].start, again[0].reopened), (f.start, 1))

    def test_a_live_enemy_waits_ten_seconds(self):
        log = [dmg(0, ME, MOB, 8092, "Mind Blast", 300)]
        tr, (a, b, c) = self._wall(log, 2.5, 9.5, 10.5)
        self.assertIsNone(a)
        self.assertIsNone(b)
        self.assertIsNotNone(c)


def cast(sec, spell_id, name, src=ME, dst=MOB):
    return line(sec, f"SPELL_CAST_SUCCESS,{src},{dst},{spell_id},\"{name}\",0x2")


def bites(until=30, every=2):
    return [line(t, f"SWING_DAMAGE,{MOB},{ME},20,20,-1,1,0,0,0,nil,nil,nil") for t in range(every, until + 1, every)]


def entry(cd, avg=500, **kw):
    return {"gaps": [cd] * 3, "spam": False, "last": None, "avg": avg, "cast": False, "cost": 0, "game_cd": None, **kw}


def one_fight(log):
    tr = Tracker()
    fights = tr.feed_lines(log + [line(59, f"SPELL_AURA_APPLIED,{ME},{ME},588,\"Inner Fire\",0x2,BUFF")])
    return tr, fights[-1]


class Cooldowns(unittest.TestCase):
    def fight(self, book, *extra, sooner=timedelta(minutes=5)):
        """a 30 s fight with Mind Blast cast once; every book entry was last cast `sooner` before it"""
        tr, f = one_fight([cast(0, 8092, "Mind Blast"), dmg(0.1, ME, MOB, 8092, "Mind Blast", 300), *extra, *bites()])
        for e in book.values():
            e["last"] = (f.start - sooner).isoformat()
        learn_cooldowns(f, tr.me, book)
        return summarize(f, tr.me, tr.me_name, book, [])

    def test_a_cooldown_never_cast_is_missed(self):
        s = self.fight({"Judgement": entry(10.0)})
        row = next(r for r in s["cooldowns"] if r["name"] == "Judgement")
        self.assertEqual(row["used"], 0)
        self.assertGreaterEqual(row["missed"], 1)
        self.assertGreater(row["lost"], 0)

    def test_excused_misses_are_not_counted(self):
        s = self.fight({"Judgement": entry(10.0)})
        row = s["cooldowns"][0]
        self.assertEqual(row["counted"], min(row["missed"], max(1, round(row["free"] / 10))))
        # cast on time: ready under 2 s each time, so nothing counted
        tr, f = one_fight([*[cast(t, 20271, "Judgement") for t in (0, 10, 20, 30)],
                           dmg(0.1, ME, MOB, 20271, "Judgement", 200), *bites(30)])
        book = {}
        learn_cooldowns(f, tr.me, book)
        row = summarize(f, tr.me, tr.me_name, book, [])["cooldowns"][0]
        self.assertEqual(row["counted"], 0)

    def test_damage_under_a_longer_name_belongs_to_the_cast(self):
        tr, f = one_fight([*[cast(t, 20271, "Judgement") for t in (0, 10, 20, 30)],
                           *[dmg(t + 0.1, ME, MOB, 20187, "Judgement of Command", 200) for t in (0, 10, 20, 30)],
                           *bites(34)])
        book = {}
        learn_cooldowns(f, tr.me, book)
        self.assertEqual(book["Judgement"]["avg"], 200)
        s = summarize(f, tr.me, tr.me_name, book, [])
        self.assertEqual([r["name"] for r in s["cooldowns"]], ["Judgement"])
        self.assertIn("Judgement of Command", [a["name"] for a in s["abilities"]])

    def test_idle_counts_only_with_a_filler(self):
        log = [cast(0, 8092, "Mind Blast"), dmg(0.1, ME, MOB, 8092, "Mind Blast", 300), *bites(30)]
        tr, f = one_fight(log)
        none = summarize(f, tr.me, tr.me_name, {}, [])
        self.assertEqual((none["idle"]["filler"], none["idle"]["lost"]), (False, 0))
        self.assertFalse(any("idle" in x for x in none["improve"]))
        smite = {"Smite": {**entry(1.0, avg=100), "gaps": [], "spam": True}}
        unsure = {"Exorcism": {**entry(1.0, avg=100), "gaps": [19.7, 24.4], "cost": 85}}   # cooldown not confirmed
        nuke = {"Shadow Bolt": entry(2.6, avg=100, cast=True)}                            # confirmed under 4 s
        self.assertFalse(summarize(f, tr.me, tr.me_name, unsure, [])["idle"]["filler"])
        self.assertTrue(summarize(f, tr.me, tr.me_name, nuke, [])["idle"]["filler"])
        some = summarize(f, tr.me, tr.me_name, smite, [])
        self.assertTrue(some["idle"]["filler"])
        self.assertGreater(some["idle"]["lost"], 0)

    def test_a_proc_is_not_a_cast(self):
        seal = lambda t, sid: cast(t, sid, "Seal of Command", dst=ME)  # noqa: E731
        tr, f = one_fight([
            dmg(0, ME, MOB, 8092, "Mind Blast", 300),
            line(0.2, f"SPELL_AURA_APPLIED,{ME},{ME},20375,\"Seal of Command\",0x2,BUFF"), seal(0.21, 20375),
            *[x for t in (1, 1.5, 5) for x in (seal(t, 20424), dmg(t + 0.01, ME, MOB, 20424, "Seal of Command", 50))],
            *bites(10)])
        book = {}
        learn_cooldowns(f, tr.me, book)
        self.assertEqual((book["Seal of Command"]["gaps"], book["Seal of Command"]["spam"]), ([], False))
        s = summarize(f, tr.me, tr.me_name, book, [])
        row = next(a for a in s["abilities"] if a["name"] == "Seal of Command")
        self.assertEqual((row["casts"], row["damage"]), (1, 150))     # the real cast only; the procs' damage counts


    def test_proc_damage_is_not_the_casts_value(self):
        seal = lambda t, sid: cast(t, sid, "Seal of Command", dst=ME)  # noqa: E731
        tr, f = one_fight([
            dmg(0, ME, MOB, 8092, "Mind Blast", 300),
            line(0.2, f"SPELL_AURA_APPLIED,{ME},{ME},20375,\"Seal of Command\",0x2,BUFF"), seal(0.21, 20375),
            *[x for t in (1, 5) for x in (seal(t, 20424), dmg(t + 0.01, ME, MOB, 20424, "Seal of Command", 50))],
            *bites(10)])
        book = {}
        learn_cooldowns(f, tr.me, book)
        self.assertEqual(book["Seal of Command"]["avg"], 0)
        book["Seal of Command"]["gaps"] = [5.0] * 3          # even with a confirmed "cooldown": no row
        s = summarize(f, tr.me, tr.me_name, book, [])
        self.assertNotIn("Seal of Command", [r["name"] for r in s["cooldowns"]])
        self.assertFalse(s["idle"]["filler"])

    def test_dropped_long_ago_is_not_shown(self):
        s = self.fight({"Judgement": entry(10.0)}, sooner=timedelta(days=8))
        self.assertEqual(s["cooldowns"], [])

    def test_one_short_gap_does_not_set_it(self):
        self.assertEqual(cooldown({"gaps": [3.0, 10.0, 10.2, 10.4]}), 10.0)
        self.assertIsNone(cooldown({"gaps": [3.0, 10.0]}))
        self.assertIsNone(cooldown({"gaps": [10.0] * 3, "spam": True}))
        self.assertEqual(cooldown({"gaps": [10.0] * 3, "game_cd": 8.0}), 8.0)
        self.assertEqual(cooldown({"gaps": [], "game_cd": 8.0}), 8.0)

    def test_a_spread_out_habit_is_no_cooldown(self):
        self.assertIsNone(cooldown({"gaps": [2.94, 3.54, 4.38, 4.93, 5.15, 5.54]}))   # re-sealing after Judgement

    def test_game_says_no_cooldown(self):
        self.assertIsNone(cooldown({"gaps": [10.0] * 3, "game_cd": 0}))
        self.assertEqual(cooldown({"gaps": [10.0] * 3, "game_cd": None}), 10.0)

    def test_cast_twice_quickly_is_no_cooldown(self):
        tr, f = one_fight([cast(0, 585, "Smite"), cast(1.5, 585, "Smite"), *[cast(t, 585, "Smite") for t in (12, 24, 36)],
                           dmg(0.1, ME, MOB, 585, "Smite", 100), *bites(40)])
        book = {}
        learn_cooldowns(f, tr.me, book)
        self.assertTrue(book["Smite"]["spam"])
        self.assertIsNone(cooldown(book["Smite"]))

    def test_learning_twice_changes_nothing(self):
        tr, f = one_fight([*[cast(t, 8092, "Mind Blast") for t in (0, 10, 20, 30)],
                           dmg(0.1, ME, MOB, 8092, "Mind Blast", 300), *bites(34)])
        book = {}
        self.assertTrue(learn_cooldowns(f, tr.me, book))
        once = copy.deepcopy(book)
        self.assertFalse(learn_cooldowns(f, tr.me, book))
        self.assertEqual(book, once)
        self.assertEqual(cooldown(book["Mind Blast"]), 10.0)

    def test_two_ranks_are_one_spell(self):
        tr, f = one_fight([cast(0, 20271, "Judgement"), cast(10, 20184, "Judgement"), cast(20, 20271, "Judgement"),
                           cast(30, 20184, "Judgement"), dmg(0.1, ME, MOB, 20271, "Judgement", 200), *bites(34)])
        book = {}
        learn_cooldowns(f, tr.me, book)
        self.assertEqual(list(book), ["Judgement"])
        s = summarize(f, tr.me, tr.me_name, book, [])
        self.assertEqual([(r["name"], r["used"]) for r in s["cooldowns"]], [("Judgement", 4)])

    def test_long_cooldown_held_off_a_boss(self):
        world = self.fight({"Hammer": entry(90.0)})
        self.assertEqual(world["kind"], "World")
        self.assertEqual((world["cooldowns"][0].get("held"), world["cooldowns"][0]["lost"]), (True, 0))
        boss = self.fight({"Hammer": entry(90.0)}, line(0.5, 'ENCOUNTER_START,1084,"Onyxia",9,40'))
        self.assertEqual(boss["kind"], "Boss")
        self.assertFalse(boss["cooldowns"][0].get("held"))
        self.assertGreater(boss["cooldowns"][0]["lost"], 0)

    def test_two_characters_two_books(self):
        with tempfile.TemporaryDirectory() as d, patch.dict("os.environ", {"APPDATA": d}):
            h = History(Paths(Path(d)))
            h.book("Player-1-A")["Judgement"] = entry(10.0)
            h.save_books()
            h2 = History(Paths(Path(d)))
            self.assertEqual(list(h2.book("Player-1-A")), ["Judgement"])
            self.assertEqual(h2.book("Player-1-B"), {})

    def test_remove_and_a_removed_fight_stays_out(self):
        """a deleted fight leaves the file, and a replay (or a combat carrying on) doesn't save it again"""
        self.addCleanup(removed.IDS.clear)
        with tempfile.TemporaryDirectory() as d, patch.dict("os.environ", {"APPDATA": d}):
            h = History(Paths(Path(d)))
            for i in ("1", "2", "3"):
                h.add({"id": i})
            h.remove({"2"})
            self.assertEqual([f["id"] for f in History(Paths(Path(d))).fights], ["1", "3"])
            removed.IDS.add("2")
            self.assertFalse(h.add({"id": "2"}))
            self.assertEqual([f["id"] for f in History(Paths(Path(d))).fights], ["1", "3"])


class Defensives(unittest.TestCase):
    def test_ready_and_unused_when_low(self):
        tr, f = one_fight([dmg(0, ME, MOB, 8092, "Mind Blast", 300), cast(15, 498, "Divine Protection"), *bites(30)])
        low = next(e for e in f.events if e.event == "SWING_DAMAGE" and (e.ts - f.start).total_seconds() == 20)
        low.info = UnitInfo("Player-1-A", 100, 1000, 0, 100, 100, 0.0, 0.0, 0, 0.0, 33)       # 10% health at 20 s
        f.cast_before["Lay on Hands"] = f.start - timedelta(seconds=60)
        book = {"Divine Shield": entry(300.0, avg=0),                   # never cast: ready
                "Divine Protection": entry(300.0, avg=0),               # cast 5 s before: used
                "Lay on Hands": {**entry(1.0, avg=0), "gaps": []},      # cooldown unknown (300 s), cast 80 s ago
                "Smite": entry(1.0)}                                    # not a defensive
        s = summarize(f, tr.me, tr.me_name, book, [])                   # Evasion: not in the book
        self.assertEqual(s["danger"]["unused"], ["Divine Shield"])
        self.assertIn("Dropped to 10% health with Divine Shield ready", s["improve"])
        self.assertFalse([x for x in s["improve"] if x.startswith("Dropped to 10% health (")])


class Verdict(unittest.TestCase):
    def test_died(self):
        tr, f = one_fight([dmg(0, ME, MOB, 8092, "Mind Blast", 300), *bites(10),
                           line(10.5, f"UNIT_DIED,{NONE},{ME},0")])
        s = summarize(f, tr.me, tr.me_name, {}, [])
        self.assertEqual(s["verdict"], "Killed by Wolf: Melee for 20.")

    def test_healing(self):
        tr, f = one_fight([dmg(0, ME, MOB, 8092, "Mind Blast", 30), *bites(10),
                           line(5, f"SPELL_HEAL,{ME},{ME},2050,\"Lesser Heal\",0x2,500,500,0,0,nil")])
        s = summarize(f, tr.me, tr.me_name, {}, [])
        self.assertEqual(s["verdict"], "Healed 500 with only 0% overhealing.")

    def test_biggest_cost(self):
        s = Cooldowns().fight({"Judgement": entry(10.0)})
        self.assertTrue(s["verdict"].startswith("Judgement sat ready"), s["verdict"])
        self.assertIn(", about ", s["verdict"])
        self.assertNotIn("≈", s["verdict"])

    def test_no_damage(self):
        tr, f = one_fight(bites(10))
        self.assertEqual(summarize(f, tr.me, tr.me_name, {}, [])["verdict"], "No damage done this fight.")

    def test_no_damage_judges_nothing(self):
        tr, f = one_fight(bites(10))
        book = {"Judgement": {"gaps": [8.0] * 3, "spam": False, "last": (f.start - timedelta(minutes=1)).isoformat(),
                              "avg": 150, "cast": False, "cost": 0, "game_cd": None}}
        learn_cooldowns(f, tr.me, book)
        s = summarize(f, tr.me, tr.me_name, book, [])
        self.assertEqual((s["cooldowns"], s["efficiency"], s["potential"]), ([], 1.0, 0))
        self.assertFalse(any("sat ready" in x or "≈" in x for x in s["improve"]))
        self.assertEqual(s["verdict"], "No damage done this fight.")

    def test_clean(self):
        busy = [x for t in (0, 2, 4) for x in (cast(t, 585, "Smite"), dmg(t + 0.1, ME, MOB, 585, "Smite", 100))]
        tr, f = one_fight([*busy, line(4.5, f"UNIT_DIED,{NONE},{MOB},0")])
        s = summarize(f, tr.me, tr.me_name, {}, [])
        self.assertEqual(s["verdict"], f"Clean fight: {s['efficiency']:.0%} of the damage that was possible.")


class Opener(unittest.TestCase):
    def opener(self, *names):
        casts = [cast(i, 100 + i, n) for i, n in enumerate(names)]
        tr, f = one_fight([*casts, *bites(10)])
        return summarize(f, tr.me, tr.me_name, {}, [])["opener"]

    def test_first_three_in_order(self):
        self.assertEqual(self.opener("Smite", "Mind Blast", "Shadow Word: Pain", "Renew"),
                         ["Smite", "Mind Blast", "Shadow Word: Pain"])

    def test_fewer_casts(self):
        self.assertEqual(self.opener("Smite", "Renew"), ["Smite", "Renew"])

    def test_no_casts(self):
        self.assertEqual(self.opener(), [])


if __name__ == "__main__":
    unittest.main()
