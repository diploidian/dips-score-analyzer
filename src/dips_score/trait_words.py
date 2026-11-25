"""What each trait of All traits says about itself (no Qt): the line under its name, how it is worked out, and your own
figures. Plain words, checked against traits.raw(). Guard and Mercy have two figures, so two entries each, by the kind that scores."""
from dataclasses import dataclass

STYLE = " A style: higher isn't better."


@dataclass(frozen=True)
class Words:
    line: str       # under its name, what the figure counts
    how: str        # the hover's first line
    you: str        # its second, after "You: ", filled by profile_view: {v} the figure, {n} the sample, {hits} of it,
                    # {v1} and {v2} Guard's figures, {names} the abilities or the enemy, {extra} what goes with it


NOTE = ("The three ticks on a bar are its tiers, and the framed word is the one you hold. This app chose each bar's "
        "two ends by hand; they don't compare you with other players. Hover a trait to see how it's worked out.")

WORDS: dict[str, Words] = {
    "Thrift": Words("healing on full health, out of all your healing",
                    "Healing past a full health bar, out of all the healing you cast in fights you healed.",
                    "{v} across {n} fights"),
    "Lifeline": Words("fights where everyone lived, out of group fights", "Group fights with no deaths, yours included.",
                      "{hits} of {n} group fights"),
    "Wall": Words("swings that did not land, out of all at you", "Swings at you that missed, or that you dodged, parried or blocked.",
                  "{hits} of {n} swings"),
    "Tempo": Words("your middle wait, where shorter is better",
                   "The middle wait: half of yours are shorter. A wait of 30 minutes or more is a break and is left out.",
                   "{v} over {n} waits"),
    "Swift": Words("wins under 15 s, out of all wins", "Won fights that lasted less than 15 seconds.", "{hits} of {n} wins"),
    "Endure": Words("length of your usual fight", "The middle fight: half of yours are shorter.", "{v} over {n} fights"),
    "Marathon": Words("fights in your longest sitting, 15 days", "The most fights you had without a break of 30 minutes.",
                      "{v} fights in one sitting"),
    "Streak": Words("fights in a row survived, 15 days", "Your longest run of fights without dying.", "{v} in a row, of {n} fights"),
    "Edge": Words("wins after falling under 35% health, out of all wins", "Won fights where your health fell under 35%.", "{hits} of {n} wins"),
    "Brink": Words("wins under 10% health, per 100 wins",
                   "Wins where your health fell under 10%, for every 100 wins.", "{hits} of {n} wins"),
    "Guard %": Words("deaths per 100 fights, and average lowest health (the bar)",
                     "Two figures, and the weaker one sets the bar and the tier. Lowest health is the lowest point you reached "
                     "in each fight, averaged.", "{v1} deaths per 100 fights and {v2} average lowest health, over {n} fights"),
    "Guard n1": Words("deaths per 100 fights (the bar), and average lowest health",
                     "Two figures, and the weaker one sets the bar and the tier. Lowest health is the lowest point you reached "
                     "in each fight, averaged.", "{v1} deaths per 100 fights and {v2} average lowest health, over {n} fights"),
    "Wary": Words("close calls met with a defensive, out of those you could have",
                  "Fights where your health fell under 35% and you used a defensive or had one ready. It's met when you "
                  "used one within 10 seconds of your lowest point.", "{hits} of {n} close calls"),
    "Crowd": Words("wins against three or more, out of wins without help",
                   "Wins alone with three or more enemies over the whole fight, the ones that joined late included. "
                   "Wins in a group count too when you mostly tank.", "{hits} of {n} wins without help"),
    "Duel": Words("fights won, out of those one on one", "Fights alone against a single enemy that ended with it dead.",
                  "{hits} of {n} one on one fights"),
    "Finish": Words("fights that end with every enemy dead, out of all fights", "Every enemy died and you lived.", "{hits} of {n} fights"),
    "Hound": Words("fights won, out of those you lived through",
                   "Won fights, out of those you lived through. Your deaths are left out, and so are fights alone where you did no "
                   "damage, so this is usually higher than Fights won.", "{hits} of {n} fights you lived through"),
    "Boss": Words("boss fights won in 15 days", "Boss fights that ended with the boss dead. Playing more raises it.", "{v} boss fights"),
    "War": Words("fights won, out of those against players", "Fights with an enemy player in them that ended with every enemy dead.",
                 "{hits} of {n} fights against players"),
    "Scourge": Words("the enemy you beat most, out of all you beat", "The enemy you beat most, out of all the enemies you beat. Players are left out.",
                     "{hits} of {n}: {names}"),
    "Blade": Words("weapon swings, out of all your damage", "Auto attacks with your weapon." + STYLE, "{v} of the damage in {n} fights"),
    "Shot": Words("automatic shots, out of all your damage", "Auto Shot and wand Shoot." + STYLE, "{v} of the damage in {n} fights"),
    "Craft": Words("abilities, out of all your damage", "Spells and abilities you cast." + STYLE, "{v} of the damage in {n} fights"),
    "Focus": Words("your biggest ability, out of your ability damage", "Your biggest ability, out of all your ability damage." + STYLE,
                   "{names}, in {n} fights"),
    "Range": Words("abilities with 5% or more of your ability damage",
                   "Abilities you cast that each did 5% or more of your ability damage. Weapon swings, procs and pets are "
                   "left out.", "{names}"),
    "Crit": Words("crits, out of all your hits", "Damaging hits that crit, your pet's left out.", "{hits} of {n} hits"),
    "Proc": Words("procs and items, out of all your damage",
                  "Damage with no cast of yours behind it: procs, items, shields that hit back." + STYLE,
                  "{v} of the damage in {n} fights"),
    "Edgewise": Words("damage done, out of what you could have done",
                      "Your damage, out of that damage plus what unused cooldowns, lost swings and idle time cost you.",
                      "{v} across {n} fights"),
    "Ready": Words("cooldown uses, out of those possible",
                   "Uses of your cooldowns, out of the uses there was time for. Cooldowns of a minute or longer count on "
                   "bosses only.", "{hits} of {n} uses"),
    "Planted": Words("casts not cut short by moving, out of all casts", "Casts in recorded runs that moving did not cancel.",
                     "{hits} of {n} casts"),
    "Primed": Words("pulls with all your usual buffs up, out of all pulls",
                    "A usual buff is one you cast on yourself and had up at 60% of pulls or more.", "{hits} of {n} pulls"),
    "Break": Words("interrupts per 100 group fights", "Enemy casts you interrupted, for every 100 group fights.",
                   "{hits} over {n} group fights"),
    "Lone": Words("fights with no group or help, out of all fights",
                  "Fights with no group where others did damage worth at most 10% of yours and healed at most 10% of what "
                  "you took.", "{hits} of {n} fights"),
    "Bond": Words("fights in a group, out of all fights", "Fights where a groupmate did damage or healing.", "{hits} of {n} fights"),
    "Lead": Words("groupmates who did less damage than you, on average",
                  "The share of groupmates with less damage than you, averaged over your group fights. Anyone who did no "
                  "damage, or healed more than that, is left out. 50% is an even share in a group of any size, though tanks are easier to beat.", "{v} across {n} group fights"),
    "Mercy %": Words("your healing on others, out of the group's",
                     "Your healing on groupmates, out of all the healing your group gave each other.",
                     "{v} across {n} group fights"),
    "Mercy n1": Words("dispels on others per 100 group fights",
                      "Debuffs you removed from groupmates, for every 100 group fights.", "{hits} over {n} group fights"),
    "Benefactor": Words("strangers helped in 15 days",
                        "Players outside your group you buffed, healed or cleansed by casting on them. Each counts once a "
                        "day, and auras don't count. Playing more raises it.", "{v} strangers. Not counted: {extra} for your group"),
    "Lifegiver": Words("revives cast in 15 days",
                       "Every revive you cast. The log doesn't say if it was accepted. Playing more raises it.",
                       "{v} revives, {extra}"),
    "Travel": Words("zones with five fights in 15 days", "Zones where you had at least five fights. Playing more raises it.",
                    "{v} zones"),
    "Menagerie": Words("kinds of enemy beaten in 15 days",
                       "Different enemy names in fights you won, players left out. Playing more raises it.", "{v} kinds"),
}


def words(key: str, kind: str) -> Words:
    return WORDS.get(key) or WORDS[f"{key} {kind}"]
