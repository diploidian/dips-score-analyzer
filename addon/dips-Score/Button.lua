-- dips-Score: the record button - a small pill that shows whether a run is recording and for how
-- long. Left-click starts or stops recording, right-click opens a menu, drag it to move it
-- (unless it's locked).
local ADDON, ns = ...
local D = dips
local W = D.Widgets

local db
local button
local REC = {0.95, 0.25, 0.25}
local IDLE = {0.45, 0.45, 0.5}

local function Clock(seconds)
    seconds = math.max(0, math.floor(seconds))
    local h, m, s = math.floor(seconds / 3600), math.floor(seconds / 60) % 60, seconds % 60
    if h > 0 then return string.format("%d:%02d:%02d", h, m, s) end
    return string.format("%d:%02d", m, s)
end

----------------------------------------------------------------------
-- Look
----------------------------------------------------------------------
local function Refresh()
    if not button then return end
    local run = ns.CurrentRun()
    if run then
        button.dot:SetColorTexture(REC[1], REC[2], REC[3])
        button.label:SetText("REC " .. Clock(time() - run.started))
        button:SetBackdropBorderColor(REC[1], REC[2], REC[3], 0.6)
    else
        button.dot:SetColorTexture(IDLE[1], IDLE[2], IDLE[3])
        button.dot:SetAlpha(1)
        button.label:SetText("Record")
        button:SetBackdropBorderColor(1, 1, 1, button:IsMouseOver() and 0.35 or 0.12)
    end
    button:SetWidth(math.max(78, button.label:GetStringWidth() + 32))
end
ns.RefreshButton = Refresh

-- Ticks once a second while recording (the timer), and pulses the dot.
local elapsed, pulse = 0, 0
local function OnUpdate(self, dt)
    if not ns.CurrentRun() then return end
    pulse = (pulse + dt) % 1.6
    self.dot:SetAlpha(0.45 + 0.55 * math.abs(math.cos(pulse / 1.6 * math.pi)))
    elapsed = elapsed + dt
    if elapsed >= 1 then
        elapsed = 0
        Refresh()
    end
end

----------------------------------------------------------------------
-- Tooltip and menu
----------------------------------------------------------------------
local function ShowTip(self)
    GameTooltip:SetOwner(self, "ANCHOR_BOTTOM")
    local run = ns.CurrentRun()
    if run then
        GameTooltip:SetText("Recording " .. (run.zone or "?"), 1, 1, 1)
        local seg = ns.Segment()
        GameTooltip:AddLine(string.format("%s - %d lines this segment, %d anchors", Clock(time() - run.started),
            ns.LineCount(), seg and #seg.anchors or 0), 0.8, 0.8, 0.85)
        if ns.IsManual() then GameTooltip:AddLine("Started by hand: runs until you stop it.", 0.6, 0.6, 0.65) end
        GameTooltip:AddLine("Click to stop.", 0.6, 0.6, 0.65)
    else
        GameTooltip:SetText("Not recording", 1, 1, 1)
        GameTooltip:AddLine("Click to start recording here.", 0.6, 0.6, 0.65)
    end
    GameTooltip:AddLine("Right-click for more." .. (db.button.locked and "" or " Drag to move."), 0.6, 0.6, 0.65)
    GameTooltip:AddLine("The game saves recordings on /reload or logout.", 0.6, 0.6, 0.65, true)
    GameTooltip:Show()
end

local function OpenMenu(self)
    GameTooltip:Hide()
    local recording = ns.CurrentRun() ~= nil
    D:OpenMenu({
        {text = "Score", title = true},
        {text = recording and "Stop recording" or "Start recording", func = ns.ToggleRecording},
        {text = "Mark this moment", disabled = not recording, func = function()
            ns.Write("X", "mark")
            ns.Print("marked.")
        end},
        {text = "Save now (reload)", func = ReloadUI},
        {separator = true},
        {text = "Lock in place", checked = function() return db.button.locked end,
            func = function() db.button.locked = not db.button.locked end},
        {text = "Settings", func = function() D:Open("score") end},
        {text = "Hide button", func = function()
            ns.SetButtonShown(false)
            ns.Print("button hidden - /dips score button brings it back.")
        end},
    }, {anchor = self, point = "TOPLEFT", relPoint = "BOTTOMLEFT", x = 0, y = -4, owner = self})
end

----------------------------------------------------------------------
-- Building and placing
----------------------------------------------------------------------
local function SavePosition()
    local point, _, relPoint, x, y = button:GetPoint(1)
    db.button.point = {point, relPoint, math.floor(x + 0.5), math.floor(y + 0.5)}
end

local function RestorePosition()
    local p = db.button.point
    button:ClearAllPoints()
    button:SetPoint(p[1] or "TOP", UIParent, p[2] or "TOP", p[3] or 0, p[4] or -120)
end

local function Build()
    button = CreateFrame("Button", "dipsScoreButton", UIParent, "BackdropTemplate")
    button:SetSize(78, 22)
    button:SetFrameStrata("MEDIUM")
    button:SetClampedToScreen(true)
    button:SetMovable(true)
    button:RegisterForClicks("LeftButtonUp", "RightButtonUp")
    button:RegisterForDrag("LeftButton")
    W.Backdrop(button, 0.04, 0.04, 0.06, 0.85)

    button.dot = button:CreateTexture(nil, "ARTWORK")
    button.dot:SetSize(8, 8)
    button.dot:SetPoint("LEFT", 9, 0)
    button.label = W.Text(button)
    button.label:SetPoint("LEFT", button.dot, "RIGHT", 7, 0)

    button:SetScript("OnClick", function(self, mouse)
        if mouse == "RightButton" then
            if D:MenuOwner() == self then return D:CloseMenu() end
            return OpenMenu(self)
        end
        ns.ToggleRecording()
        if self:IsMouseOver() then ShowTip(self) end
    end)
    button:SetScript("OnDragStart", function(self)
        if not db.button.locked then
            GameTooltip:Hide()
            self:StartMoving()
        end
    end)
    button:SetScript("OnDragStop", function(self)
        self:StopMovingOrSizing()
        SavePosition()
    end)
    button:SetScript("OnEnter", function(self)
        ShowTip(self)
        Refresh()
    end)
    button:SetScript("OnLeave", function()
        GameTooltip:Hide()
        Refresh()
    end)
    button:SetScript("OnUpdate", OnUpdate)

    RestorePosition()
end

function ns.SetButtonShown(shown)
    db.button.shown = shown and true or false
    if shown and not button then Build() end
    if button then
        button:SetShown(shown)
        Refresh()
    end
end

function ns.ResetButtonPosition()
    db.button.point = D.DeepCopy(ns.DEFAULTS.button.point)
    if button then RestorePosition() end
end

ns.OnLoad(function()
    db = ns.db
    if db.button.shown then Build() end
    Refresh()
end)

ns.OnStateChanged(Refresh)
