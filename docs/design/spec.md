# projectArthas redesign: mock-up spec

Status: draft for alignment. This round produces HTML mock-ups only. No app code changes.
Product truth: `PRODUCT.md`. Approved plan: `C:\Users\jkncg\.claude\plans\pages-like-this-are-peaceful-scone.md`.

## Intent

Today's Score page puts a radar, eleven category bars, a 22-row fights table, a paragraph of stats, a "Work on" list and a seven-lane timeline on screen at once, all at the same weight. The player opens the app in a few seconds between runs, on a second monitor or after alt-tabbing out of the game. They need the answer, not the data.

The player asks two questions, in this order:

1. **After a trash or open-world fight:** how efficient was that fight, and was there a glaring ability gap?
2. **Coming out of a dungeon:** how effective was I, meaning damage, abilities used on time, abilities missed, and rotation? And what is the one thing to fix?

## Goals

- **3-second read.** Grade, verdict and the one fix are the three most prominent things on the debrief.
- **Every loss is priced** in points, and in damage where known.
- **Two new graded categories, Rotation and Pacing,** shown on the debrief and the fight card.
- **Detail stays one click away and never competes:** timeline, spells, pulls, group.

## Non-goals

- Building the PyQt or web front end. That decision comes after these mock-ups.
- Implementing Rotation or Pacing scoring. The mock-ups use plausible numbers, marked as illustrative.
- Redesigning Settings, the Weights dialog or the tray.

## Anti-goals (a failure even if it "works")

- A wall of equal-weight panels: the screenshot problem again with nicer colours.
- Decorative motion or effects (meteors, particles, marquees) on a tool you glance at.
- Colour as the only carrier of meaning. The letter, number or label always goes with it.
- Fabricated claims: no invented players, testimonials or benchmarks. Numbers come from the real Blackfathom Deeps run (18 Nov, 75 B as DPS) or are labelled illustrative.

## Constraints

