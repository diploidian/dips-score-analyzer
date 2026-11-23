# dips-score

Scores a WoW dungeon run. New here? Start with [what the app does for you](docs/APP-GUIDE.md), then
the [guide](docs/GUIDE.md) for setup, what it tracks and
how the grade works, or [First run](docs/FIRST-RUN.md) once it's installed. It merges two data sources:

- **dips-Score** (the addon: its source is in `addon/dips-Score` here; copy that folder into
  `Interface/AddOns/`, it needs no other add-on; `/dscore` opens its settings, and `/dscore status`,
  `start`, `stop`, `mark`, `watch`, `button`, `clear` and `char` do the rest): what you pressed and when. That
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
automatically. Pick the game folder (and, if it's elsewhere, the combat log folder) in Settings;
`--wow <folder>` overrides that, and `DIPS_WOW` is used when nothing is picked.

The first time a run opens it takes a moment (up to about 20 seconds for a long one) while a page shows the
progress; a dungeon's page counts its visits in. After that it opens at once, the next start too. A few seconds
after start the app prepares the other runs in the background ("Getting runs ready · 3 of 25" under the rail).

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
its deaths. The add-on turns the combat log and advanced logging on at login (once per load, so a
`/combatlog` you type yourself stays) and when a run starts, if its `combatLog` option is on (it is by
default; `/dscore` opens the settings). It only ever turns them on, so you never need to type
`/combatlog`. The log file grows about 5 MB an hour of play; old files in the game's Logs folder can be deleted.

Upkeep's list of effects per class can be replaced: a `classes.json` next to `weights.json` with a shape
like `{"ROGUE": [["Slice and Dice", "self"]]}`, where each entry is a spell name and `"self"` (a buff on
you) or `"target"` (a debuff or DoT on an enemy), and a class listed there replaces its built-in list.

Defensives work the same way, under a `"defensives"` key: `{"defensives": {"ROGUE": ["Evasion"]}}` lists
the spells that count as a defensive for that class (see Fights after the kill).

The combat log only reports someone's health when they're hit, healed, or swing in melee. So a
ranged DPS who isn't taking damage has gaps in their health line.

The thresholds are a first guess. They're all in `TUNING` in `src/dips_score/scoring/score.py`.

## Fights after the kill

The window and the overlay show a card for each fight about 2 seconds after the last enemy dies. If
an enemy is still alive, the fight closes after 10 seconds without new log lines. A fight that
picks up again reopens with the same id. The window also shows `log delay`: how late the game wrote
the last line to its log file, which the app cannot shorten.

Each card starts with one sentence: how you died, else (when you healed) what went well, else "no
damage done", else the biggest finding when it cost 3% of your damage (or cost anything, in a fight under 90% of
the damage that was possible), else how close you came to the most you could have done. Everything is about you and your pets.

Every damage cooldown in your spell book that you cast in the last 7 days gets a row, whether or not
you pressed it in the fight:

- Possible is the number of casts that would have fit if you cast it each time it came up.
- Missed is the possible casts you did not make.
- A miss is counted only when the spell sat ready for 2 seconds or more with no excuse. Excused
  time is time you were moving (for cast-time spells), out of mana, stunned, healing someone who was
  low, or the target was nearly dead.
- Only unexcused time costs damage. Cooldowns of 60 seconds or more count on bosses only.
- A fight with no damage from you gets no cooldown rows and no lost damage, and a fight where you mostly healed keeps its rows but loses no damage.
- Procs are not casts: a Seal of Command hit that the log writes as your cast is left out. A cast owns
  damage logged under a longer name that starts with it and has no casts of its own.

Idle time is a gap of 2.5 seconds or more with nothing cast while you were not moving or stunned and had
the resource. Half of it counts as lost damage, and only if you have a filler: a damage spell you cast
twice within 2 seconds of each other, or a confirmed cooldown under 4 seconds. Without a filler
there was nothing to press.

The danger block (your health under 35%) names the defensives that sat ready and unused: off cooldown
at your lowest moment and not cast in the 10 seconds before it. Only spells in your spell book are
judged. A defensive the book has no cooldown for is assumed to have 300 seconds.

The spell book is kept per character and by spell name, since every rank has its own id. A
cooldown is learned from the 10 shortest gaps of 2 seconds or more between two casts: the shortest
gap that two others agree with (within 5%) is the cooldown, so one quick cast after a reset cannot set
it. A spell you ever cast twice within 2 seconds has no cooldown. When the character snapshot has the
game's own cooldown, the shorter of the two is used. "Best previous on this target" only counts
earlier fights within one level of this one.

The add-on also prints a line in chat after each fight of 3 seconds or more: presses (and how many were
clicks), refused casts, interrupted casts, and broken items. It counts whether or not a run is
recording. The `Print a line in chat after each fight` setting turns it off (on by default).

