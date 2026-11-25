"""The live fight tracker and summaries, on a small made-up log."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score import removed, store  # noqa: E402
from dips_score.live.summary import cooldown, learn_cooldowns, summarize  # noqa: E402
from dips_score.config import Paths  # noqa: E402
from dips_score.live import history  # noqa: E402
from dips_score.live.history import History, replay  # noqa: E402
from dips_score.live.profile import _place  # noqa: E402
from dips_score.live.tracker import Tracker  # noqa: E402
from dips_score.sources.combatlog import UnitInfo  # noqa: E402

ME = 'Player-1-A,"Nikana-Diploidian-PvP-US",0x511,0x80000000'
MOB = 'Creature-0-1-1-1-100-1,"Wolf",0xa48,0x80000000'
MOB2 = 'Creature-0-1-1-1-100-2,"Wolf",0xa48,0x80000000'
NONE = '0000000000000000,nil,0x80000000,0x80000000'
PAL = 'Player-1-P,"Pal-Realm-US",0x512,0x80000000'


def line(sec: float, rest: str) -> str:
    m, s = divmod(sec, 60)
    return f"11/17/2026 12:{int(m):02d}:{s:06.3f}-8  {rest}"


def dmg(sec, src, dst, spell_id, name, amount):
    return line(sec, f"SPELL_DAMAGE,{src},{dst},{spell_id},\"{name}\",0x20,{amount},{amount},-1,32,0,0,0,nil,nil,nil")


def swing(sec, src, dst, amount, crit="nil", glancing="nil"):
    return line(sec, f"SWING_DAMAGE,{src},{dst},{amount},{amount},-1,1,0,0,0,{crit},{glancing},nil")


class Live(unittest.TestCase):
    def test_auto_attack_hit_table(self):
        log = [swing(0, ME, MOB, 100), swing(2, ME, MOB, 200, crit="1"), swing(4, ME, MOB, 70, glancing="1"),
               line(6, f"SWING_MISSED,{ME},{MOB},DODGE,nil"), line(8, f"SWING_MISSED,{ME},{MOB},MISS,nil"),
               line(9, f"SPELL_EXTRA_ATTACKS,{ME},{ME},15494,\"Fury of Forgewright\",0x1,1"),
               swing(9.1, ME, MOB, 100), swing(10, ME, MOB, 100),
               line(11, f"RANGE_DAMAGE,{ME},{MOB},75,\"Auto Shot\",0x1,50,50,-1,1,0,0,0,nil,nil,nil,ST"),
               line(12, f"RANGE_MISSED,{ME},{MOB},75,\"Auto Shot\",0x1,MISS,nil"),
               line(3, f"SWING_MISSED,{MOB},{ME},PARRY,nil"), swing(5, MOB, ME, 40),
               line(13, f"UNIT_DIED,{NONE},{MOB},0"), line(40, f"SPELL_AURA_APPLIED,{ME},{ME},588,\"Inner Fire\",0x2,BUFF")]
        tr = Tracker()
        s = summarize(tr.feed_lines(sorted(log))[0], tr.me, tr.me_name, {}, [])
        a = s["auto"]
        self.assertEqual(a["swings"], 7)            # the old count: hits and misses
        self.assertEqual((a["landed"], a["crits"], a["glancing"], a["misses"]), (5, 1, 1, {"dodge": 1, "miss": 1}))
        self.assertEqual(a["extra"], {"Fury of Forgewright": 1})
        self.assertEqual((s["ranged"]["landed"], s["ranged"]["misses"]), (1, {"miss": 1}))
        self.assertEqual((s["swings_taken"]["landed"], s["swings_taken"]["misses"]), (1, {"parry": 1}))

    def test_summary_saves_difficulty(self):
        mob = MOB.replace("-0-1-1-1-", "-0-1-409-1-")
        log = [line(0, 'ZONE_CHANGE,409,"Molten Core",9'),
               *[dmg(t, ME, mob, 8092, "Mind Blast", 300) for t in (1, 3, 5, 7)],
               line(8, f"UNIT_DIED,{NONE},{mob},0"), line(40, f"SPELL_AURA_APPLIED,{ME},{ME},588,\"Inner Fire\",0x2,BUFF")]
        tr = Tracker()
        s = summarize(tr.feed_lines(log)[0], tr.me, tr.me_name, {}, [])
        self.assertEqual((s["kind"], s["instance"], s["difficulty"]), ("Dungeon", 409, 9))

    def test_the_enemies_say_where(self):
        """the zone line has the map's number, the open world's too, and none is written on entering a dungeon whose cave has its name"""
        def where(zone, *maps, boss=False):
            mobs = [f'Creature-0-1-{m}-1-100-{i},"Wolf",0xa48,0x80000000' if m else f'Player-1-F{i},"Foe-Realm-US",0x548,0x80000000'
                    for i, m in enumerate(maps)]
            log = [line(0, f"ZONE_CHANGE,{zone}"), *([line(1.5, 'ENCOUNTER_START,2741,"Wolf",1,5,36')] if boss else []),
                   *[dmg(1 + i + n / 10, ME, m, 8092, "Mind Blast", 300) for i in range(5) for n, m in enumerate(mobs)],
                   *[line(8 + i, f"UNIT_DIED,{NONE},{m},0") for i, m in enumerate(mobs)],
                   *([line(14, 'ENCOUNTER_END,2741,"Wolf",1,5,1,9000')] if boss else []),
                   line(60, f"SPELL_AURA_APPLIED,{ME},{ME},588,\"Inner Fire\",0x2,BUFF")]
            tr = Tracker()
            s = summarize(tr.feed_lines(sorted(log))[0], tr.me, tr.me_name, {}, [])
            return s["kind"], s["instance"], s["difficulty"], _place(s)
        self.assertEqual(where('1,"Tanaris",0', 1), ("World", 0, 0, "World"))
        self.assertEqual(where('0,"Riverglades",0', "0"), ("World", 0, 0, "World"))
        self.assertEqual(where('0,"The Deadmines",0', 36), ("Dungeon", 36, 0, "Dungeon"))
        self.assertEqual(where('0,"The Deadmines",0', 36, boss=True), ("Boss", 36, 0, "Dungeon"))
        self.assertEqual(where('189,"Scarlet Monastery",1', "0"), ("World", 0, 0, "World"))         # just left it
        self.assertEqual(where('0,"Tirisfal Glades",0', "0", 189, 189), ("Dungeon", 189, 0, "Dungeon"))
        self.assertEqual(where('1,"The Barrens",0', None)[:2], ("PvP", 0))                          # players only: the zone line
        self.assertEqual(where('489,"Warsong Gulch",0', None)[:2], ("PvP", 489))

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
        self.assertEqual(s["power"], [])            # no block of yours in these lines: nothing to go by
        self.assertTrue({"own", "rest"} <= set(s["pull"]) and {"ilvl", "stats", "power"} <= set(s))

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


class Replay(unittest.TestCase):
    """a replay over saved fights, in a data folder of its own"""
    LOG = [x for at in (0, 60) for x in (
        *[dmg(at + t, ME, MOB, 8092, "Mind Blast", 300) for t in (1, 3, 5, 7)], line(at + 8, f"UNIT_DIED,{NONE},{MOB},0"))]

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = patch.dict("os.environ", {"APPDATA": tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.paths = Paths(Path(tmp.name) / "no game")
        self.log = Path(tmp.name) / "WoWCombatLog.txt"
        self.log.write_text("".join(f"{x}\n" for x in self.LOG), encoding="utf-8")

    def rewrite(self, fights):
        (self.paths.data_dir / "fights.jsonl").write_text("".join(json.dumps(f) + "\n" for f in fights), encoding="utf-8")

    def test_keeps_spec_and_gear_sorts_and_drops_the_analyses(self):
        self.assertEqual(replay(self.paths, [self.log]), (2, 0))
        first, second = History(self.paths).fights
        self.assertNotIn("spec", first)
        # as the live app saved it, the first one missing
        second = {**second, "spec": "Shadow", "gear": 31, "damage": -1}
        self.rewrite([second])
        store.save(self.paths.analysis_dir, "1763-Nikana", ("k",), 1)
        self.assertEqual(replay(self.paths, [self.log]), (1, 1))
        a, b = History(self.paths).fights
        self.assertEqual((a["id"], b["id"]), (first["id"], second["id"]))    # the older one was added last
        self.assertEqual((b["spec"], b["gear"], b["damage"]), ("Shadow", 31, 1200))
        self.assertNotIn("spec", a)
        self.assertEqual(list(self.paths.analysis_dir.iterdir()), [])

    def test_a_deleted_fight_is_not_counted(self):
        self.addCleanup(removed.IDS.clear)
        replay(self.paths, [self.log])
        first, second = History(self.paths).fights
        removed.IDS.add(first["id"])
        self.rewrite([second])
        self.assertEqual(replay(self.paths, [self.log]), (0, 1))
        self.assertEqual([f["id"] for f in History(self.paths).fights], [second["id"]])

    def test_no_logs_touch_nothing(self):
        store.save(self.paths.analysis_dir, "1763-Nikana", ("k",), 1)
        self.assertEqual(replay(self.paths, []), (0, 0))
        self.assertEqual(len(list(self.paths.analysis_dir.iterdir())), 1)

    def test_the_oldest_by_time_go_first(self):
        h = History(self.paths)
        with patch.object(history, "KEEP", 2):
            for day in ("02", "03", "01"):
                h.add({"id": day, "start": f"2026-11-{day}T12:00:00"})
        self.assertEqual([f["id"] for f in h.fights], ["02", "03"])
        self.assertEqual([f["id"] for f in History(self.paths).fights], ["02", "03"])

    def test_a_failed_rewrite_leaves_the_file(self):
        h = History(self.paths)
        h.add({"id": "1"})
        with patch("os.replace", side_effect=PermissionError), self.assertRaises(PermissionError):
            h.remove({"1"})
        self.assertEqual([f["id"] for f in History(self.paths).fights], ["1"])


def shot(sec, sid=75, name="Auto Shot", amount=100):
    return line(sec, f"RANGE_DAMAGE,{ME},{MOB},{sid},\"{name}\",0x1,{amount},{amount},-1,1,0,0,0,nil,nil,nil,ST")


class AutoAttack(unittest.TestCase):
    """swinging between abilities isn't idle, next-swing abilities fill their swing, lost and clipped shots"""
    def test_heroic_strike_fills_its_swing(self):
        base = [swing(t, ME, MOB, 100) for t in range(0, 31, 2) if t != 6]
        hs = [cast(6, 25286, "Heroic Strike"), dmg(6.01, ME, MOB, 25286, "Heroic Strike", 300)]
        for extra, lost in (([], 1), (hs, 0)):
            tr, f = one_fight(base + extra)
            self.assertEqual(summarize(f, tr.me, tr.me_name, {}, [])["auto"]["lost_other"], lost)

    def test_swinging_between_abilities_is_not_idle(self):
        tr, f = one_fight([*[swing(t, ME, MOB, 100) for t in range(0, 31, 2)],
                           *[x for t in (0, 20) for x in (cast(t, 1752, "Sinister Strike"),
                                                          dmg(t + 0.01, ME, MOB, 1752, "Sinister Strike", 200))]])
        book = {"Sinister Strike": {**entry(1.0, avg=200), "gaps": [], "spam": True}}
        idle = (s := summarize(f, tr.me, tr.me_name, book, []))["idle"]
        self.assertGreater(idle["with_resource"], 10)
        self.assertAlmostEqual(idle["swinging_free"], idle["with_resource"])
        self.assertAlmostEqual(idle["swinging"], idle["total"])
        self.assertGreater(idle["lost"], 0)          # still the ability damage you could have added
        said = next(x for x in s["improve"] if "while swinging" in x)
        self.assertTrue(said.startswith(f"No ability used for {idle['with_resource']:.1f} s while swinging with"))

    def test_hunter_lost_and_clipped_shots(self):
        times = [t for t in range(0, 31, 3) if t not in (12, 15, 21, 24)]    # 9-18 an Aimed Shot, 18-27 nothing
        tr, f = one_fight([*[shot(t) for t in times], *bites(),
                           line(12, f"SPELL_CAST_START,{ME},{MOB},20904,\"Aimed Shot\",0x1"),
                           cast(15, 20904, "Aimed Shot")])
        s = summarize(f, tr.me, tr.me_name, {}, [])
        r = s["ranged"]
        self.assertEqual((r["shots"], r["speed"], r["shots_lost"], r["clipped"]), (len(times), 3.0, 2, 2))
        self.assertEqual(r["damage_lost"], 200)
        self.assertAlmostEqual(s["potential"], s["damage"] + 200)
        self.assertIn("2 shots lost while not shooting ≈ 200 damage", s["improve"])

    def test_wand_shots_clipped_by_any_cast(self):
        times = [x * 1.5 for x in range(21) if x != 10]          # Smite (an instant here) at 15
        tr, f = one_fight([*[shot(t, 5019, "Shoot", 50) for t in times], cast(15, 585, "Smite"),
                           dmg(15.01, ME, MOB, 585, "Smite", 200), *bites()])
        r = summarize(f, tr.me, tr.me_name, {}, [])["ranged"]
        self.assertEqual((r["shots_lost"], r["clipped"]), (0, 1))

    def test_wand_cast_starts_are_not_hard_casts(self):
        times = [x * 1.5 for x in range(21) if x not in (10, 11)]     # 13.5 to 18: two shots lost
        log = [x for t in times for x in (line(t - 0.01, f"SPELL_CAST_START,{ME},{MOB},5019,\"Shoot\",0x1"),
                                          cast(t - 0.005, 5019, "Shoot"), shot(t, 5019, "Shoot", 50))]
        tr, f = one_fight([*log, *bites()])
        r = summarize(f, tr.me, tr.me_name, {}, [])["ranged"]
        self.assertEqual((r["shots_lost"], r["clipped"]), (2, 0))

    def test_wand_idle_gap_is_lost_once(self):
        times = [x * 1.5 for x in range(21) if not 2 < x < 13]       # no shot 3 to 19.5 s, no cast 1.5 to 21 s
        log = [*[shot(t, 5019, "Shoot", 50) for t in times], *bites(),
               *[x for t in (0, 21) for x in (cast(t, 585, "Smite"), dmg(t + 0.01, ME, MOB, 585, "Smite", 200))]]
        tr, f = one_fight(log)
        book = {"Smite": {**entry(1.0, avg=200), "gaps": [], "spam": True}}
        s = summarize(f, tr.me, tr.me_name, book, [])
        self.assertGreater(s["idle"]["lost"], 0)             # priced as idle
        self.assertEqual(s["ranged"]["shots_lost"], 0)        # not again as lost shots
        unpriced = summarize(f, tr.me, tr.me_name, {}, [])     # no filler: the gap isn't idle, the shots are lost
        self.assertGreater(unpriced["ranged"]["shots_lost"], 5)

    def test_caster_without_auto_is_unchanged(self):
        tr, f = one_fight([cast(0, 8092, "Mind Blast"), dmg(0.1, ME, MOB, 8092, "Mind Blast", 300), *bites(30)])
        s = summarize(f, tr.me, tr.me_name, {"Smite": {**entry(1.0, avg=100), "gaps": [], "spam": True}}, [])
        self.assertEqual((s["auto"], s["ranged"], s["idle"]["swinging"]), (None, None, 0))
        self.assertTrue(any(x.startswith(f"{s['idle']['with_resource']:.1f} s idle with") for x in s["improve"]))


