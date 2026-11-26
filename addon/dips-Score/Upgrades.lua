-- projectArthas: /dscore upgrades list (or the List button beside Find upgrades) - the last auction house scan
-- (dipsScoreLog.market, Market.lua) in a window, ranked by gain per gold. Scored here with the standard weights (Weights.lua),
-- by what you wear now; what your own fights measured, and the usual-price guardrail, are in the app's Upgrades drawer.
-- As there: a ring or trinket is weighed against the weaker one worn, a two-hander against main and off hand together; a
-- one-hander or an off hand while a two-hander is worn, a slot whose worn item's stats can't be read, a listing not looked at
-- closely and a unique item you wear are left out, and so is anything not better than what you wear or over half the gold you
-- had at the scan. Clicking a row at the auction house searches for it, so you buy with the game's own button. Every call is
-- looked for first and run under pcall, as in Char.lua.
local ADDON, ns = ...
local IsSecret = ns.IsSecret

local W = dipsScoreWeights -- Weights.lua
local MAX_SHOWN, ROW, WIDTH = 15, 18, 500
local DPS = "ITEM_MOD_DAMAGE_PER_SECOND_SHORT"
local PRICE = Enum and Enum.AuctionHouseSortOrder and Enum.AuctionHouseSortOrder.Price or 0
-- the inventory type a scan browsed -> the worn slots it is weighed against, and what the list calls it (live/upgrades.py KIND)
local KIND = {[1] = {{1}, "Head"}, [2] = {{2}, "Neck"}, [3] = {{3}, "Shoulder"}, [16] = {{15}, "Back"}, [5] = {{5}, "Chest"},
    [9] = {{9}, "Wrist"}, [10] = {{10}, "Hands"}, [6] = {{6}, "Waist"}, [7] = {{7}, "Legs"}, [8] = {{8}, "Feet"},
    [11] = {{11, 12}, "Ring"}, [12] = {{13, 14}, "Trinket"}, [13] = {{16}, "One-hand"}, [17] = {{16, 17}, "Two-hand"},
    [22] = {{17}, "Off hand"}, [15] = {{18}, "Ranged"}}
local ROLE = {melee = "a melee damage dealer", ranged = "a ranged damage dealer", caster = "a spellcaster", healer = "a healer",
    tank = "a tank"}
-- {x, width, justify}: item, slot, gain, price, gain per gold
local COLS = {{0, 200, "LEFT"}, {205, 60, "LEFT"}, {270, 55, "RIGHT"}, {330, 100, "RIGHT"}, {435, 65, "RIGHT"}}

local frame