## Habits

The Habits page looks at the last 40 fights of the newest character in the saved fights. Fights where
you healed, or did no damage, are left out of the damage cards. The header names the character
(level, race, class, spec, gear level) from the snapshot when there is one. The session numbers
cover the latest stretch of fights with gaps under 30 minutes: fights, kills, kills per hour, average gap
between fights, average rest, and average health and mana at the pull.

The trend chart draws efficiency per fight, oldest on the left, once there are 5 fights. A gray line
marks a level-up (with the new level on top) and yellow dashes mark a change in gear level.

Cards are green (keep doing it), orange (fix) or blue (build). The ones it can show:

- Efficiency over the last 20 fights against the 20 before, when both halves have 5 fights: dropping or
  improving at 3 points or more, otherwise steady (75% or more) or stuck low.
- DPS up or down 5% or more between the two halves, split into the part from your play (the change
  in efficiency) and the rest, which moved with gear, level and what you fought.
- Cooldowns with damage lost, and swings lost per minute for melee.
- The most common failed-cast reason, and pull buffs you often start without.
- Deaths, and mana at the pull when it averages under 70%.
- A defensive that was ready when you were low.
- Harmful spells you know and have not cast in these fights (up to 3 are named), and empty gear slots.
- Gear at the pull: broken, or under 20% durability.

## Character snapshot

The add-on saves what the game knows about your character: level, race, class, your spells with their
base cooldowns and whether they hit enemies, the item level of each filled gear slot, the points in
each talent tree, and gear durability at each pull (the last 60). It takes the snapshot 3 seconds
after you enter the world and again at logout or `/reload`, so it reaches the app when the game saves.
A list that comes back empty at logout does not replace a good earlier one.

The app uses it for the game's cooldowns in your spell book, spec and gear level on each fight, your own
role (the talent tree with the most points, when the group finder gave none), and the Habits header and
cards above.

The snapshot depends on game API calls that could not be confirmed outside the game. `/dscore char`
takes a snapshot and prints what this client returned: spell count, how many have a cooldown, gear
slots, talent points and durability.

## Raids, sharing and names

Raids have their own section in the rail, under Raids, and work like Dungeons: each raid opens into its
visits, and a visit into its Debrief, Timeline, Pulls, Spells and Group tabs. The add-on records raids only
when Raids is ticked in its options (`/dscore`); it is off by default. A raid the game just saved opens
under Raids by itself.

Share (beside Settings and Reload, or Ctrl+Shift+C) copies the page showing to the clipboard as a
picture, all of it, the part scrolled off screen too, and saves it as a PNG in `Pictures\dips-score`.
Paste it into Discord or a chat. The picture is as wide as the window, lists that scroll inside a page
show only their visible rows, and the dips-Core texture is left out.

Right-click a visit or a fight in the rail and pick Rename… (or pick it and press F2) to give it a name,
such as "guild run with Anna". The name takes the date's place on a visit's row (hover it for the date) and the
target's on a fight's, and sits beside the original in the page title. Clear the text to take it off.

Delete… sits in the same menu (or pick the row and press Del). Deleting a visit also deletes the fights inside it,
and they stop counting in Habits; deleting a fight takes it off the Fights list. The visit is hidden by the app, not
erased from the game's saved file, which the game rewrites. A box asks first, as it can't be undone.

## Data the app keeps

In `%APPDATA%\dips-score`: `weights.json`, `classes.json` and `names.json` (yours), `removed.json` (the visits and
fights you deleted), `fights.jsonl` (the last 5000 fights) and `spells.json` (a spell book per character).
`spells.json` replaced `cooldowns.json`, which is no longer read; the `replay` command learns the spell books again
from your old combat logs. `cache\analysis` holds every run analysed, one file each (a few MB a run, up to about
60 MB for the longest: about 350 MB for 25 runs); it is safe to delete, as the runs are analysed again when next opened.

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
  scoring/classes.py     upkeep, defensives and talent roles, per class
  scoring/positioning.py where you stood
  live/tracker.py        tells fights apart in the combat log as it is written
  live/summary.py        one fight summed up, and the spell book
  live/history.py        fights.jsonl and spells.json; follows the log
  live/habits.py         the Habits page numbers and cards
  analysis.py            load + analyze (shared by CLI and window)
  ui/                    the PyQt6 window and timeline (fightsview.py, habitsview.py)
addon/dips-Score/Char.lua  the character snapshot and gear wear
tests/test_core.py       python -m unittest discover -s tests
tests/test_model.py      (same command)
tests/test_live.py       (same command)
tests/test_habits.py     (same command)
tests/test_char.py       (same command)
```
