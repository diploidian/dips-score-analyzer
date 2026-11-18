"""Game art, when you've extracted it (see assets/README.txt).

The app looks in two folders, every file in any sub-folder, and knows the files by their in-game names
(the folder layout doesn't matter):
    <project>/assets                 next to dips-score.pyw
    %APPDATA%/dips-score/assets

    font            frizqt__.ttf (Friz Quadrata)
    class icons     classicon_<class>.blp/png          (classicon_priest)
    raid markers    ui-raidtargetingicon_1 .. _8       (1 Star ... 8 Skull)
    frames          ui-dialogbox-border, ui-tooltip-border (edge strips: rebuilt into stretchable frames)
    spell icons     the icon files (inventory and spell icons), plus SpellMisc.csv and a listfile (.csv or
                    .txt, "fileDataID;path") to tell which icon a spell uses

.blp files are read with Pillow. Anything missing is simply not used: the drawn look stays.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase, QIcon, QImage, QPainter, QPixmap

PROJECT = Path(__file__).resolve().parents[3]
EXTS = {".png", ".tga", ".blp", ".jpg", ".jpeg", ".ttf", ".otf", ".csv", ".txt"}
MARKER_INDEX = {"Star": 1, "Circle": 2, "Diamond": 3, "Triangle": 4, "Moon": 5, "Square": 6, "Cross": 7, "Skull": 8}

_index: dict[str, Path] | None = None
_pix: dict[str, QPixmap | None] = {}
_font: str | None | bool = False       # False: not looked for yet
_spells: dict[int, str] | None = None


def folders() -> list[Path]:
    out = [PROJECT / "assets"]
    if os.environ.get("APPDATA"):
        out.append(Path(os.environ["APPDATA"]) / "dips-score" / "assets")
    return out


def cache_dir() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home()) / "dips-score" / "cache"
    base.mkdir(parents=True, exist_ok=True)
    return base


def rescan():
    """forget what was found (after you add files)"""
    global _index, _font, _spells
    _index, _font, _spells = None, False, None
    _pix.clear()
    for old in cache_dir().glob("*.png"):   # rebuilt frames and converted icons: made again from the new files
        try:
            old.unlink()
        except OSError:
            pass


def index() -> dict[str, Path]:
    """lower-case file name without extension -> file (first found wins; .png before .blp)"""
    global _index
    if _index is None:
        _index = {}
        for root in folders():
            if not root.is_dir():
                continue
            for p in sorted(root.rglob("*"), key=lambda p: p.suffix.lower() != ".png"):
                if p.suffix.lower() in EXTS and p.is_file():
                    _index.setdefault(p.stem.lower(), p)
    return _index


def find(name: str) -> Path | None:
    return index().get(name.lower())


def _load(path: Path) -> QImage | None:
    if path.suffix.lower() in (".png", ".jpg", ".jpeg"):
        img = QImage(str(path))
        return None if img.isNull() else img
    try:                                   # .blp and .tga: through Pillow
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGBA")
            data = im.tobytes("raw", "RGBA")
            return QImage(data, im.width, im.height, im.width * 4, QImage.Format.Format_RGBA8888).copy()
    except Exception:
        return None


def pixmap(name: str) -> QPixmap | None:
    key = name.lower()
    if key not in _pix:
        path = find(key)
        img = _load(path) if path else None
        _pix[key] = QPixmap.fromImage(img) if img is not None else None
    return _pix[key]


def png_path(name: str) -> str | None:
    """a .png file for it (converted into the cache if needed), for rich-text tooltips"""
    path = find(name)
    if not path:
        return None
    if path.suffix.lower() == ".png":
        return path.as_posix()
    out = cache_dir() / f"{path.stem.lower()}.png"
    if not out.exists():
        pm = pixmap(name)
        if pm is None:
            return None
        pm.save(str(out), "PNG")
    return out.as_posix()


def icon(name: str) -> QIcon | None:
    pm = pixmap(name)
    return QIcon(pm) if pm is not None else None


# ---------------------------------------------------------------------------- specific art
def class_icon_name(cls: str | None) -> str | None:
    return f"classicon_{cls.lower()}" if cls else None


def class_pixmap(cls: str | None) -> QPixmap | None:
    n = class_icon_name(cls)
    return pixmap(n) if n else None


def marker_name(marker: str | None) -> str | None:
    return f"ui-raidtargetingicon_{MARKER_INDEX[marker]}" if marker in MARKER_INDEX else None


def marker_pixmap(marker: str | None) -> QPixmap | None:
    n = marker_name(marker)
    return pixmap(n) if n else None


def font_family() -> str | None:
    """Friz Quadrata's family name, loaded from the assets folder (once)"""
    global _font
    if _font is False:
        _font = None
        path = find("frizqt__")
        if path and path.suffix.lower() in (".ttf", ".otf"):
            fid = QFontDatabase.addApplicationFont(str(path))
            fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
            _font = fams[0] if fams else None
    return _font or None