-- Calls fn; returns its first result, or nil when it is missing, fails or gives a hidden value.
local function First(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, v = pcall(fn, ...)
    if ok and not IsSecret(v) then return v end
end

local function Num(v) return type(v) == "number" and not IsSecret(v) and v or nil end

-- copper as the game writes it (trade_view.coin)
local function Coin(c)
    local g, s, k = math.floor(c / 10000), math.floor(c / 100) % 100, c % 100
    local out = {}
    if g > 0 then out[#out + 1] = g .. "g" end
    if s > 0 or g > 0 and k > 0 then out[#out + 1] = s .. "s" end
    if k > 0 or g == 0 and s == 0 then out[#out + 1] = k .. "c" end
    return table.concat(out, " ")
end

local function Ago(seconds)
    local m = math.max(1, math.floor(seconds / 60 + 0.5))
    if m < 60 then return m .. " min ago" end
    if m < 48 * 60 then return math.floor(m / 60 + 0.5) .. " h ago" end
    return math.floor(m / 1440 + 0.5) .. " days ago"
end

local function Class()
    if type(UnitClass) ~= "function" then return nil end
    local ok, _, token = pcall(UnitClass, "player")
    return ok and type(token) == "string" and not IsSecret(token) and token or nil
end

-- the role's table, the class's own values over it (gearworth.table)
local function Weights(role, cls)
    local out = {}
    for k, v in pairs(W.tables[role]) do out[k] = v end
    for k, v in pairs(W.class[role] and W.class[role][cls or ""] or {}) do out[k] = v end
    return out
end

-- an item's stats in points, worn in slot: a weapon's damage per second only in the slots the role fights with (gearworth.score)
local function Score(stats, slot, role, weights)
    local fights = false
    for _, s in ipairs(W.weaponSlots[role] or {}) do
        if s == slot then fights = true end
    end
    local points = 0
    for key, amount in pairs(stats or {}) do
        local w = weights[key]
        if w and (key ~= DPS or fights) then points = points + amount * w end
    end
    return points
end

-- What you wear in slot, in points (0 when nothing is), or false when its stats can't be read; and its item ID.
local function Worn(slot, role, weights)
    local id = Num(First(GetInventoryItemID, "player", slot))
    if not id then return 0 end
    local link = First(GetInventoryItemLink, "player", slot)
    local found = type(link) == "string" and First(C_Item and C_Item.GetItemStats, link)
    if type(found) ~= "table" then return false, id end
    local stats = {}
    for key, v in pairs(found) do
        if Num(v) then stats[key] = v end
    end
    return Score(stats, slot, role, weights), id
end

local function TwoHander()
    local id = Num(First(GetInventoryItemID, "player", 16))
    local info = C_Item and C_Item.GetItemInfoInstant or GetItemInfoInstant
    if not id or type(info) ~= "function" then return false end
    local ok, _, _, _, loc = pcall(info, id)
    return ok and not IsSecret(loc) and loc == "INVTYPE_2HWEAPON"
end

-- The scan's rows that beat what you wear for at most cap copper, the most gain per gold first (live/upgrades.py).
local function Rank(m, role, weights, cap)
    local stats, looked, bases = {}, {}, {}
    for _, s in ipairs(type(m.rowstats) == "table" and m.rowstats or {}) do
        local n, key, v = tostring(s):match("^(%d+),([^,]+),(.+)$")
        n, v = tonumber(n), tonumber(v)
        if n and v then
            stats[n] = stats[n] or {}
            stats[n][key], looked[n] = v, true
        end
    end
    for _, s in ipairs(type(m.rowtips) == "table" and m.rowtips or {}) do
        local n = tonumber(tostring(s):match("^(%d+),"))
        if n then looked[n] = true end
    end
    for _, s in ipairs(type(m.bases) == "table" and m.bases or {}) do
        local n, name = tostring(s):match("^(%d+),(.+)$")
        if n then bases[tonumber(n)] = name end
    end
    local worn, ids, two = {}, {}, TwoHander()
    for slot = 1, 19 do
        local points, id = Worn(slot, role, weights)
        worn[slot] = points
        if id then ids[id] = true end
    end
    local out = {}
    for _, s in ipairs(type(m.rows) == "table" and m.rows or {}) do
        local n, kind, id, level, quality, price, _, unique, name =
            tostring(s):match("^(%d+),(%d+),(%d+),([^,]*),([^,]*),(%d+),([^,]*),([^,]*),(.*)$")
        n, kind, id, price = tonumber(n), tonumber(kind), tonumber(id), tonumber(price)
        local k = kind and KIND[kind]
        if k and looked[n] and price > 0 and price <= cap and not (unique == "1" and ids[id])
            and not (two and (kind == 13 or kind == 22)) then
            local against
            for i, slot in ipairs(k[1]) do
                local w = worn[slot]
                if w == false then
                    against = false
                    break
                end
                if i == 1 then
                    against = w
                elseif kind == 11 or kind == 12 then
                    against = math.min(against, w) -- the weaker ring or trinket
                else
                    against = against + w
                end
            end
            local gain = against and Score(stats[n], k[1][1], role, weights) - against
            if gain and gain > 0 then
                name = name ~= "" and name or ("item " .. id)
                out[#out + 1] = {id = id, level = tonumber(level), quality = tonumber(quality), name = name,
                    base = bases[n] or name, slot = k[2], gain = gain, price = price, per = gain / (price / 10000)}
            end
        end
    end
    table.sort(out, function(a, b) return a.per > b.per end)
    return out
end

-- A row clicked: at the auction house, a search for it, so its listing and the game's Buy button show.
local function Jump(r)
    local open, scanning = ns.MarketState() -- Market.lua
    if not open then return frame.foot:SetText("Open the auction house to see the listing.") end
    if scanning then return frame.foot:SetText("A scan is under way; click again when it is done.") end
    local AH = C_AuctionHouse
    local key = AH and First(AH.MakeItemKey, r.id, r.level)
    if type(key) == "table" then pcall(AH.SendSearchQuery, key, {{sortOrder = PRICE, reverseSort = false}}, true) end
    local bar = AuctionHouseFrame and AuctionHouseFrame.SearchBar
    if type(bar) == "table" then
        if not pcall(bar.SetSearchText, bar, r.base) then
            pcall(function() bar.SearchBox:SetText(r.base) end)
        end
        pcall(bar.StartSearch, bar)
    end
    frame.foot:SetText("Searched for " .. r.base .. ". You buy with the auction house's own button.")
end

local function Cells(parent, font)
    local cells = {}
    for i, c in ipairs(COLS) do
        local fs = ns.Text(parent, font)
        fs:SetPoint("LEFT", c[1], 0)
        fs:SetWidth(c[2])
        fs:SetJustifyH(c[3])
        pcall(fs.SetWordWrap, fs, false)
        cells[i] = fs
    end
    return cells
end

local function Build()
    frame = CreateFrame("Frame", "dipsScoreUpgrades", UIParent, "BackdropTemplate")
    frame:SetWidth(WIDTH + 20)
    frame:SetPoint("CENTER")
    frame:SetFrameStrata("DIALOG")
    frame:SetClampedToScreen(true)
    frame:SetMovable(true)
    frame:EnableMouse(true)
    frame:RegisterForDrag("LeftButton")
    frame:SetScript("OnDragStart", frame.StartMoving)
    frame:SetScript("OnDragStop", frame.StopMovingOrSizing)
    frame:Hide()
    ns.Backdrop(frame, 0.04, 0.04, 0.06, 0.95)
    tinsert(UISpecialFrames, "dipsScoreUpgrades") -- Escape closes it
    local title = ns.Text(frame, "GameFontNormal")
    title:SetPoint("TOPLEFT", 10, -10)
    title:SetText("Upgrades")
    local ok, close = pcall(CreateFrame, "Button", nil, frame, "UIPanelCloseButton")
    if ok and close then close:SetPoint("TOPRIGHT", 2, 2) end
    frame.cap = ns.Text(frame)
    frame.cap:SetPoint("TOPLEFT", 10, -30)
    frame.cap:SetWidth(WIDTH)
    frame.head = CreateFrame("Frame", nil, frame)
    frame.head:SetSize(WIDTH, ROW)
    frame.head:SetPoint("TOPLEFT", frame.cap, "BOTTOMLEFT", 0, -8)
    for i, fs in ipairs(Cells(frame.head)) do
        fs:SetText(({"Item", "Slot", "Gain", "Price", "Per gold"})[i])
        fs:SetTextColor(0.55, 0.55, 0.6)
    end
    frame.rows = {}
    for i = 1, MAX_SHOWN do
        local row = CreateFrame("Button", nil, frame)
        row:SetSize(WIDTH, ROW)
        row:SetPoint("TOPLEFT", frame.head, "BOTTOMLEFT", 0, -(i - 1) * ROW)
        local hl = row:CreateTexture(nil, "HIGHLIGHT")
        hl:SetAllPoints()
        hl:SetColorTexture(1, 1, 1, 0.08)
        row.cells = Cells(row)
        row:SetScript("OnClick", function(self) Jump(self.item) end)
        frame.rows[i] = row
    end
    frame.foot = ns.Text(frame)
    frame.foot:SetWidth(WIDTH)
end

local function Fill()
    local log = ns.Log()
    local m = log and type(log.market) == "table" and log.market
    local cls = Class()
    local role = W.byClass[cls or ""] or "melee"
    local cap = m and math.max(1, math.floor((Num(m.money) or 0) / 20000 + 0.5)) * 10000 -- half your gold then, whole gold
    local rows = m and Rank(m, role, Weights(role, cls), cap) or {}
    if m then
        frame.cap:SetText(string.format("Your last scan%s, the most gain for your gold first, at most %s (half your gold then). "
            .. "Gain is in points by standard weights for %s; what your fights measured is in the app's Upgrades drawer.",
            Num(m.taken) and (", " .. Ago(time() - m.taken)) or "", Coin(cap), ROLE[role]))
    else
        frame.cap:SetText("No scan yet. At the auction house, press Find upgrades or type /dscore upgrades.")
    end
    frame.head:SetShown(#rows > 0)
    local shown = math.min(#rows, MAX_SHOWN)
    for i, row in ipairs(frame.rows) do
        local r = rows[i]
        row.item = r
        row:SetShown(r ~= nil)
        if r then
            local c = ITEM_QUALITY_COLORS and r.quality and ITEM_QUALITY_COLORS[r.quality]
            row.cells[1]:SetText(r.name)
            row.cells[1]:SetTextColor(c and c.r or 1, c and c.g or 1, c and c.b or 1)
            row.cells[2]:SetText(r.slot)
            row.cells[3]:SetText(string.format("+%.1f", r.gain))
            row.cells[4]:SetText(Coin(r.price))
            row.cells[5]:SetText(string.format("%.1f", r.per))
        end
    end
    frame.foot:ClearAllPoints()
    frame.foot:SetPoint("TOPLEFT", frame.head, "BOTTOMLEFT", 0, -shown * ROW - 8)
    if #rows > 0 then
        frame.foot:SetText((#rows > shown and string.format("The best %d of %d. ", shown, #rows) or "")
            .. "Click one at the auction house to search for it; you buy with the game's own button.")
    else
        frame.foot:SetText(m and ("Nothing in your scan beats what you wear for " .. Coin(cap) .. " or less.") or "")
    end
    frame:SetHeight(30 + frame.cap:GetStringHeight() + 8 + ROW + shown * ROW + 8 + frame.foot:GetStringHeight() + 12)
end

-- /dscore upgrades list, or List under the auction house
function ns.UpgradesList()
    if type(W) ~= "table" then return ns.Print("upgrades: the standard weights did not load.") end
    if not frame then Build() end
    Fill()
    frame:Show()
end

-- A new scan was saved: the list, when open, shows it.
function ns.RefreshUpgrades()
    if frame and frame:IsShown() then Fill() end
end
