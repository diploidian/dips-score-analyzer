-- dips-Score: records your inputs (action presses and their source, key holds, movement, casts)
-- in dungeons, as flat text lines the dips-score analyzer lines up with WoWCombatLog.txt.
-- Config: settings and loading.
local ADDON, ns = ...
local D = dips

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
    button = {          -- the record button
        shown = true,
        locked = false,
        point = {"TOP", "TOP", 0, -120}, -- point, relPoint (on the screen), x, y
    },
}

-- Files keep a local `db`; this hands it to them once the settings are loaded.
local loaders = {}
function ns.OnLoad(fn) loaders[#loaders + 1] = fn end

function ns.Print(msg) D:Print("score: " .. msg) end

local E = CreateFrame("Frame")
E:RegisterEvent("ADDON_LOADED")
E:SetScript("OnEvent", function(self, event, name)
    if name ~= ADDON then return end
    self:UnregisterEvent("ADDON_LOADED")
    ns.db = D:LoadProfile(ADDON, "dipsScoreDB", ns.DEFAULTS)
    for _, fn in ipairs(loaders) do fn() end
end)