- **Shipping target:** a PyQt6 desktop window, about 1360×900 on a second monitor, plus an overlay card over the game, about 360×220.
- **Two themes exist** ("classic" blue `#4099FF` on `#0E0E12`, and "Azeroth" gold `#FFD100` with game frame art). The mock-ups pick a direction at the Direction stage; the old look is evidence, not a requirement.
- **Grade bands:** S ≥90, A ≥80, B ≥70, C ≥60, D ≥45, F below. Fights have no grade: they get an efficiency % and a verdict, and ≥90% means "Clean fight".
- **Component references, for look and behaviour only:**
  - Magic UI: Animated Circular Progress, Number Ticker, Border Beam, Bento Grid, Blur Fade.
  - Bklit UI (https://bklit.com/docs/components): Gauge (zones), Ring Chart, horizontal stacked Bar, Heatmap, Sparkline, Sankey, Composed chart with Band.
  - The mock-ups are plain HTML/CSS/SVG/JS, with no React build.

## Data the screens use (all exists today unless marked NEW)

| Shown | Source |
|---|---|
| Points lost per category | `weight × (100 − score) / Σweight` (`scoring/score.py:407`) |
| Fix order | tips sorted by points lost. Change from today's sort by score (`score.py:185`) |
| Cooldown sat ready, damage lost | Cooldowns category summary, `live/summary.py` (`cooldowns`, `potential`) |
| Fight efficiency and verdict | `live/summary.py` (`efficiency`, `verdict`, `CLEAN = 0.90`) |
| Where the possible damage went | damage, cooldown loss, lost swings, idle loss (`live/summary.py:434`) |
| Fights per run | the Fights table on the Score tab |
| Change since last visit, per-visit scores | Dungeon page (`ui/pages.py` `DungeonPage`) |
| Placing, MVP, awards, roasts | `scoring/group.py`, `model/summary.py` |
| **NEW Rotation %** | share of presses where the highest-priority *ready* ability was pressed. Needs a priority list per class (user-editable, kept in a file like the weights) and the ready windows the app already computes (`live/ready_windows`) |
| **NEW Rotation slips** | the most frequent wrong choices: pressed X while a higher-priority Y was ready, with count and estimated damage |
| **NEW Opener check** | first 3–4 presses of each pull compared with the ideal opener |
| **NEW Pacing** | share of pulls entered safely and on time. Unsafe means entered under 50% health (or under 30% mana for mana users), or an accidental pull (heuristic). Late means first hit more than 3 s after the group's. Uses pull start health and mana, who pulled, gaps and rest times, and first press after the pull, all logged today |

The log has no positions, so "with the group" means *joined the fight in time*, not *stood near them*.

## Real numbers for the mock-ups

From `projectArthas.pyw report 6` (Blackfathom Deeps, 18 Nov 22:27, 69:45 long, 32:57 in combat, **64 fights**):

**Score 75 (B) as DPS.** The counted weight totals 75. Points lost per category = weight × (100 − score) / 75.

| Category | Weight | Score | Points lost | Summary |
|---|---|---|---|---|
| Cooldowns | 10 | 23 | **−10.3** | Consecration ready 75s (~1,177 dmg); Judgement ready 20s (~167) |
| Survival | 10 | 53 | **−6.3** | 1 death; 23s under 35% |
| Upkeep | 5 | 59 | −2.7 | Seal of Command up 69% |
| Casting | 10 | 80 | −2.7 | 830 casts, 197 refused (19%): Not yet recovered ×141 |
| Activity | 15 | 90 | −2.0 | busy 87%; 25 gaps of 2.5s+, longest 10.9s; 52 swings lost |
| Damage | 20 | 97 | −0.8 | 106,991 dmg, 128% of an even share |
| Input | 5 | 100 | 0 | 1.06 presses/cast |

Shown as info only, not counted: Interrupts (none used), Movement 100, Positioning 39 (behind the target for 44% of swings).

- **Totals:** 109,601 damage (55/s), 31 killing blows, 15,059 taken. First press after a pull: median 1.00s.
- **Bosses**, all killed, with their fight scores: Ghamoo-ra 85, Lady Sarevess 100, Geilhast 99, Twilight Lord Kelris 90, Aku'mai 99, Old Serra'kis 98.
- **Worst fights:** 43:57 Trash 50 D (busy 52%, damage 24% of even share); 69:28 Trash 53 D; 64:26 Trash 62 C; 6:25 Trash 70 C (90s, cooldowns lost 20%).
- **Group:** Anaruz Lightborne (tank), Shizuka Tsuruta (healer), Bao Kahn (you, DPS, 3rd), Evilguy Verybad (DPS), Piraña Segundo (DPS).
- **Illustrative, labelled on the page:** Rotation and Pacing numbers, dungeon visit history beyond this run, group scores other than your 3rd place.

## Builder-check answers (my calls)
- **Headline stays the real 75 B.** Rotation and Pacing appear as graded categories tagged "new · preview". The mock-up does not fold them into 75, so every real number stays real.
- **Directions:** stage 3 offers two or three visual worlds as small specimens. Only the chosen one is built at full fidelity.
- **Overlay backdrop:** a dark, blurred, neutral backdrop that suggests the game. No game art is used.
- **Interactions:**
  - The "All categories" drawer opens and shows sparklines (illustrative history).
  - Clicking a fight tile selects it and updates a one-line readout.
  - "Show me" and the Dig in tabs are visual only.
- **Effectiveness KPIs:** a grid of bullet charts (evidence: three or more KPIs read better as bullets than rings). The single grade uses a gauge with labelled zones.

## Evidence digest (ui-ux-pro-max, `design-system/dips-score/`)
- **Product pattern:** Gaming / BI dashboard. The best fit is "Data-Dense Dashboard": a KPI row, a grid, hover tooltips, 12–14px data text.
- **Style candidates:** Data-Dense Dashboard; Dark Mode (OLED, restrained glow); Cyberpunk HUD (rejected as cliché for a tool you glance at).
- **Palette candidates:** generated: neon purple `#7C3AED` with rose `#F43F5E` on `#0F0F23` (generic esports). Incumbent: classic `#4099FF` on `#0E0E12`, and Azeroth gold `#FFD100`. Data: red→amber→green for performance zones, always with text.
- **Type pairs:** Fira Code + Fira Sans (data); Inter, single family (precision utility); Russo One + Chakra Petch (generated, esports, loud).
- **UX anti-patterns:** colour-only status; gauges for 3+ KPIs (use bullets); equal-weight widget walls; hover-only detail without a keyboard path.
- **Motion tier:** Subtle (3/10). Gauge sweep, number ticker and one entrance stagger; reduced motion snaps to the final state.

**Design Read:** a calm, precise post-run instrument for the alt-tab glance. VARIANCE 4, MOTION 3, DENSITY 6.

## Screens

### 1. Run debrief (the default page after a dungeon)
Top to bottom, in priority order:

1. **Hero:**
   - A grade gauge, 0–100, with the grade bands drawn as zones; the needle or arc sweeps to 75.
   - The number ticks up to it, with the letter "B" and "as DPS".
   - The verdict sentence.
   - A change chip: "+6 vs last visit".
2. **Fix this first:** a single card with a Border Beam accent. "Consecration sat ready 75s while you were free to use it", priced at **−10.3 points (Cooldowns) · ~1,177 damage**, with a "Show me" link that would zoom the timeline. Two smaller "next" cards sit beside or under it: "You died once: −6.3 (Survival)" and "Seal of Command up 69%: −2.7 (Upkeep)".
3. **Effectiveness row:** a grid of bullet charts for Damage, Abilities on time (cooldowns), Rotation and Pacing. Each has its number, a labelled target and a one-line reason.
4. **Where your 25 points went:** one horizontal stacked bar from 0 to 100, with the earned part solid and the lost segments labelled and ordered by size. An "All categories" drawer, collapsed, holds every category with its sparkline across visits.
5. **Rotation:**
   - A priority ribbon: one cell per press for the selected pull, coloured best, second, wrong or nothing ready, with a legend and text labels.
   - Top three slips beside it.
   - Clean openers, e.g. "15 of 22".
6. **Pacing:** the path between pulls. Each pull is a dot showing the health and mana you entered with. Gaps are travel or rest, with rest shown as a dotted gap. Flags read "38% hp, you pulled" and "late 4.2s". A three-count tally sits beside it.
7. **Fight strip:** one tile per fight, width set by length, colour and letter by grade, with boss and death markers. Clicking a tile scores only that fight.
8. **Dig in:** a collapsed tab row for Timeline, Spells, Pulls and Group. This is a placeholder only in the mock-up.

### 2. After-fight card (overlay over the game, about 360×220)
- An efficiency gauge or ring with the 90% "clean" zone marked, and the number.
- The verdict sentence, then the single biggest gap ("Consecration sat ready 14s · ~220 damage").
- Small Rotation and Pacing chips: "Rotation 82%", "entered at 38% hp".
- **Two states:** a clean fight (green, with no gap box) and a gap fight. Open world shows the same card.
- **Optional detail:** a mini Sankey or stacked bar of possible damage, split into dealt, cooldowns, idle and lost swings.

### 3. Dungeon history
- A score-per-visit line drawn over grade bands (Bklit Band), with best, last and trend called out.
- **Recurring fix:** "Cooldowns cost you points in 5 of 7 visits".
- Per-category sparklines across visits, Rotation and Pacing included.
- A visit list underneath (date, score/grade, length, deaths), compact.

### 4. Group / podium
- **Your placing, large:** "2nd of 5 · 3 points behind MVP".
- A compact podium of the top three with the MVP marked.
- One row per player: role, score, two strengths and one weakness, and award and roast chips.

## Decided by the user
- Who: any player; built and tested as "me plus sharing".
- When: a quick glance between runs or dungeons and after combat, on a second monitor or after alt-tabbing.
- What first: the one fix, then the grade and where the points went.
- After a fight: efficiency plus the glaring ability gap. After a dungeon: damage, abilities on time, missed abilities, rotation.
- Rotation means following the priority order to maximize damage. Pacing means safe, efficient movement between pulls.
- Rotation and Pacing are **graded**. All five shown ideas (ribbon, slips, opener, path, tally) are in.

## My calls (check these)
- The grade uses a Bklit-style **gauge with grade zones** rather than a plain ring, so the bands read at a glance. The four effectiveness KPIs use bullet charts, not rings.
- **Default DPS weights for the new categories:** Rotation 15, Pacing 10. Existing weights are scaled down proportionally, and you can still edit them.
- **Pacing thresholds:** under 50% health or under 30% mana counts as unsafe; more than 3 s late counts as late.
- **Mock-up size:** 1360×900 for window screens and 360×220 for the overlay.
- **Mock-up location:** `docs/design/mockups/`, one HTML file per screen plus an index, also published as a private Artifact.
- **Data:** the illustrative numbers for Rotation and Pacing are labelled as such on the page.

## Left to the builder
Exact layout grid, type scale, palette and motion timing. These come from the Direction stage, where you choose between two or three visual worlds.
