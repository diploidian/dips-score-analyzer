-- dips-Score: dips manager page and /dips score commands
local ADDON, ns = ...
local D = dips

local db
ns.OnLoad(function() db = ns.db end)

local function Status()
    local run = ns.CurrentRun()
    if run then
        local seg = ns.Segment()
        ns.Print(string.format("recording %s - segment %d, %d lines, %d anchors%s.", run.zone or "?",
            #run.segments, ns.LineCount(), seg and #seg.anchors or 0,
            ns.AnchorPending() and " (taking one now)" or ""))
    else
        ns.Print("not recording.")
    end
    ns.Print(string.format("%d saved runs (keeps %d).", #ns.Log().runs, db.maxRuns))
end

local function Mark(note)
    if not ns.IsRecording() then return ns.Print("not recording.") end
    ns.Write("X", note ~= "" and note or "mark")
    ns.Print("marked.")
end

D:RegisterModule({
    id = "score",
    addon = ADDON,
    name = "Score",
    description = "Records your key presses, clicks, movement and casts in dungeons for the dips-score analyzer.",
    db = function() return db end,
    slashHelp = "status, start, stop, mark [note], watch, button, clear",
    slash = function(arg)
        local cmd, rest = arg:match("^(%S*)%s*(.-)$")
        if cmd == "status" then
            Status()
        elseif cmd == "start" then
            ns.StartManual()
        elseif cmd == "stop" then
            ns.StopManual()
        elseif cmd == "mark" then
            Mark(rest)
        elseif cmd == "watch" then
            ns.ToggleWatch()
        elseif cmd == "button" then
            ns.SetButtonShown(not db.button.shown)
        elseif cmd == "clear" then
            ns.ClearRuns()
        else
            D:Open("score")
        end
    end,
    options = function()
        return {
            {type = "section", label = "Recording"},
            {type = "description", text = "A run starts when you enter one of these and ends when you leave. "
                .. "The game only writes it to disk on /reload or logout - that's when the analyzer can read it. "
                .. "Turn on the game's combat log too (/combatlog)."},
            {type = "toggle", key = "record.party", label = "Dungeons", onChange = ns.UpdateRecording},
            {type = "toggle", key = "record.raid", label = "Raids", onChange = ns.UpdateRecording},
            {type = "toggle", key = "record.scenario", label = "Scenarios and delves", onChange = ns.UpdateRecording},
            {type = "toggle", key = "record.world", label = "Everywhere else", onChange = ns.UpdateRecording},
            {type = "toggle", key = "announce", label = "Say in chat when a run starts and ends"},

            {type = "header", label = "Record button"},
            {type = "description", text = "Click it to start or stop recording, right-click it for more, drag it "
                .. "to move it. Stopping a dungeon run by hand keeps it stopped until you leave that dungeon."},
            {type = "toggle", key = "button.shown", label = "Show the record button",
                onChange = function() ns.SetButtonShown(db.button.shown) end},
            {type = "toggle", key = "button.locked", label = "Lock it in place"},
            {type = "button", label = "Reset its position", func = function() ns.ResetButtonPosition() end},

            {type = "header", label = "Storage"},
            {type = "range", key = "maxRuns", label = "Runs kept", min = 1, max = 50, step = 1, fmt = "%d",
                desc = "Older runs are dropped at the next load."},
            {type = "range", key = "maxLines", label = "Lines per segment", min = 10000, max = 200000, step = 10000,
                fmt = "%d", desc = "A safety cap. A busy 30-minute dungeon is roughly 15,000 lines."},
            {type = "button", label = "Clear saved runs", func = function() ns.ClearRuns() end},

            {type = "section", label = "Commands"},
            {type = "description", text = "/dips score status | start | stop | mark [note] | watch | button | clear\n"
                .. "watch prints each press with whether it was a key or a click - use it to check this client "
                .. "tells them apart."},
        }
    end,
})
