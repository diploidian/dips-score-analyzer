-- dips-Score: the log - flat text lines in dipsScoreLog (saved per character).
--
-- Plain strings, not little tables: a table per event would cost ~10x the memory and make the
-- game's save on /reload or logout slow; strings save as one quoted line each.
--
-- dipsScoreLog = {
--     version = 1,
--     active = <run id while a run is open, else nil>,
--     runs = {
--         {
--             id = "1731790000-Name",     -- start time + character
--             char = "Name - Realm",
--             zone = "The Stonevault", instanceID = 2652, kind = "party", difficulty = 8,
--             started = <time()>, ended = <time() or nil>,
--             segments = {                -- one per load of the UI (a /reload starts a new one)
--                 {
--                     t0 = <debugprofilestop() at the segment's start>,
--                     anchors = {"epoch,wall,ms,err", ...},   -- see Clock.lua
--                     lines = {"t,CODE,a,b,...", ...},
--                     full = true/nil,                         -- hit maxLines
--                 },
--             },
--         },
--     },
-- }
--
-- Every line is "t,CODE,fields...": t is whole milliseconds since the segment's t0. Fields hold
-- only numbers, IDs and GUIDs (commas taken out); "?" is a value the game kept hidden, "" none.
--
--   A,slot,type,id,src        action button pressed (UseAction). type/id from GetActionInfo
--                             ("spell", 12345). src: K key binding, C mouse click, ? unknown
--   KD,bar,button / KU,...    key binding down / up on an action button (bar 0 = main bar).
--                             The gap between them is how long the key was held.
--   M,1 / M,0                 started / stopped moving
--   R,1 / R,0                 entered / left combat
--   CS,spellID                cast sent (the server was asked)
--   CB,spellID / CK,spellID   cast began / succeeded
--   CF,spellID / CI,spellID   cast failed / interrupted
--   CC,spellID / CE,spellID   channel began / ended
--   T,guid                    target changed ("" = no target)
--   D                         you died
--   E,1,encounterID / E,0,encounterID,success    boss pull / boss end (success 1/0)
--   MP,1,mapID / MP,0         keystone started / completed
--   P,guid,name,class,role    a group member (see Intent.lua): at segment start and on changes
--   X,note                    marker (manual /dscore mark, segment notes)
local ADDON, ns = ...
local IsSecret = ns.IsSecret

local now = debugprofilestop
local floor = math.floor
local tostring, type = tostring, type

ns.VERSION = 1

local log          -- dipsScoreLog
local seg          -- the segment being written, or nil when not recording
local lines, count, maxLines = nil, 0, 0

-- One field: hidden values become "?", nil "", commas are taken out of text.
local function Field(v)
    if v == nil then return "" end
    if IsSecret(v) then return "?" end
    if type(v) == "boolean" then return v and "1" or "0" end
    if type(v) == "string" then return (v:gsub(",", ";")) end
    return tostring(v)
end
ns.Field = Field

-- Appends a line; returns its index (for Rewrite) or nil if not recording.
-- Up to five fields without building a table.
function ns.Write(code, a, b, c, d, e)
    if not seg then return end
    if count >= maxLines then
        if not seg.full then
            seg.full = true
            ns.Print("this segment is full; recording stops until the next /reload.")
        end
        return
    end
    local line = floor(now() - seg.t0) .. "," .. code
    if a ~= nil then line = line .. "," .. Field(a) end
    if b ~= nil then line = line .. "," .. Field(b) end
    if c ~= nil then line = line .. "," .. Field(c) end
    if d ~= nil then line = line .. "," .. Field(d) end
    if e ~= nil then line = line .. "," .. Field(e) end
    count = count + 1
    lines[count] = line
    return count
end

-- Replaces a line already written (used to fill in an action's source once it's known).
function ns.Rewrite(index, line)
    if seg and index and index <= count then lines[index] = line end
end

function ns.IsRecording() return seg ~= nil end
function ns.Segment() return seg end
function ns.LineCount() return count end

----------------------------------------------------------------------
-- Segments (called by Runs.lua)
----------------------------------------------------------------------
function ns.OpenSegment(run)
    seg = {t0 = now(), anchors = {}, lines = {}}
    run.segments[#run.segments + 1] = seg
    lines, count = seg.lines, 0
    maxLines = ns.db.maxLines
    return seg
end

function ns.CloseSegment()
    seg, lines, count = nil, nil, 0
end

function ns.Log() return log end

----------------------------------------------------------------------
-- Loading: start the saved table, drop the oldest runs past maxRuns
----------------------------------------------------------------------
ns.OnLoad(function()
    if type(dipsScoreLog) ~= "table" or dipsScoreLog.version ~= ns.VERSION then
        dipsScoreLog = {version = ns.VERSION, runs = {}}
    end
    log = dipsScoreLog
    log.runs = log.runs or {}
    local extra = #log.runs - ns.db.maxRuns
    if extra > 0 then
        for _ = 1, extra do table.remove(log.runs, 1) end
    end
end)

function ns.ClearLog()
    ns.CloseSegment()
    wipe(log.runs)
    log.active = nil
end
