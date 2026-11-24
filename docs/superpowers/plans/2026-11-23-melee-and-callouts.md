# Melee, auto-attack and effective call-outs

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Each implementer gets one task.

## Context

dips score grew up around spell casts. The user's review of the Profile page showed two gaps:

1. **Melee is under-counted.** Melee (auto attack) is 46% of the developer's damage, yet most pages treat a
   swing as a non-event: idle time and efficiency leave swing damage out, the hit table (misses, dodges, parries,
   glancing blows) is parsed but never used, extra attacks (Windfury, Sword Specialization, Hand of Justice) are
   not read, next-swing abilities (Heroic Strike, Cleave, Raptor Strike, Maul) are not modelled, off-hand swings
   are merged with main-hand, and a hunter's Auto Shot has no lost-shot measure at all.
2. **Call-outs name spells that could not have been used.** "You know Exorcism and have never cast it" is
   useless when no undead or demon was ever in range. Every call-out about an ability (never cast, sat ready,
   missed casts) must count real chances: "used 0 of 37 chances: 37 undead and demons in 12 fights".

The user asked for both to be done app-wide, for every class, in this session, on branch
`dot-oribital/angry-lehmann-4a1ef8` (with the Profile work).

## Global Constraints

- Python 3.13+, PyQt6 >= 6.6, unittest; no new dependencies. View-models import no PyQt.
- Colours only through `theme.tok()` / `theme.grade_color()`; DESIGN.md binds every page change.
- Never invent a number: unknown stays None and shows "–" with one line saying why.
- Old saved fights and cached analyses must still load (missing keys -> None). `replay` refills fights.
- The add-on is checked by reading only on this PC; anything needing the game is listed for the user.
- Tests: `python -m unittest discover -s tests`. Commit per task; never push.
- Never propose merging `projectArthas` into `main`.

## Tasks

### M1. Read everything the log says about melee and ranged auto attacks
- `sources/combatlog.py`: for `SWING_DAMAGE` / `RANGE_DAMAGE` read resisted, blocked, glancing and crushing;
  for `*_MISSED` keep the miss type (MISS, DODGE, PARRY, BLOCK, ...) and amount; parse `SPELL_EXTRA_ATTACKS`
  (count of extra swings and the spell that gave them).
- `live/summary.py` `auto` block and `scoring/metrics.py` `Metrics`: per fight / run, swings landed, crits,
  glancing, and misses by type; extra attacks by source; ranged shots (Auto Shot, Shoot) with the same hit
  table. Plain counts, saved with the fight.
- Off-hand: split main-hand and off-hand only where the log tells them apart (an `isOffHand` field if this
  client writes one); otherwise keep one stream and say so in a code comment. No timing heuristics.
- Tests with sample log lines for each event shape.

### C1. Call-outs count real chances (all abilities, all pages)
- New `scoring/usable.py`: one table of when an ability can be used, matched by spell name:
  - target type: Exorcism, Holy Wrath (Undead, Demon); Turn Undead, Shackle Undead (Undead);
    Hibernate (Beast, Dragonkin); Banish (Demon, Elemental); Polymorph (Beast, Humanoid, Critter);
  - target health: Execute, Hammer of Wrath (target under 20%);
  - reactive: Overpower (after the target dodged you), Revenge (after you blocked, dodged or parried),
    Riposte, Counterattack (after you parried).
  The table is data, easy to extend; unknown spells are always usable.
- Chances come from data already in the fight: creature types (`dipsScoreDB.types`, read by
  `savedvars.load_types`), target health (the advanced log's foe health already collected in `summarize`),
  and the M1 hit table (dodges, parries, blocks).
- `live/readiness.py`: ready time while the condition does not hold is excused ("no valid target",
  "target above 20%", "no dodge to answer"), so "sat ready" and the lost-damage figures only count real chances.
  The same for the run analysis path (`scoring/cooldowns.py` and wherever runs compute ready time).
- Every ability call-out says its chances: Habits "Spells you never use", the Profile plate, the Debrief and
  Fight "sat ready" rows, the Spells page fix: "used X of Y chances" with what a chance was. A restricted spell
  with no known chances is left out of "never cast" lists, never named.
- Tests per condition kind, plus a spell with no table entry.

### M2. Melee time is not idle time
- `live/summary.py` idle and `scoring/metrics.py` busy time: a gap between abilities while auto-attack keeps
  landing is "swinging, no ability", not idle; lost damage for it is the ability damage you could have added
  (as now), and the wording says so. Truly idle (no swings, no casts, free to act) stays idle.
- Next-swing abilities (Heroic Strike, Cleave, Raptor Strike, Maul): the swing they replace is not a lost swing.
- Hunters: Auto Shot / Shoot lost shots, measured like swings lost (gaps over 1.6 shot intervals while not
  moving and with a target), and a shot clipped by a cast counted separately.
- `scoring/score.py` Activity and the fight efficiency use these; existing tests updated, new ones per class
  shape (warrior with Heroic Strike, rogue, hunter, caster with wand).

### M3. Show it
- Spells page: Melee / Auto Shot rows show swings or shots, speed, and the hit table (landed, crit, glancing,
  miss, dodge, parry) instead of "–" casts.
- Fight page and Debrief "Where the damage went": a melee share line ("Melee 46% of your damage") beside the
  losses, and Swings lost / Shots lost rows for hunters.
- Habits: "Swings going missing" counts misses, dodges and parries separately from swings lost.
- Each change follows DESIGN.md; captures with `scripts/shoot.py` in all four looks.

## Order

M1, then C1 (needs M1's hit table), then M2, then M3. The Profile page (Profile plan task 5) follows the
user's approval of its mock-up and reads all of the above.

## Verification

- Full suite passes.
- `replay` on the sample log with `APPDATA` in a temp folder; a melee fight's Spells and Fight pages show the hit
  table and melee share; a fight against no undead never names Exorcism.
- In game (user): the add-on still loads after `/reload`.
