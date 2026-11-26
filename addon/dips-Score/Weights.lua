-- projectArthas: the standard weights, the same tables as the app's live/gearworth.py, for the in-game list (Upgrades.lua).
-- A stat's worth in points, one point being what 1 attack power (melee, ranged, tank) or 1 spell power (caster, healer)
-- adds; an item's rating is ten to a percent on this client. What your own fights measured stays in the app.
--
--   tables       role -> {stat key: points}         gearworth.TABLES
--   class        role -> class -> {stat key: points} gearworth.CLASS, over the role's table
--   byClass      class -> role, before any fight says gearworth.BY_CLASS (any other class: melee)
--   weaponSlots  role -> the slots a weapon's damage per second counts in   gearworth.WEAPON_SLOTS
--
-- Plain values only, as a saved file holds: tests/test_weights.py reads this file as data and checks it equals the app's.
dipsScoreWeights = {
    tables = {
        melee = {ITEM_MOD_STRENGTH_SHORT = 2, ITEM_MOD_AGILITY_SHORT = 1, ITEM_MOD_ATTACK_POWER_SHORT = 1,
            ITEM_MOD_CRIT_RATING_SHORT = 2, ITEM_MOD_HIT_RATING_SHORT = 1.5, ITEM_MOD_HASTE_RATING_SHORT = 1,
            ITEM_MOD_DAMAGE_PER_SECOND_SHORT = 14},
        ranged = {ITEM_MOD_AGILITY_SHORT = 2.4, ITEM_MOD_RANGED_ATTACK_POWER_SHORT = 1, ITEM_MOD_ATTACK_POWER_SHORT = 1,
            ITEM_MOD_INTELLECT_SHORT = 0.2, ITEM_MOD_CRIT_RATING_SHORT = 2, ITEM_MOD_HIT_RATING_SHORT = 1.5,
            ITEM_MOD_DAMAGE_PER_SECOND_SHORT = 14},
        caster = {ITEM_MOD_SPELL_POWER_SHORT = 1, ITEM_MOD_SPELL_DAMAGE_DONE_SHORT = 1, ITEM_MOD_INTELLECT_SHORT = 0.4,
            ITEM_MOD_SPIRIT_SHORT = 0.1, ITEM_MOD_MANA_REGENERATION_SHORT = 0.8, ITEM_MOD_CRIT_SPELL_RATING_SHORT = 1,
            ITEM_MOD_HIT_SPELL_RATING_SHORT = 1.2, ITEM_MOD_DAMAGE_PER_SECOND_SHORT = 3},
        healer = {ITEM_MOD_SPELL_HEALING_DONE_SHORT = 1, ITEM_MOD_SPELL_POWER_SHORT = 1, ITEM_MOD_INTELLECT_SHORT = 0.6,
            ITEM_MOD_SPIRIT_SHORT = 0.4, ITEM_MOD_MANA_REGENERATION_SHORT = 1.5, ITEM_MOD_CRIT_SPELL_RATING_SHORT = 0.8,
            ITEM_MOD_STAMINA_SHORT = 0.1},
        tank = {ITEM_MOD_STAMINA_SHORT = 1.5, ITEM_MOD_AGILITY_SHORT = 1.5, ITEM_MOD_STRENGTH_SHORT = 1.5,
            ITEM_MOD_ATTACK_POWER_SHORT = 1, RESISTANCE0_NAME = 0.1, ITEM_MOD_DEFENSE_SKILL_RATING_SHORT = 1.5,
            ITEM_MOD_DODGE_RATING_SHORT = 2.5, ITEM_MOD_PARRY_RATING_SHORT = 2, ITEM_MOD_BLOCK_RATING_SHORT = 1,
            ITEM_MOD_BLOCK_VALUE_SHORT = 0.5, ITEM_MOD_HIT_RATING_SHORT = 1, ITEM_MOD_CRIT_RATING_SHORT = 1,
            ITEM_MOD_DAMAGE_PER_SECOND_SHORT = 7},
    },
    class = {
        melee = {ROGUE = {ITEM_MOD_STRENGTH_SHORT = 1, ITEM_MOD_AGILITY_SHORT = 1.7}},
    },
    byClass = {HUNTER = "ranged", MAGE = "caster", PRIEST = "caster", WARLOCK = "caster"},
    weaponSlots = {melee = {16, 17}, tank = {16, 17}, ranged = {18}, caster = {18}, healer = {}},
}
