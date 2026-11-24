"""How a character plays: the traits' figures, scores and tiers, the title, the deeds and How you fight, from hand-made
fight dicts."""
import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.live import profile_history as ph  # noqa: E402
from dips_score.live import titles, traits  # noqa: E402
from dips_score.live.profile import profile  # noqa: E402
from dips_score.live.traits import BY_KEY, NAMED, TRAITS, pick, raw, score_of, scores  # noqa: E402
from dips_score.profile_view import OUTDATED, build_profile  # noqa: E402

T0 = datetime(2026, 11, 23, 12, 0, 0)
DAY = timedelta(days=1)
FIG = {"main_role": "damage", "roles": {"damage": 1.0}, "places": {}}


def fight(i=0, **kw):
    """one a minute, the newest first: 30 s long, won alone against one Ghoul"""
    start = T0 - DAY - timedelta(minutes=i)
    f = {"me": "A", "me_name": "A", "start": start.isoformat(), "end": (start + timedelta(seconds=30)).isoformat(),
         "duration": 30, "kind": "World", "more": 0, "result": "killed", "healing_role": False, "lowest_hp": 0.6,
         "cooldowns": [], "group": None, "foes": [["Ghoul", 1]], "target": "Ghoul", "zone": "", "damage": 300,
         "difficulty": 0, "chances": {}, "helped": False, "healing_others": 0, "dispels_others": 0, "abilities": [{"name": "Smite", "casts": 3, "hits": 3, "crits": 0, "damage": 300}]}
    return f | kw


def many(n=30, **kw):
    return [fight(n - i, **kw) for i in range(n)]


def plain(n=40, **kw):
    """nothing stands out: a third got away, half with a group, six ways of doing damage, 20 enemies"""
    ab = [{"name": "Melee", "casts": 0, "damage": 30}] + [{"name": c, "casts": 1, "damage": 14} for c in "VWXYZ"]
    return [f | {"result": "they got away" if i % 3 == 0 else "killed", "group": grouped(damage_rank=2) if i % 2 else None,
                 "foes": [[f"Ghoul {i % 20}", 1]], "abilities": ab} | kw for i, f in enumerate(many(n))]


def grouped(**kw):
    return {"size": 5, "damage_rank": 1, "deaths": [], "members": [{"name": "B", "damage": 1, "healing": 100,
                                                                         "healing_others": 90}]} | kw


def known(**tiers):
    """scores() with these traits at these tiers, at the tier's first score"""
    return {t.key: {"score": (0, *traits.TIERS)[tiers[t.key]], "tier": tiers[t.key]} if t.key in tiers else None
            for t in TRAITS}


def figure(key, win, fig=None, book=None, part=0):
    return raw(win, FIG | (fig or {}), book)[key][part]


