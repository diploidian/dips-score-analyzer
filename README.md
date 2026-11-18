# dips-score

Scores a WoW dungeon run. It merges two data sources:

- **dips-Score** (the addon: its source is in `addon/dips-Score` here; copy that folder into
  `Interface/AddOns/`, it needs no other add-on; `/dscore` opens its settings, and `/dscore status`,
  `start`, `stop`, `mark`, `watch`, `button` and `clear` do the rest): what you pressed and when. That
  covers key vs click, key holds, movement, cast starts, finishes, refusals and interrupts, and
  combat start and end. It saves to `WTF/.../SavedVariables/dips-Score.lua` on `/reload` or logout.
- **The combat log** (`/combatlog`, with Advanced Combat Logging on): what actually happened.
  That covers damage, healing, kills, your health, and why a cast was refused.

The addon's clock anchors put both on one timeline. Your own casts are then matched against the
combat log to correct the remaining few milliseconds.

## Run it

Double-click `dips-score.pyw` for the window. From any folder, in PowerShell, cmd or bash:

```
python "D:\projects\dips-score-analyzer\dips-score.pyw" runs        # list saved runs
python "D:\projects\dips-score-analyzer\dips-score.pyw" report      # latest run's scorecard
python "D:\projects\dips-score-analyzer\dips-score.pyw" report 5    # run 5 from `runs`
```

The window reloads by itself when the game saves (after `/reload` or logout). New runs open
automatically. `--wow <folder>` (or the `DIPS_WOW` environment variable) points it at a
different WoW install.

Needs Python 3.13 and PyQt6.

## The score

