-- projectArthas: runs - when recording starts and stops.
--
-- A run starts when you enter an instance of a kind turned on in the settings (dungeons by
-- default) and ends when you leave it. A /reload inside keeps the run going in a new segment
-- (the reload saved the old one). /dscore start|stop does it by hand, anywhere.
local ADDON, ns = ...

local RESUME_WINDOW = 30 * 60 -- seconds: back in the same instance within this, same run

local run       -- the open run, or nil
local manual    -- started by hand (stays open until stopped by hand)

local function Where()
    local name, kind, difficulty, _, _, _, _, instanceID = GetInstanceInfo()
    if kind == nil or kind == "none" then kind = "world" end
    return name, kind, difficulty, instanceID
end

local function Wanted(kind)
    local r = ns.db.record
    return r[kind] == true
end

local function FindRun(id)
    for _, r in ipairs(ns.Log().runs) do
        if r.id == id then return r end
    end
end

-- Something that shows the state (the record button) listens here.
local listeners = {}
function ns.OnStateChanged(fn) listeners[#listeners + 1] = fn end
local function Changed()
    for _, fn in ipairs(listeners) do fn() end
end

local function OpenSegment()
    ns.OpenSegment(run)
    ns.TakeAnchor()
    if ns.OnSegmentOpened then ns.OnSegmentOpened() end
    Changed()
end

-- The analyzer needs WoWCombatLog.txt with the advanced block (health, power). Only ever turns on.
local toldLog, toldAdvanced -- once per session each
local function EnsureCombatLog()
    local turnedOn = false
    local get = C_CVar and C_CVar.GetCVar or GetCVar
    local set = C_CVar and C_CVar.SetCVar or SetCVar
    if get("advancedCombatLogging") ~= "1" then
        -- not confirmed this client lets an add-on set it: check that it stuck
        local ok = pcall(set, "advancedCombatLogging", "1")
        if ok and get("advancedCombatLogging") == "1" then
            turnedOn = true
        elseif not toldAdvanced then
            toldAdvanced = true
            ns.Print("turn on Advanced Combat Logging in the game's options (Network/System) - the analyzer needs it.")
        end
    end
    -- after the CVar, so the first lines written already carry health and power
    if LoggingCombat and not LoggingCombat() then
        LoggingCombat(true)
        turnedOn = true
    end
    if turnedOn and not toldLog then
        toldLog = true
        ns.Print("turned the combat log on for the analyzer.")
    end
end

local function StartRun(zone, kind, difficulty, instanceID)
    local started = time()
    run = {
        id = started .. "-" .. (UnitName("player") or "?"),
        char = ns.CharKey(),
        zone = zone, kind = kind, difficulty = difficulty, instanceID = instanceID,
        started = started,
        segments = {},
    }
    local log = ns.Log()
    log.runs[#log.runs + 1] = run
    log.active = run.id
    OpenSegment()
    if ns.db.combatLog then pcall(EnsureCombatLog) end
    if ns.db.announce and not ns.Quiet(kind) then ns.Print("recording " .. (zone or "?") .. ".") end
end

function ns.EndRun()
    if not run then return end
    ns.CloseSegment()
    run.ended = time()
    ns.Log().active = nil
    if ns.db.announce and not ns.Quiet(run.kind) then
        ns.Print("stopped recording " .. (run.zone or "?") .. ". /reload or log out to save it for the analyzer.")
    end
    run, manual = nil, nil
    Changed()
end

-- Called on every load screen and zone change.
function ns.UpdateRecording()
    if not ns.Log() then return end
    local zone, kind, difficulty, instanceID = Where()
    if manual then
        if run and not ns.IsRecording() then OpenSegment() end
        return
    end
    -- still in the run we were in?
    if run and run.instanceID == instanceID and run.kind == kind then
        if not ns.IsRecording() then OpenSegment() end
        return
    end
    if run then ns.EndRun() end
    -- stopped by hand here: stay stopped until you leave
    local log = ns.Log()
    if log.stoppedIn then
        if log.stoppedIn == instanceID then return end
        log.stoppedIn = nil
    end
    if not Wanted(kind) then return end
    -- after a /reload or relog: pick the saved run back up if it's the same place
    local saved = log.active and FindRun(log.active)
    if saved and saved.instanceID == instanceID and saved.kind == kind and not saved.ended
        and time() - (saved.lastSeen or saved.started) < RESUME_WINDOW then
        run = saved
        OpenSegment()
        return
    end
    if saved and not saved.ended then saved.ended = saved.lastSeen or saved.started end
    StartRun(zone, kind, difficulty, instanceID)
end

function ns.StartManual()
    if run then
        -- already recording: keep this run, it just won't end by itself now
        manual = true
        if not ns.IsRecording() then OpenSegment() end
        ns.Print("already recording " .. (run.zone or "?") .. "; it now runs until /dscore stop.")
        return
    end
    manual = true
    ns.Log().stoppedIn = nil
    StartRun(Where())
end

function ns.StopManual()
    if not run then return end
    -- an automatic run stopped by hand: don't start another one until you leave this place
    if not manual and run.kind ~= "world" then ns.Log().stoppedIn = run.instanceID end
    manual = nil
    ns.EndRun()
end

function ns.ToggleRecording()
    if run then ns.StopManual() else ns.StartManual() end
end

function ns.IsManual() return manual and true or false end

function ns.CurrentRun() return run end

-- Drops every saved run (the open one too) and starts fresh if this place records.
function ns.ClearRuns()
    run, manual = nil, nil
    ns.ClearLog()
    ns.Log().stoppedIn = nil
    ns.UpdateRecording()
    ns.Print("saved runs cleared.")
end

----------------------------------------------------------------------
-- Events
----------------------------------------------------------------------
local loginDone -- the log is turned on once per load, so /combatlog off by hand sticks
local E = CreateFrame("Frame")
E:RegisterEvent("PLAYER_ENTERING_WORLD")
E:RegisterEvent("ZONE_CHANGED_NEW_AREA")
E:RegisterEvent("PLAYER_LOGOUT")
E:SetScript("OnEvent", function(_, event)
    if event == "PLAYER_LOGOUT" then
        -- the save happens right after this: note when we were last here, for resuming
        if run then run.lastSeen = time() end
        return
    end
    if event == "PLAYER_ENTERING_WORLD" and not loginDone and ns.db then
        loginDone = true
        if ns.db.combatLog then pcall(EnsureCombatLog) end
    end
    ns.UpdateRecording()
end)