class Anchors(unittest.TestCase):
    def test_every_edge(self):
        for t in TRAITS:
            for p in t.parts:
                with self.subTest(t.key):
                    one = traits.Trait(t.key, t.family, t.name, (p,), t.epithets, t.words)
                    at = lambda s: p.low + s * (p.high - p.low)  # noqa: E731,B023
                    of = lambda s, n=p.minimum: score_of(one, [(at(s), n)])  # noqa: E731,B023
                    self.assertEqual([(of(s)["score"], of(s)["tier"]) for s in (-1, 0, .349, .35, .599, .6, .849, .85, 1, 2)],
                                     [(0, 0), (0, 0), (.349, 0), (.35, 1), (.599, 1), (.6, 2), (.849, 2), (.85, 3),
                                      (1, 3), (1, 3)])
                    self.assertIsNone(of(1, p.minimum - 1))
                    self.assertIsNone(score_of(one, [(None, 10**6)]))
                    self.assertIsNone(of(.85)["next"])
                    self.assertEqual((of(.35)["next"]["epithet"], of(0)["next"]["epithet"]), t.epithets[1::-1])
                    (kind, need), = of(.35)["next"]["needs"]
                    self.assertAlmostEqual((kind, need)[1], at(.6))

    def test_two_parts(self):
        guard, mercy = BY_KEY["Guard"], BY_KEY["Mercy"]
        g = score_of(guard, [(0, 30), (.50, 30)])
        self.assertEqual((g["score"], g["kind"], g["figure"], len(g["next"]["needs"])), (0, "%", .50, 1))   # the weaker
        self.assertEqual(len(score_of(guard, [(8, 30), (.50, 30)])["next"]["needs"]), 2)    # both short of it
        self.assertIsNone(score_of(guard, [(0, 30), (None, 0)]))                            # both must be known
        m = score_of(mercy, [(0, 30), (.35, 20)])
        self.assertEqual((m["score"], m["figure"]), (1, .35))                               # the better
        self.assertEqual(score_of(mercy, [(25, 30), (None, 0)])["score"], 1)                # one is enough

    def test_the_needed_figure_reaches_it(self):
        s = score_of(BY_KEY["Tempo"], [(36.07, 446)])
        self.assertEqual(traits.needs(s["next"], BY_KEY["Tempo"]), [("30", "s")])           # 30.75 s, falling
        s = score_of(BY_KEY["Streak"], [(97, 446)])
        self.assertEqual(traits.needs(s["next"], BY_KEY["Streak"]), [("126", "")])
        s = score_of(BY_KEY["Streak"], [(130, 446)])
        self.assertEqual(traits.needs(s["next"], BY_KEY["Streak"]), [("173", "")])          # 172.25, rising
        self.assertEqual([score_of(BY_KEY["Streak"], [(n, 446)])["score"] for n in (15, 200)], [0, 1])
        s = score_of(BY_KEY["Edge"], [(.10, 446)])
        self.assertEqual(traits.needs(s["next"], BY_KEY["Edge"]), [("12", "%")])

    def test_table(self):
        self.assertEqual(len({e for t in TRAITS for e in t.epithets}), 3 * len(TRAITS))     # no epithet twice
        self.assertEqual({t.key for t in TRAITS}, set(raw([], {})))
        self.assertEqual([t.key for t in TRAITS if t.roles in (("healer",), ("tank",))], [t.key for t in TRAITS[:3]])
        self.assertLessEqual({k for a, b, _ in NAMED for k in (a, b)}, set(BY_KEY))


