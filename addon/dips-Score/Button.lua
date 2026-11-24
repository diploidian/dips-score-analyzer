-- projectArthas: the record button - a small pill that shows whether a run is recording and for how
-- long. Left-click starts or stops recording, right-click opens a menu, drag it to move it
-- (unless it's locked).
local ADDON, ns = ...

local db
local button, menu
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

-- The right-click menu: one frame, built once, with a row per item. Items take text, func,
-- title (dim, not clickable), disabled, checked (a function) or separator.
local ROW, SEP = 20, 7

local function BuildMenu()
    menu = CreateFrame("Frame", "dipsScoreMenu", UIParent, "BackdropTemplate")
    menu:SetFrameStrata("DIALOG")
    menu:SetClampedToScreen(true)
    menu:Hide()
    ns.Backdrop(menu, 0.04, 0.04, 0.06, 0.95)
    menu.rows = {}
    tinsert(UISpecialFrames, "dipsScoreMenu") -- Escape closes it
    -- A click anywhere else closes it. pcall: this client may not have the event.
    pcall(menu.RegisterEvent, menu, "GLOBAL_MOUSE_DOWN")
    menu:SetScript("OnEvent", function(self)
        if self:IsShown() and not self:IsMouseOver() and not button:IsMouseOver() then self:Hide() end
    end)
end

local function MenuRow(i)
    if menu.rows[i] then return menu.rows[i] end
    local row = CreateFrame("Button", nil, menu)
    local hl = row:CreateTexture(nil, "HIGHLIGHT")
    hl:SetAllPoints()
    hl:SetColorTexture(1, 1, 1, 0.08)
    row.check = row:CreateTexture(nil, "ARTWORK")
    row.check:SetSize(16, 16)
    row.check:SetPoint("LEFT", 2, 0)
    row.check:SetTexture("Interface\\Buttons\\UI-CheckBox-Check")
    row.label = ns.Text(row)
    row.label:SetPoint("LEFT", 20, 0)
    row.line = row:CreateTexture(nil, "ARTWORK")
    row.line:SetHeight(1)
    row.line:SetPoint("LEFT", 4, 0)
    row.line:SetPoint("RIGHT", -4, 0)
    row.line:SetColorTexture(1, 1, 1, 0.12)
    row:SetScript("OnClick", function(self)
        menu:Hide()
        self.item.func()
    end)
    menu.rows[i] = row
    return row
end

local function ShowMenu(items, anchor)
    if not menu then BuildMenu() end
    local y, width = -4, 120
    for i, item in ipairs(items) do
        local row = MenuRow(i)
        local h = item.separator and SEP or ROW
        row.item = item
        row:ClearAllPoints()
        row:SetPoint("TOPLEFT", 4, y)
        row:SetPoint("TOPRIGHT", -4, y)
        row:SetHeight(h)
        row.line:SetShown(item.separator == true)
        row.check:SetShown(item.checked ~= nil and item.checked() == true)
        row.label:SetText(item.text or "")
        local dim = item.title or item.disabled
        row.label:SetTextColor(dim and 0.55 or 1, dim and 0.55 or 1, dim and 0.6 or 1)
        row:SetEnabled(item.func ~= nil and not dim) -- a disabled Button shows no highlight either
        row:Show()
        width = math.max(width, row.label:GetStringWidth() + 32)
        y = y - h
    end
    for i = #items + 1, #menu.rows do menu.rows[i]:Hide() end
    menu:SetSize(width + 8, 4 - y)
    menu:ClearAllPoints()
    menu:SetPoint("TOPLEFT", anchor, "BOTTOMLEFT", 0, -4)
    menu:Show()
end

local function OpenMenu(self)
    GameTooltip:Hide()
    local recording = ns.CurrentRun() ~= nil
    ShowMenu({
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
        {text = "Settings", func = function() ns.OpenSettings() end},
        {text = "Hide button", func = function()
            ns.SetButtonShown(false)
            ns.Print("button hidden - /dscore button brings it back.")
        end},
    }, self)
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
    ns.Backdrop(button, 0.04, 0.04, 0.06, 0.85)

    button.dot = button:CreateTexture(nil, "ARTWORK")
    button.dot:SetSize(8, 8)
    button.dot:SetPoint("LEFT", 9, 0)
    button.label = ns.Text(button)
    button.label:SetPoint("LEFT", button.dot, "RIGHT", 7, 0)

    button:SetScript("OnClick", function(self, mouse)
        if mouse == "RightButton" then
            if menu and menu:IsShown() then return menu:Hide() end
            return OpenMenu(self)
        end
        if menu then menu:Hide() end
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
    db.button.point = ns.DeepCopy(ns.DEFAULTS.button.point)
    if button then RestorePosition() end
end

ns.OnLoad(function()
    db = ns.db
    if db.button.shown then Build() end
    Refresh()
end)

ns.OnStateChanged(Refresh)
