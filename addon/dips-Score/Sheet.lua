-- projectArthas: the character sheet, read with the snapshot (Char.lua) and saved beside it in dipsScoreLog.char:
--
--   stats     = {"key,value", ...}                     value "?" when the game hides it; read out of combat only
--   items     = {"slot,itemID,quality,enchantID,name", ...}
--   itemstats = {"slot,KEY,value", ...}                the game's own stat keys (ITEM_MOD_STRENGTH_SHORT, ...)
--   ranks     = {"spellID,rank", ...}                  the rank text of every spell in the book that has one
--   points    = {"c,tree,node,rank,maxRank,name", ...} talents (c "talent") and Legacy (c "legacy") with points in them
--   trees     = {"c,tree,nodes,withPoints,left", ...}  left: points still to spend, "" when not known
--   skills    = {"level,max,name", ...}                professions
--
-- Every call is looked for first and run under pcall, as in Char.lua: a part that can't be read stays empty.
local ADDON, ns = ...
local IsSecret, Field = ns.IsSecret, ns.Field

local LEGACY_SYSTEM = 45
local LAST_SLOT = 19

-- Every result of a call, or an empty list when it is missing or fails.
local function Results(ok, ...) return ok and {...} or {} end -- a nil among them keeps the others' places

local function All(fn, ...)
    if type(fn) ~= "function" then return {} end
    return Results(pcall(fn, ...))
end

local function First(fn, ...) return All(fn, ...)[1] end

