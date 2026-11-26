-- projectArthas: /dscore upgrades (or the Find upgrades button under the auction house) - a scan of the auction house for
-- gear you can wear and afford, saved at dipsScoreLog.market for the app's Upgrades drawer, which works out what each
-- piece is worth to you. Nothing is bought: you buy with the game's own button.
--
--   taken, realm, faction, money, level   when, where, your gold then (copper) and your level
--   filtered = true or nil                the game's "usable only" filter was there; without it a red tooltip line drops a row
--   rows     = {"n,slot,itemID,itemLevel,quality,minPrice,count,unique,name", ...}
--              slot: the kind of slot browsed, as the game's inventory type (1 head, 13 one-hand, 17 two-hand: see KINDS);
--              minPrice in copper, the listing's that was looked at when there was one; unique "1"/"0", "" when its tooltip
--              was not read; name last, as it can hold a comma
--   rowstats = {"n,KEY,value", ...}       C_Item.GetItemStats of the listing's own link (ITEM_MOD_STRENGTH_SHORT, ...)
--   rowtips  = {"n,type,text", ...}       its tooltip, as Sheet.lua saves a worn item's (type R: the right side; "!": red or grey)
--   links    = {"n,item:...", ...}
--   bases    = {"n,name", ...}           the item's own name, when the listing's is longer (a random-stat suffix)
--
-- One browse per kind of slot, of what you can afford near your level; the MAX_ROWS of each with the highest item level are
-- kept. Then a closer look (a search for its listings) at up to MAX_LOOKS of them, the highest item level of each kind
-- first: only those get stats and lines. One query at a time, as the game's throttle allows; one not answered in WAIT
-- seconds is passed over. A new scan replaces the old, and the game writes it to disk at the next /reload or logout; a
-- scan stopped early saves nothing. Every call is looked for first and run under pcall, as in Char.lua.
local ADDON, ns = ...
local IsSecret, Field = ns.IsSecret, ns.Field