class Defensives(unittest.TestCase):
    def test_ready_and_unused_when_low(self):
        tr, f = one_fight([dmg(0, ME, MOB, 8092, "Mind Blast", 300), cast(5, 498, "Divine Protection"), *bites(30)])
        low = next(e for e in f.events if e.event == "SWING_DAMAGE" and (e.ts - f.start).total_seconds() == 20)
        low.info = UnitInfo("Player-1-A", 100, 1000, 0, 100, 100, 0.0, 0.0, 0, 0.0, 33)       # 10% health at 20 s
        f.cast_before["Lay on Hands"] = f.start - timedelta(seconds=60)
        book = {"Divine Shield": entry(300.0, avg=0),                   # never cast: ready
                "Divine Protection": entry(300.0, avg=0),               # cast 15 s before: on cooldown
                "Lay on Hands": {**entry(1.0, avg=0), "gaps": []},      # cooldown unknown (300 s), cast 80 s ago
                "Smite": entry(1.0)}                                    # not a defensive
        s = summarize(f, tr.me, tr.me_name, book, [])                   # Evasion: not in the book
        self.assertEqual(s["danger"]["unused"], ["Divine Shield"])
        self.assertIn("Dropped to 10% health with Divine Shield ready", s["improve"])
        self.assertFalse([x for x in s["improve"] if x.startswith("Dropped to 10% health (")])


    def low_at(self, cast_lines, book, at=20, died=False, since=None):
        tr, f = one_fight(sorted([dmg(0, ME, MOB, 8092, "Mind Blast", 300), *cast_lines, *bites(30),
                                  *([line(30.5, f"UNIT_DIED,{NONE},{ME},0")] if died else [])]))
        e = next(e for e in f.events if e.event == "SWING_DAMAGE" and (e.ts - f.start).total_seconds() == at)
        e.info = UnitInfo("Player-1-A", 100, 1000, 0, 100, 100, 0.0, 0.0, 0, 0.0, 33)
        f.forbearance = since and f.start - timedelta(seconds=since)
        return summarize(f, tr.me, tr.me_name, {n: entry(300.0, avg=0) for n in book}, [])["danger"]

    def test_answered_just_after_the_low(self):
        d = self.low_at([cast(22, 642, "Divine Shield")], ["Divine Shield", "Lay on Hands"])
        self.assertEqual((d["answered"], d["unused"]), (True, []))          # the lowest reading is before the save
        d = self.low_at([cast(5, 642, "Divine Shield")], ["Divine Shield", "Lay on Hands"])
        self.assertEqual((d["answered"], d["unused"]), (False, ["Lay on Hands"]))      # 15 s before: not for this

    def test_forbearance_rules_out_the_shields(self):
        both = ["Divine Shield", "Lay on Hands"]
        self.assertEqual(self.low_at([], both, since=39)["unused"], ["Lay on Hands"])
        self.assertEqual(self.low_at([], both, since=41)["unused"], both)       # over 60 s: its removal was missed
        on = line(1, f"SPELL_AURA_APPLIED,{ME},{ME},25771,\"Forbearance\",0x2,DEBUFF")
        self.assertEqual(self.low_at([on], both)["unused"], ["Lay on Hands"])
        self.assertEqual(self.low_at([on], both, since=300)["unused"], ["Lay on Hands"])     # an old one doesn't hide it

    def test_the_tracker_knows_since_when(self):
        on = lambda t: line(t, f"SPELL_AURA_APPLIED,{ME},{ME},25771,\"Forbearance\",0x2,DEBUFF")  # noqa: E731
        _, f = one_fight([on(0), on(7), dmg(10, ME, MOB, 8092, "Mind Blast", 300), *bites()])
        self.assertEqual((f.start - f.forbearance).total_seconds(), 3)          # the first one's removal was missed
        _, f = one_fight([dmg(10, ME, MOB, 8092, "Mind Blast", 300), *bites()])
        self.assertIsNone(f.forbearance)

    def test_only_one_on_yourself_answers(self):
        foe = 'Player-1-X,"Foe-Realm-US",0x548,0x80000000'
        npc = 'Creature-0-1-1-1-200-1,"Guard",0xa18,0x80000000'
        for dst, answered in ((ME, True), (NONE, True), (MOB, True), (foe, True), (PAL, False), (npc, False)):
            d = self.low_at([cast(19.5, 6789, "Death Coil", dst=dst)], ["Lay on Hands"])
            self.assertEqual(d["answered"], answered, dst)

    def test_one_that_stops_your_attacks_only_when_you_died(self):
        self.assertEqual(self.low_at([], ["Blessing of Protection"])["unused"], [])
        self.assertEqual(self.low_at([], ["Blessing of Protection"], 30, True)["unused"], ["Blessing of Protection"])


