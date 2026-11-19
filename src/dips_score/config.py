"""Where the game's files are."""
from __future__ import annotations

import json
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

    def found(self) -> bool:
        return (self.wow / "WTF").is_dir()

    @property
    def data_dir(self) -> Path:
        """the analyzer's own files (your class and role picks)"""
        return data_dir()

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


def data_dir() -> Path:
    return Path(os.environ.get("APPDATA") or str(Path.home())) / "dips-score"


def saved_wow() -> str | None:
    """the game folder picked in the app's settings"""
    try:
        wow = json.loads((data_dir() / "settings.json").read_text(encoding="utf-8")).get("wow")
    except (OSError, ValueError, AttributeError):
        return None
    return wow if isinstance(wow, str) else None


def game_folder(picked: str | Path) -> Path | None:
    """the _forever_ folder from what someone picked: it, or the _forever_ inside it"""
    for f in (Path(picked), Path(picked) / "_forever_"):
        if (f / "WTF").is_dir():
            return f
    return None


def paths(wow: str | Path | None = None) -> Paths:
    return Paths(Path(wow or os.environ.get("DIPS_WOW") or saved_wow() or DEFAULT_WOW))
