/subagent-driven-development
Project: F:\8. CLAUDE\Projects\WoW\dipAnalyzer
Brief: docs/superpowers/plans/2026-11-23-player-profile.md (on branch `dot-oribital/profile`)
Spec: the brief's "Design decisions" section, and `DESIGN.md`. Both binding.
Setup: Repo ready. Work on branch `dot-oribital/profile` (cut from `projectArthas`), in its own worktree.
Rulings:
- PyQt6 on the existing kit. No React, no web view, no new dependencies.
- The label and the plate are worked out by fixed rules, never by AI.
- No `role` field is saved per fight; role comes from `healing_role`, then the fight's `spec`.
- Share bars use `tx2` and carry no 90 tick; only scored measures use a measure ink.
- The page shows the last 15 days only; there is no all-time view. Finished 15-day slices are
  saved and never rewritten.
- No chat is ever recorded by the add-on.
- Never propose merging `projectArthas` into `main`.

Each implementer loads the skills its task names.
Paste the brief's Global Constraints, the hard rules below, and the Rulings into every implementer's Context.

Hard rules:
- Python 3.13+, PyQt6 >= 6.6, unittest. Data module and view-model import no PyQt.
- Animation is Qt only, reusing the Debrief's entrance and its `settings["motion"]` switch.
- Stop at the two gates: the user approves the mock-up before the page is built (task 1), and the
  user runs `/dscore probe` in game before any phase 2 recording is built (task 8).
- This PC has no Lua interpreter and no PyQt6 in Python 3.14: add-on Lua is checked by reading and
  in game; offscreen captures use a scratch `pip --target` PyQt6 with `scripts/shoot.py`.
- Bump the version in `pyproject.toml` before each installer build; every build bundles the add-on.
- Run the impeccable finish and motion reviews before calling a UI task done.

Done when: the tests pass, the Profile page matches the approved mock-up in all four looks with no
open material review finding, and (phase 2) the page shows the time budget from a real play session.
