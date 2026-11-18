"""Following the combat log as the game writes it.

The game appends to the newest WoWCombatLog*.txt (a new file each time /combatlog is turned on),
in batches. poll() returns the whole lines added since the last call; a line still being written
waits for the next call.
"""
from __future__ import annotations

from pathlib import Path


class LogTail:
    def __init__(self, logs_dir: Path, from_start: bool = False):
        self.dir = logs_dir
        self.path: Path | None = None
        self.pos = 0
        self.partial = b""
        self.from_start = from_start   # read files already there from the beginning (replays, tests)
        self.first = True

    def _newest(self) -> Path | None:
        files = list(self.dir.glob("WoWCombatLog*.txt"))
        return max(files, key=lambda p: p.stat().st_mtime) if files else None

    def poll(self) -> list[str]:
        newest = self._newest()
        if newest is None:
            return []
        if newest != self.path:
            # a new file: on start-up skip what's already in it (old fights), after that read it all
            self.path = newest
            self.pos = 0 if (self.from_start or not self.first) else newest.stat().st_size
            self.partial = b""
        self.first = False
        try:
            size = self.path.stat().st_size
            if size < self.pos:          # the file was cut or replaced: start over
                self.pos, self.partial = 0, b""
            if size == self.pos:
                return []
            with open(self.path, "rb") as fh:
                fh.seek(self.pos)
                data = fh.read(size - self.pos)
            self.pos = size
        except OSError:
            return []
        data = self.partial + data
        lines = data.split(b"\n")
        self.partial = lines.pop()       # an unfinished last line
        return [ln.decode("utf-8", errors="replace").rstrip("\r") for ln in lines if ln.strip()]
