-- projectArthas: the settings panel (Esc > Options > AddOns) and the /dscore command
local ADDON, ns = ...

local db
local panel, category

local function Status()
    local run = ns.CurrentRun()
    if run then
        local seg = ns.Segment()
        ns.Print(string.format("recording %s - segment %d, %d lines, %d anchors%s.", run.zone or "?",
            #run.segments, ns.LineCount(), seg and #seg.anchors or 0,
            ns.AnchorPending() and " (taking one now)" or ""))
    else
        ns.Print("not recording.")
    end
    ns.Print(string.format("%d saved runs (keeps %d).", #ns.Log().runs, db.maxRuns))
end

local function Mark(note)
    if not ns.IsRecording() then return ns.Print("not recording.") end
    ns.Write("X", note ~= "" and note or "mark")
    ns.Print("marked.")
end

----------------------------------------------------------------------
-- The options, as data: the panel builds one row per entry
----------------------------------------------------------------------
local OPTIONS = {
    {type = "section", label = "Recording"},
    {type = "description", text = "A run starts when you enter one of these and ends when you leave. "
        .. "The game only writes it to disk on /reload or logout - that's when the analyzer can read it. "
        .. "The analyzer also needs the game's combat log (/combatlog) with Advanced Combat Logging; "
        .. "the combat log toggle below turns them on at login and when a run starts (or says how, if the game won't let it)."},
    {type = "toggle", key = "record.party", label = "Dungeons", onChange = ns.UpdateRecording},
    {type = "toggle", key = "record.raid", label = "Raids", onChange = ns.UpdateRecording},
    {type = "toggle", key = "record.scenario", label = "Scenarios and delves", onChange = ns.UpdateRecording},
    {type = "toggle", key = "record.world", label = "Everywhere else", onChange = ns.UpdateRecording},
    {type = "toggle", key = "announce", label = "Say in chat when a run starts and ends"},
    {type = "toggle", key = "fightLine", label = "Print a line in chat after each fight (presses, clicks, refused casts)"},
    {type = "toggle", key = "combatLog", label = "Turn on the combat log (with advanced logging) when you log in"},

    {type = "header", label = "Record button"},
    {type = "description", text = "Click it to start or stop recording, right-click it for more, drag it "
        .. "to move it. Stopping a dungeon run by hand keeps it stopped until you leave that dungeon."},
    {type = "toggle", key = "button.shown", label = "Show the record button",
        onChange = function() ns.SetButtonShown(db.button.shown) end},
    {type = "toggle", key = "button.locked", label = "Lock it in place"},
    {type = "button", label = "Reset its position", func = function() ns.ResetButtonPosition() end},

    {type = "header", label = "Storage"},
    {type = "range", key = "maxRuns", label = "Runs kept", min = 1, max = 50, step = 1, fmt = "%d",
        desc = "Older runs are dropped at the next load."},
    {type = "range", key = "maxLines", label = "Lines per segment", min = 10000, max = 200000, step = 10000,
        fmt = "%d", desc = "A safety cap. A busy 30-minute dungeon is roughly 15,000 lines."},
    {type = "button", label = "Clear saved runs", func = function() ns.ClearRuns() end},

    {type = "section", label = "Commands"},
    {type = "description", text = "/dscore status | start | stop | mark [note] | watch | button | clear | char\n"
        .. "watch prints each press with whether it was a key or a click - use it to check this client "
        .. "tells them apart. char saves a snapshot of your spells, gear and talents and says what this client returned."},
}

-- "record.party" -> db.record, "party"
local function Slot(key)
    local t = db
    for part in key:gmatch("([^.]+)%.") do t = t[part] end
    return t, key:match("([^.]+)$")
end

----------------------------------------------------------------------
-- The panel: stock templates, built on first show
----------------------------------------------------------------------
local toggles = {}

local function Build()
    local y = -16
    local function Place(region, h, x)
        region:SetPoint("TOPLEFT", x or 16, y)
        y = y - h
    end
    for i, o in ipairs(OPTIONS) do
        local name = "dipsScoreOpt" .. i
        if o.type == "section" or o.type == "header" then
            local fs = panel:CreateFontString(nil, "ARTWORK", "GameFontNormalLarge")
            fs:SetText(o.label)
            if i > 1 then y = y - 10 end
            Place(fs, 26)
        elseif o.type == "description" then
            local fs = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlightSmall")
            fs:SetWidth(560)
            fs:SetJustifyH("LEFT")
            fs:SetText(o.text)
            Place(fs, fs:GetStringHeight() + 10)
        elseif o.type == "toggle" then
            local cb = CreateFrame("CheckButton", name, panel, "UICheckButtonTemplate")
            -- the label's field name differs between client versions
            local label = cb.Text or cb.text or _G[name .. "Text"]
            if label then label:SetText(o.label) end
            cb:SetScript("OnClick", function(self)
                local t, k = Slot(o.key)
                t[k] = self:GetChecked() and true or false
                if o.onChange then o.onChange() end
            end)
            cb.refresh = function()
                local t, k = Slot(o.key)
                cb:SetChecked(t[k])
            end
            toggles[#toggles + 1] = cb
            Place(cb, 28)
        elseif o.type == "range" then
            local s = CreateFrame("Slider", name, panel, "OptionsSliderTemplate")
            local text = s.Text or _G[name .. "Text"]
            local low, high = s.Low or _G[name .. "Low"], s.High or _G[name .. "High"]
            if low then low:SetText(string.format(o.fmt, o.min)) end
            if high then high:SetText(string.format(o.fmt, o.max)) end
            s:SetWidth(240)
            s:SetMinMaxValues(o.min, o.max)
            s:SetValueStep(o.step)
            if s.SetObeyStepOnDrag then s:SetObeyStepOnDrag(true) end
            local function Label(v)
                if text then text:SetText(o.label .. ": " .. string.format(o.fmt, v)) end
            end
            local t, k = Slot(o.key)
            s:SetValue(t[k])
            Label(t[k])
            s:SetScript("OnValueChanged", function(self, v)
                v = math.floor(v / o.step + 0.5) * o.step
                local t, k = Slot(o.key)
                if t[k] == v then return end
                t[k] = v
                Label(v)
                if o.onChange then o.onChange() end
            end)
            local desc = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlightSmall")
            desc:SetPoint("LEFT", s, "RIGHT", 16, 0)
            desc:SetText(o.desc or "")
            y = y - 16 -- room for the label above the slider
            Place(s, 40, 24)
        elseif o.type == "button" then
            local b = CreateFrame("Button", name, panel, "UIPanelButtonTemplate")
            b:SetSize(180, 22)
            b:SetText(o.label)
            b:SetScript("OnClick", function() o.func() end)
            Place(b, 30, 20)
        end
    end
    panel.built = true
end

function ns.OpenSettings()
    if category and Settings and Settings.OpenToCategory then
        Settings.OpenToCategory(category:GetID())
    elseif panel and panel.name and InterfaceOptionsFrame_OpenToCategory then
        InterfaceOptionsFrame_OpenToCategory(panel)
    else
        ns.Print("no settings window on this client - use /dscore status | start | stop | mark [note] | "
            .. "watch | button | clear | char.")
    end
end

ns.OnLoad(function()
    db = ns.db
    panel = CreateFrame("Frame", "dipsScoreOptions")
    panel:Hide()
    panel:SetScript("OnShow", function()
        if not panel.built then Build() end
        -- the menu and /dscore button change these too
        for _, cb in ipairs(toggles) do cb.refresh() end
    end)
    if Settings and Settings.RegisterCanvasLayoutCategory then
        category = Settings.RegisterCanvasLayoutCategory(panel, "projectArthas")
        Settings.RegisterAddOnCategory(category)
    elseif InterfaceOptions_AddCategory then
        panel.name = "projectArthas"
        InterfaceOptions_AddCategory(panel)
    end
end)

----------------------------------------------------------------------
-- /dscore
----------------------------------------------------------------------
SLASH_DIPSSCORE1 = "/dscore"
SlashCmdList.DIPSSCORE = function(msg)
    local cmd, rest = (msg or ""):match("^(%S*)%s*(.-)$")
    if cmd == "status" then
        Status()
    elseif cmd == "start" then
        ns.StartManual()
    elseif cmd == "stop" then
        ns.StopManual()
    elseif cmd == "mark" then
        Mark(rest)
    elseif cmd == "watch" then
        ns.ToggleWatch()
    elseif cmd == "button" then
        ns.SetButtonShown(not db.button.shown)
    elseif cmd == "clear" then
        ns.ClearRuns()
    elseif cmd == "char" then
        ns.PrintSnapshot()
    else
        ns.OpenSettings()
    end
end
