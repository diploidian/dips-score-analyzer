"""Analyses kept on disk (cache\\analysis): a run analysed once opens at once after that, the next start too."""
from __future__ import annotations

import functools
import os
import pickle
import re
import sys
from pathlib import Path


@functools.cache
def stamp() -> float:
    """what the code is (the exe's, or the newest source file's, last write): newer code never reads older results"""
    if getattr(sys, "frozen", False):
        return os.path.getmtime(sys.executable)
    return max(p.stat().st_mtime for p in Path(__file__).parent.rglob("*.py"))


def file_name(run_id: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", run_id)     # a file name Windows takes


def load(folder: Path, run_id: str, key: tuple):
    """the run's analysis, if it was made from the same key by the same code; else None"""
    try:
        with open(folder / f"{file_name(run_id)}.pkl", "rb") as f:
            k, s, a = pickle.load(f)
    except Exception:       # missing, broken, or made by code whose classes have changed since
        return None
    return a if (k, s) == (key, stamp()) else None


def save(folder: Path, run_id: str, key: tuple, a):
    # shortcut: files are uncompressed (about 350 MB for 25 runs), compress if the folder gets too big
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f"{file_name(run_id)}.tmp"
    with open(tmp, "wb") as f:
        pickle.dump((key, stamp(), a), f, pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, folder / f"{file_name(run_id)}.pkl")     # a half-written file is never read


def clear(folder: Path):
    """drop every run's file: what they were all made from has changed"""
    for f in folder.glob("*.pkl"):
        try:
            f.unlink()
        except OSError:     # in use
            pass


def prune(folder: Path, keep_ids):
    """drop the files of runs the game no longer has (or you deleted); another character's runs stay"""
    keep = {file_name(i) for i in keep_ids}
    chars = {k.split("-", 1)[-1] for k in keep}     # run ids are "<start>-<character>"
    for f in [*folder.glob("*.pkl"), *folder.glob("*.tmp")]:
        if f.stem not in keep and f.stem.split("-", 1)[-1] in chars:
            try:
                f.unlink()
            except OSError:     # in use: gone next time
                pass