class Figures(unittest.TestCase):
    def test_pace(self):
        pull = lambda g: {"since_last": g}  # noqa: E731
        win = [fight(3, pull=pull(10)), fight(2, pull=pull(20)), fight(1, pull=pull(1800)), fight(0, pull=pull(None))]
        self.assertEqual(figure("Tempo", win), (15, 2))                 # a break of half an hour is no gap
        win = [fight(0, duration=14.9), fight(0, duration=15), fight(0, duration=5, result="you died")]
        self.assertEqual(figure("Swift", win), (.5, 2))
        self.assertEqual(figure("Endure", win), (14.9, 3))
        # 30 s long and started 30 min 29 s apart: 29 min 59 s between them; one more second is another sitting
        a = [fight(0, start=(T0 - timedelta(seconds=s)).isoformat(), end=(T0 - timedelta(seconds=s - 30)).isoformat())
             for s in (1829, 0)]
        b = [fight(0, start=(T0 - timedelta(seconds=s)).isoformat(), end=(T0 - timedelta(seconds=s - 30)).isoformat())
             for s in (1830, 0)]
        self.assertEqual((traits.sittings(a), traits.sittings(b)), ([2], [1, 1]))
        self.assertEqual(traits.sittings([{k: v for k, v in f.items() if k != "end"} for f in b]), [1, 1])
        res = [fight(0, result=r) for r in ("killed", "they got away", "killed", "you died", "killed")]
        self.assertEqual(figure("Streak", res), (3, 5))

    def test_nerve(self):
        win = [fight(0, lowest_hp=v) for v in (.349, .35, .099, .10)] + [
            fight(0, lowest_hp=.05, result="you died"), fight(0, lowest_hp=None)]
        self.assertEqual(figure("Edge", win), (.75, 4))                 # wins with a health reading only
        self.assertEqual(figure("Brink", win), (1, 4))
        self.assertEqual(figure("Guard", win), (100 / 6, 6))
        d = lambda **kw: fight(0, danger=kw)  # noqa: E731
        win = [d(answered=True, unused=[]), d(answered=False, unused=["X"]), d(answered=False, unused=[]),
               d(unused=["X"]), fight(0, danger=None)]
        self.assertEqual(figure("Wary", win), (.5, 2))                  # nothing to press, or not known: not asked
        three, two = [["A", 2], ["B", 1]], [["A", 2]]
        win = [fight(0, foes=three), fight(0, foes=two), fight(0, foes=three, group=grouped()), fight(0, foes=[])]
        self.assertEqual(figure("Crowd", win), (.5, 2))                 # a group's enemies are not yours alone
        self.assertEqual(figure("Crowd", win, {"main_role": "tank"}), (2 / 3, 3))
        self.assertEqual(figure("Crowd", win + [fight(0, foes=three, helped=True)]), (.5, 2))
        win = [fight(0), fight(0, result="you died"), fight(0, group=grouped()), fight(0, foes=two), fight(0, helped=True)]
        self.assertEqual(figure("Duel", win), (.5, 2))
        self.assertEqual(figure("Duel", [{k: v for k, v in fight().items() if k != "group"}]), (None, 0))
        self.assertEqual(figure("Duel", [{k: v for k, v in fight().items() if k != "helped"}]), (1, 1))     # by the group

    def test_victory(self):
        away = fight(0, result="they got away")
        win = [fight(0), away, away | {"damage": 0}, fight(0, result="you died"), away | {"damage": 0, "group": grouped()}]
        self.assertEqual(figure("Finish", win), (.2, 5))
        self.assertEqual(figure("Hound", win), (1 / 3, 3))              # not one you ran past, nor one you died in
        win = [fight(0, kind="Boss"), fight(0, kind="Boss", result="you died"), fight(0, kind="PvP", foes=[["Bob", 9]]),
               fight(0, kind="PvP", result="they got away"), fight(0, foes=[["Ghoul", 2], ["Imp", 1]])]
        self.assertEqual((figure("Boss", win), figure("War", win)), ((1, 5), (.5, 2)))
        self.assertEqual(figure("Scourge", win), (3 / 4, 4))            # players are no kind of enemy
        self.assertEqual(figure("Menagerie", win), (2, 5))

    def test_weapon(self):
        ab = [{"name": "Melee", "casts": 0, "hits": 10, "crits": 1, "damage": 400}, {"name": "Auto Shot", "casts": 9, "damage": 100},
              {"name": "Judgement", "casts": 2, "damage": 0}, {"name": "Judgement of Command", "casts": 0, "damage": 240},
              {"name": "Smite", "casts": 1, "hits": 10, "crits": 4, "damage": 60}, {"name": "Thorns", "casts": 0, "damage": 100},
              {"name": "Bite (pet)", "casts": 0, "hits": 99, "crits": 99, "damage": 100}]
        win = [fight(0, abilities=ab), fight(0, healing_role=True, abilities=ab)]
        got = {k: figure(k, win)[0] for k in ("Blade", "Shot", "Craft", "Focus", "Range", "Proc", "Crit")}
        self.assertEqual(got, {"Blade": .4, "Shot": .1, "Craft": .3, "Focus": .8, "Range": 2, "Proc": .1, "Crit": .25})
        self.assertEqual(figure("Blade", win)[1], 1)                    # healing fights stay out

    def test_craft(self):
        fig = {"efficiency": .8, "judged": 9, "temperament": {"cooldowns_share": .5, "cooldowns_possible": 7},
               "hands": {"cut_share": .02, "move_casts": 300}}
        self.assertEqual((figure("Edgewise", [], fig), figure("Ready", [], fig)), ((.8, 9), (.5, 7)))
        win = [fight()]
        self.assertEqual(figure("Planted", win, fig, {"Smite": {"cast": True}}), (.98, 300))
        self.assertEqual(figure("Planted", win, fig, {"Smite": {"cast": False}})[0], None)  # instants can't be cut
        own = lambda *b: fight(0, pull={"own": list(b)})  # noqa: E731
        self.assertEqual(figure("Primed", [own("Might", "Aura")] * 3 + [own("Aura"), own("Aura", "Food")]), (.6, 5))
        self.assertEqual(figure("Primed", [own()] * 3), (None, 3))
        win = [fight(0, group=grouped(), interrupts=2), fight(0, interrupts=9), fight(0, group=grouped())]
        self.assertEqual(figure("Break", win), (100, 2))

    def test_company_and_road(self):
        win = [fight(0), fight(0, group=grouped(), healing=100, healing_others=30, dispels=4, dispels_others=2),
               fight(0, group=grouped(damage_rank=2)), fight(0, group=grouped(), healing_role=True)]
        self.assertEqual((figure("Lone", win), figure("Bond", win)), ((.25, 4), (.75, 4)))
        self.assertEqual(figure("Lead", win), (.5, 2))                  # a healing fight is not for topping damage
        self.assertEqual(figure("Lead", [fight(0, group=grouped(), damage=0)]), (None, 0))   # nobody did any: no first
        self.assertEqual(figure("Lone", win + [fight(0, helped=True)]), (.2, 5))
        self.assertEqual(figure("Mercy", win), (200 / 3, 3))
        self.assertEqual(figure("Mercy", win, part=1), (30 / 300, 3))
        old = [{k: v for k, v in f.items() if k != "healing_others"} for f in win]
        self.assertEqual([figure("Mercy", old, part=p) for p in (0, 1)], [(None, 0), (None, 0)])
        self.assertEqual(figure("Mercy", win, {"main_role": "healer"}, part=1), (None, 3))
        win = [fight(0, zone=z) for z in ["A"] * 5 + ["B"] * 4 + [""] * 9 + ["UNKNOWN AREA"] * 9]
        self.assertEqual(figure("Travel", win)[0], 1)

    def test_role_only(self):
        fig = {"main_role": "healer", "overheal": {"fights": 20, "healing": 80, "overheal": 20}}
        self.assertEqual(figure("Thrift", [], fig), (.2, 20))
        win = [fight(0, group=grouped()), fight(0, group=grouped(deaths=["B"])), fight(0, group=grouped(), result="you died"),
               fight(0)]
        self.assertEqual(figure("Lifeline", win), (1 / 3, 3))
        table = {"landed": 60, "misses": {"dodge": 10, "parry": 10, "miss": 10, "immune": 10}}
        self.assertEqual(figure("Wall", [fight(0, swings_taken=table), fight(0, swings_taken=None)]), (.3, 100))

    def test_roles(self):
        win = many(40, swings_taken={"landed": 10, "misses": {"dodge": 5}})
        by = {r: scores(win, FIG | {"main_role": r, "overheal": {"fights": 40, "healing": 1, "overheal": 0}})
              for r in ("damage", "healer", "tank", None)}
        self.assertEqual([bool(by[r]["Thrift"]) for r in by], [False, True, False, False])
        self.assertEqual([bool(by[r]["Wall"]) for r in by], [False, False, True, False])
        self.assertEqual([bool(by[r]["Blade"]) for r in by], [True, False, True, False])
        self.assertEqual([bool(by[r]["Finish"]) for r in by], [True, True, True, False])


