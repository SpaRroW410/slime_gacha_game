"""The in-game booklet: plain-language descriptions of every attribute and system, with what raises and lowers
them. Built from the live constants so the numbers never go stale."""
from . import config, elements, emotions, specialization, sparring
from .abilities import get_ability


def _pct(x: float) -> str:
    return f"{x * 100:+.0f}%"


def _el(key: str) -> str:
    e = elements.get(key)
    return f"{e.emoji}{e.name}"


def _elements_section() -> dict:
    c = config
    basics = [e for e in elements.ELEMENTS if e.tier == 1]
    rec = []
    for pair, res in elements.RECIPES.items():
        a, b = sorted(pair)
        r = elements.get(res)
        rec.append(dict(name=f"{_el(a)} + {_el(b)} = {_el(res)}",
                        text=f"Tier {r.tier} element. Needs effective mastery {c.SPELL_TIER_MASTERY[r.tier]} to cast; made of "
                             + ", ".join(sorted(r.components)) + "."))
    return dict(title="Elements and spells", icon="🔮", blurb="Four basic elements, their wheel and what they fuse into.", items=[
        dict(name="Basic elements", text=", ".join(f"{e.emoji}{e.name}" for e in basics) + ". Elemental mastery unlocks at "
             f"{c.MASTERY_MIN_STARS} stars for any class (mages get an extra element slot and study faster). Study an element in the "
             "Academy's Library to attune to it and raise its mastery."),
        dict(name="The wheel", text=" · ".join(f"{_el(a)} beats {_el(d)}" for a, d in elements.BEATS.items()) +
             f". Winning matchups deal x{c.ELEMENT_ADVANTAGE} damage, the reverse x{c.ELEMENT_DISADVANTAGE}. Fused elements count "
             "through their components."),
        dict(name="Mastery", text=f"Each effective mastery level adds {c.MASTERY_SPELL_BONUS:.0%} spell power. Casting an element builds "
             "its mastery. Attuned or native elements are immune to a terrain's hazard of that element."),
        dict(name="Spells", text=f"Learn spells in the Library (tier 1-3, costs rise with tier). A slime keeps {c.MAX_SPELLS} spells (more "
             "with Library levels). The Restricted Section (tier 3) opens at Library level 3."),
        dict(name="Spell lab", text="Fuse two learned spells of different elements into a brand-new spell. It costs essence, takes hours, can "
             "fizzle and backfire (never fatal), and discovered spells join the Library for everyone."),
    ] + rec)


def _specialization_section() -> dict:
    c = config
    items = [
        dict(name="How it works", text=f"Cross-training builds new classes: a swordslime that trains hard in magic can become a Battlemage. "
             f"Reach style level {c.SPEC_MIN_STYLE} in a discipline outside the class (Sparring in the Academy) and level {c.SPEC_MIN_LEVEL}, "
             f"then specialize for " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in c.SPEC_COST.items()) +
             f". It is permanent, shifts stats (the new skill lends {c.SPEC_STAT_RATIO:.0%} of its stat), grants a signature ability and "
             "doubles affinity in both styles. Specialize from the slime card's Fight tab or the Academy."),
    ]
    disc = {d.key: d for d in sparring.DISCIPLINES}
    for (a, b), key in specialization.BY_PAIR.items():
        sp = specialization.SPECS[key]
        items.append(dict(name=f"{sp.emoji} {sp.name}", text=f"{disc[a].style}-type classes + {disc[b].style} training. Signature: "
                          f"{get_ability(sp.ability).name}. {sp.description}"))
    for (a, b), key in specialization.BY_CLASS.items():
        sp = specialization.SPECS[key]
        items.append(dict(name=f"{sp.emoji} {sp.name}", text=f"{a.capitalize()} + {disc[b].style} training. Signature: "
                          f"{get_ability(sp.ability).name}. {sp.description}"))
    return dict(title="Specialization (hybrid classes)", icon="🧬", blurb="Which cross-training makes which hybrid.", items=items)


