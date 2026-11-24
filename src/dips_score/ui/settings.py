"""Settings (theme) saved in settings.json, and the settings window behind the rail's Settings link."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
                             QLabel, QLineEdit, QMessageBox, QPushButton, QRadioButton, QSlider, QVBoxLayout)

from ..config import Paths, game_folder
from . import assets, texture, theme, tokens
from .settings_store import DEFAULTS, load, save  # noqa: F401  (re-exported: app.py and live_ui.py use them from here)
from .pages import dim_label


def texture_choice(paths: Paths, settings: dict) -> tuple[bool, float, bool]:
    """(on, opacity, following dips-Core)"""
    core_on, core_alpha = texture.dips_core_setting(paths)
    following = settings.get("texture") is None
    on = core_on if following else bool(settings["texture"])
    alpha = core_alpha if settings.get("texture_alpha") is None else float(settings["texture_alpha"])
    return on, alpha, following


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
    folders_changed = pyqtSignal()
    overlay_changed = pyqtSignal()
    move_overlay = pyqtSignal(bool)

    def set_theme(self, key: str):
        """show the look chosen elsewhere (the rail), without echoing it back"""
        for b, k in zip(self.choice.buttons(), tokens.THEMES):
            b.blockSignals(True)
            b.setChecked(k == key)
            b.blockSignals(False)

    def __init__(self, paths: Paths, current: str, parent=None, settings: dict | None = None):
        super().__init__(parent)
        self.paths = paths
        self.settings = settings if settings is not None else load(paths)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)

        box = QGroupBox("Game folders")
        fl = QGridLayout(box)
        self.wow_edit, self.logs_edit = QLineEdit(readOnly=True), QLineEdit(readOnly=True)
        for i, (label, edit, pick) in enumerate((("World of Warcraft", self.wow_edit, self._pick_wow),
                                                 ("Combat logs", self.logs_edit, self._pick_logs))):
            fl.addWidget(QLabel(label), i, 0)
            fl.addWidget(edit, i, 1)
            b = QPushButton("Browse...")
            b.clicked.connect(pick)
            fl.addWidget(b, i, 2)
        reset = QPushButton("Use the game's")
        reset.setToolTip("Look for combat logs in the game folder's Logs folder")
        reset.clicked.connect(lambda: self._set_folders(logs=None))
        fl.addWidget(reset, 1, 3)
        self.folder_note = dim_label()
        fl.addWidget(self.folder_note, 2, 0, 1, 4)
        fl.setColumnStretch(1, 1)
        lay.addWidget(box)
        self._show_folders()

        box = QGroupBox("Look")
        bl = QVBoxLayout(box)
        self.choice = QButtonGroup(self)
        for key, label in tokens.THEMES.items():
            rb = QRadioButton(label)
            rb.setChecked(key == current)
            rb.toggled.connect(lambda on, k=key: on and self.theme_changed.emit(k))
            self.choice.addButton(rb)
            bl.addWidget(rb)
        self.motion = QCheckBox("Animate the Debrief and Profile when they open")
        self.motion.setChecked(bool(self.settings.get("motion", True)))
        self.motion.toggled.connect(lambda on: self._set("motion", on))
        bl.addWidget(self.motion)
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
        self.ov_on.toggled.connect(lambda on: (self._set("overlay", on), self.overlay_changed.emit()))
        ol.addWidget(self.ov_on)
        self.ov_keep = QCheckBox("Keep it up and update it after each fight")
        self.ov_keep.setChecked(bool(self.settings.get("overlay_keep", False)))
        ol.addWidget(self.ov_keep)
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
        self.ov_secs.setEnabled(not self.ov_keep.isChecked())
        self.ov_keep.toggled.connect(lambda on: (self._set("overlay_keep", on), self.ov_secs.setEnabled(not on),
                                                 self.overlay_changed.emit()))
        side = QButtonGroup(self)
        for key, label in (("left", "Left"), ("right", "Right")):
            rb = QRadioButton(label)
            rb.setChecked(self.settings.get("overlay_side", "right") == key)
            rb.clicked.connect(lambda _=False, k=key: self._side(k))   # clicked: works on the already-picked side too
            side.addButton(rb)
            row.addWidget(rb)
        self.side_buttons = side
        self.move_btn = QPushButton("Move it", checkable=True)
        self.move_btn.setToolTip("Drag the card where you want it, then press Done")
        self.move_btn.toggled.connect(lambda on: (self.move_btn.setText("Done" if on else "Move it"),
                                                  self.move_overlay.emit(on)))
        row.addWidget(self.move_btn)
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

    def _side(self, key: str):
        """Left/Right puts the card back on that edge, forgetting where it was dragged"""
        self.settings["overlay_spot"] = None
        self._set("overlay_side", key)
        self.overlay_changed.emit()

    def hideEvent(self, e):
        self.move_btn.setChecked(False)      # closing Settings locks the card again
        super().hideEvent(e)

    def _pick_wow(self):
        found = pick_wow(self, self.paths.wow)      # only a folder with WTF in it (or its parent)
        if found:
            self._set_folders(wow=str(found))

    def _pick_logs(self):
        d = QFileDialog.getExistingDirectory(self, "The folder with WoWCombatLog*.txt in it", str(self.paths.logs))
        if d:
            self._set_folders(logs=d)

    _KEEP = object()

    def _set_folders(self, wow=_KEEP, logs=_KEEP):
        """save the pick and change the shared Paths in place, so the open window follows it"""
        if wow is not self._KEEP:
            self.settings["wow_folder"] = wow
            self.paths.wow = Path(wow)
        if logs is not self._KEEP:
            self.settings["logs_folder"] = logs
            self.paths.logs_dir = Path(logs) if logs else None
        save(self.paths, self.settings)
        self._show_folders()
        self.folders_changed.emit()

    def _show_folders(self):
        for edit, path in ((self.wow_edit, self.paths.wow), (self.logs_edit, self.paths.logs)):
            edit.setText(str(path))
            edit.setToolTip(str(path))
            edit.setCursorPosition(0)
        logs = len(list(self.paths.logs.glob("WoWCombatLog*.txt"))) if self.paths.logs.is_dir() else 0
        saved = len(self.paths.saved_files()) if self.paths.accounts.is_dir() else 0
        bad = [] if (self.paths.wow / "WTF").is_dir() else ["no WTF folder in the game folder"]
        self.folder_note.setText("  ·  ".join(bad + [f"{logs} combat log{'s' if logs != 1 else ''}",
                                                    f"{saved} dips-Score saved file{'s' if saved != 1 else ''}"]))

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
