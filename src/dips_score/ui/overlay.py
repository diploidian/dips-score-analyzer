"""The after-fight overlay: a short card over the game, at half the height of the WoW window, on its right
(or left) edge. It slides in when a fight is summed up, stays a few seconds and fades out.

It never takes focus or clicks (keys and the mouse stay with the game), and stays on top of WoW's
borderless fullscreen window. (Exclusive fullscreen draws over everything; this needs borderless.)
"""
from __future__ import annotations

import ctypes
import sys

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..live.summary import spoken
from . import theme

KIND_COLOR = {"World": "#2a6a80", "Dungeon": "#5a4a8a", "Boss": "#8a3a9a", "PvP": "#a02a2a"}
WIDTH = 440


def wow_window() -> QRect | None:
    """the WoW window's rectangle, in Qt's (logical) coordinates; None if it isn't open"""
    if sys.platform != "win32":
        return None
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, "World of Warcraft")
        if not hwnd or user32.IsIconic(hwnd):
            return None
        r = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return None
    except Exception:
        return None
    cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    # screens: Qt keeps each screen's top-left in device pixels and scales its size by the screen's DPI
    for s in QGuiApplication.screens():
        g, dpr = s.geometry(), s.devicePixelRatio()
        native = QRect(g.topLeft(), g.size() * dpr)
        if native.contains(cx, cy):
            x = g.left() + (r.left - g.left()) / dpr
            y = g.top() + (r.top - g.top()) / dpr
            return QRect(int(x), int(y), int((r.right - r.left) / dpr), int((r.bottom - r.top) / dpr))
    return None


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _ord(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


def card_html(s: dict) -> str:
    """the card's text (rich text), from a fight summary"""
    def n(v):
        return f"{v:,.0f}"
    kind = s.get("kind", "World")
    chip = (f"<span style='background:{KIND_COLOR.get(kind, '#444')}; color:white; font-size:8pt;'>"
            f"&nbsp;{kind}&nbsp;</span>")
    more = f" <span style='color:{theme.DIM.name()}'>+{s['more']}</span>" if s.get("more") else ""
    dur = f"{int(s['duration'] // 60)}:{int(s['duration'] % 60):02d}"
    result = s.get("result", "")
    res_color = "#f05050" if result == "you died" else theme.DIM.name()
    lines = [f"{chip}&nbsp; <span style='font-family:\"{theme.TITLE_FONT}\"; font-size:13pt; color:{theme.TITLE.name()}'>"
             f"{_esc(s['target'])}</span>{more}"
             f"<br><span style='color:{theme.DIM.name()}'>{dur} · </span><span style='color:{res_color}'>{result}</span>"
             + (f"<span style='color:{theme.DIM.name()}'> · updated</span>" if s.get("updated") else "")]
    if s.get("verdict"):
        lines.append(f"<span style='font-size:11pt'>{_esc(s['verdict'])}</span>")
    missed = [c for c in s.get("cooldowns") or [] if not c.get("held") and c.get("counted", 0) > 0]
    if missed:
        lines.append(f"<span style='color:#f0a040'>Missed:</span> " + ", ".join(
            f"{_esc(c['name'])} ×{c['counted']}" for c in sorted(missed, key=lambda c: -c["lost"])))
    stats = [f"<b>{s['dps']:.0f}</b> DPS", f"{n(s['damage'])} dmg"]
    if s.get("healing"):
        stats.append(f"{n(s['healing'])} healed")
    stats.append(f"{n(s['taken'])} taken")
    if s.get("lowest_hp") is not None and s["taken"]:
        low = s["lowest_hp"]
        c = "#f05050" if low < 0.35 else ("#f0a040" if low < 0.6 else theme.TEXT.name())
        stats.append(f"low <span style='color:{c}'>{low:.0%}</span>")
    lines.append(" · ".join(stats))
    g = s.get("group")
    if g and g.get("size", 1) > 1:
        names = ", ".join(g["names"][:3]) + (f" +{len(g['names']) - 3}" if len(g["names"]) > 3 else "")
        if s.get("healing_role"):
            share = f"you: {g['heal_share']:.0%} of the healing ({_ord(g['heal_rank'])} of {g['size']})"
        else:
            share = f"you: {g['damage_share']:.0%} of the damage ({_ord(g['damage_rank'])} of {g['size']})"
        lines.append(f"<span style='color:{theme.DIM.name()}'>With {_esc(names)} · </span>{share}")
    if s.get("best_before") and not any(g.startswith("Beat your best") for g in s.get("good", [])):
        diff = s["dps"] - s["best_before"]
        c = "#50dc78" if diff >= 0 else theme.DIM.name()
        lines.append(f"<span style='color:{theme.DIM.name()}'>Best before: {s['best_before']:.0f} DPS</span> "
                     f"<span style='color:{c}'>({diff:+.0f})</span>")
    for g in s.get("good", [])[:2]:
        lines.append(f"<span style='color:#50dc78'>✔</span> {_esc(g)}")
    for g in [g for g in s.get("improve", []) if spoken(g) != s.get("verdict")][:3]:
        lines.append(f"<span style='color:#f0a040'>▲</span> {_esc(g)}")
    return "<br>".join(lines)


class Overlay(QWidget):
    moved = pyqtSignal(float, float)     # the card's new center, as fractions of the WoW window

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput |
                         Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(WIDTH)
        self.side = "right"
        self.seconds = 12
        self.keep = False          # stay up until the next fight replaces it
        self.spot: tuple[float, float] | None = None   # dragged there (center, fractions of the WoW window)
        self.moving = False
        self._grab: QPoint | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        self.text = QLabel()
        self.text.setTextFormat(Qt.TextFormat.RichText)
        self.text.setWordWrap(True)
        self.text.setStyleSheet(f"background: transparent; color: {theme.TEXT.name()}; font-size: 10pt;")
        lay.addWidget(self.text)
        self.hide_timer = QTimer(self, singleShot=True)
        self.hide_timer.timeout.connect(self._fade_out)
        self.fade = QPropertyAnimation(self, b"windowOpacity", self)
        self.slide = QPropertyAnimation(self, b"pos", self)
        self.slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade.finished.connect(self._faded)
        self._tex: QPixmap | None = None

    def show_fight(self, s: dict):
        self.text.setStyleSheet(f"background: transparent; color: {theme.TEXT.name()}; font-size: 10pt; "
                                f"font-family: \"{theme.FONT}\";")
        self.text.setText(card_html(s))
        self._tex = QPixmap(theme.TEXTURE) if theme.TEXTURE else None
        self.adjustSize()
        end = self._place()
        start = QPoint(end.x() + (40 if self.side == "right" else -40), end.y())
        was_shown = self.isVisible() and self.windowOpacity() > 0.5
        self.fade.stop()
        self.slide.stop()
        if was_shown:
            self.move(end)
        else:
            self.setWindowOpacity(0.0)
            self.move(start)
            self.show()
            self.slide.setDuration(300)
            self.slide.setStartValue(start)
            self.slide.setEndValue(end)
            self.slide.start()
        self.fade.setDuration(250)
        self.fade.setStartValue(self.windowOpacity())
        self.fade.setEndValue(1.0)
        self.fade.start()
        if self.keep or self.moving:
            self.hide_timer.stop()
        else:
            self.hide_timer.start(int(self.seconds * 1000))

    @staticmethod
    def _area() -> QRect:
        area = wow_window()
        if area is None:
            scr = QGuiApplication.primaryScreen()
            area = scr.availableGeometry() if scr else QRect(0, 0, 1920, 1080)
        return area

    def _place(self) -> QPoint:
        """where it was dragged to, else the right (or left) edge of the WoW window at half its height"""
        area = self._area()
        if self.spot:
            x = area.left() + round(self.spot[0] * area.width()) - self.width() // 2
            y = area.top() + round(self.spot[1] * area.height()) - self.height() // 2
            # kept inside the window, whatever size it is now
            return QPoint(max(area.left(), min(x, area.right() - self.width())),
                          max(area.top(), min(y, area.bottom() - self.height())))
        x = area.right() - self.width() - 40 if self.side == "right" else area.left() + 40
        y = area.top() + area.height() // 2 - self.height() // 2
        return QPoint(x, y)

    def set_moving(self, on: bool):
        """let the mouse drag the card (it's click-through otherwise)"""
        self.moving = on
        shown = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, not on)   # re-creates the window, hidden
        self.setCursor(Qt.CursorShape.SizeAllCursor if on else Qt.CursorShape.ArrowCursor)
        if shown:
            self.show()
        self.update()

    def mousePressEvent(self, e):
        if self.moving and e.button() == Qt.MouseButton.LeftButton:
            self._grab = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._grab is not None:
            self.move(e.globalPosition().toPoint() - self._grab)

    def mouseReleaseEvent(self, e):
        if self._grab is None:
            return
        self._grab = None
        area = self._area()

        def spot_now():
            c = self.geometry().center()
            return ((c.x() - area.left()) / max(area.width(), 1), (c.y() - area.top()) / max(area.height(), 1))
        self.spot = spot_now()
        self.move(self._place())         # dropped half off the window: pulled back inside, and saved there
        self.spot = spot_now()
        self.moved.emit(*self.spot)

    def _fade_out(self):
        self.fade.stop()
        self.fade.setDuration(700)
        self.fade.setStartValue(self.windowOpacity())
        self.fade.setEndValue(0.0)
        self.fade.start()

    def _faded(self):
        if self.windowOpacity() <= 0.01:
            self.hide()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        path = QPainterPath()
        path.addRoundedRect(r, 8, 8)
        bg = QColor(theme.PANEL)
        bg.setAlpha(232)
        p.fillPath(path, bg)
        if self._tex is not None and not self._tex.isNull():
            p.save()
            p.setClipPath(path)
            p.drawTiledPixmap(r.toRect(), self._tex)
            p.restore()
        edge = QColor(theme.EDGE)
        edge.setAlpha(200)
        p.setPen(QPen(edge, 1.5))
        p.drawPath(path)
        if self.moving:     # a dashed edge says "drag me"
            p.setPen(QPen(theme.ACCENT, 2, Qt.PenStyle.DashLine))
            p.drawPath(path)
