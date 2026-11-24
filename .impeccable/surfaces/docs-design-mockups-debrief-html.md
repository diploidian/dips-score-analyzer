---
version: 1
slug: "docs-design-mockups-debrief-html"
primary_target: "docs/design/mockups/debrief.html"
related_targets: ["docs/design/mockups/fight-card.html","docs/design/mockups/history.html","docs/design/mockups/group.html"]
---

# Surface brief: projectArthas redesign mock-ups

Scope: four mock-up pages (run debrief, after-fight card, dungeon history, group) under docs/design/mockups/. Visitor mode: Operate (the fight card is a glance surface over the game).
Audience and job: a WoW player alt-tabbed or on a second monitor, a few seconds between runs; learn the one fix, then the grade and where the points went.
Proof and content: the real Blackfathom Deeps run (18 Nov 22:27, 75 B as DPS, 64 fights). Rotation, Pacing, older visits and other players' scores are illustrative and labelled.
Constraints: shipping app is PyQt6; mock-ups are static HTML/CSS with a little JS for the theme toggle and entrance motion.
Memorable moment: the fight grid where the four fights to review are circled by hand in highlighter, the route drawing itself in review order.
Approval record (user, this session): the user picked "Split Sheet, circled", then asked for Classical and Timeless in palette 1's sans serif with the ruled points breakdown and one colour per bar, then approved night modes. Approved sketches: .impeccable/mocks/palettes/p3b-timeless-sans.html, p2b-classical-sans.html, p3n-timeless-night.html, p2n-classical-night.html (comparison page .impeccable/mocks/palettes/index.html). The two smaller "next fix" rows inside the Fix plate were in the approved spec ("two smaller next cards") and in every approved sketch.
Unresolved: build path (PyQt redraw vs embedded web view), Rotation and Pacing scoring, default weights.

## Direction contract

THESIS: A post-run race sheet you read in three seconds: one giant result, one fix on the only solid plate, and a fight catalog where the review list is circled by hand. It refuses the equal-weight widget wall of analytics dashboards.

OWN-WORLD: Two themes, each day and night, all as tokens. Classical: soft ivory, burgundy plate, gold leaf, forest; night is warm near-black with lifted burgundy and hot-rose highlighter. Timeless: ivory with a dark walnut rail, olive plate, rust, teal; night is walnut-black with glowing amber highlighter. Barlow and Barlow Condensed throughout, Caveat only for the hand marks. Hairline-ruled modules with small boxed tracked-caps labels; one colour per measure; grade letters always shown.

STORY: The player sees 75 B and the verdict, reads the single fix and its price (−10.3 points, ~1,177 damage), scans four measures and the points breakdown, then looks at the four circled fights. They leave knowing what to press differently next run.

FIRST VIEWPORT: Left rail (Dungeons, Fights, Habits, recent runs). Main column: giant 75 with boxed B and verdict, the Fix this first plate beside it with its Show me button, then Effectiveness (four coloured bars, target at 90), then Where your 25 points went (ruled list, Earned 75 of 100). Right column: Fights · 64, an 8×8 numbered cell grid with the four worst circled and routed. Header holds the view tabs; the theme and day/night toggles sit in the rail's Look block (user confirmed 19 Nov: "Keep in rail"; it reads as an app setting; day/night defaults to Auto).

FORM: Split Sheet, circled: a grounded direction (Split Sheet, my roll-assigned #6) joined with the Circled Catalog challenger's fight-grid signature; 1st of the user's finalists. seed:5f159d94009501de

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
