"""The player profile's figures and label, and its saved 15-day slices, from hand-made fight dicts."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score import removed  # noqa: E402
from dips_score.live import profile_history as ph  # noqa: E402
from dips_score.live import profile_runs  # noqa: E402
from dips_score.live.profile import label, profile  # noqa: E402
from dips_score.profile_view import build_profile, mine, run_row  # noqa: E402

T0 = datetime(2026, 11, 23, 12, 0, 0)
DAY = timedelta(days=1)


def fight(days_ago=1.0, me="A", **kw):
    start = T0 - days_ago * DAY
    f = {"me": me, "me_name": me, "start": start.isoformat(), "duration": 60, "kind": "World", "more": 0,
         "result": "killed", "healing_role": False, "lowest_hp": 50, "cooldowns": [],
         "abilities": [{"name": "Smite", "casts": 3, "damage": 300, "share": 1.0}]}
    f.update(kw)
    return f


def run(days_ago=1.0, **kw):
    r = {"start": T0 - days_ago * DAY, "role": "damage", "score": 85.0, "grade": "A", "presses": 100,
         "by_key": 90, "by_click": 10, "failed": 5, "casts": 95, "combat_time": 600, "move_interrupts": 4,
         "wasted_cast_time": 6.5}
    r.update(kw)
    return r


def figs(**kw):
    """minimal figures for label()"""
    base = {"roles": {"damage": 1.0, "healer": 0.0, "tank": 0.0}, "places": {"Dungeon": 0.0, "World": 1.0, "PvP": 0.0},
            "temperament": {"deaths_per_hour": 2, "median_pull": 2, "cooldowns_share": 0.8}, "hands": None}
    for k, v in kw.items():
        base[k] = {**base[k], **v} if isinstance(v, dict) and base.get(k) else v
    return base


class Windows(unittest.TestCase):
    def test_edges(self):
        p = profile([fight(30), fight(29.999), fight(15), fight(14.999), fight(0)], None, {}, [], T0)
        self.assertEqual(p["now"]["fights"], 2)          # (now - 15 days, now]: a fight at now counts
        self.assertEqual(p["before"]["fights"], 2)       # exactly 15 days back is Before; exactly 30 is out

    def test_before_none(self):
        p = profile([fight(1)], None, {}, [], T0)
        self.assertIsNone(p["before"])
        self.assertIsNone(p["now"]["hands"])

    def test_the_sheet_reaches_the_view(self):
        char = {"taken": 1795576160, "stats": {"str": 93}, "pulls": [("x", 80, 1), ("y", 60, 2)]}
        v = build_profile(profile([fight(1)], char, {}, [], T0), [])
        self.assertEqual((v.sheet.need, v.sheet.wear, v.sheet.gear), ("", "2 pieces broken at your last pull.", []))
        self.assertTrue(build_profile(profile([fight(1)], None, {}, [], T0), []).sheet.need)

    def test_newest_character_only(self):
        p = profile([fight(2, me="B"), fight(1, me="A")], None, {}, [], T0)
        self.assertEqual((p["name"], p["now"]["fights"]), ("A", 1))

    def test_no_fights(self):
        self.assertIsNone(profile([], None, {}, [], T0)["now"])


class Figures(unittest.TestCase):
    def test_role_from_healing_role_and_spec(self):
        char = {"class": "PALADIN"}
        fs = [fight(1, healing_role=True, duration=30), fight(1, spec="Protection", duration=60),
              fight(1, spec="Retribution", duration=10), fight(1, duration=0)]
        roles = profile(fs, char, {}, [], T0)["now"]["roles"]
        self.assertEqual(roles, {"healer": 0.3, "tank": 0.6, "damage": 0.1})

    def test_places_boss_is_dungeon(self):
        fs = [fight(1, kind="Boss"), fight(1, kind="Dungeon"), fight(1, kind="World"), fight(1, kind="PvP")]
        self.assertEqual(profile(fs, None, {}, [], T0)["now"]["places"],
                         {"Dungeon": 0.5, "Raid": 0.0, "World": 0.25, "PvP": 0.25})     # old fights: no difficulty, never Raid

    def test_places_by_difficulty(self):
        fs = [fight(1, kind="Dungeon", instance=33, difficulty=1), fight(1, kind="Boss", instance=409, difficulty=9),
              fight(1, kind="Boss", instance=0, difficulty=0), fight(1, kind="Dungeon", instance=1, difficulty=999),
              fight(1, kind="World", instance=0, difficulty=0), fight(1, kind="PvP", instance=30, difficulty=9),
              fight(1, kind="Dungeon", instance=0, difficulty=148), fight(1, kind="Boss")]
        self.assertEqual(profile(fs, None, {}, [], T0)["now"]["places"],
                         {"Dungeon": 3 / 8, "Raid": 2 / 8, "World": 2 / 8, "PvP": 1 / 8})
        raid = profile([fight(1, kind="Boss", instance=409, difficulty=9)], None, {}, [], T0)["now"]
        self.assertEqual(raid["label"], "Careful raid damage dealer.")

    def test_restricted_spells(self):
        char = {"spells": {"Exorcism": {"harm": True}, "Turn Undead": {"harm": True}, "Smite": {"harm": True}}}
        book = {"Smite": {"last": (T0 - DAY).isoformat()}}
        fs = [fight(2, foes=[["Ghoul", 3], ["Wolf", 1]]), fight(2, foes=[["Imp", 2]]), fight(2, foes=[["Wolf", 4]])]
        n = profile(fs, char, book, [], T0)["now"]
        self.assertEqual((n["unused"], n["restricted"]), ([], {}))                  # no creature types: left out
        n = profile(fs, char, book, [], T0, {"Wolf": "Beast"})["now"]
        self.assertEqual(n["unused"], [])                                           # none of them met
        n = profile(fs, char, book, [], T0, {"Ghoul": "Undead", "Imp": "Demon", "Wolf": "Beast"})["now"]
        self.assertEqual(n["unused"], ["Exorcism", "Turn Undead"])
        self.assertEqual(n["restricted"], {"Exorcism": {"chances": 5, "fights": 2},
                                           "Turn Undead": {"chances": 3, "fights": 1}})

    def test_restricted_with_plain_unused(self):
        char = {"spells": {"Exorcism": {"harm": True}, "Holy Wrath": {"harm": True}, "Turn Undead": {"harm": True},
                           "Consecration": {"harm": True}}}
        fs = [fight(2, foes=[["Imp", 2], ["Wolf", 1]]), fight(2, foes=[["Bandit", 3]])]
        n = profile(fs, char, {}, [], T0, {"Imp": "Demon", "Wolf": "Beast"})["now"]       # Bandit has no type
        self.assertEqual(n["unused"], ["Exorcism", "Holy Wrath", "Consecration"])           # no undead: Turn Undead out
        self.assertEqual(set(n["restricted"]), {"Exorcism", "Holy Wrath"})
        self.assertEqual(n["restricted"]["Exorcism"], {"chances": 2, "fights": 1})

    def test_losses_and_efficiency(self):
        cd = lambda n, lost, counted, **kw: {"name": n, "lost": lost, "counted": counted, "possible": 4, "missed": 2, **kw}  # noqa: E731
        fs = [fight(1, damage=800, potential=1000, cooldowns=[cd("Judge", 100, 2), cd("Conse", 40, 1)]),
              fight(1, damage=100, potential=200, cooldowns=[cd("Judge", 0, 0), cd("Conse", 60, 1), cd("Zeal", 0.4, 1)]),
              fight(1, damage=500, potential=500, healing_role=True, cooldowns=[cd("Judge", 900, 9)]),   # healing
              fight(1, damage=0, potential=0, cooldowns=[cd("Judge", 900, 9)]),                          # no damage done
              fight(1, damage=100),                                                                      # no potential
              fight(1, damage=100, potential=100, cooldowns=[{"name": "Judge", "lost": 5}, {"possible": 2}])]    # old rows
        n = profile(fs, None, {}, [], T0)["now"]
        self.assertEqual((n["damage"], n["judged"], n["efficiency"]), (1100, 3, 1000 / 1300))
        self.assertEqual([tuple(s.values()) for s in n["losses"]],
                         [("Judge", 105, 2, 2, None), ("Conse", 100, 2, 2, None)])
        json.dumps(n)
        tie = [cd("B", 50, 1), cd("A", 50, 1)]
        n = profile([fight(1, damage=100, cooldowns=tie)], None, {}, [], T0)["now"]
        self.assertEqual([s["name"] for s in n["losses"]], ["A", "B"])
        n = profile([fight(1, cooldowns=tie)], None, {}, [], T0)["now"]             # an old fight: no damage saved
        self.assertEqual((n["damage"], n["efficiency"], n["losses"]), (None, None, []))
        # lost and the damage it is a share of come from the same fights
        n = profile([fight(1, cooldowns=tie), fight(1, damage=100, cooldowns=tie)], None, {}, [], T0)["now"]
        self.assertEqual((n["damage"], n["losses"][0]["lost"]), (100, 50))
        heal = profile([fight(1, healing_role=True, damage=5, potential=5, cooldowns=[cd("Judge", 9, 1)])],
                       None, {}, [], T0)["now"]
        self.assertEqual((heal["damage"], heal["efficiency"], heal["losses"]), (None, None, []))

    def test_losses_of_a_conditional_spell(self):
        ex = lambda lost, **kw: {"name": "Exorcism", "lost": lost, "counted": 2, **kw}  # noqa: E731
        fs = [fight(1, damage=9, cooldowns=[c]) for c in (ex(100, chances=3), ex(0, chances=4),
                                                          ex(500), ex(500, chances=0))]     # unknown, or none: out
        s, = profile(fs, None, {}, [], T0)["now"]["losses"]
        self.assertEqual((s["lost"], s["fights"], s["chances"]), (100, 1, 3))

    def test_close_calls_and_overheal(self):
        fs = [fight(1, danger={"unused": ["B", "A"], "answered": False}), fight(1, danger={"unused": [], "answered": True}),
              fight(1, danger={"t": 1}), fight(1, danger={"unused": ["A"]}),      # an old one: not known if answered
             
              fight(1, danger=None), fight(1, healing_role=True, healing=60, overheal=40), fight(1, healing=9, overheal=9)]
        n = profile(fs, None, {}, [], T0)["now"]
        self.assertEqual(n["close_calls"], {"fights": 2, "unused": 1, "spell": "A", "count": 1})
        self.assertEqual(n["overheal"], {"fights": 1, "healing": 60, "overheal": 40})
        n = profile([fight(1, healing_role=True)], None, {}, [], T0)["now"]
        self.assertEqual((n["close_calls"], n["overheal"]),
                         ({"fights": 0, "unused": 0, "spell": None, "count": None}, None))

    def test_opener(self):
        o = ["A", "B", "C"]
        fs = [fight(1, opener=o), fight(1, opener=o), fight(1, opener=["X", "B", "C"]), fight(1, opener=["A"]),
              fight(1)]
        self.assertEqual(profile(fs, None, {}, [], T0)["now"]["opener"], {"casts": o, "count": 2, "of": 3})
        self.assertIsNone(profile([fight(1)], None, {}, [], T0)["now"]["opener"])

    def test_hands_grades_and_temperament(self):
        fs = [fight(1, result="you died", more=2, cooldowns=[{"possible": 4, "missed": 1}]), fight(1)]
        n = profile(fs, None, {}, [run(1), run(1, score=None), run(20)], T0)["now"]
        self.assertEqual(n["hands"]["runs"], 2)
        self.assertAlmostEqual(n["hands"]["click_share"], 0.1)
        self.assertAlmostEqual(n["hands"]["per_minute"], 10)
        self.assertAlmostEqual(n["hands"]["refused_share"], 0.05)
        self.assertEqual(n["grades"]["damage"], {"runs": 1, "score": 85.0, "grade": "A"})
        self.assertIsNone(n["grades"]["healer"])
        t = n["temperament"]
        self.assertEqual((t["deaths"], t["deaths_per_hour"], t["median_pull"], t["cooldowns_share"]), (1, 30, 2, 0.75))

    def test_click_share_ignores_unknown_source(self):
        n = profile([fight(1)], None, {}, [run(1, presses=1000, by_key=60, by_click=40)], T0)["now"]
        self.assertAlmostEqual(n["hands"]["click_share"], 0.4)        # 40 of 100 keyed or clicked, not of 1000
        self.assertNotIn(" who ", n["label"])                          # clicking is the plate's, not the label's
        none = profile([fight(1)], None, {}, [run(1, by_key=0, by_click=0)], T0)["now"]
        self.assertIsNone(none["hands"]["click_share"])
        self.assertFalse(" who " in none["label"])

    def test_no_seconds_no_main_role(self):
        self.assertIsNone(profile([fight(1, duration=0)], None, {}, [], T0)["now"]["main_role"])

    def test_healer_signature_by_casts(self):
        fs = [fight(1, healing_role=True, abilities=[{"name": "Heal", "casts": 9, "damage": 0},
                                                     {"name": "Smite", "casts": 1, "damage": 500}])]
        sig = profile(fs, None, {}, [], T0)["now"]["signature"]
        self.assertEqual((sig["basis"], sig["top"][0]["name"], sig["top"][0]["share"]), ("casts", "Heal", 0.9))

    def test_unused(self):
        char = {"spells": {"Consecration": {"harm": True}, "Smite": {"harm": True}, "Heal": {"harm": False}}}
        book = {"Smite": {"last": (T0 - DAY).isoformat()}}
        self.assertEqual(profile([fight(2)], char, book, [], T0)["now"]["unused"], ["Consecration"])

    def test_unused_health_and_reactive(self):
        char = {"spells": {"Hammer of Wrath": {"harm": True}, "Overpower": {"harm": True}}}
        self.assertEqual(profile([fight(2)], char, {}, [], T0)["now"]["unused"], [])     # chances unknown: left out
        fs = [fight(2, chances={"Hammer of Wrath": 0, "Overpower": 0})]
        self.assertEqual(profile(fs, char, {}, [], T0)["now"]["unused"], [])             # none: nothing to use
        fs += [fight(2, chances={"Hammer of Wrath": 3, "Overpower": 7})]
        n = profile(fs, char, {}, [], T0)["now"]
        self.assertEqual(n["unused"], ["Hammer of Wrath", "Overpower"])
        self.assertEqual(n["restricted"], {"Hammer of Wrath": {"chances": 3, "fights": 1},
                                           "Overpower": {"chances": 7, "fights": 1}})


class Label(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(label(figs()), "World damage dealer.")
        self.assertEqual(label(figs(temperament={"deaths_per_hour": 1, "median_pull": 2})), "Careful world damage dealer.")
        self.assertEqual(label(figs(temperament={"deaths_per_hour": 4, "median_pull": 3})), "Reckless world damage dealer.")
        self.assertEqual(label(figs(temperament={"cooldowns_share": 0.4})), "Hoarding world damage dealer.")
        self.assertEqual(label(figs(roles={"damage": 0.5, "healer": 0.5})), "World hybrid.")
        self.assertEqual(label(figs(places={"World": 0.4, "Dungeon": 0.3, "PvP": 0.3})), "Damage dealer.")
        self.assertEqual(label(figs(roles={"damage": 0, "healer": 1}, places={"World": 0, "Dungeon": 1},
                                    temperament={"deaths_per_hour": 0, "median_pull": 1}, hands={"click_share": 0.3})),
                         "Careful dungeon healer.")
        self.assertEqual(label(figs(hands={"click_share": 0.04})), "World damage dealer.")
        self.assertEqual(label(figs(hands={"click_share": 0.1})), "World damage dealer.")

    def test_from_profile(self):
        self.assertEqual(profile([fight(1)], None, {}, [], T0)["now"]["label"], "Careful world damage dealer.")


class History(unittest.TestCase):
    def fights(self, *blocks):
        """n fights per 15-day block counted back from T0 (block 0 is Now)"""
        return sorted((fight(15 * b + 1 + i * 0.1, helped=False) for b, n in enumerate(blocks) for i in range(n)),
                      key=lambda f: f["start"])

    def test_first_run_fill_in_and_floor(self):
        saved = {}
        added = ph.update(saved, self.fights(12, 10, 9, 11), None, {}, [], T0)
        self.assertEqual([s["fights"] for s in saved["A"]], [11, 10])        # oldest first; 9 is under the floor
        self.assertEqual(added, saved["A"])
        self.assertEqual(saved["A"][-1]["to"], (T0 - 15 * DAY).isoformat())  # Now is not saved
        self.assertIsInstance(saved["A"][0]["label"], str)

    def test_nothing_saved_under_floor(self):
        saved = {}
        ph.update(saved, self.fights(12, 9), None, {}, [], T0)
        self.assertEqual(saved, {})

    def test_slice_added_exactly_15_days_later_and_not_rewritten(self):
        fs = self.fights(12, 10)
        saved = {}
        ph.update(saved, fs, None, {}, [], T0)
        first = json.dumps(saved)
        # opened again the same day, the day after, or up to the last moment: still in Now, the file unchanged
        for later in (timedelta(0), timedelta(milliseconds=20), timedelta(hours=11), DAY, 15 * DAY - timedelta(seconds=1)):
            self.assertEqual(ph.update(saved, fs, None, {}, [], T0 + later), [])
        self.assertEqual(json.dumps(saved), first)
        fs2 = fs + [fight(-0.5 - i * 0.1) for i in range(3)]                  # fights after T0 stay out of the slice
        added = ph.update(saved, fs2, None, {}, [], T0 + 15 * DAY)
        self.assertEqual(len(added), 1)
        self.assertEqual((added[0]["fights"], added[0]["to"]), (12, T0.isoformat()))
        self.assertEqual(json.dumps({"A": saved["A"][:1]}), first)
        self.assertEqual(len(saved["A"]), 2)

    def test_fights_from_before_helped_save_nothing_until_replayed(self):
        old = self.fights(12, 10, 11)
        for f in old:
            del f["helped"]
            f |= {"difficulty": 0, "chances": {}}                             # as 0.16 and 0.17 saved them
        saved = {}
        self.assertEqual(ph.update(saved, old, None, {}, [], T0), [])
        self.assertEqual(saved, {})                                           # so the fill-in is tried again
        ph.update(saved, [{**f, "helped": False} for f in old], None, {}, [], T0)
        self.assertEqual([s["fights"] for s in saved["A"]], [11, 10])

    def test_a_mixed_block_is_skipped_and_later_ones_save(self):
        saved = {}
        fs = self.fights(12, 10)
        ph.update(saved, fs, None, {}, [], T0)
        del fs[-1]["helped"]                                                  # in the block that is Now at T0
        later = fs + [fight(-1 - i * 0.1, helped=False) for i in range(10)]
        self.assertEqual(ph.update(saved, later, None, {}, [], T0 + 15 * DAY), [])
        added = ph.update(saved, later, None, {}, [], T0 + 30 * DAY)
        self.assertEqual([s["to"] for s in added], [(T0 + 15 * DAY).isoformat()])
        fs[-1]["helped"] = False                                              # replayed too late: unsaved for good
        self.assertEqual(ph.update(saved, later, None, {}, [], T0 + 30 * DAY), [])
        self.assertEqual(len(saved["A"]), 2)

    def test_save_is_on_disk_before_it_replaces(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "profile_runs.json"
            ph.save(path, {"A": []})
            calls = mock.Mock()
            with mock.patch("os.fsync", calls.fsync), mock.patch("os.replace", calls.replace):
                ph.save(path, {"A": [1]})
            self.assertEqual([c[0] for c in calls.method_calls], ["fsync", "replace"])
            self.assertEqual(ph.load(path), {"A": []})

    def test_save_and_load(self):
        saved = {}
        ph.update(saved, self.fights(0, 10), None, {}, [], T0)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "profile_history.json"
            self.assertEqual(ph.load(path), {})
            ph.save(path, saved)
            self.assertEqual(ph.load(path), saved)
            self.assertEqual(list(Path(d).iterdir()), [path])

    def test_load_locked_or_broken(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("profile_history.json", "profile_runs.json"):
                path = Path(d) / name
                self.assertEqual(ph.load(path), {})                     # not there yet
                path.write_text('{"A": []}', encoding="utf-8")
                with mock.patch.object(Path, "read_text", side_effect=PermissionError):
                    self.assertIsNone(ph.load(path))
                self.assertEqual(ph.load(path), {"A": []})              # only locked: left where it is
                for broken in ('{"A": [', "[]"):
                    path.write_text(broken, encoding="utf-8")
                    self.assertIsNone(ph.load(path))
                    self.assertFalse(path.exists())
                    aside = list(Path(d).glob(f"{path.stem}.bad-*.json"))
                    self.assertEqual([p.read_text(encoding="utf-8") for p in aside], [broken])
                    aside[0].unlink()
                path.write_bytes(b"\xff\xfe{")                          # not UTF-8 either
                self.assertIsNone(ph.load(path))
                self.assertEqual(ph.load(path), {})                     # the next time starts a new one

    def test_run_rows_kept(self):
        rows = {"old": run(61, parts=["old"]), "r1": run(40, parts=["r1", "r1b"])}
        kept = json.loads(json.dumps(profile_runs.pack(rows, T0)))
        self.assertEqual(list(kept), ["r1"])                            # 60 days
        now = {"r1": run(40, parts=["r1", "r1b"], score=90.0), "r2": run(1, parts=["r2"])}
        merged = profile_runs.merge(kept, now)
        self.assertEqual({k: r["score"] for k, r in merged.items()}, {"r1": 90.0, "r2": 85.0})      # upserted
        self.assertEqual(merged["r1"]["start"], rows["r1"]["start"])
        # the add-on kept only the visit's second piece: already in the whole visit's row
        self.assertEqual(list(profile_runs.merge(kept, {"r1b": run(40, parts=["r1b"])})), ["r1"])
        # a score is kept over none (its combat log is gone)
        self.assertEqual(profile_runs.merge(kept, {"r1": run(40, parts=["r1"], score=None)})["r1"]["score"], 85.0)
        bare = profile_runs.pack({"r1": run(40, parts=["r1"], score=None)}, T0)
        self.assertEqual(profile_runs.merge(bare, {"r1": run(40, parts=["r1"], score=None, presses=7)})["r1"]["presses"], 7)
        with mock.patch.object(removed, "IDS", {"r1"}):
            self.assertEqual(profile_runs.merge(kept, {}), {})          # deleted


def many(n=10, days_ago=1.0, **kw):
    return [fight(days_ago, **kw) for _ in range(n)]


def page(fs, runs=(), char=None, book=None, earlier=()):
    return build_profile(profile(fs, char, book or {}, list(runs), T0), list(earlier))


def title_of(v):
    """the plate's title, None without a plate"""
    return v.plate and v.plate.title


