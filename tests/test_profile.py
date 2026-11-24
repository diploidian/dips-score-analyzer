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
        return sorted((fight(15 * b + 1 + i * 0.1) for b, n in enumerate(blocks) for i in range(n)),
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
        with mock.patch.object(removed, "IDS", {"r1"}):
            self.assertEqual(profile_runs.merge(kept, {}), {})          # deleted


def many(n=10, days_ago=1.0, **kw):
    return [fight(days_ago, **kw) for _ in range(n)]


def page(fs, runs=(), char=None, book=None, earlier=()):
    return build_profile(profile(fs, char, book or {}, list(runs), T0), list(earlier))


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
        self.assertEqual(v.meta, "level 36 Scourge Paladin · last 15 days · 10 fights")
        self.assertIsNone(v.need)

    def test_plate_order(self):
        clicky = [run(1, by_key=60, by_click=40)]
        cd = [{"possible": 10, "missed": 6}]
        char = {"spells": {"Consecration": {"harm": True}}}
        deadly = many(2, result="you died", cooldowns=cd) + many(8, cooldowns=cd)
        self.assertEqual(page(deadly, clicky, char).plate.title, "You click instead of pressing keys")
        self.assertEqual(page(deadly, char=char).plate.title, "You leave your cooldowns unused")
        self.assertEqual(page(many(2, result="you died") + many(8), char=char).plate.title,
                         "You know Consecration and have never cast it")
        p = page(many(2, result="you died") + many(8)).plate
        self.assertEqual((p.title, p.figure, p.button), ("You die in 20% of your fights", "2 deaths", "Open Habits"))

    def test_plate_why(self):
        char = {"spells": {"Consecration": {"harm": True}}}
        ab = [{"name": "Smite", "casts": 3, "damage": 300}, {"name": "Seal", "casts": 1, "damage": 0}]
        self.assertEqual(page(many(abilities=ab), char=char).plate.why,
                         "Smite and Seal carry your casts. Consecration is the harmful spell left on the bench.")
        self.assertEqual(page(many(cooldowns=[{"possible": 10, "missed": 6}])).plate.why,
                         "60 uses of a ready cooldown went unspent.")
        self.assertEqual(page(many(2, result="you died") + many(8)).plate.why,
                         "2 of your last 10 fights ended with you dead.")
        self.assertEqual(page(many(), [run(1, by_key=60, by_click=40)]).plate.why, "")     # nothing real to add
        self.assertEqual(page(many()).plate.why, "")

    def test_nothing_stands_out_strongest(self):
        # margins: keys 0.30 - 0.01 = 0.29, cooldowns 0.90 - 0.50 = 0.40, deaths 0.15 - 0 = 0.15
        p = page(many(cooldowns=[{"possible": 10, "missed": 1}]), [run(1, by_key=99, by_click=1)]).plate
        self.assertEqual((p.title, p.figure), ("Nothing stands out", "90% cooldowns used"))
        self.assertEqual(page(many()).plate.figure, "0 deaths")

    def test_chip_threshold_and_sign(self):
        cd = lambda used: [{"possible": 100, "missed": 100 - used}]  # noqa: E731
        v = page(many(cooldowns=cd(60)) + many(days_ago=20, cooldowns=cd(55)))
        c = row(v.temperament, "Cooldowns used")
        self.assertEqual((c.chip, c.mark), ("+5 pts vs the 15 days before", "more cooldowns"))
        v = page(many(cooldowns=cd(60)) + many(days_ago=20, cooldowns=cd(56)))
        self.assertIsNone(row(v.temperament, "Cooldowns used").chip)
        v = page(many(cooldowns=cd(40)) + many(days_ago=20, cooldowns=cd(52)))
        self.assertEqual(row(v.temperament, "Cooldowns used").chip, "−12 pts vs the 15 days before")
        self.assertIsNone(row(v.temperament, "Deaths per hour").chip)      # per-hour figures get no chip

    def test_chip_from_displayed_figures(self):
        cd = lambda used: [{"possible": 1000, "missed": 1000 - used}]  # noqa: E731
        v = page(many(cooldowns=cd(546)) + many(days_ago=20, cooldowns=cd(504)))      # 55 against 50: raw 4.2
        self.assertEqual(row(v.temperament, "Cooldowns used").chip, "+5 pts vs the 15 days before")
        v = page(many(cooldowns=cd(554)) + many(days_ago=20, cooldowns=cd(496)))      # 55 against 50: raw 5.8
        self.assertEqual(row(v.temperament, "Cooldowns used").chip, "+5 pts vs the 15 days before")
        v = page(many(cooldowns=cd(544)) + many(days_ago=20, cooldowns=cd(496)))      # 54 against 50: raw 4.8
        self.assertIsNone(row(v.temperament, "Cooldowns used").chip)

    def test_role_and_place_marks(self):
        v = page(many(healing_role=True) + many(days_ago=20))
        # damage -100 and healer +100 tie: the increase
        self.assertEqual((row(v.roles, "Healer").mark, row(v.roles, "Damage").chip),
                         ("more healing", "−100 pts vs the 15 days before"))
        v = page(many() + many(days_ago=20, kind="Dungeon"))
        self.assertEqual(row(v.places, "World").mark, "more open world")

    def test_meta_level_without_char(self):
        self.assertEqual(page(many(level=30)).meta, "level 30 · last 15 days · 10 fights")

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
        self.assertFalse(any(r.chip or r.mark for r in v.hands + v.roles + v.places + v.temperament))
        self.assertIsNone(v.before)

    def test_before_line_only_when_labels_differ(self):
        self.assertIsNone(page(many() + many(days_ago=20)).before)
        v = page(many() + many(days_ago=20, kind="Dungeon"))
        self.assertEqual(v.before, "Before: careful dungeon damage dealer.")

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
        self.assertEqual(len(v.hands), 1)
        self.assertEqual((v.hands[0].value, v.hands[0].note),
                         ("–", "Hands needs a recorded run: play with the dips-Score add-on on, then reload."))
        self.assertNotIn(" who ", v.label)

    def test_hands_with_runs(self):
        v = page(many(), [run(1)])
        k = row(v.hands, "Keys or clicks")
        self.assertEqual((k.value, k.unit, k.note), ("90", "% keys", "10 clicks in 100 presses, in 1 recorded run"))
        self.assertEqual((row(v.hands, "Refused presses").ink, row(v.hands, "Presses per minute").value),
                         ("m-cast", "10.0"))
        c = row(v.hands, "Cut short by moving")
        self.assertEqual((c.value, c.unit, c.ink), ("4", "%", "m-cast"))
        self.assertEqual(c.note, "4 of 95 casts cut because you started to move, 6.5 s of cast time lost, in 1 recorded run")
        self.assertEqual((row(v.hands, "Presses per minute").ink, row(v.temperament, "Average lowest health").ink),
                         ("m-act", "m-surv"))

    def test_cut_short_unknown_without_move_keys(self):
        old = run(1)
        del old["move_interrupts"], old["wasted_cast_time"]
        h = profile(many(), None, {}, [old], T0)["now"]["hands"]
        self.assertEqual((h["move_runs"], h["move_interrupts"], h["wasted_cast_time"], h["cut_share"]),
                         (0, None, None, None))
        c = row(page(many(), [old]).hands, "Cut short by moving")
        self.assertEqual((c.value, c.note), ("–", "no cut casts saved in these runs"))
        both = profile(many(), None, {}, [run(1), run(1)], T0)["now"]["hands"]
        self.assertEqual((both["move_runs"], both["move_interrupts"], both["wasted_cast_time"]), (2, 8, 13.0))
        self.assertAlmostEqual(both["cut_share"], 8 / 190)
        # mixed: only the run carrying the keys counts, its casts the base
        mixed = profile(many(), None, {}, [run(1), old], T0)["now"]["hands"]
        self.assertEqual((mixed["move_runs"], mixed["move_casts"], mixed["move_interrupts"]), (1, 95, 4))
        self.assertAlmostEqual(mixed["cut_share"], 4 / 95)
        c = row(page(many(), [run(1), old]).hands, "Cut short by moving")
        self.assertEqual(c.note, "4 of 95 casts cut because you started to move, 6.5 s of cast time lost, in 1 recorded run")
        zero = row(page(many(), [run(1, casts=0, move_interrupts=0, wasted_cast_time=0.0)]).hands, "Cut short by moving")
        self.assertEqual((zero.value, zero.note),
                         ("–", "0 of 0 casts cut because you started to move, 0.0 s of cast time lost, in 1 recorded run"))

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
        self.assertEqual(v.plate.title, "You know Exorcism and have never cast it")
        self.assertEqual(v.plate.why, "Smite carries your casts. Exorcism works on undead and demons. "
                                      "You fought 24 of them in 6 fights and cast it 0 times.")
        self.assertNotEqual(page(fs, char=char).plate.title, "You know Exorcism and have never cast it")

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
        self.assertEqual([r.ink for r in v.temperament], ["m-surv", "tx", "m-surv", "m-cd"])

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
        self.assertEqual([r.value for r in v.temperament], ["–", "–", "–", "–"])
        self.assertTrue(all(r.value == "–" for r in v.roles + v.places))
        self.assertEqual(v.opener, "–")


if __name__ == "__main__":
    unittest.main()