class Empty(unittest.TestCase):
    def test_nothing_known_is_unknown(self):
        bare = [{"me": "A", "me_name": "A", "start": (T0 - DAY).isoformat()}] * 40
        nones = [{"me": "A", "me_name": "A", "start": (T0 - DAY).isoformat(),
                  **dict.fromkeys(("end", "duration", "kind", "result", "lowest_hp", "cooldowns", "group", "foes", "target",
                                   "zone", "damage", "abilities", "pull", "danger", "swings_taken", "interrupts", "dispels",
                                   "level", "healing", "taken", "dps", "healing_role", "more", "spec"))}] * 40
        for win in ([], [fight()], bare, nones):
            p = profile(win, None, None, None, T0)
            json.dumps(p)
            if win:
                self.assertIsNotNone(p["now"]["title"])
                self.assertEqual(p["now"]["hero"], None)
            build_profile(p, [])
        self.assertEqual([t["key"] for t in profile([fight()], None, {}, [], T0)["now"]["traits"]], [])
        self.assertTrue(all(v is None for v in scores(bare, {}).values()))


class Choosing(unittest.TestCase):
    def test_family_rule(self):
        sc = known(Tempo=3, Streak=2, Edge=1)
        self.assertEqual(pick(sc), ["Tempo", "Edge"])                   # Streak is Tempo's family
        self.assertEqual(pick(known(Tempo=0)), [])

    def test_ties(self):
        self.assertEqual(pick(known(Tempo=2, Finish=2, Travel=2)), ["Tempo", "Finish"])     # the table's order
        self.assertEqual(pick(known(Tempo=2, Thrift=2)), ["Thrift", "Tempo"])               # role-only first

    def test_named_order_and_reach(self):
        for a, b, title in NAMED:
            self.assertEqual(traits.named(known(**{a: 2, b: 2}))[0], title)
            self.assertIsNone(traits.named(known(**{a: 2, b: 1})))
        self.assertEqual(traits.named(known(Edge=2, Crowd=3, Streak=3)), ("the Cornered Lion", "Crowd", "Edge"))

    def test_named_title_leads(self):
        sc = known(Travel=3, Lone=2, Tempo=3)
        sc["Travel"]["score"] = 1
        c = titles.crest([fight()], FIG | {"places": {"World": 1.0}}, sc, "PALADIN", None, None)
        self.assertEqual(c["title"], "the Lone Storm, Crusader of the Wilds")
        self.assertEqual((c["lead"], c["second"]), ("Tempo", "Fights all over the map, fights alone."))


