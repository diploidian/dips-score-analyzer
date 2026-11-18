Game art for the Azeroth theme (optional)
=========================================

Put files extracted from your WoW install anywhere in this folder (sub-folders are fine). The app finds
them by name when it starts, or when you press "Look again" in Settings. Without them the Azeroth theme
draws a look-alike instead.

These are Blizzard's files: they're for use on your own computer only. Don't share them, and keep this
folder out of any public repository.

How to get them
---------------
Use wow.export (free, open source: https://github.com/Kruithne/wow.export). Point it at
  D:\Program Files (x86)\World of Warcraft
pick the _forever_ product, then export (PNG is fine; .blp works too) into this folder:

  What                     Where it is in the game files                       Used for
  ----                     -----------------------------                       --------
  fonts\FRIZQT__.TTF       fonts/frizqt__.ttf                                  titles, names, everything
  classicon_*              interface/icons/classicon_warrior ... _druid        class icons next to names
  ui-raidtargetingicon_1-8 interface/targetingframe/                           marker icons on pulls
  ui-dialogbox-border      interface/dialogframe/                              the frame around the tabs
  ui-tooltip-border        interface/tooltips/                                 the frame around tooltips

Spell icons (optional, bigger)
------------------------------
1. Export the whole interface/icons folder (it's large).
2. In wow.export's "Data Tables" tab, export SpellMisc as CSV into this folder.
3. Put a listfile here too (wow.export can export its listfile; it's "fileDataID;path" per line, named
   anything with "listfile" in it, .csv or .txt).
The app then knows which icon each spell uses and shows it in the Spells tab and on the timeline.
