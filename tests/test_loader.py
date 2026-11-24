"""Runs analysed off the window's thread (ui/loader.py): they arrive through done, what you look at goes first.
Needs PyQt6, so it is skipped on a Python without it."""
import importlib.util
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

HAVE_QT = importlib.util.find_spec("PyQt6") is not None


@unittest.skipUnless(HAVE_QT, "needs PyQt6")
class LoaderTests(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        self.app = QApplication.instance() or QApplication([])
        from dips_score.config import Paths
        from dips_score.ui.loader import Loader
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = mock.patch.dict(os.environ, {"APPDATA": tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.loader = Loader(Paths(Path(tmp.name) / "no game"))
        self.addCleanup(self.loader.stop)        # before the folder goes (cleanups run last first)
        self.got = []
        self.loader.done.connect(lambda *out: self.got.append(out))

    def wait_for(self, n):
        """spin the event loop until n results are in (queued from the worker), or fail after 10 s"""
        from PyQt6.QtCore import QDeadlineTimer, QEventLoop
        deadline = QDeadlineTimer(10000)
        while len(self.got) < n and not deadline.hasExpired():
            self.app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        self.assertEqual(len(self.got), n)

    def test_a_run_arrives_and_is_read_back_from_the_store(self):
        run = SimpleNamespace(id="1763-Nikana")
        with mock.patch("dips_score.analysis.analyze", return_value={"score": 87}) as analyze:
            self.loader.want(run, ("1763-Nikana", 1), urgent=True)
            self.wait_for(1)
            self.loader.want(run, ("1763-Nikana", 1), urgent=True)     # again: from the store, not analysed
            self.wait_for(2)
        self.assertEqual(analyze.call_count, 1)
        self.assertEqual(self.got, [("1763-Nikana", ("1763-Nikana", 1), {"score": 87}, "")] * 2)

    def test_stop_waits_for_the_run_and_its_result_is_there_to_take(self):
        """as the window does before a replay: nothing comes in after it"""
        started, gate = threading.Event(), threading.Event()

        def analyze(run, _paths):
            started.set()
            gate.wait(10)
            return run.id
        with mock.patch("dips_score.analysis.analyze", side_effect=analyze):
            for rid in ("r1", "r2"):
                self.loader.want(SimpleNamespace(id=rid), (rid,), urgent=False)
            started.wait(10)
            threading.Timer(0.1, gate.set).start()
            self.loader.stop()
        self.app.sendPostedEvents()
        self.assertEqual([out[0] for out in self.got], ["r1"])      # r2 was dropped
        self.assertTrue((self.loader.paths.analysis_dir / "r1.pkl").exists())     # for the replay to clear

    def test_urgent_overtakes_the_warm_up_and_an_ask_twice_runs_once(self):
        started, gate, order = threading.Event(), threading.Event(), []

        def analyze(run, _paths):
            started.set()
            gate.wait(10)        # the first job holds the thread while the rest queue up
            order.append(run.id)
            return run.id
        runs = [SimpleNamespace(id=f"{i}-Nikana") for i in range(4)]
        with mock.patch("dips_score.analysis.analyze", side_effect=analyze):
            self.loader.want(runs[0], (runs[0].id,), urgent=False)
            self.assertTrue(started.wait(10))
            for r in runs[1:3]:
                self.loader.want(r, (r.id,), urgent=False)
            self.loader.want(runs[2], (runs[2].id,), urgent=False)     # twice: once
            self.loader.want(runs[3], (runs[3].id,), urgent=True)
            self.loader.want(runs[3], (runs[3].id,), urgent=True)
            gate.set()
            self.wait_for(4)
            self.app.processEvents()
        self.assertEqual(order, ["0-Nikana", "3-Nikana", "1-Nikana", "2-Nikana"])
        self.assertEqual(len(self.got), 4)

    def test_a_failing_run_arrives_as_an_error_and_the_next_still_runs(self):
        def analyze(run, _paths):
            if run.id == "1-Nikana":
                raise ValueError("broken log")
            return run.id
        with mock.patch("dips_score.analysis.analyze", side_effect=analyze):
            for i in (1, 2):
                self.loader.want(SimpleNamespace(id=f"{i}-Nikana"), (i,), urgent=True)
            self.wait_for(2)
        (rid, _, a, err), ok = self.got
        self.assertEqual((rid, a), ("1-Nikana", None))
        self.assertIn("broken log", err)
        self.assertEqual(ok, ("2-Nikana", (2,), "2-Nikana", ""))


if __name__ == "__main__":
    unittest.main()
