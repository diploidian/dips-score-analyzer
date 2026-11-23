# dips score: a coach that watches your hands

Most WoW tools tell you what happened in a fight. dips score also tells you what you did to make
it happen: which buttons you pressed, which ones the game refused, how long you stood still with
nothing cast, how many seconds the tank sat at 40% before your heal started, and which cooldown
spent the boss fight lit up on your bar. Then it grades the run from S to F and names the two or
three things worth fixing first.

This page covers what the app is, what it records and how, how the grade comes from those
records, and what it offers each role and class. The [reference guide](GUIDE.md) has every
threshold and formula, and [First run](FIRST-RUN.md) walks you to your first scorecard.

## Contents

1. [What it is for](#what-it-is-for)
2. [What you get](#what-you-get)
3. [Installing the app](#installing-the-app)
4. [What it tracks, and how](#what-it-tracks-and-how)
5. [From records to a grade](#from-records-to-a-grade)
6. [After every fight](#after-every-fight)
7. [Over weeks of play](#over-weeks-of-play)
8. [Raids, sharing and names](#raids-sharing-and-names)
9. [Why each role would use it](#why-each-role-would-use-it)
10. [Why each class would use it](#why-each-class-would-use-it)
11. [How it compares with a log parser](#how-it-compares-with-a-log-parser)
12. [What it can't do](#what-it-cant-do)

## What it is for

After a bad pull you know the group nearly died, but you rarely know why. Maybe you reacted late. Maybe you reacted on time and the heal was refused because you
were out of range. Maybe you were mashing a spell that was still on cooldown. The combat log can't
separate these, because it only records what reached the game world. Your presses, refusals and
the gap between "someone got hit" and "you started casting" never reach it.

dips score records that missing half from inside the game, joins it to the combat log, and turns
both into a score you can improve on purpose. The score is judged against fixed numbers, not
against other players, so an 82 in an easy run means the same as an 82 in a hard one. That makes
it a fair way to race yourself.

It is built for the Forever client (Interface 16001, the `_forever_` install) and needs no other
add-on.

## What you get

- A grade from S to F for every dungeon run, scored on the card for your role (healer, DPS or
  tank), with the tips for your three weakest categories under "Work on".
- A card that slides in over the game about 2 seconds after each kill, with one sentence about the
  fight ("Killed by Defias Pillager: Fireball for 412." or "Clean fight: 94% of the damage that
  was possible."), the cooldowns you missed, and what to try next.
- A row for every damage cooldown you own, in every fight, with how many casts would have fit, how
  many you made, and roughly how much damage the gap cost.
- A danger box when you drop under 35% health, listing the hits and the defensives you had ready
  and didn't press.
- A Habits page that reads your last 40 fights and tells you whether your damage rose because you
  played better or because your gear did.
- A group placing for dungeons with a podium, an MVP, awards and roasts, so the run is fun to look
  back on as well as useful.
- A line in chat after every fight, even with the app closed:
  `14 s - 31 presses (4 clicks), 2 refused, 1 interrupted`.

## Installing the app

The app comes as a normal Windows installer, `dips-score-setup-<version>.exe`. You don't need
Python, a terminal or any packages: everything the app needs is inside it.

1. Run the setup file. It installs for your Windows account only unless you choose all users, so
   it doesn't need administrator rights.
2. It asks where the game is. Pick the `_forever_` folder, the one with `Logs`, `WTF` and
   `Interface` in it. If the folder has no `WTF` inside, the installer warns you before it goes on.
3. Choose whether you want a desktop icon. The app is in the Start menu as "dips score" either way.
4. Copy the `addon/dips-Score` folder into the game's `Interface/AddOns/` folder.
5. Log in to the game and type `/dscore watch`, then press a few abilities with keys and a few
   with the mouse. Chat prints "key" or "click" for each one, which confirms the add-on is working.

If you ever move the game, open the app's settings (the cog at the bottom left) and change the
folder under Game folders. You can point it at a separate combat log folder there too. The note
under the folders says how many combat logs and saved add-on files it found, so you can tell at a
glance that it is looking in the right place.

For the overlay to show over the game, set the game to borderless fullscreen. Exclusive fullscreen
draws over everything, the card included.

If you'd rather run it from source, double-click `dips-score.pyw` with Python 3.13 and PyQt6
installed. It's the same app.

## What it tracks, and how

The app has two sources and lines them up on one timeline.

### The add-on: your side of the keyboard

The dips-Score add-on writes one short line per event, with a millisecond timestamp. It records:

- every action button press, with the slot, the spell or item, and whether it came from a key or a
  mouse click
- when each key went down and came back up, so it knows how long you held it
- when you started and stopped moving
- when you entered and left combat
- your casts at every stage: sent, began, succeeded, failed, interrupted, channel start and end
- target changes and your deaths
- boss pulls and ends, keystone start and completion
- each group member's name, class, race and group finder role
- notes you drop with `/dscore mark`

It only sees your own character. No add-on can read another player's keyboard.

Key and click are told apart by watching which of the game's handlers fires for the press: the
key binding handler or the button's click handler. A click only counts when the mouse is over the
button. This works on the main bar and the game's extra bars. Bars drawn by other add-ons skip
those handlers, so their presses are recorded with an unknown source.

The add-on also saves a character snapshot: level, race, class, every spell you know with its base
cooldown, the item level of each gear slot, your talent points per tree, and your gear durability
at each pull. That is how the app knows about a cooldown you own but have never pressed.

Recording starts on its own when you enter a dungeon and stops when you leave. You can switch on
raids, scenarios, delves or the open world in `/dscore`. The add-on also turns on the combat log
and Advanced Combat Logging at login, so you never have to remember `/combatlog`.

### The combat log: what happened in the world

Damage, healing, overhealing, health, mana, rage and energy, positions, enemies, kills, buffs,
debuffs, interrupts, dispels and boss names come from the game's combat log. Health, power and
positions are only written with Advanced Combat Logging on, which is why the add-on turns it on
for you.

### Putting the two together

The add-on's clock and the log's clock run separately. At the start of each recording and every
time you leave combat, the add-on catches the frame where the game's second ticks over and writes
both clocks down. At 144 frames per second that reading is good to about 3 ms. The app draws a
line between these readings, which also corrects slow drift over a long run.

Then it checks itself. Each successful cast in the add-on's record is paired with the same cast in
the log. With five or more pairs, it shifts everything by the median gap, and the Score page shows
how well it did, for example "42/45 casts matched, corrected +8 ms, spread -6..9 ms". That
precision is what makes reaction times and "moved just before the cast broke" trustworthy.

### When the data reaches the app

Fight cards, the overlay and Habits come from the combat log, which the game writes as you play,
so they need nothing from you. The dungeon scorecard also needs the add-on's record, which the game
only saves on `/reload` or logout. Do either after a run (the record button's right-click menu has
"Save now (reload)") and the app picks up the run a second or two later and opens it.

A brand new character's first save is picked up too, without restarting the app.

## From records to a grade

### Each category is a straight line between two numbers

Every category has a value that scores 0 and a value that scores 100, with a straight line in
between. Activity, for example, scores 0 at 55% of combat spent busy and 100 at 90%, so 72.5% busy
is a 50. Only time in combat counts, so the run between packs never costs you anything.

The total is the weighted average of the categories, and the grade follows from it:

| Grade | Total |
|---|---|
| S | 90 and up |
| A | 80 to 89 |
| B | 70 to 79 |
| C | 60 to 69 |
| D | 45 to 59 |
| F | below 45 |

### Your role picks the scorecard

A healer is judged on keeping people alive, a tank on holding mobs, and a damage dealer on damage
and the habits behind it. The app takes your role from the Group tab if you set it there, then the
group finder role, then your talents (the tree with the most points), then a guess from your
spells.

| Healer | Weight | DPS | Weight | Tank | Weight |
|---|---|---|---|---|---|
| Group health | 35 | Damage | 20 | Holding mobs | 25 |
| Response | 35 | Activity | 15 | Pickups | 25 |
| Efficiency | 20 | Cooldowns | 10 | Survival | 20 |
| Casting | 10 | Interrupts | 10 | Activity | 10 |
| Hybrid bonus | up to +10 | Casting | 10 | Upkeep | 10 |
| | | Movement | 10 | Casting | 5 |
| | | Survival | 10 | Input | 5 |
| | | Upkeep | 5 | | |
| | | Input | 5 | | |
| | | Resource | 5 | | |

Categories not listed for a role are still shown, as info only. The weights are yours: "Scoring
weights..." in the app has a slider for each, and a weight of 0 keeps the category on the card
without counting it.

### Which source each category uses

Several categories can't be built from the log alone:

| Category | What it measures | Needs the add-on? |
|---|---|---|
| Response | Seconds from a party member's dip under 60% to you starting a heal, HoT or shield on them | Yes: the log shows heals landing, not when you started them |
| Casting | Presses the game refused, with the reason | Yes: refused presses never reach the log |
| Movement | Casts you broke by moving | Yes: the log has no movement start |
| Input | Presses per successful cast (mashing), and how many were clicks | Yes |
| Activity | Share of combat spent casting, channeling, on the global cooldown or swinging | Both |
| Cooldowns | Damage your ready cooldowns would have done | Log, plus the snapshot for spells you never pressed |
| Group health, Survival | Deaths, and time under 35% | Log (Advanced Combat Logging) |
| Damage | Your share of the group's damage, pets included | Log |
| Interrupts | Enemy casts you could have stopped, and how fast you did | Log |
| Upkeep | How long your class's buffs and DoTs were up | Log |
| Resource | Time spent at full rage or energy | Log (Advanced Combat Logging) |
| Holding mobs, Pickups | Who mobs went for first, and how fast you got them back | Log |

The app is careful not to punish what isn't your fault:

- A rage or energy user who presses an ability without the resource is pooling, so "Not enough
  rage" and "Not enough energy" don't count as refusals.
- Healers aren't marked down for queueing the next heal early ("Not yet recovered", "Spell not
  ready yet").
- A dip that someone else healed within 6 seconds is left out of your Response.
- A cooldown of a minute or more held through trash counts as held, not missed.
- Interrupts only count once you have interrupted in a run, since the log can't tell whether your
  class and level give you one, and only spells somebody interrupted at least once are chances.
- Upkeep only judges buffs and DoTs you applied at least once in the run, so a spell you haven't
  learned yet never counts against you.
- Without Advanced Combat Logging, categories that need health or power readings step aside and the
  total is worked out from what's left.

### Tips that name names

Every category under 85 gets a tip, and the card shows the tips for your three lowest. They point
at specifics: the refusal reason you hit most, the player whose dips you were slowest to answer,
the cooldown that sat ready longest, the enemy spell you most often let through. If nothing is
under 85, the card says "Nothing stands out - nice run."

## After every fight

Keep the app open, or in the system tray (start it with `live`, as in `dips-score.pyw live`), and each fight gets a card about 2
seconds after the last enemy dies. It works in the open world too, since it only needs the combat
log.

The card opens with a verdict, the first of these that fits: how you died, what went well if you
mostly healed, "No damage done this fight.", the biggest finding if it cost 3% of your damage or
more, or how close you came to the most you could have done.

Below that you get the cooldown sheet. Each damage cooldown you have cast in the last week gets a
row: Used, Possible, Missed, Excused, Free and Lost. A cooldown only counts as missed when it sat
ready for 2 seconds or more with no excuse. Moving (for cast-time spells), being out of mana,
stunned, healing someone who was low, or a target that was nearly dead are all excuses. Idle time
is counted the same way: 2.5 seconds or more with nothing cast while you could have acted, and only
when you had a filler spell to press.

Settings has a section for the card, under "After each fight":

- Keep it up, so the card stays on screen and updates in place after each fight instead of fading.
- Move it, which unlocks the card so you can drag it anywhere over the game. It remembers the spot
  and keeps the card inside the game window, whatever size the window is.
- How long it stays (4 to 30 seconds) and which side it slides in from.

It never takes focus from the game and lets clicks pass through it unless you are moving it.

The Fights page keeps your last 5,000 fights. Each one lists every enemy in it, most damaged
first, so a pull of three Defias and a Bandit reads as exactly that. Hover a fight in the list to
see them.

## Over weeks of play

The Habits page reads the last 40 fights of the character you played most recently. It opens with
who you are ("Mapomimi, level 33 Undead Priest, Shadow, gear 31") and your session: fights, kills
per hour, average rest between pulls, and average health and mana at the pull.

The trend chart shows your efficiency per fight, with a gray line at each level-up and yellow
dashes where your gear level changed. The cards are green for habits to keep, orange for ones to
fix and blue for ones to build on. The most useful for a levelling character splits a change in
damage into the part that came from your play and the part that came from gear, level and what
you fought. So when your damage goes up 15%, you can see how much of that you earned.

Other cards catch the slow leaks: the cooldown that costs you the most, your most common refusal,
pull buffs you usually have but sometimes forget, mana at the pull when it averages under 70%,
damage spells you know and never use, empty gear slots, and gear that went into a pull broken or
under 20% durability.

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

## Why each role would use it

### Healers

No meter can show reaction time. A healer at the top of the healing chart can still be slow to
start, and a healer lower down can be the reason nobody died. Response measures exactly that: when
someone drops under 60% after taking damage, how many seconds until you started healing them, and
how many dips you never answered. The hover on the timeline even shows who reacted to each sharp
drop.

Group health and Response are 70% of the healer card between them. Efficiency adds overhealing and
mana, so you learn whether your overheal comes from big heals cast too early, and whether long
pulls drain you dry. If most of your refusals are range errors, the tip says so, and that points
at where you stand.

Healers who also fight get the hybrid bonus of up to 10 points, but only when the healing held up.
Your damage share is multiplied by your Group health and Response scores, so damage bought by
letting the group fall earns nothing.

The app sorts healing without a spell list: a heal with a cast time, a HoT, or a shield you put on
someone else in the group. That means the healer card works the same for Priests, Paladins,
Shamans and Druids.

### Damage dealers

Damage tells you where you stood in the group. The rest of the card tells you why. Activity shows
the gaps where you did nothing. Cooldowns shows damage left on your bar, in numbers. Casting and
Input show presses that went nowhere. Movement shows casts you walked out of, each of which costs
the cast time and a global cooldown. Interrupts rewards watching enemy cast bars, with how fast you
kicked.

Melee players get a count of swings lost instead of broken casts, split into swings lost while
casting and swings lost for other reasons. Rage and energy users get Resource, which shows how long
they sat capped with income going to waste.

### Tanks

The tank card is built around what the group feels. Holding mobs counts how many mobs in each pull
went for you first. Pickups times how long it took to get a mob back when it left you, judged only
on enemy melee swings, so an area spell landing on the healer doesn't count as a lost mob. The
Pickups tip names the player mobs turned to most often.

The Pulls tab lists every pull with who started it, how many mobs and packs it had, and which mob
went for whom first. If someone in your group keeps pulling ahead of you, it shows up there as
Eager Beaver in the group placing.

Tank measurements need only the basic combat log, so they work even without Advanced Combat
Logging, and they work for any tank in your group.

## Why each class would use it

The same three cards apply to everyone. What changes per class is the Upkeep list, the defensives
the danger box looks for, which talent tree means which role, and a few rules for how a class shows
up in the log.

| Class | Upkeep | Defensives | Talent roles |
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

Buffs on yourself come before the semicolon, effects on enemies after it. You can replace any
class's lists with a `classes.json` in `%APPDATA%\dips-score`, and the [reference
guide](GUIDE.md#changing-the-weights) shows the format.

### Warrior

For a Warrior, a refused press often just means you were pooling rage, so "Not enough rage" doesn't count against you, and Resource shows
the opposite problem, time spent at full rage with nothing to spend it on. As a melee fighter,
Activity counts your swings and Movement is info only. Protection Warriors get the tank card from
their talents, so Holding mobs and Pickups judge what a Protection player actually cares about.
The danger box tells you whether Shield Wall or Last Stand sat ready while you were under 35%.

### Paladin

Paladins can fill any role, and the talent snapshot picks the right card. Holy Paladins get the
healer card with Response timing. Protection Paladins get the tank card. Retribution Paladins get
the DPS card, where cooldowns such as Judgement and Exorcism get their own rows on the cooldown
sheet. Upkeep watches your
seals and Righteous Fury, so a seal that dropped mid-pull shows up. A Seal of Command hit that
the log writes as your cast is recognised as a proc and left off the cooldown sheet. Divine Shield and Holy
Shield on yourself aren't mistaken for healing shields, and your dispels count toward Interrupts
and toward Utility in the group placing.

### Hunter

Several rules are written for Hunters:

- Auto Shot isn't a press, a cast or a global cooldown, but each shot keeps you busy for up to 2
  seconds in Activity, so standing and shooting counts as working.
- Feign Death shows up as a death in this client's log. If you act again within 20 seconds without
  a resurrection, the app removes the false death, so your Survival score stays honest. Feign Death
  also counts as a defensive.
- A pull your pet started is your pull, and your pet's damage counts as yours.
- Hunter's Mark, Eagle Eye and tracking don't count as starting a pull.

Upkeep shows how much of combat Hunter's Mark and Serpent Sting were up, counting a sting while
at least one enemy has it.

### Rogue

Rogues live on a 1.0-second global cooldown and an energy bar, and the app judges them that way.
Activity uses the shorter global cooldown, "Not enough energy" is pooling rather than a mistake,
and Resource shows time spent capped. Slice and Dice and Rupture uptime are the Upkeep numbers,
and the lost-swing count is a good measure of how often you were out of reach of your target. The
danger box tracks Evasion, Vanish and Cloak of Shadows.

### Priest

The healer card was written with Priests in mind. Power Word: Shield counts as an answer to a dip,
Renew counts as a HoT, and Vampiric Embrace counts as passive healing that isn't judged, so it
can't pad or hurt your overheal number. The tips speak Priest ("Shield or Renew the tank", "use a
lower rank"). Shadow Priests get the DPS card, where Mind Flay counts as busy until the channel
ends and Upkeep watches Shadow Word: Pain and Devouring Plague. Mind Vision doesn't count as
starting a pull.

### Shaman

Restoration Shamans get the healer card, and Elemental and Enhancement Shamans get the DPS card.
Lightning Shield counts for Upkeep and isn't confused with a healing shield. Enhancement Shamans who
fight mostly in melee get the melee rules, with swings in Activity and Movement as info only.
Elemental Shamans with long casts get the most out of the Movement numbers. Flame Shock uptime and
Shamanistic Rage in the danger box round it out.

### Mage

A Mage's damage depends on finishing casts, so Movement and Casting are the categories to watch.
Every cast you walked out of is counted, and refused presses come with the game's reason, so
you can see whether you were out of range or out of mana. Counterspell feeds the Interrupts score with your
reaction time. Ice Block, Ice Barrier and Mana Shield are the defensives the danger box looks for.
Detect Magic doesn't count as starting a pull.

### Warlock

Pets summoned during the run are credited to you: their damage counts in your share and shows as
"(pet)" rows on the Spells tab, and your pet's interrupts count as yours. Upkeep watches
Corruption, Curse of Agony and Immolate, which makes it one of the most useful numbers for an
Affliction Warlock. Long casts mean Movement matters a lot, and Death Coil and Howl of Terror are
the defensives the danger box checks.

### Druid

Druids change how they play with each form, and the app follows them. Restoration Druids get the
healer card, and a HoT started on someone counts as your answer to their dip. In cat form you are
an energy user on a 1.0-second global cooldown, and in bear form a rage user. The app reads which
power you used most. Feral has no fixed talent role because it can tank or deal damage, so the app
guesses from your spells, and you can set it on the Group tab when the guess is wrong. Balance
Druids with cast times gain the most from the Movement numbers, and Upkeep covers Moonfire, Insect
Swarm, Rake and Rip.

## How it compares with a log parser

A log parser and dips score read the same combat log, so they agree on damage, healing and deaths.
dips score adds what only an add-on can see: refused presses with their reasons, key versus click,
key hold times, mashing, the moment you started moving, your own combat start and end, and cast
timing matched to the log within a few milliseconds. It also carries your spell list, gear,
talents and durability, which this client's log doesn't contain.

From those, it works out what a parser can't: reaction times for healers, possible versus missed
casts for each cooldown, excused versus unexcused ready time, and how much of a damage change came
from you. And because the grade is judged against fixed numbers, you can compare this week's run
with last week's even if the group was different.

## What it can't do

- It has no threat data. "Who a mob went for" is who it hit first.
- It only sees other players through the combat log, so the group placing judges everyone,
  including you, on the log alone.
- The game only saves add-on data on `/reload` or logout. A crash before that loses the run's
  presses and movement, though fight cards don't wait for a save.
- Without Advanced Combat Logging, Group health, Response, Resource and Positioning can't be judged,
  and Survival only counts deaths.
- Presses on action bars from other add-ons have no key or click source.
- The scoring thresholds are a first guess and may change. You can change the weights yourself.
- The scorecards were tuned for five-player dungeons. Raids can be recorded, but expect the numbers
  to need more care there.

The add-on writes one short line per event and does no analysis in the game, and the app only
reads files and finds the game window to place the overlay. It never plays for you or changes
anything in the game beyond turning on the combat log.
