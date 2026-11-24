-- projectArthas: the creature type of each enemy you meet, by name, saved at dipsScoreDB.types (account-wide)
-- so the analyzer can tell whether a spell that only works on some types (Exorcism: undead and demons)
-- had anything to work on. types = {["Risen Ghoul"] = "Undead", ...}, plain strings, at most MAX names.
--
-- Calls are looked for first and run under pcall, as in Char.lua; a hidden or missing value is skipped.
local ADDON, ns = ...
local IsSecret = ns.IsSecret

local MAX = 2000 -- past this, names already known still update; new ones are not added

local count -- names in dipsScoreDB.types, counted once on the first write

local function Try(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, v = pcall(fn, ...)
    if not ok or IsSecret(v) then return nil end
    return v
end

local function Note(unit)
    if not (ns.db and type(unit) == "string") then return end -- before ADDON_LOADED there is nowhere to save
    if not Try(UnitExists, unit) or Try(UnitIsPlayer, unit) or not Try(UnitCanAttack, "player", unit) then return end
    local name, kind = Try(UnitName, unit), Try(UnitCreatureType, unit)
    if type(name) ~= "string" or name == "" or type(kind) ~= "string" or kind == ""
        or kind == "Not specified" then return end
    local types = ns.db.types
    if type(types) ~= "table" then types = {}; ns.db.types = types end
    if types[name] == kind then return end
    if types[name] == nil then
        if not count then
            count = 0
            for _ in pairs(types) do count = count + 1 end
        end
        if count >= MAX then return end
        count = count + 1
    end
    types[name] = kind
end

local UNITS = {PLAYER_TARGET_CHANGED = "target", UPDATE_MOUSEOVER_UNIT = "mouseover"}

local E = CreateFrame("Frame")
for _, event in ipairs({"PLAYER_TARGET_CHANGED", "UPDATE_MOUSEOVER_UNIT", "NAME_PLATE_UNIT_ADDED"}) do
    pcall(E.RegisterEvent, E, event) -- some don't exist on every client
end
E:SetScript("OnEvent", function(_, event, unit)
    pcall(Note, UNITS[event] or unit) -- NAME_PLATE_UNIT_ADDED hands over its own token ("nameplate3")
end)
