"""The in-game booklet: plain-language descriptions of every attribute and system, with what raises and lowers
them. Built from the live constants so the numbers never go stale."""
from . import attributes, config, emotions, keeper, potions, relationships


def _pct(x: float) -> str:
    return f"{x * 100:+.0f}%"


def build() -> list:
    c = config
    need_rows = [
        ("Energy", "Falls by 2.5 per hour awake. Sleeping (or the Rest Area) refills it. At zero a slime takes damage "
                   f"({c.STARVE_HP_LOSS:.0%} of max HP per hour together with hunger)."),
        ("Food", f"Falls by 2 per hour. One food item restores {c.FOOD_NUTRITION}. A slime at zero food starves and can die."),
        ("Safety", "Drops when a slime is wounded or witnesses death; recovers when healthy. Low safety breeds fear."),
        ("Belonging", "Falls by 1.5 per hour (more for chatty slimes); rises with petting, friends, parties and companionship. "
                      "Low belonging breeds loneliness."),
        ("Esteem", "Rises with victories, levelling, praise and being useful; falls with defeats. High esteem breeds pride."),
    ]
    sections = [
        dict(title="Needs and mood", icon="🫧", blurb="The five needs decide how a slime feels, whether it asks for care, "
             "and how well it fights.", items=[dict(name=n, text=t) for n, t in need_rows] + [
            dict(name="Mood", text=f"Mood is the weighted average of the needs that currently matter (the first unmet tier and "
                                   f"below). It scales battle power from x{c.MOOD_POWER_MIN} (miserable) to x{c.MOOD_POWER_MAX} (ecstatic).")]),
        dict(title="Morale", icon="🎖️", blurb="'Fight readiness' of a slime, 0-100.", items=[
            dict(name="What it does", text=f"Scales battle power from x{c.MORALE_POWER_MIN} to x{c.MORALE_POWER_MAX}. Below {c.MORALE_BROKEN} "
                                           f"a slime is broken and may freeze in battle ({c.MORALE_FREEZE_CHANCE:.0%} per turn)."),
            dict(name="Raises it", text=f"Victories ({c.MORALE_WIN:+d}, bosses {c.MORALE_BOSS_WIN:+d} more), rest, a good mood, Barracks levels, "
                                        "reconciliation, ascending, repairing its own gear, trusting a bonded weapon, Keeper abilities."),
            dict(name="Lowers it", text=f"Defeats ({c.MORALE_LOSS:+d}), a friend's death ({c.MORALE_FRIEND_DEATH:+d}), other deaths "
                                        f"({c.MORALE_ALLY_DEATH:+d}), quarrels and brawls, being knocked out, and merges or chamber sacrifices "
                                        "(worse while sacrifice stress is high)."),
            dict(name="Sacrifice stress", text="Every merge, chamber destruction or ego fusion adds stress; it decays by 1 per day and "
                                               "amplifies the morale cost of the next sacrifice.")]),
        dict(title="Feelings (emotions)", icon="🎭", blurb="Thirteen passing feelings, 0-100 each. They shift stats and combat "
             "attributes in proportion to their strength (total change per stat is capped at +-35%).",
             items=[dict(name=f"{e.emoji} {e.name}",
                         text=("Battle effect at 100: " + (", ".join(
                             [f"{k.upper()[:3]} {_pct(v)}" for k, v in e.stats.items()] +
                             [f"{k.replace('_', ' ')} {_pct(v)}" for k, v in e.mods.items()]) or "none") + ". "
                               f"Rises with: {emotions.TRIGGERS[e.key][0]} {emotions.TRIGGERS[e.key][1]}")) for e in emotions.EMOTIONS.values()]
             + [dict(name="Traits", text="Grumpy slimes anger easily, timid ones fear more, brave ones less, kind ones feel more "
                                         "affection, proud ones more pride, chatty ones get lonely faster.")]),
        dict(title="Stats and combat", icon="⚔️", blurb="What the numbers mean.", items=[
            dict(name="HP", text="Health. At zero a slime is knocked out (Pit, Rift, Quarry) or dies (Hollow Descent)."),
            dict(name="ATK", text="Strength: scales physical moves. Anger raises it, fear and sadness lower it."),
            dict(name="DEF", text="Armor: every hit is reduced by half of it. Anger lowers it, calm raises it."),
            dict(name="MAG", text="Magic: scales spells and healing. Wonder and dread raise it."),
            dict(name="SPD", text="Speed: who acts first. Sadness and loneliness lower it, anxiety and joy raise it."),
            dict(name="Stamina", text=f"Every action costs stamina ({c.STAMINA_COSTS['attack']} + {c.STAMINA_COSTS['power']} x the move's power). "
                                      f"A slime without enough acts winded (x{c.STAMINA_WINDED_MULT} damage). It refills between rounds, "
                                      f"{c.STAMINA_HOUR_REGEN:.0%} per hour, x{c.STAMINA_SLEEP_MULT} asleep or resting. Stamina potions raise the maximum and the recovery."),
            dict(name="Crit rate / damage", text=f"Base {c.CRIT_CHANCE:.0%} chance for x{c.CRIT_MULT} damage; raised by relics, star attributes, fury and some feelings."),
            dict(name="Other attributes", text="Evasion, guard (less damage taken), regeneration, spell power, resist and lifesteal come from "
                                               "stars, relics, potions and feelings."),
            dict(name="Terrain", text="Every battlefield boosts or dampens elements and may hurt both sides each round (attuned or native "
                                      "elements are immune).")]),
        dict(title="Rarity, stars and ascension", icon="✨", blurb="How a slime grows beyond levels.", items=[
            dict(name="Rarity", text="Common, uncommon, rare, epic, legendary. Each step multiplies stats and unlocks one class skill. "
                                     "Ascend with white gel: " + ", ".join(f"{k} {v}" for k, v in c.RARITY_ASCEND_GEL.items()) + "."),
            dict(name="Stars", text="1-5. Each star adds one class attribute. Ascend with ascension stones: " +
                 ", ".join(f"{k - 1}>{k}: {v}" for k, v in c.STAR_ASCEND_STONES.items()) +
                 f" (common equivalents; {c.STONE_MERGE} stones merge into one of the next rarity)."),
            dict(name="Merging", text=f"A donor's collected XP and {c.MERGE_STAT_SHARE:.0%} of its stats are absorbed; the share shrinks as an "
                                      f"attribute grows (down to {c.MERGE_SHARE_FLOOR:.0%}). The donor is consumed."),
            dict(name="Evolution", text="At the level cap a slime may evolve (costs essence) and raises its cap.")]),
        dict(title="Bonds, family and the Keeper", icon="💞", blurb="Relationships between slimes, and your own progress.", items=[
            dict(name="Ties", text="Friends (bond 25+), best friends (45+), rivals (sour bond and quarrels), mentors (8+ levels ahead) and "
                                   "couples (deep bond, compatibility, affection). Reviewed once a day."),
            dict(name="Children", text=f"A couple together {c.BUD_MIN_DAYS}+ days can have a child (rest {c.BUD_COOLDOWN_DAYS} days between). "
                                       "Traits, class and rarity come from both parents."),
            dict(name="Compatibility", text="Traits, class chemistry, shared elements, friendship and bond decide how well two slimes work "
                                            "together; the party average becomes a +-10% synergy bonus."),
            dict(name="The Keeper", text="You level up by playing; each level gives a skill point for the four skill branches and unlocks "
                                         "daily abilities.")]),
        dict(title="Dungeons and death", icon="🕳️", blurb="Where death is possible.", items=[
            dict(name="Hollow Descent", text="Permadeath. Floors in order; you may leave only after a boss floor. Every slime must have "
                                             "cleared the floors above."),
            dict(name="Gloop Pit, Wayfarer's Rift, Starfall Quarry", text="Nobody dies. A knocked-out slime loses morale (and XP in the Pit) and its relics are battered."),
            dict(name="Scouting", text="Reach 100% of every targeted floor within the hour budget or the whole party is lost."),
            dict(name="No care inside", text="You cannot feed, pet, talk to or give potions to a slime that is inside a dungeon. "
                                              "Slimes' autonomy still helps them before they leave.")]),
        dict(title="Time", icon="⏳", blurb="Two ways time can pass.", items=[
            dict(name="Turn-based", text="Time passes when you act or press the wait buttons. Every activity costs game hours."),
            dict(name="Live (wall clock)", text=f"Time passes by itself. At home the clock runs at {c.LIVE_LOBBY_RATE:g} game hour per real hour "
                                                f"(study, hunts and brewing take real time); while any party is in a dungeon it runs "
                                                f"{c.LIVE_DUNGEON_RATE:g}x faster. Speed presets multiply both. Offline progress is capped at "
                                                f"{c.LIVE_CATCHUP_MAX_HOURS} game hours."),
            dict(name="Clearing a floor", text="Takes longer deeper down, shorter if the party is stronger than the floor and if it has been "
                                               f"scouted (up to {c.CLEAR_KNOWLEDGE_CUT:.0%} faster). Bigger parties are a little slower.")]),
        dict(title="Autonomy", icon="🤖", blurb="What slimes do without asking.", items=[
            dict(name="The 66% rule", text="With autonomy on, slimes may use up to 66% of a stock (potions, relics, gear, scrap) by themselves: "
                                           "tired slimes drink stamina potions, hurt ones vigor, they mend and equip gear, prepare for trips "
                                           "and brew potions the colony is short of. The rest is yours.")]),
    ]
    return sections
