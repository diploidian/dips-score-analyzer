# The dips-score guide

dips-score tells you how well you played, and what to change next time. It looks at the parts of
your play you control: what you pressed, when you pressed it, whether the game accepted it, how
quickly you reacted when someone in your group got into trouble, and which cooldowns you left
sitting on your bar.

It has two parts that work together:

- The dips-Score add-on runs inside the game. It records your own inputs while you play: action
  presses and whether each came from a key or a mouse click, how long you held keys, when you
  started and stopped moving, and every stage of every cast. It also saves a snapshot of your
  character (level, spells, gear and talents) and prints a short line in chat after each fight.
- The dips-score app runs on your desktop. It reads what the add-on saved, lines it up with the
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
the edge of the game window about 2 seconds after the last enemy dies. It opens with one sentence
about the fight ("Killed by Defias Pillager: Fireball for 412.", or "Clean fight: 94% of the damage
that was possible."), then your numbers, the cooldowns you missed, what went well and what to
improve. Even with the app closed, the add-on prints a line in chat:
`14 s - 31 presses (4 clicks), 2 refused, 1 interrupted`.

Over time, the Habits page looks across your last 40 fights and tells you what you keep doing
right, what keeps costing you, and whether your damage went up because you played better or
because your gear did.

For dungeons, the whole group also gets ranked on what the combat log shows, with a podium, an MVP
and a handful of awards and roasts. Each run is kept, so you can watch your score for a dungeon move
over a week of practice.

## Setting it up

This takes about ten minutes the first time.

1. Install Python 3.13 from python.org, then run `pip install PyQt6` in a terminal.
2. Copy the `addon/dips-Score` folder into your game's `Interface/AddOns/` folder. If you keep the
   project somewhere permanent, you can link the folder instead, so updates arrive by themselves:
   `New-Item -ItemType Junction -Path "<WoW>\Interface\AddOns\dips-Score" -Target "<project>\addon\dips-Score"`
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
8. Double-click `dips-score.pyw`. It finds your newest run and opens it.

Installed and want the short version, with fixes for common problems? See [First run](FIRST-RUN.md).

The app looks for the game in `D:\Program Files (x86)\World of Warcraft\_forever_`. If yours is
elsewhere, it asks for the folder the first time and remembers it. You can change it later in
Settings (the cog), under Game folder. From a terminal, `--wow "<your folder>"` or the `DIPS_WOW`
environment variable still override it.

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

In the settings you choose where recording starts by itself: dungeons (on by default), raids,
scenarios and delves, or everywhere else. Two more switches, both on by default: the chat line after
each fight, and turning the combat log on when you log in. The add-on only ever turns the log on. It
does this once per login, so if you type `/combatlog` to turn it off, it stays off until you log in
again.

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

It records your own character only. Other players' inputs are never visible to an add-on, and pet
casts aren't recorded.

### The character snapshot

Beside the run log, the add-on saves what the game knows about your character: level, race, class,
your spells with their base cooldowns and whether they hit enemies, the item level of each filled
gear slot, and the points in each talent tree. It takes the snapshot 3 seconds after you enter the
world (spell and item data may not be ready on the first frame) and again at logout or `/reload`. If
a list comes back empty at logout, the earlier good one is kept.

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
the app shifts everything by the median gap. The Score page shows the result in a line such as
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

Every category that scores below 85 has a tip attached. The scorecard shows the tips for your three
lowest categories, under "Work on". The tips name specifics where they can: the refusal reason you
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

The overlay lists them in one line, such as "Missed: Judgement x2, Exorcism x1".

### Idle time

Idle time is a gap of 2.5 seconds or more with nothing cast, while you weren't moving or stunned and
had the resource to act. Half of it counts as lost damage, and only if you have a filler: a damage
spell you cast twice within 2 seconds, or a confirmed cooldown under 4 seconds. Without a filler
there was nothing to press, so nothing is lost.

### The danger box and defensives

When your health falls under 35%, the card shows a danger box with the hits that did it. It also
names the defensives that sat ready and unused: off cooldown at your lowest moment, and not cast in
the 10 seconds before it. Only spells in your spell book are judged, so a defensive you don't have
costs nothing. A defensive the book has no cooldown for is assumed to have 300 seconds.

### Your spell book

The app keeps a spell book for each character, by spell name, since every rank has its own ID. It
learns each cooldown from your casts: it keeps the 10 shortest gaps of 2 seconds or more between two
casts, and the cooldown is the shortest gap that two others agree with (within 5%). So one quick
cast after a cooldown reset can't set it. A spell you ever cast twice within 2 seconds has no
cooldown. When the character snapshot has the game's own cooldown for a spell, the shorter of the
two is used. The snapshot also means a cooldown you have never pressed can still show as missed.

"Best previous on this target" only compares fights within one level of this one, so levelling up
doesn't hand out records.

## Habits

The Habits page looks at the last 40 fights of the character you played most recently. Fights where
you healed, or did no damage, are left out of the damage cards.

The header names the character, with level, race, class, spec and gear level from the snapshot,
such as "Mapomimi, level 33 Undead Priest, Shadow, gear 31".
Below it are the session numbers, for the latest stretch of fights with less than 30 minutes between
them: fights, kills, kills per hour, average gap between fights, average rest (time eating,
drinking or bandaging), and average health and mana at the pull.

The trend chart draws your efficiency for each fight, oldest on the left, once there are 5 fights.
A gray line marks a level-up, with the new level on top. Yellow dashes mark a change in gear level.

The cards are green (keep doing it), orange (fix it) or blue (build on it). The ones it can show:

- Efficiency over the last 20 fights against the 20 before, when both halves have at least 5
  fights: dropping or improving by 3 points or more, otherwise steady (75% or more) or stuck low.
- Damage per second up or down 5% or more between the two halves, split into the part from your
  play (the change in efficiency) and the rest, which moved with gear, level and what you fought.
- The cooldowns that lost the most damage, and swings lost per minute for melee.
- Your most common failed-cast reason, and the pull buffs you usually have but sometimes forget.
- Deaths, and mana at the pull when it averages under 70%.
- A defensive that was ready when you were low.
- Damage spells you know and haven't cast in these fights (up to 3 are named), and empty gear
  slots.
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

The switch at the top has three modes: Dungeons, Fights and Habits. In Dungeons, the left side lists
your dungeons, each with its visits labelled by date, time, score and grade. "Scoring weights..."
and the settings cog are below.

A dungeon page shows a bar chart of your score on every visit, coloured by grade, and a table with
the length, time in combat, score, bosses, deaths and wipes of each. Double-click a visit to open
it.

### A visit

A visit has five tabs above a timeline.

- Score shows your total, grade, every category with its numbers, the "Work on" tips, a radar chart
  and the sync line. A table lists each fight; click one to score just that fight, or "Whole run" to
  go back. The player picker at the top shows anyone else's group card.
- Group lists every player with class, race and role, where each role came from ("your pick", "from
  the add-on", "talents" or "guessed from spells"), and lets you correct them. Your own role here
  decides which scorecard you get.
- Pulls lists every pull: when, how many mobs and packs, who pulled, how long, and who died. A
  second list shows each mob, its raid marker, who it went for, when it died and who killed it.
- Spells breaks down casts, casts per minute, failures, damage, healing, overhealing, crits and
  share, for any player, over the whole run, bosses only or trash only. Clicking a spell highlights
  its casts on the timeline.
- Summary shows the podium, everyone's placing with the reason, their strengths and weaknesses, and
  their awards.

### The timeline

The timeline has lanes for pulls, deaths, your Response (healers) or Activity (everyone else), your
casts, your presses (white for a key, orange for a click, red for mashing) and your movement, then a
spell row and a health row for every player. Scroll to zoom, drag to pan, double-click to see the
whole run, and shift-scroll to reach everyone's rows. Hovering shows everyone's health at that
moment and who reacted to a sharp drop.

### The Fights page and the overlay

Each fight gets a card with the verdict, its stats, damage left on the table, your group, your best
previous damage on the same target, the danger box, the top findings, your abilities, your
cooldowns (Spell, CD, Used, Possible, Missed, Excused, Free, Lost), auto attacks, buffs, failed
casts, idle time and resources. It keeps your last 5,000 fights. Fights saved before the newer
columns existed show "-" in them.

The overlay is the panel that slides in after each fight, with the verdict on top and the Missed
line below your numbers. It needs the game in borderless fullscreen; exclusive fullscreen hides it.
You can change how long it stays (4 to 30 seconds, 12 by default) and which side it appears on. It
never takes focus from the game.

### The Habits page

Covered in [Habits](#habits) above. While it is open, it refreshes after every fight.

### Tray mode and the command line

Run `dips-score.pyw live` to keep the app in the system tray while you play, with the overlay. Its
menu opens the main window or shows the last fight again.

On the command line, `dips-score.pyw runs` lists saved runs, `report` prints the latest run's
scorecard (`report 5` for run 5, `--role healer`, `--role dps` or `--role tank` to choose a card),
and `replay` adds fights from old combat logs to the Fights page and learns your spell book from
them.

### Files the app keeps

Everything is in `%APPDATA%\dips-score`: `weights.json` and `classes.json` (your settings),
`fights.jsonl` (the last 5,000 fights) and `spells.json` (a spell book per character).
`spells.json` replaced the older `cooldowns.json`, which is no longer read. Run `replay` once to
rebuild your spell books from old combat logs.

## If you already use a log parser

A log parser and dips-score read the same combat log, so for damage, healing and deaths they agree.
What dips-score adds comes from the add-on, and none of it is in the log:

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
- Without Advanced Combat Logging, Group health, Response, Resource and Positioning can't be judged,
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
