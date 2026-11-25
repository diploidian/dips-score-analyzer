# The projectArthas guide

projectArthas tells you how well you played, and what to change next time. It looks at the parts of
your play you control: what you pressed, when you pressed it, whether the game accepted it, how
quickly you reacted when someone in your group got into trouble, and which cooldowns you left
sitting on your bar.

It has two parts that work together:

- The projectArthas add-on runs inside the game. It records your own inputs while you play: action
  presses and whether each came from a key or a mouse click, how long you held keys, when you
  started and stopped moving, and every stage of every cast. It also saves a snapshot of your
  character (level, spells, gear and talents) and prints a short line in chat after each fight.
- The projectArthas app runs on your desktop. It reads what the add-on saved, lines it up with the
  game's combat log to within a few milliseconds, and turns the two into a scorecard with a grade
  from S to F and a short list of things to work on. While you play, it also follows the combat
  log and shows a card for each fight about 2 seconds after the kill.

It is built for the Forever client (Interface 16001, the `_forever_` install folder) and needs no
other add-on.

## Contents

1. [Why use it](#why-use-it)
2. [Setting it up](#setting-it-up)
3. [What it records, and how](#what-it-records-and-how)
4. [How the grade is worked out](#how-the-grade-is-worked-out)
5. [Fights, cooldowns and the verdict](#fights-cooldowns-and-the-verdict)
6. [Habits](#habits)
7. [Roles](#roles)
8. [Classes](#classes)
9. [A tour of the app](#a-tour-of-the-app)
10. [If you already use a log parser](#if-you-already-use-a-log-parser)
11. [Limits worth knowing](#limits-worth-knowing)
12. [Questions](#questions)

## Why use it

A combat log tells you what happened: who hit what, for how much, and who died. It can't tell you
what you were trying to do. You can see that your damage was low, but not whether you spent part of
a boss fight pressing a spell that was still on cooldown, clicked half your heals with the mouse, or
let your best cooldown sit ready for twenty seconds.

The add-on fills in that missing half. A few examples of what you get to see:

- Refused presses, with the reason. Every time the game says no ("Out of range", "Not enough
  mana", "Invalid target"), the app finds the matching refusal in the combat log and counts it. If
  most of yours are range errors, the tip tells you so.
- Casts cut short by moving. If you started moving within 0.6 seconds before a cast broke, or
  were already moving, the app counts it as a cast you lost to movement. You get a rate per minute.
- Mashing. Pressing the same button three times within one second is a burst. Presses per
  successful cast shows how much of your input did nothing.
- Clicking. The share of presses you made with the mouse. Clicking is slower than a key, and the
  score nudges you toward bindings.
- Your reaction time as a healer. When a party member drops below 60% health after taking a hit,
  the app measures how many seconds passed before you started a heal, HoT or shield on them. The
  combat log shows the heal landing, but not how long you waited to start it.
- Missed cooldowns. Every damage cooldown you have used in the last week gets a row in each fight,
  whether or not you pressed it, with how many casts would have fit and roughly how much damage the
  unused ones cost.

You get feedback after every fight, too. If the app is open while you play, a panel slides in at
the edge of the game window about 2 seconds after the last enemy dies. It shows how much of your
possible damage you did, with one sentence about the fight ("Killed by Defias Pillager: Fireball for 412.", or "Clean fight: 94% of the damage
that was possible."), and your biggest gap.
The Fights page has the rest. Even with the app closed, the add-on prints a line in chat:
`14 s - 31 presses (4 clicks), 2 refused, 1 interrupted`.

Over time, the Habits page looks across your last 40 fights and tells you what you keep doing
right, what keeps costing you, and whether your damage went up because you played better or
because your gear did.

For dungeons, the whole group also gets ranked on what the combat log shows, with a podium, an MVP
and a handful of awards and roasts. Each run is kept, so you can watch your score for a dungeon move
over a week of practice.

## Setting it up

This takes about ten minutes the first time.

1. Run `projectArthas-setup-<version>.exe` and pick your `_forever_` folder. It installs the app and
   the add-on, and you don't need Python. Windows may warn you, as the installer isn't code signed.
2. If the game was open, close it and start it again. Check that projectArthas is ticked under
   AddOns at the character screen.
3. Log in. The add-on turns on the combat log and Advanced Combat Logging for you and says so in
   chat ("turned the combat log on for the analyzer."). If the game won't let an add-on change the
   advanced setting, the chat line tells you to turn it on yourself in the game's options.
4. Check that key and click detection works: type `/dscore watch` and press a few buttons, some
   with keys and some with the mouse. Each press is printed to chat as "key" or "click". The add-on
   watches the game's own action bars. Presses on replacement bars from other add-ons are recorded
   with an unknown source.
5. Type `/dscore char`. It takes a character snapshot and prints what the game returned: how many
   spells, how many with a cooldown, gear slots filled, talent points and gear durability. Numbers
   above zero mean the snapshot works on your client.
6. Play. Recording starts when you enter a dungeon and stops when you leave. A small record button
   near the top of the screen shows `REC` and the time while it runs. Fights in the open world
   still show up on the Fights page, because those come from the combat log alone.
7. Save. The game only writes add-on data to disk when you `/reload` or log out. Do one of those
   after the run. The record button's right-click menu has "Save now (reload)".
8. Open projectArthas from the Start menu. It finds your newest run and opens it.

To run it from source, install Python 3.13, run `pip install PyQt6` and double-click
`projectArthas.pyw`. Copy the `addon/dips-Score` folder into the game's `Interface/AddOns/` folder, or
link it so updates arrive by themselves:
`New-Item -ItemType Junction -Path "<WoW>\Interface\AddOns\dips-Score" -Target "<project>\addon\dips-Score"`

Installed and want the short version, with fixes for common problems? See [First run](FIRST-RUN.md).

The app looks for the game in `D:\Program Files (x86)\World of Warcraft\_forever_`. If yours is
elsewhere, it asks for the folder the first time and remembers it. You can change it later in
Settings, under Game folders, along with a separate combat log folder if yours isn't the
game's `Logs`. From a terminal, `--wow "<your folder>"` overrides it; the `DIPS_WOW` environment variable
(the installer sets it) is used when nothing is picked in Settings.

### Add-on commands

| Command | What it does |
|---|---|
| `/dscore` | Opens the settings (also under Esc > Options > AddOns) |
| `/dscore status` | Says whether it is recording, and how many runs are saved |
| `/dscore start` / `stop` | Starts or stops a recording by hand, anywhere |
| `/dscore mark [note]` | Drops a marker into the recording |
| `/dscore watch` | Prints each press to chat with "key" or "click" |
| `/dscore button` | Shows or hides the record button |
| `/dscore clear` | Deletes the saved runs |
| `/dscore char` | Takes a character snapshot and prints what the game returned |
| `/dscore probe` | Notes which game calls this client has, for the developer; saved on `/reload` (run it once anywhere, once at the auction house, once at a mailbox with a sale in it) |

In the settings you choose where recording starts by itself: dungeons (on by default), raids,
scenarios and delves, or everywhere else. Two more switches, both on by default: the chat line after
each fight, and turning the combat log on when you log in. The add-on only ever turns the log on. It
does this once per login, so if you type `/combatlog` to turn it off, it stays off until you log in
again.

### Upgrading from an older version

1. The add-on has a new file, `Types.lua`. Close the game completely and start it again the first
   time: `/reload` alone doesn't load a new file.
2. In the app, open Settings and press **Add fights from my old combat logs** once, before you rely on
   Earlier on the Profile page. It sums up again every saved fight whose combat log is still in the Logs
   folder, so old fights get their difficulty (dungeon or raid) and their chances. The runs are analysed
   again after it, in the background.

Fights summed up by 0.16 or 0.17 need step 2 once more for 0.18.0. Until then, 15-day blocks with older
fights in them aren't saved to Earlier. Once a newer block has been saved, the older ones are left out
for good.

## What it records, and how

### What the add-on writes

Each thing that happens becomes one short line of text with a timestamp in milliseconds. The add-on
records:

- every action button press, with the slot, the spell or item on it, and whether it came from a key
  or a click
- key down and key up on action buttons, so the app knows how long you held each key
- starting and stopping moving
- entering and leaving combat
- your casts at every stage: sent, began, succeeded, failed, interrupted, and channels starting and
  ending, each with its spell ID
- target changes and your own deaths
- boss pulls and boss ends (with whether the boss died), and keystone start and completion
- each group member's name, class, race and group finder role
- markers you add with `/dscore mark`
- the name and creature type of each hostile non-player unit you target, mouse over or see a
  nameplate for (see [Enemy creature types](#enemy-creature-types))

It records your own character only. Other players' inputs are never visible to an add-on, and pet
casts aren't recorded.

### Enemy creature types

A second part of the add-on, `Types.lua`, saves the name and creature type of every hostile
non-player unit you target, mouse over or see a nameplate for ("Risen Ghoul" is Undead). It reads
nothing from chat and saves no player names. It keeps up to 2000 names, account-wide. The app uses
them to tell whether a spell that only works on some types had anything to work on (see
[Chances](#chances)). Like everything the add-on saves, they reach the app on `/reload` or logout.

### The character snapshot

Beside the run log, the add-on saves what the game knows about your character: level, race, class,
your spells with their base cooldowns and whether they hit enemies, the item level of each filled
gear slot, and the points in each talent tree. Since add-on 0.5.0 it also saves what the Character sheet
shows: your stats, each worn item with its stats, tooltip and enchant, spell ranks, talent and Legacy
points, and professions. It takes the snapshot 3 seconds after you enter the
world (spell and item data may not be ready on the first frame) and again at logout or `/reload`. If
a list comes back empty at logout, the earlier good one is kept.

Since add-on 0.6.0 it also counts where your time goes, in seconds per day: hunting, questing, dungeons, raids,
PvP (battlegrounds, arenas, and any fight with an enemy player), professions (gathering, skinning, crafting), the auction house and mailbox, travelling, in town, and away (AFK, or 3 minutes
without moving, casting or fighting, outside an instance), with the quests handed in. It keeps 60 days, and the time of each level
you reach and each change of your main hand (the item and its enchant). No place, name or chat is saved.

Since add-on 0.7.0 it also counts your trade, per day: the seconds the auction house window is open, the money that leaves your
purse while it is open, and the money that reaches your purse from auction mails (a sale, or a bid refunded), with how many sale
mails and the items in them. A mail counts when its money arrives, not when it is sent. No item, buyer or price is saved.

At each pull it also records your gear durability: the lowest percentage and how many items are
broken. It keeps the last 60. Durability can only be read inside the game, which is why the add-on
records it.

Every game call the snapshot uses is checked first and run safely, so a call this client doesn't
support leaves that part empty and the rest still saves. `/dscore char` shows you which parts worked.

### How key and click are told apart

When you press an action button, the add-on writes the press first with an unknown source. Within
the same frame the game also calls either the button's click handler or its key binding handler. The
add-on hooks both and fills in the source. A key binding wins over a click, and a click only counts
when the mouse pointer is over the button. This works on the main bar and the extra bars (bottom
left, bottom right, right, left and bars 5 to 7). Bars drawn by other add-ons don't go through these
handlers, so their presses keep the unknown source.

### How the two clocks are matched

The add-on and the combat log keep time differently. The add-on has a precise millisecond counter
that starts at an arbitrary point. The combat log has wall-clock time. To match them, the add-on
takes clock anchors: it watches for the frame where the game's second counter ticks over, and
records both clocks at that moment. The error is half the time between two frames, which is about 3
ms at 144 frames per second. It keeps the tightest of four good readings and ignores readings worse
than 25 ms, such as ones taken during a loading screen.

It takes an anchor when a recording segment starts and again every time you leave combat. The app
draws a straight line between anchors, so slow drift over a long run is corrected as it goes.

Then it checks its own work. Each of your successful casts in the add-on's record is matched to the
same spell's cast in the combat log, if one is within 1.5 seconds. Once at least five casts match,
the app shifts everything by the median gap. The Debrief shows the result in a line such as
"42/45 casts matched, corrected +8 ms, spread -6..9 ms". Wand Shoot and Auto Shot are left out of
this matching because they repeat too often to pair reliably.

### What comes from the combat log

Health, mana, rage, energy, damage, healing, overhealing, positions, enemies, kills, buffs, debuffs,
interrupts, dispels and boss names all come from the combat log. The app reads any
`WoWCombatLog*.txt` in your `Logs` folder whose times overlap the run.

Health, power and positions are only in the log with Advanced Combat Logging on. Without them, the
categories that need those readings say "needs Advanced Combat Logging" and take no weight, so your
total is worked out from the rest. The log file grows about 5 MB an hour of play. Old files in the
game's Logs folder can be deleted.

### When a run starts and stops

A run starts when you enter a kind of instance that is turned on in the settings, and ends when you
leave. A `/reload` or relog inside the same instance within 30 minutes carries on the same run. If
you stop a dungeon recording by hand, it stays stopped until you leave that dungeon. A manual run
started with `/dscore start` lasts until `/dscore stop`.

The add-on keeps your 15 most recent runs (you can set 1 to 50). Each segment of a run has a safety
cap of 80,000 lines; a busy 30-minute dungeon is roughly 15,000. If a segment ever fills up, you get
a chat warning and recording pauses until the next `/reload`.

## How the grade is worked out

### Scores and grades

Each category gets a score from 0 to 100. Every category has two points: a value that scores 0 and a
value that scores 100. In between, the score moves in a straight line. For example, Activity scores
0 at 55% of combat spent busy and 100 at 90%, so 72.5% busy scores 50.

The total is the weighted average of the categories that count, plus a bonus for healers, capped at
100.

| Grade | Total |
|---|---|
| S | 90 and up |
| A | 80 to 89 |
| B | 70 to 79 |
| C | 60 to 69 |
| D | 45 to 59 |
| F | below 45 |

Everything is measured over time in combat only. Running between packs doesn't count against you.

### You are scored by your role

There are three scorecards: healer, DPS and tank. Your role comes from, in order:

1. what you picked on the Group tab
2. the group finder role the add-on recorded
3. your talents: the role of the tree with the most points, from the character snapshot
4. a guess from the spells you cast and what you did

If none of these give a role, the app uses the healer scorecard. If you have never queued through
the group finder and have no snapshot yet, set your role on the Group tab. The command line takes
`report --role healer`, `--role dps` or `--role tank`.

### The healer scorecard

| Category | Weight | Scores 100 at | Scores 0 at |
|---|---|---|---|
| Group health | 35 | no deaths, nobody under 35% | someone under 35% for 10% of combat |
| Response | 35 | 1 second to start a heal | 6 seconds, or half of dips missed |
| Efficiency | 20 | 15% overhealing | 50% overhealing |
| Casting | 10 | 10% of presses refused | 55% refused |
| Pacing | 5 | 95% of pulls entered safely and on time | 50% |
| Movement | info only | | |
| Input | info only | | |
| Positioning | info only | | |
| Hybrid bonus | up to +10 | | |

Group health: each death in the group costs 35 points. Time with someone under 35% health takes off
up to 40 more.

Response is built around dips. A dip is a party member falling from 60% health or more to below 60%,
in combat, with damage landing on them in the three seconds before. Health that someone traded away
on purpose, or a bad reading, isn't a dip because there was no damage first. For each dip the app
finds the first heal, HoT or shield you started that landed on that person. A heal you were already
casting counts as instant. If you started nothing within 6 seconds, the dip counts as missed and as
6 seconds in the median. If the person got back above 60% within 6 seconds without your help and
didn't die, someone else covered it and it is left out entirely. The Response score is 60% from your
median time and 40% from the share of dips you missed.

Group health and Response both need health readings. Without Advanced Combat Logging they show
"needs Advanced Combat Logging" and take no weight.

Efficiency is 70% overhealing on your cast heals and HoTs, and 30% mana. Passive healing, such as
Vampiric Embrace or potions, isn't judged. Each heal refused for lack of mana costs 25 points of the
mana part, and dropping under 5% mana costs 30. The summary also lists your dispels.

Casting for healers only counts refusals that mean something went wrong: out of range, wrong target,
no mana, and the like. Pressing early ("Not yet recovered", "Spell not ready yet", "Another action
is in progress", "Can't do that while moving") isn't held against a healer, because queueing the
next heal is good healing.

The hybrid bonus rewards a healer who also deals damage, as long as the healing held up. Your damage
is compared with an even split of the group's total. Damage done while everyone was above 80% counts
fully, the rest counts half. That share is then multiplied by your Group health and Response scores.
A healer who let the group fall over to squeeze in damage gets little or nothing.

### The DPS scorecard

| Category | Weight | Scores 100 at | Scores 0 at |
|---|---|---|---|
| Damage | 20 | 130% of an even share | 50% of an even share |
| Activity | 15 | busy 90% of combat | busy 55% |
| Cooldowns | 10 | no damage lost | 15% of your damage lost |
| Interrupts | 10 | every chance taken, quickly | see below |
| Casting | 10 | 10% of presses refused | 55% refused |
| Movement | 10 | no casts cut by moving | 3 cut per minute |
| Survival | 10 | no deaths, never under 35% | under 35% for a quarter of combat |
| Upkeep | 5 | buffs and DoTs up 90% of combat | up 40% |
| Input | 5 | 1.3 presses per cast, 10% clicks | 2.6 presses per cast, 60% clicks |
| Resource | 5 | at full rage or energy 2% of combat | 20% |
| Pacing | 5 | 95% of pulls entered safely and on time | 50% |
| Positioning | info only | | |

Damage is your damage, your pets' included, against an even split of the group's damage. Solo there
is nothing to compare with, so it isn't judged.

Activity is the share of combat you spent doing something. A cast counts from start to finish and
for at least one global cooldown (1.5 seconds, or 1.0 for energy users). An instant counts for one
global cooldown. A channel counts until it ends. Each wand or Auto Shot shot counts for up to 2
seconds, and each melee swing keeps you busy until the next one, for at most one swing. If you use
rage or energy, time when you couldn't afford your cheapest ability counts as waiting. Waiting
isn't held against you.

Cooldowns is the damage your unused damage cooldowns cost, as a share of your damage plus that loss.
It uses the same measurement as the fight cards, described in
[Fights, cooldowns and the verdict](#fights-cooldowns-and-the-verdict).

Interrupts is half how many chances you let through (0 at 60% let through) and half how fast you
stopped the rest (100 at 0.8 seconds, 0 at 2.5). A chance is an enemy starting a cast of a spell
that somebody interrupted at least once in the run, so a spell nobody can kick is never held
against you. A cast someone else stopped, or an enemy that died first, is left out. If you
dispelled anyone in the run, dispels are judged the same way (100 at 1.5 seconds, 0 at 5, with 8
seconds to answer) and the two are averaged. If you never interrupted in the run, the category
says so and takes no weight, since the log can't tell whether your class and level give you an
interrupt.

Casting counts every refusal for DPS, including pressing early. Rage and energy users are the
exception: "Not enough rage" or "Not enough energy" is pooling and doesn't count.

Movement: if you fight in melee (at least 10 swings, and more swings than hard casts), Movement is
info only, since melee has no cast to cut.

Survival: each of your deaths costs 45 points, and time under 35% health takes off up to 40.

Upkeep is the share of combat your class's buffs and DoTs were up. A buff counts while it is on
you; a DoT counts while at least one enemy has it, because in a dungeon you can't keep a DoT on
everything. Only effects you applied at least once in the run are judged, so your level and talents
never count against you. The lists are in the [Classes](#classes) section.

Input is 60% presses per successful cast and 40% the share of presses made with the mouse.

Resource is for rage and energy users only: the share of combat your power sat at its maximum, so
anything more coming in was wasted. It needs Advanced Combat Logging.

Pacing is on all three scorecards: the share of pulls you went into safely and on time. Safe is at
least 50% health and, if you use mana, 30% mana, half a second before the pull. On time is a first
press within 3 seconds of your combat beginning; a pull you started yourself is always on time. It
needs Advanced Combat Logging.

### The tank scorecard

| Category | Weight | Scores 100 at | Scores 0 at |
|---|---|---|---|
| Holding mobs | 25 | 90% of mobs went for you first | 40% |
| Pickups | 25 | 1.5 seconds to get a mob back | 6 seconds, or half never back |
| Survival | 20 | no deaths, never under 35% | under 35% for a quarter of combat |
| Activity | 10 | as DPS | |
| Upkeep | 10 | as DPS | |
| Casting | 5 | as DPS | |
| Input | 5 | as DPS | |
| Pacing | 5 | as DPS | |
| Movement, Interrupts, Cooldowns, Resource, Positioning | info only | | |

Holding mobs counts, of the mobs pulled, how many went for you first. The combat log has no threat
data, so this uses the first hit each enemy landed, counted from 20 seconds before the fight.

Pickups looks at what happens after a mob leaves you. Only an enemy's melee swings say who it is
attacking: a spell can hit anyone, and an area spell on the healer doesn't mean the mob turned to
them. A loss is a swing landing on someone in the group who isn't you, when that enemy's previous
swing was on you (or it is its first swing at all). The pickup is the seconds until that enemy's
next swing on you. If it isn't back within 6 seconds, that's a miss, unless the enemy died, the
fight ended or you were dead first, which don't count either way. Caster mobs that never swing
aren't judged. The score is 60% your median pickup time and 40% the share never picked back up.

Tank measurements come from the basic combat log, so they work without Advanced Combat Logging, and
they work for any tank in the group.

### Tips

Every category that scores below 85 has a tip attached. The Debrief puts the one that costs you
the most points on its plate and the next two under it. The tips name specifics where they can: the refusal reason you
hit most, the person whose dips you were slowest on, the cooldown that sat ready longest, the enemy
spell you most often let through, or the buff that fell off most. If nothing is under 85, the card
says "Nothing stands out - nice run."

### Changing the weights

The weights are yours to change. "Scoring weights..." in the app has a slider for each category and
role. Weights are relative, so 35, 35, 20, 10 scores the same as 7, 7, 4, 2. Setting a category to 0
makes it info only: you still see it, but it doesn't count and gives no tips. "Back to defaults"
puts them back. Your weights are saved in `%APPDATA%\dips-score\weights.json`.

The class lists for Upkeep and for defensives can be changed too, in a `classes.json` next to
`weights.json`. A class you list there replaces its built-in list:

```json
{"ROGUE": [["Slice and Dice", "self"], ["Rupture", "target"]],
 "defensives": {"ROGUE": ["Evasion", "Vanish"]}}
```

`"self"` is a buff on you and `"target"` is a debuff or DoT on an enemy.

### The group placing and the MVP

The add-on only sees your inputs, so for ranking the whole group fairly, everyone (you included) is
judged on what the combat log shows:

| Role | Categories |
|---|---|
| Tank | Holding mobs 40, Pickups 25, Survival 35, Damage 25 |
| Healer | Group health, Response and Efficiency as on the healer scorecard, plus the hybrid bonus |
| DPS | Damage 60 (against an even split of the group's damage), Survival 25, Utility 15 (interrupts and dispels per 10 minutes) |

Awards then add 2 points each (at most 6) and roasts take 2 away. The highest placing is first, and
MVP.

Awards: Wrecking Ball (most damage), Boss Bane (most damage to bosses), Janitor (most damage to
trash), Patch Kit (most healing by someone who isn't the healer), Shush (most interrupts), Scrubber
(most dispels), Last Word (most killing blows), Untouchable (the damage dealer who took the fewest
hits) and Spare Hands (the healer who still found time to hurt things).

Roasts: Punching Bag (took the most hits without being the tank), Carpet Sampler (most deaths),
Eager Beaver (started two or more pulls without being the tank) and Overflowing Cup (most
overhealing).

Each player also gets a radar chart of damage, healing, tanking, utility, kills and survival, scaled
against the best in the group.

## Fights, cooldowns and the verdict

The Fights page works from the combat log alone, while you play, in dungeons and the open world. It
needs no `/reload`, because the game writes the combat log as you go.

### When a fight ends

A fight's card appears about 2 seconds after the last enemy dies. If an enemy is still alive, the
fight closes after 10 seconds with no new log lines. If the fighting picks up again, the same fight
reopens and its card is updated, so you never get a duplicate. The window shows `log delay`: how
late the game wrote its last line to the log file. That delay is the game's, and the app can't
shorten it.

### The verdict

Each card starts with one sentence, picked from the first of these that fits:

1. You died: who killed you, with what, and for how much.
2. You mostly healed: the first thing that went well.
3. You did no damage: "No damage done this fight."
4. The biggest finding, when it cost 3% of your damage or more (or cost anything at all, in a fight
   under 90% of the damage that was possible).
5. How close you came to the most you could have done, with "Clean fight:" in front at 90% or more.

### Every missed cooldown

Every damage cooldown in your spell book that you cast in the last 7 days gets a row, whether or not
you pressed it in this fight:

- Possible is the number of casts that would have fit if you cast it each time it came up.
- Missed is the possible casts you didn't make.
- A miss only counts when the spell sat ready for 2 seconds or more with no excuse. Excused time is
  time you were moving (for spells with a cast time), out of mana, stunned, healing someone who was
  low, or when the target was nearly dead.
- Only unexcused time costs damage: the free seconds divided by the cooldown, times the spell's
  average hit.
- Cooldowns of 60 seconds or more count on bosses only. Saving a 3-minute cooldown on a trash pack
  is marked as held, not missed.
- A fight with no damage from you gets no cooldown rows, and a fight where you mostly healed keeps
  its rows but loses no damage.
- Procs aren't casts. A Seal of Command hit that the log writes as your cast is left out.

The rows are in the fight's All the details drawer. The overlay shows only the biggest gap.

### Idle time

Idle time is a gap of 2.5 seconds or more with nothing cast, while you weren't moving or stunned and
had the resource to act. Half of it counts as lost damage, and only if you have a filler: a damage
spell you cast twice within 2 seconds, or a confirmed cooldown under 4 seconds. Without a filler
there was nothing to press, so nothing is lost.

### Auto attacks

Your melee swings and your ranged shots (Auto Shot, wand Shoot) are read from the combat log.

- On the Spells tab the Melee row, and the Auto Shot or Shoot row, have a hit table line: how many
  swings or shots, their speed, the share that landed (with crit and glancing among the landed ones,
  as the Crit column), and the share missed, dodged, parried, blocked and so on. Extra swings are
  listed by the spell that gave them. Only swings at enemies count.
- When melee or shots are 10% or more of your damage, the Fight page and the Debrief say so in one
  line over the losses ("Melee 46% of your damage"). It is words only: it is not a loss.
- Time with no ability used is split. The part where auto attack was running is "no ability used
  while swinging" (or shooting); the rest is idle. Both cost the damage an ability could have added,
  and only if you have a filler.
- Heroic Strike, Cleave, Raptor Strike and Maul replace the next swing, so they fill the swing they
  take. A gap in your swings longer than 1.6 swings, while you weren't casting, is swings lost. For
  Auto Shot and wands it is shots lost, less time moving or with no enemy alive. A shot that a cast
  pushed back is counted apart, as "Shots clipped by casts" (a hard cast, or any cast for a wand).
  A wand's shots inside an idle gap that was already priced aren't lost a second time.

### Chances

A spell that can't always be used is only called out when you had a chance to use it. A chance is:

- for a spell that works on some creature types (Exorcism, Holy Wrath, Turn Undead, Shackle Undead,
  Enslave Demon, Banish, Hibernate, Polymorph, Scare Beast, Soothe Animal, Tame Beast), one enemy of
  those types in the fight;
- for a spell that needs a low target (Execute, Hammer of Wrath), an enemy that dropped under 20%
  health, which needs Advanced Combat Logging;
- for a spell that answers an avoided attack (Overpower and Mongoose Bite after the target dodges
  you; Revenge after you block, dodge or parry; Riposte and Counterattack after you parry), one such
  attack, with 5 seconds to answer. Overpower counts only in Battle Stance and Revenge only in Defensive Stance, so
  a chance only counts while that stance was on you. With no stance seen in the fight, the chances
  are unknown.

Ready time outside a chance is excused, and the fight cards say how many chances there were ("sat
ready 12 s across 3 chances"). When the chances can't be known (no creature types loaded, no enemy
health in the log, a fight saved before chances were counted), the spell is never called out as
unused. Enemy types come from the add-on, so an enemy it never recorded is unknown, and new types
need a `/reload` or logout to reach the app. Fights saved before this existed get their chances when
you run `replay`.

### The danger box and defensives

When your health falls under 35%, the card shows a danger box with the hits that did it. It also
names the defensives that sat ready and unused: off cooldown at your lowest moment. It names none when
you cast one on yourself within 10 seconds of that moment, before or after. Forbearance rules out the
paladin's shields. One that stops your own attacks or ends the fight for you (Blessing of Protection,
Divine Protection, Ice Block, Feign Death, Vanish) is named only when you died. Only spells in your
spell book are judged, so a defensive you don't have costs nothing. A defensive the book has no
cooldown for is assumed to have 300 seconds. A fight summed up before 0.18.0 doesn't say whether you
pressed one, so the fight page and the card name none for it.

### Your spell book

The app keeps a spell book for each character, by spell name, since every rank has its own ID. It
learns each cooldown from your casts: it keeps the 10 shortest gaps of 2 seconds or more between two
casts, and the cooldown is the shortest gap that two others agree with (within 5%). So one quick
cast after a cooldown reset can't set it. A spell you ever cast twice within 2 seconds has no
cooldown. When the character snapshot has the game's own cooldown for a spell, the shorter of the
two is used. The snapshot also means a cooldown you have never pressed can still show as missed.

"Best previous on this target" only compares fights within one average item level of this one (the combat log's own
figure), so better gear doesn't hand out records.

## Habits

The Habits page looks at the last 40 fights of the character you played most recently. Fights where
you healed, or did no damage, are left out of the damage cards.

The header names the character, with level, race, class, spec and gear level from the snapshot,
such as "Mapomimi, level 33 Undead Priest, Shadow, gear 31".
Below it are the session numbers, for the latest stretch of fights with less than 30 minutes between
them: fights, kills, kills per hour, average gap between fights, average rest (time eating,
drinking or bandaging), and average health and mana at the pull.

The trend chart draws your efficiency for each fight, oldest on the left, once there are 5 fights.
A gray line marks a level-up, with the new level on top (from the levels add-on 0.6.0 records; before it there is none). Yellow dashes mark a change in gear level.

The cards are grouped into Fix, Build and Keep. The ones it can show:

- Efficiency over the last 20 fights against the 20 before, when both halves have at least 5
  fights: dropping or improving by 3 points or more, otherwise steady (75% or more) or stuck low.
- Damage per second up or down 5% or more between the two halves, split into the part from your
  play (the change in efficiency) and the rest, which moved with gear, level and what you fought.
- The cooldowns that lost the most damage, and swings lost per minute for melee.
- Swings not landing: when 10% or more of at least 50 swings missed, were dodged or parried.
- Your most common failed-cast reason, and the pull buffs you usually have but sometimes forget.
- Deaths, and mana at the pull when it averages under 70%.
- A defensive that was ready when you were low.
- Damage spells you know and haven't cast in these fights (up to 3 are named), and empty gear
  slots. A spell that needs a chance is only named when you had one (see [Chances](#chances)).
- Gear at the pull that was broken or under 20% durability.

The damage split is the most useful card for a levelling character. Damage per second is the damage
that was possible per second times your efficiency. Efficiency is your play; what was possible
moves with gear, level and the targets you fought. So the card can say how much of a 15% rise was
you.

## Roles

### Healers

Response is the category a healer can't get from the combat log alone, because the log has no
reaction times. A healer who tops the healing meter can still be slow to react, and one who heals
less can be the reason nobody died.

The app sorts your healing from the combat log, without a spell list:

- a cast heal is a spell with a cast start and a heal
- a HoT is periodic healing
- a shield is an aura you put on a player with "Shield" in its name, as long as it went on someone
  else in the group at least once, or showed an absorb on its target within 2 seconds of going on
- everything else counts as passive and isn't judged

The shield rule keeps Lightning Shield, Divine Shield and Holy Shield on yourself from counting as
heals, while Power Word: Shield still does. So the healer scorecard works for any healing class.
The tips are written with a Priest in mind ("Shield or Renew the tank", "use a lower rank"), but the
measurements are the same for everyone.

What the healer card can show you:

- whether you are slow to react to the tank, or to the damage dealers
- whether your overhealing comes from casting big heals early
- whether you run out of mana in long pulls
- how many of your refusals are range errors, which point at positioning

### Damage dealers

Damage, Activity and Cooldowns carry the most weight between them. Damage says where you stood
against the group. Activity shows the gaps where you did nothing: late starts, waiting with nothing
else to press, or standing still while the group moved. Cooldowns shows what you left on your bar.
Interrupts rewards the player who watches enemy cast bars.

Casters with cast times get the most out of Movement: a cast you start and then walk out of costs
the cast time and a global cooldown. Melee players get a count of lost auto-attack swings instead,
split into swings lost while casting and swings lost for other reasons. Rage and energy users get
Resource, which shows how long they sat capped.

### Tanks

Tanks have their own scorecard. Holding mobs and Pickups together are half the default weight, and
they measure the two things a group notices: whether mobs went for you at the pull, and how fast
you got back the ones that wandered off. The Pickups tip names the player mobs most often turned
to.

The Pulls tab is useful for tanks too: it lists every pull with who started it, how many mobs and
packs were in it, how long it took, and which mob went for whom first.

## Classes

The app treats each class a little differently. The same scorecards apply to everyone, but these
tables decide what Upkeep looks for, which spells count as defensives, and which talent tree means
which role. Feral Druid is left out of the talent roles because it can tank or do damage, so the
guess from your spells decides.

| Class | Upkeep | Defensives | Talent trees |
|---|---|---|---|
| Warrior | Battle Shout; Sunder Armor, Rend, Demoralizing Shout, Thunder Clap | Shield Wall, Last Stand | Arms, Fury: DPS; Protection: tank |
| Paladin | Seal of Righteousness, Seal of Command, Righteous Fury, Holy Shield | Divine Protection, Divine Shield, Lay on Hands, Blessing of Protection | Holy: healer; Protection: tank; Retribution: DPS |
| Hunter | Hunter's Mark, Serpent Sting | Feign Death, Deterrence | all DPS |
| Rogue | Slice and Dice; Rupture | Evasion, Vanish, Cloak of Shadows | all DPS |
| Priest | Inner Fire; Shadow Word: Pain, Devouring Plague | Power Word: Shield, Desperate Prayer | Discipline, Holy: healer; Shadow: DPS |
| Shaman | Lightning Shield; Flame Shock | Shamanistic Rage | Restoration: healer; Elemental, Enhancement: DPS |
| Mage | Living Bomb | Ice Block, Ice Barrier, Mana Shield | all DPS |
| Warlock | Corruption, Curse of Agony, Immolate | Death Coil, Howl of Terror | all DPS |
| Druid | Moonfire, Insect Swarm, Rake, Rip | Barkskin, Frenzied Regeneration, Survival Instincts | Balance: DPS; Restoration: healer |

In the Upkeep column, buffs on yourself come before the semicolon and effects on enemies after it,
where a class has both.

### Warrior

A rage user, so "Not enough rage" refusals don't count against you, and Resource shows how long you
sat at full rage. As a melee fighter your Movement is info only, and Activity counts your swings.
Protection Warriors get the tank card from their talents. Interrupts count for you as soon as you
use one in a run.

### Paladin

Can be a healer, a tank or DPS, and the talent snapshot tells the app which. Holy Paladins get the
healer card, and your seals and Righteous Fury are what Upkeep looks for. Divine Shield and Holy
Shield on yourself aren't counted as healing shields. Paladin dispels count toward Interrupts once
you dispel in a run, and toward Utility in the group placing.

### Druid

The most varied class here. Restoration Druids lean on HoTs, which the app judges like cast heals
for Response and overhealing; a HoT started on someone counts as your answer to their dip. In cat
form you are an energy user with a 1.0-second global cooldown; in bear form, a rage user. The app
uses the power type most of your readings carry. Feral has no fixed talent role, so set it on the
Group tab if the guess is wrong. Balance players with cast times have the most to gain from the
Movement numbers.

### Priest

The healer scorecard and its tips were written with Priests in mind. Power Word: Shield counts as a
response to a dip, Renew as a HoT, and Vampiric Embrace as passive healing that isn't judged. Shadow
Priests get the DPS card, where channels like Mind Flay count as busy until they end, and Upkeep
watches Shadow Word: Pain and Devouring Plague. Mind Vision isn't counted as starting a pull.

### Shaman

Can heal or deal damage. Restoration Shamans get the healer card; Elemental and Enhancement Shamans
get the DPS card. Lightning Shield counts for Upkeep, and isn't counted as a healing shield.
Enhancement Shamans who fight mostly in melee get the melee treatment: Movement as info only and
swings in Activity.

### Mage

A caster with cast times, so watch Movement and Casting most closely. Detect Magic isn't counted as
starting a pull. Counterspell counts toward Interrupts. Ice Block, Ice Barrier and Mana Shield are
the defensives the danger box looks for.

### Warlock

Pets summoned during the run are credited to you: their damage counts in your Damage share and
appears as "(pet)" rows on the Spells tab. An interrupt by your pet counts as yours. Upkeep watches
your DoTs, which makes it one of the most useful categories for Affliction. Warlocks with long casts
also gain a lot from the Movement numbers.

### Rogue

An energy user with a 1.0-second global cooldown, so Activity is judged on the shorter cooldown and
"Not enough energy" refusals don't count. Resource shows time at full energy. Movement is info only
for melee, and the lost-swing count is a good measure of how often you were out of reach. Slice and
Dice and Rupture are what Upkeep looks for.

### Hunter

Several things are handled for Hunters specifically:

- Auto Shot doesn't count as a press, a cast or a global cooldown, but each shot keeps you busy for
  up to 2 seconds in Activity.
- Feign Death shows up in the combat log as a death on this client. If you act again within 20
  seconds without being resurrected, the app drops the false death. Feign Death also counts as a
  defensive.
- A pull started by your pet is your pull, and your pet's damage counts as yours.
- Hunter's Mark, Eagle Eye and the tracking spells aren't counted as starting a pull.
- The group placing treats Hunters as unable to interrupt or dispel, so Utility doesn't count for
  them there. On your own card, Interrupts only counts in a run where you interrupted something.

## A tour of the app

The app reloads by itself when the game saves, so if it is open when you `/reload`, the new run
appears and opens on its own after a second or two.

### The main window

The left side has five pages at the top: Dungeons, Raids, Fights, Habits and Profile. In Dungeons and
Raids it lists each one with its visits, labelled by date, time, score and grade. The theme and day or
night are at the bottom, with Settings, Reload and Share. "Scoring weights..." is in Settings.

A dungeon's or raid's own page has three tabs:

- History draws your score on every visit over the grade bands, calls out the best and the last, names
  the measure that keeps costing you points, and lists every visit. Double-click one to open it. A visit
  with under 60 seconds in combat is listed but not compared.
- Bosses has the average boss score on the last visit, the route with the weakest boss circled, and each
  boss's score visit by visit. "Show the fight" opens it on the timeline.
- Records has your best score, fastest clear, least time in combat, most killing blows, highest damage
  per second in a fight, longest S streak and deathless visits, and says when the last visit's top fix
  would have beaten your best score.

### A visit

A visit has five tabs.

- Debrief shows your score, grade and verdict, the one fix to make with the next two, the main measures,
  and where the points went. Every category is in the All categories drawer. A grid has every fight with
  its score and circles the ones to review; pick one to score just that fight. "Show me" opens the
  timeline there. The player picker at the top shows anyone else's card.
- Timeline has the run on one clock, with a fight picker and every idle moment, longest first (see
  below).
- Pulls shows how safely you went into them, the one pull to fix, the run pull by pull with your mana
  under it, and who pulled. The All pulls drawer has every pull with its mobs.
- Spells ranks your abilities by damage and by healing, with casts, casts per minute, refusals, crits,
  overhealing and share, for any player, over the whole run, bosses only or trash only. Picking a spell
  highlights its casts on the timeline.
- Group shows where you placed and what would move you up, the podium, everyone's card with their
  strengths, weaknesses and map, and the awards. The Edit roles drawer lets you correct a class or role.
  Your own role there decides which scorecard you get.

### The timeline

The timeline has lanes for pulls, deaths, your Response (healers) or Activity (everyone else), your
casts and spells, your presses (white for a key, orange for a click, red under mashing), your movement,
and health for you and the tank. The Group row opens to everyone else's spells and health. Scroll to
zoom, drag to pan and double-click to see the whole run. Hover for details.

### The Fights page and the overlay

Each fight's page shows how much of the damage you could have done you did, the verdict, the biggest
gap, the key figures, where the rest went, what went well, the pull, the danger box and your group. The
All the details drawer has your abilities, cooldowns (Spell, CD, Used, Possible, Missed, Excused, Free,
Lost), auto attacks, buffs, failed casts, idle time and resources. The app keeps your last 5,000 fights.
Fights saved before the newer columns existed show "-" in them.

The overlay is the card that slides in after each fight: the share of your possible damage, the verdict,
and the biggest gap or your death. It needs the game in borderless fullscreen; exclusive fullscreen hides
it. You can change how long it stays (4 to 30 seconds, 12 by default), keep it up, pick its side or drag
it where you want it. It never takes focus from the game.

### The Habits page

Covered in [Habits](#habits) above. While it is open, it refreshes after every fight.

### The Profile page

The Profile page is who you are as a player over the last 15 days, for the character you played
most recently. It needs 10 fights in those 15 days. With fewer it shows one line ("Your profile needs
10 fights from the last 15 days (4 so far)") and the Earlier list, open. Top to bottom:

- The crest is a block framed in gold rules at the top left. Its first line is your race, class and
  level. Under it is your title, large (see [How the Profile makes your title](#how-the-profile-makes-your-title)),
  then a second line that names your next two strongest traits in plain words ("Fights without pause,
  wins one on one."). Under that are up to two feats from the window, best first, each with its enemy
  where it is known (never a player's name): your closest win ("won after dropping to 2% health
  against Bloodscalp Berserker"), your biggest pull beaten, your longest run without a death, boss
  kills, your best damage per second, fights won against players, levels gained, your longest sitting.
  A feat has to be good by its own measure to show, so there may be one or none. Under the crest, when
  most of the window's fights were summed up by an older version (before 0.18.0), a quiet line says
  "Based on older fight records. Import your combat logs in Settings for the full picture."
- The hero figure is the number behind your title: the figure of the trait that gives it its epithet,
  with what it is ("25 s between one fight and the next"). A chip beside it says how far it moved
  against days 16 to 30 when it is a share. Under it is a short label such as "Careful world damage
  dealer." (from your deaths per hour, usual pull, cooldowns used, where you fight most and your main
  role) and, when your title was another one in days 16 to 30, "Before:" and that title. If no trait
  has reached its first tier yet, the hero figure is your main role's share of fight time instead.
- The plate sits beside the hero figure. It has one of two tabs, "Worth changing" or "Going well", and
  says one thing, the first rule that applies:
  1. You die in 15% or more of your fights.
  2. The ability that lost the most damage by sitting ready (1% of your damage or more), with what it
     cost, and the next two under it. Not for a healer, and not when you reach 90% or more of your
     possible damage.
  3. Five or more close calls with a defensive ready, naming the spell.
  4. A harmful spell you know and have not cast. A spell that needs a chance (an enemy of a type, an
     enemy under 20% health, an avoided attack) counts only in fights where its chances are known.
  5. A healer's overheal of 40% or more.
  6. Under half your possible cooldowns used.
  7. Input gone badly wrong: 60% or more of 500 or more key and click presses were clicks, or 40% or
     more of 500 or more casts tried were refused. It shows only if it was not already so, at the same
     figure or worse, in days 16 to 30. It is the last of the fixes, and the only place input reaches
     the plate.

  If none applies, the tab reads "Going well": a healer's overheal as it stands ("Your healing
  lands"), or, with 10 or more fights where you did damage and 90% or more of your possible damage
  reached, "Your last 15 days were clean". Otherwise there is no plate at all. It stays hidden while
  your possible damage is under 90% or unknown, rather than say there is nothing to fix. The plate's
  button opens Habits.
- Signature is your top five spells by share of damage (by share of casts for a healer), with melee
  shown as "Melee (auto attack)" and its swings, and your usual opening of three casts. The All spells
  drawer under it lists every spell with its casts and share, closed by a total of 100%.
- Role mix is your share of fight time as damage, healer and tank, with the average score of your
  graded runs in each. Where you fight is the share in dungeons, raids, the open world and PvP.
  A chip such as "+12 pts vs the 15 days before" sits on a share that moved 5 points or more against
  days 16 to 30.
- How you fight, under those on the right, is a card of rows that suit how you play, five of them and
  then Cut short by moving. The rows depend on your main role. A damage dealer sees time between
  fights, wins on the edge, wins against three or more, auto attack against abilities and possible
  damage reached. A healer sees overheal, share of the group's healing, fights nobody died and
  dispels. A tank sees hits avoided, damage taken a second, usual pull, lowest health and interrupts.
  If 25% or more of your fights are against players it is the PvP rows instead: fights won, fights
  where the enemy broke off, length, wins on the edge and deaths. The title's own row comes first. A row
  with no data gives way to your next best trait, and a figure is never shown twice. Cut short by moving
  (casts the game cut because you started to move) is always there when a recorded run knows it. Each row
  is one trait's figure, so the title and the card cannot disagree. Share rows have a bar and a chip
  against days 16 to 30.
- Hands is a closed drawer at the foot of the left column: keys against clicks, presses per minute and
  refused presses, over your recorded runs. It has no colour, no chip and no ring, and it is never part
  of your title, the hero figure or the crest, because keys and clicks are how you hold the mouse, not
  how your character plays. It reaches the plate only when badly wrong (rule 7 above). It needs a
  recorded run: play with the add-on on and `/reload`. Without one the drawer is not there.
- Where your time goes, under both columns, is how you spent your hours, from what the add-on counted (add-on 0.6.0, the
  one from 0.22): your Player Type, one bar, and each part's share and hours, with a chip when it moved 5 points or more
  against the 15 days before. It fills in after a `/reload` or logout and needs 5 hours of play. Away time (AFK, or 3 minutes without moving, casting
  or fighting outside an instance) is left out. If counting began inside the 15 days it says so, and nothing is compared. It
  shows even when there are too few fights for the rest of the page. See [How your Player Type is picked](#how-your-player-type-is-picked).
- Trade, a drawer under Where your time goes, is your auction house in the last 15 days, from the add-on's counts (add-on
  0.7.0): how long the auction house window was open and its share of your play, how many items your sale mails held, and your
  profit or loss, with the profit per hour there from 10 minutes on. Beside them are the two sums it comes from: money from auction
  mails (sales and refunded bids, after the house's cut) and money spent while the auction house was open (buying, bids,
  deposits). Things you bought and kept count as spent, and a sale counts when you collect its mail, so it can land after what it
  cost you. When a sale mail doesn't say how many items it held, the count says "or more"; when none does, it is a dash. Gold
  stays off the crest, the titles and Share.
- All traits is a drawer under both columns, open when the page is wide. It lists every trait with a
  score above 0, by family, with its figure, its tier in a gold frame (the epithet you have earned, empty
  under the first tier), a line saying what the figure counts, and a bar of its score with the figures it
  begins and ends at under it. Hover a row to see how it is worked out, your own numbers ("You: 681 of
  1,209 fights") and where each tier begins. The app's author chose the two ends of every bar by hand; they
  don't compare you with other players. Its title counts them: "All traits (14)". It uses two columns from 700 px of width. If you open
  or shut it yourself, it stays as you left it.
- Character sheet is a closed drawer under All traits. It needs the add-on from 0.21 (add-on 0.5.0), a full
  restart of the game after installing it (a new add-on file is not picked up by `/reload`), then a
  `/reload` or logout. Until then the drawer says so. It is what the character carries at the
  add-on's last reading: after you enter the world, a few seconds after you change gear or level, and at `/reload`.
  Where the game hides or zeroes the stats (in combat, at a full logout), the last whole reading stays, with its time.
  Only its measured figures come from the last 15 days.
  - Gear: every piece on one line of item levels, the average, how many of each rarity, then each slot
    with the item's name in its rarity's colour, its stats and what it does, every line as the game's tooltip writes it, and a tag
    for an empty slot, the lowest piece, or one that takes an enchant and has none. An item whose link the
    game had not loaded is "name not read yet", and is never called not enchanted. The tooltip lines need add-on
    0.5.2; without them an item shows only its armor, five stats, resistances and weapon damage, and the page says so.
    A line the game shows in red or grey says "not active" ("not met" for a need), a piece at no durability says "broken",
    and "from gear" is left out when a worn piece was not read or is broken, or when it would be more than you have.
    Left out: the item's name and level, how it binds, where it is worn, durability, requirements, price, the list of
    a set's pieces, and who made it, which is never saved.
  - Stats: what your fights measured (damage, healing, swing speed and average swing) beside what the
    game says, then the game's figures. A primary stat's bar is your own total (it compares you with nobody): what
    your gear gives, by rarity, what is your own without gear or buffs (race, class, level and talents), and
    what buffs, enchants and set bonuses added when it was read. The last two need add-on 0.5.2 and a `/reload`;
    until then they are one part. A figure the game hides is a dash.
    What 10 more attack power adds is measured from your own swings: the log has each one's damage before armor, crits and
    glancing. Only fights with the weapon you hold now count, from when add-on 0.6.0 began to record it, and only days whose swings
    spread as that weapon's own roll does, so another weapon before that, or a buff on swings, is left out, and swings under Seal of the Crusader never count. Until 100 swings say it clearly, "estimate" marks the classic
    formula's figure, shown only when that formula lands within 10% of the game's own damage.
    "10 more spell power adds" compares hits of one spell, at one rank and one character level, on one day, at two amounts of spell power,
    with attack power held still. "0" means none was seen. It needs the levels the add-on from 0.22 (add-on 0.6.0) records, and says so until then.
    Healing power is not measured. "How your swings land" counts your misses, dodges, parries, glancing blows and crits against
    what you fought, and a glancing blow against your plain swings on the same enemy: the game does not give your weapon skill, and this is what it does. These need fights summed up by 0.22:
    press **Add fights from my old combat logs** once in Settings.
  - Abilities: casts in fights and each ability's share of your damage, its procs with it, with auto
    attack and the remaining procs and items, so the shares add up. Then the casts that do no damage, and the
    spells you know and did not cast in a fight. The rank you cast, and a flag when you know a
    higher one, come from fights saved by 0.21 or newer.
  - Talents and Legacy: the points you have, by name.
- The one ring. When a trait reached a tier it had not reached in days 16 to 30 (the title's trait
  first, else one in How you fight, else the highest), the page circles it by hand and writes "new:
  Relentless". The circle goes on the tier in All traits while that is open, else on the figure in
  How you fight, else the note sits in the crest's second line. That is the page's one ring, so no
  share chip is ringed then. With no new tier, the one biggest move of a share against days 16 to 30
  is ringed instead (on a tie, the increase).
- Earlier, at the foot, lists your finished 15-day blocks: dates, the title you had (the label for a
  block saved before titles existed), main role, deaths per hour and cooldowns used, and your Player Type when
  it is known, then what your middle fight had: gear, spell power, armor, health and mana, buffs included ("stats not recorded" before 0.22). A block is saved
  once its end is 15 days back, when it has left the current window, and never rewritten. A block with
  fewer than 10 fights isn't saved. A block waits until every run's figures have been read. A block
  with a fight summed up before 0.18.0 isn't saved until that fight has been refreshed (see
  [Upgrading from an older version](#upgrading-from-an-older-version): press **Add fights from my old combat logs** again). Blocks
  already saved stay as they are.

In a narrow window the page makes room. Under 1420 px of window width the hero figure is smaller. When
the page is too narrow for two columns (under about 970 px) the right column goes under the left and
All traits shuts. Narrower still, the plate goes under the hero figure. The page scrolls down and never
sideways.

### How your Player Type is picked

Each part of your time has its own bar, and your type is the part furthest over its bar ("twice its bar" beats "just
over"). The bars differ because a quarter of your time trading is a lot and a quarter of it questing is not. Parts with
20% or more, or over their bar, can follow as the second half: "Huntmaster, and part Errant". With nothing over its bar
you are an Adventurer. The app's author picked the bars by hand; they don't compare you with other players.

| Part | What counts | Bar | Type |
|---|---|---|---|
| Hunting | fights outside instances, and 90 seconds after one | 30% | Huntmaster |
| Questing | 5 minutes after a quest is taken, moves on or is handed in, its fights too | 35% | Errant |
| Dungeons | inside a dungeon | 30% | Delver |
| Raids | inside a raid | 25% | Siegebreaker |
| PvP | battlegrounds, arenas, and any fight with an enemy player, with 90 seconds after it | 25% | Warmonger |
| Professions | each gathering, skinning or crafting action, and 3 minutes after mining, herbs or fishing | 20% | Artisan |
| Auction house and mail | their windows open | 15% | Merchant Prince |
| Travelling | flight paths, and anything outside the rest | 35% | Wayfarer |
| In town | resting, with none of the above | 35% | Hearthkeeper |

### How the Profile makes your title

A title is worked out by fixed rules from your saved fights. There is no AI in it and no chance: the
same fights give the same title.

Every trait is one figure of the window's fights, for example the median seconds between fights for
Tempo, scored from 0 to 100 between a low and a high anchor. Tier 1 begins at a score of 35, tier 2 at
60 and tier 3 at 85, and each tier has its own epithet. A trait needs a minimum sample (the Needs
column: fights, casts, swings or hits, whichever it counts). With fewer, or with data the saved fights
lack, it has no score and is left out, never guessed. A trait that doesn't suit your main role (a
healer has no melee share) is left out too. Where a trait has two figures, "/" means both must be known
and the weaker one scores, and "or" means the better known one scores.

| Family | Trait | What it measures | Score 0 to 100 | Needs | Epithets (tier 1, 2, 3) | Roles |
|---|---|---|---|---|---|---|
| Healing | Overheal | of your healing cast on full health | 45% to 10% | 20 | Sparing, Measured, Unwasting | healer |
| Healing | Fights nobody died | of group fights with nobody dead | 70% to 98% | 20 | Reassuring, Faithful, Saving | healer |
| Tanking | Hits avoided | of swings at you missed, dodged, parried or blocked | 10% to 35% | 200 | Braced, Immovable, Impregnable | tank |
| Pace | Time between fights | between one fight and the next | 120 s to 15 s | 30 | Steady, Tireless, Relentless | all |
| Pace | Wins under 15 seconds | of your wins took under 15 seconds | 10% to 45% | 30 | Quick, Swift, Lightning | all |
| Pace | Fight length | is your usual fight | 45 s to 120 s | 30 | Patient, Enduring, Everlasting | all |
| Pace | Longest sitting | fights in your longest sitting | 40 to 200 | 30 | Dogged, Unresting, Unwearied | all |
| Pace | Longest run without a death | fights in a row survived | 15 to 200 | 30 | Surviving, Unfallen, Deathless | all |
| Nerve | Wins on the edge | of your wins came after dropping under 35% health | 5% to 25% | 30 | Daring, Fearless, Unyielding | all |
| Nerve | Wins under 10% health | wins under 10% health per 100 wins | 0.2 to 1.7 | 100 | Lucky, Defiant, Death-Cheating | all |
| Nerve | Deaths and lowest health | deaths per 100 fights; is your average lowest health | 8.0 to 0.0 / 50% to 85% | 30 / 30 | Guarded, Unbroken, Untouchable | all |
| Nerve | Close calls answered | of close calls answered with a defensive | 30% to 90% | 10 | Wary, Cool-Headed, Unshaken | all |
| Nerve | Wins against three or more | of your wins alone were against three or more | 8% to 40% | 30 | Bold, Overrunning, Unstoppable | all |
| Nerve | Wins one on one | of fights one on one won | 70% to 97% | 20 | Sure, Deadly, Peerless | all |
| Victory | Fights won | of your fights end with the kill | 70% to 97% | 30 | Proven, Victorious, Conquering | all |
| Victory | Nobody got away | of fights end with nobody getting away | 80% to 99% | 30 | Dogging, Hunting, Inescapable | all |
| Victory | Boss kills | bosses beaten | 3 to 25 | 10 | Giant-Felling, Throne-Toppling, Mountain-Breaking | all |
| Victory | Player fights won | of fights against players won | 35% to 75% | 10 | Feared, Dreaded, Warlike | all |
| Victory | Most beaten enemy | of the enemies you beat are of one kind | 8% to 30% | 30 | Vengeful, Merciless, Exterminating | all |
| Weapon | Melee share | of your damage is your weapon's own swing | 30% to 65% | 30 | Iron, Steel, Blade-Sworn | damage, tank |
| Weapon | Auto shot share | of your damage is automatic shots | 25% to 60% | 30 | Keen, Far-Sighted, True-Shot | damage, tank |
| Weapon | Ability share | of your damage is your abilities | 60% to 95% | 30 | Gifted, Fierce, Spellforged | damage, tank |
| Weapon | Top ability's share | of your ability damage is one ability | 35% to 75% | 30 | Devoted, Single-Minded, Masterful | damage, tank |
| Weapon | Main damage abilities | abilities with 5% or more of your ability damage | 2 to 8 | 30 | Adaptable, Cunning, Many-Handed | damage, tank |
| Weapon | Critical hits | of your hits crit | 8% to 30% | 500 | Fortunate, Savage, Fatebound | damage, tank |
| Weapon | Proc and item share | of your damage is procs and items | 8% to 30% | 30 | Charged, Crackling, Storm-Touched | damage, tank |
| Craft of play | Possible damage reached | of possible damage reached | 75% to 95% | 30 | Honed, Precise, Flawless | damage, tank |
| Craft of play | Cooldowns used | of possible cooldowns used | 50% to 90% | 50 | Prompt, Eager, Unsparing | damage, tank |
| Craft of play | Casts not cut short | of casts not cut short by moving | 97% to 100% | 200 | Grounded, Unmoved, Rooted | all |
| Craft of play | Pulled with your usual buffs | of fights pulled with your usual buffs | 70% to 98% | 30 | Ready-Armed, Blessed, Oathbound | all |
| Craft of play | Interrupts | interrupts per 100 group fights | 5.0 to 40.0 | 20 | Watchful, Silencing, Spellbreaking | all |
| Company | Fights alone | of your fights are alone | 55% to 97% | 30 | Wandering, Lone, Sovereign | all |
| Company | Fights in a group | of fights in a group | 50% to 97% | 30 | Loyal, Stalwart, Sworn | all |
| Company | Groupmates out-damaged | of your groupmates out-damaged, on average | 30% to 90% | 20 | Rising, Leading, Commanding | damage, tank |
| Company | Help for the group | dispels on others per 100 group fights; of the group's healing on others is yours | 3.0 to 25.0 or 10% to 35% | 30 or 20 | Merciful, Guarding, Selfless | all |
| Company | Benefactor | strangers buffed, healed or cleansed | 5 to 75 | 5 | Kind, Generous, Great-Hearted | all |
| Company | Lifegiver | revives cast | 2 to 25 | 3 | Rousing, Rekindling, Life-Giving | all |
| Road | Zones fought in | zones with five fights or more | 5 to 22 | 30 | Roaming, Far-Travelled, Worldly | all |
| Road | Different enemies beaten | different enemies beaten | 80 to 500 | 30 | Curious, Seasoned, All-Seeing | all |

Your title is `<epithet> <class noun> of <where>`:

- The epithet is the one for your best trait that has reached tier 1. The next traits that name you
  (for the second line) must come from other families, so two players with the same best trait still
  differ. On a tie the trait nearer the top of the table wins, role-only ones first.
- The class noun comes from your class and the talent tree you played most in the window (your
  snapshot's if the fights don't say). The tree decides it, so two paladins differ:

| Class | Talent trees |
|---|---|
| Warrior | Arms: Warblade, Fury: Reaver, Protection: Ironwall |
| Paladin | Holy: Lightmender, Protection: Shieldsworn, Retribution: Crusader |
| Hunter | Beast Mastery: Packwarden, Marksmanship: Deadeye, Survival: Trailstalker |
| Rogue | Assassination: Nightblade, Combat: Swashblade, Subtlety: Veilwalker |
| Priest | Discipline: Oathkeeper, Holy: Dawnkeeper, Shadow: Duskcaller |
| Shaman | Elemental: Stormbinder, Enhancement: Thunderfist, Restoration: Tidemender |
| Mage | Arcane: Spellweaver, Fire: Emberwright, Frost: Rimecaller |
| Warlock | Affliction: Hexbinder, Demonology: Pactkeeper, Destruction: Cinderlord |
| Druid | Balance: Starcaller, Feral: Wildfang (Thornhide when you tank), Restoration: Grovekeeper |

  With no known tree it is your main role's noun for the class (Crusader for a damage paladin), and a
  Slayer, Mender or Bulwark when the class has none for that role. With no known tree and a main role
  under 60% of your fight time, you are a Champion.
- Where is the first that applies:
  - Bane: one creature type is 40% or more of the foes whose type is known, and types are known for half
    of all foes: "Bane of the Undead", "Bane of Beasts", "Bane of Demons", "Bane of Dragonkin", "Bane of
    Elementals", "Bane of Giants". It stands in place of "of": "Relentless Crusader, Bane of Beasts".
  - Scourge: one named people or order is 15% or more of the enemies you beat, at least 30 kills across
    at least two kinds of name: "Crusader, Scourge of the Defias". Only a list of known peoples counts,
    since a first word may as well be a place. Fights against players are left out.
  - A zone: 25% or more of your fights: "of the Arathi Highlands".
  - A place: 50% or more of your fight time in one kind of place: "of the Wilds", "of the Depths", "of the
    Great Halls", "of the Battlefield".
  - "of the Long Road": no place reaches 50% and your Zones fought in is tier 2 or better.
  - Nothing, when none is known.

A window where no trait has reached tier 1 has no epithet, so the title is a bare "Crusader of the
Wilds".

Named titles are rarer. When two particular traits are both at tier 2 or better, the title becomes a
named one, the first of these that applies, with your class and place after it: "the Lone Storm,
Crusader of the Arathi Highlands". The better scoring of the two is the title's trait for the hero
figure and the card.

| Traits (both tier 2 or better) | Title |
|---|---|
| Wins on the edge + Wins against three or more | the Cornered Lion |
| Wins on the edge + Longest run without a death | the One Who Walks Away |
| Deaths and lowest health + Longest run without a death | the Unfelled |
| Wins under 10% health + Fights alone | the Last One Standing |
| Fights alone + Time between fights | the Lone Storm |
| Fights alone + Zones fought in | the Long Walker |
| Time between fights + Fights won | the Reaping Wind |
| Wins under 15 seconds + Critical hits | the Sudden End |
| Melee share + Fight length | the Grinding Wheel |
| Melee share + Wins one on one | the First Blade |
| Wins against three or more + Proc and item share | the Gathering Thunder |
| Nobody got away + Most beaten enemy | the Old Grudge |
| Boss kills + Groupmates out-damaged | the Crownbreaker |
| Player fights won + Wins on the edge | the Nerveless |
| Player fights won + Wins one on one | the Arena's Answer |
| Top ability's share + Possible damage reached | the Perfectionist |
| Main damage abilities + Cooldowns used | the Full Quiver |
| Zones fought in + Different enemies beaten | the Walking Atlas |
| Fights in a group + Help for the group | the Open Hand |
| Lifegiver + Benefactor | the Open Heart |
| Lifegiver + Help for the group | the Second Dawn |
| Lifegiver + Fights in a group | the Last Hope |
| Benefactor + Zones fought in | the Wayside Saint |
| Benefactor + Fights alone | the Stranger's Friend |
| Interrupts + Close calls answered | the Cold Eye |
| Fights nobody died + Overheal | the Quiet Miracle |
| Fights nobody died + Fights in a group | the Reason They Lived |
| Hits avoided + Deaths and lowest health | the Door That Holds |
| Wins against three or more + Hits avoided | the Breakwater |

Titles are saved with each finished 15-day block, so Earlier reads as a history of who you were.

### What the Profile counts

- Alone means no group, no more than 10% of your damage done by others (players, their pets or
  friendly characters), and no more than 10% of the damage you took healed by players outside your
  group or their pets. A fight with outside help is a helped fight, not an alone one, even without a
  group. Fights alone and fights in a group feed Fights alone, Fights in a group, Wins one on one and
  Wins against three or more.
- Help for others (dispels, healing and your share of it) leaves out yourself, your pets and your
  guardians, and a dispel of an enemy, which is a purge. Your share of the group's healing is yours
  against what the group gave each other, and Help for the group uses it for non-healers only.
- **Lifegiver** counts every revive you cast, in your group or not; the log does not say whether it was accepted.
- **Benefactor** counts each stranger (a player outside your group) you helped, once a day. A buff, a heal or a dispel counts only when you
  cast it on that very player, so an aura that radiates does not, nor does a buff the game logs again when somebody
  comes back into range. Buffs on your own group are shown but do not score. No names are saved. Click
  **Add fights from my old combat logs** in Settings once to fill it in.
- Groupmates out-damaged is the share of groupmates with less damage than you, averaged over your group
  fights. Anyone who did no damage, or healed more than that, is left out, so 50% is an even share in a group of any size,
  though tanks are easier to beat.
- Help for the group shows as Share of group healing or Dispels on others, whichever scores.
- Some figures are totals of the 15 days (bosses, zones, enemies, Benefactor, Lifegiver), so playing more
  raises them.
- Blocks saved by 0.19 or older keep the scores of the rules they were saved with.
- A close call is a fight where your health fell under 35%. It is answered if you cast a defensive on
  yourself within 10 seconds before or after your lowest moment. It counts toward Close calls answered
  only if you answered it or a defensive sat ready.
- Feign Death is not a death. This client logs it as one, but the app removes it, so it doesn't count
  in deaths per hour, longest run without a death, deaths and lowest health or the plate's 15% rule,
  and your buffs stay on through it for Pulled with your usual buffs and Upkeep.
- Time between fights counts gaps inside a sitting only. A gap of 30 minutes or more starts a new
  sitting, which Longest sitting counts.
- A fight won is one where every enemy died and you lived. Nobody got away is the rest of the fights
  you lived through, an enemy you ran past included, so it leaves out fights where you did no damage.
- Fights saved by an older version (before 0.18.0) lack some of what the traits need (a group, help,
  chances, difficulty). Those traits have no score until the fights are summed up again, and the page says so under
  the crest. In Settings, press **Add fights from my old combat logs** once (or run `replay`). It sums up
  again every saved fight whose combat log is still in the Logs folder, and it also adds fights you played
  while the app was closed, so the history grows past what the app saw live. It can only use the logs you
  still have.

### Tray mode and the command line

Run `projectArthas.pyw live` to keep the app in the system tray while you play, with the overlay. Its
menu opens the main window or shows the last fight again.

On the command line, `projectArthas.pyw runs` lists saved runs, `report` prints the latest run's
scorecard (`report 5` for run 5, `--role healer`, `--role dps` or `--role tank` to choose a card),
and `replay` adds fights from old combat logs to the Fights page and learns your spell book from
them.

### Files the app keeps

Everything is in `%APPDATA%\dips-score`: `weights.json` and `classes.json` (your settings),
`fights.jsonl` (the last 5,000 fights), `spells.json` (a spell book per character) and `help.jsonl` (what you did for
other players, without their names).
`profile_history.json` holds the Earlier blocks of the Profile page, and `profile_runs.json` what it
takes from each recorded run, kept 60 days because the add-on keeps only its last runs.
`spells.json` replaced the older `cooldowns.json`, which is no longer read. Run `replay` once to
rebuild your spell books from old combat logs.

## If you already use a log parser

A log parser and projectArthas read the same combat log, so for damage, healing and deaths they agree.
What projectArthas adds comes from the add-on, and none of it is in the log:

- presses, including the ones the game refused, with the reason paired from the log
- key versus click, key hold times and mashing bursts
- the exact moments you started and stopped moving, matched to the casts that broke
- your own combat start and end, which is how it splits a run into fights
- cast timing on your side, synced to the log within a few milliseconds
- your spell list with base cooldowns, gear, talents and durability, which the log doesn't carry on
  this client

From the log itself it also works out a cooldown sheet with
possible and missed casts per fight, excused against unexcused ready time, interrupt chances with
reaction times, tank pickup times, and how much of a damage change came from gear.

Your number is judged against fixed thresholds, so it means the same thing in an easy run and a hard
one, and you can compare yourself with yourself over time.

What it doesn't try to do: it has no threat data, so "who a mob went for" is the first player it
hit. The killing blow is the killer's last hit. The dungeon view shows one character at a time, the
one that saved most recently. And it only sees other players through the combat log.

## Limits worth knowing

- The thresholds are a first guess and may change in later versions. You can change the weights
  yourself.
- The combat log only reports someone's health when they are hit, healed or swing in melee. A
  ranged player who takes no damage has gaps in their health line. Each reading is treated as valid
  for at most 5 seconds.
- The game only saves add-on data on `/reload` or logout. A crash before that loses the recording,
  and the snapshot only reaches the app after a save. Fight cards don't wait for a save.
- Without a combat log that covers the run, the healer and tank scorecards can't be worked out at
  all. The DPS scorecard falls back to the add-on categories.
- Without Advanced Combat Logging, Group health, Response, Resource, Pacing and Positioning can't be judged,
  and Survival only counts deaths.
- Presses on action bars drawn by other add-ons are recorded without a key or click source.
- Pets are credited to their owner only when the log shows them being summoned.
- Positioning's "behind the target" assumes how this client's log writes facing, which hasn't been
  confirmed on real data. Positioning is info only by default.
- Running out of mana to exactly 0% isn't caught by the low-mana penalty on the healer card. The
  refused-for-mana penalty still applies.

## Questions

### Does it slow the game down?

The add-on writes one short line of text per event and does no analysis in game. The snapshot runs
when you enter the world and when you log out. All the scoring happens in the desktop app.

### Does it play for me or change anything in game?

No. The add-on records, prints its chat line, and turns on the combat log and Advanced Combat
Logging if you leave that setting on. The app only reads files from your game folder and finds the
game window to place the overlay.

### Do I need to `/reload` after every fight?

No. Fight cards, the overlay and the Habits page come from the combat log, which the game writes
while you play. You only need a `/reload` or logout for the dungeon scorecard (your presses and
movement) and for a new character snapshot.

### Can I use it on several characters?

Yes. Spell books and Habits are kept per character. The dungeon view shows the character that saved
most recently, so log in on the one you want to review and `/reload`.

### Why did my score change after I edited the Group tab?

Your role decides your scorecard, and other players' roles decide the group placing. Correcting a
role rescores the run.

### Why does a category say "needs Advanced Combat Logging"?

The log for that run had no health, power or position readings. The add-on turns the setting on at
login, but if the game wouldn't let it, chat told you to turn it on in the options. Runs logged
before it was on stay that way.

### Why does my score say "no clock anchor: times are a guess"?

The add-on couldn't take a clean clock reading, which can happen when the game stutters heavily.
Scores still work, but the timings are less exact.

### Why is a cooldown I never use listed as missed?

It is in your spell book, either because you cast it in the last 7 days or because the snapshot
says you know it. If you are holding it on purpose and it has a cooldown of a minute or more, it
only counts on bosses.

### Do I need to keep the app open while I play?

No. You can open it after the run and it scores everything from the saved files. Keep it open (or in
the tray) if you want the overlay after each fight and the live Fights page. The add-on's chat line
works either way.

### Can I score raids?

Turn on "Raids" in the add-on settings and it will record them. The scorecards were designed and
tuned around five-player dungeons.
