-- projectArthas: where your time goes. Every 5 seconds the time since the last look goes to one state of today, in
-- dipsScoreLog.time (per character). No chat, no names, no places.
--
--   time = {
--       cols = "away,trade,...",                         -- the order of a day's numbers
--       now  = {day = "2026-11-25", quest = 310.2, ...}, -- today, seconds, added to in place
--       days = {"2026-11-24,310,420,...", ...},          -- finished days, whole seconds, the last MAX_DAYS
--   }
--   levels = {"time(),level", ...}                       -- at login when it changed, and at each level
--   weapons = {"time(),itemID:enchantID", ...}           -- the main hand, the same way; "0:0" for none
--
-- Trade, beside the states in the same day: "auction" seconds with the auction house open, "spent" copper that left your
-- purse while it was open, "mailin" copper that came from auction mails (a sale, a refunded bid), "sales" sale mails taken,
-- "sold" the items in them, "unread" sale mails that did not say how many, "blind" mails whose money could not be read (or the
-- mailbox could not be watched at all). Mail money counts when it reaches your purse. Away time is not auction time.
--
-- The first that applies: in combat, where you are (an instance), a fight with an enemy player ("skirmish") or what you were
-- at; on a taxi; away (AFK); dead (what you were at, DEAD seconds of it); away (nothing done for IDLE seconds, outside an
-- instance); a profession at work (gathering, skinning, crafting; not with the auction house or the mailbox open); an instance; the auction house or the mailbox; a fight with
-- an enemy player lately; quest progress lately; gathering lately; a fight lately; resting; roaming. A new column goes at the
-- end of COLS.
--
-- It writes straight into the saved table and does nothing at logout, where the game answers 0 to everything. In combat it
-- only asks who your target is. Calls are looked for first and run under pcall; a hidden answer counts as "no".
local ADDON, ns = ...
local IsSecret = ns.IsSecret

local TICK = 5
local MOST = 10                     -- of one look: a loading screen or a freeze is not made up for
local IDLE = 180                    -- without moving, casting or fighting, and no auction house or mailbox open
local QUEST, GATHER, HUNT = 300, 180, 90 -- "lately"
local CRAFT = 60                    -- a cast you sent, with a profession window open
local AT_WORK, SKIN = 30, 15        -- after a profession's own cast: to loot, to wait for a bite; a skinner is back at the hunt sooner
local DEAD = 600                    -- a corpse run longer than this is being away
local SETTLE = 10                   -- after entering the world, where the game may report the whole quest log as changed
local MAX_DAYS, MAX_LEVELS, MAX_WEAPONS = 60, 100, 400
local MAIN_HAND = 16
local COLS = {"away", "trade", "raid", "dungeon", "pvp", "skirmish", "taxi", "craft", "quest", "gather", "hunt", "town", "roam", "turnins",
    "auction", "spent", "mailin", "sales", "sold", "unread", "blind"}
local KINDS = {party = "dungeon", scenario = "dungeon", raid = "raid", pvp = "pvp", arena = "pvp"}
local TRADE_FRAMES = {"AuctionHouseFrame", "AuctionFrame", "MailFrame"}
local AUCTION_FRAMES = {"AuctionHouseFrame", "AuctionFrame"}
local MAIL_WAIT = 30                -- seconds a taken mail's money may take to reach the purse
local CRAFT_FRAMES = {"ProfessionsFrame", "TradeSkillFrame", "CraftFrame"}
-- what a profession casts outside its window, by a rank of it (every rank has the same name): its state, its seconds, a trip of it
local ACTIONS = {
    [2575] = {"gather", AT_WORK, true}, [2366] = {"gather", AT_WORK, true}, [7620] = {"gather", AT_WORK, true}, -- mining, herbs, fishing
    [8613] = {"gather", SKIN}, [13262] = {"craft", AT_WORK}, [31252] = {"craft", AT_WORK}, [51005] = {"craft", AT_WORK}, -- skinning, disenchanting, prospecting, milling
}

