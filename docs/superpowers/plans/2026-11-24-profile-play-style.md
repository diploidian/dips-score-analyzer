# Profile, second pass: how your character plays

## Context

The Profile page is live and the user's rulings on it are:
- **Crest:** option B, a gold double-ruled crest, above the big figure and the plate.
- **Input stays, quietly:** keys, clicks and presses are the player's hands, not the character's play.
  They stay on the page but are almost never highlighted, only when something is badly wrong.
- **"Cut short by moving" stays.** It is play, not input.
- **Traits and titles:** liked; the user asked for more of both.
- **Plate:** "Nothing stands out / 99% keys" was wrong at 80% of possible damage. Its rework is
  paused half done, uncommitted and untested, in this worktree.

Base: `dot-oribital/angry-lehmann-4a1ef8` at `6e4db66` (0.17.0). Dungeon runs keep their Input score.

**What the data says** (read-only, and why anchors are set on replayed data): the saved file has 453
fights, nearly all summed up by older versions. A full replay of the logs gives 1,102 fights (the app
was not running for the rest). Same character: 76% -> 85% of fights won, 36 -> 25 s between fights,
deaths 5.5 -> 3.4 per 100 fights, top zone Stranglethorn Vale -> Arathi Highlands.

## 1. Input, demoted

- **Hands** becomes a closed drawer at the foot of the left column, "Hands (3)": keys or clicks,
  presses per minute, refused presses. No chips, no ring, no colour, never in the crest, the hero
  figure, the title or a fallback. `profile_runs.json` keeps its fields.
- **On the plate only when badly wrong:** clicks 60% or more of known presses, or 40% or more of
  presses refused, with 500 presses or more. Even then it comes after dying, and it is not shown two
  15-day windows running unless it got worse.
- **Cut short by moving** moves into How you fight, keeping its chip.

## 2. Traits: 34, in seven families

New pure module `src/dips_score/live/traits.py`, one table. Each trait has a figure, a low and high
anchor (score 0 to 1), a minimum sample, the roles it applies to, and three epithets (score 0.35, 0.6,
0.85). Unknown data gives no score. Figures come from saved fights; a trait whose data turns out not
to support it is cut and listed in the report, never faked.

**Pace**

| Trait | Figure | Anchors | Epithets |
|---|---|---|---|
| Tempo | median s between fights in a sitting | 120 -> 15 | Steady, Tireless, Relentless |
| Swift | share of wins under 15 s | 10 -> 45% | Quick, Swift, Lightning |
| Endure | median fight length | 45 -> 120 s | Patient, Enduring, Everlasting |
| Marathon | longest sitting, fights | 40 -> 200 | Dogged, Unresting, Unwearied |
| Streak | longest run without a death | 15 -> 120 | Surviving, Unfallen, Deathless |

**Nerve**

| Trait | Figure | Anchors | Epithets |
|---|---|---|---|
| Edge | wins after dropping under 35% health | 5 -> 25% | Daring, Fearless, Unyielding |
| Brink | wins under 10% health, count | 2 -> 15 | Lucky, Defiant, Death-Cheating |
| Guard | deaths per 100 fights and average lowest health, the weaker | 8 -> 0, 50 -> 85% | Guarded, Unbroken, Untouchable |
| Wary | close calls answered with a defensive | 30 -> 90% | Wary, Cool-Headed, Unshaken |
| Crowd | wins against three or more | 8 -> 40% | Bold, Overrunning, Unstoppable |
| Duel | wins one on one | 70 -> 97% | Sure, Deadly, Peerless |

**Victory**

| Trait | Figure | Anchors | Epithets |
|---|---|---|---|
| Finish | fights won by the kill | 70 -> 97% | Proven, Victorious, Conquering |
| Hound | fights where nobody got away | 80 -> 99% | Dogging, Hunting, Inescapable |
| Boss | boss kills | 3 -> 25 | Giant-Felling, Throne-Toppling, Mountain-Breaking |
| War | player fights won, 10 or more fought | 35 -> 75% | Feared, Dreaded, Warlike |
| Scourge | one enemy name's share of kills | 8 -> 30% | Vengeful, Merciless, Exterminating |

**Weapon**

| Trait | Figure | Anchors | Epithets |
|---|---|---|---|
| Blade | melee auto share of damage | 30 -> 65% | Iron, Steel, Blade-Sworn |
| Shot | ranged auto share | 25 -> 60% | Keen, Far-Sighted, True-Shot |
| Craft | ability share | 60 -> 95% | Gifted, Fierce, Spellforged |
| Focus | top ability's share of ability damage | 35 -> 75% | Devoted, Single-Minded, Masterful |
| Range | abilities worth 5% or more | 3 -> 9 | Adaptable, Cunning, Many-Handed |
| Crit | hits that crit | 8 -> 30% | Fortunate, Savage, Fatebound |
| Proc | proc and item damage share | 8 -> 30% | Charged, Crackling, Storm-Touched |

**Craft of play**

