"""What the Trade drawer on the Profile page shows, as plain data (no Qt), from live.days.trade of the last 15 days: a
sentence, three figures (time at the auction house, items sold, profit or loss) and the two sums the last one comes from."""
from __future__ import annotations

from dataclasses import dataclass, field

NEED = "Your trade fills in after you visit the auction house or collect an auction mail, and /reload with the add-on from 0.24 or newer."
NA = "–"
PER_HOUR_MIN = 600          # seconds at the auction house a "per hour" needs
IN, OUT = "role-heal", "role-dmg"       # money in and ahead; money out and behind
NOTE = ("Auction mails: the money you collected from them, sales and refunded bids, after the house took its cut. Spent there: what "
        "left your purse while the auction house was open, for buying, bids and deposits. A sale counts when you collect its mail, "
        "so it can land after what it cost you.")


@dataclass
class TradeRow:
    name: str
    value: str          # "38 min", "34", "3g 43s 45c"
    unit: str = ""      # quiet, after the value: "ahead", "or more"
    note: str = ""
    ink: str = "tx"


@dataclass
class Ledger:
    name: str
    value: str
    width: float        # 0..1 of the larger of the two
    ink: str


@dataclass
class TradeView:
    need: str = NEED                # shown instead of the rest
    say: str = ""                   # "Your auctions put 3g 43s 45c in your purse."
    cap: str = ""                   # "In the last 15 days, as of your last /reload or logout."
    rows: list[TradeRow] = field(default_factory=list)
    ledger: list[Ledger] = field(default_factory=list)
    note: str = NOTE


def coin(c: float) -> str:
    """copper as the game writes it: leading zero units dropped, inner ones kept, copper only when there is some"""
    c = abs(round(c))
    g, s, c = c // 10000, c // 100 % 100, c % 100
    return " ".join([f"{g:,}g"] * bool(g) + [f"{s}s"] * bool(s or g and c) + [f"{c}c"] * bool(c or not (g or s)))


def _hm(seconds: float) -> str:
    h, m = divmod(round(seconds / 60), 60)
    return f"{h} h {m} min" if h else f"{m} min"


def _day(iso: str) -> str:
    from datetime import date
    d = date.fromisoformat(iso)
    return f"{d.day} {d:%b}"


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def build_trade(t: dict | None) -> TradeView:
    if not t:
        return TradeView()
    net = t["came"] - t["spent"]
    word = "ahead" if net > 0 else "behind" if net < 0 else ""
    v = TradeView("", f"Your auctions put {coin(net)} in your purse." if net > 0 else f"Your auctions cost you {coin(net)}." if net
                  else "Your auctions came out even.",
                  f"{'Since ' + _day(t['since']) + ', when counting began' if t['since'] else 'In the last 15 days'}, "
                  "as of your last /reload or logout.")
    share = t["auction"] / t["seconds"] if t["seconds"] else 0
    v.rows.append(TradeRow("Time at the auction house", _hm(t["auction"]),
                           note=(f"{round(share * 100)}%" if round(share * 100) >= 1 else "under 1%") + " of your play, the auction house window only",
                           ink="gold"))
    mails = _plural(t["sales"], "sale mail")
    if not t["sales"]:
        v.rows.append(TradeRow("Items sold", "0", note="no sale mail collected", ink="m-cast"))
    elif t["unread"] == t["sales"]:
        v.rows.append(TradeRow("Items sold", NA, note=f"the game didn't say how many were in your {mails}"))
    else:
        v.rows.append(TradeRow("Items sold", f"{t['sold']:,}", "or more" if t["unread"] else "", ink="m-cast",
                               note=f"from {mails} you collected" + (f"; {t['unread']} didn't say how many" if t["unread"] else "")))
    per = f"{coin(net * 3600 / t['auction'])} {word} per hour at the auction house. " if net and t["auction"] >= PER_HOUR_MIN else ""
    v.rows.append(TradeRow("Profit or loss", coin(net), word, per + "Things you bought and kept count as spent.",
                           IN if net > 0 else OUT if net < 0 else "tx"))
    top = max(t["came"], t["spent"]) or 1
    v.ledger = [Ledger("Auction mails", coin(t["came"]), t["came"] / top, IN), Ledger("Spent there", coin(t["spent"]), t["spent"] / top, OUT)]
    return v
