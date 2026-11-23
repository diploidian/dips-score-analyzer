"""Runs analysed off the window's thread: read back from the store, else analysed and saved there. What you're
looking at goes ahead of the runs warmed up in the background."""
from __future__ import annotations

import itertools
import queue
import threading
import traceback

from PyQt6.QtCore import QObject, pyqtSignal

from .. import analysis, store
from ..config import Paths


class Loader(QObject):
    done = pyqtSignal(str, object, object, str)    # run id, its key, the analysis (None: it failed), the error
    threaded = True     # False: a job runs at once, inside want (the tests)

    def __init__(self, paths: Paths, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.jobs: queue.PriorityQueue = queue.PriorityQueue()     # (0 urgent / 1 warm-up, order, run id)
        self.queued: dict[str, tuple] = {}      # run id -> (urgent, run, key): the newest ask for it
        self.running: tuple | None = None       # (run id, key)
        self.lock = threading.Lock()
        self.order = itertools.count()
        self.thread: threading.Thread | None = None

    def job(self, run, key: tuple) -> tuple:
        """the run's analysis: from the store, else analysed and saved there"""
        try:
            a = store.load(self.paths.analysis_dir, run.id, key)
            if a is None:
                a = analysis.analyze(run, self.paths)
                try:
                    store.save(self.paths.analysis_dir, run.id, key, a)
                except Exception:       # not saved: it's analysed again next time, that's all
                    traceback.print_exc()
            return run.id, key, a, ""
        except Exception:
            return run.id, key, None, traceback.format_exc()

    def want(self, run, key: tuple, urgent: bool):
        """get this run; an urgent ask overtakes the warm-up, and a run asked for twice is got once"""
        if not self.threaded:
            self.done.emit(*self.job(run, key))
            return
        with self.lock:
            if self.running == (run.id, key):
                return
            was = self.queued.get(run.id)
            self.queued[run.id] = (urgent or bool(was and was[0]), run, key)
            if was and (was[0] or not urgent):      # queued already, as soon as this ask needs
                return
            self.jobs.put((0 if urgent else 1, next(self.order), run.id))
        if self.thread is None:
            # shortcut: a thread shares the interpreter with the window, so it can stutter while a big run is
            # analysed; move the job to a process if that bothers
            self.thread = threading.Thread(target=self._work, daemon=True)
            self.thread.start()

    def drop(self):
        """forget what's queued (the window closed); the job running ends on its own"""
        with self.lock:
            self.queued.clear()

    def stop(self):
        """drop the queue and end the thread (the tests: nothing left holding their temp folder)"""
        self.drop()
        if self.thread:
            self.jobs.put((-1, -1, None))
            self.thread.join()
            self.thread = None

    def _work(self):
        while True:
            prio, _, rid = self.jobs.get()
            if rid is None:
                return
            with self.lock:
                ask = self.queued.get(rid)
                if ask is None or ask[0] != (prio == 0):     # dropped, or asked again more urgently: done there
                    continue
                del self.queued[rid]
                _, run, key = ask
                self.running = (rid, key)
            out = self.job(run, key)
            with self.lock:
                self.running = None
            try:
                self.done.emit(*out)
            except RuntimeError:        # the window (and this) was deleted meanwhile
                return
