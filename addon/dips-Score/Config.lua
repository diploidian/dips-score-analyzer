-- projectArthas: records your inputs (action presses and their source, key holds, movement, casts)
-- in dungeons, as flat text lines the projectArthas app lines up with WoWCombatLog.txt.
-- Config: settings and loading.
local ADDON, ns = ...

ns.DEFAULTS = {
    record = {          -- where a run starts by itself
        party = true,     -- dungeons (and keystones)
        raid = false,
        scenario = false,
        world = false,    -- outside instances
    },
    maxRuns = 15,       -- oldest runs are dropped at load past this
    maxLines = 80000,   -- per segment (one load of the UI); past this a segment stops recording
    announce = true,    -- a chat line when a run starts and ends
    combatLog = true,   -- turn the game's combat log (and advanced logging) on at login and when a run starts
    fightLine = true,   -- a chat line after each fight: presses, clicks, refused casts
    dungeonsOnly = false, -- those two lines only in dungeons and raids
    button = {          -- the record button
        shown = true,
        locked = false,
        point = {"TOP", "TOP", 0, -120}, -- point, relPoint (on the screen), x, y
    },
}

-- Whether the chat lines stay away in a place of that kind (GetInstanceInfo's, "none" or "world" outside).
local INSIDE = {party = true, raid = true, scenario = true}
function ns.Quiet(kind)
    return ns.db.dungeonsOnly and not INSIDE[kind] or false
end

-- Files keep a local `db`; this hands it to them once the settings are loaded.
local loaders = {}
function ns.OnLoad(fn) loaders[#loaders + 1] = fn end

local E = CreateFrame("Frame")
E:RegisterEvent("ADDON_LOADED")
E:SetScript("OnEvent", function(self, event, name)
    if name ~= ADDON then return end
    self:UnregisterEvent("ADDON_LOADED")
    ns.db = ns.LoadSettings(ns.DEFAULTS)
    for _, fn in ipairs(loaders) do fn() end
end)
