# All traits: say what each number is, and fix the misleading ones

## Context

The user finds the All traits scores arbitrary: "Abilities that count 4, next at 6", "Fights alone
56%, Wandering at 70%: what's the percent based off of?" Three causes in the code:
- `TraitRow.note` (what the figure is) exists but `TraitTable` never paints it.
- The bar runs between two hidden ends. Fights alone starts at 55%, so 56% looks empty.
- The sample ("of 1,209 fights") is worked out, then dropped in `score_of`.

Fable advised and the humanizer guide sets the wording. Some scores were also misleading; the user
asked to fix those and "everything you think is incorrect or could be explained better". Placement the
user chose: a plain line and the bar's two ends on every row, the rest on hover.

Base: `projectArthas` at `60f007a`. Branch: `dot-oribital/trait-words` from its tip.

## The row and the hover

```
Fights alone                                 56%
[=|--------------|-------|-------|-----------]
55%   share of fights with no group or help   97%

hover: Fights with no group, where others did at most 10% of your damage and
       gave at most 10% of your healing.
       You: 681 of 1,209 fights in the last 15 days.
       Wandering from 70%, Lone from 81%, Sovereign from 91%.
```

- The "X at 70%, you are at 56%" line goes; all three tier marks are in the hover.
- One line at the top of the open drawer: "Each bar runs between two ends this app chose by hand. They
  don't compare you with other players. Hover a trait to see how it's worked out."
- The accessible name of the table holds every line and hover text, so nothing is hover-only for a
  screen reader. No new focus handling (the table is one painted part).
- Benefactor's and Lifegiver's extra parts move to the hover. Their names stay (the user chose them).

## Scores that change

| Trait | Now | Becomes | Your result |
|---|---|---|---|
| Abilities that count (`Range`) | 5% of ALL damage, scale 3 to 9; swings make 9 impossible | **Main damage abilities**: 5% of ability damage, scale 2 to 8 | 4 (Judgement 32%, Seal of Command 26%, Holy Strike 24%, Consecration 16%); Adaptable from 5 |
| Top of the group (`Lead`) | fights ranked 1st; in a duo that is 50% by luck | **Groupmates out-damaged**: the average share of groupmates below you, so 50% is an even share in any group size; scale 30% to 85% | 37% (23% in duos, 74% in groups of five); Rising from 50% |
| Wins under 10% health (`Brink`) | a total, so it grows with playtime | per 100 wins, at least 100 wins, scale 0.2 to 1.7 | 1.2 per 100 (12 of 1,028); stays Defiant |
| Deaths and lowest health (`Guard`) | shows only the weaker figure, the next tier needs both | the row shows both; the bar is the weaker, and says which | 3.4 deaths per 100, 67% lowest |
| Help for the group (`Mercy`) | the figure could be dispels or healing | the row is named after the figure that scores: "Share of group healing" or "Dispels on others" | 11% share of group healing |

Not first places against your even share, as I first offered: that ratio lets a five-man group score
far more than a duo. Out-damaging groupmates reads the same in every size.

Kept, explained better: Boss kills, zones, enemies, Benefactor, Lifegiver, longest sitting and longest run
stay totals and say "in 15 days". Fights won and Nobody got away share their wins; the hovers say that
the second leaves out your deaths. Melee, auto shot, ability, proc and focus shares say they are a style.

Saved 15-day slices are never rewritten, so older ones keep scores from the old rules. Trait keys do
not change, so named titles keep working. "the Crownbreaker" and "the Full Quiver" use Lead and Range.

## Wording (row line, then hover; `{}` filled from your fights)

Plain verbs, short, no dashes, nothing a hover repeats from the row. Draft for the user's review:

