"""What the Group page shows (dips_score/group_view.py), on the real Blackfathom standings (copied in as literals from
group-data.json) and on stubs; the radar's damage axis against the card's; the page itself when PyQt6 is there:
PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.group_view import build_group, of_line  # noqa: E402
from dips_score.model.roster import Player  # noqa: E402
from dips_score.model.summary import Award  # noqa: E402
from dips_score.scoring.group import GroupData, Placing, damage_share  # noqa: E402
from dips_score.scoring.radar import Radar, radars  # noqa: E402
from dips_score.scoring.score import Category  # noqa: E402

HAVE_QT = importlib.util.find_spec("PyQt6") is not None

# Blackfathom Deeps, 18 Nov 22:27 (run 6), as dump_group_data.py saw it: guid, name, role, score, grade, points,
# strengths, weaknesses, radar values, radar details
GROUP = [
    ("pir", "Piraña Segundo", "DPS", 94.6, "S", 100.6,
     ["Damage: 102,728 damage (123% of an even share, 52/s)",
      "Survival: 0 deaths; took 4,958 damage (1.0x the damage dealers' middle)"], [],
     [100.0, 2.8, 8.4, 100.0, 100.0, 100],
     ["110.9K damage", "1.6K healing", "8.0K taken, 4 of 161 mobs went for them first", "34 interrupts, 2 dispels",
      "50 killing blows", "0 deaths"]),
    ("ana", "Anaruz Lightborne", "TANK", 61.8, "C", 65.8,
     ["Holding mobs: 130 of 161 mobs went for them first (81%)", "Damage: 80,379 damage (96% of an even share)"],
     ["Pickups: 64 times a mob left them: median 6.0s to get it back, 38 not back within 6s"],
     [81.6, 10.4, 100.0, 8.3, 60.0, 60],
     ["90.5K damage", "6.1K healing", "58.4K taken, 130 of 161 mobs went for them first", "0 interrupts, 3 dispels",
      "30 killing blows", "1 death"]),
    ("me", "Bao Kahn", "DPS", 67.4, "C", 65.4,
     ["Damage: 106,991 damage (128% of an even share, 54/s)"],
     ["Survival: 1 death; took 15,059 damage (3.0x the damage dealers' middle)",
      "Utility: 0 interrupts and dispels (0.0 per 10 min)"],
     [96.5, 7.8, 18.8, 0.0, 62.0, 60],
     ["107.0K damage", "4.6K healing", "15.7K taken, 14 of 161 mobs went for them first", "0 interrupts, 0 dispels",
      "31 killing blows", "1 death"]),
    ("evi", "Evilguy Verybad", "DPS", 60.9, "C", 62.9, [], [],
     [77.0, 0.0, 7.5, 0.0, 64.0, 60],
     ["85.4K damage", "0 healing", "4.7K taken, 9 of 161 mobs went for them first", "0 interrupts, 0 dispels",
      "32 killing blows", "1 death"]),
    ("shi", "Shizuka Tsuruta", "HEALER", 49.4, "D", 47.4,
     ["Efficiency: 45,993 cast healing, 3% overheal; 357 passive; lowest mana 0%, 0 refused for mana"],
     ["Group health: 4 deaths (Anaruz Lightborne, Shizuka Tsuruta, Bao Kahn, Evilguy Verybad); someone under 35% "
      "for 77s (4% of combat)"],
     [43.1, 100.0, 6.4, 0.0, 56.0, 60],
     ["47.8K damage", "58.8K healing", "5.7K taken, 4 of 161 mobs went for them first", "0 interrupts, 0 dispels",
      "28 killing blows", "1 death"]),
]
# a.summary.awards, in the run's order: title, blurb, holder, stat, good
AWARDS = [
    ("Wrecking Ball", "Most damage done.", "pir", "111K damage (56/s)", True),
    ("Boss Bane", "Most damage to bosses.", "me", "14K on bosses", True),
    ("Janitor", "Most damage to trash.", "pir", "98K on trash", True),
    ("Patch Kit", "Most healing by someone who isn't the healer.", "ana", "6.1K healing", True),
    ("Punching Bag", "Took the most hits without being the tank.", "me", "16K damage taken", False),
    ("Shush", "Most interrupts.", "pir", "34 interrupts", True),
    ("Scrubber", "Most dispels.", "ana", "3 dispels", True),
    ("Last Word", "Most killing blows.", "pir", "50 killing blows", True),
    ("Untouchable", "Damage dealer who took the fewest hits.", "evi", "only 4.7K damage taken", True),
    ("Spare Hands", "Healer who still found time to hurt things.", "shi", "48K damage on top of 59K healing", True),
    ("Carpet Sampler", "Spent the most time lying down.", "shi", "1 death", False),
    ("Eager Beaver", "Started the most pulls without being the tank.", "me", "8 pulls started", False),
    ("Overflowing Cup", "Most overhealing.", "shi", "11% of their healing", False),
]
YOUR_DEATH = 1204.9     # your one death, at the end of pull 23
# two cards' categories (name, score, weight, summary), as rank_group saw them
CATEGORIES = {
    "me": [("Damage", 97.3, 60, "106,991 damage (128% of an even share, 54/s)"),
           ("Survival", 36.0, 25, "1 death; took 15,059 damage (3.0x the damage dealers' middle)"),
           ("Utility", 0.0, 15, "0 interrupts and dispels (0.0 per 10 min)")],
    "evi": [("Damage", 61.3, 60, "82,875 damage (99% of an even share, 42/s)"),
            ("Survival", 60.0, 25, "1 death; took 4,427 damage (0.9x the damage dealers' middle)"),
            ("Utility", 0.0, 0, "0 interrupts and dispels (0.0 per 10 min) - a Hunter can't, so it doesn't count")],
}
# a.summary.stats: damage, dps, on bosses, healing, overheal share, taken, deaths, interrupts, dispels, killing blows,
# pulls started
STATS = {
    "pir": (110898, 56.1, 12955, 1644, 0.667, 7970, 0, 34, 2, 50, 2),
    "ana": (90534, 45.8, 9485, 6138, 0.298, 58400, 1, 0, 3, 30, 69),
    "me": (106991, 54.1, 14001, 4616, 0.389, 15713, 1, 0, 0, 31, 8),
    "evi": (85395, 43.2, 9157, 0, 0.0, 4706, 1, 0, 0, 32, 6),
    "shi": (47834, 24.2, 5653, 58829, 0.111, 5711, 1, 0, 0, 28, 7),
}


def analysis(group=GROUP, awards=AWARDS, me="me", deaths=((YOUR_DEATH, "me"),), with_radars=True):
    """a stub Analysis with what build_group reads"""
    aws = [Award(t, b, g, s, good) for t, b, g, s, good in awards]
    roster = {g: Player(g, name, role=role, is_me=g == me) for g, name, role, *_ in group}
    ranking = []
    for rank, (g, _, _, score, grade, points, plus, minus, *_) in enumerate(group, 1):
        cats = [Category(*c) for c in CATEGORIES.get(g, [])]
        card = SimpleNamespace(total=score, grade=grade, categories=cats, bonus=0.0, bonus_note="")
        ranking.append(Placing(g, card, points, rank, [aw for aw in aws if aw.guid == g], plus, minus))
    rs = {g: Radar(g, values, details) for g, *_, values, details in group} if with_radars else {}
    return SimpleNamespace(ranking=ranking, roster=roster, radars=rs, summary=SimpleNamespace(awards=aws),
                           deaths=[SimpleNamespace(t=t, guid=g) for t, g in deaths],
                           data=SimpleNamespace(player_guid=me))


def with_numbers(a):
    """the stub, with the summary's numbers and run line (as the old Summary tab read them)"""
    names = ("damage", "dps", "boss_damage", "healing", "overheal_share", "taken", "deaths", "interrupts", "dispels",
             "killing_blows", "pulls_started")
    for p in a.roster.values():
        p.role_from = "addon"
    a.summary.stats = {g: SimpleNamespace(player=a.roster[g], **dict(zip(names, STATS[g]))) for g in a.roster}
    a.summary.combat_time, a.summary.bosses_killed, a.summary.bosses = 1977.6, 6, 6
    a.summary.trash_killed, a.summary.wipes = 152, 0
    a.data.duration = 4185.3
    a.deaths = [SimpleNamespace(t=t, guid=g) for t, g in ((600.0, "ana"), (900.0, "shi"), (YOUR_DEATH, "me"),
                                                         (1300.0, "evi"))]
    return a


