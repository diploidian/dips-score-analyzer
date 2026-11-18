"""The scoring weights window: a slider per category, per role. Changes apply at once and are saved
(weights.json)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSlider,
                             QVBoxLayout)

from ..config import Paths
from ..scoring.score import BONUS, DEFAULT_WEIGHTS, ROLES, WEIGHTS, reset_weights, save_weights
from .pages import dim_label

HELP = {
    "Group health": "deaths in the group, and time with someone under 35%",
    "Response": "how fast you start a heal when someone drops under 60%",
    "Efficiency": "overhealing on your cast heals, and running out of mana",
    "Casting": "refused presses (for a healer, not the ones from pressing early)",
    "Movement": "casts cut short by moving",
    "Input": "mashing, and pressing buttons with the mouse",
    "Activity": "share of combat spent casting, on the GCD or wanding",
    "Survival": "your own deaths and time under 35%",
    "Holding mobs": "share of mobs whose first hit went to you",
    "Pickups": "how fast a mob that turned to someone else is back on you",
    "Damage": "your damage against an even split of the group's (needs a group)",
    "Interrupts": "enemy casts you stopped, and debuffs you dispelled (only spells someone stopped count)",
    "Cooldowns": "damage cooldowns that sat ready while you were free to use them (learned from your casts)",
    "Upkeep": "share of combat your class's buffs and DoTs were up (only ones you applied; classes.json edits the list)",
    "Resource": "time spent at full rage or energy, so power was wasted (needs Advanced Combat Logging)",
    BONUS: "most points added for the damage you also did, scaled by how well you healed",
}


class WeightsDialog(QDialog):
    changed = pyqtSignal()

    def __init__(self, paths: Paths, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.setWindowTitle("Scoring weights")
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        lay.addWidget(dim_label("How much each category counts toward your total, per role. A category at 0 is info "
                                "only: still shown, but it doesn't count and gives no tips. Weights are relative "
                                "(35/35/20/10 is the same as 7/7/4/2). Changes apply at once and are saved."))
        self.sliders: dict[tuple[str, str], tuple[QSlider, QLabel]] = {}
        for role in ROLES:
            title = "DPS" if role == "dps" else role.title()
            box = QGroupBox(title)
            grid = QGridLayout(box)
            for i, key in enumerate(DEFAULT_WEIGHTS[role]):
                name = QLabel(key)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(0, 20 if key == BONUS else 50)
                slider.setValue(int(WEIGHTS[role][key]))
                value = QLabel()
                value.setFixedWidth(60)
                slider.valueChanged.connect(lambda v, r=role, k=key: self._set(r, k, v))
                grid.addWidget(name, i, 0)
                grid.addWidget(slider, i, 1)
                grid.addWidget(value, i, 2)
                grid.addWidget(dim_label(HELP.get(key, "")), i, 3)
                grid.setColumnStretch(3, 1)
                self.sliders[(role, key)] = (slider, value)
                self._show_value(role, key)
            lay.addWidget(box)
        row = QHBoxLayout()
        reset = QPushButton("Back to defaults")
        reset.clicked.connect(self._reset)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(reset)
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)
        self.save_timer = QTimer(self, singleShot=True, interval=400)
        self.save_timer.timeout.connect(lambda: save_weights(self.paths.weights_file))

    def _show_value(self, role: str, key: str):
        _, label = self.sliders[(role, key)]
        v = WEIGHTS[role][key]
        label.setText(f"+{v:g} max" if key == BONUS else ("info" if v == 0 else f"{v:g}"))

    def _set(self, role: str, key: str, v: int):
        WEIGHTS[role][key] = v
        self._show_value(role, key)
        self.save_timer.start()
        self.changed.emit()

    def _reset(self):
        reset_weights()
        for (role, key), (slider, _) in self.sliders.items():
            slider.blockSignals(True)
            slider.setValue(int(WEIGHTS[role][key]))
            slider.blockSignals(False)
            self._show_value(role, key)
        save_weights(self.paths.weights_file)
        self.changed.emit()
