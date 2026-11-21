"""The after-fight overlay: a short card over the game, at half the height of the WoW window, on its right
(or left) edge. It slides in when a fight is summed up, stays a few seconds and fades out.

It never takes focus or clicks (keys and the mouse stay with the game), and stays on top of WoW's
borderless fullscreen window. (Exclusive fullscreen draws over everything; this needs borderless.)
"""
from __future__ import annotations

import ctypes
import math
import sys

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget

from ..overlay_view import PANEL_ALPHA, CardView, build_card
from . import theme
from .kit import adv, baseline, box, draw_tag, elide, flow, font, line, text_at, wrapped
from .theme import tok

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
        self.view: CardView | None = None
        self.hide_timer = QTimer(self, singleShot=True)
        self.hide_timer.timeout.connect(self._fade_out)
        self.fade = QPropertyAnimation(self, b"windowOpacity", self)
        self.slide = QPropertyAnimation(self, b"pos", self)
        self.slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade.finished.connect(self._faded)
        self._tex: QPixmap | None = None

    def show_fight(self, s: dict):
        self.view = build_card(s)
        self._tex = QPixmap(theme.TEXTURE) if theme.TEXTURE else None
        self.resize(WIDTH, math.ceil(self._card(None)))      # as tall as what it holds
        self.update()
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
        r = QRectF(self.rect())
        bg = tok("panel")
        bg.setAlpha(PANEL_ALPHA)
        p.fillRect(r, bg)
        if self._tex is not None and not self._tex.isNull():
            p.drawTiledPixmap(self.rect(), self._tex)
        box(p, r, tok("tx"))        # square, a 1px tx edge
        if self.moving:     # a dashed edge says "drag me"
            p.setPen(QPen(theme.ACCENT, 2, Qt.PenStyle.DashLine))
            p.drawRect(r.adjusted(1, 1, -1, -1))
        if self.view:
            self._card(p)

    def _card(self, p: QPainter | None) -> float:
        """the card's content (docs/design/mockups/fight-card.html), painted, or measured with p None: the head, the
        figure over its bar and the clean tick, the verdict, the plate band (the biggest gap, or your death), the
        chips and the mark. The mock-up's muted words are tx2: mu reads under 4.5:1 on the see-through panel. No
        Dismiss: the card takes no clicks. Returns its height."""
        v = self.view
        x, w, y = 14, WIDTH - 28, 11
        nf, mf, cf = font(13, 700, num=True, spacing=0.08), font(12), font(12)
        meta = " · ".join(s for s in (v.at, v.length, "updated" if v.updated else "") if s)
        if p:
            tag_w = draw_tag(None, 0, 0, v.kind) + 8 if v.kind else 0
            nw = line(p, nf, tok("tx"), x, y, 16, elide(nf, v.name.upper(), w - tag_w - adv(mf, meta) - 8))
            line(p, mf, tok("tx2"), x + nw + 8, y, 16, meta)
            if v.kind:
                draw_tag(p, x + w - tag_w + 8, y + 8, v.kind, tok("tx2"))
        y += 16 + 6
        bf = font(30, 700, num=True)
        base = baseline(bf, y, 27)
        bw = text_at(p, bf, tok("tx2" if v.big == "–" else "tx"), x, base, v.big)     # "–": nothing to show
        text_at(p, cf, tok("tx2"), x + bw + 8, base, elide(cf, v.caption, w - bw - 8))
        y += 27
        if v.efficiency is not None:        # the bar to the 90% tick, "clean" under it
            y += 5
            if p:
                p.fillRect(QRectF(x, y, w, 10), tok("track"))
                p.fillRect(QRectF(x, y, w * min(1.0, v.efficiency), 10), tok("m-dmg" if v.clean else "m-cd"))
                p.fillRect(QRectF(round(x + w * 0.9), y - 3, 2, 16), tok("tx"))
                tf = font(11, 600, num=True, spacing=0.12)
                line(p, tf, tok("tx2"), x + w * 0.9 - adv(tf, "CLEAN") / 2, y + 15, 11, "CLEAN")
            y += 10 + 5 + 11
        if v.verdict:
            y += 6 + wrapped(p, font(15, 500), tok("tx"), x, y + 6, w, 18, v.verdict)
        if v.gap:
            y += 6
            words, em = v.gap
            gf, ef = font(13), font(13, 600)
            items = [(s, gf, tok("plate-tx")) for s in words.split()] + [(s, ef, tok("plate-ac")) for s in em.split()]
            h = 7 + 11 + 3 + flow(None, items, 0, 0, w - 20, adv(gf, " "), 1) + 7
            if p:
                p.fillRect(QRectF(x, y, w, h), tok("plate"))
                line(p, font(11, 700, num=True, spacing=0.16), tok("plate-mu"), x + 10, y + 7, 11,
                     "DEATH" if v.died else "BIGGEST GAP")
                flow(p, items, x + 10, y + 7 + 11 + 3, w - 20, adv(gf, " "), 1)
            y += h
        if v.chips:
            y += 6
            cx = x
            for chip in v.chips:
                if p:
                    p.fillRect(QRectF(cx, y + 5, 8, 8), tok("m-pace"))
                cx += 14 + line(p, cf, tok("tx2"), cx + 14, y, 17, chip) + 14
            y += 17
        y += 6
        line(p, font(11, 700, num=True, spacing=0.14), tok("tx2"), x, y, 16, "DIPS SCORE")
        return y + 16 + 10