local MAX_ROWS, MAX_LOOKS, WAIT, TRIES = 30, 40, 10, 3
local ARMOR = Enum and Enum.ItemClass and Enum.ItemClass.Armor or 4
local WEAPON = Enum and Enum.ItemClass and Enum.ItemClass.Weapon or 2
local PRICE = Enum and Enum.AuctionHouseSortOrder and Enum.AuctionHouseSortOrder.Price or 0
-- {the inventory type saved as the rows' slot, what chat calls it, {item class, inventory type}, ...}: what one browse asks for
local KINDS = {
    {1, "head", {ARMOR, 1}}, {2, "neck", {ARMOR, 2}}, {3, "shoulder", {ARMOR, 3}}, {16, "back", {ARMOR, 16}},
    {5, "chest", {ARMOR, 5}, {ARMOR, 20}}, {9, "wrist", {ARMOR, 9}}, {10, "hands", {ARMOR, 10}}, {6, "waist", {ARMOR, 6}},
    {7, "legs", {ARMOR, 7}}, {8, "feet", {ARMOR, 8}}, {11, "finger", {ARMOR, 11}}, {12, "trinket", {ARMOR, 12}},
    {13, "one-hand", {WEAPON, 13}, {WEAPON, 21}}, {17, "two-hand", {WEAPON, 17}},
    {22, "off hand", {WEAPON, 22}, {ARMOR, 14}, {ARMOR, 23}},
    {15, "ranged", {WEAPON, 15}, {WEAPON, 25}, {WEAPON, 26}, {ARMOR, 28}},
}

local AH            -- C_AuctionHouse, once a scan starts
local scan          -- the scan under way, nil when none
local shown         -- the auction house is open
local button

local function Say(msg) ns.Print("upgrades: " .. msg) end

-- Calls fn; returns its first result, or nil when it is missing, fails or gives a hidden value.
local function First(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, v = pcall(fn, ...)
    if ok and not IsSecret(v) then return v end
end

local function Num(v) return type(v) == "number" and not IsSecret(v) and v or nil end

local function Button()
    if not button and AuctionHouseFrame and CreateFrame then
        button = CreateFrame("Button", nil, AuctionHouseFrame, "UIPanelButtonTemplate")
        button:SetSize(120, 22)
        button:SetPoint("TOPRIGHT", AuctionHouseFrame, "BOTTOMRIGHT", 0, -2)
        button:SetScript("OnClick", function() ns.Upgrades(scan and "stop" or "") end)
        local list = CreateFrame("Button", nil, AuctionHouseFrame, "UIPanelButtonTemplate")
        list:SetSize(60, 22)
        list:SetPoint("RIGHT", button, "LEFT", -4, 0)
        list:SetText("List")
        list:SetScript("OnClick", function() ns.UpgradesList() end) -- Upgrades.lua
    end
    if button then button:SetText(scan and "Stop the scan" or "Find upgrades") end
end

-- The game will take a query now (a client without the call is never held back).
local function Ready()
    if type(AH.IsThrottledMessageSystemReady) ~= "function" then return true end
    local ok, ready = pcall(AH.IsThrottledMessageSystemReady)
    return not ok or ready == true
end

-- A row's name and quality, as the game knows them now; nil while it has not loaded the item.
local function Name(row)
    local info = First(AH.GetItemKeyInfo, row.key)
    if type(info) ~= "table" then return end
    if type(info.itemName) == "string" and not IsSecret(info.itemName) then
        row.base = info.itemName
        row.name = row.name or info.itemName
    end
    row.quality = Num(info.quality) or row.quality
    if info.isEquipment == false then row.drop = true end
end

-- A looked-at row's tooltip: whether it is unique, and, without the game's filter, whether a red line says you can't use it.
-- A tooltip not loaded yet is read again at the save.
local function Tip(row, filtered)
    if row.tips or not row.full then return end
    local lines = ns.TipLines(First(C_TooltipInfo and C_TooltipInfo.GetHyperlink, row.full)) -- Sheet.lua
    if not lines or #lines == 0 then return end
    row.tips, row.unique = lines, "0"
    for _, l in ipairs(lines) do
        if l.shade == "red" and not filtered then row.drop = true end
        if l.left:find("^Unique") then row.unique = "1" end
    end
end

-- The query the scan is at: a browse of one kind of slot, or a search for one row's listings. True when the game took it.
local function Query()
    local s, sorts = scan, {{sortOrder = PRICE, reverseSort = false}}
    if s.looks then return pcall(AH.SendSearchQuery, s.looks[s.look].key, sorts, true) end
    local classes = {}
    for i = 3, #KINDS[s.kind] do
        classes[#classes + 1] = {classID = KINDS[s.kind][i][1], inventoryType = KINDS[s.kind][i][2]}
    end
    return pcall(AH.SendBrowseQuery, {searchString = "", sorts = sorts, filters = s.filters, itemClassFilters = classes,
        minLevel = math.max(1, s.level - 10), maxLevel = s.level})
end

-- The rows looked at closer: the highest item level of each kind first, then the next of each, up to MAX_LOOKS.
local function Looks()
    local by = {}
    for _, row in ipairs(scan.rows) do
        by[row.slot] = by[row.slot] or {}
        table.insert(by[row.slot], row) -- each kind's are kept highest first
    end
    local looks = {}
    for depth = 1, MAX_ROWS do
        for _, kind in ipairs(KINDS) do
            local row = by[kind[1]] and by[kind[1]][depth]
            if row and #looks < MAX_LOOKS then looks[#looks + 1] = row end
        end
    end
    scan.looks, scan.look = looks, 1
    if #looks > 0 then Say("looking closer at " .. #looks .. " listings.") end
end

local function Save()
    local s, log = scan, ns.Log()
    scan = nil
    pcall(Button)
    if not log then return Say("not loaded yet; nothing saved.") end
    local m = {taken = time(), realm = First(GetRealmName), faction = First(UnitFactionGroup, "player"), money = s.money,
        level = s.level, filtered = s.filtered or nil, rows = {}, rowstats = {}, rowtips = {}, links = {}, bases = {}}
    local n, looked = 0, 0
    for _, row in ipairs(s.rows) do
        if not row.name or not row.quality then Name(row) end -- the game may have loaded it since
        Tip(row, s.filtered)
        if not row.drop then
            n = n + 1
            m.rows[n] = n .. "," .. row.slot .. "," .. row.id .. "," .. Field(row.level) .. "," .. Field(row.quality) .. ","
                .. row.price .. "," .. Field(row.count) .. "," .. (row.unique or "") .. "," .. (row.name or "")
            for _, line in ipairs(row.stats or {}) do m.rowstats[#m.rowstats + 1] = n .. "," .. line end
            ns.TipRows(row.tips, n .. ",", m.rowtips)
            if row.link then
                m.links[#m.links + 1] = n .. "," .. row.link
                looked = looked + 1
            end
            if row.base and row.name and row.base ~= row.name then m.bases[#m.bases + 1] = n .. "," .. row.base end
        end
    end
    log.market = m
    if ns.RefreshUpgrades then pcall(ns.RefreshUpgrades) end -- Upgrades.lua's list, when open
    Say(string.format("saved %d listings, %d of them looked at closely%s. List shows them here; /reload, then open Upgrades on "
        .. "the app's Profile.", n, looked, s.missed > 0 and (", " .. s.missed .. " queries went unanswered") or ""))
end

local Send

local function Advance()
    local s = scan
    if not s then return end
    s.waiting, s.tries = false, 0
    if s.looks then s.look = s.look + 1 else s.kind = s.kind + 1 end
    Send()
end

-- Sends the query the scan is at, when the game will take one (else AUCTION_HOUSE_THROTTLED_SYSTEM_READY calls it again).
function Send()
    local s = scan
    if not s or s.waiting or not Ready() then return end
    if not s.looks and s.kind > #KINDS then Looks() end
    if s.looks and s.look > #s.looks then return Save() end
    local step = s.looks and "look " .. s.look or "kind " .. s.kind
    if s.said ~= step then -- a query sent again is not said again
        s.said = step
        if not s.looks then
            Say(string.format("slot %d of %d (%s)", s.kind, #KINDS, KINDS[s.kind][2]))
        elseif s.look % 10 == 0 then
            Say(string.format("listing %d of %d", s.look, #s.looks))
        end
    end
    if not Query() then
        if s.looks then return Advance() end
        scan = nil
        pcall(Button)
        return Say("the game refused the browse; scan stopped, nothing saved.")
    end
    s.sent = s.sent + 1
    s.waiting = s.sent -- which query is waited for: an answer or a drop ends the wait, so its timer knows
    local sent = s.sent
    if C_Timer and C_Timer.After then
        C_Timer.After(WAIT, function()
            if scan == s and s.waiting == sent then
                s.missed = s.missed + 1
                Advance()
            end
        end)
    end
end

-- A browse came back: what you can afford of it, the highest item level first, MAX_ROWS kept.
local function Browsed()
    local s, slot = scan, KINDS[scan.kind][1]
    local ok, found = pcall(AH.GetBrowseResults)
    if not ok or type(found) ~= "table" then return end
    local mine = {}
    for _, r in ipairs(found) do
        if type(r) == "table" and type(r.itemKey) == "table" then
            local id, price = Num(r.itemKey.itemID), Num(r.minPrice)
            if id and price and price <= s.money then
                mine[#mine + 1] = {key = r.itemKey, slot = slot, id = id, level = Num(r.itemKey.itemLevel), price = price,
                    count = Num(r.totalQuantity)}
            end
        end
    end
    table.sort(mine, function(a, b)
        if (a.level or 0) ~= (b.level or 0) then return (a.level or 0) > (b.level or 0) end
        return a.price < b.price
    end)
    for i = 1, math.min(#mine, MAX_ROWS) do
        Name(mine[i])
        s.rows[#s.rows + 1] = mine[i]
    end
end

-- A search came back: the cheapest listing's link, its full name (a random-stat item's tells it from the others), its
-- price, stats and tooltip.
local function Looked()
    local row = scan.looks[scan.look]
    local r = First(AH.GetItemSearchResultInfo, row.key, 1)
    local link = type(r) == "table" and r.itemLink
    if type(link) ~= "string" or IsSecret(link) then return end
    row.full, row.link = link, link:match("item:[%-%d:]+")
    row.name = link:match("%[(.-)%]") or row.name
    row.price = Num(r.buyoutAmount) or row.price
    row.stats = {}
    local stats = First(C_Item and C_Item.GetItemStats, link)
    for key, v in pairs(type(stats) == "table" and stats or {}) do
        if Num(v) then row.stats[#row.stats + 1] = Field(key) .. "," .. string.format("%.3f", v) end
    end
    Tip(row, scan.filtered)
end

-- The auction house is open; a scan is under way (Upgrades.lua's Jump waits for it).
function ns.MarketState() return shown == true, scan ~= nil end

-- /dscore upgrades [stop | list]
function ns.Upgrades(arg)
    if arg == "list" then return ns.UpgradesList() end -- Upgrades.lua
    if arg == "stop" then
        Say(scan and "scan stopped, nothing saved." or "no scan under way.")
        scan = nil
        return pcall(Button)
    end
    if scan then return Say("a scan is under way; /dscore upgrades stop cancels it.") end
    if not shown then return Say("open the auction house first.") end
    AH = C_AuctionHouse
    if not (AH and AH.SendBrowseQuery and AH.GetBrowseResults and AH.SendSearchQuery and AH.GetItemSearchResultInfo) then
        return Say("this client's auction house can't be browsed by an add-on.")
    end
    local usable = Enum and Enum.AuctionHouseFilter and Enum.AuctionHouseFilter.UsableOnly
    scan = {kind = 1, rows = {}, money = First(GetMoney) or 0, filters = {usable}, filtered = usable ~= nil,
        level = First(UnitLevel, "player") or 1, sent = 0, missed = 0, tries = 0}
    Say("scanning " .. #KINDS .. " kinds of slot. Keep the auction house open; /dscore upgrades stop cancels.")
    pcall(Button)
    Send()
end

local E = CreateFrame("Frame")
for _, event in ipairs({"AUCTION_HOUSE_SHOW", "AUCTION_HOUSE_CLOSED", "AUCTION_HOUSE_BROWSE_RESULTS_UPDATED",
    "ITEM_SEARCH_RESULTS_UPDATED", "AUCTION_HOUSE_THROTTLED_SYSTEM_READY", "AUCTION_HOUSE_THROTTLED_MESSAGE_DROPPED"}) do
    pcall(E.RegisterEvent, E, event)
end
E:SetScript("OnEvent", function(_, event)
    if event == "AUCTION_HOUSE_SHOW" then
        shown = true
        pcall(Button)
        if C_Timer and C_Timer.After then C_Timer.After(0.2, function() pcall(Button) end) end -- its window may load after this
    elseif event == "AUCTION_HOUSE_CLOSED" then
        shown = false
        if scan then
            scan = nil
            Say("the auction house closed: scan stopped, nothing saved.")
        end
        pcall(Button)
    elseif not scan then
        return
    elseif event == "AUCTION_HOUSE_THROTTLED_SYSTEM_READY" then
        Send()
    elseif event == "AUCTION_HOUSE_THROTTLED_MESSAGE_DROPPED" then
        if scan.waiting then -- the query was dropped: sent again when the game is ready, at most TRIES times
            scan.waiting, scan.tries = false, scan.tries + 1
            if scan.tries > TRIES then Advance() else Send() end
        end
    elseif event == "AUCTION_HOUSE_BROWSE_RESULTS_UPDATED" and scan.waiting and not scan.looks then
        pcall(Browsed)
        Advance()
    elseif event == "ITEM_SEARCH_RESULTS_UPDATED" and scan.waiting and scan.looks then
        pcall(Looked)
        Advance()
    end
end)
