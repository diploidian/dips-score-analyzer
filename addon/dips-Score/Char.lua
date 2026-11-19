-- dips-Score: the character snapshot - what the game knows about you, saved at dipsScoreLog.char
-- for the analyzer (spells and their base cooldowns, gear, talent points).
--
-- This client mixes API generations and not every call is known to work, so each one is looked for
-- first and run under pcall; a part that can't be read stays empty and the rest still saves.
-- Lists are flat strings, like the log lines (see Log.lua); only the name comes last, since it is the
-- one field that can hold a comma.
--
--   spells  = {"spellID,cooldownMs,harm,name", ...}   cooldownMs "" = unknown, 0 = none; harm 1/0/""
--   gear    = {"slot,itemID,itemLevel", ...}          inventory slots 1-19 that hold something
--   talents = {"tab,tabName,points", ...}
local ADDON, ns = ...
local IsSecret, Field = ns.IsSecret, ns.Field

local LAST_SLOT = 19
local SETTLE = 3 -- seconds after entering the world: spell and item data may not be loaded on the first frame

local found = {walk = "none", cooldowns = false, harm = false} -- what the last snapshot could read

-- Calls fn; returns its first result, or nil when it is missing, fails or gives a hidden value.
local function Try(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, v = pcall(fn, ...)
    if not ok or IsSecret(v) then return nil end
    return v
end

local function SpellName(id)
    local name = Try(C_Spell and C_Spell.GetSpellName, id)
    if type(name) ~= "string" then
        local info = Try(GetSpellInfo, id) -- a name on older clients, a table on newer ones
        name = type(info) == "table" and info.name or info
    end
    return type(name) == "string" and name or nil
end

-- "1" / "0", or "" when no call could say.
local function Harmful(id)
    for _, fn in ipairs({IsHarmfulSpell or false, C_Spell and C_Spell.IsSpellHarmful or false}) do
        if fn then
            local ok, v = pcall(fn, id)
            if ok and not IsSecret(v) then return v and "1" or "0" end
        end
    end
    return ""
end

-- One spell as a flat string, or nil when it has no name.
local function SpellLine(id)
    local name = SpellName(id)
    if not name then return nil end
    local cd = Try(GetSpellBaseCooldown, id)
    if type(cd) ~= "number" then cd = nil else found.cooldowns = true end
    local harm = Harmful(id)
    if harm ~= "" then found.harm = true end
    return Field(id) .. "," .. Field(cd) .. "," .. harm .. "," .. Field(name)
end

-- Each walk calls add(spellID) for every learned, non-passive spell; it returns false if the API is missing.
local function WalkRetail(add)
    local B = C_SpellBook
    if not (B and B.GetNumSpellBookSkillLines and B.GetSpellBookSkillLineInfo and B.GetSpellBookItemInfo
        and Enum and Enum.SpellBookSpellBank) then return false end
    local lines = Try(B.GetNumSpellBookSkillLines)
    if type(lines) ~= "number" then return false end
    local learned = Enum.SpellBookItemType and Enum.SpellBookItemType.Spell
    for l = 1, lines do
        local line = Try(B.GetSpellBookSkillLineInfo, l)
        if type(line) == "table" and not line.offSpecID then
            local from = line.itemIndexOffset or 0
            for i = from + 1, from + (line.numSpellBookItems or 0) do
                local item = Try(B.GetSpellBookItemInfo, i, Enum.SpellBookSpellBank.Player)
                -- the book also lists spells you get later; itemType tells them apart
                if type(item) == "table" and item.spellID and not item.isPassive
                    and (not learned or item.itemType == learned) then
                    add(item.spellID)
                end
            end
        end
    end
    return true
end

local function WalkClassic(add)
    if not (GetNumSpellTabs and GetSpellTabInfo and GetSpellBookItemInfo) then return false end
    local tabs = Try(GetNumSpellTabs)
    if type(tabs) ~= "number" then return false end
    for t = 1, tabs do
        local ok, _, _, offset, count = pcall(GetSpellTabInfo, t)
        if ok and type(offset) == "number" and type(count) == "number" then
            for i = offset + 1, offset + count do
                local ok2, kind, id = pcall(GetSpellBookItemInfo, i, "spell")
                if ok2 and type(kind) == "table" then kind, id = kind.itemType, kind.spellID end
                if ok2 and kind == "SPELL" and type(id) == "number" and not IsSecret(id)
                    and not Try(IsPassiveSpell, i, "spell") then
                    add(id)
                end
            end
        end
    end
    return true
end

local function Spells()
    local out, seen = {}, {}
    local function add(id)
        if seen[id] then return end -- the same spell can sit in two tabs
        seen[id] = true
        out[#out + 1] = SpellLine(id)
    end
    found.cooldowns, found.harm = false, false
    found.walk = "retail"
    if not WalkRetail(add) or #out == 0 then
        found.walk = "classic"
        if not WalkClassic(add) or #out == 0 then found.walk = "none" end
    end
    return out
end

-- The item level is the fourth return of GetItemInfo.
local function FourthOf(fn, item)
    if type(fn) ~= "function" then return nil end
    local ok, _, _, _, level = pcall(fn, item)
    return ok and level or nil
end

-- Item level from whichever call works; nil when none does.
local function ItemLevel(link, id)
    local item = link or id
    local level = Try(C_Item and C_Item.GetDetailedItemLevelInfo, item)
        or FourthOf(C_Item and C_Item.GetItemInfo, item) or FourthOf(GetItemInfo, item)
    return type(level) == "number" and not IsSecret(level) and level or nil
end

local function Gear()
    local out = {}
    for slot = 1, LAST_SLOT do
        local id = Try(GetInventoryItemID, "player", slot)
        if type(id) == "number" then
            local link = Try(GetInventoryItemLink, "player", slot)
            out[#out + 1] = slot .. "," .. id .. "," .. Field(ItemLevel(type(link) == "string" and link or nil, id))
        end
    end
    return out
end

-- The tab name is the first text return that is not a texture path (the order differs by client).
local function TabName(tab)
    local ok, a, b, c = pcall(GetTalentTabInfo, tab)
    if not ok then return "" end
    for _, v in ipairs({a, b, c}) do
        if type(v) == "string" and not IsSecret(v) and not v:find("[\\/]") then return v end
    end
    return ""
end

local function Talents()
    local out = {}
    local tabs = Try(GetNumTalentTabs)
    if type(tabs) ~= "number" then return out end
    for tab = 1, tabs do
        local points = 0
        for i = 1, Try(GetNumTalents, tab) or 0 do
            local ok, _, _, _, _, rank = pcall(GetTalentInfo, tab, i)
            if ok and type(rank) == "number" and not IsSecret(rank) then points = points + rank end
        end
        out[#out + 1] = tab .. "," .. Field(TabName(tab)) .. "," .. points
    end
    return out
end

-- Builds the snapshot and stores it in the saved log (ClearLog leaves it alone).
-- Returns what was stored and what this call actually read (they differ when a list was kept).
function ns.Snapshot()
    local log = ns.Log()
    if not log then return end
    local class = select(2, UnitClass("player"))
    local read = {
        guid = Try(UnitGUID, "player"), name = UnitName("player"), realm = GetRealmName(), class = class,
        race = UnitRace("player"), level = Try(UnitLevel, "player"), taken = time(), -- race: the display name
        spells = Spells(), gear = Gear(), talents = Talents(),
    }
    local stored, before = {}, log.char or {}
    for k, v in pairs(read) do stored[k] = v end
    -- at logout these calls may stop answering: an empty read must not wipe a good earlier one
    for _, key in ipairs({"spells", "gear", "talents"}) do
        if #stored[key] == 0 and type(before[key]) == "table" and #before[key] > 0 then
            stored[key] = before[key]
        end
    end
    log.char = stored
    return stored, read
end

-- /dscore char: take one and say what this client gave.
function ns.PrintSnapshot()
    local _, c = ns.Snapshot() -- what this call read, not what was kept
    if not c then return ns.Print("not loaded yet.") end
    local withCd = 0
    for _, s in ipairs(c.spells) do
        local cd = tonumber(s:match("^[^,]*,([^,]*)"))
        if cd and cd > 0 then withCd = withCd + 1 end
    end
    local tabs = {}
    for _, t in ipairs(c.talents) do
        local n, label, points = t:match("^([^,]*),([^,]*),([^,]*)$")
        tabs[#tabs + 1] = (label ~= "" and label or "tab " .. n) .. " " .. points
    end
    ns.Print(string.format("level %s %s %s.", tostring(c.level), tostring(c.race), tostring(c.class)))
    ns.Print(string.format("%d spells, %d with a cooldown (spellbook walk: %s; base cooldowns %s; harm flag %s).",
        #c.spells, withCd, found.walk, found.cooldowns and "available" or "missing",
        found.harm and "available" or "missing"))
    ns.Print(string.format("%d gear slots filled. Talents: %s.", #c.gear,
        #tabs > 0 and table.concat(tabs, ", ") or "none read"))
end

----------------------------------------------------------------------
-- Events
----------------------------------------------------------------------
local E = CreateFrame("Frame")
E:RegisterEvent("PLAYER_ENTERING_WORLD")
E:RegisterEvent("PLAYER_LOGOUT") -- also fires on /reload, right before the save
E:SetScript("OnEvent", function(_, event)
    if event == "PLAYER_ENTERING_WORLD" and C_Timer and C_Timer.After then
        C_Timer.After(SETTLE, function() pcall(ns.Snapshot) end)
    else
        pcall(ns.Snapshot)
    end
end)
