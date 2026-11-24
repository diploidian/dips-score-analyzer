# Player Profile: design brief and build plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to
> implement this plan task by task. Each implementer loads the skills its task names. This file is
> both the design and the brief; `DESIGN.md` is the binding design system.

## Context

dips score judges single fights and runs, and Habits sums up the last 40 fights. Nothing yet says
what kind of player you are across everything recorded. This adds a **Profile** page: role mix,
where you fight, signature spells, hands, temperament, a one-line label, and how those have moved.
It also adds new add-on recording for what fights cannot show (time, quests, PvP, bars, gold).
The AI coach is a separate workstream; it will later read the profile's data, so the profile's
data module must stand alone as plain data.

Decisions already made by the user: profile first, PyQt6 on the existing kit (HTML mock-up first,
as every other page), impeccable for design review and UI build, label by fixed rules (no AI).

## What exists and gets reused (all on branch `projectArthas`, tip `96ae1c8`)

- `src/dips_score/live/history.py`: `History.fights` (up to 5000 saved fight summaries), `chars`, `book(me)`.
- Each saved fight (`live/summary.py::summarize`) already has: `kind` (PvP / Boss / Dungeon / World),
  `zone`, `duration`, `abilities` (name, casts, damage, share), `healing_role`, `healing`, `damage`,
  `cooldowns` (possible, missed), `lowest_hp`, `result`, `more` (extra enemies), `failed`, `idle`,
  `interrupts`, `dispels`, `level`, `gear`, `spec`, `pull`.
- `src/dips_score/live/habits.py` + `habits_view.py` + `ui/habitsview.py`: the pattern to copy
  (pure data module, pure view-model, widget that only paints). `tests/test_habits.py` shows the test style.
- `src/dips_score/sources/savedvars.py::load_runs`: the add-on's press log per run
  (`A,slot,type,id,src` with K key / C click, `KD`/`KU` holds, `CF` fails, `M` moving, `P` group roles).
- `src/dips_score/scoring/metrics.py`: `Metrics` already counts `by_key`, `by_click` and `click_share`
  from a run's lines (used by `scoring/score.py::_input`); reuse it for Hands.
- `src/dips_score/model/roster.py` and `scoring/classes.py::talent_role`: role from talents.
- `src/dips_score/ui/kit.py`: `Hero`, `Plate`, `BarRows`, `KeyFigures`, `Drawer`, `draw_label_tab`,
  `draw_tag`, `draw_hand_circle`, `draw_hand_note`.
- `src/dips_score/ui/debrief.py`: the entrance (`QVariantAnimation`, `ENTRANCE_MS`, `set_progress`)
  and the reduced-motion switch (`settings["motion"]`). The Profile page uses the same two.
- `src/dips_score/ui/tokens.py` / `theme.tok()`: every colour. `scripts/shoot.py`: offscreen captures.
- `addon/dips-Score/Char.lua`: the probe-then-`pcall` pattern for a client whose calls are not all known to work.
- `DESIGN.md` (the Race Sheet system) and the six page principles in
  `docs/superpowers/plans/2026-11-20-pyqt-redesign-remaining-pages.md` (Global Constraints) are binding.

## Design decisions

**Design Read:** Reading this as: one new dense product page inside an existing desktop app, for a
WoW player glancing between runs, with the app's "Race Sheet" language, leaning toward the existing
DESIGN.md tokens and `ui/kit.py` parts (redesign mode: preserve).

**Dials:** `DESIGN_VARIANCE` 6 (match existing: unequal weight, no symmetry), `MOTION_INTENSITY` 3
(one authored entrance), `VISUAL_DENSITY` 8 (ruled rows, no card boxes).

**Scope note:** dense product UI is outside design-taste's scope (its section 13). Only its
anti-slop rules apply: no equal card wall, no kicker labels, no decorative dots, no invented
numbers. DESIGN.md wins everywhere else. No 3D, so no `threejs-*` skills.

**Composition** (left fluid column, right fixed 460 px column, as the Debrief):

