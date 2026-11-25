"""settings.json: the defaults and reading/writing them. Pure Python, so tests can import it without Qt."""
from __future__ import annotations

import json

from ..config import Paths
from . import tokens

DEFAULTS = {"theme": "timeless",
            "motion": True,           # the debrief's short entrance (number ticks, bars grow, circles draw on)
            "mode": "auto",           # day | night | auto (follow the OS)
            "overlay": True,          # the card after each fight
            "overlay_dungeons": False,    # only after fights in dungeons and raids
            "overlay_seconds": 12,
            "overlay_keep": False,    # stay up, updated after each fight, instead of fading out
            "overlay_side": "right",
            "overlay_spot": None,     # [x, y] where it was dragged (fractions of the WoW window); None: overlay_side
            "texture": None,          # None: follow dips-Core's own setting; True/False: your pick here
            "texture_alpha": None,
            "wow_folder": None,       # None: --wow, DIPS_WOW or the default (config.paths reads these two)
            "logs_folder": None}      # None: <wow folder>\Logs


def load(paths: Paths) -> dict:
    out = dict(DEFAULTS)
    f = paths.data_dir / "settings.json"
    if f.exists():
        try:
            saved = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                out.update({k: v for k, v in saved.items() if k in DEFAULTS})
        except (ValueError, OSError):
            pass
    out["theme"], out["mode"] = tokens.normalize(out["theme"], out["mode"])
    return out


def save(paths: Paths, settings: dict):
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    (paths.data_dir / "settings.json").write_text(json.dumps(settings, indent=1), encoding="utf-8")
