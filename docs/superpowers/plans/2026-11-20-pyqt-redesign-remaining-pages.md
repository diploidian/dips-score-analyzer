# PyQt Redesign, Phase 3 (every other page) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every page other than the Debrief up to the approved mock-ups: the shell (rail and tabs), Timeline, Pulls, Spells, Group, the Fight page, Habits, the dungeon page (History, Bosses, Records) and the after-fight overlay card.

**Architecture:** This repeats the Debrief's proven split for every page.
- **View-model:** a pure-Python module turns the analysis (or the live fight / habits dict) into exactly what the page shows. It has no Qt, so it can be unit-tested on the dev PC.
- **Widgets:** each page only paints its view-model.
- **Kit:** shared painted parts (hero, label tab, plate, ruled bar rows, drawer, highlighter marks) are pulled out of `ui/debrief.py` into `ui/kit.py`, so every page draws them the same way.

**Tech Stack:** Python 3.13+, PyQt6 ≥ 6.6 (QPainter, QSS), unittest, `scripts/shoot.py` for offscreen captures, PyInstaller + Inno Setup.

**Spec:** the approved mock-ups are the composition to match. Each page lists its own file (all in `docs/design/mockups/`). Shared tokens are in `assets/theme.css`. Also read `DESIGN.md`, `docs/design/spec.md`, and the Phase 1–2 plan `docs/superpowers/plans/2026-11-19-pyqt-redesign-theme-and-debrief.md`, whose Global Constraints still apply.

## Global Constraints

- **Base:** branch `dot-oribital/redesign-pages` from the tip of `dot-oribital/nostalgic-margulis-54a6bb`, which holds the built Debrief and the approved mock-ups (`61fd7ea`).
- **Every page follows the Debrief's principles:**
  1. One question answered at the top, with a big figure and a verdict sentence.
  2. Exactly one solid plate (the thing to act on), with a label tab straddling its top edge.
  3. Ranked rows, with bars sized by impact.
  4. Full tables only inside a collapsed "All … (n)" drawer.
  5. Quiet colour:
     - player names are set in `tx`, never in class colour;
     - kind tags (Boss / Dungeon / PvP / Trash) are tracked-caps text with a 1 px `ln` border;
     - no rows of boxed stat tiles, no coloured side stripes;
     - the highlighter is used only for one "look here" mark per page.
  6. Section names are boxed label tabs, never a small label above a heading.
- **Colours** come only from `ui/tokens.py` through `theme.tok()` or the legacy names, with no hex or `QColor(r, g, b)` literals in UI code. That includes the leftovers in `timeline.py` (lines ~53, 230, 232, 507, 540, 552, 662), `fightsview.py` and `overlay.py`.
- **Text:** at least 11 px, and at least 4.5:1 contrast in all four looks. Grade letters always show.
- **Real data or a label:** every figure comes from the analysis, live fight or habits data. Where data is missing (older logs, a single visit, no advanced logging), show an honest empty state ("–", "first visit — records start here"). Never invent a number.
- **Tests:** `python -m unittest discover -s tests`. View-model modules must not import PyQt. Widget tests may use the PyQt copy and skip without it.
- **Version:** `0.12.0` before the installer build. This is a large change under the project's versioning rule.

## Review Focus

1. **A run with no health or mana data** (advanced combat logging off, or a hunter or warrior with no mana). Pulls shows "–" for mana and health at pull. The verdict drops its mana clause, and there's no crash. Test: `test_pulls_without_resources`.
2. **A dungeon with only one visit.** Bosses shows today's scores with no trend line; Records reads "first visit — records start here", and no record is shown as broken. Test: `test_records_single_visit`.
3. **A healer or tank on Spells and Group.** The healing group leads on Spells for a healer, and the Group cards draw any role's strengths, weaknesses and map. Tests: `test_spells_healer`, `test_group_view_healer_you`.
4. **An older live fight dict missing keys** (no `cooldowns`, `auto` or `group`). The Fight page and overlay render the parts that exist and hide the rest. Test: `test_fight_view_minimal_dict`.
5. **Habits with fewer than 5 fights or no fix cards.** No trend chart, an empty state reading "Play a few more fights", and no plate when there's nothing to fix. Test: `test_habits_view_empty`.