def nine_patch(name: str) -> str | None:
    """A frame image the window style can stretch, built from the game's backdrop edge strip.

    A backdrop edge file is 8 square pieces in a row: left, right, top, bottom, top-left, top-right,
    bottom-left, bottom-right (the top and bottom pieces stored turned on their side). Rebuilt here into a
    3x3 frame with an empty middle."""
    src = pixmap(name)
    if src is None or src.height() == 0 or src.width() < src.height() * 8:
        return None
    out = cache_dir() / f"{name.lower()}-9.png"
    if out.exists():
        return out.as_posix()
    s = src.height()
    piece = lambda i: src.copy(i * s, 0, s, s)  # noqa: E731
    img = QPixmap(s * 3, s * 3)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.drawPixmap(0, s, piece(0))                       # left
    p.drawPixmap(2 * s, s, piece(1))                   # right
    from PyQt6.QtGui import QTransform
    turn = QTransform().rotate(90)
    p.drawPixmap(s, 0, piece(2).transformed(turn))     # top
    p.drawPixmap(s, 2 * s, piece(3).transformed(turn))  # bottom
    p.drawPixmap(0, 0, piece(4))
    p.drawPixmap(2 * s, 0, piece(5))
    p.drawPixmap(0, 2 * s, piece(6))
    p.drawPixmap(2 * s, 2 * s, piece(7))
    p.end()
    img.save(str(out), "PNG")
    return out.as_posix()


# ---------------------------------------------------------------------------- spell icons
def _spell_map() -> dict[int, str]:
    """spell id -> icon file name, from SpellMisc.csv (spell -> icon file id) and a listfile (id -> path)"""
    global _spells
    if _spells is not None:
        return _spells
    _spells = {}
    misc = find("spellmisc")
    lists = [p for k, p in index().items() if "listfile" in k]
    if not misc or not lists:
        return _spells
    paths: dict[int, str] = {}
    for lf in lists:
        try:
            with open(lf, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    fid, _, path = line.strip().partition(";")
                    if fid.isdigit() and path.lower().startswith("interface/icons/"):
                        paths[int(fid)] = Path(path).stem.lower()
        except OSError:
            continue
    try:
        with open(misc, encoding="utf-8", errors="replace", newline="") as fh:
            rows = csv.reader(fh)
            head = [h.strip().lower() for h in next(rows)]
            sid = next(i for i, h in enumerate(head) if h == "spellid")
            ico = next(i for i, h in enumerate(head) if "spelliconfiledataid" in h)
            for row in rows:
                try:
                    f = int(row[ico])
                    if f in paths:
                        _spells[int(row[sid])] = paths[f]
                except (ValueError, IndexError):
                    continue
    except (OSError, StopIteration):
        pass
    return _spells


def spell_icon_name(spell_id: int | None) -> str | None:
    if spell_id is None:
        return None
    name = _spell_map().get(spell_id)
    return name if name and find(name) else None


def spell_pixmap(spell_id: int | None) -> QPixmap | None:
    n = spell_icon_name(spell_id)
    return pixmap(n) if n else None


# ---------------------------------------------------------------------------- what was found
def report() -> list[tuple[str, str, bool]]:
    """(what, detail, found) for the settings window"""
    from ..model.roster import CLASSES
    classes = sum(1 for c in CLASSES if class_pixmap(c) is not None)
    markers = sum(1 for m in MARKER_INDEX if marker_pixmap(m) is not None)
    spells = len(_spell_map())
    return [
        ("Game font (Friz Quadrata)", "frizqt__.ttf", font_family() is not None),
        ("Class icons", f"{classes} of {len(CLASSES)}", classes > 0),
        ("Raid marker icons", f"{markers} of 8", markers > 0),
        ("Dialog frame", "ui-dialogbox-border", nine_patch("ui-dialogbox-border") is not None),
        ("Tooltip frame", "ui-tooltip-border", nine_patch("ui-tooltip-border") is not None),
        ("Spell icons", f"{spells:,} spells mapped" if spells else "needs SpellMisc.csv + a listfile", spells > 0),
    ]