class GroupViewTests(unittest.TestCase):
    def test_group_view_blackfathom(self):
        v = build_group(analysis())
        self.assertEqual((v.place, v.of), (3, 5))
        self.assertEqual((round(v.behind_next, 1), round(v.behind_mvp)), (0.4, 35))
        self.assertEqual(of_line(v), "of 5 · 0.4 points behind 2nd · 35 behind the MVP")
        self.assertEqual(v.reason, "67 as a damage dealer, −2 from awards — strongest at damage, held back by survival")
        self.assertEqual((v.cards[0].name, v.cards[0].mvp, v.cards[0].role), ("Piraña Segundo", True, "DPS"))
        self.assertEqual([c.rank for c in v.cards], [1, 2, 3, 4, 5])
        self.assertEqual([c.name for c in v.podium], ["Piraña Segundo", "Anaruz Lightborne", "Bao Kahn"])
        you = v.cards[2]
        self.assertTrue(you.you and not any(c.you for c in v.cards if c is not you))
        self.assertEqual((you.points, you.score, you.grade, v.cards[1].role), (65.4, 67.4, "C", "Tank"))
        self.assertEqual(you.plus, [("Damage", "106,991 damage (128% of an even share, 54/s)")])
        self.assertEqual(you.minus[0], ("Survival", "1 death; took 15,059 damage (3.0x the damage dealers' middle)"))
        self.assertIn(("Punching Bag", False, "Roast, −2: Took the most hits without being the tank. 16K damage taken"),
                      you.awards)
        self.assertEqual(you.awards[0], ("Boss Bane", True, "Award, +2: Most damage to bosses. 14K on bosses"))
        self.assertEqual(you.radar[0], 96.5)
        self.assertEqual(you.details[5], "1 death")
        self.assertEqual([round(x, 1) for x in v.average], [79.6, 24.2, 28.2, 21.7, 68.4, 68.0])
        title, caption = v.move_up
        self.assertEqual(title, "You took 15,059 damage — 3× the other damage dealers.")
        self.assertEqual(caption,
                         "Roasts cost you 4 points (Punching Bag, Eager Beaver); one place is 0.4 points away.")
        self.assertTrue(caption.endswith("one place is 0.4 points away."))
        self.assertEqual(v.death_at, YOUR_DEATH)
        # the awards list: every award, then every roast, each in the run's order; the blurb without its full stop
        self.assertEqual(v.awards[0],
                         ("Wrecking Ball", "Most damage done", "Piraña Segundo", "111K damage (56/s)", True))
        self.assertEqual([t for t, *_ in v.awards][-4:], ["Punching Bag", "Carpet Sampler", "Eager Beaver",
                                                          "Overflowing Cup"])
        self.assertEqual(sum(good for *_, good in v.awards), 9)

    def test_class_and_level(self):
        a = analysis()
        a.roster["me"].cls, a.roster["me"].cls_from, a.roster["me"].level = "PALADIN", "addon", 39
        a.roster["evi"].cls, a.roster["evi"].cls_from = "HUNTER", "spells"
        cards = {c.name: c for c in build_group(a).cards}
        self.assertEqual((cards["Bao Kahn"].who, cards["Bao Kahn"].who_tip, cards["Bao Kahn"].cls), ("Paladin 39", "", "PALADIN"))
        self.assertEqual((cards["Evilguy Verybad"].who, cards["Evilguy Verybad"].who_tip),
                         ("Hunter", "Class guessed from the spells they cast. "
                                    "Level not recorded: the run is older than add-on 0.6.3"))
        self.assertEqual((cards["Piraña Segundo"].who, cards["Piraña Segundo"].who_tip), ("", ""))      # not known

    def test_breakdown(self):
        """a card's score help: each category's score, weight and numbers, the bonus, the awards"""
        v = build_group(analysis())
        self.assertEqual(v.cards[2].breakdown.split("\n"), [
            "Bao Kahn — 3rd, 65 points",
            "67 as a damage dealer, −2 from awards",
            "Damage 97 · weight 60 · 106,991 damage (128% of an even share, 54/s)",
            "Survival 36 · weight 25 · 1 death; took 15,059 damage (3.0x the damage dealers' middle)",
            "Utility 0 · weight 15 · 0 interrupts and dispels (0.0 per 10 min)",
            "Boss Bane +2 · 14K on bosses",
            "Punching Bag −2 · 16K damage taken",
            "Eager Beaver −2 · 8 pulls started"])
        self.assertIn("Utility 0 · info only · 0 interrupts and dispels (0.0 per 10 min) - a Hunter can't, so it "
                      "doesn't count", v.cards[3].breakdown)
        a = analysis()
        a.ranking[4].card.bonus, a.ranking[4].card.bonus_note = 2.5, "45,421 damage = 40% of an even share"
        self.assertIn("Hybrid bonus +2.5 · 45,421 damage = 40% of an even share", build_group(a).cards[4].breakdown)

    def test_move_up_phrasing(self):
        """the known weakness lines in plain words; anything else as it is"""
        def title(minus):
            g = [list(row) for row in GROUP]
            g[2][7] = minus
            return build_group(analysis(g)).move_up[0]
        self.assertEqual(title(["Damage: 50,120 damage (61% of an even share, 25/s)"]),
                         "You did 50,120 damage — 61% of an even share.")
        self.assertEqual(title(["Utility: 0 interrupts and dispels (0.0 per 10 min)"]),
                         "You never interrupted or dispelled.")
        self.assertEqual(title(["Utility: 3 interrupts and dispels (0.9 per 10 min)"]),
                         "You interrupted or dispelled 3 times — 0.9 per 10 min.")
        self.assertEqual(title(["Survival: 2 deaths; took 9,000 damage (2.5x the damage dealers' middle)"]),
                         "You took 9,000 damage — 2.5× the other damage dealers.")
        self.assertEqual(title(["Survival: 2 deaths; took 4,000 damage (1.0x the damage dealers' middle)"]),
                         "You died 2 times.")
        self.assertEqual(title(["Pickups: 64 times a mob left you: median 6.0s to get it back"]),
                         "64 times a mob left you: median 6.0s to get it back.")
        self.assertEqual(title([]), "No one category held you back.")

    def test_caption_without_roasts(self):
        aws = [aw for aw in AWARDS if aw[0] not in ("Punching Bag", "Eager Beaver")]
        v = build_group(analysis(awards=aws))
        self.assertEqual(v.move_up[1], "One place is 0.4 points away.")
        one = [aw for aw in AWARDS if aw[0] != "Eager Beaver"]
        self.assertEqual(build_group(analysis(awards=one)).move_up[1],
                         "A roast cost you 2 points (Punching Bag); one place is 0.4 points away.")

    def test_group_view_healer_you(self):
        """you're the healer and placed 1st, with no weaknesses, no radar and no death"""
        g = [list(row) for row in GROUP]
        g[0], g[4] = g[4], g[0]
        g[0][6], g[0][7] = [], []
        v = build_group(analysis(g, me="shi", deaths=(), with_radars=False))
        self.assertEqual((v.place, v.of), (1, 5))
        self.assertIsNone(v.move_up)
        self.assertIsNone(v.behind_next)
        self.assertIsNone(v.behind_mvp)
        self.assertIsNone(v.death_at)
        self.assertIsNone(v.average)
        self.assertEqual(v.cards[0].role, "Healer")
        self.assertTrue(v.cards[0].you and v.cards[0].mvp)
        self.assertEqual((v.cards[0].radar, v.cards[0].details, v.cards[0].plus), (None, None, []))
        self.assertEqual(of_line(v), "of 5 · MVP")
        self.assertEqual(v.reason, "49 as a healer, −2 from awards")

    def test_nobody_ranked(self):
        v = build_group(analysis([], awards=[], deaths=()))
        self.assertEqual((v.place, v.of, v.cards, v.podium, v.awards, v.move_up), (None, 0, [], [], [], None))
        self.assertEqual(of_line(v), "")

    def test_you_not_in_the_standings(self):
        v = build_group(analysis(me="someone else", deaths=()))
        self.assertEqual((v.place, v.of, v.move_up, v.behind_next), (None, 5, None, None))
        self.assertEqual(len(v.cards), 5)


