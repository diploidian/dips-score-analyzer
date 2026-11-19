-- dips-Score: intent - what you pressed and when, and the game events around it.
--
-- Key or click? Every action button press runs UseAction, but UseAction doesn't say how it was
-- pressed. Our hooks run *after* the game's own code, and in this order within the same frame:
--     UseAction hook  ->  button OnClick hook  ->  ActionButtonDown/Up hook (key bindings)
-- So the press is written first with source "?", and the later hooks fill it in if they fire in
-- the same frame (same GetTime()). A key binding wins over a click.
-- Addon action bars (Bartender, Dominos, ...) still show up through UseAction, as "?".
local ADDON, ns = ...
local IsSecret = ns.IsSecret

local Write, Field = ns.Write, ns.Field
local GetTime = GetTime

local watching = false -- /dscore watch: print each press to chat

-- The fight in progress (REGEN_DISABLED to REGEN_ENABLED), counted whether or not a run records.
local fight

local function Count(n, one, many) return n .. " " .. (n == 1 and one or many) end

local function EndFight()
    local f = fight
    fight = nil
    local secs = f and math.floor(GetTime() - f.start + 0.5)
    if not secs or secs < 3 or not (ns.db and ns.db.fightLine) then return end
    local parts = {Count(f.presses, "press", "presses") .. " (" .. Count(f.clicks, "click", "clicks") .. ")"}
    if f.refused > 0 then parts[#parts + 1] = f.refused .. " refused" end
    if f.interrupted > 0 then parts[#parts + 1] = f.interrupted .. " interrupted" end
    ns.Print(secs .. " s - " .. table.concat(parts, ", "))
end

----------------------------------------------------------------------
-- Action presses
----------------------------------------------------------------------
local pressIndex, pressFrame, pressBase, pressSrc -- the last press: line index, GetTime(), text, source

local function MarkSource(src)
    if pressFrame ~= GetTime() then return end
    if pressSrc == "K" then return end -- a key binding already claimed it
    if fight then
        if src == "C" and pressSrc ~= "C" then fight.clicks = fight.clicks + 1 end
        if src == "K" and pressSrc == "C" then fight.clicks = fight.clicks - 1 end -- the key took it back
    end
    pressSrc = src
    if pressIndex then -- nil when not recording
        ns.Rewrite(pressIndex, pressBase .. src)
        if watching then ns.Print("  ^ " .. (src == "K" and "key" or "click")) end
    end
end

local function OnUseAction(slot)
    if fight then fight.presses = fight.presses + 1 end
    pressFrame, pressSrc, pressIndex = GetTime(), "?", nil
    if not ns.IsRecording() then return end
    local kind, id = GetActionInfo(slot)
    local index = Write("A", slot, kind, id, "?")
    if not index then return end
    -- the line minus its last field, to rewrite with the source
    local line = ns.Segment().lines[index]
    pressIndex, pressBase = index, line:sub(1, -2)
    if watching then
        ns.Print(string.format("press: slot %s, %s %s", Field(slot), Field(kind), Field(id)))
    end
end

-- Key bindings on the game's bars: ACTIONBUTTON1 -> ActionButtonDown(1),
-- MULTIACTIONBAR1BUTTON1 -> MultiActionButtonDown(bar, 1), and the matching Up on release.
local function OnKeyDown(bar, button)
    if ns.IsRecording() then Write("KD", bar, button) end
    MarkSource("K")
end

local function OnKeyUp(bar, button)
    if ns.IsRecording() then Write("KU", bar, button) end
    MarkSource("K") -- presses that fire on key up
end

-- A click on one of the game's action buttons. "Keybind" is what newer clients pass when a key
-- binding clicks the button; a real mouse button only counts while the pointer is over it.
local function OnButtonClick(self, button)
    if button == "Keybind" then
        MarkSource("K")
    elseif (button == "LeftButton" or button == "RightButton") and self:IsMouseOver() then
        MarkSource("C")
    end
end

local BUTTON_SETS = {
    "ActionButton", "MultiBarBottomLeftButton", "MultiBarBottomRightButton", "MultiBarRightButton",
    "MultiBarLeftButton", "MultiBar5Button", "MultiBar6Button", "MultiBar7Button",
}

local hooked = false
local function HookPresses()
    if hooked then return end
    hooked = true
    if UseAction then hooksecurefunc("UseAction", OnUseAction) end
    if ActionButtonDown then hooksecurefunc("ActionButtonDown", function(id) OnKeyDown(0, id) end) end
    if ActionButtonUp then hooksecurefunc("ActionButtonUp", function(id) OnKeyUp(0, id) end) end
    if MultiActionButtonDown then hooksecurefunc("MultiActionButtonDown", OnKeyDown) end
    if MultiActionButtonUp then hooksecurefunc("MultiActionButtonUp", OnKeyUp) end
    for _, prefix in ipairs(BUTTON_SETS) do
        for i = 1, 12 do
            local b = _G[prefix .. i]
            if b and b.HookScript then b:HookScript("OnClick", OnButtonClick) end
        end
    end
end

----------------------------------------------------------------------
-- Events
----------------------------------------------------------------------
local CAST_CODES = {
    UNIT_SPELLCAST_SENT = "CS",            -- unit, target, castGUID, spellID
    UNIT_SPELLCAST_START = "CB",           -- unit, castGUID, spellID
    UNIT_SPELLCAST_SUCCEEDED = "CK",
    UNIT_SPELLCAST_FAILED = "CF",
    UNIT_SPELLCAST_INTERRUPTED = "CI",
    UNIT_SPELLCAST_CHANNEL_START = "CC",
    UNIT_SPELLCAST_CHANNEL_STOP = "CE",
}

local E = CreateFrame("Frame")

local handlers = {
    PLAYER_STARTED_MOVING = function() Write("M", 1) end,
    PLAYER_STOPPED_MOVING = function() Write("M", 0) end,
    PLAYER_REGEN_DISABLED = function() Write("R", 1) end,
    PLAYER_REGEN_ENABLED = function()
        Write("R", 0)
        ns.TakeAnchor() -- out of combat: a fresh anchor to correct for clock drift
    end,
    PLAYER_TARGET_CHANGED = function() Write("T", UnitGUID("target") or "") end,
    PLAYER_DEAD = function() Write("D") end,
    ENCOUNTER_START = function(id) Write("E", 1, id) end,
    ENCOUNTER_END = function(id, _, _, _, success) Write("E", 0, id, success) end,
    CHALLENGE_MODE_START = function(mapID) Write("MP", 1, mapID) end,
    CHALLENGE_MODE_COMPLETED = function() Write("MP", 0) end,
    GROUP_ROSTER_UPDATE = function() ns.WriteRoster() end,
    PLAYER_ROLES_ASSIGNED = function() ns.WriteRoster() end,
}

----------------------------------------------------------------------
-- The group: a P line per member, written when a segment opens and whenever it changes (only
-- members whose line would differ from the last one written).
--   P,guid,name,class,role,race  name "First Surname" (GetUnitName(unit, true): on this server
--                              UnitName only gives the first name), class "PRIEST", role
--                              "TANK"/"HEALER"/"DAMAGER"/"NONE" (the group finder's assignment),
--                              race the non-localised token "NightElf" (empty if unknown)
----------------------------------------------------------------------
local rosterSeen = {}

local function RosterUnits()
    local units = {"player"}
    if IsInRaid and IsInRaid() then
        units = {}
        for i = 1, (GetNumGroupMembers and GetNumGroupMembers() or 0) do units[#units + 1] = "raid" .. i end
    else
        for i = 1, 4 do units[#units + 1] = "party" .. i end
    end
    return units
end

function ns.WriteRoster()
    if not ns.IsRecording() then return end
    for _, unit in ipairs(RosterUnits()) do
        local guid = UnitExists(unit) and UnitGUID(unit)
        if guid and not ns.IsSecret(guid) then
            local name = (GetUnitName and GetUnitName(unit, true)) or UnitName(unit)
            local _, class = UnitClass(unit)
            local role = UnitGroupRolesAssigned and UnitGroupRolesAssigned(unit) or "NONE"
            local _, race = UnitRace(unit)
            race = race or ""
            local line = Field(name) .. "|" .. Field(class) .. "|" .. Field(role) .. "|" .. Field(race)
            if rosterSeen[guid] ~= line then
                rosterSeen[guid] = line
                Write("P", guid, name, class, role, race)
            end
        end
    end
end

E:SetScript("OnEvent", function(_, event, ...)
    if event == "PLAYER_LOGIN" then return HookPresses() end
    -- the fight line counts whether or not a run records
    if event == "PLAYER_REGEN_DISABLED" then
        fight = {start = GetTime(), presses = 0, clicks = 0, refused = 0, interrupted = 0}
    elseif event == "PLAYER_REGEN_ENABLED" then
        EndFight()
    elseif fight and event == "UNIT_SPELLCAST_FAILED" then
        fight.refused = fight.refused + 1
    elseif fight and event == "UNIT_SPELLCAST_INTERRUPTED" then
        fight.interrupted = fight.interrupted + 1
    end
    if not ns.IsRecording() then return end
    local code = CAST_CODES[event]
    if code then
        local spellID
        if event == "UNIT_SPELLCAST_SENT" then
            spellID = select(4, ...)
        else
            spellID = select(3, ...)
        end
        return Write(code, spellID)
    end
    local fn = handlers[event]
    if fn then fn(...) end
end)

E:RegisterEvent("PLAYER_LOGIN")
for event in pairs(handlers) do pcall(E.RegisterEvent, E, event) end -- some don't exist on every client
for event in pairs(CAST_CODES) do pcall(E.RegisterUnitEvent, E, event, "player") end

-- A new segment starts with where things stand, so it reads right on its own.
function ns.OnSegmentOpened()
    Write("X", "segment")
    if InCombatLockdown() or UnitAffectingCombat("player") then Write("R", 1) end
    if IsPlayerMoving and IsPlayerMoving() then Write("M", 1) end
    local guid = UnitGUID("target")
    if guid then Write("T", guid) end
    wipe(rosterSeen) -- a new segment lists the whole group again
    ns.WriteRoster()
end

----------------------------------------------------------------------
-- /dscore watch
----------------------------------------------------------------------
function ns.ToggleWatch()
    watching = not watching
    ns.Print("watch " .. (watching and "on: each press prints with how it was pressed." or "off."))
    if watching and not ns.IsRecording() then
        ns.Print("not recording right now - /dscore start to record here.")
    end
end
