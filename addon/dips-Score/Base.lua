-- projectArthas: the small helpers the other files share. The add-on needs no other add-on.
local ADDON, ns = ...

-- Newer clients hide some values from add-ons ("secret" values): they can be shown, not compared.
function ns.IsSecret(v)
    return issecretvalue ~= nil and issecretvalue(v) or false
end

function ns.CharKey()
    return (UnitName("player") or "Unknown") .. " - " .. (GetRealmName() or "")
end

function ns.DeepCopy(v)
    if type(v) ~= "table" then return v end
    local out = {}
    for k, x in pairs(v) do out[k] = ns.DeepCopy(x) end
    return out
end

function ns.Print(msg)
    DEFAULT_CHAT_FRAME:AddMessage("|cff66ccffprojectArthas|r " .. msg)
end

----------------------------------------------------------------------
-- Settings (dipsScoreDB)
----------------------------------------------------------------------
local function FillDefaults(t, defaults)
    for k, v in pairs(defaults) do
        if type(v) == "table" then
            if type(t[k]) ~= "table" then t[k] = {} end
            FillDefaults(t[k], v)
        elseif t[k] == nil then
            t[k] = v
        end
    end
end

-- Returns the settings table with `defaults` filled in.
function ns.LoadSettings(defaults)
    local db = dipsScoreDB
    if type(db) ~= "table" then db = {} end
    -- Saved while this ran on dips-Core: settings were kept per profile. Take this character's.
    if type(db.profiles) == "table" then
        local name = type(db.chars) == "table" and db.chars[ns.CharKey()] or "Default"
        db = db.profiles[name] or db.profiles.Default
        if type(db) ~= "table" then db = {} end
    end
    FillDefaults(db, defaults)
    dipsScoreDB = db
    return db
end

----------------------------------------------------------------------
-- Look: a flat dark fill with a 1px edge (the frame needs BackdropTemplate)
----------------------------------------------------------------------
local WHITE = "Interface\\Buttons\\WHITE8x8"
local FLAT = {bgFile = WHITE, edgeFile = WHITE, edgeSize = 1}

function ns.Backdrop(frame, r, g, b, a)
    frame:SetBackdrop(FLAT)
    frame:SetBackdropColor(r, g, b, a)
    frame:SetBackdropBorderColor(1, 1, 1, 0.12)
end

function ns.Text(parent, font)
    local fs = parent:CreateFontString(nil, "OVERLAY", font or "GameFontHighlightSmall")
    fs:SetJustifyH("LEFT")
    return fs
end
