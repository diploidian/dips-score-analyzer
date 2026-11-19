"""Settings (theme) saved in settings.json, and the settings window behind the cog."""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
                             QLabel, QMessageBox, QPushButton, QRadioButton, QSlider, QVBoxLayout)

from ..config import Paths, game_folder
from . import assets, texture, theme
from .pages import dim_label

DEFAULTS = {"theme": "wow",
            "wow": None,              # the game folder you picked; None: the default install
            "overlay": True,          # the card after each fight
            "overlay_seconds": 12,
            "overlay_side": "right",
            "texture": None,          # None: follow dips-Core's own setting; True/False: your pick here
            "texture_alpha": None}


def load(paths: Paths) -> dict:
    out = dict(DEFAULTS)
    f = paths.data_dir / "settings.json"
    if f.exists():
        try:
            saved = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                out.update({k: v for k, v in saved.items() if k in DEFAULTS})
        except (ValueError, OSError):
            pass
    return out


def texture_choice(paths: Paths, settings: dict) -> tuple[bool, float, bool]:
    """(on, opacity, following dips-Core)"""
    core_on, core_alpha = texture.dips_core_setting(paths)
    following = settings.get("texture") is None
    on = core_on if following else bool(settings["texture"])
    alpha = core_alpha if settings.get("texture_alpha") is None else float(settings["texture_alpha"])
    return on, alpha, following


def save(paths: Paths, settings: dict):
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    (paths.data_dir / "settings.json").write_text(json.dumps(settings, indent=1), encoding="utf-8")


def pick_wow(parent, start: Path) -> Path | None:
    """ask for the game folder until it's one with WTF in it, or they cancel"""
    while True:
        picked = QFileDialog.getExistingDirectory(parent, "Where is World of Warcraft (the _forever_ folder)?",
                                                  str(start if start.exists() else Path.home()))
        if not picked:
            return None
        found = game_folder(picked)
        if found:
            return found
        QMessageBox.warning(parent, "Not the game folder",
                            f"{picked} has no WTF folder in it. Pick the _forever_ folder inside your "
                            "World of Warcraft folder.")