class RadarTests(unittest.TestCase):
    def test_radar_damage_matches_card(self):
        """the map's damage axis is the fight-windowed damage the cards are scored on, not the whole log's"""
        fights = [SimpleNamespace(start=0.0, end=100.0), SimpleNamespace(start=200.0, end=300.0)]
        # (time, amount): the 400 s hits fall outside every fight, so they count for the log, not the card
        series = {"pir": [(10, 100000), (250, 2728), (400, 8170)], "me": [(20, 106991)], "ana": [(30, 80379),
                                                                                                (400, 10155)]}
        whole = {g: sum(v for _, v in s) for g, s in series.items()}
        stats = {g: SimpleNamespace(damage=whole[g], healing=10, taken=100, interrupts=1, dispels=0, killing_blows=3,
                                    deaths=0) for g in series}
        a = SimpleNamespace(summary=SimpleNamespace(stats=stats), data=SimpleNamespace(fights=fights),
                            group=GroupData(damage=series))
        rs = radars(a)
        roster = dict.fromkeys(series)
        windows = [(f.start, f.end) for f in fights]
        card = {g: damage_share(a.group, roster, g, windows)[0] for g in series}      # what player_card uses
        self.assertEqual(card, {"pir": 102728, "me": 106991, "ana": 80379})
        for g in series:
            self.assertAlmostEqual(rs[g].values[0], 100 * card[g] / 106991)
        self.assertEqual([rs[g].details[0] for g in series], ["102.7K damage", "107.0K damage", "80.4K damage"])
        # the other axes as they were: healing, taken, utility and kills all level; no mob went for anyone first
        self.assertEqual(rs["pir"].values[1:], [100.0, 50.0, 100.0, 100.0, 100.0])


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class GroupPageTests(unittest.TestCase):
    def test_page_paints_and_shows_your_death(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the page)
        from dips_score.ui.group import GroupTab
        tab = GroupTab()
        tab.resize(1200, 900)
        shown = []
        tab.show_me.connect(lambda a, b: shown.append((a, b)))
        tab.show_view(build_group(analysis()), "Blackfathom Deeps", "Wed 18 Nov 22:27 · 69:45 long")
        self.assertEqual(tab.plate.button.text(), "Show your death")
        self.assertTrue(tab.plate.has_button)
        tab.plate.button.click()
        self.assertEqual(shown, [(YOUR_DEATH - 20, YOUR_DEATH + 5)])
        self.assertEqual(tab.roles_drawer.label, "EDIT ROLES (5)")
        self.assertTrue(tab.roles_drawer.body.isHidden())
        self.assertFalse(tab.grab().isNull())
        tips = [t for _, t in tab.standings.tips]
        self.assertIn("Roast, −2: Took the most hits without being the tank. 16K damage taken", tips)
        self.assertIn(build_group(analysis()).cards[2].breakdown, tips)        # the score line's help
        tab.show_view(build_group(analysis(me="pir", deaths=())), "Blackfathom Deeps", "")    # 1st, alive: no button
        self.assertEqual((tab.plate.title, tab.plate.has_button), ("You placed first.", False))
        tab.show_view(build_group(analysis(me="pir", deaths=((300.0, "pir"),))), "", "")     # 1st, died: none either
        self.assertFalse(tab.plate.has_button)
        self.assertEqual(tab.plate.body, "Strongest at damage: 102,728 damage (123% of an even share, 52/s).")
        tab.show_view(build_group(analysis([], awards=[], deaths=())), "No run selected", "")   # nobody: no plate
        self.assertTrue(tab.plate.isHidden())
        self.assertFalse(tab.grab().isNull())

    def test_edit_roles_signals(self):
        """the Edit roles drawer's table: a class or role picked emits changed, the button emits forget"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication, QPushButton
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the page)
        from dips_score.ui.group import GroupTab
        tab = GroupTab()
        a = analysis()
        with_numbers(a)
        a.roster["me"].cls = "PALADIN"
        changed, forgot = [], []
        tab.changed.connect(lambda *x: changed.append(x))
        tab.forget.connect(lambda: forgot.append(True))
        tab._fill_roles(a)
        self.assertEqual(tab.t.rowCount(), 5)
        row = next(r for r in range(5) if tab.t.item(r, 1).text() == "Bao Kahn  (you)")
        tab.t.cellWidget(row, 3).setCurrentIndex(0)      # Tank
        self.assertEqual(changed, [("me", "PALADIN", "TANK")])
        next(b for b in tab.findChildren(QPushButton) if b.text() == "Forget my picks").click()
        self.assertEqual(forgot, [True])

    def test_all_the_numbers(self):
        """the old Summary tab's numbers, in placing order, names in tx, with the run line over them"""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841 (kept alive for the page)
        from dips_score.ui.group import GroupTab
        tab = GroupTab()
        a = with_numbers(analysis())
        tab._fill_numbers(a)
        self.assertEqual((tab.numbers_drawer.label, tab.numbers_drawer.body.isHidden()), ("ALL THE NUMBERS (5)", True))
        self.assertEqual(tab.run_line.text(), "69:45 long, 32:57 in combat · bosses 6/6 · 152 trash killed · 4 deaths")
        t = tab.numbers
        self.assertEqual([t.horizontalHeaderItem(c).text() for c in range(t.columnCount())],
                         ["Player", "Role", "Damage", "DPS", "On bosses", "Healing", "Overheal", "Taken", "Deaths",
                          "Interrupts", "Dispels", "Killing blows", "Pulls"])
        self.assertEqual([t.item(r, 0).text() for r in range(5)], [g[1] for g in GROUP])     # placing order
        self.assertEqual([t.item(2, c).text() for c in range(13)],
                         ["Bao Kahn", "DPS", "107K", "54", "14K", "4.6K", "39%", "16K", "1", "", "", "31", "8"])
        self.assertIsNone(t.item(2, 0).data(Qt.ItemDataRole.ForegroundRole))      # no class colour
        self.assertTrue(t.item(2, 0).toolTip().startswith("Bao Kahn — 3rd, 65 points"))
        self.assertEqual(t.item(2, 2).toolTip(), "Bao Kahn — damage: damage to enemies, pets included\n"
                                                 "2nd highest in the group, 24% of the group's")
        self.assertEqual(t.item(2, 3).toolTip(),
                         "Bao Kahn — dps: damage per second of combat\n2nd highest in the group")
        self.assertEqual(t.item(2, 1).toolTip(), "role: from addon")
        a.summary.wipes = 1
        tab._fill_numbers(a)
        self.assertTrue(tab.run_line.text().endswith("4 deaths · 1 wipe"))


if __name__ == "__main__":
    unittest.main()
