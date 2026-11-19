"""The Habits page: what you keep doing right or wrong across many fights, and the pace of this session."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from . import theme
from .fightsview import StatBox
from .overlay import _esc
from .pages import dim_label

EDGE = {"keep": "#50dc78", "fix": "#f0a040", "build": "#5aa0f0"}


def _fmt(v, spec: str = ".0f", unit: str = "") -> str:
    return "-" if v is None else f"{v:{spec}}{unit}"


class HabitsPage(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.scroll)
        self.show_habits({"cards": [], "session": None, "fights": 0})

    def show_habits(self, h: dict):
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(12, 10, 16, 16)
        self.scroll.setWidget(body)
        if not h.get("fights"):
            lay.addWidget(dim_label("Fights appear here once you have some."))
            lay.addStretch(1)
            return
        c = h.get("char")
        if c:    # "Mapomimi, level 33 Undead Priest, Shadow, gear 31"
            kind = " ".join(x.title() for x in (c.get("race"), c.get("class")) if x)
            who = ", ".join([h["name"], " ".join(x for x in (f"level {c['level']}" if c.get("level") else "", kind) if x)]
                            + [x for x in (c.get("spec"), f"gear {c['gear']}" if c.get("gear") else "") if x])
        else:
            who = h["name"] + (f", level {h['level']}" if h.get("level") else "")
        head = QLabel(f"<span style='font-family:\"{theme.TITLE_FONT}\"; font-size:17pt; font-weight:700; "
                      f"color:{theme.TITLE.name()}'>{_esc(who)}</span> "
                      f"<span style='color:{theme.DIM.name()}'>last {h['fights']} fights</span>")
        lay.addWidget(head)
        s = h.get("session")
        if s:
            row = QHBoxLayout()
            stats = [(str(s["fights"]), "Fights"), (str(s["kills"]), "Kills"),
                     (_fmt(s["kills_per_hour"]), "Kills / hour"), (_fmt(s["avg_gap"], ".0f", " s"), "Avg gap"),
                     (_fmt(s["avg_rest"], ".0f", " s"), "Avg rest"),
                     (_fmt(s["avg_start_hp"] and s["avg_start_hp"] * 100, ".0f", "%"), "Start health"),
                     (_fmt(s["avg_start_mana"] and s["avg_start_mana"] * 100, ".0f", "%"), "Start mana")]
            for v, label in stats:
                row.addWidget(StatBox(v, label))
            row.addStretch(1)
            lay.addLayout(row)
        for c in h["cards"]:
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background: {theme.panel()}; border: 1px solid {theme.EDGE.name()}; "
                               f"border-left: 4px solid {EDGE[c['kind']]}; border-radius: 6px; }} "
                               f"QLabel {{ background: transparent; border: 0; }}")
            cl = QVBoxLayout(card)
            title = QLabel(f"<b>{_esc(c['title'])}</b>")
            title.setWordWrap(True)
            cl.addWidget(title)
            detail = dim_label(c["detail"])
            detail.setWordWrap(True)
            detail.setTextFormat(Qt.TextFormat.PlainText)
            cl.addWidget(detail)
            lay.addWidget(card)
        lay.addStretch(1)