class Nouns(unittest.TestCase):
    def test_every_tree(self):
        self.assertEqual({c: len(set(t.values())) for c, t in titles.NOUNS.items()}, dict.fromkeys(titles.NOUNS, 3))
        for cls, trees in titles.NOUNS.items():
            for tree, word in trees.items():
                self.assertEqual(titles.noun(cls, tree, "damage", 1.0), word)
                self.assertEqual(titles.noun(cls, tree, "damage", .4), word)       # the tree stands over mixed roles
        self.assertEqual(titles.noun("DRUID", "Feral Combat", "tank", 1.0), "Thornhide")

    def test_unknown_spec(self):
        for cls, roles in titles.ROLE_NOUN.items():
            for role, word in roles.items():
                self.assertEqual(titles.noun(cls, None, role, .6), word)
                self.assertEqual(titles.noun(cls, "No such tree", role, .6), word)
        self.assertEqual(titles.noun("MAGE", None, "tank", 1.0), "Bulwark")

    def test_no_class_and_mixed(self):
        self.assertEqual([titles.noun(None, None, r, 1.0) for r in ("damage", "healer", "tank")],
                         ["Slayer", "Mender", "Bulwark"])
        self.assertEqual(titles.noun("PALADIN", None, "damage", .59), "Champion")
        self.assertEqual(titles.noun(None, None, None, None), "Champion")

    def test_spec_from_the_fights_then_the_snapshot(self):
        t = lambda fs, char: profile(fs, char, {}, [], T0)["now"]["title"]  # noqa: E731
        char = {"class": "PALADIN", "spec": "Holy"}
        self.assertEqual(t(plain(spec="Protection"), char), "Shieldsworn of the Wilds")
        self.assertEqual(t(plain(), char), "Lightmender of the Wilds")
        self.assertEqual(t(plain(), None), "Slayer of the Wilds")
        half = plain(20, spec="Protection") + plain(20, spec="Holy")
        self.assertEqual([t(h, char) for h in (half, half[::-1])], ["Saving Lightmender of the Wilds"] * 2)    # a tie: by name


