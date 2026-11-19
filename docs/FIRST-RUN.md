# First run: from installed to your first scorecard

You have installed the app and the dips-Score add-on. This page takes you from there to your first
scored run. Everything happens in the game or in the app, and it takes one dungeon.

## 1. Check the add-on in the game

1. At the character screen, click **AddOns** and make sure **dips-Score** is ticked. If it says
   "out of date", tick **Load out of date AddOns**.
2. Log in. If the combat log was off, chat says "turned the combat log on for the analyzer." (no
   line means it was already on). If chat tells you to turn on Advanced Combat Logging yourself,
   find it in the game's options under Network/System and tick it. Without it the app can't see
   health or mana.
3. Type `/dscore watch` in chat and use a few abilities, some with a key and some with the mouse.
   Each one should print "key" or "click". Type `/dscore watch` again to stop.
4. Type `/dscore char`. Every number it prints should be above zero.

## 2. Open the app and point it at the game

Open **dips score** from the Start menu (or, without the installer, double-click `dips-score.pyw` in the
app's folder).

The first time, if the app can't find the game, it asks for the game folder. Pick the
`_forever_` folder inside your World of Warcraft folder. Picking the World of Warcraft folder
itself works too. The app remembers your choice.

You can check or change the folder any time: click the cog (⚙) at the bottom left, next to Reload, and the
folders are at the top under **Game folders**: the game folder, and the combat log folder if yours isn't the
game's own `Logs`. A change takes effect right away; the line under them says how many combat logs and
dips-Score saved files it finds there.

With nothing recorded yet, the bottom of the window says "No runs yet". That's expected.

## 3. Leave the app open while you play

While the app is open, a card slides in over the game after each fight (the overlay). For it to
show, set the game's display mode to **borderless fullscreen** (Options > Graphics). Exclusive
fullscreen hides it.

To check the overlay, open the cog's settings and click **Show it** under "After each fight". The
same section sets how long the card stays and which side it appears on.

## 4. Run a dungeon

Enter a dungeon. Recording starts by itself, and the record button near the top of the screen
shows `REC` and a timer. Play normally. After each fight you get a line in chat and the overlay
card.

To record outside dungeons (raids, delves, the open world), type `/dscore` to open the add-on's
settings (or right-click the record button and choose **Settings**), and tick where recording
should start.

## 5. Save, then look

When you leave the dungeon, chat says "stopped recording ... /reload or log out to save it for the
analyzer." The game only writes the recording to disk then. Type `/reload`, log out, or
right-click the record button and choose **Save now (reload)**.

A second or two later, the new run appears in the app and opens by itself.

## 6. Check who you are

Open the run's **Group** tab and find yourself. Your role there decides which scorecard you get:
healer, tank or damage. It is usually right ("from the add-on" or "talents"). If it says
"guessed from spells" and is wrong, change it. The app remembers your pick.

That's it. The **Score** tab now shows your grade and what to work on.

## Optional: add your old fights

If you've played with the combat log on before, click the cog and then **Add fights from my old
combat logs**. Those fights then show on the **Fights** and **Habits** pages.

## If something's wrong

| What you see | What to do |
|---|---|
| Double-clicking `dips-score.pyw` does nothing | Python or PyQt6 isn't installed. Go back to [Setting it up](GUIDE.md#setting-it-up). |
| "Game folder not found" at the bottom of the window | Click the cog, then **Browse...** next to World of Warcraft under Game folders, and pick `_forever_`. |
| "No runs yet" after a dungeon | You haven't saved since the run. Type `/reload` in the game. `/dscore status` says how many runs are saved. |
| `/dscore` is an unknown command | The add-on isn't loaded. Check the AddOns list at the character screen (step 1). |
| A run says no combat log covers it | The combat log was off. In `/dscore` settings, leave "Turn on the combat log" ticked, or type `/combatlog` before the first pull. |
| A run says advanced logging was off | Turn on Advanced Combat Logging in the game's options (step 1). |
| No overlay after fights | Keep the app open while you play, and use borderless fullscreen (step 3). |
| Presses show as unknown, not key or click | They came from another add-on's action bars. The add-on watches the game's own bars. |

For what the scores mean, read the [guide](GUIDE.md).
