# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

(The mock-ups are web pages. The shipping app is a PyQt6 desktop window plus a frameless overlay drawn over the game; see Capabilities and Constraints.)

## Stack

Undecided. Mock-ups are static HTML/CSS/JS. After the mock-ups are agreed, choose between keeping PyQt6 widgets (redrawing the look with QPainter/QSS) and embedding a web front end (React + Magic UI) in the desktop app.

## Users

World of Warcraft players who want to get better at their own play in dungeons. The product is built for any player who installs it; while it is being built and tested, the primary user is the developer, who also shares results with groupmates.

## Product Purpose

projectArthas grades what a player controls in a dungeon run: what they pressed and when, refused presses, reaction time, cooldowns left unused, movement, interrupts. An in-game add-on records inputs; the desktop app lines them up with the combat log and produces a 0-100 score, an S-F grade by role (healer, DPS, tank), and a short list of what to work on. Success is the player knowing, within seconds of a run or a fight, the one thing to change next time.

## Positioning

Damage meters rank output; projectArthas judges decisions. It sees the player's own keypresses and refusals (from the add-on), not just the combat log, so it can say "Consecration sat ready 75s while you were free to use it" rather than "your DPS was 54".

## Operating Context

- Opened in two moments: a quick glance between runs or dungeons, and right after combat. Usually on a second monitor or by alt-tabbing out of the game.
- A card appears over the game about 2 seconds after each fight (the overlay), with a one-sentence verdict.
- Deeper review (timeline, spells, pulls) happens occasionally, when something looks off.
- Results get shared with groupmates (podium, MVP, awards and roasts).

## Capabilities and Constraints

- Per run: a scorecard per role with weighted categories (DPS: Damage, Activity, Cooldowns, Interrupts, Casting, Movement, Survival, Upkeep, Input, Resource; healer: Group health, Response, Efficiency, Casting; tank: Holding mobs, Pickups, Survival, ...). Weights are user-editable; weight 0 means info only.
- Grade bands: S ≥90, A ≥80, B ≥70, C ≥60, D ≥45, F below.
- Per fight: no grade; an efficiency share and a verdict decided by the 90% rule ("Clean fight" at ≥90% of possible damage).
- Group: every member scored from the combat log, placing points, MVP, 9 awards and 4 roasts.
- Across time: score per dungeon visit; Habits over the last 40 fights (play vs gear).
- The shipping UI is PyQt6 with two themes (classic blue, and "Azeroth" gold using game frame art). No web view today.
- Terms the product uses: run, visit, fight, pull, trash, boss, refused press, Work on, verdict, Clean fight, Habits.

## Evidence on Hand

- Real run data from the developer's own play (e.g. Blackfathom Deeps, 18 Nov, 75 B as DPS, 22 fights).
- A sample 33 MB combat log for replay.
- No testimonials, user counts or benchmarks exist; do not invent them.

## Product Principles

1. Lead with the one thing to change, priced in points and damage.
2. Judge what the player controls, and say it with specifics (who, which spell, how long).
3. A glance must be enough; detail is there when asked for, never in the way.
4. The player owns the scale: weights are theirs, and the numbers explain themselves.

## Accessibility & Inclusion

Grades and categories must not rely on colour alone (the letter, number and label always accompany colour). Motion must respect reduced-motion settings.
