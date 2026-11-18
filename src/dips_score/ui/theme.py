"""Colors, fonts and the window style, in two themes:

    classic   flat and dark, with the dips accent (the original look)
    wow       "Azeroth": dark stone and leather, gold-bronze frames, gold titles, game-style tooltips and
              buttons. Uses the game's own font and frame art when they're in the assets folder (see
              assets.py), and draws a look-alike when they aren't.

Everything that paints reads these module values when it paints, so `apply()` switches the theme at once
(the window then re-shows what's open so widgets with their own styles pick it up).
"""
from PyQt6.QtGui import QColor

NAME = "classic"
TEXTURE: str | None = None   # the dips-Core texture tile (see texture.py), drawn behind every window
FONT = "Segoe UI"          # body text
TITLE_FONT = "Segoe UI"    # titles and names

# ---- palette (replaced by apply) ----
ACCENT = QColor(64, 153, 255)
BG = QColor(14, 14, 18)
PANEL = QColor(22, 22, 28)
LANE = QColor(28, 28, 35)
GRID = QColor(255, 255, 255, 18)
TEXT = QColor(234, 234, 240)
DIM = QColor(150, 150, 160)
EDGE = QColor(42, 42, 51)          # panel borders
SELECT = QColor(29, 53, 80)        # selected rows
TITLE = QColor(255, 255, 255)      # titles

# ---- meaning colors (the same in both themes) ----
COMBAT = QColor(64, 153, 255, 50)
BOSS = QColor(200, 120, 255, 70)
BUSY = QColor(80, 200, 120)
IDLE = QColor(240, 80, 80)
CAST = QColor(64, 153, 255)
CAST_OK = QColor(120, 190, 255)
CAST_BAD = QColor(240, 80, 80)
FAIL = QColor(255, 170, 60)
KEY = QColor(220, 220, 230)
CLICK = QColor(255, 150, 50)
SPAM = QColor(240, 80, 80)
MOVE = QColor(250, 210, 80)
HP = QColor(80, 220, 120)
HP_LOW = QColor(240, 80, 80)
HIT = QColor(240, 80, 80, 160)
DEATH = QColor(255, 60, 60)

PALETTES = {
    "classic": dict(ACCENT=QColor(64, 153, 255), BG=QColor(14, 14, 18), PANEL=QColor(22, 22, 28),
                    LANE=QColor(28, 28, 35), GRID=QColor(255, 255, 255, 18), TEXT=QColor(234, 234, 240),
                    DIM=QColor(150, 150, 160), EDGE=QColor(42, 42, 51), SELECT=QColor(29, 53, 80),
                    TITLE=QColor(255, 255, 255), COMBAT=QColor(64, 153, 255, 50)),
    # the game's own UI colors: gold text (1, 0.82, 0), parchment-white body text, bronze frames
    "wow": dict(ACCENT=QColor(255, 209, 0), BG=QColor(12, 10, 8), PANEL=QColor(24, 19, 14),
                LANE=QColor(31, 25, 19), GRID=QColor(255, 209, 0, 16), TEXT=QColor(240, 230, 210),
                DIM=QColor(168, 151, 122), EDGE=QColor(122, 94, 52), SELECT=QColor(74, 52, 18),
                TITLE=QColor(255, 209, 0), COMBAT=QColor(255, 196, 80, 45)),
}
THEMES = {"classic": "Classic (flat dark)", "wow": "Azeroth (World of Warcraft style)"}


def apply(name: str):
    """switch the palette and fonts (call app.setStyleSheet(stylesheet()) after)"""
    global NAME, FONT, TITLE_FONT
    from . import assets
    NAME = name if name in PALETTES else "classic"
    g = globals()
    for k, v in PALETTES[NAME].items():
        g[k] = QColor(v)
    if NAME == "wow":
        game = assets.font_family()          # Friz Quadrata, if it's in the assets folder
        FONT = game or "Segoe UI"
        TITLE_FONT = game or "Palatino Linotype"
    else:
        FONT = TITLE_FONT = "Segoe UI"


def grade_color(grade: str) -> QColor:
    return {"S": QColor(255, 200, 60), "A": QColor(80, 220, 120), "B": QColor(64, 153, 255),
            "C": QColor(200, 200, 210), "D": QColor(255, 150, 50)}.get(grade, QColor(240, 80, 80))


def score_color(s: float) -> QColor:
    if s >= 85:
        return QColor(80, 220, 120)
    if s >= 65:
        return QColor(64, 153, 255)
    if s >= 45:
        return QColor(255, 170, 60)
    return QColor(240, 80, 80)


def _c(c: QColor) -> str:
    return f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha()})"


def set_texture(path: str | None):
    global TEXTURE
    TEXTURE = path


def panel() -> str:
    """panel color: a little see-through when the texture is on, so it shows behind panels too"""
    return _c(QColor(PANEL.red(), PANEL.green(), PANEL.blue(), 205)) if TEXTURE else PANEL.name()