| Part | Content | Kit part |
|---|---|---|
| Hero | Big figure: share of fight time in your main role ("72%", caption "of fight time healing"). Verdict sentence: the label ("Careful dungeon healer who clicks."). Under it, one quiet line with the earlier label when it differs ("Before: reckless world damage dealer."). Meta line as Habits (level, class, spec, gear), ending "last 15 days · n fights". | hero |
| Plate, tab "Worth changing" | The one trait that costs you most (rule below), its figure, and a button "Open Habits". | plate (the only one) |
| Signature (left) | Top 5 spells by presses, bar = share of your damage or healing; your usual opening three presses as one line; drawer "All spells (n)". | ruled bar rows, drawer |
| Hands (left) | Key vs click share, presses per minute, refused-press rate, casting while moving. Says "needs a recorded run" when no run exists. | ruled rows |
| Role mix (right) | Damage / Healer / Tank share of fight time, with the average grade where runs exist (letter always printed). | ruled bar rows |
| Where you fight (right) | Dungeon / Raid / World / PvP share of fight time. | ruled bar rows |
| Temperament (right) | Deaths per hour of fighting, usual pull size, average lowest health, cooldowns used of possible. | ruled rows |
| What changed | No toggle. A row shows a small chip when it moved 5 points or more against Before ("+12 vs the 15 days before"). | chip |
| Highlighter | One mark: circles the row that moved most against Before, with a Caveat note. None when nothing moved or there is no Before. | highlighter mark |
| Earlier (foot of page) | Drawer "Earlier (n)": one ruled row per finished 15-day slice, newest first: the dates, that slice's label, and three figures (main role share, deaths per hour, cooldowns used). Text only; nothing opens from a row. | drawer |

**Windows.** The page always shows the current playing style; there is no all-time view.
- **Now:** fights from the last 15 calendar days, counted back from today. The whole page, the label
  and the plate come from Now only.
- **Before:** fights from days 16 to 30. Used only to say what changed.
- **Earlier slices:** each finished 15-day slice is saved once and never rewritten, in
  `%APPDATA%/dips-score/profile_history.json`, per character: `from`, `to`, `fights`, `label`, and
  the profile's figures as plain data (the AI coach workstream will read them). A slice is saved
  when 15 days have passed since the last saved slice's end. On first run the history is filled in
  from the saved fights, in 15-day blocks counted back from today. A slice with fewer than 10
  fights is not saved.

**Colour rulings (my calls):** share bars (role, place, signature) use `tx2`, never a measure ink.
A Temperament or Hands row that is a scored measure uses that measure's ink (Cooldowns `m-cd`,
Survival `m-surv`, Casting `m-cast`). The 90 target tick is for effectiveness bars only, so share
bars carry no tick. New copy uses no long dashes; the existing "–" empty-value mark stays.

**Label rule** (fixed, same every time): `<temperament> <place> <role>` plus ` who <hands>` when a
hands trait is strong. Defaults, builder may tune and must put in one table in the view-model:
- role: the largest share of fight time; "hybrid" when no role reaches 60%.
- place: the largest share; omitted when none reaches 50%.
- temperament: "careful" (deaths per hour and pull size both in the low band), "reckless" (both high),
  "hoarding" (cooldowns used under 50% of possible), else omitted.
- hands: "clicks" when clicks are 30% or more of presses; "keybinds" when under 5%.

**Plate rule:** first that applies, in this order: clicking 30%+ of presses; cooldowns used under
50% of possible; harmful spells known but never cast (reuse `habits._build_cards`); dying in 15%+ of
fights. Nothing applies: the plate reads "Nothing stands out" with the strongest trait.

**Empty states:** fewer than 10 fights in the last 15 days: "Your profile needs 10 fights from the
last 15 days (n so far)." The Earlier drawer still shows, so a returning player sees who they were.
Fights in Now but none in Before: the page shows normally, with no chips, no mark and no "Before"
line. A section without data shows "–" and one line saying what it needs. Never an invented number.

**Motion thesis** (motion-design, bound by DESIGN.md's Motion section; personality: rigid, zero
overshoot): one entrance per visit to the page. The hero figure counts up over 700 ms; bars grow
from the left over 700 ms with a 60 ms stagger, capped at 8 staggered bars so the cascade stays
under 500 ms; then the highlighter mark draws (550 ms, starting at 900 ms) and the note fades in.
Nothing loops. With reduced motion everything renders settled.
`Allowed patterns:` count-up, bar grow, highlighter draw. Qt animations only;
reuse the entrance code the Debrief already has before writing any.

## Global Constraints

- Branch `dot-oribital/profile` from the tip of `projectArthas`. Never propose merging into `main`.
- Python 3.13+, PyQt6 ≥ 6.6, unittest. No new dependencies.
- Data module and view-model import no PyQt. Widgets only paint the view-model.
- Colours only through `theme.tok()`; no hex or `QColor(r, g, b)` in UI code. Text 11 px or larger,
  4.5:1 in all four looks. Square corners, no shadows, one plate.
- Real data or an honest empty state.
- The profile is per character (the character of the newest fight, as Habits).
- Tests: `python -m unittest discover -s tests`. This PC has no Lua and no PyQt6 in Python 3.14
  (see `tests` skip pattern and `scripts/shoot.py` with a scratch `pip --target` PyQt6).
