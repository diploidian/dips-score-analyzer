"""wowauctions.net item pages: lowest buyout, count, 30-day median and scan time, read from the page's __NEXT_DATA__.

The site blends random-stat variants ("of the Owl") into one price per item ID, so callers use these prices only
for gear without them. Network: one page at a time, at least PAUSE seconds apart, and nothing that names the user.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request

from .. import version

URL = "https://www.wowauctions.net/auctionHouse/{server}/{realm}/{faction}/{item}"
PAUSE = 2.0
TIMEOUT = 20
_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', re.S)


def user_agent() -> str:
    return f"projectArthas/{version() or 'dev'} (personal use)"


def parse_page(html: str) -> dict | None:
    """{"min", "median", "count", "seen", "name"} from one item page; None when the page has no price for it"""
    m = _DATA.search(html)
    if not m:
        return None
    try:
        props = json.loads(m.group(1))["props"]["pageProps"]
        row = props["v2"]["row"]
        if not row or row.get("min_buyout") is None:
            return None
        median = (row.get("stats") or {}).get("median_30d", row.get("median"))
        return {"min": int(row["min_buyout"]),
                "median": int(median) if median is not None else None,
                "count": int(row.get("quantity") or 0),
                "seen": row.get("seen_at") or props.get("item", {}).get("realm_last_scan"),
                "name": (props.get("item") or {}).get("item_info", {}).get("name")}
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def fetch(item_ids, server: str, realm: str, faction: str, opener=None) -> dict:
    """{itemID: {..., "source": "wowauctions"}}; an item whose page fails or has no price is left out"""
    out = {}
    for i, item in enumerate(item_ids):
        if i:
            time.sleep(PAUSE)
        req = urllib.request.Request(URL.format(server=server, realm=realm, faction=faction, item=int(item)),
                                     headers={"User-Agent": user_agent()})
        try:
            with (opener or urllib.request.urlopen)(req, timeout=TIMEOUT) as r:
                got = parse_page(r.read().decode("utf-8", "replace"))
        except Exception:       # offline, 404, timeout, a changed page: skip this one
            continue
        if got:
            out[int(item)] = {**got, "source": "wowauctions"}
    return out
