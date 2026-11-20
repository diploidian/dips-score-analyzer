"""Colors, fonts and the window style: two themes (Timeless, Classical) x two modes (day, night).

The colours come from tokens.py. `apply()` picks a token set and fills the module values below; everything
that paints reads them when it paints, so applying a theme switches the whole look at once (the window then
re-shows what's open so widgets with their own styles pick it up).
"""
import sys
from pathlib import Path

from PyQt6.QtGui import QColor, QFontDatabase

from . import tokens

NAME = "timeless"
MODE = "day"                 # resolved: "day" or "night", never "auto"
T: dict[str, QColor] = {}    # the current token set
TEXTURE: str | None = None   # the dips-Core texture tile (see texture.py), drawn behind every window

FONT = "Barlow"                  # body text
NUM_FONT = "Barlow Condensed"    # numbers and labels
HAND_FONT = "Caveat"             # the handwritten notes
TITLE_FONT = FONT                # titles and names (older pages read this)

FONTS_DIR = Path(__file__).parent / "fonts"
_fonts_loaded = False

# ---- legacy names: filled from T by apply(), so pages not yet redesigned follow the theme ----
ACCENT = BG = PANEL = LANE = GRID = TEXT = DIM = EDGE = SELECT = TITLE = QColor()
COMBAT = BOSS = BUSY = IDLE = CAST = CAST_OK = CAST_BAD = FAIL = KEY = CLICK = QColor()
SPAM = MOVE = HP = HP_LOW = HIT = DEATH = QColor()

def _alpha(c: QColor, a: int) -> QColor:
    c = QColor(c)
    c.setAlpha(a)
    return c


def apply(name: str, mode: str = "auto", os_dark: bool = False) -> None:
    """switch the palette (call app.setStyleSheet(stylesheet()) after)"""
    global NAME, MODE, T
    NAME, m = tokens.normalize(name, mode)
    MODE = tokens.resolve(m, os_dark)
    T = {k: QColor(v) for k, v in tokens.TOKENS[(NAME, MODE)].items()}
    g = globals()
    g.update(ACCENT=tok("gold"), BG=tok("bg"), PANEL=tok("panel"), LANE=tok("track"), GRID=_alpha(T["ln"], 120),
             TEXT=tok("tx"), DIM=tok("mu"), EDGE=tok("ln"), SELECT=tok("track"), TITLE=tok("tx"),
             COMBAT=_alpha(T["plate"], 45), BOSS=_alpha(T["gC"], 70), BUSY=tok("m-dmg"), IDLE=tok("m-surv"),
             CAST=tok("m-cast"), CAST_OK=tok("m-pace"), CAST_BAD=tok("gD"), FAIL=tok("hl-note"), KEY=tok("tx2"),
             CLICK=tok("hl"), SPAM=tok("gD"), MOVE=tok("m-upk"), HP=tok("m-dmg"), HP_LOW=tok("gD"),
             HIT=_alpha(T["gD"], 160), DEATH=tok("gD"))


def _lum(c: QColor) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())


def _contrast(a: QColor, b: QColor) -> float:
    x, y = sorted((_lum(a), _lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def readable(c: QColor, on: QColor | None = None) -> QColor:
    """c darkened (same hue) until it reads at 4.5:1 on `on` (default: panel); unchanged when it already does.
    shortcut: only darkens, so a light-on-dark colour that fails on a night theme is left alone."""
    on = on or T["panel"]
    h, s, l, a = c.getHslF()
    out = QColor(c)
    while _contrast(out, on) < 4.5 and l > 0 and _lum(on) > 0.3:
        l = max(0.0, l - 0.02)
        out.setHslF(max(h, 0.0), s, l, a)
    return out


def tok(key: str) -> QColor:
    return QColor(T[key])


def load_fonts() -> None:
    """register the bundled Barlow / Barlow Condensed / Caveat files (needs a QApplication); once"""
    global _fonts_loaded
    if _fonts_loaded:
        return
    for f in sorted(FONTS_DIR.glob("*.ttf")):
        if QFontDatabase.addApplicationFont(str(f)) < 0:
            print(f"dips score: couldn't load font {f.name}", file=sys.stderr)
    _fonts_loaded = True


def grade_color(grade: str) -> QColor:
    return tok({"S": "gS", "A": "gA", "B": "gB", "C": "gC"}.get(grade, "gD"))


def score_color(s: float) -> QColor:
    return tok("gS" if s >= 85 else "gB" if s >= 65 else "gC" if s >= 45 else "gD")


def _c(c: QColor) -> str:
    return f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha()})"


def set_texture(path: str | None):
    global TEXTURE
    TEXTURE = path


def panel() -> str:
    """panel color: a little see-through when the texture is on, so it shows behind panels too"""
    return _c(_alpha(PANEL, 205)) if TEXTURE else PANEL.name()