class FeignDeath(unittest.TestCase):
    """logged as UNIT_DIED with its last field 1; without one, told apart by acting again within 20 s"""
    def s(self, *lines, who=ME, flag=",0"):
        lines = [*lines, dmg(0, ME, MOB, 8092, "Mind Blast", 300), dmg(1, PAL, MOB, 1, "Holy Strike", 10), *bites(30),
                 line(10.5, f"UNIT_DIED,{NONE},{who}{flag}")]
        tr, f = one_fight(sorted(lines))
        low = next(e for e in f.events if e.event == "SWING_DAMAGE" and (e.ts - f.start).total_seconds() == 8)
        low.info = UnitInfo("Player-1-A", 100, 1000, 0, 100, 100, 0.0, 0.0, 0, 0.0, 33)
        return summarize(f, tr.me, tr.me_name, {"Feign Death": entry(30.0, avg=0)}, [])

    def test_yours(self):
        acts = cast(13, 8092, "Mind Blast")
        real, feign = self.s(), self.s(flag=",1")
        self.assertEqual((real["result"], feign["result"]), ("you died", "they got away"))
        self.assertTrue(real["verdict"].startswith("Killed by Wolf"))
        self.assertFalse(feign["verdict"].startswith("Killed by"))
        self.assertEqual((real["danger"]["unused"], feign["danger"]["unused"]), (["Feign Death"], []))
        hearthed = self.s(acts)                                     # a real death, then released and acting soon
        self.assertEqual((hearthed["result"], hearthed["verdict"]), (real["result"], real["verdict"]))
        rez = line(12, f"SPELL_RESURRECT,{PAL},{ME},1,\"Redemption\",0x2")      # a log without the field
        self.assertEqual([self.s(*x, flag="")["result"] for x in ((), (acts,), (rez, acts))],
                         ["you died", "they got away", "you died"])

    def test_buffs_stay_on_through_a_feign(self):
        buff = line(0, f"SPELL_AURA_APPLIED,{ME},{ME},13165,\"Aspect of the Hawk\",0x2,BUFF")
        for flag, own in (("1", ["Aspect of the Hawk"]), ("0", [])):
            log = [buff, dmg(1, ME, MOB, 75, "Arcane Shot", 300), line(3, f"UNIT_DIED,{NONE},{ME},{flag}"),
                   line(4, f"UNIT_DIED,{NONE},{MOB},0"), dmg(40, ME, MOB2, 75, "Arcane Shot", 300)]
            _, f = one_fight(log)
            self.assertEqual((f.own_buffs_at_pull, f.buffs_at_pull), (own, own))

    def test_the_groups_and_a_foes(self):
        self.assertEqual([self.s(who=PAL, flag=x)["group"]["deaths"] for x in (",0", ",1")], [["Pal"], []])
        self.assertEqual([self.s(line(31, f"UNIT_DIED,{NONE},{MOB},0"), who=MOB, flag=x)["result"] for x in (",0", ",1")],
                         ["killed", "killed"])
        self.assertEqual(self.s(who=MOB, flag=",1")["result"], "they got away")