local last, done = 0, 0             -- GetTime() of the last look, of the last thing you did
local castAt, questAt, gatherAt, huntAt, pvpAt = -1e9, -1e9, -1e9, -1e9, -1e9
local work, workUntil = nil, 0      -- "gather" or "craft", and until when
local entered = 0                   -- GetTime() of entering the world
local inCombat, kind, deadSince
local living = "roam"               -- the last state alive
local midnight = 0                  -- time() of the next one
local actions                       -- name -> its entry of ACTIONS
local money                         -- copper in the purse at the last look
local taken = {}                    -- auction mails whose money was taken and has not arrived: {copper, sale, items, GetTime()}
local auctionOpen = false           -- between the game's AUCTION_HOUSE_SHOW and _CLOSED (another auction UI may hide its frame)
local hooked = false                -- the mail calls could be watched

local function Try(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, v = pcall(fn, ...)
    if not ok or IsSecret(v) then return nil end
    return v
end

local function Shown(names)
    for _, name in ipairs(names) do
        local f = _G[name]
        if type(f) == "table" and Try(f.IsShown, f) then return true end
    end
    return false
end

----------------------------------------------------------------------
-- The saved table
----------------------------------------------------------------------
local function Freeze(now)
    local out = {now.day}
    for _, col in ipairs(COLS) do out[#out + 1] = string.format("%d", (now[col] or 0) + 0.5) end
    return table.concat(out, ",")
end

-- Today's row; at a new day the finished one is frozen. The PC's clock, as in the combat log.
local function Today()
    local log = ns.Log()
    if not log then return nil end
    local t = log.time
    if type(t) ~= "table" then t = {}; log.time = t end
    t.days = t.days or {}
    if not t.now or time() >= midnight then
        local d = date("*t")
        midnight = time({year = d.year, month = d.month, day = d.day + 1, hour = 0})
        local day = date("%Y-%m-%d")
        if t.now and t.now.day ~= day then
            t.days[#t.days + 1] = Freeze(t.now)
            while #t.days > MAX_DAYS do table.remove(t.days, 1) end
            t.now = nil
        end
        t.cols = table.concat(COLS, ",")
        t.now = t.now or {day = day}
    end
    return t.now
end

-- "time(),what" at the end of a list, when it is not what the last one says.
local function Note(list, what, most)
    local was = list[#list]
    if was and was:match(",(.+)$") == what then return list end
    list[#list + 1] = time() .. "," .. what
    while #list > most do table.remove(list, 1) end
    return list
end

local function Level(level)
    local log = ns.Log()
    if not log or type(level) ~= "number" or level < 1 then return end
    log.levels = Note(log.levels or {}, tostring(level), MAX_LEVELS)
end

-- changed: the game says so; else an empty answer may only mean it is not loaded yet.
local function Weapon(changed)
    local log = ns.Log()
    if not log then return end
    local link = Try(GetInventoryItemLink, "player", MAIN_HAND)
    local what
    if type(link) == "string" then
        local id, enchant = link:match("item:(%d+):?(%d*)")
        what = id and id .. ":" .. (enchant ~= "" and enchant or "0")
    elseif changed and Try(GetInventoryItemID, "player", MAIN_HAND) == nil then
        what = "0:0"
    end
    if what then log.weapons = Note(log.weapons or {}, what, MAX_WEAPONS) end
end

----------------------------------------------------------------------
-- One look
----------------------------------------------------------------------
local function Lately(t)
    if t - pvpAt < HUNT then return "skirmish" end
    if t - questAt < QUEST then return "quest" end
    if t - gatherAt < GATHER then return "gather" end
    if t - huntAt < HUNT then return "hunt" end
end

-- Fighting an enemy player or a pet of one (a duel too).
local function Skirmish()
    return (Try(UnitPlayerControlled, "target") or Try(UnitIsPlayer, "target")) and Try(UnitCanAttack, "player", "target")
        and Try(UnitAffectingCombat, "target")
end

local function State(t)
    if inCombat then
        done, huntAt, deadSince = t, t, nil
        if not kind and Skirmish() then pvpAt = t end
        living = kind or (t - pvpAt < HUNT and "skirmish") or (t - questAt < QUEST and "quest") or "hunt"
        return living
    end
    if Try(UnitOnTaxi, "player") then
        done = t
        return "taxi"
    end
    if (Try(GetUnitSpeed, "player") or 0) > 0 then done = t end
    if Try(UnitIsAFK, "player") then return "away" end
    if Try(UnitIsDeadOrGhost, "player") then
        deadSince = deadSince or t
        return t - deadSince <= DEAD and living or "away"
    end
    deadSince = nil
    local trading = Shown(TRADE_FRAMES)
    if not kind and not trading and t - done > IDLE then return "away" end
    living = (not trading and (t < workUntil and work or t - castAt < CRAFT and Shown(CRAFT_FRAMES) and "craft"))
        or kind
        or (trading and "trade")
        or Lately(t)
        or (Try(IsResting) and "town")
        or "roam"
    return living
end

local function AtAuction()
    return auctionOpen or Shown(AUCTION_FRAMES)
end

local function Look()
    local t = GetTime()
    local dt = math.min(t - last, MOST)
    last = t
    local now = dt > 0 and Today()
    if not now then return end
    local state = State(t)
    now[state] = (now[state] or 0) + dt
    if state ~= "away" and AtAuction() then now.auction = (now.auction or 0) + dt end
    if not hooked and Shown({"MailFrame"}) then now.blind = 1 end
end

----------------------------------------------------------------------
-- Trade
----------------------------------------------------------------------
local function Add(now, col, n) now[col] = (now[col] or 0) + n end

-- A mail's subject against one of the game's formats ("Auction successful: %s").
local function Says(subject, format)
    if type(subject) ~= "string" or IsSecret(subject) or type(format) ~= "string" then return false end
    local pattern = format:gsub("%%%d*%$?s", "\1"):gsub("[%%%^%$%(%)%.%[%]%*%+%-%?]", "%%%0"):gsub("\1", ".+")
    return subject:match("^" .. pattern .. "$") ~= nil
end

local function Expire(t)
    for k = #taken, 1, -1 do
        if t - taken[k][4] > MAIL_WAIT then table.remove(taken, k) end
    end
end

-- Hooked after the game's TakeInboxMoney and AutoLootMailItem: an auction mail's money is on its way.
local function Taking(i)
    if type(i) ~= "number" then return end
    local ok, _, _, _, subject, cash = pcall(GetInboxHeaderInfo, i)
    if not ok or IsSecret(cash) or type(cash) ~= "number" then
        local now = Today()
        if now then Add(now, "blind", 1) end
        return
    end
    if cash <= 0 then return end
    local ok2, invoice, _, _, _, _, _, _, _, _, _, items = pcall(GetInboxInvoiceInfo or error, i)
    if not ok2 or IsSecret(invoice) then invoice = nil end
    if IsSecret(items) or type(items) ~= "number" or items < 1 then items = nil end
    local sale = invoice == "seller" or (invoice == nil and Says(subject, _G.AUCTION_SOLD_MAIL_SUBJECT))
    if not (sale or invoice or Says(subject, _G.AUCTION_OUTBID_MAIL_SUBJECT) or Says(subject, _G.AUCTION_REMOVED_MAIL_SUBJECT)) then return end
    Expire(GetTime())
    taken[#taken + 1] = {cash, sale, sale and items, GetTime()}
    while #taken > 50 do table.remove(taken, 1) end
end

-- The purse changed: spent at the auction house, or an auction mail's money arrived.
local function Money()
    local m = Try(GetMoney)
    if type(m) ~= "number" then return end
    local was = money
    money = m
    local now = was and m ~= was and Today()
    if not now then return end
    if m < was then
        if m > 0 and AtAuction() then Add(now, "spent", was - m) end      -- at logout the game answers 0
        return
    end
    Expire(GetTime())
    local function Count(mail)
        Add(now, "mailin", mail[1])
        if mail[2] then
            Add(now, "sales", 1)
            if mail[3] then Add(now, "sold", mail[3]) else Add(now, "unread", 1) end
        end
    end
    for k = 1, #taken do
        if taken[k][1] == m - was then
            Count(table.remove(taken, k))
            return
        end
    end
    local sum = 0                   -- several arrived at once: the oldest ones, adding up to it
    for k = 1, #taken do
        sum = sum + taken[k][1]
        if sum == m - was then
            for _ = 1, k do Count(table.remove(taken, 1)) end
            return
        end
    end
end

local ticker, failed = nil, 0
local function Start()
    if ticker or not (C_Timer and C_Timer.NewTicker) then return end
    last = GetTime()
    ticker = C_Timer.NewTicker(TICK, function()
        if pcall(Look) then
            failed = 0
            return
        end
        failed = failed + 1
        if failed >= 3 then ticker:Cancel() end
    end)
end

----------------------------------------------------------------------
-- Events: they only set a flag or a time
----------------------------------------------------------------------
local function Where()
    local ok, _, what = pcall(GetInstanceInfo)
    kind = ok and not IsSecret(what) and KINDS[what] or nil
end

-- A profession's own cast: one of ACTIONS, or a recipe.
local function Work(spell, t)
    if inCombat or IsSecret(spell) or type(spell) ~= "number" then return end
    if not actions then
        actions = {}
        for id, action in pairs(ACTIONS) do
            local name = Try(C_Spell and C_Spell.GetSpellName, id)
            if type(name) == "string" then actions[name] = action end
        end
    end
    local name = Try(C_Spell and C_Spell.GetSpellName, spell)
    local action = type(name) == "string" and actions[name]
    if action then
        work, workUntil = action[1], t + action[2]
        if action[3] then gatherAt = t end
        return
    end
    local recipe = Try(C_TradeSkillUI and C_TradeSkillUI.GetRecipeInfo, spell)
    if type(recipe) == "table" and not IsSecret(recipe.learned) and recipe.learned == true then
        work, workUntil = "craft", t + AT_WORK
    end
end

local E = CreateFrame("Frame")
for _, event in ipairs({"PLAYER_ENTERING_WORLD", "ZONE_CHANGED_NEW_AREA", "PLAYER_REGEN_DISABLED", "PLAYER_REGEN_ENABLED",
    "QUEST_ACCEPTED", "QUEST_TURNED_IN", "PLAYER_LEVEL_UP", "PLAYER_EQUIPMENT_CHANGED", "PLAYER_STARTED_MOVING", "PLAYER_MONEY",
    "AUCTION_HOUSE_SHOW", "AUCTION_HOUSE_CLOSED"}) do
    pcall(E.RegisterEvent, E, event)
end
pcall(E.RegisterUnitEvent, E, "UNIT_SPELLCAST_SENT", "player")      -- only what you pressed: in a town the game casts one on you every second
pcall(E.RegisterUnitEvent, E, "UNIT_SPELLCAST_SUCCEEDED", "player")
pcall(E.RegisterUnitEvent, E, "UNIT_QUEST_LOG_CHANGED", "player")
for _, name in ipairs({"TakeInboxMoney", "AutoLootMailItem"}) do
    if type(_G[name]) == "function" and pcall(hooksecurefunc, name, function(i) pcall(Taking, i) end) then hooked = true end
end

local function OnEvent(event, ...)
    local t = GetTime()
    if event == "UNIT_SPELLCAST_SENT" then
        done, castAt = t, t
    elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
        Work(select(3, ...), t)
    elseif event == "PLAYER_STARTED_MOVING" then
        done = t
    elseif event == "PLAYER_MONEY" then
        if ticker then Money() end
    elseif event == "AUCTION_HOUSE_SHOW" or event == "AUCTION_HOUSE_CLOSED" then
        auctionOpen = event == "AUCTION_HOUSE_SHOW"
    elseif event == "PLAYER_REGEN_DISABLED" then
        inCombat = true
    elseif event == "PLAYER_REGEN_ENABLED" then
        inCombat, huntAt, done = false, t, t
    elseif event == "PLAYER_ENTERING_WORLD" or event == "ZONE_CHANGED_NEW_AREA" then
        Where()
        if event == "PLAYER_ENTERING_WORLD" then
            last, done, entered = t, t, t
            inCombat = Try(InCombatLockdown) or false
            if C_Timer and C_Timer.After then
                C_Timer.After(3, function()
                    pcall(Level, Try(UnitLevel, "player"))
                    pcall(Weapon)
                    money = Try(GetMoney)
                    pcall(Start)
                end)
            end
        end
    elseif event == "PLAYER_LEVEL_UP" then
        Level((...))
    elseif event == "PLAYER_EQUIPMENT_CHANGED" then
        if (...) == MAIN_HAND and ticker then Weapon(true) end
    elseif event ~= "UNIT_QUEST_LOG_CHANGED" or t - entered > SETTLE then -- quests
        questAt, done = t, t
        if event == "QUEST_TURNED_IN" then
            local now = Today()
            if now then now.turnins = (now.turnins or 0) + 1 end
        end
    end
end
E:SetScript("OnEvent", function(_, event, ...) pcall(OnEvent, event, ...) end)
