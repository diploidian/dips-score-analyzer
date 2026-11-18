"""Where the game's files are."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_WOW = Path(r"D:\Program Files (x86)\World of Warcraft\_forever_")


@dataclass
class Paths:
    wow: Path

    @property
    def logs(self) -> Path:
        return self.wow / "Logs"

    @property
    def accounts(self) -> Path:
        return self.wow / "WTF" / "Account"

    def saved_files(self) -> list[Path]:
        """Every character's dips-Score saved file, most recently saved first."""
        files = self.accounts.glob("*/*/*/SavedVariables/dips-Score.lua")
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    @property
    def data_dir(self) -> Path:
        """the analyzer's own files (your class and role picks)"""
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "dips-score"

    @property
    def roster_file(self) -> Path:
        return self.data_dir / "roster.json"

    @property
    def weights_file(self) -> Path:
        return self.data_dir / "weights.json"

    @property
    def classes_file(self) -> Path:
        return self.data_dir / "classes.json"

    def character_of(self, saved: Path) -> str:
        # .../Account/<account>/<realm>/<character>/SavedVariables/dips-Score.lua
        return saved.parent.parent.name


def paths(wow: str | Path | None = None) -> Paths:
    return Paths(Path(wow or os.environ.get("DIPS_WOW") or DEFAULT_WOW))
