# Profile, third pass: Benefactor, Player Type, Character sheet

## Context

The Profile (0.18.0 on `projectArthas`, `1cc0bdf`) says how your character fights. It knows nothing of
what you do for others between fights, how you spend your time, or what you carry. This adds the
user's three ideas as four releases, each shippable alone. Base: `projectArthas`.

**The user's rulings:** the helping score is **Benefactor**; strangers and every revive score, buffs on
groupmates are shown but do not score; Player Type is the time bar first, auction second; auction
figures are only time there, items sold, and profit or loss (no listed or cancelled counts);
projections combine facts, formulas and measurement, with **measured first**.

**Measured on the real logs (6 days with data).** 14 revives (11 group, 3 strangers). An earlier figure
of 61 blessings on strangers was too high: 33 were the game re-logging a buff on someone who came back
into range. Counting only your own casts: 28 blessings and a bandage, 16 heals; 36 strangers helped.
Retribution Aura reached others 436 times and must not count.

**What each source can give:** the app today drops everything you do for others outside fights
(`live/tracker.py:144-146`, `245`). Advanced log lines carry your attack power, spell power, armor,
health and mana (not read today). The add-on's talent list is empty on this client (its calls do not
exist); talents and the Legacy tree look reachable through `C_Traits`. The auction house is the modern
API. No add-on on this PC uses `UnitStat` or `GetInboxInvoiceInfo`, so those need a probe.

## Release A, 0.19.0: Benefactor, and the probe

**What counts** (a line in the combat log with you as source, a friendly player as target):
- A revive: `SPELL_RESURRECT` (the log does not say it was accepted: copy says "revives cast").
- A buff: `SPELL_AURA_APPLIED` BUFF with your `SPELL_CAST_SUCCESS` of that spell on that same player
  within 1.5 s. This alone removes auras and re-logged buffs.
- A heal or a dispel on them.
- Never: yourself, pets, hostile players (reaction flags), anything on an enemy.

**Figure:** strangers helped (each person once a day, not in your group) plus revives cast (a revive is
not also a stranger helped). Unknown under 5, so a class with nothing to give gets no score, not a low one.
**Trait:** key `Benefactor`, family Company (so the family rule keeps it from taking both title
slots with Mercy), epithets Kind, Generous, Great-Hearted, kind count, anchors 5 to 100 per 15 days
(provisional: one character; a sweep reports how often each tier comes up). Mercy stays as it is.
**Named titles:** Benefactor + Travel "the Wayside Saint"; Benefactor + Lone "the Stranger's Friend".
**Deeds:** "raised 14 of the fallen", "helped 36 strangers". No player names.
**Page:** its All traits row (ink `role-heal`), with a line under it: revives, strangers helped,
buffs given to groupmates.

**Storage:** new `live/helping.py` and `%APPDATA%/dips-score/help.jsonl`: one row per act `{id, me,
t, kind, spell, group, who}`, `who` a short hash, no names. The id (time, spell, target hash) makes
live and `replay` agree. `Tracker.feed_lines` hands on your lines outside fights too; `History`
owns the file beside `fights.jsonl`. Figures join `profile.figures`. `CURRENT` is not changed.

**Probe:** `/dscore probe` writes `dipsScoreDB.probe` (no printing to copy): for each call, missing,
error, hidden, or a value. Run once out of combat, once at the auction house, once at a mailbox with
a sale in it. It covers stats, item stats, spell rank text, talents (`C_Traits`), the Legacy tree
(system 45), auction and mail events, sale mail fields, money, quest, zone, resting and AFK events,
taxi, skills and resistances. The app reads the file; a short `docs/PROBE.md` records the result.
**Gate: releases B to D build only what the probe shows works.**

## Release B, 0.20.0: where your time goes

**Add-on:** new `Life.lua`: every 5 s, adds to one state per day in `dipsScoreLog.time` (flat
strings, last 60 days; `version` stays 1). First that applies: AFK (not counted), auction house or
mailbox open (Trading), raid, dungeon, battleground or PvP combat, on a taxi (Travelling), gathering
or crafting cast, quest progress within 5 minutes (Questing), world combat within 1 minute (Hunting),
city or resting (In town), else Roaming. No chat, no names. Also recorded: quests handed in, levels.
**App:** merges each day into `days.json` (the larger value wins: counters only grow).
**Page:** one full-width bar "Where your time goes", right above All traits, segments in colour with
label and hours, and the type as its headline:

