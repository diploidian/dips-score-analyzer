-- projectArthas: /dscore probe - which game calls this client has and what they answer, saved at
-- dipsScoreDB.probe[place] = {"name = answer", ...} for the developer. place is "auction" or "mail" while that
-- window is open, else "world"; a later probe of the same place replaces it. Nothing is recorded by itself.
-- At the auction house it also browses one slot (head pieces you can use) and searches the first row's listings, and
-- notes what came back in dipsScoreDB.probe["auction browse"]: whether the Upgrades scan can read rows, links and stats.
--
-- Nothing personal is saved: mail, auctions and event arguments keep numbers and kinds of values only, never
-- their text (no names, no subjects).
local ADDON, ns = ...
local IsSecret = ns.IsSecret

local MAX_LIST = 12     -- entries shown of a list
local MAX_TEXT = 60

local EVENTS = {
    "AUCTION_HOUSE_SHOW", "AUCTION_HOUSE_CLOSED", "AUCTION_HOUSE_SHOW_FORMATTED_NOTIFICATION",
    "AUCTION_HOUSE_PURCHASE_COMPLETED", "COMMODITY_PURCHASE_SUCCEEDED", "AUCTION_HOUSE_AUCTION_CREATED",
    "PLAYER_INTERACTION_MANAGER_FRAME_SHOW", "PLAYER_INTERACTION_MANAGER_FRAME_HIDE", "MAIL_SHOW", "MAIL_CLOSED",
    "MAIL_INBOX_UPDATE", "PLAYER_MONEY", "QUEST_ACCEPTED", "QUEST_TURNED_IN", "QUEST_LOG_UPDATE", "UNIT_QUEST_LOG_CHANGED",
    "PLAYER_XP_UPDATE", "PLAYER_LEVEL_UP", "PLAYER_FLAGS_CHANGED", "PLAYER_UPDATE_RESTING", "PLAYER_CONTROL_LOST",
    "PLAYER_CONTROL_GAINED", "TAXIMAP_OPENED", "ZONE_CHANGED_NEW_AREA", "PLAYER_EQUIPMENT_CHANGED",
    "TRADE_SKILL_SHOW", "SKILL_LINES_CHANGED", "TIME_PLAYED_MSG", "PVP_MATCH_ACTIVE", "PLAYER_DEAD",
}

local seen = {}     -- event -> how often it fired, and the kinds of its last arguments
local open = {}     -- "auction"/"mail" -> open now

