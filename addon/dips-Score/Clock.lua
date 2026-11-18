-- dips-Score: the clock anchor.
--
-- Lines are timed with debugprofilestop() (milliseconds, precise, but counted from nothing in
-- particular). WoWCombatLog.txt is timed with your PC's wall clock. An anchor ties the two together:
-- it's the debugprofilestop() reading at the moment time() ticked over to a new second.
--
-- time() only moves once a second, so we watch it every frame and catch the tick: the real tick
-- happened somewhere between the last frame before it and the first frame after, so we take the
-- middle and keep half that gap as the error (about 3 ms at 144 fps). Several ticks are watched
-- and the tightest one is kept.
--
-- Saved as "epoch,wall,ms,err" in the segment's anchors:
--   epoch  time() right after the tick (whole seconds)
--   wall   the same second as local time, "2026-11-16 20:15:03" (the combat log uses local time
--          too, so the analyzer needs no timezone math)
--   ms     milliseconds since the segment's t0 when that second began
--   err    +/- milliseconds
-- So a line at t happened at: wall + (t - ms) / 1000 seconds.
--
-- A segment gets an anchor as it opens and another after every fight, so the analyzer can correct
-- for the two clocks drifting apart over a long run.
local ADDON, ns = ...

local now = debugprofilestop
local time, date, format = time, date, string.format

local TICKS = 4         -- good second boundaries kept per anchor
local MAX_TRIES = 30    -- boundaries watched at most (right after a load screen frames hitch for a while)
local MAX_ERR = 25      -- ms; a tick caught across a longer frame (a load screen hitch) is skipped

local watcher = CreateFrame("Frame")
watcher:Hide()

local lastSec, lastMs, best, ticksLeft, triesLeft, target

local function Finish()
    watcher:Hide()
    if best and target and ns.Segment() == target then
        local anchors = target.anchors
        anchors[#anchors + 1] = format("%d,%s,%.1f,%.1f", best.epoch, date("%Y-%m-%d %H:%M:%S", best.epoch),
            best.ms - target.t0, best.err)
    end
    best, target = nil, nil
end

watcher:SetScript("OnUpdate", function()
    local ms, sec = now(), time()
    if lastSec and sec ~= lastSec then
        if sec == lastSec + 1 then
            local err = (ms - lastMs) / 2
            if err <= MAX_ERR then
                if not best or err < best.err then
                    best = best or {}
                    best.epoch, best.ms, best.err = sec, lastMs + err, err
                end
                ticksLeft = ticksLeft - 1
            end
        end
        triesLeft = triesLeft - 1
        if ticksLeft <= 0 or triesLeft <= 0 then
            lastSec, lastMs = nil, nil
            return Finish()
        end
    end
    lastSec, lastMs = sec, ms
end)

-- Takes an anchor for the open segment (over the next few seconds). Safe to call again while one
-- is being taken: it just keeps going.
function ns.TakeAnchor()
    local seg = ns.Segment()
    if not seg then return end
    if watcher:IsShown() and target == seg then return end
    target, best, ticksLeft, triesLeft = seg, nil, TICKS, MAX_TRIES
    lastSec, lastMs = nil, nil
    watcher:Show()
end

function ns.AnchorPending() return watcher:IsShown() end