| Trait | Figure | Anchors | Epithets |
|---|---|---|---|
| Edgewise | possible damage reached | 75 -> 95% | Honed, Precise, Flawless |
| Ready | cooldowns used of possible | 50 -> 90% | Prompt, Eager, Unsparing |
| Planted | casts not cut short by moving (recorded runs) | 97 -> 100% | Grounded, Unmoved, Rooted |
| Primed | fights pulled with your usual buffs up | 70 -> 98% | Ready-Armed, Blessed, Oathbound |
| Break | interrupts per 100 group fights | 5 -> 40 | Watchful, Silencing, Spellbreaking |

**Company**

| Trait | Figure | Anchors | Epithets |
|---|---|---|---|
| Lone | fights outside a group | 55 -> 97% | Wandering, Lone, Sovereign |
| Bond | fights in a group | 50 -> 97% | Loyal, Stalwart, Sworn |
| Lead | group fights topping the damage | 25 -> 70% | Rising, Leading, Commanding |
| Mercy | dispels per 100 fights, or a non-healer's group heal share | 3 -> 25, 10 -> 35% | Merciful, Guarding, Selfless |

**Road**

| Trait | Figure | Anchors | Epithets |
|---|---|---|---|
| Travel | zones with 5 fights or more | 5 -> 22 | Roaming, Far-Travelled, Worldly |
| Menagerie | different enemies beaten | 80 -> 500 | Curious, Seasoned, All-Seeing |

Role-only additions: **healer** Thrift (low overheal: Sparing, Measured, Unwasting), Lifeline (group
fights nobody died: Reassuring, Faithful, Saving); **tank** Wall (avoided hits: Braced, Immovable,
Impregnable), Anvil (damage taken per second while winning: Sturdy, Hardened, Adamant).

**Choosing:** highest score wins. One family cannot take both the epithet and the second trait, so two
players with the same best trait still differ. Role-only traits get first place on a tie.

## 3. Titles

**Standard:** `<epithet> <class noun> of <where>`.

**Class nouns**, by class and talent tree (spec), then role, then plain. Each tree has its own, so two
paladins differ:

| Class | Trees |
|---|---|
| Warrior | Arms Warblade, Fury Reaver, Protection Ironwall |
| Paladin | Holy Lightmender, Protection Shieldsworn, Retribution Crusader |
| Hunter | Beast Mastery Packwarden, Marksmanship Deadeye, Survival Trailstalker |
| Rogue | Assassination Nightblade, Combat Swashblade, Subtlety Veilwalker |
| Priest | Discipline Oathkeeper, Holy Dawnkeeper, Shadow Duskcaller |
| Shaman | Elemental Stormbinder, Enhancement Thunderfist, Restoration Tidemender |
| Mage | Arcane Spellweaver, Fire Emberwright, Frost Rimecaller |
| Warlock | Affliction Hexbinder, Demonology Pactkeeper, Destruction Cinderlord |
| Druid | Balance Starcaller, Feral Wildfang (tank: Thornhide), Restoration Grovekeeper |
| Unknown spec | the class's damage, healer or tank noun; no class: Slayer, Mender, Bulwark |
| Mixed roles | Champion |

**Where**, first that applies:
- *Bane*: one creature type is 40% of known foes: "Bane of the Undead", "of Beasts", "of Demons",
  "of Dragonkin", "of Elementals", "of Giants" (needs types for half of the foes).
- *Nemesis*: one enemy group's name is 15% of kills: "Scourge of the Syndicate" (shared first word of
  enemy names, 30 kills or more).
- *Zone*: 25% of fights: "of the Arathi Highlands" ("the" from a small list).
- *Place*: "of the Wilds", "of the Depths", "of the Great Halls", "of the Battlefield", "of the Long
  Road" (no place reaches 50% and Travel is tier 2).

**Named titles** replace the standard one when two traits are both tier 2 or better. Rarer, so worth
chasing. First match in this order:

| Traits | Title |
|---|---|
| Edge + Crowd | the Cornered Lion |
| Edge + Streak | the One Who Walks Away |
| Guard + Streak | the Unfelled |
| Brink + Lone | the Last One Standing |
| Lone + Tempo | the Lone Storm |
| Lone + Travel | the Long Walker |
| Tempo + Finish | the Reaping Wind |
| Swift + Crit | the Sudden End |
| Blade + Endure | the Grinding Wheel |
| Blade + Duel | the First Blade |
| Crowd + Proc | the Gathering Thunder |
| Hound + Scourge | the Old Grudge |
| Boss + Lead | the Crownbreaker |
| War + Edge | the Nerveless |
| War + Duel | the Arena's Answer |
| Focus + Edgewise | the Perfectionist |
| Range + Ready | the Full Quiver |
| Travel + Menagerie | the Walking Atlas |
| Bond + Mercy | the Open Hand |
| Break + Wary | the Cold Eye |
| Lifeline + Thrift (healer) | the Quiet Miracle |
| Lifeline + Bond (healer) | the Reason They Lived |
| Wall + Anvil (tank) | the Door That Holds |
| Crowd + Wall (tank) | the Breakwater |

