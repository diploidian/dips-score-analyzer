"""Live: follows the combat log while the app runs, sums up each fight as it ends, shows the overlay and tells
the Fights page. Also the tray-only mode (`dips-score.pyw live`): just the overlay, in the background."""
from __future__ import annotations

import sys

from PyQt6.QtCore import QObject, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ..config import Paths
from ..live.history import History, Live
from ..sources.savedvars import load_char
from . import settings as app_settings
from . import theme
from .overlay import Overlay

POLL_MS = 250


class LiveController(QObject):
    fight = pyqtSignal(dict)

    def __init__(self, paths: Paths, settings: dict):
        super().__init__()
        self.paths, self.settings = paths, settings
        self.history = History(paths)
        self.live = Live(paths, self.history)
        self.overlay = Overlay()
        self.overlay.moved.connect(self._moved)
        self.load_chars()
        self.timer = QTimer(self, interval=POLL_MS)
        self.timer.timeout.connect(self._poll)
        self.timer.start()
        self.refresh()       # kept up: the last fight is there from the start

    def load_chars(self):
        """the character snapshots in every saved file, and the enemies' creature types in the account-wide ones
        (the game rewrites them on /reload and logout)"""
        self.history.load_types(self.paths.account_saved_files())
        for path in self.paths.saved_files():
            try:
                char = load_char(path)
            except (OSError, ValueError):       # a half-written file: the next reload tries again
                continue
            if char:
                self.history.set_char(char)

    def _poll(self):
        try:
            done = self.live.poll()
        except Exception:
            import traceback
            traceback.print_exc()
            return
        for s in done:
            self.fight.emit(s)
            if self.settings.get("overlay", True):
                self.show(s)

    def _sync(self):
        """the overlay's settings, from settings.json's"""
        self.overlay.seconds = float(self.settings.get("overlay_seconds", 12))
        self.overlay.side = self.settings.get("overlay_side", "right")
        self.overlay.keep = bool(self.settings.get("overlay_keep", False))
        spot = self.settings.get("overlay_spot")
        self.overlay.spot = tuple(spot) if spot else None

    def show(self, s: dict):
        self._sync()
        self.overlay.show_fight(s)

    def show_last(self):
        if self.history.fights:
            self.show(self.history.fights[-1])

    def move_mode(self, on: bool):
        """unlock the card to be dragged (with the last fight on it, or a stand-in), or lock it again"""
        self.overlay.set_moving(on)
        if on:
            self.show(self.history.fights[-1] if self.history.fights else
                      {"target": "Drag me where you want me", "kind": "World", "duration": 0, "result": "",
                       "dps": 0, "damage": 0, "taken": 0})
        elif not self.overlay.keep:
            self.overlay.hide_timer.start(int(self.overlay.seconds * 1000))

    def _moved(self, x: float, y: float):
        self.settings["overlay_spot"] = [round(x, 4), round(y, 4)]
        app_settings.save(self.paths, self.settings)

    def refresh(self):
        """apply changed overlay settings: hide the card, or put the last fight up (kept, or timed again)"""
        self._sync()
        if not self.settings.get("overlay", True):
            self.overlay.hide()
        elif self.settings.get("overlay_keep") or self.overlay.isVisible():
            self.show_last()


def tray_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setBrush(theme.tok("rail"))       # the rail's mark: called after apply_look, so it is in the look in use
    p.setPen(theme.tok("rail-ac"))
    p.drawEllipse(4, 4, 56, 56)
    f = QFont("Segoe UI", 28)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(0, 0, 64, 62), Qt.AlignmentFlag.AlignCenter, "d")
    p.end()
    return QIcon(pm)


def run_tray(paths: Paths) -> int:
    """the overlay alone, from the system tray"""
    from .app import Window, apply_look
    from ..scoring.classes import load_upkeep
    from ..scoring.score import load_weights
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    settings = app_settings.load(paths)
    apply_look(paths, settings)
    load_weights(paths.weights_file)
    load_upkeep(paths.classes_file)
    ctl = LiveController(paths, settings)
    # follow Windows' light/dark switch while no window is open to do it (the window does it when open)
    QGuiApplication.styleHints().colorSchemeChanged.connect(
        lambda *_: apply_look(paths, settings) if settings["mode"] == "auto" else None)
    holder: dict = {}

    def open_window():
        if "w" not in holder:
            holder["w"] = Window(paths, live=ctl)
        holder["w"].show()
        holder["w"].raise_()
        holder["w"].activateWindow()

    tray = QSystemTrayIcon(tray_icon())
    tray.setToolTip("dips score - watching the combat log")
    menu = QMenu()
    for text, fn in (("Open dips score", open_window), ("Show the last fight", ctl.show_last)):
        act = QAction(text, menu)
        act.triggered.connect(fn)
        menu.addAction(act)
    toggle = QAction("Overlay after each fight", menu, checkable=True)
    toggle.setChecked(settings.get("overlay", True))

    def set_overlay(on):
        settings["overlay"] = on
        app_settings.save(paths, settings)
        ctl.refresh()
    toggle.toggled.connect(set_overlay)
    menu.addAction(toggle)
    menu.addSeparator()
    quit_act = QAction("Quit", menu)
    quit_act.triggered.connect(app.quit)
    menu.addAction(quit_act)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: open_window() if reason == QSystemTrayIcon.ActivationReason.DoubleClick
                           else None)
    tray.show()
    tray.showMessage("dips score", "Watching the combat log. An overlay will sum up each fight.",
                     QSystemTrayIcon.MessageIcon.Information, 4000)
    holder["tray"] = tray
    return app.exec()