class Others(unittest.TestCase):
    """what went to others, and what others outside the group did"""
    OUT = 'Player-1-O,"Out-Realm-US",0x518,0x80000000'
    GUARD = 'Creature-0-1-1-1-200-1,"Guard",0xa18,0x80000000'

    def s(self, *lines):
        tr, f = one_fight(sorted([dmg(0, ME, MOB, 8092, "Mind Blast", 300), *bites(), *lines]))
        return summarize(f, tr.me, tr.me_name, {}, [])

    def test_helped_over_a_tenth(self):
        hit = lambda src, n: self.s(dmg(3, src, MOB, 1, "Shot", n))["helped"]  # noqa: E731
        self.assertEqual([hit(self.OUT, 30), hit(self.OUT, 31), hit(self.GUARD, 31)], [False, True, True])
        self.assertTrue(hit('Pet-0-1-1-1-1-1,"Wolfie",0x1118,0x80000000', 31))             # their pet
        self.assertFalse(hit(PAL, 999))                                                   # your group
        self.assertFalse(hit('Pet-0-1-1-1-1-1,"Mine",0x1111,0x80000000', 999))             # yours
        self.assertFalse(hit(MOB2, 999))                                                  # an enemy
        self.assertFalse(self.s()["helped"])

    def test_helped_by_heals_over_a_tenth_of_the_damage_taken(self):
        def got(src, n, over=0, dst=ME):                        # 300 damage taken
            return self.s(line(3, f"SPELL_HEAL,{src},{dst},2050,\"Heal\",0x2,{n},{n},{over},0,nil"))["helped"]
        self.assertEqual([got(self.OUT, 30), got(self.OUT, 31), got(self.OUT, 31, 1)], [False, True, False])
        self.assertTrue(got('Pet-0-1-1-1-1-1,"Wolfie",0x1118,0x80000000', 31))              # their pet
        self.assertEqual([got(x, 999) for x in (self.GUARD, PAL, ME, 'Pet-0-1-1-1-1-1,"Mine",0x1111,0x80000000')],
                         [False] * 4)                           # a friendly NPC, your group, you, your pet
        self.assertFalse(got(self.OUT, 999, dst=PAL))

    def test_healing_and_dispels_on_others(self):
        heal = lambda src, dst: line(3, f"SPELL_HEAL,{src},{dst},2050,\"Lesser Heal\",0x2,50,50,10,0,nil")  # noqa: E731
        free = lambda dst: line(3, f"SPELL_DISPEL,{ME},{dst},527,\"Cleanse\",0x2,118,\"Polymorph\",0x40,DEBUFF")  # noqa: E731
        s = self.s(heal(ME, ME), heal(ME, PAL), heal(ME, self.GUARD), heal(PAL, PAL), heal(PAL, ME),
                   free(ME), free(PAL), free(MOB))
        self.assertEqual((s["healing"], s["healing_others"]), (120, 80))
        self.assertEqual((s["dispels"], s["dispels_others"]), (3, 1))
        m, = s["group"]["members"]
        self.assertEqual((m["healing"], m["healing_others"]), (80, 40))

    def test_pets_summoned_before_the_fight_are_not_others(self):
        heal = lambda src, dst: line(3, f"SPELL_HEAL,{src},{dst},1,\"Demonic Energies\",0x2,50,50,10,0,nil")  # noqa: E731
        free = lambda dst: line(3, f"SPELL_DISPEL,{ME},{dst},527,\"Cleanse\",0x2,118,\"Polymorph\",0x40,DEBUFF")  # noqa: E731
        mine, theirs, totem = ('Pet-0-1-1-1-1-1,"Imp",0x1111,0x80000000', 'Pet-0-1-1-1-1-2,"Imp",0x1112,0x80000000',
                               'Creature-0-1-1-1-300-1,"Totem",0x2111,0x80000000')
        ward = 'Creature-0-1-1-1-300-2,"Ward",0x911,0x80000000'          # yours by its affiliation, no pet type
        s = self.s(*[heal(ME, x) for x in (mine, theirs, totem, ward)], *[free(x) for x in (mine, theirs, ward)],
                   heal(PAL, theirs), heal(PAL, mine), heal(PAL, ME))
        self.assertEqual((s["healing_others"], s["dispels_others"]), (0, 0))
        m, = s["group"]["members"]
        self.assertEqual((m["healing"], m["healing_others"]), (120, 40))
        # the helped rule goes by the source's group: a pet of yours or a member's from before the fight is no outsider
        self.assertEqual([self.s(dmg(3, x, MOB, 1, "Firebolt", 999))["helped"] for x in (mine, theirs, totem, ward)],
                         [False] * 4)
        self.assertTrue(self.s(dmg(3, theirs.replace("0x1112", "0x1118"), MOB, 1, "Firebolt", 999))["helped"])


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
