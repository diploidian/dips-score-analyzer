-- projectArthas: where your time goes. Every 5 seconds the time since the last look goes to one state of today, in
-- dipsScoreLog.time (per character). No chat, no names, no places.
--
--   time = {
--       cols = "away,trade,...",                         -- the order of a day's numbers
--       now  = {day = "2026-11-25", quest = 310.2, ...}, -- today, seconds, added to in place
--       days = {"2026-11-24,310,420,...", ...},          -- finished days, whole seconds, the last MAX_DAYS
--   }
--   levels = {"time(),level", ...}                       -- at login when it changed, and at each level
--
-- The first that applies: in combat, where you are (an instance), a fight with an enemy player ("skirmish") or what you were
-- at; on a taxi; away (AFK); dead (what you were at, DEAD seconds of it); away (nothing done for IDLE seconds, outside an
-- instance); a profession at work (gathering, skinning, crafting); an instance; the auction house or the mailbox; a fight with
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
local CRAFT = 60                    -- a cast, with a profession window open
local AT_WORK, SKIN = 30, 15        -- after a profession's own cast: to loot, to wait for a bite; a skinner is back at the hunt sooner
local DEAD = 600                    -- a corpse run longer than this is being away
local SETTLE = 10                   -- after entering the world, where the game may report the whole quest log as changed
local MAX_DAYS, MAX_LEVELS = 60, 100
local COLS = {"away", "trade", "raid", "dungeon", "pvp", "skirmish", "taxi", "craft", "quest", "gather", "hunt", "town", "roam", "turnins"}
local KINDS = {party = "dungeon", scenario = "dungeon", raid = "raid", pvp = "pvp", arena = "pvp"}
local TRADE_FRAMES = {"AuctionHouseFrame", "AuctionFrame", "MailFrame"}
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

local function Level(level)
    local log = ns.Log()
    if not log or type(level) ~= "number" or level < 1 then return end
    log.levels = log.levels or {}
    local was = log.levels[#log.levels]
    if was and tonumber(was:match(",(%d+)$")) == level then return end
    log.levels[#log.levels + 1] = time() .. "," .. level
    while #log.levels > MAX_LEVELS do table.remove(log.levels, 1) end
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
    living = (not trading and t < workUntil and work)
        or (t - castAt < CRAFT and Shown(CRAFT_FRAMES) and "craft")
        or kind
        or (trading and "trade")
        or Lately(t)
        or (Try(IsResting) and "town")
        or "roam"
    return living
end

local function Look()
    local t = GetTime()
    local dt = math.min(t - last, MOST)
    last = t
    local now = dt > 0 and Today()
    if not now then return end
    local state = State(t)
    now[state] = (now[state] or 0) + dt
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
    "QUEST_ACCEPTED", "QUEST_TURNED_IN", "PLAYER_LEVEL_UP"}) do
    pcall(E.RegisterEvent, E, event)
end
pcall(E.RegisterUnitEvent, E, "UNIT_SPELLCAST_SUCCEEDED", "player")
pcall(E.RegisterUnitEvent, E, "UNIT_QUEST_LOG_CHANGED", "player")

local function OnEvent(event, ...)
    local t = GetTime()
    if event == "UNIT_SPELLCAST_SUCCEEDED" then
        done, castAt = t, t
        Work(select(3, ...), t)
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
                    pcall(Start)
                end)
            end
        end
    elseif event == "PLAYER_LEVEL_UP" then
        Level((...))
    elseif event ~= "UNIT_QUEST_LOG_CHANGED" or t - entered > SETTLE then -- quests
        questAt, done = t, t
        if event == "QUEST_TURNED_IN" then
            local now = Today()
            if now then now.turnins = (now.turnins or 0) + 1 end
        end
    end
end
E:SetScript("OnEvent", function(_, event, ...) pcall(OnEvent, event, ...) end)
