# Upgrade Finder in projectArthas

## Context

ForeverHUD has a design (not built, not approved) for an "Upgrade Finder": one button that answers "what gear on
the auction house, that I can wear and afford, is the biggest upgrade for my gold?" The two docs are
`F:\8. CLAUDE\Projects\WoW\ForeverHUD\docs\upgrade-finder\2026-11-25-upgrade-finder-{design,handoff}.md`.

It fits projectArthas better:
- The add-on already saves worn gear: item IDs, the game's own stat numbers (`itemstats`) and every tooltip line.
  It also saves your stats, talents and gold flow at the auction house (Trade).
- The app already measures what 1 attack power and 1 spell power are worth from your own combat log
  (`live/worth.py`). An add-on can't see combat numbers at all.
- The app can reach the internet, so there's no need for an outside program writing a Lua feed file.
- ForeverHUD has no auction or gear code, so nothing is lost there.

Fable reviewed the split, and the owner decided:
- No Buy button. Jump to listings, then the game's own Buy.
- Results show in the app first, with an in-game list in a later phase.
- The ForeverHUD docs get marked superseded.
- Outside prices come from wowauctions.net and Undermine Exchange, built now.

## Split

| Part | Home |
|---|---|
| Scan the auction house, judge wearability, save rows | add-on, new `addon/dips-Score/Market.lua` |
| Worth per stat, scoring, ranking, guardrails, results | app |
| Usual-price history | app, `%APPDATA%\dips-score\market.json` (30 days of lowest price per key per day) |
| wowauctions.net and Undermine readers | app, `sources/wowauctions.py`, `sources/undermine.py` |
| In-game list + Jump to listings | add-on, phase 4 |
| Buy button, Pawn, Auctionator, profile card, cast counting | not built |

What changes from the ForeverHUD design:
- Role comes from `live/profile.py figures()["main_role"]`, with the `model/roster.py` override behind it. That
  makes the profile card and the friend-or-enemy probe unnecessary.
- No `AHFeed.lua`: the app does the ranking, so it doesn't need to hand prices back to the add-on.
- Random-stat items on Forever have no suffix ID. Their links carry bonus IDs, and Auctionator's Forever branch
  tells variants apart by name. Every row and price is keyed by item ID plus full item name.

## Phase 0: probes (add-on only)

Extend `Probe.lua Auction()` and run `/dscore probe` once at the auction house. Results are saved to
`dipsScoreDB.probe.auction`.

The probes answer:
1. Does `C_AuctionHouse.SendBrowseQuery` per slot work, and what fields does a `GetBrowseResults` row have?
2. Do the filters `Enum.AuctionHouseFilter.UsableOnly` and `UpgradesOnly` exist?
3. Can stats and tooltip lines be read straight from a browse row? Try `C_TooltipInfo.GetItemKey`,
   `GetItemKeyInfo`, and `C_Item.GetItemStats` on a link built from the row.
4. If not: do `SendSearchQuery` and `GetItemSearchResultInfo(...).itemLink` work?

Also check, with no game needed:
- wowauctions.net: does it list random-stat variants separately, and is the page readable by a program?
- Undermine: is a Forever realm in `/v1/static/realms.json`? This needs the owner's free API key.

## Phase 1: what a point is worth (app; `links` in the add-on)

- `Sheet.lua Items()`: also save `links = {"slot,item:..."}`, the full item string (`Probe.lua Gear()` already
  extracts it), and add it to `ns.WORN`. Parse it in `sources/savedvars.py _sheet`.
- `live/worth.py`: a new function that turns each `spells()` slope into damage per second per spell power, using
  that spell's hits per fight second.
- New `live/gearworth.py`:
  - Role tables (damage melee, damage caster, damage ranged, healer, tank), anchored to attack power or spell
    power.
  - `score(stats, role, measured)` returns the damage per second added, plus standard points, with each stat's
    source marked `measured` or `standard`.
- Honesty rules:
  - Only measured parts make a damage-per-second figure. The standard part is shown beside it as points.
  - A weapon swap is always standard.
  - Healers and tanks get standard tables, and the sheet says so in one line.
  - No slope means no measured label; the existing `CLEAR` and `MIN_HITS` gates in `worth.py` stay.
- Show it as "What a point is worth" in the Character sheet's Stats tab (`sheet_view.py`, `ui/sheetpart.py`).
- Tests: `tests/test_worth.py`, a new `tests/test_gearworth.py`, and `tests/test_sheet.py` (links).

## Phase 2: scan and the Upgrades drawer

