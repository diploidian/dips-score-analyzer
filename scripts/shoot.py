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
ap.add_argument("--tab", default="Score")
ap.add_argument("--look", default="timeless,day", help="<theme>,<mode>")
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
    json.dumps({"theme": theme_name, "mode": mode, "wow_folder": str(wow)}), encoding="utf-8")

if args.saved:
    _load = analysis.load_saved
    analysis.load_saved = lambda p, saved=None, merge=True: _load(p, Path(args.saved), merge)

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from dips_score.ui import app as ui  # noqa: E402

qapp = QApplication([])
paths = config.paths()
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
want = args.tab.lower()
if want not in PAGES and want not in TABS:
    sys.exit(f"unknown --tab {args.tab!r}; valid: " + ", ".join(w.tabs.tabText(i) for i in range(w.tabs.count()))
             + ", " + ", ".join(k.title() for k in PAGES))
if want in PAGES:
    PAGES[want].click()
else:
    w._open_run_id(w.runs[args.run - 1].id)
    w.tabs.setCurrentIndex(TABS[want])


def grab():
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    w.grab().save(args.out)
    qapp.quit()


QTimer.singleShot(400, grab)
qapp.exec()
shutil.rmtree(tmp, ignore_errors=True)
print("saved", args.out)