| Trait | Row line | Hover, first line | You: |
|---|---|---|---|
| Overheal | healing that landed on full health | Healing past a full health bar, as a share of all healing you cast while healing. | {v} across {n} fights |
| Fights nobody died | group fights where everyone lived | Group fights with no deaths, yours included. | {hits} of {n} group fights |
| Hits avoided | swings at you that missed | Swings that missed or that you dodged, parried or blocked. | {hits} of {n} swings |
| Time between fights | usual wait between fights | The middle wait, half are shorter. A wait of 30 minutes or more starts a new sitting and is left out. | {v} over {n} waits |
| Wins under 15 seconds | wins that took under 15 s | Won fights shorter than 15 seconds. | {hits} of {n} wins |
| Fight length | length of your usual fight | The middle fight, half are shorter. | {v} over {n} fights |
| Longest sitting | fights in your longest sitting, 15 days | The most fights without a break of 30 minutes. | {v} fights in one sitting |
| Longest run without a death | fights in a row survived, 15 days | The longest run of fights between two deaths. | {v} of {n} fights |
| Wins on the edge | wins after falling under 35% health | Won fights where your health fell under 35%. | {hits} of {n} wins |
| Wins under 10% health | per 100 wins | Wins where your health fell under 10%, for every 100 you won. | {count} of {n} wins |
| Deaths and lowest health | deaths per 100 fights, and average lowest health | Two figures; the weaker one sets the bar and the tier. Lowest health is the lowest point in each fight, averaged. | {v1} and {v2}, {n} fights |
| Close calls answered | close calls met with a defensive | A close call is under 35% health. It counts when you used a defensive within 10 s, or one was ready. | {hits} of {n} close calls |
| Wins against three or more | wins alone against three or more | Solo wins with three or more enemies in the fight. A tank's group wins count too. | {hits} of {n} wins |
| Wins one on one | solo fights with one enemy, won | Fights alone against a single enemy that ended with it dead. | {hits} of {n} fights |
| Fights won | fights where every enemy died | Every enemy died and you lived. | {hits} of {n} fights |
| Nobody got away | fights you lived through, won | Won fights, out of those you lived through and did damage in. Your deaths are left out, so this is higher than Fights won. | {hits} of {n} fights |
| Boss kills | bosses beaten in 15 days | Boss fights you won. More playing raises it. | {v} bosses |
| Player fights won | fights against players, won | Fights with a player in them that you won. | {hits} of {n} fights |
| Most beaten enemy | of your kills are one enemy | The enemy name you beat most, as a share of all you beat. | {v} of {n} enemies |
| Melee share | of your damage is weapon swings | Auto attacks with your weapon. A style: higher isn't better. | {v} of damage in {n} fights |
| Auto shot share | of your damage is auto shots | Auto Shot and wand Shoot. A style: higher isn't better. | {v} of damage in {n} fights |
| Ability share | of your damage is abilities | Spells and abilities you cast. A style: higher isn't better. | {v} of damage in {n} fights |
| Top ability's share | of ability damage is one ability | Your biggest ability, as a share of ability damage. A style: higher isn't better. | {v}, {name} |
| Main damage abilities | abilities with 5% of ability damage | Abilities you cast that did 5% or more of your ability damage. Swings, procs and pets are left out. | {v}: {names with shares} |
| Critical hits | hits that crit | Damaging hits that crit, pets left out. | {v} of {n} hits |
| Proc and item share | of your damage is procs and items | Damage with no cast of yours behind it: procs, items, shields that hit back. | {v} of damage in {n} fights |
| Possible damage reached | damage done of what was possible | Your damage over the most the app worked out you could have done, given cooldowns and swings. | {v} across {n} fights |
| Cooldowns used | cooldown uses out of possible | Uses of your ready cooldowns, out of the times they could have been used. | {hits} of {n} uses |
| Casts not cut short | casts you didn't cut by moving | Casts in recorded runs that moving did not cancel. | {v} of {n} casts |
| Pulled with your usual buffs | pulls with all your usual buffs | A usual buff is one you had up at 60% of pulls. | {hits} of {n} pulls |
| Interrupts | per 100 group fights | Enemy casts you interrupted, for every 100 group fights. | {v} over {n} fights |
| Fights alone | share of fights with no group or help | Fights with no group, where others did at most 10% of your damage and gave at most 10% of your healing. | {hits} of {n} fights |
| Fights in a group | share of fights in a group | Fights where a groupmate did damage or healing. | {hits} of {n} fights |
| Groupmates out-damaged | groupmates you out-damaged, on average | In each group fight, the share of groupmates with less damage than you. 50% is an even share. Easier against healers and tanks. | {v} across {n} fights |
| Share of group healing | healing on others that was yours | Your healing on groupmates, out of all the healing the group gave each other. | {v} in {n} fights |
| Dispels on others | per 100 group fights | Debuffs you removed from groupmates, for every 100 group fights. | {v} over {n} fights |
| Benefactor | strangers helped in 15 days | Players outside your group you buffed, healed or cleansed by casting on them. Each counts once a day; auras don't. | {v} strangers, and {b} buffs for your group |
| Lifegiver | revives cast in 15 days | Every revive you cast. The log doesn't say if it was accepted. | {v}: {g} in your group, {s} strangers |
| Zones fought in | zones with five fights, 15 days | Zones where you had at least five fights. | {v} zones |
| Different enemies beaten | enemy kinds beaten in 15 days | Different enemy names in fights you won. | {v} of {n} fights |