Reads "the Lone Storm, Crusader of the Arathi Highlands", so class and place always show.

**Second line:** the next two traits in plain words ("Fights without pause, wins on the edge").
**Deeds line:** up to two single feats from the window, best first, each with its enemy where known:
closest win ("won with 2% health left against Bloodscalp Berserker"), biggest pull beaten ("seven at
once"), longest streak ("97 fights without falling"), boss kills, best fight's damage per second,
player kills, levels gained, longest sitting.

**On the developer's data:** saved fights as they are: Tempo 0.80, Streak 0.66, Edge 0.52, Blade 0.46,
Travel 0.41 -> **Tireless Crusader of Stranglethorn Vale**. After importing all logs: Tempo 0.90 ->
**Relentless Crusader of the Arathi Highlands**, second trait Streak (0.78). Spec is unknown in the
saved fights, so the class's damage noun applies.

**Over time:** slices save `title` and the trait scores; Earlier shows titles as a history. Before
shows its title when it differs. A tier reached for the first time since the last window gets the
page's one ring and a hand note ("new: Relentless").

## 4. Metrics that fit the player: How you fight

One card, five rows picked by main role (or PvP at 25% of fights), each row a trait's figure, so
title and card cannot disagree; the title's own row first. Rows without data give way to the next.
- **Damage:** time between fights, wins on the edge, pulls and wins against three or more, melee /
  ability split, possible damage reached, cut short by moving.
- **Healer:** overheal, group heal share, fights nobody died, dispels, cut short by moving.
- **Tank:** hits avoided, damage taken per second, usual pull, lowest health, interrupts.
- **PvP:** fights won, escapes, length, wins on the edge, deaths.
- **All traits drawer:** every scored trait by family, its figure, a bar of its score, its tier, and
  what the next tier needs ("Relentless at 31 s, you are at 36 s").

The **hero figure** becomes the title trait's figure and caption; role share stays in Role mix.
Temperament folds into this card and the plate, so nothing is said twice.

## 5. The plate

Finish the paused work: dying in 15% of fights; the ability with the most damage left unused, with
chances and the next two under it; close calls with a defensive ready (5 or more, spell named); never
cast with real chances; a healer's overheal of 40%; cooldowns under 50%; input when badly wrong. At 90%
of possible damage it says the window is clean. Healing and no-damage fights stay out, as in Habits.

**Swings lost stays out of the plate.** The earlier figure of about 127,900 was wrong: it came from
fights summed up by older versions. The same fights replayed give 39,486, and 27% to 52% of swing
losses fall in moving, no enemy, stuns or lulls. Excusing those app-wide changes scores, so it is a
separate decision.

**Outdated fights:** when fewer than half of the window's fights carry the current data, the page shows
one quiet line under the crest: "Based on older fight records. Import your combat logs in Settings
for the full picture."

## 6. The crest

Left column, above the figure and the plate. Double gold rule (2px and 1px, square; `gold` draws
rules only, never a fill, so the plate stays the one solid surface). Lines: race, class and level; the
title, about 74px Barlow Condensed 700, stepping to two lines, never elided; the second line; the
deeds. The page header keeps name, gear and window. No motion. Full accessible name. DESIGN.md gains
the crest and title style. Under 10 fights: no crest.

## Files

`live/traits.py` (new), `live/profile.py`, `live/profile_history.py`, `profile_view.py`,
`ui/profileview.py`, `ui/kit.py`, `DESIGN.md`, `docs/design/mockups/profile.html`, docs, tests. Reuse
`usable.py`, `habits.cooldown_losses` (paused edit), `talent_role`, `kit.BarRows`, `Plate`, `Drawer`.

## Steps

1. **Plate:** finish and test the paused edits; commit.
2. **Data:** traits, titles, deeds, packs, slices. Tests: every anchor edge and minimum sample, every
   noun, Where rule and named title reachable, family rule, ties, missing keys, 0.16 and 0.17 files.
3. **Mock-up, then page:** crest, card, drawers, Hands at the foot.
4. **Gate:** captures on a copy of the real data (as saved, and replayed), four looks, plus sample
   healer, tank, PvP and caster pages. The user sees them before any merge.
5. Task review, impeccable finish review, fixes, final review.
6. Docs, the next version after the one in `pyproject.toml`, merge into `projectArthas`, rebuild. No
   push unless asked.

## Verification

- Full suite without and with PyQt6.
- On a copy of the real data in a temp APPDATA, title, first card row and hero figure agree with a hand
  count; input appears only in its drawer.
- Five hand-made players give five different titles and the right pack; a sweep over generated players
  reports how often each epithet and named title comes up, so none is dead and none swallows the rest.

## My calls (change any)

Every name, anchor and order in the tables; the hero figure; folding Temperament; the input limits (60%
clicks, 40% refused); one ring for a new tier.