----------------------------------------------------------------------
-- Stats
----------------------------------------------------------------------
local function Stats()
    local out = {}
    if First(InCombatLockdown) then return out end -- some values are hidden in combat
    local function put(key, v)
        if IsSecret(v) then
            out[#out + 1] = key .. ",?"
        elseif type(v) == "number" then
            out[#out + 1] = key .. "," .. string.format("%.3f", v)
        end
    end
    local function sum(...) -- the numbers added up, or the first hidden one
        local total
        for i = 1, select("#", ...) do
            local v = select(i, ...)
            if IsSecret(v) then return v end
            if type(v) == "number" then total = (total or 0) + v end
        end
        return total
    end
    for i, key in ipairs({"str", "agi", "sta", "int", "spi"}) do put(key, All(UnitStat, "player", i)[2]) end
    local ap, rap = All(UnitAttackPower, "player"), All(UnitRangedAttackPower, "player")
    put("ap", sum(ap[1], ap[2], ap[3]))
    put("rap", sum(rap[1], rap[2], rap[3]))
    put("armor", All(UnitArmor, "player")[2])
    put("health", First(UnitHealthMax, "player"))
    put("mana", First(UnitPowerMax, "player", 0))
    for i, key in ipairs({"holy", "fire", "nature", "frost", "shadow", "arcane"}) do
        put("res_" .. key, All(UnitResistance, "player", i)[2])
    end
    put("crit", First(GetCritChance))
    put("rangedcrit", First(GetRangedCritChance))
    put("dodge", First(GetDodgeChance))
    put("parry", First(GetParryChance))
    put("block", First(GetBlockChance))
    put("hit", First(GetHitModifier))
    put("spellhit", First(GetSpellHitModifier))
    put("haste", First(GetHaste))
    put("healing", First(GetSpellBonusHealing))
    local best, crit
    for school = 2, 7 do
        local v, c = First(GetSpellBonusDamage, school), First(GetSpellCritChance, school)
        if IsSecret(v) then best = v break end
        if type(v) == "number" and (best == nil or v > best) then best = v end
        if not IsSecret(c) and type(c) == "number" and (crit == nil or c > crit) then crit = c end
    end
    put("spellpower", best)
    put("spellcrit", crit)
    local regen = All(GetManaRegen)
    put("regen", regen[1])
    put("regencombat", regen[2])
    local damage = All(UnitDamage, "player")
    put("dmgmin", damage[1])
    put("dmgmax", damage[2])
    put("dmgbonus", sum(damage[5], damage[6]))
    put("speed", First(UnitAttackSpeed, "player"))
    local move = All(GetUnitSpeed, "player")
    put("runspeed", move[2])
    return out
end

----------------------------------------------------------------------
-- Gear
----------------------------------------------------------------------
local function Items()
    local items, stats = {}, {}
    for slot = 1, LAST_SLOT do
        local id = First(GetInventoryItemID, "player", slot)
        local link = First(GetInventoryItemLink, "player", slot)
        if type(id) == "number" and not IsSecret(id) then
            local quality, enchant = First(GetInventoryItemQuality, "player", slot), ""
            local name = ""
            if type(link) == "string" and not IsSecret(link) then
                enchant = link:match("item:%d+:(%d*)") or ""
                name = link:match("%[(.-)%]") or ""
                local found = First(C_Item and C_Item.GetItemStats, link)
                if type(found) == "table" then
                    for key, v in pairs(found) do
                        if type(v) == "number" and not IsSecret(v) then
                            stats[#stats + 1] = slot .. "," .. Field(key) .. "," .. string.format("%.3f", v)
                        end
                    end
                end
            end
            items[#items + 1] = slot .. "," .. id .. "," .. Field(quality) .. "," .. enchant .. "," .. name
        end
    end
    return items, stats
end

----------------------------------------------------------------------
-- Spell ranks, talents, Legacy, professions
----------------------------------------------------------------------
local function Ranks(spells)
    local out = {}
    for _, line in ipairs(spells) do
        local id = tonumber(line:match("^(%d+)"))
        local rank = id and First(C_Spell and C_Spell.GetSpellSubtext, id)
        if type(rank) == "string" and not IsSecret(rank) and rank ~= "" then out[#out + 1] = id .. "," .. Field(rank) end
    end
    return out
end

local function NodeName(config, node)
    local entry = type(node.activeEntry) == "table" and node.activeEntry.entryID
        or type(node.entryIDs) == "table" and node.entryIDs[1]
    local e = entry and First(C_Traits.GetEntryInfo, config, entry)
    local d = type(e) == "table" and e.definitionID and First(C_Traits.GetDefinitionInfo, e.definitionID)
    if type(d) ~= "table" then return "" end
    local name = d.overrideName
    if type(name) ~= "string" or name == "" then
        name = d.spellID and First(C_Spell and C_Spell.GetSpellName, d.spellID)
    end
    return type(name) == "string" and not IsSecret(name) and name or ""
end

local function Trees(kind, config, points, trees)
    if type(config) ~= "number" or not C_Traits then return end
    local info = First(C_Traits.GetConfigInfo, config)
    if type(info) ~= "table" or type(info.treeIDs) ~= "table" then return end
    for _, tree in ipairs(info.treeIDs) do
        local nodes = First(C_Traits.GetTreeNodes, tree)
        local with = 0
        for _, id in ipairs(type(nodes) == "table" and nodes or {}) do
            local node = First(C_Traits.GetNodeInfo, config, id)
            local rank = type(node) == "table" and node.currentRank
            if type(rank) == "number" and not IsSecret(rank) and rank > 0 then
                with = with + 1
                points[#points + 1] = kind .. "," .. tree .. "," .. id .. "," .. rank .. ","
                    .. Field(node.totalMaxRanks or node.maxRanks) .. "," .. NodeName(config, node)
            end
        end
        local money = First(C_Traits.GetTreeCurrencyInfo, config, tree, true)
        local left = type(money) == "table" and type(money[1]) == "table" and money[1].quantity
        if type(nodes) == "table" and #nodes > 0 then
            trees[#trees + 1] = kind .. "," .. tree .. "," .. #nodes .. "," .. with .. "," .. (type(left) == "number" and left or "")
        end
    end
end

local function Skills()
    local out = {}
    local list = All(GetProfessions)
    for i = 1, 7 do
        if type(list[i]) == "number" then
            local p = All(GetProfessionInfo, list[i])
            if type(p[1]) == "string" and type(p[3]) == "number" and not IsSecret(p[1]) and not IsSecret(p[3]) then
                out[#out + 1] = p[3] .. "," .. Field(p[4]) .. "," .. p[1]
            end
        end
    end
    return out
end

-- Adds the sheet to the snapshot being built (Char.lua); a part that fails stays empty.
function ns.ReadSheet(read)
    read.stats, read.items, read.itemstats, read.ranks, read.points, read.trees, read.skills = {}, {}, {}, {}, {}, {}, {}
    pcall(function() read.stats = Stats() end)
    pcall(function() read.items, read.itemstats = Items() end)
    pcall(function() read.ranks = Ranks(read.spells) end)
    pcall(function()
        Trees("talent", First(C_ClassTalents and C_ClassTalents.GetActiveConfigID), read.points, read.trees)
        Trees("legacy", First(C_Traits and C_Traits.GetConfigIDBySystemID, LEGACY_SYSTEM), read.points, read.trees)
    end)
    pcall(function() read.skills = Skills() end)
end
ns.SHEET = {"stats", "items", "itemstats", "ranks", "points", "trees", "skills"}
