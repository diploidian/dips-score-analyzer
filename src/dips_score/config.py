"""Where the game's files are."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_WOW = Path(r"D:\Program Files (x86)\World of Warcraft\_forever_")


def data_dir() -> Path:
    return Path(os.environ.get("APPDATA") or str(Path.home())) / "dips-score"


@dataclass
class Paths:
    wow: Path
    logs_dir: Path | None = None     # picked in Settings when the combat logs aren't in <wow>/Logs

    @property
    def logs(self) -> Path:
        return self.logs_dir or self.wow / "Logs"

    @property
    def accounts(self) -> Path:
        return self.wow / "WTF" / "Account"

    def saved_files(self) -> list[Path]:
        """Every character's projectArthas saved file, most recently saved first."""
        files = self.accounts.glob("*/*/*/SavedVariables/dips-Score.lua")
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    def account_saved_files(self) -> list[Path]:
        """Each account's account-wide projectArthas saved file (dipsScoreDB: settings, enemy creature types)."""
        return sorted(self.accounts.glob("*/SavedVariables/dips-Score.lua"))

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
    def names_file(self) -> Path:
        return self.data_dir / "names.json"

    @property
    def removed_file(self) -> Path:
        return self.data_dir / "removed.json"

    @property
    def classes_file(self) -> Path:
        return self.data_dir / "classes.json"

    @property
    def analysis_dir(self) -> Path:
        """the runs analysed, one file each (store.py)"""
        return self.data_dir / "cache" / "analysis"

    def character_of(self, saved: Path) -> str:
        # .../Account/<account>/<realm>/<character>/SavedVariables/dips-Score.lua
        return saved.parent.parent.name


def game_folder(picked: str | Path) -> Path | None:
    """the _forever_ folder from what someone picked: it, or the _forever_ inside it"""
    for f in (Path(picked), Path(picked) / "_forever_"):
        if (f / "WTF").is_dir():
            return f
    return None


def _picked() -> dict:
    """the folders picked in Settings (settings.json; the ui module owns the rest of that file)"""
    try:
        saved = json.loads((data_dir() / "settings.json").read_text(encoding="utf-8"))
        return saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        return {}


def paths(wow: str | Path | None = None) -> Paths:
    """the game folder: --wow, else the one picked in Settings, else DIPS_WOW, else the default"""
    picked = _picked()
    logs = picked.get("logs_folder")
    return Paths(Path(wow or picked.get("wow_folder") or os.environ.get("DIPS_WOW") or DEFAULT_WOW),
                 Path(logs) if logs else None)