---

### Task 0: Branch

- [ ] Create `dot-oribital/redesign-pages` from the tip of `dot-oribital/nostalgic-margulis-54a6bb`. Run the tests and expect 155 OK (6 skipped without PyQt).

### Task 1: The kit, plus the healer "0 points" fix

**Files:**
- Create: `src/dips_score/ui/kit.py`
- Modify: `src/dips_score/ui/debrief.py` (use the kit, no visual change)
- Test: `tests/test_fightgrid.py` (still passes)

**Interfaces — produces** (Qt, in `ui/kit.py`; the names are what later tasks import):
- `draw_label_tab(p, x, y, text) -> QRectF`: the boxed tracked-caps tab.
- `class Plate(QWidget)`, with `set(title: str, price: str | None, caption: str | None, button: str | None, rows: list[tuple[str, str]])` and signal `clicked()`. It is the solid plate with a straddling label tab, set via `Plate(label)`, matching the Debrief's FixPlate.
- `class Hero(QWidget)`, with `set(big: str, suffix: str | None, caption: str | None, chip: str | None, verdict: str)`.
- `class BarRows(QWidget)`, with `set(rows: list[BarRow], total: tuple[str, str] | None)`, where `BarRow(name, value_text, fraction, ink, note=None)`. This is the ruled list with one ink per row and an optional heavy-rule total line, generalised from the Debrief's Breakdown.
- `class KeyFigures(QWidget)`, with `set(items: list[tuple[str, str]])`: a single ruled row of number and caption, no boxes.
- `class Drawer(QWidget)`, with `Drawer(title)` and `set_count(n)`. It's a chevron toggle that shows or hides its body widget and can be focused from the keyboard.
- `draw_hand_circle(p, rect, ink, rotation, frac=1.0)` and `draw_hand_note(p, text, anchor, target)`: the Caveat highlighter marks, pulled out of the Debrief's FightGrid.
- `def tag(text: str) -> QLabel`: a tracked-caps kind tag.

**Steps:**
- [ ] **Step 1:** Before touching anything, capture `scripts/shoot.py --tab Debrief` in the 4 looks as a baseline.
- [ ] **Step 2:** Move the parts into `kit.py` and make `ui/debrief.py` use them.
- [ ] **Step 3:** Re-shoot. Expected: pixel-identical to the baseline; compare files with `cmp`.
- [ ] **Step 4: Fix the healer "0 points" heading.** When the card total is capped at 100 with a hybrid bonus, the breakdown says "Where your 0 points went".
  - New title: `"Where the points went"` when `100 − earned` is 0 but rows exist.
  - Add `test_breakdown_title_capped` (pure: a helper `breakdown_title(earned, rows, whose)` in `debrief.py`).
- [ ] **Step 5:** Commit `kit: shared painted parts; Debrief uses them unchanged`.

### Task 2: Shell — rail and tabs, Timeline as a tab, Summary folded into Group

**Files:** `src/dips_score/ui/app.py` and `src/dips_score/ui/settings.py`, plus `ui/theme.py` (QSS for the rail nav and links).

