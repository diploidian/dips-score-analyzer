"""What the last auction house scan (the add-on's Market.lua, savedvars._market) has that beats what you wear, and what it
costs. Pure data but for remember() and web(), which read and keep prices on disk.

upgrades(char, s, history, web, now) -> None without a scan, else {"taken", "money", "age" (seconds since the scan), "role",
"rows", "unread" (listings the scan did not look at closely, so without stats)}. s: live.sheet.sheet, for the role and what your
fights measured. Each row, the biggest gain first:
  {"n", "id", "name", "quality", "kind", "slot" (the slot it is weighed against, a label), "price", "count", "tips", "source"
   ("scan"), "age", "usual" (copper, None when not known), "usual_from" ("your scans", "wowauctions", "undermine"), "usual_seen",
   "usual_min" (the web only gave its lowest price), "gain" {"dps", "points", "rank"} (None: "not compared", see why),
   "why", "per_gold" (gain rank per gold, None without a gain or a price), "gold_rank" (1: the most gain for the gold)}
A ring or trinket is weighed against the weaker one worn, a two-hander against main and off hand together; a one-hander or an
off hand while a two-hander is worn is not compared, nor is a slot whose worn item's stats were not read. A unique item you
already wear is dropped, and so is anything not better than what you wear.

pick(rows, cap, times) -> the rows priced at or under cap (copper) and not over times their usual price"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from statistics import median

from .. import store
from . import gearworth

FILE = "market.json"
KEEP_DAYS = 30
MIN_DAYS = 3                # days of your own scans a usual price needs before the web's is passed over
TIMES = 2                   # hide what costs over this many times its usual price
TWO_HAND = 17
# the inventory type a scan browsed -> the worn slots it goes in (Char.lua's numbers), and what the drawer calls it
KIND = {1: ((1,), "Head"), 2: ((2,), "Neck"), 3: ((3,), "Shoulder"), 16: ((15,), "Back"), 5: ((5,), "Chest"), 9: ((9,), "Wrist"),
        10: ((10,), "Hands"), 6: ((6,), "Waist"), 7: ((7,), "Legs"), 8: ((8,), "Feet"), 11: ((11, 12), "Ring"),
        12: ((13, 14), "Trinket"), 13: ((16,), "One-hand"), 17: ((16, 17), "Two-hand"), 22: ((17,), "Off hand"),
        15: ((18,), "Ranged")}


def key(row: dict) -> str:
    """a price's key: item id and full name, as random-stat variants share an id"""
    return f"{row['id']}:{row['name']}"


def remember(paths, market: dict | None, now: datetime | None = None) -> dict[str, dict[str, int]]:
    """market.json's lowest price per key per day for KEEP_DAYS, the scan's rows added: {key: {"2026-11-25": copper}}. Written
    only when it changed; a file that can't be read starts over, one that can't be written is written next time"""
    path, now = paths.data_dir / FILE, now or datetime.now()
    try:
        days = json.loads(path.read_text(encoding="utf-8"))["days"]
        days = days if isinstance(days, dict) else {}
    except (OSError, ValueError, KeyError, TypeError):
        days = {}
    cut, changed = (now.date() - timedelta(days=KEEP_DAYS)).isoformat(), False
    for k, seen in list(days.items()):
        kept = {d: p for d, p in seen.items() if d >= cut and isinstance(p, int)} if isinstance(seen, dict) else {}
        changed |= kept != seen
        if kept:
            days[k] = kept
        else:
            del days[k]
    if market and market.get("taken") and (day := date.fromtimestamp(market["taken"]).isoformat()) >= cut:
        for r in market["rows"]:
            seen = days.setdefault(key(r), {})
            if not isinstance(seen.get(day), int) or r["price"] < seen[day]:
                seen[day], changed = r["price"], True
    if changed:
        try:
            store.write_file(path, json.dumps({"days": days}))
        except OSError:
            pass
    return days


def web(paths) -> dict:
    """the web's prices, {item id: {"min", "median", "seen", "source"}}; {} without them"""
    try:
        from . import webprices
        got = webprices.cached(paths)
        return got if isinstance(got, dict) else {}
    except Exception:       # not built, or its file can't be read: your own scans are enough
        return {}


