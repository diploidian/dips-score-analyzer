"""The Fights page: every fight summed up after it ended (open world and dungeons), newest first, and one
fight in detail."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QScrollArea,
                             QVBoxLayout, QWidget)

from . import theme
from .overlay import KIND_COLOR, _esc
from .pages import dim_label, item, table


def _n(v) -> str:
    return f"{v:,.0f}"


def _dur(s: float) -> str:
    return f"{int(s // 60)}:{int(s % 60):02d}"


def chip(kind: str) -> str:
    return (f"<span style='background:{KIND_COLOR.get(kind, '#444')}; color:white; font-size:8pt; font-weight:600'>"
            f"&nbsp;{kind}&nbsp;</span>")


class FightList(QListWidget):
    picked = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.fights: list[dict] = []
        self.currentRowChanged.connect(self._row)

    def set_fights(self, fights: list[dict]):
        keep = self.currentRow()
        self.fights = list(reversed(fights))            # newest first
        self.blockSignals(True)
        self.clear()
        for f in self.fights:
            self._add(f)
        self.blockSignals(False)
        if self.fights:
            self.setCurrentRow(max(0, keep))
            self._row(self.currentRow())

    def add_fight(self, f: dict):
        """a new fight on top (or an updated one in place); follows it if you were looking at the newest"""
        for i, old in enumerate(self.fights):
            if old.get("id") == f.get("id"):
                self.fights[i] = f
                it = self.item(i)
                self.removeItemWidget(it)
                self.takeItem(i)
                self._add(f, i)
                self.setCurrentRow(i)
                self._row(i)
                return
        at_top = self.currentRow() <= 0
        self.fights.insert(0, f)
        self._add(f, 0)
        if at_top:
            self.setCurrentRow(0)
        else:
            self.setCurrentRow(self.currentRow() + 1)

    def _add(self, f: dict, row: int | None = None):
        it = QListWidgetItem()
        lbl = QLabel(f"{chip(f['kind'])}&nbsp; <b>{_esc(f['target'])}</b>"
                     + (f" <span style='color:{theme.DIM.name()}'>+{f['more']}</span>" if f.get("more") else "")
                     + f"<br><span style='color:{theme.DIM.name()}'>{f['dps']:.0f} DPS · "
                     f"{f.get('efficiency', 1):.0%} · {_dur(f['duration'])}"
                     + (" · <span style='color:#f05050'>died</span>" if f.get("result") == "you died" else "")
                     + "</span>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setContentsMargins(6, 4, 6, 4)
        lbl.setStyleSheet("background: transparent;")
        it.setSizeHint(lbl.sizeHint())
        if row is None:
            self.addItem(it)
        else:
            self.insertItem(row, it)
        self.setItemWidget(it, lbl)

    def _row(self, row: int):
        if 0 <= row < len(self.fights):
            self.picked.emit(self.fights[row])


class StatBox(QFrame):
    def __init__(self, value: str, label: str):
        super().__init__()
        self.setStyleSheet(f"StatBox {{ background: {theme.panel()}; border: 1px solid {theme.EDGE.name()}; "
                           f"border-radius: 6px; }} QLabel {{ background: transparent; border: 0; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        v = QLabel(value)
        v.setStyleSheet(f"font-size: 22pt; font-weight: 700; color: {theme.TITLE.name()};")
        lay.addWidget(v)
        lay.addWidget(dim_label(label))
        self.setMinimumWidth(130)


class FightDetail(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.scroll)
        self.body: QWidget | None = None
        self.show_fight(None)

    def _section(self, lay, title: str):
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(f"color: {theme.ACCENT.name()}; font-weight: 700; letter-spacing: 1px; margin-top: 10px;")
        lay.addWidget(lbl)

    def _table(self, lay, headers: list[str], rows: list[list], right_from: int = 1):
        t = table(headers, stretch=0)
        t.setSelectionMode(t.SelectionMode.NoSelection)
        for r in rows:
            i = t.rowCount()
            t.insertRow(i)
            for c, v in enumerate(r):
                t.setItem(i, c, item(v, align_right=c >= right_from))
        t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        t.setFixedHeight(t.horizontalHeader().height() + 4 + sum(t.rowHeight(i) for i in range(t.rowCount())))
        lay.addWidget(t)

    def show_fight(self, f: dict | None):
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(12, 10, 16, 16)
        self.scroll.setWidget(body)
        self.body = body
        if not f:
            lay.addWidget(dim_label("No fights yet. Turn on the combat log in game (/combatlog) and fight something: "
                                    "each fight shows up here (and on the overlay) a few seconds after it ends."))
            lay.addStretch(1)
            return
        when = datetime.fromisoformat(f["start"])
        head = QLabel(f"{chip(f['kind'])}&nbsp; <span style='font-family:\"{theme.TITLE_FONT}\"; font-size:17pt; "
                      f"font-weight:700; color:{theme.TITLE.name()}'>{_esc(f['target'])}</span>"
                      + (f" <span style='color:{theme.DIM.name()}'>+{f['more']} more</span>" if f.get("more") else ""))
        head.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(head)
        lay.addWidget(dim_label(f"{when:%a %d %b %H:%M:%S} · {f.get('zone') or '?'} · {f['result']}"))
        if f.get("verdict"):
            v = QLabel(f"<span style='font-size:13pt'>{_esc(f['verdict'])}</span>")
            v.setTextFormat(Qt.TextFormat.RichText)
            lay.addWidget(v)
        boxes = QGridLayout()
        boxes.setSpacing(10)
        stats = [(_dur(f["duration"]), "Duration"), (_n(f["damage"]), "Damage"), (f"{f['dps']:.0f}", "DPS"),
                 (_n(f["taken"]), "Taken"), (_n(f["healing"]), "Healing")]
        for i, (v, label) in enumerate(stats):
            boxes.addWidget(StatBox(v, label), 0, i)
        boxes.setColumnStretch(len(stats), 1)
        lay.addLayout(boxes)
        left = (f.get("potential") or f["damage"]) - f["damage"]
        if f.get("healing_role"):
            lbl = QLabel(f"<span style='font-size:13pt'>Mostly healing this fight</span> "
                         f"<span style='color:{theme.DIM.name()}'>(damage you didn't do isn't counted)</span>")
        elif left >= 1:
            lbl = QLabel(f"<span style='font-size:13pt'>Damage left on the table: about {_n(left)}</span> "
                         f"<span style='color:{theme.DIM.name()}'>estimate - only time you were free to act</span>")
        else:
            lbl = QLabel("<span style='font-size:13pt'>Nothing left on the table</span>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setToolTip("Cooldowns that sat ready while you were free (not moving for cast-time spells, not out of "
                       "mana, not stunned, the target not nearly dead, nobody low while you heal), melee swings "
                       "lost while not casting, and idle time while standing with resource to spare (half counted).")
        lay.addWidget(lbl)
        g = f.get("group")
        if g and g.get("size", 1) > 1:
            self._section(lay, "Group")
            rows = [[m["name"], _n(m["damage"]), _n(m["healing"])] for m in g["members"]]
            rows.insert(0, ["You", _n(f["damage"]), _n(f["healing"])])
            self._table(lay, ["Player", "Damage", "Healing"], sorted(rows, key=lambda r: -float(r[1].replace(",", ""))))
            line = (f"You did {g['damage_share']:.0%} of the damage ({g['damage_rank']} of {g['size']}) and "
                    f"{g['heal_share']:.0%} of the healing.")
            if g.get("deaths"):
                line += " Died: " + ", ".join(g["deaths"]) + "."
            lay.addWidget(QLabel(line))
        if f.get("best_before"):
            diff = f["dps"] - f["best_before"]
            lay.addWidget(QLabel(f"Best previous on this target: {f['best_before']:.0f} DPS ({diff:+.0f} now)"))
        if f.get("danger"):
            d = f["danger"]
            box = QFrame()
            box.setStyleSheet("QFrame { background: rgba(70, 12, 12, 200); border: 2px solid #c03030; "
                              "border-radius: 6px; } QLabel { background: transparent; border: 0; }")
            bl = QVBoxLayout(box)
            hits = "".join(f"<li>{_esc(h['who'])}: {_esc(h['spell'])} for {_n(h['amount'])}</li>" for h in d["hits"])
            t = QLabel(f"<b style='color:#ff7070; font-size:12pt'>DANGER AT {_dur(d['t'])}</b><br><br>"
                       f"Lowest health {d['hp']:.0%}<ul style='margin-left:-20px'>{hits}</ul>"
                       + (f"Ready and unused: {_esc(', '.join(d['unused']))}" if d.get("unused") else ""))
            t.setTextFormat(Qt.TextFormat.RichText)
            bl.addWidget(t)
            lay.addWidget(box)
        if f.get("good") or f.get("improve"):
            self._section(lay, "Top findings")
            for g in f.get("good", []):
                lay.addWidget(QLabel(f"<span style='color:#50dc78'>✔</span> {_esc(g)}"))
            for g in f.get("improve", []):
                lay.addWidget(QLabel(f"<span style='color:#f0a040'>▲</span> {_esc(g)}"))
        if f.get("abilities"):
            self._section(lay, "Abilities")
            self._table(lay, ["Ability", "Casts", "Hits", "Crits", "Miss", "Damage", "Avg", "Share"],
                        [[a["name"], a["casts"], a["hits"], a["crits"], a["miss"], _n(a["damage"]),
                          _n(a["avg"]), f"{a['share']:.0%}"] for a in f["abilities"]])
        if f.get("cooldowns"):
            self._section(lay, "Cooldowns")
            rows = []
            for c in f["cooldowns"]:
                lost = "held" if c.get("held") else _n(c["lost"])
                missed = c.get("missed", "-")
                if "counted" in c and c["missed"] > c["counted"]:
                    missed = f"{c['missed']} ({c['missed'] - c['counted']} excused)"
                if "free" in c:
                    why = ", ".join(f"{k} {v:.1f}s" for k, v in c.get("excused", {}).items()) or "-"
                    rows.append([c["name"], f"{c['cd']:.1f} s", c["used"], c.get("possible", "-"),
                                 missed, why, f"{c['free']:.1f} s", lost])
                else:      # saved before ready time was measured
                    rows.append([c["name"], f"{c['cd']:.1f} s", c["used"], "-", "-", "-", "-", lost])
            self._table(lay, ["Spell", "CD", "Used", "Possible", "Missed", "Excused", "Free", "Lost"], rows)
            lay.addWidget(dim_label("Possible: the casts that would have fit if you cast it each time it came up. "
                                    "Missed: the ones you didn't make (those that sat ready under 2 s with no excuse are marked excused). Excused: ready time with a good reason. Free: "
                                    "the rest, when you could have cast it - only that counts as lost damage. "
                                    "Cooldowns of a minute or more only count on bosses (held: saved for one). "
                                    "Cooldowns are learned from your casts and get more exact the more you play."))
        if f.get("auto"):
            a = f["auto"]
            self._section(lay, "Auto attacks")
            lay.addWidget(QLabel(f"{a['swings']} swings every {a['speed']:.1f} s; {a['lost']} lost "
                                 f"({a['lost_casting']} while casting, {a['lost_other']} other), about "
                                 f"{_n(a['damage_lost'])} damage."))
        if f.get("buffs"):
            self._section(lay, "Your buffs")
            self._table(lay, ["Name", "Uptime"], [[b["name"], f"{b['uptime']:.0%}"] for b in f["buffs"]])
        if f.get("failed"):
            self._section(lay, "Failed casts")
            self._table(lay, ["Spell", "Reason", "Count"], [[x["spell"], x["reason"], x["count"]] for x in f["failed"]],
                        right_from=2)
        idle = f.get("idle") or {}
        self._section(lay, "Idle time")
        lay.addWidget(QLabel(f"{idle.get('total', 0):.1f} s idle (gaps of 2.5 s or more with nothing cast): "
                             f"{idle.get('with_resource', 0):.1f} s free, {idle.get('moving', 0):.1f} s moving, "
                             f"stunned or with nothing to hit, {idle.get('out_of_resource', 0):.1f} s out of resource. "
                             + ("You have no filler spell to press between cooldowns, so idle time isn't counted."
                                if idle.get("filler") is False else "Only the free part counts.")))
        res = f.get("resource") or {}
        self._section(lay, "Resource")
        parts = []
        if res.get("start") is not None:
            parts.append(f"Started {res['start']:.0%}")
        if res.get("end") is not None:
            parts.append(f"ended {res['end']:.0%}")
        if res.get("start_hp") is not None:
            parts.append(f"started at {res['start_hp']:.0%} health")
        lay.addWidget(QLabel(", ".join(parts) + "." if parts else "Not known (needs Advanced Combat Logging)."))
        pull = f.get("pull") or {}
        self._section(lay, "Pull")
        since = pull.get("since_last")
        txt = f"{since:.0f} s since the last fight" if since is not None else "First fight since the log started"
        if pull.get("buffs"):
            txt += ". Buffs at pull: " + ", ".join(pull["buffs"][:8])
        lay.addWidget(QLabel(txt + "."))
        lay.addStretch(1)
        for lbl in body.findChildren(QLabel):
            lbl.setWordWrap(True)