**Decisions (from the mock-ups, every page's shell):**
- **Tabs:** `Debrief · Timeline · Pulls · Spells · Group`.
  - The old "Summary" tab goes away; its content becomes the Group page in Task 5.
  - The old roster-editing "Group" table moves into the new Group page as an "Edit roles" drawer in Task 5. Until then, keep the existing `GroupTab` widget reachable inside that drawer position.
- **Timeline:** the `Timeline` widget leaves the `timeline_pane` splitter and becomes the "Timeline" tab's page. Remove the splitter and the force-show logic. Task 8 adds its header strip.
  - Debrief "Show me" and fight picks, Pulls "Show this pull" and Spells "Show on the timeline" all switch to the Timeline tab with `set_view`.
  - Spells' `highlight` stays wired.
- **Rail:**
  - The three mode buttons become a vertical nav list of flat text items (`Dungeons`, `Fights`, `Habits`), with the current item in `rail-on` and weight 600, styled like the mock-up rail.
  - The run tree (Dungeons) and the fight list (Fights) stay underneath.
  - Status and lag become one quiet `rail-mu` line.
  - Under the Look block, a "Settings · Reload" text-link row replaces the cog and the Reload button.
  - "Scoring weights…" moves into the Settings dialog as a button that opens the existing `WeightsDialog`.

**Steps:**
- [ ] **Step 1:** Implement.
- [ ] **Step 2:** Update `scripts/shoot.py --tab` to accept `Timeline`; keep `Summary` as an alias of Group.
- [ ] **Step 3: Verify.**
  - Shoot each tab plus Fights and Habits in Timeless Day and Classical Night.
  - "Show me" on the Debrief lands on the Timeline tab, zoomed to the 6:25 fight. Check this with a shoot option `--click show-me`.
  - Tests pass.
- [ ] **Step 4:** Commit `shell: Timeline tab, Group replaces Summary, rail nav and Settings · Reload`.

### Task 3: Pulls

**Files:**
- Create: `src/dips_score/pulls_view.py` (pure), `src/dips_score/ui/pulls.py`
- Modify: `ui/pages.py`, removing `PullsTab` once the new page is wired (keep its mob tree inside the drawer)
- Test: `tests/test_pulls.py`

**Mock-up:** `docs/design/mockups/pulls.html` (track, mana line, pull-safety row, pulled-by row, "All pulls" drawer). Pacing is not graded yet, so tag it `preview`.

**Interfaces — produces:**
- `def resource_at(events, guid, t) -> tuple[float | None, float | None]`: your health and mana fractions from the last `e.info` sample for `guid` at or before `t`. Mana only counts when `power_type == 0` and `max_power > 0`.
- `@dataclass PullRow`, with fields:
  - `n`, `at`, `start`, `end`, `label`, `boss`;
  - `mobs`, `packs`, `extra_packs`;
  - `pulled_by: str | None`, `you_pulled`, `how`;
  - `length_s`, `gap_before_s: int | None`, `you_died`;
  - `hp: float | None`, `mana: float | None`.
- `@dataclass PullsView`, with fields:
  - `rows`, `total`, `verdict`, `fix: PullRow | None`;
  - `under_half_hp`, `lowest_hp: tuple[float, str] | None`;
  - `under_half_mana: list[str]`, `joined: int`, `you_pulled: list[str]`;
  - `pullers: list[tuple[str, int]]`;
  - `breaks: list[tuple[str, str, int]]` (gaps of 300 s or more: from, to, minutes).
- `def build_pulls(a) -> PullsView`

**Rules:**
- **Fix pull:**
  1. The pull you died in.
  2. Else the pull you entered with the lowest mana, if under 50%.
  3. Else the one with the lowest health, if under 50%.
  4. Else `None`. The plate then reads "No risky pulls" with no button.
- **Mana slide:** the longest run of 3 or more consecutive pulls where each starts with less mana than the one before and every gap is under 30 s, reported as "from X% to Y% over N pulls".
- **Verdict:** assemble it from the health clause (lowest health), the slide clause if there is one, and the death clause if there is one.

**Steps:**
- [ ] **Step 1: Write the failing tests** (pure, with `SimpleNamespace` stubs plus one literal of the real run's 64 pulls; copy the pull fields from the `"pulls"` array of `C:\Users\jkncg\AppData\Local\Temp\claude\346d74d9e052217f\44ba439a-4368-4390-bc36-5bdc8351bc49\scratchpad\mock-data.json`, which was dumped from the real run):
  - `test_resource_at` (mana ignored for `power_type != 0`);
  - `test_pulls_blackfathom`:
    - `fix.at == "18:15"`, `under_half_hp == 0`, `lowest_hp == (0.57, "63:27")`;
    - `under_half_mana == ["17:10", "18:15"]`, `joined == 22`;
    - `you_pulled == ["12:27","15:54","28:16","37:35","43:12","55:02"]`;
    - one break of 8 minutes;
  - `test_pulls_without_resources`.
- [ ] **Steps 2–4:** RED, implement, GREEN.
- [ ] **Step 5: Build the widgets** (`ui/pulls.py`) from the kit:
  - Hero ("64 pulls").
  - Plate "Pull to fix".
  - The track, painted with QPainter:
    - dots placed by time, sized by mob count, filled by mana on one ink at varying opacity, with a legend;
    - "you" ticks over your pulls;
    - breaks drawn dotted and labelled;
    - the death pull circled with `draw_hand_circle` and noted "died here".
  - Mana line with a 50% gridline.
  - Pull safety shown as `KeyFigures`, tagged `preview`.
  - Pulled-by row, with names in `tx` and a neutral square before each.
  - Drawer "All pulls (n)" holding the old table and mob tree.
- [ ] **Step 6:** Shoot Pulls in 4 looks and compare with the mock-up. Commit.

### Task 4: Spells

**Files:** create `src/dips_score/spells_view.py` and `src/dips_score/ui/spells.py`; modify `ui/pages.py` (remove `SpellsTab` once wired); test `tests/test_spells.py`.

**Mock-up:** `docs/design/mockups/spells.html`.

**Interfaces — produces:**
- `@dataclass AbilityRow`, with fields:
  - `name`, `note: str | None`;
  - `casts`, `refused`, `refused_share`;
  - `damage`, `share`, `per_min`, `crit`, `healing`, `overheal_share`.
- `@dataclass SpellsView`, with fields:
  - `total_damage`, `dps`, `verdict`;
  - `fix: tuple[str, str, str] | None` (title, price, caption);
  - `next_rows: list[tuple[str, str]]`;
  - `damage_rows`, `healing_rows`, `buff_rows`, `all_rows`.
- `def merge_by_name(rows: list[SpellRow]) -> list[SpellRow]`. It sums rows that share a name. A damage-only row named `"<X> of <Y>"` folds into a casts-only row named `X`, keeping `note = "damage from <X> of <Y>"`.
- `def build_spells(a, guid, scope) -> SpellsView`, where `scope` is `"all"`, `"boss"` or `"trash"`, as today.

**Rules:**
- `refused_share = failed / (casts + failed)`.
- `share` is a row's damage over total damage.
- `per_min` is casts per combat minute.
- Group membership:
  - **damage rows:** damage > 0, sorted by damage;
  - **healing rows:** healing > 0;
  - **buff rows:** casts > 0 with no damage and no healing.
- **Fix** (for you): the ability with the most damage lost from `a.cooldowns`, priced as "~N damage". **Next rows:** abilities with a refused share above 25%, then the next cooldown.
- **For another player:** no fix plate, because cooldowns are only known for you.

**Steps:**
- [ ] **Step 1: Write the failing tests:**
  - `test_merge_by_name` (the two Seal of Command rows; Judgement plus Judgement of Command);
  - `test_spells_blackfathom`:
    - Holy Strike `refused == 109` with `casts + refused == 288` and `round(refused_share, 2) == 0.38`;
    - Melee and Seal of Command shares add up to 0.63 ± 0.01;
    - `len(all_rows) == 21`;
    - fix is Consecration, about 1,177 damage;
  - `test_spells_healer`.
- [ ] **Steps 2–4:** RED, implement, GREEN.
- [ ] **Step 5: Build the widgets:**
  - Hero ("110K", "damage · 56/s").
  - Plate "Ability to fix", whose button switches to Timeline and highlights the spell.
  - BarRows "Where your damage came from", using the `m-dmg` ink, with compact columns (casts, refused "109 · 38%" in `gD` when the share is above 25%, per min, crit).
  - The highest refusal gets the page's one hand circle.
  - Healing rows.
  - Drawers "Buffs, seals and blessings (n)" and "All spells (n)".
  - The player and scope selects stay in the header.
- [ ] **Step 6:** Shoot in 4 looks. Commit.

### Task 5: Group (replaces Summary) and the radar damage fix

**Files:**
- Create: `src/dips_score/group_view.py`, `src/dips_score/ui/group.py`
- Modify:
  - `scoring/radar.py` (damage source)
  - `ui/radar.py` (restyle with tokens: rings in `ln`, average dashed in `mu`, fill at 18%)
  - `ui/summary.py` (delete once replaced)
  - `ui/pages.py` (the GroupTab table moves into the "Edit roles" drawer)
- Test: `tests/test_group_view.py`

**Mock-up:** `docs/design/mockups/group.html` (built on real standings).

**Interfaces — produces:**
- `@dataclass PlayerCard`, with fields:
  - `rank`, `name`, `role`, `you`, `mvp`, `reason`;
  - `plus: list[tuple[str, str]]`, `minus: list[tuple[str, str]]`;
  - `awards: list[tuple[str, bool, str]]` (title, good, tooltip);
  - `radar: list[float] | None`, `points`, `score`, `grade`.
- `@dataclass GroupView`, with fields:
  - `place`, `of`;
  - `behind_next: float | None`, `behind_mvp: float | None`;
  - `reason`;
  - `move_up: tuple[str, str] | None` (title, caption);
  - `podium: list[PlayerCard]`, `cards`, `average: list[float] | None`;
  - `awards: list[tuple[str, str, str, str, bool]]`.
- `def build_group(a) -> GroupView`

**Rules:**
- `plus` and `minus` split the `strengths` and `weaknesses` lines on the first `": "`.
- **Move-up title:** the evidence of your first weakness, phrased with the multiplier when there is one ("You took 15,059 damage — 3× the other damage dealers.").
- **Move-up caption:** names the roasts that cost you points, then "one place is X points away".
- **Radar fix:** the damage axis uses the same fight-windowed damage as `group_data`, so a card's strengths line and its map agree.

**Steps:**
- [ ] **Step 1: Write the failing tests:**
  - `test_group_view_blackfathom`:
    - `place == 3`, `of == 5`;
    - `round(behind_next, 1) == 0.4`, `round(behind_mvp) == 35`;
    - `cards[0].name == "Piraña Segundo"` and `cards[0].mvp`;
    - your awards include Punching Bag with `good is False`;
  - `test_radar_damage_matches_card`: for each player, the radar damage value equals the windowed damage `group_data` uses;
  - `test_group_view_healer_you`.
- [ ] **Steps 2–4:** RED, implement, GREEN.
- [ ] **Step 5: Build the widgets** to match the mock-up:
  - Hero ("3rd").
  - Plate "To move up".
  - A flat 3-step podium, with your step outlined in the highlighter.
  - `PlayerCard` widgets: rank, name and role, reason, +/− rows in `m-dmg` and `gD`, award and roast chips, the token-styled radar (`m-cast` for others, the highlighter only on yours), and points with the score and grade.
  - Ruled "Awards this run" list.
  - "Edit roles" drawer holding the roster table with its class and role combos and "Forget my picks".
- [ ] **Step 6:** Shoot the full page. Commit.

### Task 6: The Fight page and fight list

**Files:**
- Create: `src/dips_score/fight_view.py`
- Modify: `src/dips_score/ui/fightsview.py` (`FightList` rows and `FightDetail` rewritten on the kit; `STYLE`, `StatBox` and the colour literals go)
- Test: `tests/test_fight_view.py`

**Mock-up:** `docs/design/mockups/fight.html`.

**Interfaces — produces:**
- `@dataclass FightView`, with fields:
  - `name`, `when`, `kind`, `efficiency: float | None`, `verdict`, `duration`, `result`;
  - `figures: list[tuple[str, str]]`;
  - `gap: tuple[str, str] | None`;
  - `rows: list[tuple[str, str, float]]` (label, detail, damage);
  - `left_on_table: float | None`;
  - `went_well: list[str]`, `also: list[str]`;
  - `group: list[tuple[str, int, int, bool]] | None`, `group_line: str | None`;
  - `abilities`.
- `def build_fight(d: dict) -> FightView`. It is built from the live fight dict whose keys `FightDetail` reads today.

**Rules:**
- **Rows:**
  - `auto.damage_lost` becomes "Swings lost ×n";
  - each `cooldowns` entry with `lost > 0` becomes "<name> sat ready <held> s".
- Rows are sorted by damage. The gap is the top row.
- `left_on_table = potential − damage` when both exist.
- **Missing keys:** the matching section is `None` or empty, never an error.

**Steps:**
- [ ] **Step 1: Write the failing tests.**
  - `test_fight_view_oracle` uses a dict literal with the user's real "Blackfathom Oracle +3" fight values: 49% efficiency; damage 2,583; 23 DPS; 433 taken; 53 healing; 12 swings lost ≈1,538; Judgement 64.6 s ≈614; Consecration 72.8 s ≈343; Holy Strike 38.6 s ≈211. It asserts:
    - the row order;
    - `left_on_table ≈ 2705`;
    - the group line reads "25% of the damage (3rd of 5)".
  - `test_fight_view_minimal_dict`.
- [ ] **Steps 2–4:** RED, implement, GREEN.
- [ ] **Step 5: Build the widgets.**
  - The detail has:
    - Hero (efficiency bullet with the 90 "clean" tick, verdict, kind tag and "they got away");
    - KeyFigures (damage, DPS, taken, healing);
    - Plate "Biggest gap" → Timeline;
    - BarRows "Where the damage went", with a "Left on the table" total;
    - "Went well" with drawn checks in `m-dmg`;
    - Group rows;
    - Drawer "Abilities (n)".
  - Fight list rows show the name, then a muted line "DPS · efficiency · length", and a text kind tag. Efficiency is inked with `gS` at 90 or above and `gD` under 60, otherwise `tx2`.
- [ ] **Step 6:** Shoot Fights in 4 looks. Commit.

### Task 7: Habits

**Files:**
- Create: `src/dips_score/habits_view.py`
- Modify: `src/dips_score/live/habits.py` (add an optional `cost` number to the cards where it's known), `src/dips_score/ui/habitsview.py` (rewritten on the kit; `EDGE` stripes and `StatBox` go)
- Test: `tests/test_habits.py` (extend)

**Mock-up:** `docs/design/mockups/habits.html`.

**Interfaces — produces:**
- `@dataclass HabitsView`, with fields:
  - `title`, `meta`;
  - `recent: float | None`, `before: float | None`;
  - `verdict`, `fix: tuple[str, str, str] | None`;
  - `figures`;
  - `trend: list[float]`, `split_at: int | None`;
  - `groups: list[tuple[str, list[tuple[str, str, bool]]]]` (Fix, Build, Keep; title, detail, is_plate).
- `def build_habits(h: dict) -> HabitsView`

**Rules:**
- `recent` is the mean of the last 20 `trend[*].efficiency` values and `before` the mean of the ones preceding them. `split_at` is the index where the last-20 window starts.
- The plate is the fix card with the largest `cost`, falling back to the first fix card. It stays listed in its group, marked "habit to fix".
- With fewer than 5 fights: no trend, and the empty-state text.

**Steps:**
- [ ] **Step 1:** Write the failing tests, `test_habits_view_real` (the user's figures: 76.5 vs 86.8; plate "Consecration left unused" with cost 7,298; groups 6/4/1) and `test_habits_view_empty`.
- [ ] **Steps 2–4:** RED, implement, GREEN.
- [ ] **Step 5: Build the widgets:**
  - Hero ("77%", chip "−10 pts vs the 18 before").
  - Plate "Habit to fix".
  - KeyFigures.
  - The restyled TrendChart: 50% gridline, the two period averages as dashed segments, the drop's onset circled with `draw_hand_circle` and noted "drop starts here", and gear and level markers in `mu`.
  - Grouped ruled habit list, with an 8 px group square in `gD` / `m-cast` / `m-dmg`.
- [ ] **Step 6:** Shoot. Commit.

### Task 8: The Timeline tab

**Files:**
- Create: `src/dips_score/timeline_view.py`
- Modify: `src/dips_score/ui/timeline.py` (tokens for every literal; health lanes on `panel`; the readable crosshair), `ui/app.py` (header strip)
- Test: `tests/test_timeline_view.py`

**Mock-up:** `docs/design/mockups/timeline.html`.

**Interfaces — produces:** `def idle_moments(idle: list[tuple[float, float]], window: tuple[float, float], min_s=2.5) -> list[tuple[float, float]]` (longest first, clipped to the fight) and `def fight_verdict(moments) -> str`.

**Rule:** use the app's own idle intervals (`Data.idle`, which also feeds the Activity score), so the timeline and the scorecard agree. The mock-up's 13.9 s versus 10.9 s mismatch came from recomputing gaps from busy spans.

**Steps:**
- [ ] **Step 1:** Write the failing tests: `test_idle_moments_clip_and_sort` and `test_fight_verdict_text`.
- [ ] **Steps 2–4:** RED, implement, GREEN.
- [ ] **Step 5: Build the widgets:**
  - **Header strip:** fight select ("6:25 Trash · 90 s · 70 C"), previous and next buttons, "Whole run", and "wheel to zoom · drag to pan" in `mu`.
  - **Verdict line.**
  - **Lanes**, calm: idle gaps of 2.5 s or more washed in the highlighter at low alpha with their seconds labelled; health as lines on `panel`; the other players' lanes inside a collapsed "Group (n)" lane row.
  - **Plate and list:** Plate "In this fight" ("Longest idle: X s at T") next to a BarRows "Idle moments, longest first".
- [ ] **Step 6:** Shoot. Commit.

### Task 9: Dungeon page — History

**Files:**
- Create: `src/dips_score/dungeon_view.py`
- Modify: `src/dips_score/ui/pages.py` (`DungeonPage` becomes a tabbed page: History, Bosses, Records; `ScoreChart` goes)
- Test: `tests/test_dungeon_view.py`

**Mock-up:** `docs/design/mockups/history.html`.

**Interfaces — produces:**
- `@dataclass Visit(when, run_id, length, combat, score: float | None, grade, bosses: str, deaths, wipes, categories: dict[str, float])`
- `def visits(pairs: list[tuple[Run, Analysis | None]]) -> list[Visit]` (newest first; unscored visits say "too short to judge")
- `@dataclass HistoryView(visits, best: Visit | None, last: Visit | None, trend: float | None, recurring: tuple[str, int, int, float] | None, series: dict[str, list[float | None]])`
- `def build_history(vs) -> HistoryView`

**Rules:**
- **Recurring fix:** the category that lost points in the most scored visits, reported as (name, in N of M, average points lost).
- **Trend:** the last score minus the mean of the up-to-5 scores before it.

**Steps:**
- [ ] **Step 1:** Write the failing tests with stub visits: `test_history_recurring`, `test_history_unscored_visits`.
- [ ] **Steps 2–4:** RED, implement, GREEN.
- [ ] **Step 5: Build the widgets:**
  - Score line over the grade bands.
  - Best and last callouts.
  - Plate "Recurring fix".
  - A small multiple per counted category across visits.
  - Ruled visits table, where a double-click opens the run as today.
- [ ] **Step 6:** Shoot. Commit.

### Task 10: Dungeon page — Bosses and Records

**Files:** extend `dungeon_view.py` and the dungeon page; test `tests/test_dungeon_view.py`.

**Mock-ups:** `docs/design/mockups/bosses.html` and `records.html`.

**Interfaces — produces:**
- `@dataclass BossRow(name, today: float | None, grade, kill_s, dps, share, lost: list[tuple[str, float]], history: list[float | None], best: tuple[float, str] | None)`
- `def build_bosses(pairs) -> (rows, weakest: BossRow | None, average: float | None)`, in dungeon order of first appearance.
- `@dataclass Record(name, value: str, when: str, today: str, status: str, new_today: bool)`
- `def build_records(pairs) -> (records, within_reach: tuple[str, str] | None)`

**Records:**
- best score;
- fastest clear (`data.duration`);
- least time in combat;
- most killing blows (`metrics.kills`);
- highest DPS in a fight;
- longest S streak (fight cards scoring 90 or more in a row);
- deathless visits.

**Rules:**
- **Within reach:** the best score, when today's score plus today's top points-lost category would beat it ("+N needed — your <category> fix is worth X").
- **Single visit:** every record has `status = "first visit"`, and the page shows "first visit — records start here".

**Steps:**
- [ ] **Step 1: Write the failing tests:**
  - `test_bosses_weakest` (from stub analyses: the Blackfathom bosses with today's real scores, so Ghamoo-ra is weakest at 85.5 and the average is 95);
  - `test_records_new_today`;
  - `test_records_within_reach` (75.3 + 10.3 beats 82, so the text reads "+7 needed — your Cooldowns fix is worth 10.3");
  - `test_records_single_visit`.
- [ ] **Steps 2–4:** RED, implement, GREEN.
- [ ] **Step 5: Build the widgets:**
  - **Bosses:** Hero (average and grade), Plate "Boss to fix", "The route" (stations with grade letters, the weakest circled), and "Boss by boss" rows with sparklines and a dashed 90 line.
  - **Records:** Hero (best score), Plate "Within reach" with the 60–100 scale, and the ruled records board, where only one "new record today" (the first in board order) gets the hand circle.
- [ ] **Step 6:** Shoot both tabs. Commit.

### Task 11: The after-fight overlay card

**Files:**
- Create: `src/dips_score/overlay_view.py`
- Modify: `src/dips_score/ui/overlay.py` (the card is painted on the kit instead of rich text; `KIND_COLOR` goes)
- Test: `tests/test_overlay_view.py`

**Mock-up:** `docs/design/mockups/fight-card.html` (380×236, four states).

**Interfaces — produces:** `@dataclass CardView(name, at, length, kind, efficiency, clean: bool, verdict, gap: tuple[str, str] | None, chips: list[str], boss: bool)` and `def build_card(d) -> CardView`.

**Rules:**
- `clean` means efficiency of 0.90 or more; a clean card has no gap box.
- A died fight's gap box reads "Died at T · show the last 5 s".
- Chips only show for data that exists, such as "Entered at X% hp" from `resource.start_hp`. Rotation is not scored, so there is no rotation chip.
- Warning colours are checked for contrast against the card's actual composited background (panel at the card's alpha, over a dark game frame), not the bare panel.

**Steps:**
- [ ] **Step 1:** Write the failing tests: `test_card_gap`, `test_card_clean`, `test_card_died`, `test_card_minimal_dict`.
- [ ] **Steps 2–4:** RED, implement, GREEN.
- [ ] **Step 5:** Build the painted card. Keep the overlay's position, fade and move behaviour unchanged.
- [ ] **Step 6:** Shoot the 4 states offscreen with `shoot.py --overlay`. Commit.

### Task 12: Whole-branch check and installer

- [ ] **Step 1:** Run the full tests, with and without the PyQt copy.
- [ ] **Step 2:** Shoot every page in the 4 looks and compare side by side with the mock-ups in `docs/design/mockups/`. Fix material differences in one batch.
- [ ] **Step 3:** Run `impeccable detect` on any HTML touched (there should be none). Grep `src/dips_score/ui` for `QColor(` with digits and `#[0-9a-fA-F]{6}` outside `tokens.py`. Expected: none.
- [ ] **Step 4:** Bump `pyproject.toml` to `0.12.0`, run `packaging\build.ps1`, and confirm the fonts are in the PyInstaller output. Do not install.
- [ ] **Step 5:** Commit `0.12.0: every page redesigned`.

---

**Out of scope:**
- Rotation and Pacing scoring: the Pulls page tags Pacing as `preview`, and the Spells page shows refusals but no priority order.
- Persisting cross-visit data: Bosses and Records re-analyse the visits, as the History page does today.