Before shipping I check each line against its code in `raw()`; a line the code doesn't support is corrected.

## Changes

- `live/traits.py`: `Trait` gains `line` and `how`; `score_of` also returns `n`, `low`, `high`, and for
  Guard both parts; new `Range`, `Lead` and `Brink` figures in `raw()` and `damage_split` (which also
  returns the counted abilities' names and shares); new anchors.
- `profile_view.py`: `TraitRow` gains `line`, `ends` ("55%", "97%"), `tip`; `next` goes. Mercy's name from
  its figure, Guard's two figures. Tier marks from `traits.needs` (already rounds toward the tier).
  `_trait_row` must accept a trait entry without the new keys (a saved one).
- `ui/kit.py`: `Tips` (the hover helper) moves here from `ui/group.py`, which imports it. The tip is
  escaped rich text so long lines wrap.
- `ui/profileview.py`: `TraitTable(Tips)` paints the top line, the ends and the row line, records one rect
  per row, and puts line and tip in the accessible name.
- `titles.py`: How you fight rows and captions follow the new names and figures.
- `docs/GUIDE.md` traits table, `docs/design/mockups/profile.html` row shape, version `0.20.0`.
  The time-bar release becomes `0.21.0` and so on.

## Verification

- Tests: every trait has a line, a hover and tier marks; `{hits} of {n}` is a whole number; the new
  Range, Lead and Brink at their edges; Guard shows two figures; a saved entry without the new keys still
  builds; the tips' rects cover the rows (PyQt); names and captions stay unique.
- On a copy of the real data in a temp APPDATA: 4, 37%, 1.2 per 100, 681 of 1,209 as above; compare
  title, second line and crest before and after, and report every tier that changed.
- Captures in four looks and at a narrow width, and one with a hover open. The user sees them before
  the merge. Full suite with and without PyQt6.
- The impeccable finish review on the drawer.

## Also

Delete the empty file `x` I left by mistake in another session's temp folder
(`C:\Users\jkncg\AppData\Local\Temp\claude\97e57e3ebd1271de`).

## Changed while building

Lead leaves out groupmates who did no damage or healed more than that, scale 30% to 90% (35%, Rising from 51%). The row's line sits under the name, and the two ends alone under the bar. The words follow the design review.

## My calls (change any)

The new anchors (one character's data), the row lines and hovers, "the middle" for median, dropping the
"next tier" line from the row, no installer build or merge until you say so.