Categories are weighted into a total out of 100 and a grade (S 90+, A 80+, B 70+, C 60+, D 45+, F).
Everything is measured over combat time only. You're scored by your role in the group (healer, dps
or tank): set it on the Group tab (it's guessed from your spells otherwise), or pass `report --role dps`.

The weights are yours to change: **Scoring weights...** in the window has a slider per category
and role (saved in `%APPDATA%\dips-score\weights.json`). A category at 0 is **info only**: still
shown, but it doesn't count and gives no tips.

**Healer** (defaults)

| Category | Weight | Measures |
|---|---|---|
| Group health | 35 | Deaths in the group, and time with someone under 35% |
| Response | 35 | When someone drops under 60% (after taking damage): seconds until you *start* a heal, HoT or shield on them; how many got nothing from you within 6s (dips someone else covered don't count) |
| Efficiency | 20 | Overhealing on your cast heals and HoTs (passive healing like Vampiric Embrace isn't judged); running out of mana |
| Casting | 10 | Refused presses that mean something went wrong (out of range, wrong target, no mana); pressing early doesn't count |
| Movement | info | Casts cut short by moving, per minute |
| Input | info | Presses per successful cast (mashing), and the share made with the mouse |
| Positioning | info | Where you stood: how often you took hits far from the tank (needs Advanced Combat Logging) |
| Hybrid bonus | up to +10 | Your damage as a share of an even split of the group's damage (damage while everyone was above 80% counts fully, the rest half), times Group health x Response. So damage only adds points when the healing held up. |

**DPS**

| Category | Weight | Measures |
|---|---|---|
| Damage | 20 | Your damage, pets included, as a share of an even split of the group's damage (not judged solo) |
| Activity | 15 | Share of combat spent casting, channeling, on the GCD, wanding or swinging in melee (time waiting for rage/energy doesn't count against you) |
| Cooldowns | 10 | Damage cooldowns that sat ready while you were free to use them, as a share of the damage you could have done |
| Interrupts | 10 | Enemy casts you could have stopped, and how fast you stopped them; dispels are folded in when you dispelled anyone this run |
| Casting | 10 | Share of presses the game refused, with the reasons from the combat log (waiting for rage or energy doesn't count) |
| Movement | 10 | Casts cut short by moving, per minute |
| Survival | 10 | Deaths, and time under 35% health |
| Upkeep | 5 | The buffs and DoTs your class keeps up, as the share of combat they were up (only ones you applied this run) |
| Input | 5 | Presses per successful cast (mashing), and the share made with the mouse |
| Resource | 5 | Share of combat your rage or energy sat at its maximum, so more coming in was wasted (needs Advanced Combat Logging) |
| Positioning | info | Melee: how often you were behind your target; everyone else: how often you took hits far from the tank (needs Advanced Combat Logging) |

**Tank**

| Category | Weight | Measures |
|---|---|---|
| Holding mobs | 25 | Of the mobs pulled, how many went for the tank first |
| Pickups | 25 | When a mob leaves the tank, how long until it's back on them (median), and how often it never comes back within 6 seconds |
| Survival | 20 | Deaths, and time under 35% health |
| Activity | 10 | Share of combat spent casting, channeling, on the GCD, wanding or swinging in melee (time waiting for rage/energy doesn't count against you) |
| Upkeep | 10 | The buffs and DoTs your class keeps up, as the share of combat they were up (only ones you applied this run) |
| Casting | 5 | Share of presses the game refused, with the reasons from the combat log (waiting for rage or energy doesn't count) |
| Input | 5 | Presses per successful cast (mashing), and the share made with the mouse |
| Movement | info | Casts cut short by moving, per minute |
| Interrupts | info | Enemy casts you could have stopped, and how fast you stopped them; dispels are folded in when you dispelled anyone this run |
| Cooldowns | info | Damage cooldowns that sat ready while you were free to use them, as a share of the damage you could have done |
| Resource | info | Share of combat your rage or energy sat at its maximum, so more coming in was wasted (needs Advanced Combat Logging) |
| Positioning | info | Melee: how often you were behind your target; everyone else: how often you took hits far from the tank (needs Advanced Combat Logging) |

Some categories need health, power or position readings, which the combat log only has with Advanced
Combat Logging. Without them, Group health, Response (healer) and Positioning show "needs Advanced
Combat Logging" and take no weight, so the total is worked out from what's left (`unavailable` in
`score.py`). Resource is left off the card when there are no power readings, and Survival still scores
its deaths. The add-on turns the combat log and advanced logging on when a run starts, if its
`combatLog` option is on (it is by default; `/dscore` opens the settings). It only ever turns them on.

Upkeep's list of effects per class can be replaced: a `classes.json` next to `weights.json` with a shape
like `{"ROGUE": [["Slice and Dice", "self"]]}`, where each entry is a spell name and `"self"` (a buff on
you) or `"target"` (a debuff or DoT on an enemy), and a class listed there replaces its built-in list.

The combat log only reports someone's health when they're hit, healed, or swing in melee. So a
ranged DPS who isn't taking damage has gaps in their health line.

The thresholds are a first guess. They're all in `TUNING` in `src/dips_score/scoring/score.py`.

## Layout

```
src/dips_score/
  sources/luadata.py     reads SavedVariables as data (never runs it)
  sources/savedvars.py   dipsScoreLog -> runs, segments, anchors, lines
  sources/combatlog.py   WoWCombatLog lines -> events (incl. this client's 19-field advanced block)
  model/sync.py          addon clock -> wall clock (anchors, drift, cast-matching correction)
  model/run.py           one run with both sources merged; fights; bosses
  scoring/metrics.py     measuring
  scoring/score.py       judging
  scoring/tank.py        tank measuring
  scoring/interrupts.py  interrupts and dispels
  scoring/cooldowns.py   cooldowns that sat ready
  scoring/upkeep.py      buffs and DoTs kept up
  scoring/classes.py     the upkeep table, per class
  scoring/positioning.py where you stood
  analysis.py            load + analyze (shared by CLI and window)
  ui/                    the PyQt6 window and timeline
tests/test_core.py       python -m unittest discover -s tests
tests/test_model.py      (same command)
tests/test_live.py       (same command)
```
