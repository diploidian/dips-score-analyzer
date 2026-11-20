"""Dev only (not packaged): build the window offscreen, open a run on a tab, save a screenshot.

    PYTHONPATH=<folder with PyQt6> python scripts/shoot.py --run 6 --tab Group --look classical,night --out x.png

--run is the number `python dips-score.pyw runs` prints. --saved picks a dips-Score.lua (default: the game's).
Settings and history live in a temp APPDATA, so yours are never touched.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--saved")
ap.add_argument("--run", type=int, default=1)
ap.add_argument("--tab", default="Debrief")
ap.add_argument("--look", default="timeless,day", help="<theme>,<mode>")
ap.add_argument("--click-look", help="<theme>,<mode>: click the rail's Look buttons after the window is up")
ap.add_argument("--replay", action="store_true", help="sum up the game's old combat logs into the temp history (Fights page)")
ap.add_argument("--hover", action="store_true", help="after the run opens, show the timeline and put the mouse over it")
ap.add_argument("--click", choices=["show-me", "show-pull", "all-pulls"],
                help="show-me: press the Debrief's \"Show me on the timeline\"; show-pull: the Pulls plate's "
                     "\"Show this pull\"; all-pulls: open the Pulls drawer and pick its first row")
ap.add_argument("--overlay", action="store_true", help="save the after-fight card (a real fight from the history) instead of the window")
ap.add_argument("--size", default="1500x950")
ap.add_argument("--out", required=True)
args = ap.parse_args()

tmp = tempfile.mkdtemp(prefix="dips-shoot-")
os.environ["APPDATA"] = tmp
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score import analysis, config  # noqa: E402

theme_name, mode = args.look.split(",")
wow = config.paths().wow     # --wow is not offered: DIPS_WOW or the default
(Path(tmp) / "dips-score").mkdir()
# wow_folder pre-seeded so the first-run folder picker never opens a modal dialog offscreen
(Path(tmp) / "dips-score" / "settings.json").write_text(
    json.dumps({"theme": theme_name, "mode": mode, "wow_folder": str(wow), "motion": False}), encoding="utf-8")

if args.saved:
    _load = analysis.load_saved
    analysis.load_saved = lambda p, saved=None, merge=True: _load(p, Path(args.saved), merge)

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from dips_score.ui import app as ui  # noqa: E402

qapp = QApplication([])
paths = config.paths()
if args.replay or args.overlay:
    from dips_score.live.history import replay
    from dips_score.sources import combatlog
    replay(paths, combatlog.find_logs(paths.logs))
settings = ui.app_settings.load(paths)
ui.apply_look(paths, settings)
ui.load_weights(paths.weights_file)
ui.load_upkeep(paths.classes_file)
w = ui.Window(paths)
width, height = (int(v) for v in args.size.lower().split("x"))
w.resize(width, height)
w.show()
PAGES = {"dungeons": w.mode_dungeons, "fights": w.mode_fights, "habits": w.mode_habits}
TABS = {w.tabs.tabText(i).lower(): i for i in range(w.tabs.count())}
want = {"score": "debrief", "summary": "group"}.get(args.tab.lower(), args.tab.lower())   # the old names
if want not in PAGES and want not in TABS:
    sys.exit(f"unknown --tab {args.tab!r}; valid: " + ", ".join(w.tabs.tabText(i) for i in range(w.tabs.count()))
             + ", " + ", ".join(k.title() for k in PAGES))
if want in PAGES:
    PAGES[want].click()
else:
    w._open_run_id(w.runs[args.run - 1].id)
    w.tabs.setCurrentIndex(TABS[want])
if args.click_look:
    for key in args.click_look.split(","):
        w.look_buttons[key].click()
if want in TABS:
    w.tabs.setCurrentIndex(TABS[want])     # the redraw keeps it, but be sure
if args.click == "show-me":
    w.score.page.plate.button.click()
elif args.click == "show-pull":
    w.pulls.plate.button.click()
elif args.click == "all-pulls":
    w.pulls.drawer.flip()
    w.pulls.table.selectRow(0)


if args.hover:
    from PyQt6.QtCore import QPoint
    from PyQt6.QtTest import QTest
    w.show_on_timeline(w.timeline.v0, w.timeline.v1)
    QTimer.singleShot(150, lambda: QTest.mouseMove(w.timeline, QPoint(w.timeline.width() // 2, w.timeline.height() // 2)))


def grab():
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    if args.overlay:
        from PyQt6.QtGui import QPainter, QPixmap
        from dips_score.ui.overlay import Overlay
        fights = w.live.history.fights
        s = next((f for f in reversed(fights) if f.get("result") == "you died"), fights[-1])
        ov = Overlay()
        ov.show_fight(s)
        ov.setWindowOpacity(1)
        pm = QPixmap(ov.size())
        pm.fill(0x3a4a3a)      # roughly what the card sits on in game
        ov.render(pm)
        pm.save(args.out)
    else:
        w.grab().save(args.out)
    qapp.quit()


QTimer.singleShot(400, grab)
qapp.exec()
if args.click_look:
    print("settings.json:", (Path(tmp) / "dips-score" / "settings.json").read_text(encoding="utf-8"))
shutil.rmtree(tmp, ignore_errors=True)
print("saved", args.out)