def _usual(row: dict, history: dict, web: dict) -> dict:
    """your own scans' median of the daily lowest prices, once there are MIN_DAYS of them; else the web's, only for an item
    under its own name (the sites blend random-stat variants); else what your scans have"""
    days = list((history.get(key(row)) or {}).values())
    w = web.get(row["id"]) or web.get(str(row["id"])) or {}
    if len(days) < MIN_DAYS and row["name"] == row.get("base", row["name"]) and (w.get("median") or w.get("min")):
        return {"usual": w.get("median") or w["min"], "usual_from": w.get("source"), "usual_seen": w.get("seen"),
                "usual_min": not w.get("median")}
    return {"usual": median(days) if days else None, "usual_from": "your scans" if days else None, "usual_seen": None,
            "usual_min": False}


def _two_hander(char: dict) -> bool:
    return any(left.strip() == "Two-Hand" for _, left, _ in (char.get("tips") or {}).get(16) or [])


def _against(char: dict, kind: int, role: str, s: dict, cls) -> tuple[dict | None, str]:
    """what a row of that kind is weighed against, or None and why not"""
    items, given = char.get("items") or {}, char.get("itemstats") or {}
    slots = KIND[kind][0]
    if kind in (13, 22) and _two_hander(char):
        return None, "you wear a two-hander"
    if any(x in items and x not in given for x in slots):
        return None, "the stats of what you wear there were not read"
    worn = [gearworth.score(given.get(x) or {}, role, s.get("measured"), x, cls) for x in slots]
    if kind in (11, 12):
        return min(worn, key=lambda w: w["rank"]), ""       # the weaker ring or trinket
    dps = [x["dps"] for x in worn if x["dps"] is not None]
    return {"dps": sum(dps) if dps else None, "points": sum(x["points"] for x in worn), "rank": sum(x["rank"] for x in worn)}, ""


def upgrades(char: dict | None, s: dict | None, history: dict | None = None, web: dict | None = None,
             now: datetime | None = None) -> dict | None:
    market = (char or {}).get("market")
    if not market or not market.get("rows"):
        return None
    s, history, web, now = s or {}, history or {}, web or {}, now or datetime.now()
    cls = char.get("class")
    role = s.get("gear_role") or gearworth.role(None, [], cls)
    age = max(0.0, now.timestamp() - market["taken"]) if market.get("taken") else None
    worn_ids = {i["id"] for i in (char.get("items") or {}).values() if i.get("id")}
    rows, unread = [], 0
    for r in market["rows"]:
        if r["kind"] not in KIND or r["unique"] and r["id"] in worn_ids:
            continue
        if not r["stats"] and not r["tips"]:            # not looked at closely
            unread += 1
            continue
        slots, label = KIND[r["kind"]]
        mine = gearworth.score(r["stats"], role, s.get("measured"), slots[0], cls)
        worn, why = _against(char, r["kind"], role, s, cls)
        gain = worn and {"dps": None if mine["dps"] is None and worn["dps"] is None else (mine["dps"] or 0) - (worn["dps"] or 0),
                         "points": mine["points"] - worn["points"], "rank": mine["rank"] - worn["rank"]}
        if gain and gain["rank"] <= 0:
            continue
        rows.append({k: r[k] for k in ("n", "id", "name", "quality", "kind", "price", "count", "tips")} | {
            "slot": label, "source": "scan", "age": age, "gain": gain, "why": why, **_usual(r, history, web),
            "per_gold": gain["rank"] / (r["price"] / 10000) if gain and r["price"] else None})
    rows.sort(key=lambda x: (x["gain"] is None, -(x["gain"] or {"rank": 0})["rank"], x["price"]))
    by_gold = {id(x): k + 1 for k, x in enumerate(sorted((x for x in rows if x["per_gold"] is not None), key=lambda x: -x["per_gold"]))}
    for x in rows:
        x["gold_rank"] = by_gold.get(id(x))
    return {"taken": market.get("taken"), "money": market.get("money"), "age": age, "role": role, "rows": rows, "unread": unread}


def pick(rows: list[dict], cap: float | None, times: float | None = TIMES) -> list[dict]:
    """the rows you would pay for: at or under cap (copper; None: any), and not over times their usual price (None: any)"""
    return [r for r in rows if (cap is None or r["price"] <= cap) and (times is None or not r["usual"] or r["price"] <= times * r["usual"])]