def stylesheet() -> str:
    """the whole window's style for the theme in use: flat and square, 1px lines"""
    # windows carry the background (and the texture); everything inside is see-through unless it's a panel
    tex = f"background-image: url({TEXTURE}); background-repeat: repeat-xy;" if TEXTURE else ""
    pnl = panel()
    ln, tx, mu, hl = T["ln"].name(), T["tx"].name(), T["mu"].name(), T["hl"].name()
    btn_ln = ln if tokens.TOKENS[(NAME, MODE)]["btn-ln"] == "transparent" else T["btn-ln"].name()
    return f"""
QWidget {{ background: transparent; color: {tx}; font-family: "{FONT}"; font-size: 10pt; }}
QMainWindow, QDialog {{ background-color: {T["bg"].name()}; {tex} }}
QComboBox QAbstractItemView, QComboBoxPrivateContainer, QMenu {{ background: {T["panel"].name()};
    border: 1px solid {ln}; selection-background-color: {T["track"].name()}; selection-color: {tx}; }}
QListWidget, QTableWidget, QTreeWidget {{ background: {pnl}; border: 1px solid {ln}; outline: 0; }}
QTableWidget {{ gridline-color: {ln}; }}
QListWidget::item:selected, QTableWidget::item:selected, QTreeWidget::item:selected {{
    background: {T["track"].name()}; color: {tx}; }}
QTreeWidget::item {{ padding: 4px 2px; }}
QHeaderView::section {{ background: {pnl}; color: {mu}; border: 0; border-bottom: 1px solid {ln};
    padding: 4px 6px; }}
QLabel#dim {{ color: {mu}; }}
QLabel#title {{ font-size: 15pt; font-weight: 600; color: {tx}; }}
#rail {{ background: {T["rail"].name()}; color: {T["rail-tx"].name()}; }}
#rail QLabel {{ color: {T["rail-tx"].name()}; }}
#rail QLabel#dim {{ color: {T["rail-mu"].name()}; }}
#rail QLabel#look {{ color: {T["rail-mu"].name()}; font-family: "{NUM_FONT}"; font-size: 11px; font-weight: 600; }}
#rail QPushButton {{ background: {T["rail"].name()}; color: {T["rail-tx"].name()};
    border: 1px solid {T["rail-mu"].name()}; padding: 5px 10px; font-weight: 500; }}
#rail QPushButton:hover {{ background: {T["rail-on"].name()}; }}
#rail QPushButton:checked {{ background: {T["rail-on"].name()}; border: 1px solid {T["rail-tx"].name()};
    font-weight: 600; }}
#rail QPushButton[seg="1"] {{ border-right-width: 0; }}
#rail QPushButton[seg="1"][last="1"] {{ border-right-width: 1px; }}
#rail QPushButton[seg="1"]:checked {{ border-right-width: 1px; }}
#rail QToolButton {{ background: {T["rail"].name()}; color: {T["rail-tx"].name()};
    border: 1px solid {T["rail-mu"].name()}; font-size: 14pt; padding: 1px 8px; }}
#rail QToolButton:hover {{ background: {T["rail-on"].name()}; }}
QSplitter::handle {{ background: {ln}; }}
QScrollBar:vertical {{ background: {T["panel"].name()}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {ln}; min-height: 20px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollArea {{ border: 0; }}
QComboBox {{ background: {T["panel"].name()}; border: 1px solid {ln}; padding: 2px 6px; }}
QTabWidget::pane {{ border: 1px solid {ln}; top: -1px; background: {pnl}; }}
QTabBar::tab {{ background: {pnl}; color: {mu}; padding: 6px 16px; border: 1px solid {ln};
    border-bottom: 0; margin-right: 2px; }}
QTabBar::tab:selected {{ color: {tx}; border: 1px solid {tx}; font-weight: 600; }}
QGroupBox {{ border: 1px solid {ln}; margin-top: 10px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; color: {tx}; }}
QSlider::groove:horizontal {{ background: {ln}; height: 4px; }}
QSlider::handle:horizontal {{ background: {hl}; width: 12px; margin: -4px 0; }}
QRadioButton::indicator {{ width: 12px; height: 12px; border: 1px solid {mu}; border-radius: 7px;
    background: {T["panel"].name()}; }}
QRadioButton::indicator:checked {{ border: 1px solid {hl}; background: {hl}; }}
QPushButton, QToolButton {{ background: {T["btn"].name()}; color: {T["btn-tx"].name()};
    border: 1px solid {btn_ln}; padding: 5px 12px; }}
QPushButton:hover, QToolButton:hover {{ border-color: {hl}; }}
QPushButton:checked {{ border-color: {hl}; }}
QPushButton#showme {{ border-color: {T["plate-ln"].name()}; font-size: 13px; font-weight: 600; padding: 10px 16px; }}
QToolTip {{ background: {T["panel"].name()}; color: {tx}; border: 1px solid {ln}; padding: 4px; }}
QLineEdit, QSpinBox {{ background: {T["panel"].name()}; border: 1px solid {ln}; selection-background-color: {hl};
    selection-color: {T["bg"].name()}; }}
"""


apply("timeless", "day")
