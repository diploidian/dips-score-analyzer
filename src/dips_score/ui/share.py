"""Share a page: the whole of it, scrolled-off part too, as a picture on the clipboard and in a PNG file."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication, QScrollArea, QWidget

from .theme import tok


def page_widget(w: QWidget) -> QWidget:
    """the painted page inside a tab: a scroll area's widget (the tab's, or the first one it holds), else the tab"""
    scroll = w if isinstance(w, QScrollArea) else w.findChild(QScrollArea)
    return scroll.widget() if scroll and scroll.widget() else w


def snapshot(w: QWidget) -> QImage:
    """w drawn whole on the theme's ground (with the dips-Core texture on, pages don't paint their own)"""
    # shortcut: the texture isn't in the picture, only the flat ground; draw it here if friends miss it
    pm = w.grab()
    img = QImage(pm.size(), QImage.Format.Format_ARGB32)
    img.setDevicePixelRatio(pm.devicePixelRatio())
    img.fill(tok("bg"))
    p = QPainter(img)
    p.drawPixmap(0, 0, pm)
    p.end()
    return img


def share(w: QWidget, folder: Path, name: str) -> Path:
    """the page on the clipboard and saved as folder/<name>-<yyyymmdd-HHMMSS>.png"""
    # shortcut: the picture is as wide as the window is now, and lists that scroll inside a page (the Debrief's
    # fight grid past 8 rows, the Pulls drawer) show only their visible rows; render them whole if that matters
    img = snapshot(page_widget(w))
    QApplication.clipboard().setImage(img)
    folder.mkdir(parents=True, exist_ok=True)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip(" .") or "dips-score"   # what Windows refuses
    path = folder / f"{name}-{datetime.now():%Y%m%d-%H%M%S}.png"
    if not img.save(str(path)):
        raise OSError(f"couldn't write {path}")
    return path