def _class_skills_section() -> dict:
    from . import attributes
    from .archetypes import ARCHETYPES
    items = []
    for cls, keys in attributes.RARITY_SKILLS.items():
        arch = ARCHETYPES.get(cls)
        rar = "; ".join(f"{r}: {get_ability(k).name} - {get_ability(k).description}" for r, k in zip(config.RARITIES[1:], keys))
        evo = attributes.EVOLUTION_SKILLS[cls]
        items.append(dict(name=f"{arch.emoji} {arch.name}",
                          text=f"By rarity - {rar}. First evolution: {evo[0].name} - {evo[0].description} "
                               f"The second evolution raises it to {evo[1].name}."))
    return dict(title="Class skills", icon="🌟", blurb="One class skill per rarity step, and one signature skill when a slime "
                "evolves (stars give attributes instead, see Rarity, stars and ascension).", items=items)


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
        _elements_section(),
        _specialization_section(),
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
            dict(name="Stars", text="1-5. Each star adds one class attribute, boosted by rarity (" + ", ".join(f"{k} x{v:g}" for k, v in c.STAR_ATTR_RARITY_BOOST.items()) +
                 "). A slime may ascend to 2/3/4/5 stars only once it has reached a level that depends on its rarity: " +
                 "; ".join(f"{k} " + "/".join(map(str, v)) for k, v in c.STAR_LEVELS.items()) + ". Stone costs are multiplied by " +
                 ", ".join(f"x{v:g} ({k})" for k, v in c.STAR_STONE_MULT.items()) + ". Rising in rarity resets the stars to 1 and locks the star attributes until they are re-earned. Ascend with ascension stones: " +
                 ", ".join(f"{k - 1}>{k}: {v}" for k, v in c.STAR_ASCEND_STONES.items()) +
                 f" (common equivalents; {c.STONE_MERGE} stones merge into one of the next rarity)."),
            dict(name="XP needed per level", text="Doubles with each rarity: x" +
                 ", x".join(f"{v:g} ({k})" for k, v in c.XP_RARITY_MULT.items()) + ". Stars do not change it. Above level 50 stats grow at 60% per level, and the Pit pays more XP the higher your party's level."),
            dict(name="Merging", text=f"A donor's collected XP and {c.MERGE_STAT_SHARE:.0%} of its stats are absorbed; the share shrinks as an "
                                      f"attribute grows (down to {c.MERGE_SHARE_FLOOR:.0%}). The donor is consumed."),
            dict(name="Evolution", text="At the level cap a slime may evolve (costs essence) and raises its cap.")]),
        _class_skills_section(),
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
            dict(name="Take command", text="Hollow Descent, Gloop Pit and skirmishes can be fought by hand: every slime acts on its own turn "
                                           "(pick the ability, then the target). Switch to auto, for one turn or the rest of the fight, whenever you like. "
                                           "Rift, Quarry and sparring are always automatic."),
            dict(name="Scouting", text="Reach 100% of every targeted floor within the hour budget or the whole party is lost."),
            dict(name="Quarrels away from home", text="While either slime is in a dungeon, hunting or studying, you cannot mediate (no talk, no snack): the quarrel "
                                                       "keeps growing and is out of your hands until they return."),
            dict(name="Commander's gifts", text="Purple gel is the one way to reach a party inside the Hollow Descent or fighting a skirmish: "
                                                f"{c.GIFT_MORALE_COST} gel raises the whole party's morale by {c.GIFT_MORALE_GAIN}, {c.GIFT_PEACE_COST} gel settles quarrels inside the party, "
                                                f"and potions are bought and drunk at once for {'/'.join(map(str, c.GIFT_POTION_PURPLE))} gel (grades 1-5). "
                                                "In a manual battle the effect applies to the live fight."),
            dict(name="Capstones and proficiency", text=f"A legendary 5-star that never specialized earns two class capstones for good. Each slime has a class "
                                                         f"proficiency (0-100): the first capstone needs {c.PROF_ONE_CAPSTONE:.0f}, the second {c.PROF_BOTH_CAPSTONES:.0f}. "
                                                         f"Fighting, sparring and (for magic classes) studying raise it; after {c.PROF_IDLE_DAYS} idle days it fades by "
                                                         f"{c.PROF_DECAY:g} a day (never below {c.PROF_FLOOR:.0f}), and the second capstone goes first."),
            dict(name="Hybrid capstones", text=f"A specialized slime that reaches legendary 5-star gets one hybrid capstone, at no more than "
                                               f"{c.HYBRID_CAPSTONE_MAX:.0%} of a pure capstone's strength (30% to 60% depending on its second proficiency, which grows "
                                               f"from its hybrid skills and training in its secondary discipline). A slime that was pure first keeps its pure "
                                               f"capstones only while it keeps practising its original discipline; neglect it and they lock, the second one first."),
            dict(name="Vice Keeper", text=f"People > Keeper: appoint a trusted slime ({c.VICE_MIN_STARS} stars or more) as Vice Keeper. In its own group (same party and "
                                          "same dungeon or task) it can mediate quarrels and feed and tend slimes even where you cannot reach, and it settles "
                                          "quarrels by itself (at home it leaves serious ones to you). It never merges or destroys, and cannot be merged or "
                                          "destroyed while in office."),
            dict(name="Potion slots", text="A slime can have 2 potions active at once at 1 star, up to 6 at 5 stars; wait for one to wear off before adding another."),
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
