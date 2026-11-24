"""What the after-fight card shows (dips_score/overlay_view.py), on real fights from the live fight store (copied in as
literals, cut to the keys the card reads) and on the bare stand-in the card shows while it's being moved; the card's
inks against its see-through panel; and the painted card itself when PyQt6 is there:
PYTHONPATH=<folder with PyQt6> python -m unittest discover -s tests"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.overlay_view import PANEL_ALPHA, build_card  # noqa: E402
from dips_score.ui import tokens  # noqa: E402
from test_tokens import contrast  # noqa: E402

HAVE_QT = importlib.util.find_spec("PyQt6") is not None

# Wed 18 Nov 23:30:52, Blackfathom Deeps: 55%, entered at 57% health
GAP = {
    "start": "2026-11-18T23:30:52.757000", "duration": 96.475, "kind": "Dungeon", "zone": "Blackfathom Deeps",
    "target": "Old Serra'kis", "more": 1, "result": "killed", "damage": 2778, "dps": 28.795024617776626,
    "healing": 102, "taken": 492, "efficiency": 0.5451677112869854, "healing_role": False,
    "verdict": "11 swings lost while not attacking, about 1,327 damage.", "danger": None,
    "cooldowns": [{"name": "Consecration", "cd": 8.91, "free": 57.50000000000055, "lost": 496.9135802469183},
                  {"name": "Judgement", "cd": 8.0, "free": 38.50000000000028, "lost": 283.13541666666873},
                  {"name": "Holy Strike", "cd": 9.99, "free": 33.400000000000205, "lost": 210.6306306306319}],
    "auto": {"swings": 12, "lost": 11, "lost_casting": 0, "lost_other": 11, "damage_lost": 1327.0},
    "idle": {"with_resource": 41.370999999999995, "lost": 0.0},
    "resource": {"start": 1.0, "end": 0.9868529170090387, "start_hp": 0.5683890577507599, "type": 0},
    "updated": True,
}
# Wed 18 Nov 22:28:01: 95%, a few seconds of cooldowns left (no gap box for a clean fight)
CLEAN = {
    "start": "2026-11-18T22:28:01.326000", "duration": 38.052, "kind": "Dungeon", "zone": "Blackfathom Deeps",
    "target": "Murkshallow Snapclaw", "more": 1, "result": "killed", "damage": 2083, "dps": 54.7408808998213,
    "healing": 130, "taken": 308, "efficiency": 0.9519408011718342, "healing_role": False,
    "verdict": "Clean fight: 95% of the damage that was possible.", "danger": None,
    "cooldowns": [{"name": "Holy Strike", "cd": 9.99, "free": 9.499999999999982, "lost": 58.64197530864186},
                  {"name": "Judgement", "cd": 8.03, "free": 6.199999999999994, "lost": 46.519302615192984}],
    "auto": {"swings": 10, "lost": 0, "lost_casting": 0, "lost_other": 0, "damage_lost": 0.0},
    "idle": {"with_resource": 20.072000000000003, "lost": 0.0},
    "resource": {"start": 1.0, "end": 0.8935108153078203, "start_hp": 1.0, "type": 0}, "updated": False,
}
# Wed 18 Nov 22:45:40: died 1:49 in, at 91% (a death is never a clean fight)
DIED = {
    "start": "2026-11-18T22:45:40.546000", "duration": 122.945, "kind": "Dungeon", "zone": "Blackfathom Deeps",
    "target": "Blindlight Muckdweller", "more": 1, "result": "you died", "damage": 5547, "dps": 45.11773557281712,
    "healing": 1163, "taken": 2343, "efficiency": 0.9083471672307534, "healing_role": False,
    "verdict": "Killed by Blindlight Muckdweller: Melee for 68.",
    "danger": {"t": 109.446, "hp": 0.0, "answered": False, "unused": [],
               "hits": [{"who": "Blindlight Muckdweller", "spell": "Melee", "amount": 68},
                        {"who": "Blindlight Oracle", "spell": "Melee", "amount": 61}]},
    "cooldowns": [{"name": "Consecration", "cd": 12.07, "free": 8.399999999999986, "lost": 114.03479701739832}],
    "auto": {"swings": 22, "lost": 11, "lost_casting": 8, "lost_other": 3, "damage_lost": 336.9},
    "idle": {"with_resource": 31.028999999999996, "lost": 0.0},
    "resource": {"start": 0.4425956738768719, "end": 0.0, "start_hp": 1.0, "type": 0}, "updated": True,
}
# what the card shows while it is being moved and there's no fight yet (live_ui.py's stand-in)
MINIMAL = {"target": "Drag me where you want me", "kind": "World", "duration": 0, "result": "", "dps": 0,
           "damage": 0, "taken": 0}


class CardViewTests(unittest.TestCase):
    def test_card_gap(self):
        v = build_card(GAP)
        self.assertEqual((v.name, v.at, v.length, v.kind, v.boss, v.updated),
                         ("Trash", "23:30", "96 s", "", False, True))
        self.assertAlmostEqual(v.efficiency, 0.5452, places=4)
        self.assertEqual((v.big, v.caption, v.clean, v.died), ("55%", "of the damage that was possible", False, False))
        self.assertEqual(v.verdict, "11 swings lost while not attacking, about 1,327 damage.")
        self.assertEqual(v.gap, ("Swings lost", "×11 · ≈ 1,327 damage"))     # the biggest of the Fight page's rows
        self.assertEqual(v.chips, ["Entered at 57% hp"])
        cd = build_card(dict(GAP, auto=None))
        self.assertEqual(cd.gap, ("Consecration sat ready", "57.5 s · ≈ 497 damage"))
        old = build_card(dict(GAP, auto=None, cooldowns=[{"name": "Judgement", "cd": 8.0, "lost": 600.0}]))
        self.assertEqual(old.gap, ("Judgement sat ready", "≈ 600 damage"))   # saved before ready time was measured
        self.assertEqual(build_card(dict(GAP, resource={"start_hp": None})).chips, [])   # no health data: no chip

    def test_card_clean(self):
        v = build_card(CLEAN)
        self.assertEqual((v.name, v.at, v.length, v.big), ("Trash", "22:28", "38 s", "95%"))
        self.assertEqual((v.clean, v.gap, v.chips, v.updated), (True, None, [], False))   # entered at full: no chip
        self.assertEqual(v.verdict, "Clean fight: 95% of the damage that was possible.")
        boss = build_card(dict(CLEAN, kind="Boss", target="Lady Sarevess", duration=183.387))
        self.assertEqual((boss.name, boss.kind, boss.boss, boss.length), ("Lady Sarevess", "Boss kill", True, "3:03"))
        self.assertEqual(build_card(dict(CLEAN, kind="Boss", result="they got away")).kind, "Boss")
        self.assertEqual((build_card(dict(CLEAN, kind="PvP", target="Evilguy")).name,
                          build_card(dict(CLEAN, kind="PvP")).kind), ("Evilguy", "PvP"))
        world = build_card(dict(CLEAN, kind="World", zone="Kalimdor"))
        self.assertEqual((world.name, world.kind), ("Kalimdor", ""))
        self.assertTrue(build_card(dict(CLEAN, efficiency=0.9)).clean)
        self.assertFalse(build_card(dict(CLEAN, efficiency=0.899)).clean)

    def test_card_died(self):
        v = build_card(DIED)
        self.assertEqual((v.died, v.clean, v.big), (True, False, "91%"))
        self.assertEqual(v.verdict, "Killed by Blindlight Muckdweller: Melee for 68.")     # what killed you
        self.assertEqual(v.gap, ("Died at 1:49", ""))         # informational: the card takes no clicks
        self.assertEqual(v.chips, [])
        ready = build_card(dict(DIED, danger=dict(DIED["danger"], unused=["Divine Protection", "Lay on Hands"])))
        self.assertEqual(ready.gap, ("Died at 1:49 ·", "Divine Protection and Lay on Hands were ready"))
        one = build_card(dict(DIED, danger=dict(DIED["danger"], unused=["Divine Protection"])))
        self.assertEqual(one.gap, ("Died at 1:49 ·", "Divine Protection was ready"))
        old = {"t": 109.446, "unused": ["Divine Protection"]}           # not known whether one was pressed
        self.assertEqual(build_card(dict(DIED, danger=old)).gap, ("Died at 1:49", ""))
        self.assertEqual(build_card(dict(DIED, danger=None)).gap, ("Died at 2:02", ""))    # no health data: the end

    def test_card_minimal_dict(self):
        """the move stand-in and an old saved fight: what's missing is left out, never an error"""
        v = build_card(MINIMAL)
        self.assertEqual((v.name, v.at, v.length, v.kind, v.efficiency, v.big), ("Drag me where you want me", "",
                                                                                "0 s", "", None, "–"))
        self.assertEqual((v.caption, v.verdict, v.gap, v.chips, v.clean, v.died, v.boss),
                         ("no damage done this fight", "", None, [], False, False, False))
        old = {"start": "2026-11-18T22:22:52.938000", "duration": 20.4, "damage": 300, "dps": 14.7, "taken": 120,
               "healing": 0, "result": "they got away", "kind": "Dungeon", "target": "Aku'mai"}
        v = build_card(old)
        self.assertEqual((v.name, v.at, v.big, v.caption, v.gap, v.chips),
                         ("Trash", "22:22", "–", "not measured in this older fight", None, []))
        heal = build_card(dict(GAP, healing_role=True, healing=4200, efficiency=1.0, verdict="Healed 4,200."))
        self.assertEqual((heal.gap, heal.caption), (None, "mostly healing: damage you didn't do isn't counted"))

    def test_inks_read_on_the_see_through_card(self):
        """the card's panel is painted at PANEL_ALPHA over the game: its text inks reach 4.5:1 on that blend over a
        black and over a white frame, in all four looks; the gap box is solid plate. mu falls short (4.48:1 on
        Timeless day over black), so the card's muted words are tx2."""
        def over(fg: str, frame: int) -> str:
            a = PANEL_ALPHA / 255
            return "#" + "".join(f"{round(int(fg[i:i + 2], 16) * a + frame * (1 - a)):02x}" for i in (1, 3, 5))
        self.assertEqual(over("#F7F0E3", 0), "#e1dacf")
        self.assertEqual(len(tokens.TOKENS), 4)
        for look, t in tokens.TOKENS.items():
            for frame in (0, 255):
                bg = over(t["panel"], frame)
                for ink in ("tx", "tx2"):
                    self.assertGreaterEqual(contrast(t[ink], bg), 4.5, (look, frame, ink))
            for ink in ("plate-tx", "plate-mu", "plate-ac"):
                self.assertGreaterEqual(contrast(t[ink], t["plate"]), 4.5, (look, ink))
        day = tokens.TOKENS[("timeless", "day")]
        self.assertLess(contrast(day["mu"], over(day["panel"], 0)), 4.5)


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class OverlayCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        from dips_score.ui import theme
        cls.app = QApplication.instance() or QApplication([])
        theme.load_fonts()

    def test_card_paints_every_state_and_stays_click_through(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QPixmap
        from dips_score.ui.overlay import WIDTH, Overlay
        ov = Overlay()
        heights = {}
        for name, d in (("gap", GAP), ("clean", CLEAN), ("died", DIED), ("minimal", MINIMAL)):
            ov.show_fight(d)
            heights[name] = ov.height()
            self.assertEqual(ov.width(), WIDTH)
            pm = QPixmap(ov.size())
            ov.render(pm)
        self.assertGreater(heights["gap"], heights["clean"])          # the gap box and the chip take room
        self.assertGreater(heights["clean"], heights["minimal"])      # no bar for "–"
        flags = ov.windowFlags()
        for f in (Qt.WindowType.WindowTransparentForInput, Qt.WindowType.WindowDoesNotAcceptFocus,
                  Qt.WindowType.WindowStaysOnTopHint):
            self.assertTrue(flags & f, f)
        ov.hide()


if __name__ == "__main__":
    unittest.main()