- Add-on `Market.lua`, listed in the toc:
  - `/dscore upgrades`, plus a button on the auction window.
  - Browses each slot, paced on `AUCTION_HOUSE_THROTTLED_SYSTEM_READY` with a retry on a dropped message, as
    Auctionator does. Shows progress and can be cancelled.
  - Keeps only usable rows (the filter if probe 2 passes, otherwise no red tooltip line, using `Sheet.lua`'s
    `Off()`/`Plain()`) priced at or under `GetMoney()`.
  - Saves to `dipsScoreLog.market`: `taken`, `realm`, `faction`, `money`;
    `rows "n,slot,itemID,itemLevel,quality,minPrice,count,unique,name"`; `rowstats "n,KEY,value"`;
    `rowtips "n,type,text"`. At most 30 rows per slot, and a new scan replaces the old one.
  - Does a second pass of at most 40 searches only if probe 3 fails.
- App:
  - `savedvars.py _market(log)`.
  - New `live/upgrades.py` ranks by gain and by gain per gold:
    - rings and trinkets compare with the weaker of the two
    - a two-hander compares with main hand plus off hand
    - a one-hander while a two-hander is worn is "not compared"
    - unique-equipped clashes are dropped
  - Price history goes into `market.json`.
- New "Upgrades" drawer on the Profile page, beside Trade and Character sheet. It follows the Trade pattern:
  `upgrades_view.py` with a `NEED` empty state, `ui/upgradespart.py`, wired in `profile_view.py` and
  `ui/profileview.py`.
  - Rows show item, slot, gain, price, gain per gold, source and age. Clicking one shows its tooltip lines word
    for word.
  - Filters: at most N gold (default half your gold), and hide anything above N times the usual price.
  - It stays off the plate.
- Tests: new `tests/test_market.py` (inline Lua with odd and missing rows) and `tests/test_upgrades.py`.

## Phase 3: outside prices (app)

- `sources/wowauctions.py`, standard library only:
  - At least 2 seconds between pages, at most one run an hour, and a clear User-Agent with no personal details.
  - Reads lowest price, count, 30-day median and scan time.
  - Used for random-stat items only if the site separates variants.
  - Ask the site owner before giving the app to other players.
- `sources/undermine.py`: only through its official API (`api.undermine.exchange`), with your own key stored in
  settings and gzip requests, inside the 3,000-points-an-hour budget.
  - Its terms forbid scraping the website, so the website is never read.
  - Only if Forever realms are in its realm list. The API page says it covers Retail, and suffix variants are a
    paid tier.
- Settings: "Prices from the web" switch (off by default), realm and faction, and an Undermine API key field.
- The usual price comes from your own scans first, then Undermine, then wowauctions.net. Rows from the web say
  "lowest price only" and their age.
- Tests: each parser against a saved sample response in `tests/`, with no network in tests.

## Phase 4: in-game list and Jump

- An add-on window shows the last scan, scored with `Weights.lua`, the standard tables labelled "standard
  weights".
- Clicking a row runs the auction search for that item, so you buy with the game's own button.
- One unittest loads `Weights.lua` through `sources/luadata.py` and checks it equals the Python tables.

## Also

- Add one line at the top of each ForeverHUD upgrade-finder doc: "Superseded: built in projectArthas, see
  `<plan path>`".
- Every installer build bumps the `pyproject` version, and every add-on change bumps the toc version. The dev PC's
  AddOns folder is a real copy, so changed add-on files must be copied over.
- Docs: a new "Upgrades" section in `docs/GUIDE.md`, `README.md`, `docs/OVERVIEW.md` and `docs/APP-GUIDE.md`.
- Work in a new branch off `projectArthas` (`dot-oribital/upgrades`), one commit per phase.

## Verification

- Every phase: `python -m unittest discover -s tests` with the PyQt6 venv at `packaging\.venv`
  (`QT_QPA_PLATFORM=offscreen`).
- Phase 0: read `dipsScoreDB.probe.auction` after `/reload`.
- Phase 1: the Character sheet shows measured and standard values for the current character, checked with
  `scripts/shoot.py` offscreen captures.
- Phase 2: scan at the auction house, `/reload`, and the drawer lists only wearable, affordable gear. Hand-check
  two items' gain against their stats.
- Phase 3: run each reader once by hand. The Upgrades rows show web prices labelled with their age, and nothing
  breaks with the switch off or offline.
- Lua is verified only in game, because this PC has no Lua.

## Open risks

- Browsing the auction house is unproven on this client. Auctionator's modern code running on Interface 16001 is
  strong evidence.
- Undermine may not cover Forever through its API, in which case only wowauctions.net is used.
- Results in the app need a `/reload` after the scan until phase 4.
- The cap of 30 rows per slot, by item level, can miss a low-level item with unusually good stats.
