# PyQt Redesign, Phase 1–2 (Theme + Run Debrief) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the approved "Split Sheet, circled" design into the PyQt app: the two new themes with day and night (plus Auto) and the rail "Look" toggle, then the run debrief that replaces the Score tab.

**Architecture:**
- Colours live in one pure-Python token table (`ui/tokens.py`), copied from the mock-ups' `theme.css`. A test fails if the two ever differ.
- `theme.py` derives every colour the app already paints with (`ACCENT`, `BG`, the timeline's meaning colours …) from those tokens, so pages not redrawn yet still follow the theme.
- The debrief is split in two:
  - a pure view-model (`debrief.py`) that turns a `Scorecard` and the fight list into what the page shows (testable without Qt);
  - widgets (`ui/debrief.py`) that only paint it.

**Tech Stack:** Python 3.13+, PyQt6 ≥ 6.6 (QPainter, QSS, `QStyleHints.colorScheme`), unittest, PyInstaller + Inno Setup (`packaging/build.ps1`).

**Spec:**
- `docs/design/spec.md` and `DESIGN.md`.
- The approved mock-ups in `docs/design/mockups/`. `debrief.html` is the composition to match; `assets/theme.css` holds the token values.
- The direction contract in `.impeccable/surfaces/docs-design-mockups-debrief-html.md`.

## Global Constraints

- **Base:** build on `projectArthas` (tip `5dbc222`, which has the installer and folder settings), not on `main`. Task 0 brings the design commit `5a2ac67` across.
- **Themes:**
  - Exactly two: `timeless` and `classical`.
  - Modes: `day`, `night` and `auto`. Auto follows Windows' light/dark setting.
  - Defaults: theme `timeless`, mode `auto`.
  - Saved `"wow"` or `"classic"` from older settings load as `timeless`. The Classic and Azeroth looks are retired. **Decision for the user to confirm at plan review.**
- **Colours:** every colour comes from the token table. No new hex literals in UI code except inside `tokens.py`.
- **Fonts:**
  - Barlow (400, 500, 600) for UI and body.
  - Barlow Condensed (500, 600, 700) for numbers, headings and labels.
  - Caveat only for hand marks.
  - Bundled under `src/dips_score/ui/fonts/` with their OFL licence, so nothing relies on installed fonts.
- **Grade bands are unchanged:** S ≥90, A ≥80, B ≥70, C ≥60, D ≥45, F below. The grade letter is always drawn next to any grade colour.
- **One solid plate per page.** On the debrief it is "Fix this first".
- **No functional text under 11px.** Body and muted text must be ≥ 4.5:1 against its background in all four theme combinations; the token values already meet this.
- **Every category in a card is reachable on the debrief.** Today `ScorePanel` shows only the first 6 rows (`pages.py:117`); that cap goes.
- **Version:** bump `pyproject.toml` to `0.11.0` before the next installer build (a large change, per the project's versioning rule).
- **Tests:** `python -m unittest discover -s tests`. Pure modules must not import PyQt, because the dev PC's Python has no PyQt6.
- **Widget checks:** use the offscreen screenshot script `scripts/shoot.py`, created in Task 2.

## Review Focus

1. **Runs with more than 64 fights** (long sessions). The grid grows past 8 rows. Expected: it scrolls, and the circles stay on the right cells. Covered by `test_review_long_run` and the Task 8 screenshot with 70 fights.
2. **Nothing or little to review.** Every fight ≥ 90, or fewer than 4 fights below 90. Expected: no empty circles; the note reads "review these 2", or "every fight 90+" with no circles. Covered by `test_review_none` and `test_review_few`.
3. **Empty or unjudgeable card.** No combat, or grade `-` (advanced logging off). Expected: the hero shows "–" with the card's note, the plate shows its empty state, and nothing crashes. Covered by `test_view_empty_card`.
4. **Healer and tank roles.** Expected: the measures and breakdown use that role's categories (e.g. Group health, Response) with colours from the fallback table, never a KeyError. Covered by `test_measures_healer` and `test_measures_tank`.
5. **Info-only categories and user-edited weights.** Weight 0 or unavailable categories (Interrupts with none used, Movement, Positioning) never appear in the breakdown or measures. Changing a weight changes the points lost. Covered by `test_points_lost_excludes_info` and `test_points_lost_follows_weights`.

---

### Task 0: Branch and design files

**Files:** none edited. Git only.

- [ ] **Step 1:** Create a branch from `projectArthas`. If there is no worktree yet, use superpowers:using-git-worktrees. Cherry-pick `5a2ac67` (mock-ups, spec, PRODUCT.md, DESIGN.md, theme tokens).
- [ ] **Step 2:** Run `python -m unittest discover -s tests`. Expected: the same pass count as on `projectArthas`, with 0 failures.

### Task 1: Token table

**Files:**
- Create: `src/dips_score/ui/tokens.py` (pure Python, no Qt)
- Test: `tests/test_tokens.py`

**Interfaces — produces:**
- `THEMES: dict[str, str]`. Exactly `{"timeless": "Timeless", "classical": "Classical"}`, in that order.
- `MODES = ("day", "night", "auto")`
- `TOKENS: dict[tuple[str, str], dict[str, str]]`. Keys are `(theme, "day"|"night")`. Values map the 36 token names in `theme.css` without the `--` (`bg`, `panel`, `ln`, `track`, `rail`, `rail-on`, `rail-tx`, `rail-mu`, `rail-ac`, `tx`, `tx2`, `mu`, `plate`, `plate-tx`, `plate-mu`, `plate-ac`, `plate-ln`, `btn`, `btn-tx`, `btn-ln`, `gold`, `gS` … `gD`, `hl`, `hl-note`, `m-dmg`, `m-cd`, `m-rot`, `m-pace`, `m-surv`, `m-upk`, `m-cast`, `m-act`) to `"#RRGGBB"`. `btn-ln` may be `"transparent"`.
- `MEASURE_INK: dict[str, str]`. Category name to token name:
  - Damage → `m-dmg`
  - Cooldowns → `m-cd`
  - Rotation → `m-rot`
  - Pacing → `m-pace`
  - Survival → `m-surv`
  - Upkeep → `m-upk`
  - Casting → `m-cast`
  - Activity → `m-act`
  - Group health → `m-surv`
  - Response → `m-cd`
  - Efficiency → `m-dmg`
  - Holding mobs → `m-dmg`
  - Pickups → `m-cd`
  - Interrupts → `m-cast`
  - Movement → `m-pace`
  - Input → `m-act`
  - Resource → `m-upk`
  - Positioning → `m-act`
- `def ink_for(category: str) -> str`. Returns `MEASURE_INK` or `"m-act"` for an unknown name.
- `def normalize(theme: str | None, mode: str | None) -> tuple[str, str]`. Unknown or legacy themes (`"wow"`, `"classic"`, `None`) become `"timeless"`. Unknown modes become `"auto"`.
- `def resolve(mode: str, os_dark: bool) -> str`. Returns `"day"` or `"night"`.

- [ ] **Step 1: Write the failing tests**
  - `test_tokens_match_css`: parse the four `html[data-theme=…][data-mode=…]` blocks of `docs/design/mockups/assets/theme.css`. The `:root` block shares its values with Timeless Day. Assert each `TOKENS[(theme, mode)]` equals the parsed dict exactly, keys and lower-cased hex values.
  - `test_normalize`:
    - `normalize("wow", None) == ("timeless", "auto")`
    - `normalize("classic", "night") == ("timeless", "night")`
    - `normalize("classical", "bogus") == ("classical", "auto")`
  - `test_resolve`:
    - `resolve("auto", True) == "night"`
    - `resolve("auto", False) == "day"`
    - `resolve("day", True) == "day"`
  - `test_ink_for`: `ink_for("Cooldowns") == "m-cd"` and `ink_for("Something new") == "m-act"`.
- [ ] **Step 2:** Run `python -m unittest tests.test_tokens -v`. Expected: FAIL with ImportError.
- [ ] **Step 3:** Implement `tokens.py`, copying the values from `theme.css`.
- [ ] **Step 4:** Run the same command. Expected: 4 passed.
- [ ] **Step 5:** Commit `tokens: the four theme token sets, checked against the mock-ups' theme.css`.

### Task 2: Theme, fonts and settings

**Files:**
- Modify: `src/dips_score/ui/theme.py` (whole module)
- Modify: `src/dips_score/ui/settings.py` (`DEFAULTS`, the theme radio list)
- Modify: `src/dips_score/ui/app.py:431-441` (`apply_look`)
- Create: `src/dips_score/ui/fonts/` with Barlow-Regular/Medium/SemiBold, BarlowCondensed-Medium/SemiBold/Bold, the Caveat variable font and `OFL.txt`, all from github.com/google/fonts `ofl/`
- Modify: `packaging/build.ps1`. Add `--add-data "..\src\dips_score\ui\fonts;dips_score\ui\fonts"`. The spec path is `build`, so the source is relative to it.
- Create: `scripts/shoot.py` (dev only, not packaged). Usage: `--saved <path> --run <n> --tab <name> --look <theme>,<mode> --size WxH --out <png>`.
  - It builds the window offscreen, opens the run on the named tab, waits 400 ms and saves `grab()`.
  - It uses the memory recipe: `QT_QPA_PLATFORM=offscreen`, `QT_QPA_FONTDIR=C:\Windows\Fonts`, PyQt6 installed with `pip --target` into a scratch folder.
  - APPDATA points at a temp folder so the user's history and settings are untouched.

**Interfaces:**
- Consumes: `tokens.TOKENS`, `tokens.normalize`, `tokens.resolve`.
- Produces in `theme.py`:
  - Module values: `NAME: str` (theme), `MODE: str` (`"day"|"night"`, resolved), `T: dict[str, QColor]` (the current token set).
  - `def apply(name: str, mode: str = "auto", os_dark: bool = False) -> None`.
  - `def tok(key: str) -> QColor` (a copy of `T[key]`).
  - `def load_fonts() -> None`. Idempotent; uses `QFontDatabase.addApplicationFont` on every file in `fonts/`.
  - `FONT = "Barlow"`, `NUM_FONT = "Barlow Condensed"`, `HAND_FONT = "Caveat"`.
  - `grade_color(grade) -> QColor` returns `gS`…`gD`, with `gD` for `F`.
  - `score_color(s) -> QColor`: ≥85 `gS`, ≥65 `gB`, ≥45 `gC`, else `gD`.
  - `stylesheet() -> str`.
- Legacy names. Keep them so untouched pages follow the theme, all set in `apply()` from `T`:

  | Legacy | Token |
  |---|---|
  | ACCENT | `gold` |
  | BG | `bg` |
  | PANEL | `panel` |
  | LANE | `track` |
  | GRID | `ln` at alpha 120 |
  | TEXT | `tx` |
  | DIM | `mu` |
  | EDGE | `ln` |
  | SELECT | `track` |
  | TITLE | `tx` |
  | COMBAT | `plate` at alpha 45 |
  | BOSS | `gC` at alpha 70 |
  | BUSY | `m-dmg` |
  | IDLE | `m-surv` |
  | CAST | `m-cast` |
  | CAST_OK | `m-pace` |
  | CAST_BAD | `gD` |
  | FAIL | `hl-note` |
  | KEY | `tx2` |
  | CLICK | `hl` |
  | SPAM | `gD` |
  | MOVE | `m-upk` |
  | HP | `m-dmg` |
  | HP_LOW | `gD` |
  | HIT | `gD` at alpha 160 |
  | DEATH | `gD` |

- `stylesheet()` is flat and square, matching DESIGN.md:
  - No border-radius and no gradients.
  - Panels and tables: 1px `ln` borders on `panel`.
  - `QTabBar::tab`: selected gets an inset 1px `tx` frame (`border: 1px solid tx`) and weight 600.
  - `QPushButton`: `btn`/`btn-tx`, 1px `btn-ln` border, or `ln` when transparent.
  - `#rail` (the left column): background `rail`, text `rail-tx`; `#rail QLabel#dim` gets `rail-mu`.
  - `QToolTip`: `panel` with a `ln` border.
  - Selection: `hl` on `bg`.
  - The texture option keeps working as today.
- `settings.DEFAULTS`: `"theme": "timeless"`, plus `"mode": "auto"`. `load()` passes both through `tokens.normalize`.

- [ ] **Step 1:** Add `test_settings_legacy_theme` to `tests/test_tokens.py`. It writes `{"theme": "wow"}` to a temp settings file and asserts `settings.load(paths)["theme"] == "timeless"` and `["mode"] == "auto"`. If `settings.py` imports Qt, move `DEFAULTS` and `load` into a pure `ui/settings_store.py` and re-export them from `settings.py`.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement the `theme.py`, `settings` and `apply_look` changes.
  - `apply_look` calls `theme.load_fonts()` and then `theme.apply(settings["theme"], settings["mode"], os_dark)`.
  - `os_dark` is `QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark`.
- [ ] **Step 4:** Run the unit tests. Expected: all pass. Then write `scripts/shoot.py` and capture the existing window on each tab in Timeless Day and Classical Night. Expected: every page (Group, Pulls, Spells, Summary, Habits, timeline) renders in the new colours, with no white-on-ivory text.
- [ ] **Step 5:** Commit `theme: Timeless and Classical, day and night, bundled Barlow/Caveat`.

### Task 3: The rail and its Look toggle

**Files:**
- Modify: `src/dips_score/ui/app.py:52-98` (the left column) and `_set_theme`

**Interfaces:**
- Consumes: `theme.apply`, `settings`.
- Produces:
  - `Window._set_look(theme: str | None = None, mode: str | None = None) -> None`. Saves the settings, reapplies the theme and re-shows what's open (what `_set_theme` does today).
  - `_set_theme` becomes a one-line call to it.

- [ ] **Step 1:** Give the left column `setObjectName("rail")`. Under the reload/cog row, add a "Look" label (Barlow Condensed 11px, 0.12em, uppercase, `rail-mu`) and two rows of checkable `QPushButton`s:
  - one exclusive group: Classical | Timeless;
  - one exclusive group: Day | Night | Auto.

  The checked state comes from the settings. Clicking calls `_set_look`.
- [ ] **Step 2:** Connect `QGuiApplication.styleHints().colorSchemeChanged` to re-apply the theme when the mode is `auto`.
- [ ] **Step 3:** Rename the `"Score"` tab to `"Debrief"`.
- [ ] **Step 4: Verify.**
  - `scripts/shoot.py --look classical,night` (it clicks Classical, then Night). Expected: the rail and all tabs switch, and the choice survives a restart (settings.json holds `"theme": "classical", "mode": "night"`).
  - Unit tests still pass.
- [ ] **Step 5:** Commit `rail: Look toggle (theme, day/night/auto) that follows Windows`.

### Task 4: Points lost and the fix order

**Files:**
- Modify: `src/dips_score/scoring/score.py` (`Scorecard`, around lines 169-187)
- Test: `tests/test_debrief.py`

**Interfaces — produces:**
- `Scorecard.points_lost() -> list[tuple[Category, float]]`. For counted categories only, `weight × (100 − score) / Σcounted weights`, largest first. Categories with `round(lost, 1) == 0` are dropped.
- `Scorecard.tips` returns the tips of the 3 categories with the most points lost that have a tip and a score < 85. Today it sorts by lowest score.

- [ ] **Step 1: Write the failing tests.** Use a card built from the real Blackfathom numbers: `Category(name, score, weight, summary, tip)` for Damage 97/20, Activity 90/15, Cooldowns 23/10, Interrupts 0/10 unavailable, Casting 80/10, Movement 100/0, Survival 53/10, Upkeep 59/5, Input 100/5, Positioning 39/0.
  - `test_points_lost_blackfathom`: names in order `["Cooldowns", "Survival", "Upkeep", "Casting", "Activity", "Damage"]`, values rounded to 1 = `[10.3, 6.3, 2.7, 2.7, 2.0, 0.8]`, and the values sum to `100 − total` within 0.05.
  - `test_points_lost_excludes_info`: no Interrupts, Movement, Positioning or Input (Input lost 0).
  - `test_points_lost_follows_weights`: Survival weight 20 makes Survival first.
  - `test_tips_by_points_lost`: with tips on Cooldowns, Survival and Upkeep, `card.tips` is in that order.
- [ ] **Step 2:** Run `python -m unittest tests.test_debrief -v`. Expected: FAIL.
- [ ] **Step 3:** Implement. `_card`'s formula is unchanged.
- [ ] **Step 4:** Run the same command. Expected: PASS. The full suite also passes, since report and overlay output use `tips` and only the order changed.
- [ ] **Step 5:** Commit `score: points lost per category; Work on tips ordered by points lost`.

### Task 5: The debrief view-model

**Files:**
- Create: `src/dips_score/debrief.py` (pure, no Qt)
- Test: `tests/test_debrief.py`

**Interfaces:**
- Consumes: `Scorecard.points_lost()`, `Scorecard.tips`, `tokens.ink_for`.
- Produces:

```python
@dataclass
class FightCell:  index: int; at: str; label: str; score: int | None; grade: str; boss: bool; died: bool; start: float; end: float
@dataclass
class Measure:    name: str; score: float | None; ink: str; reason: str; on_target: bool
@dataclass
class Lost:       name: str; points: float; ink: str
@dataclass
class Fix:        title: str; points: float; category: str; damage: str | None   # damage like "~1,177 damage"
@dataclass
class DebriefView:
    total: str; grade: str; role: str; note: str; verdict: str
    fix: Fix | None; next_fixes: list[Fix]; measures: list[Measure]; lost: list[Lost]; earned: int
    fights: list[FightCell]; review: list[int]           # review: FightCell.index values, chronological
def build_view(card: Scorecard, fights: list[FightCell], damage_share: float | None, deaths: int) -> DebriefView
def fight_cells(a) -> list[FightCell]      # adapter over Analysis; reuses ScoreTab's dead_in logic (pages.py:282-287)
```

Rules the tests pin:
- **Measure names:** Cooldowns shows as "Abilities on time"; everything else uses its category name.
- **Measures:** the 4 counted categories with the highest weight, ties in card order. The reason is the category summary cut at its first `;`. `on_target = score >= 90`.
- **Fix:** the top `points_lost` category that has a tip. The title is the tip up to its first `" ("` or `". "`, and `damage` is the first match of `~[\d,]+ damage`. `next_fixes` are the next two, the same way.
- **Verdict:**
  - If `damage_share` is set and Damage scored ≥ 85: `f"Strong damage — {damage_share:.0%} of an even share — but {fix.title}."` The title keeps its capital, since it usually starts with a spell name.
  - Otherwise: `f"{fix.title}."`
  - Append `" and you died once"` (or `" and you died {deaths} times"`) before the final period when `deaths > 0` and the fix category isn't Survival.
  - With no fix: `"Nothing stands out — nice run."`
- **Review:** fights with a score below 90. Take the 4 lowest (ties go to the earliest), then put them in chronological order.
- **Empty card:** `total "–"`, `grade "-"`, `note = card.note`, `fix None`, empty lists.

- [ ] **Step 1: Write the failing tests** (in `tests/test_debrief.py`, Blackfathom card from Task 4):
  - `test_view_blackfathom`:
    - `fix.title == "Consecration sat ready 75s while you were free to use it"`, `fix.points == 10.3` (rounded) and `fix.damage == "~1,177 damage"`;
    - `verdict == "Strong damage — 128% of an even share — but Consecration sat ready 75s while you were free to use it and you died once."`;
    - measures named `["Damage", "Activity", "Abilities on time", "Casting"]`;
    - `earned == 75`.
  - `test_review_blackfathom`: cells from the real fight list (scores in `spec.md`, 64 fights) give review fights at 6:25, 43:57, 64:26, 69:28.
  - `test_review_long_run`: 70 cells, the 4 lowest at indices 2, 65, 30, 68, gives `[2, 30, 65, 68]`.
  - `test_review_none`: all ≥ 90 gives `[]`.
  - `test_review_few`: two below 90 gives those two.
  - `test_view_empty_card`.
  - `test_measures_healer`: Group health 35, Response 35, Efficiency 20, Casting 10, giving those four with inks `m-surv`, `m-cd`, `m-dmg`, `m-cast`.
  - `test_measures_tank`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit `debrief: view-model (fix, verdict, measures, points lost, review list)`.

### Task 6: Debrief widgets: hero, plate, measures, breakdown

**Files:**
- Create: `src/dips_score/ui/debrief.py`
- Modify: `src/dips_score/ui/pages.py`. `ScoreTab` hosts `DebriefPage` in place of `ScorePanel` and the fights table. Remove `ScorePanel` and `Bar` if nothing else uses them; grep first.

**Interfaces:**
- Consumes: `DebriefView`, `theme.tok`, `theme.NUM_FONT`/`FONT`.
- Produces:
  - `class DebriefPage(QWidget)`, with:
    - `show_view(view: DebriefView, title: str, sub: str) -> None`;
    - signals `zoom = pyqtSignal(float, float)` and `picked = pyqtSignal(int)` (fight index, or -1 for the whole run).
  - Children, each a `QWidget` that paints itself: `Hero`, `FixPlate`, `MeasureBars`, `Breakdown`. Task 7 adds `FightGrid`.

Layout, from `debrief.html`, at 1440×900 and 1360×900:
- Two columns: left takes the remaining width; right is 460 px for the grid.
- Left, top to bottom:
  1. **Hero:** Barlow Condensed 700 at 150px; 126px below 1420px window width. The boxed grade beside it has a 2px `gold` frame and the letter in its grade ink. The verdict sits underneath.
  2. **FixPlate,** on `plate`:
     - "Fix this first" label box straddling the top edge;
     - title in 23px Barlow Condensed 600;
     - "−{points} points" in 32px `plate-ac`, then the category and damage in 13px `plate-mu`;
     - the "Show me on the timeline" button;
     - a `plate-ln` rule, then `next_fixes` rows (12–13px, values in `plate-ac`).
  3. **MeasureBars:** name; a 10px bar on `track` filled with the measure's ink; a 2px `tx` tick at 90; the reason in 11px `mu`; the value in 30px Barlow Condensed with "on target" or "below 90" in 11px `mu`. A `preview` tag is shown when the category name is Rotation or Pacing.
  4. **Breakdown:** rows of name, a bar whose length is ∝ points and at most 220px in the category's ink, and the value right-aligned. Hairline `ln` rules between rows, then a 2px `tx` rule and "Earned · {earned} of 100".
- Section names are boxed label tabs (Barlow Condensed 700, 11px, 0.16em, uppercase, 1px `ln` frame on `panel`), never a label above a heading.
- **Empty states:**
  - fix None: the plate reads "Nothing stands out — nice run." with no button;
  - empty card: the hero shows "–" and `note`, and the measure and breakdown sections are hidden.
- **Show me:** emits `zoom` on the fight whose own card lost the most points in the fix's category (padded the way `ScoreTab._pick` does).

- [ ] **Step 1:** Implement the widgets and wire `ScoreTab`. Keep the player combo. `set_analysis` builds the view through `build_view(...)`, using `a.card` for you and `pl.card` / `player_card(...)` for others, as today.
- [ ] **Step 2:** Run `scripts/shoot.py --tab Debrief` (left column only until Task 7 lands). Expected: the content matches `docs/design/mockups/debrief.html` with the same `#timeless-day-still` look, and "Earned · 75 of 100" is visible above 900px at 1360 wide.
- [ ] **Step 3:** Run the unit tests. Expected: all pass.
- [ ] **Step 4:** Commit `debrief: hero, fix plate, measures and points breakdown replace the Score card`.

### Task 7: Fight grid with hand marks

**Files:**
- Modify: `src/dips_score/ui/debrief.py` (add `FightGrid`)

**Interfaces:**
- Consumes: `DebriefView.fights` and `.review`, `theme.HAND_FONT`.
- Produces: `class FightGrid(QWidget)`, with `set_cells(cells: list[FightCell], review: list[int]) -> None` and signal `picked(int)`.

Painting, with cells 54×75 px, 8 columns and a 1px `gold` outer frame:
1. Cell grounds and inset `ln` hairlines.
2. Highlighter strokes in `hl`:
   - circles: an ellipse of rx 31, ry 26 centred on the score row of each review cell, 5px wide, slightly rotated per cell (alternate −5°/+4°);
   - the route: quadratic curves between consecutive circles, 1.6px at 60% opacity;
   - the death cross: an 8px "×" drawn as two lines at the lower-left of a died review cell's circle.
3. Cell text, each glyph run with a 3px `panel` halo (`QPainterPath.addText`, stroked in `panel`, then filled):
   - the number and time: Barlow Condensed 11px, `mu`;
   - the score: 21px Barlow Condensed 700;
   - the grade letter: 14px in its grade ink;
   - a 6×6 `tx` square top-right on bosses.
4. Above the grid: the Caveat 27px note in `hl-note`, with an arrow to the first circle. It reads "review these {n}", or "every fight 90+" when `review` is empty.

More than 8 rows: the grid sits in a `QScrollArea` that is 608px tall. Clicking a cell emits `picked(index)`, and the page then shows that fight's card with a "Whole run" button, as `ScoreTab._pick` does today.

- [ ] **Step 1:** Implement `FightGrid` and add it to `DebriefPage`. The header line reads "FIGHTS · {n} · circled = review first", plus the grade key.
- [ ] **Step 2:** With `scripts/shoot.py --tab Debrief`, capture Blackfathom (run 6 in the dev save) in 4 looks at 1440×900, plus Timeless Day at 1360×900.
- [ ] **Step 3: Verify by eye** against `.impeccable/review/debrief-*.png` (the mock-up captures):
  - the circles sit on 6:25, 43:57, 64:26 and 69:28;
  - all cell text reads through the route;
  - nothing clips at 900px.
  
  Also capture a synthetic 70-fight run (duplicate fights in a test fixture) and check the grid scrolls with the circles on the right cells.
- [ ] **Step 4:** Commit `debrief: fight grid with the four fights to review circled`.

### Task 8: Entrance motion

**Files:** modify `src/dips_score/ui/debrief.py` and `ui/settings.py` (`DEFAULTS["motion"] = True`, plus a checkbox in the Settings dialog's Look group).

- [ ] **Step 1:** One `QVariantAnimation` from 0 to 1 over 900 ms (OutQuart) on each `show_view`. Then:
  - the hero number ticks from 0 to its total over the first 700 ms;
  - each bar's fill length is scaled by `clamp((p − i·0.06) / 0.6)`;
  - the circles draw on in review order with `QPainterPath` `percentAtLength` trimming, starting at 0.55;
  - the note fades in last.
  
  With `motion` off, or in `scripts/shoot.py`, p = 1 immediately.
- [ ] **Step 2:** Manually check a run opens with the animation and that switching theme does not replay it. Check the screenshot script still captures the settled state.
- [ ] **Step 3:** Commit `debrief: one entrance (ticker, bars, circles), off in settings`.

### Task 9: Whole-branch check and installer

- [ ] **Step 1:** Run `python -m unittest discover -s tests`. Expected: all pass.
- [ ] **Step 2:** Re-shoot the 4 looks. Compare them side by side with `.impeccable/review/debrief-*.png`, then fix material differences in one batch.
- [ ] **Step 3:** Bump `pyproject.toml` to `0.11.0`. Run `packaging\build.ps1`. Expected: `dist\dips-score-setup-0.11.0.exe` exists. Install it and confirm the fonts load in the installed app (the title is Barlow Condensed, not Segoe UI).
- [ ] **Step 4:** Commit `0.11.0: redesigned debrief and Timeless/Classical themes`.

---

**Out of scope here (next plans):**
- Restyling the after-fight overlay card, dungeon history, group/podium, Fights and Habits pages. They follow the theme after Task 2 but keep their layouts.
- Rotation and Pacing scoring (per-class priority lists, pull safety) and their weights.
