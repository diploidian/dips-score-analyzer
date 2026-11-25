"""projectArthas: scores a WoW dungeon run from the projectArthas addon's input log and the combat log."""
import sys
import tomllib
from pathlib import Path


def version() -> str:
    """pyproject.toml's version (the installed app carries the file), "" when it can't be read"""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parents[2]))
    try:
        return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, ValueError, KeyError):
        return ""
