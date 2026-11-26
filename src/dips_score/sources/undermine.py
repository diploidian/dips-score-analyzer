"""Undermine Exchange, through its official API only (its website terms forbid scraping: never read its pages).

Needs the user's own free API key. Every response is JSON {request, result}. The API says it covers Retail, so
callers check realms() for a Forever realm before asking for prices. Item paths and field names are not confirmed:
the path is one constant and every field is optional.
"""
from __future__ import annotations

import gzip
import json
import urllib.request

from .wowauctions import TIMEOUT, user_agent

API = "https://api.undermine.exchange"
REALMS = "/v1/static/realms.json"
ITEM = "/v1/realm/{region}/{realm}/item/{item}.json"      # guessed from the documented /v1/realm/:region/:realm/...
MAX_ITEMS = 200     # requests per run; one run an hour stays well inside the 3,000 points an hour


def _get(key: str, path: str, opener) -> dict:
    req = urllib.request.Request(API + path, headers={"Authorization": f"ApiKey {key}", "Accept-Encoding": "gzip",
                                                      "User-Agent": user_agent()})
    with (opener or urllib.request.urlopen)(req, timeout=TIMEOUT) as r:
        body = r.read()
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return json.loads(body.decode("utf-8"))


def parse_realms(data) -> list[dict]:
    """[{"region", "slug", "name"}] from realms.json, whether result is {region: [realms]} or [realms with region]"""
    result = data.get("result") if isinstance(data, dict) else None
    rows = []
    if isinstance(result, dict):
        for region, realms in result.items():
            for r in realms if isinstance(realms, list) else []:
                if isinstance(r, dict):
                    rows.append({**r, "region": r.get("region", region)})
    elif isinstance(result, list):
        rows = [r for r in result if isinstance(r, dict)]
    return [{"region": str(r.get("region") or ""), "slug": str(r.get("slug") or ""), "name": str(r.get("name") or "")}
            for r in rows if r.get("slug")]


def forever(realms: list[dict]) -> list[dict]:
    return [r for r in realms if "forever" in (r["slug"] + " " + r["name"]).lower()]


def parse_item(data) -> dict | None:
    """{"min", "median", "seen"} from one item summary; None without a lowest price"""
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, dict):
        return None

    def first(*keys):
        return next((result[k] for k in keys if result.get(k) is not None), None)
    low, median = first("min", "minPrice", "min_price", "minBuyout"), first("median", "medianPrice", "median_price")
    try:
        return None if low is None else {"min": int(low), "median": int(median) if median is not None else None,
                                         "seen": first("lastUpdated", "last_updated", "updated")}
    except (TypeError, ValueError):
        return None


def realms(key: str, opener=None) -> list[dict]:
    """raises on network or key trouble; the caller decides what that means"""
    return parse_realms(_get(key, REALMS, opener))


def prices(key: str, region: str, realm: str, item_ids, opener=None) -> dict:
    """{itemID: {"min", "median", "seen", "source": "undermine"}}; items that fail are left out"""
    out = {}
    for item in list(item_ids)[:MAX_ITEMS]:
        try:
            got = parse_item(_get(key, ITEM.format(region=region, realm=realm, item=int(item)), opener))
        except Exception:
            continue
        if got:
            out[int(item)] = {**got, "source": "undermine"}
    return out