| Largest share (30% or more) | Type |
|---|---|
| Hunting | Slayer |
| Questing | Errant |
| Dungeon / Raid | Delver / Siegebreaker |
| PvP | Warmonger |
| Gathering and crafting | Artisan |
| Trading | Merchant Prince |
| Travelling and Roaming | Wayfarer |
| In town | Townsman |
| None reaches 30% | Adventurer |

Under 5 recorded hours: "Your time bar needs 5 hours of play with the add-on (n so far)."
"Where you fight" stays. Before gets a chip per segment, as the share rows do.

## Release C, 0.21.0: Trade

A closed drawer "Trade" under the time bar, three rows:
- **Time at the auction house** (auction house window only), and its share of play.
- **Items sold** (from the sale mails collected).
- **Profit or loss**: money received in auction mails, less money that left your purse while the
  auction house was open. Deposits, the house's cut and refunded bids then settle themselves. The
  note says so plainly: "things you bought and kept count as spent". Under it: profit per hour there.

Gold stays off the crest, the titles and Share. If the probe finds no readable sale mail, the two
figures show "–" and say why.

## Release D, 0.22.0: Character sheet

A closed drawer under All traits (as the user placed it), kept apart from traits because it is what
you carry, not how you play. Two columns of ruled rows, sub-tabs Gear | Stats | Abilities | Talents and Legacy.
- **Gear:** every slot with item, level, enchant; flags only for facts (empty, lowest, not enchanted,
  broken at pull). The loader keeps the item id it drops today (`savedvars.py:176`).
- **Stats:** each stat with how much comes from gear ("Strength 90, 34 from gear"); attack and spell
  power, armor, health, mana, resistances, weapon skills, professions. Read out of combat; a value
  the game hides says "hidden by the game". The combat log's own figures fill what the add-on cannot.
- **Abilities:** every known spell with its rank, casts and damage share in the window; never cast
  ones muted; a flag when you cast a lower rank than you know.
- **Talents and Legacy:** tree, points, each talent's rank; Legacy points and tree, if readable.
- **Projections**, in Stats: damage per second, healing per second, swing speed, and what 10 attack
  power or spell power is worth. Each is filled by the first that applies, and says which:
  1. **Measured:** from your own fights, with the count it rests on. A stat's worth compares the same
     weapon and the same enemy level at two attack power levels 40 or more apart, 200 hits each.
  2. **Estimate:** the classic formula (weapon damage plus attack power / 14 x speed), shown only
     while it lands within 10% of your own measured hits. Otherwise it is not shown.
  3. "–", with what it needs.

  Out: projecting an item you do not own, and upgrade suggestions (no item data or stat weights).
- **Saved:** each 15-day slice keeps mean item level and the stats, so a jump in numbers can be told
  from better play. The page says the sheet is as of your last /reload or logout.

## Steps, per release

1. Data and view-model with tests (no PyQt). 2. Mock-up in `docs/design/mockups/profile.html`; the user
approves. 3. Page (`ui/profileview.py`, `kit.Drawer`, `kit.Fold`). 4. Captures in four looks on a copy of
the real data; impeccable finish review. 5. `docs/GUIDE.md` (traits table), `README.md`, version bump,
installer. Merge into `projectArthas` and push only when asked.

**Files:** `live/helping.py`, `live/days.py`, `live/sheet.py` (new); `live/tracker.py`,
`live/history.py`, `live/traits.py`, `live/titles.py`, `live/profile.py`, `profile_view.py`,
`ui/profileview.py`, `sources/savedvars.py`, `sources/combatlog.py` (advanced block);
add-on: `Probe.lua`, `Life.lua` (new), `Char.lua`, `Options.lua`, `.toc`.

## Review focus

1. A buff re-logged on someone who came back into range, a radiating aura, and a pet's buff: none counts.
2. The same fight seen live, then replayed: each act counted once.
3. The same stranger helped three times in a day counts once; a revive in your own group counts.
4. No add-on data: the bar, Trade and sheet show empty states; nothing breaks.
5. Two characters; a day that rolls over midnight; a daylight-saving change.

## Verification

- Full suite with and without PyQt6; the new modules import without PyQt.
- Release A on a copy of the real logs: 14 revives, 36 strangers helped, no Retribution Aura counted.
- Release B to D: after the probe and a play session with /reload, figures match a hand count; a sale
  in game appears as one item and its money.

## My calls (change any)

Once per stranger per day; the anchors; the type names and 30%; the 5-minute and 1-minute rules;
"profit or loss" including things you kept; Trading counts mail in the time bar; the order A to D.

## Advisor

Fable advised. Taken: the cast-target rule's intent, keeping Mercy, no player names, the probe, no
item projections. Not taken, by the user's ruling: "strangers only" for revives, "never say profit",
and refusing all formula projections.