class Where(unittest.TestCase):
    def w(self, win, places=None, types=None, **tiers):
        return titles.where(win, {"places": places or {}}, known(**tiers), types)

    def test_bane(self):
        foes = [["G", 4], ["H", 6]]
        for kind, word in titles.BANE.items():
            self.assertEqual(self.w([fight(foes=foes)], types={"G": kind, "H": "Humanoid"}), (f"Bane of {word}", True))
        self.assertIsNone(self.w([fight(foes=[["G", 39], ["H", 61]])], types={"G": "Beast", "H": "Humanoid"}))
        self.assertIsNone(self.w([fight(foes=foes)], types={"G": "Beast"}))         # types for less than half
        self.assertIsNone(self.w([fight(foes=foes)], types={"H": "Humanoid", "G": "Critter"}))
        self.assertIsNone(self.w([fight(foes=foes, kind="PvP")], types={"G": "Beast", "H": "Beast"}))

    def test_nemesis(self):
        foes = [["Syndicate Spy", 20], ["Syndicate Thug", 10], ["Wolf", 170]]
        self.assertEqual(self.w([fight(foes=foes)]), ("Scourge of the Syndicate", True))
        self.assertIsNone(self.w([fight(foes=foes + [["Bear", 1]])]))               # under 15%
        self.assertIsNone(self.w([fight(foes=[["Syndicate Spy", 20], ["Syndicate Thug", 9]])]))     # under 30 kills
        self.assertIsNone(self.w([fight(foes=[["Syndicate Spy", 99]])]))            # one name shares nothing
        self.assertIsNone(self.w([fight(foes=[["Highland Strider", 50], ["Highland Thrasher", 50]])]))      # a place
        dark = [["Dark Iron Sentry", 20], ["Dark Iron Raider", 20], ["Dark Strand Cultist", 20], ["Dark Adept", 20]]
        self.assertEqual(self.w([fight(foes=dark)])[0], "Scourge of the Dark Iron")
        tied = [["Witherbark A", 20], ["Witherbark B", 20], ["Defias A", 20], ["Defias B", 20]]
        self.assertEqual({self.w([fight(foes=o)])[0] for o in (tied, tied[::-1])}, {"Scourge of the Defias"})
        self.assertEqual(self.w([fight(foes=[["Scarlet Monk", 20], ["Scarlet Adept", 20]])])[0],
                         "Scourge of the Scarlet Crusade")

    def test_zone(self):
        z = lambda name: self.w([fight(zone=name)] + [fight(zone=c) for c in "abc"])  # noqa: E731
        self.assertEqual([z(n) for n in ("Arathi Highlands", "Stranglethorn Vale", "The Barrens")],
                         [("the Arathi Highlands", False), ("Stranglethorn Vale", False), ("the Barrens", False)])
        self.assertEqual({self.w([fight(zone=c) for c in o])[0] for o in ("ab", "ba")}, {"a"})      # a tie: by name
        self.assertIsNone(self.w([fight(zone=c) for c in "abcde"]))                 # under 25%
        self.assertIsNone(self.w([fight(zone=""), fight(zone="UNKNOWN AREA")]))

    def test_place_then_long_road(self):
        for place, word in titles.PLACE_OF.items():
            self.assertEqual(self.w([fight()], {place: .5}), (word, False))
        self.assertEqual(self.w([fight()], {"World": .49, "PvP": .49}, Travel=2), ("the Long Road", False))
        self.assertIsNone(self.w([fight()], {"World": .49}, Travel=1))
        self.assertIsNone(self.w([fight()], {"World": None}, Travel=2))

    def test_order(self):
        win = [fight(zone="Arathi Highlands", foes=[["Syndicate Spy", 20], ["Syndicate Thug", 20]])]
        types = {"Syndicate Spy": "Undead", "Syndicate Thug": "Undead"}
        self.assertEqual([self.w(win, {"World": 1.0}, t)[0] for t in (types, None)],
                         ["Bane of the Undead", "Scourge of the Syndicate"])
        c = titles.crest(win, FIG, known(Tempo=1), "MAGE", "Frost", types)
        self.assertEqual(c["title"], "Steady Rimecaller, Bane of the Undead")


class Deeds(unittest.TestCase):
    def test_two_best_and_who_with(self):
        win = [fight(0, lowest_hp=.02, target="Bloodscalp Berserker", group=grouped(size=3)), fight(0, foes=[["Spy", 7]],
                                                                                                 target="Spy")]
        self.assertEqual(titles.deeds(win, FIG), ["won after dropping to 2% health against Bloodscalp Berserker, in a group of 3",
                                                  "beat seven in one fight, alone, Spy among them"])
        crowd = [fight(0, foes=[["Spy", 20]], target="?", group=grouped(size=2))]
        self.assertEqual(titles.deeds(crowd, FIG), ["beat 20 in one fight, in a group of 2"])

    def test_alone_only_when_known(self):
        seven = fight(0, foes=[["Spy", 7]], target="?")
        old = {k: v for k, v in seven.items() if k != "helped"}
        self.assertEqual(titles.deeds([old], FIG), ["beat seven in one fight, without a group"])
        self.assertEqual(titles.deeds([seven | {"helped": True}], FIG), [])
        low = fight(0, lowest_hp=.02, target="Imp")
        self.assertEqual(titles.deeds([low], FIG), ["won after dropping to 2% health against Imp"])
        self.assertEqual(titles.deeds([low | {"helped": True}], FIG),
                         ["won after dropping to 2% health against Imp, with help"])
        self.assertEqual(titles.deeds([low | {"lowest_hp": .005}], FIG), [])        # would read 0%
        self.assertEqual(titles.deeds([low | {"lowest_hp": .0051}], FIG), ["won after dropping to 1% health against Imp"])
        pvp = many(6, kind="PvP")
        self.assertEqual(titles.deeds([{k: v for k, v in f.items() if k != "helped"} for f in pvp], FIG),
                         ["6 fights won against players, 6 of them without a group"])
        self.assertEqual(titles.deeds(pvp[:5] + [pvp[5] | {"helped": True}], FIG),
                         ["6 fights won against players, 5 of them alone"])

    def test_the_others(self):
        self.assertIn("40 fights in a row survived", titles.deeds(many(40), FIG))
        self.assertEqual(titles.deeds(many(33), FIG), [])                # the trait's anchors, 15 to 200
        self.assertEqual(titles.deeds(many(2, dps=318.4, target="Imp"), FIG), ["318 damage per second against Imp"])
        boss = many(9, kind="Boss", group=grouped())
        self.assertEqual(titles.deeds(boss, FIG), ["9 bosses beaten with a group"])
        self.assertEqual(titles.deeds(many(4, kind="PvP") + many(2, kind="PvP", group=grouped()), FIG),
                         ["6 fights won against players, 4 of them alone"])
        self.assertEqual(titles.deeds([fight(0, level=8), fight(1, level=10)], FIG), ["gained 2 levels"])
        self.assertIn("130 fights in one sitting", titles.deeds(many(130), FIG))
        old = [{k: v for k, v in f.items() if k != "group"} for f in many(2, lowest_hp=.01)]
        self.assertEqual(titles.deeds(old, FIG), [])                    # alone or not is not known