class SettingsDialog(QDialog):
    theme_changed = pyqtSignal(str)
    texture_changed = pyqtSignal()
    test_overlay = pyqtSignal()
    imported = pyqtSignal()
    assets_rescanned = pyqtSignal()
    open_weights = pyqtSignal()

    def __init__(self, paths: Paths, current: str, parent=None, settings: dict | None = None):
        super().__init__(parent)
        self.paths = paths
        self.settings = settings if settings is not None else load(paths)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)

        box = QGroupBox("Game folder")
        gl = QHBoxLayout(box)
        self.wow_note = dim_label(str(self.paths.wow) + ("" if self.paths.found() else "  (not found)"))
        gl.addWidget(self.wow_note, 1)
        change = QPushButton("Change...")
        change.clicked.connect(self._pick_wow)
        gl.addWidget(change)
        lay.addWidget(box)

        box = QGroupBox("Look")
        bl = QVBoxLayout(box)
        self.choice = QButtonGroup(self)
        for key, label in theme.THEMES.items():
            rb = QRadioButton(label)
            rb.setChecked(key == current)
            rb.toggled.connect(lambda on, k=key: on and self.theme_changed.emit(k))
            self.choice.addButton(rb)
            bl.addWidget(rb)
        bl.addWidget(dim_label("Azeroth uses the game's own font, frames and icons when they're in the assets folder "
                               "(below), and draws a look-alike when they aren't."))
        lay.addWidget(box)

        box = QGroupBox("Texture")
        tl = QVBoxLayout(box)
        on, alpha, following = texture_choice(self.paths, self.settings)
        self.tex_on = QCheckBox("Draw the dips-Core texture behind the windows")
        self.tex_on.setChecked(on)
        self.tex_on.toggled.connect(self._tex_toggled)
        tl.addWidget(self.tex_on)
        row = QHBoxLayout()
        row.addWidget(QLabel("Opacity"))
        self.tex_alpha = QSlider(Qt.Orientation.Horizontal)
        self.tex_alpha.setRange(0, 100)
        self.tex_alpha.setValue(round(alpha * 100))
        self.tex_alpha.valueChanged.connect(lambda v: self.tex_value.setText(f"{v}%"))
        self.tex_alpha.sliderReleased.connect(self._tex_alpha)       # making the image takes a moment
        row.addWidget(self.tex_alpha, 1)
        self.tex_value = QLabel(f"{round(alpha * 100)}%")
        self.tex_value.setFixedWidth(40)
        row.addWidget(self.tex_value)
        match = QPushButton("Match dips-Core")
        match.clicked.connect(self._tex_follow)
        row.addWidget(match)
        tl.addLayout(row)
        self.tex_note = dim_label()
        tl.addWidget(self.tex_note)
        self._tex_note(following)
        box.setVisible(texture.source(self.paths) is not None)   # nothing to draw without dips-Core's texture
        lay.addWidget(box)

        box = QGroupBox("After each fight")
        ol = QVBoxLayout(box)
        self.ov_on = QCheckBox("Show a summary over the game when a fight ends")
        self.ov_on.setChecked(bool(self.settings.get("overlay", True)))
        self.ov_on.toggled.connect(lambda on: self._set("overlay", on))
        ol.addWidget(self.ov_on)
        row = QHBoxLayout()
        row.addWidget(QLabel("Stays for"))
        self.ov_secs = QSlider(Qt.Orientation.Horizontal)
        self.ov_secs.setRange(4, 30)
        self.ov_secs.setValue(int(self.settings.get("overlay_seconds", 12)))
        secs_lbl = QLabel(f"{self.ov_secs.value()} s")
        secs_lbl.setFixedWidth(40)
        self.ov_secs.valueChanged.connect(lambda v: (secs_lbl.setText(f"{v} s"), self._set("overlay_seconds", v)))
        row.addWidget(self.ov_secs, 1)
        row.addWidget(secs_lbl)
        side = QButtonGroup(self)
        for key, label in (("left", "Left"), ("right", "Right")):
            rb = QRadioButton(label)
            rb.setChecked(self.settings.get("overlay_side", "right") == key)
            rb.toggled.connect(lambda on, k=key: on and self._set("overlay_side", k))
            side.addButton(rb)
            row.addWidget(rb)
        test = QPushButton("Show it")
        test.setToolTip("Show the last fight on the overlay now")
        test.clicked.connect(self.test_overlay.emit)
        row.addWidget(test)
        ol.addLayout(row)
        row = QHBoxLayout()
        imp = QPushButton("Add fights from my old combat logs")
        imp.clicked.connect(self._import)
        row.addWidget(imp)
        self.imp_note = dim_label()
        row.addWidget(self.imp_note, 1)
        ol.addLayout(row)
        ol.addWidget(dim_label("Works with the game in borderless fullscreen (not exclusive fullscreen). Fights come from "
                               "the combat log alone, so /combatlog must be on; the game writes it in batches, so a "
                               "summary shows up a few seconds after the fight ends."))
        lay.addWidget(box)

        box = QGroupBox("Game art")
        self.art = QGridLayout(box)
        lay.addWidget(box)
        self.where = dim_label()
        lay.addWidget(self.where)
        row = QHBoxLayout()
        open_btn = QPushButton("Open the assets folder")
        open_btn.clicked.connect(self._open_folder)
        again = QPushButton("Look again")
        again.clicked.connect(self._rescan)
        how = QPushButton("How to get them")
        how.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(assets.PROJECT / "assets" / "README.txt"))))
        row.addWidget(open_btn)
        row.addWidget(again)
        row.addWidget(how)
        row.addStretch(1)
        lay.addLayout(row)

        row = QHBoxLayout()
        weights = QPushButton("Scoring weights...")
        weights.clicked.connect(self.open_weights.emit)
        row.addWidget(weights)
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(close)
        lay.addLayout(row)
        self._fill_art()

    def _set(self, key: str, value):
        self.settings[key] = value
        save(self.paths, self.settings)

    def _pick_wow(self):
        found = pick_wow(self, self.paths.wow)
        if found:
            self._set("wow", str(found))
            self.wow_note.setText(f"{found}  (close and reopen the app to use it)")

    def _import(self):
        from ..live.history import replay
        from ..sources import combatlog
        from PyQt6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            n = replay(self.paths, combatlog.find_logs(self.paths.logs))
        finally:
            QApplication.restoreOverrideCursor()
        self.imp_note.setText(f"Added {n} fight{'s' if n != 1 else ''}." if n else "Nothing new to add.")
        self.imported.emit()

    def _tex_note(self, following: bool):
        core_on, core_alpha = texture.dips_core_setting(self.paths)
        if texture.source(self.paths) is None:
            self.tex_note.setText("dips-Core's texture.tga wasn't found in the AddOns folder.")
        elif following:
            self.tex_note.setText(f"Following dips-Core's setting ({'on' if core_on else 'off'}, {core_alpha:.0%}). "
                                  "Change it here to use your own.")
        else:
            self.tex_note.setText(f"Your own setting here (dips-Core has it {'on' if core_on else 'off'}, "
                                  f"{core_alpha:.0%}).")

    def _tex_toggled(self, on: bool):
        self.settings["texture"] = on
        save(self.paths, self.settings)
        self._tex_note(False)
        self.texture_changed.emit()

    def _tex_alpha(self):
        self.settings["texture_alpha"] = self.tex_alpha.value() / 100
        if self.settings.get("texture") is None:
            self.settings["texture"] = self.tex_on.isChecked()
        save(self.paths, self.settings)
        self._tex_note(False)
        self.texture_changed.emit()

    def _tex_follow(self):
        self.settings["texture"] = self.settings["texture_alpha"] = None
        save(self.paths, self.settings)
        on, alpha, _ = texture_choice(self.paths, self.settings)
        for w in (self.tex_on, self.tex_alpha):
            w.blockSignals(True)
        self.tex_on.setChecked(on)
        self.tex_alpha.setValue(round(alpha * 100))
        self.tex_value.setText(f"{round(alpha * 100)}%")
        for w in (self.tex_on, self.tex_alpha):
            w.blockSignals(False)
        self._tex_note(True)
        self.texture_changed.emit()

    def _fill_art(self):
        while self.art.count():
            w = self.art.takeAt(0).widget()
            if w:
                w.deleteLater()
        for i, (what, detail, found) in enumerate(assets.report()):
            mark = QLabel("✓" if found else "–")
            mark.setStyleSheet(f"color: {theme.BUSY.name() if found else theme.DIM.name()}; font-weight: 700;")
            self.art.addWidget(mark, i, 0)
            self.art.addWidget(QLabel(what), i, 1)
            self.art.addWidget(dim_label(detail), i, 2)
        self.art.setColumnStretch(2, 1)
        self.where.setText("Looking in: " + "  ·  ".join(str(f) for f in assets.folders()))

    def _open_folder(self):
        folder = assets.PROJECT / "assets"
        folder.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _rescan(self):
        assets.rescan()
        self._fill_art()
        self.assets_rescanned.emit()