def row(rows, name):
    return next(r for r in rows if r.name == name)


def slice_(to_days_ago, lab="Careful world damage dealer.", main=0.9, dph=2.0, cds=0.5):
    hi = T0 - to_days_ago * DAY
    return {"from": (hi - 15 * DAY).isoformat(), "to": hi.isoformat(), "fights": 12, "label": lab,
            "figures": {"main_role": "damage", "roles": {"damage": main},
                        "temperament": {"deaths_per_hour": dph, "cooldowns_share": cds}}}


class View(unittest.TestCase):
    def test_hero_chip(self):
        v = page(many(healing_role=True) + many(days_ago=20) + many(10, 20, healing_role=True))
        self.assertEqual((v.hero, v.chip, v.chip_ink), ("100", "+50 pts vs the 15 days before", "role-heal"))
        self.assertIsNone(page(many()).chip)

    def test_hero_meta_label(self):
        char = {"class": "PALADIN", "race": "Scourge", "level": 36, "spec": None}
        v = page(many(), char=char)
        self.assertEqual((v.hero, v.hero_unit, v.caption), ("100", "%", "of fight time dealing damage"))
        self.assertEqual(v.label, "Careful world damage dealer.")
        self.assertEqual((v.meta, v.crest.who), ("last 15 days · 10 fights", "Scourge Paladin, level 36"))
        self.assertEqual(page(many(9), char=char).meta, "level 36 Scourge Paladin · last 15 days · 9 fights")     # no crest
        self.assertEqual(page(many(), char=char | {"gear": {"1": 31}}).meta, "gear 31 · last 15 days · 10 fights")
        self.assertIsNone(v.need)

    def test_plate_order(self):
        """each fight does everything wrong; taking away the rule that applies shows the next one"""
        kw = dict(cooldowns=[{"name": "Judge", "lost": 10, "counted": 1, "possible": 10, "missed": 6}], damage=30,
                  potential=40, danger={"unused": ["Divine Shield"], "answered": False}, healing=50, overheal=50, spec="Holy")
        char = {"class": "PALADIN", "spells": {"Consecration": {"harm": True}}}
        runs = [run(1, presses=500, by_key=200, by_click=300, failed=200, casts=300)]
        fs = many(2, result="you died", **kw) + many(8, **kw)
        p = page(fs, runs, char).plate
        self.assertEqual((p.title, p.figure, p.button), ("You die in 20% of your fights", "2 deaths", "Open Habits"))
        title = lambda **more: page(many(10, **{**kw, **more}), runs, char).plate.title  # noqa: E731
        self.assertEqual(title(spec="Retribution"), "Judge sat ready")
        self.assertEqual(title(), "Divine Shield sat ready in 10 close calls")       # a healer's lost damage is not it
        kw["danger"] = None
        self.assertEqual(title(), "You know Consecration and have not cast it")
        char["spells"] = {}
        self.assertEqual(title(), "Much of your healing lands on full health")
        kw.update(overheal=10, potential=32)
        self.assertEqual(title(), "You leave your cooldowns unused")
        kw["cooldowns"] = []
        self.assertEqual(title(), "You click instead of pressing keys")
        runs[0].update(by_key=499, by_click=1)
        self.assertEqual(title(), "The game turns down your presses")
        runs[0].update(failed=100)
        self.assertEqual(title(), "Your healing lands")                                     # nothing to change
        self.assertEqual(title(spec="Retribution"), "Your last 15 days were clean")

    def test_plate_sat_ready(self):
        cd = lambda n, lost, counted, **kw: {"name": n, "lost": lost, "counted": counted, **kw}  # noqa: E731
        rows = [cd("Conse", 63.1, 130), cd("Judge", 50, 3), cd("Strike", 20, 2), cd("Fourth", 10, 1)]
        p = page(many(damage=1000, potential=1250, cooldowns=rows)).plate
        self.assertEqual((p.title, p.figure, p.caption), ("Conse sat ready", "about 631 damage",
                                                          "1,300 casts missed in 10 fights"))
        self.assertEqual(p.why, "Press it when it comes up: that is about 6% more damage over these 15 days.")
        self.assertEqual(p.next, [("Judge", "500 damage"), ("Strike", "200 damage")])
        one = lambda lost: page(many(9) + [fight(damage=1000, potential=1250, cooldowns=[cd("Conse", lost, 1)])]).plate  # noqa: E731
        p = one(10)                                                             # 1% of the damage
        self.assertEqual((p.caption, p.next), ("1 cast missed in 1 fight", []))
        self.assertIn("about 1% more damage", p.why)
        self.assertEqual([one(x) for x in (9.9, 5)], [None] * 2)             # 80% of possible damage: nothing to show
        p = page(many(damage=100, cooldowns=[{"name": "Conse", "lost": 4}])).plate      # old fights: no casts
        self.assertEqual((p.title, p.caption), ("Conse sat ready", "in 10 fights"))
        p = page(many(damage=100, potential=150, cooldowns=[cd("Exorcism", 5, 1, chances=2)])).plate
        self.assertEqual(p.caption, "10 casts missed in 20 chances, in 10 fights")
        self.assertEqual(p.why, "It works on undead and demons. Press it when it comes up: that is about 5% more damage over "
                                "these 15 days.")

    def test_plate_clean(self):
        cd = [{"name": "Conse", "lost": 10, "counted": 1}]
        p = page(many(damage=90, potential=100, cooldowns=cd)).plate                  # exactly 90%
        self.assertEqual((p.title, p.figure, p.caption), ("Your last 15 days were clean", "90% of possible damage",
                                                          "in 10 fights where you did damage"))
        self.assertEqual(p.tab, "Going well")
        title = lambda damage, n=10: title_of(page(many(n, damage=damage, potential=1000, cooldowns=cd) + many(10 - n)))  # noqa: E731
        self.assertEqual([title(894), title(896), title(899)], ["Conse sat ready"] + ["Your last 15 days were clean"] * 2)
        self.assertIsNone(page(many(9, damage=950, potential=1000, cooldowns=cd) + many(1)).plate)  # too few to call clean

    def test_plate_healer_with_one_solo_fight(self):
        solo = fight(damage=100, potential=150, cooldowns=[{"name": "Smite", "lost": 50, "counted": 5}])
        heal = many(9, healing_role=True, healing=50, overheal=50)
        self.assertEqual(page(heal + [solo]).plate.title, "Much of your healing lands on full health")
        self.assertEqual(page(many(9) + [solo]).plate.title, "Smite sat ready")

    def test_plate_close_calls(self):
        low, safe = {"unused": ["Shield"], "answered": False}, {"unused": [], "answered": True}
        p = page(many(5, danger=low) + many(3, danger=safe) + many(5)).plate
        self.assertEqual((p.title, p.figure, p.caption), ("Shield sat ready in 5 close calls", "5 of 5",
                                                          "close calls with a defensive ready, in your last 13 fights"))
        two = {"unused": ["Shield", "Wall"], "answered": False}
        p = page(many(3, danger={**low, "unused": ["Wall"]}) + many(4, danger=two) + many(2, danger=low) + many(3, danger=safe)).plate
        self.assertEqual((p.title, p.figure), ("Wall sat ready in 7 close calls", "7 of 9"))
        old = {"unused": ["Shield"]}                                    # summed up before "answered": not counted
        self.assertIsNone(page(many(4, danger=low) + many(6, danger=old)).plate)
        self.assertIsNone(page(many(4, danger=low) + many(6)).plate)

    def test_plate_overheal_is_a_healers(self):
        kw = dict(healing=60, overheal=40)
        p = page(many(healing_role=True, **kw)).plate
        self.assertEqual((p.tab, p.figure, p.caption), ("Worth changing", "40% overheal",
                                                        "400 of 1,000 healing, in 10 healing fights"))
        p = page(many(healing_role=True, healing=61, overheal=40)).plate
        self.assertEqual((p.tab, p.title, p.figure, p.caption), ("Going well", "Your healing lands", "40% overheal",
                                                                 "400 of 1,010 healing, in 10 healing fights"))
        self.assertIsNone(page(many(healing_role=True)).plate)                              # no overheal known
        self.assertIsNone(page(many(4, healing_role=True, **kw) + many(6)).plate)

    def test_plate_input_only_when_badly_wrong(self):
        def title(now, before=None, n=500):
            hands = lambda days, share, n: run(days, presses=n, by_key=n - round(n * share), by_click=round(n * share))  # noqa: E731
            runs = [hands(1, now, n)] + ([hands(20, *before)] if before else [])
            return title_of(page(many() + many(days_ago=20), runs))
        bad, none = "You click instead of pressing keys", None
        self.assertEqual([title(.6), title(.59), title(.6, n=499)], [bad, none, none])     # 500 of the known presses
        self.assertEqual([title(.7, (.7, 500)), title(.7, (.8, 500)), title(.7, (.69, 500))], [none, none, bad])
        self.assertEqual([title(.7, (.8, 499)), title(.7, (.5, 500))], [bad, bad])        # not shown in Before
        self.assertEqual(title(.7, (.696, 500)), none)                                    # the same displayed figure
        p = page(many(), [run(1, presses=100, failed=200, casts=300)]).plate                # 500 casts tried
        self.assertEqual((p.title, p.figure, p.caption), ("The game turns down your presses", "40% refused",
                                                          "200 of 500 casts tried, in 1 recorded run"))
        self.assertIsNone(page(many(), [run(1, presses=900, failed=200, casts=299)]).plate)

    def test_plate_without_the_new_figures(self):
        p = profile(many() + many(days_ago=20), None, {}, [run(1)], T0)
        for f in (p["now"], p["before"]):
            for k in ("damage", "efficiency", "judged", "losses", "close_calls", "overheal"):
                del f[k]
        self.assertIsNone(build_profile(p, [slice_(15)]).plate)

    def test_old_history_file_still_loads(self):
        """a profile_history.json saved by 0.16 or 0.17: kept as it is, shown, and added to"""
        fs = many(days_ago=50, helped=False) + many(days_ago=20, helped=False) + many(helped=False)
        old = {}
        ph.update(old, fs, None, {}, [], T0 - 20 * DAY)
        for f in (s["figures"] for s in old["A"]):
            for k in ("damage", "efficiency", "judged", "losses", "close_calls", "overheal"):
                del f[k]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile_history.json"
            path.write_text(json.dumps(old), encoding="utf-8")
            saved = ph.load(path)
        self.assertEqual(saved, old)
        self.assertTrue(old["A"])
        self.assertEqual(ph.update(saved, fs, None, {}, [], T0 + 20 * DAY) and saved["A"][:len(old["A"])], old["A"])
        v = build_profile(profile(fs, None, {}, [], T0), saved["A"])
        self.assertEqual(len(v.earlier), len(saved["A"]))

    def test_plate_why(self):
        char = {"spells": {"Consecration": {"harm": True}}}
        ab = [{"name": "Smite", "casts": 3, "damage": 300}, {"name": "Seal", "casts": 1, "damage": 0}]
        self.assertEqual(page(many(abilities=ab), char=char).plate.why,
                         "Smite and Seal carry your casts. Consecration is the harmful spell left on the bench.")
        self.assertEqual(page(many(cooldowns=[{"possible": 10, "missed": 6}])).plate.why,
                         "60 uses of a ready cooldown went unspent.")
        self.assertEqual(page(many(2, result="you died") + many(8)).plate.why,
                         "2 of your last 10 fights ended with you dead.")
        self.assertEqual(page(many(damage=95, potential=100)).plate.why, "")

    def test_nothing_stands_out(self):
        keys = [run(1, by_key=99, by_click=1)]
        self.assertIsNone(page(many(cooldowns=[{"possible": 10, "missed": 1}]), keys).plate)    # no figure, no plate
        self.assertIsNone(page(many(damage=80, potential=100), keys).plate)              # under 90%: no plate
        self.assertIsNone(page(many(damage=89, potential=100), keys).plate)
        p = page(many(damage=95, potential=100), keys).plate
        self.assertEqual((p.tab, p.title, p.figure), ("Going well", "Your last 15 days were clean", "95% of possible damage"))

    def test_chip_threshold_and_sign(self):
        def dungeon(now, before):       # of 100 fights
            mix = lambda n, **kw: many(n, kind="Dungeon", **kw) + many(100 - n, **kw)  # noqa: E731
            return row(page(mix(before, days_ago=20) + mix(now)).places, "Dungeon")
        c = dungeon(60, 55)
        self.assertEqual((c.chip, c.mark), ("+5 pts vs the 15 days before", "more dungeons"))
        self.assertIsNone(dungeon(60, 56).chip)
        self.assertEqual(dungeon(40, 52).chip, "−12 pts vs the 15 days before")

    def test_chip_from_displayed_figures(self):
        def chip(now, before):          # shares of the fight time
            mix = lambda s, **kw: many(5, kind="Dungeon", duration=s, **kw) + many(5, duration=1 - s, **kw)  # noqa: E731
            return row(page(mix(before, days_ago=20) + mix(now)).places, "Dungeon").chip
        self.assertEqual(chip(.546, .504), "+5 pts vs the 15 days before")      # 55 against 50: raw 4.2
        self.assertEqual(chip(.554, .496), "+5 pts vs the 15 days before")      # 55 against 50: raw 5.8
        self.assertIsNone(chip(.544, .496))                                     # 54 against 50: raw 4.8

    def test_role_and_place_marks(self):
        v = page(many(healing_role=True) + many(days_ago=20))
        # damage -100 and healer +100 tie: the increase
        self.assertEqual((row(v.roles, "Healer").mark, row(v.roles, "Damage").chip),
                         ("more healing", "−100 pts vs the 15 days before"))
        v = page(many() + many(days_ago=20, kind="Dungeon"))
        self.assertEqual(row(v.places, "World").mark, "more open world")

    def test_meta_level_without_char(self):
        self.assertEqual(page(many(9, level=30)).meta, "level 30 · last 15 days · 9 fights")
        self.assertEqual(page(many(level=30)).crest.who, "level 30")

    def test_highlighter_tie_break(self):
        # Dungeon 0 -> 50 and World 100 -> 50 both move 50 points; Dungeon grew
        v = page(many(5, kind="World") + many(5, kind="Dungeon") + many(days_ago=20, kind="World"))
        marks = [r for r in v.places if r.mark]
        self.assertEqual(len(marks), 1)
        self.assertEqual(v.places[0].name, "Dungeon")          # equal shares keep Dungeon, World, PvP order
        self.assertEqual((marks[0].name, marks[0].mark), ("Dungeon", "more dungeons"))
        self.assertEqual(row(v.places, "World").chip, "−50 pts vs the 15 days before")

    def test_no_before(self):
        v = page(many(kind="Dungeon"))
        self.assertFalse(any(r.chip or r.mark for r in v.card + v.hands + v.roles + v.places))
        self.assertIsNone(v.before)

    def test_before_line_only_when_titles_differ(self):
        self.assertIsNone(page(many() + many(days_ago=20)).before)
        v = page(many() + many(days_ago=20, kind="Dungeon"))
        self.assertEqual(v.before, "Before: Slayer of the Depths")

    def test_under_ten_keeps_earlier(self):
        v = page(many(6), earlier=[slice_(20)])
        self.assertEqual(v.need, "Your profile needs 10 fights from the last 15 days (6 so far).")
        self.assertTrue(v.meta.endswith("last 15 days · 6 fights"))
        self.assertEqual((len(v.earlier), v.earlier_title), (1, "Earlier (1)"))
        self.assertIsNone(v.plate)
        self.assertEqual(build_profile(profile([], None, {}, [], T0), []).need,
                         "Your profile needs 10 fights from the last 15 days (0 so far).")

    def test_run_rows(self):
        def a(guid="A", role="dps", combat=600.0, me=NS(role="DPS"), grade="B", total=72.0):
            run_ = NS(start_time=T0, id="r", parts=["r"], player_name="Bao")
            m = NS(combat_time=combat, presses=9, by_key=8, by_click=1, failed=2, casts=7, moving_time=1.5,
                   move_interrupts=1, wasted_cast_time=0.5)
            card = NS(empty=False, grade=grade, total=total, role=role, categories=[], points_lost=lambda: [])
            return NS(data=NS(run=run_, player_guid=guid, duration=900.0), metrics=m, card=card, summary=None,
                      deaths=[], wipes=[], me=me, role=role)
        r = run_row(a())
        self.assertEqual(r, {"me": "A", "parts": ["r"], "name": "Bao", "start": T0, "role": "damage",
                             "score": 72.0, "grade": "B", "presses": 9, "by_key": 8, "by_click": 1, "failed": 2, "casts": 7, "combat_time": 600.0,
                             "moving_time": 1.5, "move_interrupts": 1, "wasted_cast_time": 0.5})
        short, unknown = run_row(a(combat=20.0)), run_row(a(guid=None, role="healer", me=None))
        self.assertEqual((short["role"], short["score"]), (None, None))     # too short to compare: no grade
        self.assertIsNone(unknown["role"])                                  # no combat log: "healer" is only a default
        self.assertEqual(mine({"1": r, "2": unknown, "3": run_row(a("B")), "4": None}, "A", "Bao"),
                         {"1": r, "2": unknown})

    def test_hands_without_runs(self):
        v = page(many())
        self.assertEqual(v.hands, [])
        self.assertNotIn(" who ", v.label)

    def test_hands_with_runs(self):
        v = page(many(), [run(1)])
        k = row(v.hands, "Keys or clicks")
        self.assertEqual((k.value, k.unit, k.note), ("90", "% keys", "10 clicks in 100 presses, in 1 recorded run"))
        self.assertEqual([r.name for r in v.hands], ["Keys or clicks", "Presses per minute", "Refused presses"])
        self.assertEqual(row(v.hands, "Presses per minute").value, "10.0")
        self.assertEqual({r.ink for r in v.hands}, {"tx"})

    def test_hands_never_stand_out(self):
        """however far the input moved: no chip, no mark"""
        runs = [run(1, by_key=100, by_click=0, failed=0), run(20, by_key=10, by_click=90, failed=90)]
        v = page(many() + many(days_ago=20), runs)
        self.assertFalse(any(r.chip or r.mark for r in v.hands))

    def test_cut_short_is_play(self):
        """always in How you fight when it is known, after the five, with its chip"""
        fs = many(40, pull={"since_last": 60}, potential=400, damage=300, group=None, helped=False)
        for runs, n in (([], 5), ([run(1)], 6)):
            with self.subTest(n):
                self.assertEqual(len(page(fs, runs).card), n)
        v = page(many(days_ago=20) + many(), [run(1), run(20, move_interrupts=19)])
        c = row(v.card, "Cut short by moving")
        self.assertEqual((c.value, c.unit, c.note, c.chip),
                         ("4", "%", "4 of 95 casts, in recorded runs", "−16 pts vs the 15 days before"))
        self.assertEqual(sum(r.name == c.name for r in v.card), 1)

    def test_cut_short_unknown_without_move_keys(self):
        old = run(1)
        del old["move_interrupts"], old["wasted_cast_time"]
        h = profile(many(), None, {}, [old], T0)["now"]["hands"]
        self.assertEqual((h["move_runs"], h["move_interrupts"], h["wasted_cast_time"], h["cut_share"]),
                         (0, None, None, None))
        self.assertNotIn("Cut short by moving", [r.name for r in page(many(), [old]).card])
        both = profile(many(), None, {}, [run(1), run(1)], T0)["now"]["hands"]
        self.assertEqual((both["move_runs"], both["move_interrupts"], both["wasted_cast_time"]), (2, 8, 13.0))
        self.assertAlmostEqual(both["cut_share"], 8 / 190)
        # mixed: only the run carrying the keys counts, its casts the base
        mixed = profile(many(), None, {}, [run(1), old], T0)["now"]["hands"]
        self.assertEqual((mixed["move_runs"], mixed["move_casts"], mixed["move_interrupts"]), (1, 95, 4))
        self.assertAlmostEqual(mixed["cut_share"], 4 / 95)
        self.assertEqual(row(page(many(), [run(1), old]).card, "Cut short by moving").note, "4 of 95 casts, in recorded runs")
        zero = page(many(), [run(1, casts=0, move_interrupts=0, wasted_cast_time=0.0)])
        self.assertNotIn("Cut short by moving", [r.name for r in zero.card])

    def test_melee_leads_with_swings(self):
        ab = [{"name": "Melee", "casts": 0, "damage": 460}, {"name": "Seal of Command", "casts": 0, "damage": 140},
              {"name": "Smite", "casts": 3, "damage": 400}, {"name": "Seal", "casts": 1, "damage": 0}]
        fs = many(abilities=ab, auto={"swings": 20})
        sig = profile(fs, None, {}, [], T0)["now"]["signature"]
        self.assertAlmostEqual(sum(s["share"] for s in sig["spells"]), 1.0)
        self.assertEqual([s["name"] for s in sig["top"]], ["Melee", "Smite", "Seal of Command", "Seal"])
        v = page(fs)
        m = v.signature[0]
        self.assertEqual((m.name, m.value, m.casts, m.ink), ("Melee (auto attack)", "46", "200 swings", "m-dmg"))
        self.assertEqual(v.spells[0], ("Melee (auto attack)", "200 swings", "46.0%"))
        self.assertEqual(v.spells[-1], ("Seal", "10", "–"))
        # a fight without a swing count (one swing saves none) leaves the others' sum
        v = page(fs[:9] + many(1, abilities=ab))
        self.assertEqual(v.signature[0].casts, "180 swings")
        self.assertEqual(page(many(abilities=ab)).signature[0].casts, "–")     # no count anywhere: none shown
        self.assertEqual(row(v.signature, "Seal of Command").casts, "–")        # a proc isn't cast

    def test_roles_grade(self):
        v = page(many(), [run(1)])
        d, h = row(v.roles, "Damage"), row(v.roles, "Healer")
        self.assertEqual((d.grade, d.letter, d.note, d.ink), ("85", "A", "average of 1 graded run", "role-dmg"))
        self.assertEqual((h.grade, h.note, h.value), ("–", "no run graded as healer yet", "0"))

    def test_healer_signature(self):
        ab = [{"name": "Heal", "casts": 9, "damage": 0}, {"name": "Smite", "casts": 1, "damage": 500}]
        v = page(many(healing_role=True, abilities=ab))
        self.assertEqual((v.caption, v.sig_header, v.spells_header),
                         ("of fight time healing", "share of your casts", "share of casts"))
        self.assertEqual((v.signature[0].name, v.signature[0].value, v.signature[0].bar), ("Heal", "90", 0.9))
        self.assertEqual({r.ink for r in v.signature}, {"m-cast"})
        self.assertEqual(v.spells_title, "All spells (2)")

    def test_damage_signature_no_damage_row(self):
        ab = [{"name": "Smite", "casts": 3, "damage": 300}, {"name": "Seal", "casts": 1, "damage": 0}]
        v = page(many(abilities=ab, opener=["Seal", "Smite", "Smite"]))
        s = row(v.signature, "Seal")
        self.assertEqual((s.value, s.bar, s.note), ("–", None, "no damage of its own"))
        self.assertEqual(v.spells[1], ("Seal", "10", "–"))
        self.assertEqual((v.opener, v.opener_note),
                         ("Seal, Smite, Smite", "your usual opening: the first three casts in 10 of 10 fights"))

    def test_restricted_plate(self):
        char = {"spells": {"Exorcism": {"harm": True}}}
        types = {"Ghoul": "Undead", "Imp": "Demon"}
        fs = many(6, foes=[["Ghoul", 3], ["Imp", 1]]) + many(4)
        v = build_profile(profile(fs, char, {}, [], T0, types), [])
        self.assertEqual(v.plate.title, "You know Exorcism and have not cast it")
        self.assertEqual(v.plate.why, "Smite carries your casts. Exorcism works on undead and demons. "
                                      "You fought 24 of them in 6 fights and cast it 0 times.")
        self.assertIsNone(page(fs, char=char).plate)

    def test_reactive_and_health_plate(self):
        char = {"spells": {"Overpower": {"harm": True}, "Execute": {"harm": True}}}
        fs = many(3, chances={"Overpower": 4, "Execute": 2}) + many(7, chances={"Overpower": 0, "Execute": 0})
        self.assertEqual(build_profile(profile(fs, char, {}, [], T0), []).plate.why,
                         "Smite carries your casts. Overpower works after the target dodges you, in Battle Stance. "
                         "You had 12 dodges in 3 fights and cast it 0 times. Execute works on enemies under 20% health. You fought 6 "
                         "of them in 3 fights and cast it 0 times.")

    def test_inks(self):
        v = page(many(kind="Dungeon"), [run(1)])
        self.assertEqual([r.ink for r in v.roles], ["role-dmg", "role-heal", "role-tank"])
        self.assertEqual({r.name: r.ink for r in v.places},
                         {"Dungeon": "place-dungeon", "Raid": "place-raid", "World": "place-world", "PvP": "place-pvp"})

    def test_earlier_old_slice(self):
        old = {"from": (T0 - 30 * DAY).isoformat(), "to": (T0 - 15 * DAY).isoformat(), "fights": 12, "label": None,
               "figures": {"main_role": "healer", "temperament": {}}}
        e = page(many(), earlier=[old]).earlier[0]
        self.assertEqual((e.label, e.role, e.deaths, e.cooldowns), ("–", "–", "–", "–"))
        self.assertEqual(page(many(), earlier=[slice_(15)]).earlier[0].role, "Damage 90%")

    def test_earlier_newest_first(self):
        v = page(many(), earlier=[slice_(45, "Reckless world hybrid.", 0.55, 7.0, 0.61), slice_(15, dph=None)])
        self.assertEqual([e.dates for e in v.earlier], ["25 Oct to 8 Nov", "25 Sep to 9 Oct"])
        e = v.earlier[1]
        self.assertEqual((e.label, e.role, e.deaths, e.cooldowns), ("Reckless world hybrid", "Damage 55%", "7.0", "61%"))
        self.assertEqual(v.earlier[0].deaths, "–")

    def test_missing_values_dash(self):
        v = page(many(duration=0, more=None, lowest_hp=None))
        self.assertEqual((v.hero, v.hero_unit), ("–", ""))
        self.assertTrue(all(r.value == "–" for r in v.roles + v.places))
        self.assertEqual(v.opener, "–")


if __name__ == "__main__":
    unittest.main()
