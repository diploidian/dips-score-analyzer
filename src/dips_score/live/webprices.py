"""Prices from the web, kept in webprices.json: Undermine first (only with your key and only if it lists a Forever
realm), wowauctions.net for the rest. At most one run an hour.

refresh() does network calls and sleeps between pages: run it off the UI thread. Neither function ever raises.
"""
from __future__ import annotations

import json
import time

from .. import store
from ..config import Paths
from ..sources import undermine, wowauctions

FILE = "webprices.json"
EVERY = 3600


def _read(paths: Paths) -> dict:
    try:
        data = json.loads((paths.data_dir / FILE).read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("items"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"stamp": 0, "items": {}}


def cached(paths: Paths) -> dict:
    """{itemID: {"min", "median", "seen", "source"}}"""
    out = {}
    for k, v in _read(paths)["items"].items():
        try:
            out[int(k)] = {f: v.get(f) for f in ("min", "median", "seen", "source")}
        except (ValueError, AttributeError):
            continue
    return out


def refresh(paths: Paths, settings: dict, item_ids, now=None) -> str:
    """fetch what's due and merge it into the cache; returns a short reason saying what happened"""
    try:
        return _refresh(paths, settings, item_ids, time.time() if now is None else now)
    except Exception as e:      # never break the caller: the old cache stays as it was
        return f"Web prices failed: {type(e).__name__}"


def _refresh(paths: Paths, settings: dict, item_ids, now: float) -> str:
    if not settings.get("web_prices"):
        return "Prices from the web are off"
    data = _read(paths)
    if now - float(data.get("stamp") or 0) < EVERY:
        return f"Web prices were fetched {int((now - data['stamp']) // 60)} min ago"
    wanted = sorted({int(i) for i in item_ids})
    if not wanted:
        return "No items to price"
    data["stamp"] = now        # stamped before fetching: a failed run still waits its hour
    store.write_file(paths.data_dir / FILE, json.dumps(data))
    server = settings.get("web_server") or "forever-us"
    got, notes = {}, []
    key = (settings.get("undermine_key") or "").strip()
    if key:
        try:
            region = server.rsplit("-", 1)[-1]
            ours = [r for r in undermine.forever(undermine.realms(key)) if r["region"] == region]
            if not ours:
                notes.append("Undermine has no Forever realms")
            else:
                slug = f"{settings.get('web_realm') or 'pvp'}-{server}"
                realm = next((r for r in ours if r["slug"] == slug), ours[0])["slug"]
                got.update(undermine.prices(key, region, realm, wanted))
        except Exception:
            notes.append("Undermine didn't answer (check the key)")
    rest = [i for i in wanted if i not in got]
    if rest:
        got.update(wowauctions.fetch(rest, server, f"{settings.get('web_realm') or 'pvp'}-{server}",
                                     settings.get("web_faction") or "alliance"))
    data["items"].update({str(k): {f: v.get(f) for f in ("min", "median", "seen", "source")} for k, v in got.items()})
    store.write_file(paths.data_dir / FILE, json.dumps(data))
    return "; ".join(notes + [f"{len(got)} of {len(wanted)} prices from the web"])