class Page(unittest.TestCase):
    def page(self, fs, earlier=(), **kw):
        return build_profile(profile(fs, kw.get("char"), kw.get("book") or {}, kw.get("runs") or [], T0), list(earlier))

    def test_crest_hero_card_and_drawer(self):
        char = {"class": "PALADIN", "race": "Undead", "level": 37}
        fs = plain(40, pull={"since_last": 15}, zone="Arathi Highlands")
        v = self.page(fs, char=char)
        self.assertEqual((v.crest.who, v.crest.title), ("Undead Paladin, level 37", "Relentless Crusader of the Arathi Highlands"))
        self.assertEqual((v.hero, v.hero_unit, v.caption), ("15", "s", "between one fight and the next"))
        self.assertEqual((v.card[0].name, v.card[0].value, v.card[0].unit), ("Time between fights", "15", "s"))
        self.assertEqual(len(v.card), 5)
        pace = dict(v.traits)["Pace"]
        self.assertEqual((pace[0].tier, pace[0].bar, pace[0].next), ("Relentless", 1, ""))
        streak = next(r for r in pace if r.key == "Streak")
        self.assertEqual(streak.next, "Surviving at 80, you are at 40")
        self.assertEqual(v.traits_title, f"All traits ({sum(len(r) for _, r in v.traits)})")
        self.assertTrue(all(r.bar > 0 for _, rows in v.traits for r in rows))       # no score: not listed
        self.assertTrue(all(rows for _, rows in v.traits))
        self.assertNotIn("Shot", {r.key for _, rows in v.traits for r in rows})

    def test_next_and_now_never_read_the_same(self):
        of = lambda v: dict(self.page(many(40, pull={"since_last": v})).traits)["Pace"][0].next  # noqa: E731
        self.assertEqual(of(36), "Relentless at 30s, you are at 36s")
        edge = many(38) + many(2, result="you died")        # Finish 95.0%, its top tier at 92.95%
        self.assertEqual(dict(self.page(edge).traits)["Victory"][0].next, "")
        streak = plain(80)                                  # Surviving at 79.75
        self.assertEqual(next(r for r in dict(self.page(streak[1:]).traits)["Pace"] if r.key == "Streak").next,
                         "Surviving at 80, you are at 79")
        low = plain(1000, result="killed")
        for f in low[:119]:
            f["lowest_hp"] = .3                             # 11.9% of wins, shown 12%; Daring at 12%
        edge = next(r for r in dict(self.page(low).traits)["Nerve"] if r.key == "Edge")
        self.assertEqual((edge.value, edge.next), ("12", "Daring at 12%, you are at 11.9%"))

    def test_hero_falls_back_to_the_role(self):
        v = self.page(many(12))
        self.assertEqual((v.hero, v.hero_unit, v.caption), ("100", "%", "of fight time dealing damage"))

    def test_packs(self):
        pack = lambda fs, **kw: [r.name for r in self.page(fs, **kw).card]  # noqa: E731
        fs = plain(40, pull={"since_last": 60}, potential=400)
        self.assertEqual(pack(fs), ["Time between fights", "Auto attack or abilities", "Possible damage reached",
                                    "Abilities that count", "Deaths and lowest health"])     # 26 wins: no Edge
        self.assertEqual(pack(plain(90, pull={"since_last": 30}))[:4],
                         ["Time between fights", "Wins on the edge", "Wins against three or more",
                          "Auto attack or abilities"])
        heal = plain(40, healing_role=True, healing=90, overheal=10, group=grouped(), dispels=0)
        # the Quiet Miracle, so Lifeline leads
        self.assertEqual(pack(heal)[:4], ["Fights nobody died", "Overheal", "Group healing", "Dispels"])
        tank = many(40, spec="Protection", taken=50, swings_taken={"landed": 9, "misses": {}}, group=grouped(), interrupts=1)
        got = pack(tank, char={"class": "WARRIOR"})
        self.assertLessEqual({"Hits avoided", "Damage taken", "Usual pull", "Average lowest health"}, set(got))
        guard = [f | {"lowest_hp": .84} for f in tank]
        sc = profile(guard, {"class": "WARRIOR"}, {}, [], T0)["now"]
        keys = titles.pack(guard, sc, sc["rows"], {t["key"]: t for t in sc["traits"]}, "Guard")
        self.assertEqual((keys[0], "lowest" in keys), ("Guard", False))             # one figure, said once
        pvp = many(30) + many(10, kind="PvP")
        self.assertEqual(pack(pvp)[1:], ["Player fights won", "Broken off", "Fight length", "Wins on the edge"])

    def test_outdated(self):
        old = [{k: v for k, v in f.items() if k != "chances"} for f in many(7)]
        self.assertEqual(self.page(old + many(6)).outdated, OUTDATED)
        self.assertEqual(self.page(old + many(7)).outdated, "")

    def before(self, n=40, **kw):
        return [f | {"start": (datetime.fromisoformat(f["start"]) - 20 * DAY).isoformat(), "end": None} for f in plain(n, **kw)]

    def test_before_and_the_ring(self):
        now = plain(40, pull={"since_last": 15})
        v = self.page(self.before(pull={"since_last": 60}) + now)
        self.assertEqual((v.ring, v.ring_key, v.card[0].mark), ("new: Relentless", "Tempo", "new: Relentless"))
        self.assertEqual(sum(bool(r.mark) for r in v.card + v.hands + v.roles + v.places), 1)
        self.assertEqual(v.before, "Before: Steady Slayer of the Wilds")
        self.assertIsNone(self.page(self.before(pull={"since_last": 15}) + now).ring)
        self.assertIsNone(self.page(self.before(29, pull={"since_last": 60}) + now).ring)   # Before's is not known
        v = self.page(self.before(instance=1, pull={"since_last": 15}) + now)           # else the moved row
        self.assertEqual((v.ring, [r.mark for r in v.places if r.mark]), (None, ["more open world"]))

    def test_no_chip_between_two_kinds_of_figure(self):
        # Guard's weaker part: deaths before, health now. Both are known, but not comparable
        now = plain(40, lowest_hp=.7)
        before = self.before(lowest_hp=.9)
        for f in before[:10]:
            f["result"] = "you died"
        row = next(r for r in self.page(before + now).card if r.name == "Deaths and lowest health")
        self.assertEqual((row.value, row.chip), ("70", None))

    def test_slices(self):
        fs = self.before(pull={"since_last": 15}) + plain(40)
        saved = {}
        ph.update(saved, fs, None, {}, [], T0)
        s = saved["A"][0]
        self.assertEqual((s["title"], s["traits"]["Tempo"]), ("Relentless Slayer of the Wilds", 1))
        self.assertEqual(json.loads(json.dumps(saved)), saved)
        self.assertEqual(self.page(fs, saved["A"]).earlier[0].label, "Relentless Slayer of the Wilds")
        old = {k: v for k, v in s.items() if k not in ("title", "traits")}
        old["figures"] = {k: v for k, v in s["figures"].items() if k in ("main_role", "roles", "temperament", "label")}
        self.assertEqual(self.page(fs, [old]).earlier[0].label, s["label"].rstrip("."))
        self.assertEqual(ph.update({"A": [old]}, fs, None, {}, [], T0), [])


if __name__ == "__main__":
    unittest.main()
