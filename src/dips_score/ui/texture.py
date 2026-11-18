"""The dips-Core texture behind the analyzer's windows, as the dips add-ons draw it in game: the add-on's own
texture.tga, at 100% scale (one texture pixel per screen pixel), repeating, at the opacity you pick.

Until you change it in Settings, on/off and opacity follow dips-Core's own setting (the Global page:
Appearance > Texture), read from its saved variables.
"""
from __future__ import annotations

from pathlib import Path

from ..config import Paths
from ..sources import luadata
from . import assets

DEFAULT_ALPHA = 0.5     # dips-Core's own default


def source(paths: Paths) -> Path | None:
    p = paths.wow / "Interface" / "AddOns" / "dips-Core" / "texture.tga"
    return p if p.exists() else None


def dips_core_setting(paths: Paths) -> tuple[bool, float]:
    """(enabled, alpha) from dips-Core's saved variables, or its defaults"""
    for f in sorted(paths.accounts.glob("*/SavedVariables/dips-Core.lua"), key=lambda p: p.stat().st_mtime,
                    reverse=True):
        try:
            db = luadata.load(f).get("dipsCoreDB") or {}
            tex = db.get("texture") or {}
            return bool(tex.get("enabled", True)), float(tex.get("alpha", DEFAULT_ALPHA))
        except Exception:
            continue
    return True, DEFAULT_ALPHA


def tile(paths: Paths, alpha: float) -> str | None:
    """a .png of the texture with the opacity baked in (made once per opacity, kept in the cache)"""
    src = source(paths)
    if src is None:
        return None
    alpha = max(0.0, min(1.0, alpha))
    out = assets.cache_dir() / f"dips-texture-{round(alpha * 100)}.png"
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out.as_posix()
    try:
        from PIL import Image
        with Image.open(src) as im:
            im = im.convert("RGBA")
            r, g, b, a = im.split()
            a = a.point(lambda v: int(v * alpha))
            Image.merge("RGBA", (r, g, b, a)).save(out, "PNG")
    except Exception:
        return None
    return out.as_posix()