- Version before each installer build (the project is at `0.15.0`): `0.16.0` for phase 1, `0.17.0`
  for phase 2. Every build
  bundles `addon\dips-Score` and keeps the junction check.

## Phase 1: the profile from data already recorded

1. **Mock-up.** `docs/design/mockups/profile.html` on `assets/theme.css`, linked from `index.html`,
   with real figures from the developer's data or the "illustrative" label. Skills:
   `impeccable:impeccable` (build, then critique), `design-taste-frontend` (anti-slop only),
   `motion-design`. **Gate: the user approves the mock-up in all four looks before task 5.**
2. **Per-fight field.** In `live/summary.py::summarize` add `opener` (the first three cast names).
   Older fights lack it; `replay` fills it in. Tests in `tests/test_live.py`. No `role` field is
   saved: the profile works a fight's role out as "healer" when `healing_role` is set, else the role
   of the fight's saved `spec` (through `talent_role`), else "damage".
3. **Data.** `src/dips_score/live/profile.py::profile(fights, char, book, runs, now) -> dict`:
   shares by role and by kind (weighted by `duration`), top spells, usual opener, hands (from runs,
   reusing `Metrics`), and temperament figures, once for Now and once for Before. `now` is passed in
   so tests are fixed in time. Also `src/dips_score/live/profile_history.py`: load the saved slices,
   fill them in from fights on first run, and add a slice when one finishes; written beside
   `fights.jsonl` the way `History` writes its files. Tests `tests/test_profile.py`: slice edges,
   the 10-fight floor, first-run fill-in, and that a saved slice is not rewritten.
4. **View-model.** `src/dips_score/profile_view.py::build_profile(p, earlier) -> ProfileView`
   (dataclass, as `HabitsView`): hero figure, label, the "Before" line, plate, rows, chips and the
   highlighter target (Now against Before), the Earlier rows, empty states. The label and plate
   tables live here; a slice's saved label comes from the same function. Tests in `tests/test_profile.py`.
5. **Page.** `src/dips_score/ui/profileview.py::ProfilePage` on `ui/kit.py`; a "Profile" entry on
   the rail after Habits in `ui/app.py` (no fight list, as Habits); the entrance motion; a
   `scripts/shoot.py` capture in all four looks. Skills: `impeccable:impeccable`, `motion-design`.
6. **Review.** `impeccable:impeccable-finish-reviewer` against the approved mock-up and
   `impeccable:impeccable-motion-reviewer` on the entrance; fix every material finding.
7. **Docs and build.** `docs/APP-GUIDE.md` and `README.md` gain the Profile; version `0.16.0`; installer.

## Phase 2: new add-on recording, and what it unlocks

8. **Probe first.** A `/dscore probe` command that prints which game calls exist and answer on this
   client (zone and resting state, quest and experience events, honor and battleground results,
   group size, action bar contents and key bindings, money). The user runs it in game; results go
   in `docs/PROBE.md`. **Gate: build only what the probe shows works.**
9. **Recording.** New `addon/dips-Score/Life.lua`, always on and tiny: per-day counters saved as
   flat strings, as `Log.lua` does (seconds per zone and per state: city, instance, resting, solo /
   party / raid; quests accepted and handed in; experience and level-ups; honor kills, battleground
   results, duels; gold earned, spent and repair cost). `Char.lua` gains the action bars:
   `"slot,type,id,key"`. No chat is ever recorded. Add to the `.toc`.
10. **App.** `sources/savedvars.py` reads the new data; `live/profile.py` adds the time budget
    (replacing fight-time shares as the lead for "Where you play"), questing and PvP focus in the
    label, and two plate candidates (an important spell with no key; a spell on the bars never
    pressed). The new figures use the same two windows and are saved into the same slice records.
    Tests with sample saved-variable text.
11. **Page.** Update the mock-up, then the page; same review as task 6; version `0.17.0`; installer.
    Consumables and profession casts are added here only if the probe shows a source for them.

## Review focus

1. A character with only World fights and no recorded run: Hands shows its empty state, the label
   has no hands part, nothing crashes.
2. A healer with no damage fights: Signature ranks by healing share.
3. Two characters in the history: only the newest fight's character is profiled.
4. Fights saved before task 2 (no `opener`) or without a `spec`: counted, role from `healing_role`.
5. Fewer than 10 fights in the last 15 days, and a player back after a month away (Now empty,
   Earlier drawer filled).
6. The day a slice closes: one record is added, earlier records are unchanged.

## Verification