def stylesheet() -> str:
    """the whole window's style for the theme in use"""
    # windows carry the background (and the texture); everything inside is see-through unless it's a panel
    tex = f"background-image: url({TEXTURE}); background-repeat: repeat-xy;" if TEXTURE else ""
    pnl = panel()
    base = f"""
QWidget {{ background: transparent; color: {TEXT.name()}; font-family: "{FONT}"; font-size: 10pt; }}
QMainWindow, QDialog {{ background-color: {BG.name()}; {tex} }}
QComboBox QAbstractItemView, QComboBoxPrivateContainer, QMenu {{ background: {PANEL.name()};
    selection-background-color: {SELECT.name()}; }}
QListWidget, QTableWidget, QTreeWidget {{ background: {pnl}; border: 1px solid {EDGE.name()}; outline: 0; }}
QTableWidget {{ gridline-color: {_c(QColor(EDGE.red(), EDGE.green(), EDGE.blue(), 90))}; }}
QListWidget::item:selected, QTableWidget::item:selected, QTreeWidget::item:selected {{
    background: {SELECT.name()}; color: white; }}
QTreeWidget::item {{ padding: 4px 2px; }}
QHeaderView::section {{ background: {pnl}; color: {DIM.name()}; border: 0;
    border-bottom: 1px solid {EDGE.name()}; padding: 4px 6px; }}
QLabel#dim {{ color: {DIM.name()}; }}
QLabel#title {{ font-family: "{TITLE_FONT}"; font-size: 15pt; font-weight: 600; color: {TITLE.name()}; }}
QSplitter::handle {{ background: {PANEL.darker(130).name()}; }}
QScrollBar:vertical {{ background: {PANEL.name()}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {EDGE.name()}; min-height: 20px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollArea {{ border: 0; }}
QComboBox {{ background: {PANEL.lighter(130).name()}; border: 1px solid {EDGE.name()}; padding: 2px 6px; }}
QTabBar::tab {{ background: {pnl}; color: {DIM.name()}; padding: 6px 16px; border: 1px solid {EDGE.name()};
    border-bottom: 0; margin-right: 2px; }}
QTabBar::tab:selected {{ color: {TITLE.name()}; border-top: 2px solid {ACCENT.name()}; }}
QGroupBox {{ border: 1px solid {EDGE.name()}; margin-top: 10px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; color: {TITLE.name()}; }}
QSlider::handle:horizontal {{ background: {ACCENT.name()}; width: 12px; margin: -4px 0; border-radius: 6px; }}
QRadioButton::indicator {{ width: 12px; height: 12px; border: 1px solid {DIM.name()}; border-radius: 7px;
    background: {PANEL.name()}; }}
QRadioButton::indicator:checked {{ border: 1px solid {ACCENT.name()};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 {ACCENT.name()},
    stop:0.55 {ACCENT.name()}, stop:0.65 {PANEL.name()}); }}
QSlider::groove:horizontal {{ background: {EDGE.name()}; height: 4px; }}
"""
    if NAME == "classic":
        return base + f"""
QTabWidget::pane {{ border: 1px solid {EDGE.name()}; top: -1px; background: {pnl}; }}
QPushButton, QToolButton {{ background: #23232c; border: 1px solid #33333d; padding: 5px 12px; }}
QPushButton:hover, QToolButton:hover {{ border-color: {ACCENT.name()}; }}
QPushButton:checked {{ border-color: {ACCENT.name()}; }}
QToolTip {{ background: #1b1b22; color: {TEXT.name()}; border: 1px solid #3a3a45; padding: 4px; }}
"""
    from . import assets
    frame = assets.nine_patch("ui-dialogbox-border")       # the game's dialog frame, if extracted
    tip = assets.nine_patch("ui-tooltip-border")
    pane = (f"border: 12px solid transparent; border-image: url({frame}) 12 12 12 12 stretch stretch;"
            if frame else f"border: 2px ridge {EDGE.name()};")
    tooltip = (f"border: 6px solid transparent; border-image: url({tip}) 6 6 6 6 stretch stretch;"
               if tip else "border: 2px solid #6a7894; border-radius: 4px;")
    return base + f"""
QTabWidget::pane {{ {pane} background: {pnl}; top: -1px; }}
QTabBar::tab {{ font-family: "{TITLE_FONT}"; background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #2b2117, stop:1 #17120c);
    color: {DIM.name()}; border: 1px solid {EDGE.name()}; border-bottom: 0; border-top-left-radius: 4px;
    border-top-right-radius: 4px; }}
QTabBar::tab:selected {{ color: {TITLE.name()}; background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #4a3518,
    stop:1 #241a0e); border: 1px solid {ACCENT.darker(140).name()}; border-bottom: 0; }}
QTreeWidget, QTableWidget {{ border: 2px ridge {EDGE.name()}; }}
QHeaderView::section {{ font-family: "{TITLE_FONT}"; color: {TITLE.name()};
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #2a2015, stop:1 #1a140d); }}
QPushButton, QToolButton {{ font-family: "{TITLE_FONT}"; color: {TITLE.name()}; padding: 5px 14px;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #7a1410, stop:0.5 #520c08, stop:1 #330604);
    border: 1px solid #b08a3e; border-radius: 3px; }}
QPushButton:hover, QToolButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #9a2018,
    stop:0.5 #6a120c, stop:1 #400806); border-color: {ACCENT.name()}; }}
QPushButton:pressed, QPushButton:checked {{ background: #2a0503; }}
QComboBox {{ background: #1e1710; border: 1px solid #8a6d3b; border-radius: 2px; }}
QToolTip {{ background: rgba(6, 8, 20, 240); color: {TEXT.name()}; padding: 6px; {tooltip} }}
QScrollBar::handle:vertical {{ background: #6a5230; border-radius: 4px; }}
"""