-- A value as text; words: keep a string's own text (only where it can't be personal).
local function Show(v, words)
    if IsSecret(v) then return "hidden" end
    local kind = type(v)
    if kind == "string" then
        if not words then return "text" end
        return '"' .. v:sub(1, MAX_TEXT):gsub("[\r\n]", " ") .. '"'
    elseif kind == "table" then
        local keys = {}
        for k in pairs(v) do
            if #keys == MAX_LIST then break end
            keys[#keys + 1] = tostring(k)
        end
        table.sort(keys)
        return "table{" .. table.concat(keys, " ") .. "}"
    elseif kind == "function" or kind == "userdata" then
        return kind
    end
    return tostring(v)
end

local function Pack(...) return {n = select("#", ...), ...} end

local function List(p, words, from)
    local out = {}
    for i = from or 1, math.min(p.n, MAX_LIST + 2) do out[#out + 1] = Show(p[i], words) end
    return #out > 0 and table.concat(out, " | ") or "nothing"
end

-- "C_Item.GetItemStats" -> the function, or nil.
local function Find(path)
    local v = _G
    for part in path:gmatch("[^.]+") do
        if type(v) ~= "table" then return nil end
        v = v[part]
    end
    return type(v) == "function" and v or nil
end

local out

local function Add(name, answer) out[#out + 1] = name .. " = " .. answer end

-- Calls a game function by its name and notes the answer; returns the packed results when it worked.
local function Ask(words, path, ...)
    local fn = Find(path)
    local args = {}
    for i = 1, select("#", ...) do args[i] = Show((select(i, ...)), false) end
    local name = path .. "(" .. table.concat(args, ", ") .. ")"
    if not fn then return Add(name, "missing") end
    local p = Pack(pcall(fn, ...))
    if not p[1] then return Add(name, "error") end
    Add(name, List(p, words, 2))
    return p
end

local function Stats()
    for i = 1, 5 do Ask(true, "UnitStat", "player", i) end
    for i = 0, 6 do Ask(true, "UnitResistance", "player", i) end
    for _, fn in ipairs({"UnitAttackPower", "UnitRangedAttackPower", "UnitArmor", "UnitHealthMax", "UnitPowerMax",
        "UnitDamage", "UnitAttackSpeed", "UnitRangedDamage"}) do Ask(true, fn, "player") end
    for _, fn in ipairs({"GetCritChance", "GetRangedCritChance", "GetDodgeChance", "GetParryChance", "GetBlockChance",
        "GetSpellBonusHealing", "GetHaste", "GetHitModifier", "GetSpellHitModifier", "GetManaRegen"}) do Ask(true, fn) end
    Ask(true, "GetSpellBonusDamage", 2)
    Ask(true, "GetSpellCritChance", 2)
    Ask(true, "GetUnitSpeed", "player")
    Ask(true, "GetWeaponSkill")
    Ask(true, "InCombatLockdown")
end

local function Gear()
    for _, slot in ipairs({1, 5, 16}) do
        local ok, link = pcall(GetInventoryItemLink, "player", slot)
        if ok and type(link) == "string" and not IsSecret(link) then
            Add("item link of slot " .. slot, (link:match("item:[%-%d:]+") or "no item text"))
            Ask(true, "C_Item.GetItemStats", link)
            Ask(true, "GetItemStats", link)
            Ask(true, "C_Item.GetItemInfo", link)
        end
    end
end

local function Spells()
    local log = ns.Log()
    for i, line in ipairs(log and log.char and log.char.spells or {}) do
        if i > 8 then break end
        local id = tonumber(line:match("^(%d+)"))
        if id then
            Ask(true, "C_Spell.GetSpellSubtext", id)
            Ask(true, "GetSpellSubtext", id)
        end
    end
    Ask(true, "GetNumSkillLines")
    for i = 1, 12 do Ask(true, "GetSkillLineInfo", i) end
    Ask(true, "GetProfessions")
    Add("C_SkillInfo", Show(C_SkillInfo))
    for _, line in ipairs({43, 54, 55, 95, 136, 160, 162, 172, 229}) do -- weapon skills and defense
        local p = Ask(true, "C_SkillInfo.GetSkillLineInfoByID", line)
        if p and type(p[2]) == "table" and not IsSecret(p[2]) then
            for k, v in pairs(p[2]) do Add("skill " .. line .. " " .. tostring(k), Show(v, true)) end
        end
    end
    Ask(true, "UnitAttackBothHands", "player")
    Ask(true, "UnitDefense", "player")
end

-- A talent or Legacy tree: how many nodes it has, and the first few with points in them.
local function Tree(label, config)
    if type(config) ~= "number" then return Add(label, "no config") end
    local p = Ask(true, "C_Traits.GetConfigInfo", config)
    local info = p and p[2]
    if type(info) ~= "table" or type(info.treeIDs) ~= "table" then return end
    for _, tree in ipairs(info.treeIDs) do
        local q = Ask(true, "C_Traits.GetTreeNodes", tree)
        local nodes = q and q[2]
        Ask(true, "C_Traits.GetTreeCurrencyInfo", config, tree, true)
        local shown, with = 0, 0
        for _, node in ipairs(type(nodes) == "table" and nodes or {}) do
            local ok, n = pcall(C_Traits.GetNodeInfo, config, node)
            if ok and type(n) == "table" and type(n.currentRank) == "number" and not IsSecret(n.currentRank)
                and n.currentRank > 0 then
                with = with + 1
                if shown < 3 then
                    shown = shown + 1
                    Add(label .. " node " .. node, "rank " .. n.currentRank .. " " .. Show(n))
                    local entry = n.activeEntry and n.activeEntry.entryID
                    local ok2, e = pcall(C_Traits.GetEntryInfo, config, entry)
                    if ok2 and type(e) == "table" then
                        Add(label .. " entry", Show(e))
                        Ask(true, "C_Traits.GetDefinitionInfo", e.definitionID)
                    end
                end
            end
        end
        Add(label .. " tree " .. tree, (type(nodes) == "table" and #nodes or 0) .. " nodes, " .. with .. " with points")
    end
end

local function Trees()
    local p = Ask(true, "C_ClassTalents.GetActiveConfigID")
    Tree("talents", p and p[2])
    Ask(true, "GetNumTalentTabs")
    p = Ask(true, "C_Traits.GetConfigIDBySystemID", 45)
    Tree("legacy", p and p[2])
    for name, v in pairs(_G) do
        if type(name) == "string" and type(v) ~= "function" and name:find("^C_.*Legacy") then Add(name, Show(v)) end
    end
    if type(Constants) == "table" then Add("Constants.LegacyConsts", Show(Constants.LegacyConsts)) end
end

local function Life()
    for _, fn in ipairs({"GetMoney", "IsResting", "IsInInstance", "GetRealZoneText", "UnitXP", "UnitXPMax",
        "IsInGroup", "IsInRaid", "GetNumGroupMembers"}) do Ask(true, fn, "player") end
    for _, fn in ipairs({"UnitIsAFK", "UnitOnTaxi", "UnitIsDeadOrGhost", "UnitAffectingCombat", "UnitIsPVP"}) do
        Ask(true, fn, "player")
    end
    Ask(true, "C_PvP.IsBattleground")
    Ask(true, "C_QuestLog.GetNumQuestLogEntries")
end

-- Sale mails: the invoice's kind and numbers. Every other text stays "text".
local function Mail()
    local p = Ask(false, "GetInboxNumItems")
    for i = 1, math.min(p and tonumber(p[2]) or 0, 10) do
        local ok, kind = pcall(GetInboxInvoiceInfo or error, i)
        Add("mail " .. i .. " invoice kind", ok and Show(kind, true) or "missing or error")
        Ask(false, "GetInboxInvoiceInfo", i)
        Ask(false, "GetInboxHeaderInfo", i)
    end
    for _, name in ipairs({"AUCTION_SOLD_MAIL_SUBJECT", "AUCTION_EXPIRED_MAIL_SUBJECT", "AUCTION_WON_MAIL_SUBJECT",
        "AUCTION_OUTBID_MAIL_SUBJECT", "AUCTION_REMOVED_MAIL_SUBJECT"}) do Add(name, Show(_G[name], true)) end
end

-- The browse and search answers come later, as events: they are noted in dipsScoreDB.probe["auction browse"].
local browse          -- the answers being gathered, nil when no browse is waiting
local searched        -- the itemKey searched for, waiting for its results

local function Note(name, answer)
    browse[#browse + 1] = name .. " = " .. answer
end

-- What a browse row or an item's stats hold, field by field (item names are not personal; owners are left out).
local function Fields(label, t)
    if type(t) ~= "table" or IsSecret(t) then return Note(label, Show(t)) end
    for k, v in pairs(t) do
        if k ~= "owners" then
            Note(label .. " " .. tostring(k), type(v) == "table" and Show(v) .. " " .. List(Pack(unpack(v)), true)
                or Show(v, true))
        end
    end
end

-- One gear slot's browse: the cheapest head pieces you can use, near your level.
local function Browse()
    local AH = C_AuctionHouse
    if not (AH and AH.SendBrowseQuery) then return Add("browse", "C_AuctionHouse.SendBrowseQuery missing") end
    local filters = {}
    if Enum and Enum.AuctionHouseFilter and Enum.AuctionHouseFilter.UsableOnly then
        filters[1] = Enum.AuctionHouseFilter.UsableOnly
    end
    local armor = Enum and Enum.ItemClass and Enum.ItemClass.Armor or 4
    local head = Enum and Enum.InventoryType and Enum.InventoryType.IndexHeadType or 1
    local sort = Enum and Enum.AuctionHouseSortOrder and Enum.AuctionHouseSortOrder.Price or 0
    local level = UnitLevel("player") or 1
    local query = {searchString = "", sorts = {{sortOrder = sort, reverseSort = false}}, filters = filters,
        itemClassFilters = {{classID = armor, inventoryType = head}}, minLevel = math.max(1, level - 10), maxLevel = level}
    local ok = pcall(AH.SendBrowseQuery, query)
    Add("C_AuctionHouse.SendBrowseQuery(head, usable " .. tostring(filters[1] ~= nil) .. ")", ok and "sent" or "error")
    if ok then browse = {"taken = " .. time()} end
end

local function Auction()
    Ask(false, "C_AuctionHouse.GetNumOwnedAuctions")
    local p = Ask(false, "C_AuctionHouse.GetOwnedAuctionInfo", 1)
    if p and type(p[2]) == "table" then
        for k, v in pairs(p[2]) do Add("owned auction " .. tostring(k), Show(v)) end
    end
    Ask(false, "C_AuctionHouse.GetNumBidTypes")
    for _, path in ipairs({"C_AuctionHouse.SendBrowseQuery", "C_AuctionHouse.GetBrowseResults",
        "C_AuctionHouse.GetItemKeyInfo", "C_AuctionHouse.SendSearchQuery", "C_AuctionHouse.GetNumItemSearchResults",
        "C_AuctionHouse.GetItemSearchResultInfo", "C_AuctionHouse.MakeItemKey", "C_AuctionHouse.ReplicateItems",
        "C_AuctionHouse.GetReplicateItemLink", "C_AuctionHouse.IsThrottledMessageSystemReady",
        "C_AuctionHouse.GetTimeLeftBandInfo", "C_TooltipInfo.GetItemKey", "C_TooltipInfo.GetHyperlink",
        "C_AuctionHouse.SearchForItemKeys"}) do
        Add(path, Find(path) and "exists" or "missing")
    end
    Ask(false, "C_AuctionHouse.IsThrottledMessageSystemReady")
    for _, enum in ipairs({"AuctionHouseFilter", "AuctionHouseSortOrder", "ItemClass", "InventoryType"}) do
        local e = Enum and Enum[enum]
        Add("Enum." .. enum, type(e) == "table" and Show(e) or "missing")
    end
    Browse()
end

-- A browse came back: note the first rows, then search the first equipment row for its listings and link.
local function Browsed()
    local ok, rows = pcall(C_AuctionHouse.GetBrowseResults)
    Note("GetBrowseResults", ok and (type(rows) == "table" and #rows .. " rows" or Show(rows)) or "error")
    if not ok or type(rows) ~= "table" then return end
    for i = 1, math.min(#rows, 3) do
        Fields("row " .. i, rows[i])
        local key = type(rows[i]) == "table" and rows[i].itemKey
        Fields("row " .. i .. " itemKey", key)
        local ok2, info = pcall(C_AuctionHouse.GetItemKeyInfo, key)
        Fields("row " .. i .. " GetItemKeyInfo", ok2 and info or "error")
        if C_TooltipInfo and C_TooltipInfo.GetItemKey and type(key) == "table" then
            local ok3, tip = pcall(C_TooltipInfo.GetItemKey, key.itemID, key.itemLevel, key.itemSuffix)
            local lines = ok3 and type(tip) == "table" and tip.lines
            Note("row " .. i .. " C_TooltipInfo.GetItemKey", ok3 and (type(lines) == "table" and #lines .. " lines" or Show(tip)) or "error")
            for j = 1, math.min(type(lines) == "table" and #lines or 0, 6) do
                Note("row " .. i .. " tip line " .. j, Show(lines[j].leftText, true))
            end
        end
        if not searched and type(key) == "table" and C_AuctionHouse.SendSearchQuery then
            local sort = Enum and Enum.AuctionHouseSortOrder and Enum.AuctionHouseSortOrder.Price or 0
            local ok4 = pcall(C_AuctionHouse.SendSearchQuery, key, {{sortOrder = sort, reverseSort = false}}, true)
            Note("row " .. i .. " SendSearchQuery", ok4 and "sent" or "error")
            if ok4 then searched = key end
        end
    end
end

-- The search came back: the first listing's link, and what the game says about its stats.
local function Searched()
    local key = searched
    searched = nil
    local ok, n = pcall(C_AuctionHouse.GetNumItemSearchResults, key)
    Note("GetNumItemSearchResults", ok and Show(n) or "error")
    local ok2, r = pcall(C_AuctionHouse.GetItemSearchResultInfo, key, 1)
    if not ok2 or type(r) ~= "table" then return Note("GetItemSearchResultInfo", ok2 and Show(r) or "error") end
    Fields("listing 1", r)
    local link = r.itemLink
    if type(link) == "string" and not IsSecret(link) then
        Note("listing 1 item text", link:match("item:[%-%d:]+") or "none")
        local ok3, stats = pcall(C_Item.GetItemStats, link)
        Fields("listing 1 C_Item.GetItemStats", ok3 and stats or "error")
    end
end

local function SaveBrowse(why)
    if not browse then return end
    Note("finished", why)
    if type(ns.db.probe) ~= "table" then ns.db.probe = {} end
    ns.db.probe["auction browse"] = browse
    ns.Print(string.format("probe (auction browse): %d answers noted. /reload to save them.", #browse))
end

function ns.Probe()
    if not ns.db then return ns.Print("not loaded yet.") end
    local place = open.auction and "auction" or open.mail and "mail" or "world"
    out = {}
    Add("taken", tostring(time()))
    Add("build", List(Pack(GetBuildInfo()), true))
    local parts = {Stats, Gear, Spells, Trees, Life}
    if place == "mail" then parts = {Mail, Life} elseif place == "auction" then parts = {Auction, Life} end
    for _, part in ipairs(parts) do
        local ok = pcall(part)
        if not ok then Add("part stopped early", "error") end
    end
    for _, event in ipairs(EVENTS) do Add("event " .. event, seen[event] or "not fired") end
    if type(ns.db.probe) ~= "table" then ns.db.probe = {} end
    ns.db.probe[place] = out
    ns.Print(string.format("probe (%s): %d answers noted. /reload to save them.", place, #out))
end

local E = CreateFrame("Frame")
for _, event in ipairs(EVENTS) do
    if not pcall(E.RegisterEvent, E, event) then seen[event] = "does not exist" end
end
local OPENS = {AUCTION_HOUSE_SHOW = "auction", MAIL_SHOW = "mail"}
local CLOSES = {AUCTION_HOUSE_CLOSED = "auction", MAIL_CLOSED = "mail"}
local count = {}
-- The browse probe's answers (not counted as plain events: they only matter while a browse waits).
local B = CreateFrame("Frame")
for _, event in ipairs({"AUCTION_HOUSE_BROWSE_RESULTS_UPDATED", "ITEM_SEARCH_RESULTS_UPDATED",
    "AUCTION_HOUSE_THROTTLED_SYSTEM_READY", "AUCTION_HOUSE_THROTTLED_MESSAGE_DROPPED", "AUCTION_HOUSE_CLOSED"}) do
    if not pcall(B.RegisterEvent, B, event) then seen[event] = "does not exist" end
end
B:SetScript("OnEvent", function(_, event)
    if not browse then return end
    if event == "AUCTION_HOUSE_BROWSE_RESULTS_UPDATED" then
        pcall(Browsed)
        if not searched then SaveBrowse("browse answered, no search sent") end
    elseif event == "ITEM_SEARCH_RESULTS_UPDATED" then
        if searched then pcall(Searched) end
        SaveBrowse("search answered")
        browse = nil
    elseif event == "AUCTION_HOUSE_THROTTLED_MESSAGE_DROPPED" then
        Note("event " .. event, "fired")
    elseif event == "AUCTION_HOUSE_CLOSED" then
        SaveBrowse("auction house closed first")
        browse, searched = nil, nil
    end
end)
E:SetScript("OnEvent", function(_, event, ...)
    if OPENS[event] then open[OPENS[event]] = true end
    if CLOSES[event] then open[CLOSES[event]] = nil end
    count[event] = (count[event] or 0) + 1
    local ok, args = pcall(List, Pack(...), false)
    seen[event] = "fired " .. count[event] .. ": " .. (ok and args or "unreadable")
end)