- `python -m unittest discover -s tests` passes; `profile.py` and `profile_view.py` import without PyQt.
- `python -m dips_score --wow "S:\GAMES\BLIZZARD\World of Warcraft\_forever_" replay` with `APPDATA`
  set to a temp folder, then open the Profile page: figures match a hand count on a few fights, the
  meta line says "last 15 days", chips compare against days 16 to 30, and `profile_history.json`
  holds one record per earlier 15-day block with 10 or more fights. Reopen the same day: the
  history file is unchanged.
- `scripts/shoot.py` captures of the page in Timeless and Classical, day and night, beside the mock-up.
- The impeccable finish and motion reviews have no open material finding.
- Phase 2: after a play session and `/reload`, the saved file holds the new lines and the page
  shows the time budget.

## Amendment, 23 Nov: the user's mock-up review (binding; overrides earlier text)

1. **No hands part in the label.** The label is `<temperament> <place> <role>` only. Clicking shows up only as
   the plate, when clicks are 30% or more of keyed + clicked presses.
2. **Cut short by moving, not time moving.** The Hands row is "Cut short by moving": casts the game cut because
   you started to move, and the cast time lost (`Metrics.move_interrupts`, `Metrics.wasted_cast_time`; the run
   dicts gain `move_interrupts` and `wasted_cast_time`). Share for chips: cut casts of all casts.
3. **Raids are told apart.** `summarize` saves the fight's `difficulty` (the tracker already reads it; replay
   fills old fights). Places are Dungeon, Raid, World, PvP: a fight in an instance with a raid difficulty is
   Raid, any other instance is Dungeon. A Boss fight sorts into the instance it was in; a boss outside an
   instance (world bosses, Dalaran) is World. Raid difficulty ids live in one table in `live/profile.py`.
4. **Keys or clicks** stays one Hands row ("Keys or clicks"), with a chip when it moves 5 points. It is not in
   the label.
5. **Colour across the page**, as the Debrief does:
   - scored rows take their measure's ink (`m-cd` cooldowns used, `m-cast` refused presses and cut short by
     moving, `m-surv` deaths and lowest health, `m-act` presses per minute);
   - grade letters and scores take their grade ink (`theme.grade_color`);
   - Role mix bars take new role inks `role-dmg`, `role-heal`, `role-tank`; Where you fight bars take new place
     inks `place-dungeon`, `place-raid`, `place-world`, `place-pvp`. Each new token is added to all four
     theme-mode sets at once (DESIGN.md's Four Sets Rule), in `assets/theme.css`, `ui/tokens.py` and DESIGN.md,
     each clearing 4.5:1 on `panel` where it colours text and 3:1 where it is only a bar;
   - Signature bars take `m-dmg`.
6. **Melee and procs count.** Signature ranks by share of your damage across everything in the fight's
   `abilities`, including "Melee" (auto attack; shown as "Melee (auto attack)" with its swings, not casts) and
   procs (item, racial and seal procs keep their own names). Shares add up to 100% across the All spells list;
   the top-5 rows show the share of all your damage. Spells with no damage still list in All spells with "–".
7. **Restricted spells.** A spell that only works on some enemy types (Exorcism and Holy Wrath: undead and demons;
   Turn Undead: undead; a small table in `live/profile.py`, matched by name) is never named as "never cast"
   unless you met enemies it works on. With creature types recorded (item 8), the plate reads, for example:
   "Exorcism works on undead and demons. You fought 37 of them in 12 fights and cast it 0 times." Without
   creature types for the window, restricted spells are left out of the "never cast" plate.
8. **The add-on records enemy creature types.** New `addon/dips-Score/Types.lua`: on target change, mouseover
   and nameplate added, for a hostile non-player unit, save `name -> creatureType` (`UnitCreatureType`, probed
   and run under `pcall` as `Char.lua` does) in `dipsScoreDB.types` (account-wide, capped at 2000 names, plain
   strings). `sources/savedvars.py` reads it; the profile counts a window's enemies by type from each fight's
   `foes` names. Checked by reading (no Lua here) and then in game by the user.
9. **Earlier rows** show the main role by name with its share ("Damage 96%"), not a bare percent under "Main role".
10. **Look follows the built Habits page** (the PyQt page at `projectArthas`, captured with `scripts/shoot.py
    --tab Habits`): its hero, chip ("+1 pts vs the 9 before" style, boxed in the measure or grade ink), plate,
    and the Fix / Build / Keep card styling where the profile lists traits. The mock-up is revised to match it
    before the page is built.
11. **Out of this plan:** deeper melee and auto-attack tracking across the whole app for every class is its own
    workstream.
