"""The in-game booklet: plain-language descriptions of every attribute and system, with what raises and lowers
them. Built from the live constants so the numbers never go stale."""
from . import bestiary, config, elements, emotions, specialization, sparring
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
        ("Energy", "Falls by 2.5 per hour awake. Sleeping (22 per hour) or the Rest Area (26 to 64 per hour by level) refills it. At zero a slime takes damage "
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
                                   f"below). It scales battle power from x{c.MOOD_POWER_MIN} (miserable) to x{c.MOOD_POWER_MAX} (ecstatic)."),
            dict(name="Hospital ward and Rest Area", text=f"On a slime's card: Rest Area (greyed out when full), Hospital (greyed out when its beds are full, or the slime is not hurt) and Call back (greyed out for slimes in the Descent, scouting or a monster wave). Hospital patients heal {int(c.WARD_NO_DOCTOR_BONUS * 100)}% faster than in the Rest Area, or {int(c.WARD_DOCTOR_BONUS * 100)}% faster with a doctor on duty, and go home once healed. Beds: {', '.join(map(str, c.HOSPITAL_BEDS))} by Hospital level."),
            dict(name="Merging a nuisance", text=f"Merging or destroying a slime that keeps brawling (it has brawled {c.NUISANCE_BRAWLS} times or is brawling now) or that most of the colony dislikes changes nobody's morale and adds no sacrifice stress. Being weak is no reason: a weak but liked slime is still mourned."),
            dict(name="Refusing orders", text=f"A slime can refuse a post or an expedition (the Descent, Pit, Rift, Quarry, hunts, scouting, rescues): when its energy is under {c.REFUSE_ENERGY}%, when it is badly hurt (under {int(c.REFUSE_HP['job'] * 100)}% HP for a post, {int(c.REFUSE_HP['dungeon'] * 100)}% for an expedition), in a bleak mood, or in a rage. Pickers show who refuses and why. Merging and sacrifice never ask. Town > Buildings has a 'Wake everybody' button that leaves slimes under {c.REFUSE_ENERGY}% energy asleep; a tired one wakes grumpy."),
            dict(name="Faces", text="Every slime shows its mood on its face: from a wide grin (ecstatic) to a tearful frown (miserable), eyes shut when asleep. A strong feeling (50 or more) takes over the face: angry brows, wide-eyed fear, a smug smirk, blushing affection, a calm smile and so on.")]),
        dict(title="Minds", icon="💭", blurb="Slimes remember, want things and ask for them.", items=[
            dict(name="Memories", text="Each slime remembers who ate its snack, who tended it, who fought beside it and who fell. Memories fade over a few weeks. Grudges make quarrels likelier and become the stated reason; thanks make them rarer."),
            dict(name="How quarrels end", text=f"Most spats mend on their own (kind slimes let go fastest, grumpy and proud ones hold out). Once a day a slime with a guilty conscience may apologise, and a friend of both may talk them round. An unsettled quarrel grows, and at its worst comes to blows: after a brawl both keep apart for {c.CONFLICT_BRAWL_COOL} hours. A feud brawls at most {c.CONFLICT_MAX_BRAWLS} times, then they stop speaking: a cold war of {c.COLD_WAR_HOURS // 24} days with no more fights but no growing closer either."),
            dict(name="Goals", text="Every few days a slime picks a goal: get stronger, beat a rival, spend time with a friend, be left alone, or never go back into the dungeons after a friend fell. Idle slimes at home act on it and say so in the journal."),
            dict(name="Requests", text="A slime may ask for a rest day, to join a friend's party, to be moved away from someone it holds a grudge against, or for a post that fits its class. Grant or decline from the slime's card or the Requests box. An unanswered request lapses after three days."),
            dict(name="Trust", text="Granting raises a slime's trust in you (+6), declining lowers it (-4, or -8 for a rest day, which also costs sanity). Trusting slimes put up with more: they refuse in a bleak mood later, and above 80 they go into the dungeons even when they would rather not."),
            dict(name="Drift", text="Experience rewrites traits: six knock-outs make a slime timid, 25 victories proud, 15 acts of healing kind. The new trait replaces its second one."),
        ]),
        dict(title="Sanity", icon="🧠", blurb="How much a slime can take before it breaks.", items=[
            dict(name="The reserve", text="Common 60, uncommon 70, rare 80, epic 90, legendary 100. Rarer slimes also lose less from each blow (x1.3 for a common down to x0.7 for a legendary)."),
            dict(name="What wears it down", text="A friend or partner dying, any death in the colony a little, being knocked out, losing a battle, brawls and quarrels, and hours spent miserable (needs very low)."),
            dict(name="What builds it back", text="Sleep and the Rest Area (more with a better Barracks), a Hospital bed, idling at home in a good mood, winning fights, the Keeper's Soothe, and one talk a day. More talks or pets the same day help less and less."),
            dict(name="Why it matters", text="Sanity caps the mood: at full sanity there is no cap, at zero the best a slime can feel is grumpy, however well it is fed. Mood drives combat power. Under 20% of its reserve a slime refuses dungeons, under 10% it refuses work."),
        ]),
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
                 ", ".join(f"x{v:g} ({k})" for k, v in c.STAR_STONE_MULT.items()) + ". A slime may rise in rarity only at level 100 and 5 stars. Rising resets the stars to 1, but star attributes already unlocked are kept and hit harder at the new rarity; every star above the one that unlocked an attribute adds 10% to it. Ascend with ascension stones: " +
                 ", ".join(f"{k - 1}>{k}: {v}" for k, v in c.STAR_ASCEND_STONES.items()) +
                 f" (common equivalents; {c.STONE_MERGE} stones merge into one of the next rarity)."),
            dict(name="XP needed per level", text="Doubles with each rarity: x" +
                 ", x".join(f"{v:g} ({k})" for k, v in c.XP_RARITY_MULT.items()) + ". Stars do not change it. The Pit, hunts and the Hollow Descent all pay by the XP a level costs (the Descent multiplies its floor XP by 1, 1.33, 2, 3.2 or 5.3 for common to legendary, so rarer slimes keep pace; stars never change XP). The Pit pays by the XP a level costs: a common needs about 3.5 won runs per level, +50% per rarity step, and deeper depths pay more. Above level 50 stats grow at 60% per level, and the Pit pays more XP the higher your party's level."),
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
            dict(name="Hollow Descent", text="Permadeath. Floors in order; you may leave for free only after a boss floor (an emergency Retreat is the costed exception). Every slime must have "
                                             "cleared the floors above."),
            dict(name="Gloop Pit, Wayfarer's Rift, Starfall Quarry", text="Nobody dies. A knocked-out slime loses morale (never XP) and its relics are battered; in the Pit it also drops its gear. All three farming dungeons now and then (about 5% per foe) hand out a little extra gel, food, essence or scrap. The Pit (XP) is run by a full party; the Rift (relics) and the Quarry (ascension stones) take any 1-5 slimes. Each has its own sub-tab in Dungeons."),
            dict(name="Lures", text="A lure costs 1 purple gel per run. In the Wayfarer's Rift it multiplies the odds of rarer relics; in the Gloop Pit it draws richer prey: x1.5 XP and x3 chance of gear. If the purple gel runs out in a Pit session the remaining runs go without a lure."),
            dict(name="Take command", text="Hollow Descent, Gloop Pit and wave simulations can be fought by hand: every slime acts on its own turn "
                                           "(pick the ability, then the target). Switch to auto, for one turn or the rest of the fight, whenever you like. "
                                           "Rift, Quarry and sparring are always automatic."),
            dict(name="Scouting", text="Reach 100% of every targeted floor within the hour budget or the whole party is lost."),
            dict(name="Quarrels away from home", text="Slimes only quarrel when they share a place: both at home, or away together in the same party. A quarrel waits (it does not "
                                                       "grow) while one of them is away, and you cannot mediate it (no talk, no snack) until they are together again."),
            dict(name="Commander's gifts", text="Purple gel is the one way to reach a party inside the Hollow Descent or in a wave simulation: "
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
            dict(name="Party leaders", text=f"Every party has a leader: the one you set, else its highest-level member. A confident leader adds up to {c.LEADER_POWER:.0%} to the party's "
                                            "synergy, and while the party is away (in a dungeon, on a hunt) the leader settles quarrels between members."),
            dict(name="Vice Keeper hunts and challenges", text=f"The Vice Keeper can organise a hunt: it forms up to {c.VICE_HUNT_MAX_PARTIES} full parties from free, rested slimes, joins and leads the first, "
                                                              "and acts for every party in that hunt. The parties disband when the hunt ends. Any 3-star slime can challenge the Vice Keeper "
                                                              "for the post (a proud, stronger slime may ask by itself); you approve or reject, and an approved challenge is settled in a friendly duel."),
            dict(name="Day plans for posts", text="Every post has a Day plan (in its building's tab): eight 3-hour shifts of the day, each work, forage or sleep, plus up to three 'if' rules checked at the start of every shift (the first that fits wins), e.g. 'if nobody is hurt: forage', 'if the pantry holds 10 days of food or more: sleep', 'if my energy is under 30%: sleep'. A sleep shift restores energy, and the worker goes back to the post afterwards. A blacksmith or brewer can forage twice, sleep, then craft."),
            dict(name="Formations: front and back rows", text=f"Every slime stands in the front or the back row of a fight (set it on the party card or the slime's Orders; 'auto' puts casters and archers at the back). Melee single-target blows can only reach the front row while someone stands there, unless the attacker uses arrows, spells, area attacks or backstabs. Whoever stands in the back row takes x{c.ROW_BACK_GUARD:g} damage, and a melee fighter in the back row hits for only x{c.ROW_BACK_MELEE:g}. Monsters line up too: casters, supports and hunters stand at the back. The manual arena only lets you pick targets that can be reached."),
            dict(name="Reports and hauls arrive with the party", text="When a party leaves for a dungeon session (Pit, Rift, Quarry, Descent floor, wave simulation, sparring) the fight is already settled, but its report and the resources it earned only arrive when the party is back: the report opens by itself and the haul is added to your stores then. A session ends early, and the party comes home earlier, if the whole party is knocked out."),
            dict(name="Session length", text=f"A farming session (Gloop Pit, Wayfarer's Rift, Starfall Quarry) never lasts more than {c.SESSION_MAX_HOURS} game hours, camping to heal included: at most {c.GRIND_MAX_RUNS} Pit runs or {c.ADV_MAX_RUNS} Rift/Quarry runs of 2 hours each. The time is shown before you start, and the party comes home early if camping uses up the day. Hospital patients show as 'hospital' (with their healing bonus) rather than 'resting'."),
            dict(name="Turn-based time and sessions", text="In turn-based mode a dungeon floor, a spar, a drill or a wave simulation no longer fast-forwards the colony: the party is shown as away with the hours still to go, and time moves only when you press +1h / +4h / +1 day. In live mode the same hours pass with the clock. Dismissing a slime from a work post mid-shift loses that shift: nothing is cooked, forged or brewed."),
            dict(name="Party training", text="The Party Training Yard (Academy > Training) is a fourth yard for a whole party: pick a party and everyone trains for themselves in their own field. Every member gains class proficiency and every pair grows closer, which raises the party's synergy. One flat drill cost for the whole party (1 white gel for the basic drill). Each level holds one more party; upgrades cost more than the single yards. Sparring against another party is separate (the Party Arena)."),
            dict(name="Facilities and places", text="Every drilling yard (Blade Yard, Archery Range, Mana Pool) and every sparring arena (Sword, Archery, Spell) is its own building with its own upgrade in Town > Buildings. A yard trains two slimes at once per level; an arena holds one duel (two slimes) per level. The Party Arena, where two whole parties spar as teams, holds one team match per level and costs far more to upgrade. When a facility is full you must wait or upgrade it; each panel in the Academy lists who is in it and how long is left."),
            dict(name="Training facility", text=f"Academy > Training facility: solo drills in the Blade Yard, Archery Range or Mana Pool raise a slime's class proficiency "
                                                f"(base +{c.PROF_DRILL:g}, less near mastery, more with the Training Grounds). Tiers unlock with the Training Grounds: "
                                                + "; ".join(f"{t[0]} (level {t[1]}, {t[2]}h, x{t[4]:g})" for t in c.DRILL_TIERS) + ". No stars are needed, so a slime that has just risen in rarity "
                                                "and is back to one star can still drill (it just cannot study new elements until it has three stars again). Mages, Medics and Necromancers are always pulled at 3 stars or more, and a rarity ascension keeps their earned elemental mastery (it simply cannot grow until the stars catch up)."),
            dict(name="Rarity shapes", text="A slime's silhouette shows its rarity inside a round ring: common is a plain dome, uncommon grows round ears (green ring), rare is a "
                                             "droplet with a pointed tip (blue ring), epic wears a crown (purple ring), legendary a golden crown and halo (glowing gold ring)."),
            dict(name="Camping and reinforcements", text="Camping in the Hollow Descent is limited per floor: about as many hours as the floor number, stretched by how well the floor is scouted (floor 3 unscouted: 3 hours). Ambushes are always possible, and become rarer while another party closes in from below. Two parties standing on the same floor can fight it together as one force. A 5-star mage attuned to two elements can instead call a party from home straight to the floor for purple gel (1, plus 1 per 5 floors); the called party does not need to have cleared the floors above (a party arriving on its own does)."),
            dict(name="Appointments", text="Non-combat posts live in their own buildings (no wages). Training Grounds: three trainers, one per discipline (sword, archery, magic), each 2 stars or more - they speed up proficiency and fighting-style gains for drills and sparring in their discipline (+15%, more with their level and the building). Library: a librarian hurries students along and gives attuned slimes mastery. Armory: a blacksmith mends gear for free and, slowly (every 4 shifts), forges a weapon or a relic if the materials are there. Alchemy Lab: a brewer brews potions from the herbs on hand. Kitchen: a chef cooks the recipe you pick into the pantry (porridge, stew, pie, feast as the chef levels up); hungry slimes eat from it first, and the Kitchen tab shows how many are hungry. Hospital: a medic doctor heals every injured slime at home every hour; the tab counts the injured and wounded. Appoint from each building's own screen; places = building level (trainers: one each). Work runs in 3-hour shifts; a finished shift earns a small bonus. Each trade has its own level and a natural talent (+25%). A working slime is not free for parties, hunts, drills or merging until dismissed; switching is free. A chef, blacksmith, brewer or doctor with nothing to do goes foraging for a shift and can be called back at once. Workers leave when too tired."),
            dict(name="Weaknesses and resistances", text="Every monster has an element (it is weak to what beats it and resists what it beats: water > fire > wind > earth > water), and many families are weak to or resist several more. Weakness x1.5, resistance x0.7 (never beyond x0.5 / x2): " + "; ".join(f"{fam}: weak to {', '.join(w) or 'nothing'}, resists {', '.join(r) or 'nothing'}" for fam, (w, r) in sorted(bestiary.FAMILY_TRAITS.items())) + ". Compound elements count through their components. A fully scouted floor lists what its foes are weak to and resist."),
            dict(name="Elemental floors", text="Every sixth floor from floor 3 that is not a boss floor (3, 9, 21, 27, 33, 39) is an elemental floor: its ground favours one basic element - that element's spells hit 25% harder and the element that beats it 20% softer, for both sides - and the floor's own creatures are favoured in its waves. Scouting reveals the element; bring spells of it (or avoid the opposing one)."),
            dict(name="Floor modifiers", text="Many floors of the Hollow Descent (never a boss floor) lie under a modifier that changes the whole fight, using the battle's own statuses: Poison Fog (everyone starts poisoned), Darkness (everyone is harder to hit), Thin Air (everyone slower), Brittle Ground (less armor for everyone), Bloodlust (foes hit harder, the party crits more) and Sacred Spring (the party mends each round). A floor scouted to 40% reveals its modifier; the fight log always shows it."),
            dict(name="Wave simulation", text="Dungeons > Wave simulation: a full party at home fights 1-5 waves of monsters as a drill. You set the minimum and maximum monster level (1-50). Nobody can die and there is no loot. The XP is fixed by the monsters and their level (deeper monsters pay more; no luck, no rarity factor) and is split between the members. It also trains class (battle) proficiency and builds teamwork (bonds). Each wave takes 2 hours, a lost wave ends the simulation, and you can take command of every turn."),
            dict(name="Scouting", text="Dungeons > Scouting: send one to five slimes (no party needed) to learn floors. They must reach 100% of every floor within the hour budget; leave the budget empty for the safe budget the estimate recommends. Floors they finish stay fully known even if they run out of time on the last one. The floor above the first floor scouted must be scouted already or cleared in the Descent (by anyone in the colony, not each scout), so even a level-1 slime can scout onward over known floors."),
            dict(name="Rescue parties", text="Scouts that run out of budget are no longer lost on the spot: they are stranded on the floor they reached, and the Colony shows a timer (24 hours). One to five slimes can be sent to rescue them. Floors that are already scouted are a known road: rescuers only need to have walked the unscouted floors on the way, and each scouted floor costs a quarter hour instead of an hour. The trip takes 4 hours plus the floors to cross, costs food, can be ambushed (deaths are permanent) and succeeds more often the stronger and better-informed the rescuers are. A failed attempt leaves the scouts waiting if time remains; if the deadline passes they are lost, as before. Several parties can be in the Descent, a rescue or other expeditions at the same time, each with its own timer in live mode."),
            dict(name="Retreat", text="Mid-segment there is one costed way out: a Retreat. It costs purple gel (2, plus 1 per 5 floors deep), 12 morale per slime and drains the party's stamina, and the flight can be ambushed (35% base, higher deeper, lower on well-scouted floors) - a hit can be fatal, and deaths are permanent. Floors already cleared stay cleared for each slime, but to go back down the party must enter again from a checkpoint. At a checkpoint the exit is free."),
            dict(name="Wayside stops", text="On floors 3, 8, 13, 18 ... a wayside stop waits between fights. The party can rest there once (3 hours, +50% HP, no ambush) and buy one of each supply with white gel: Healing Salve (+35% HP), Trail Ration (+5 food), Ward Charm (+15% defense next fight) and Whetstone (+15% attack next fight). Prices rise with depth."),
            dict(name="Spell mutation", text="A fused (tier 2 or 3) spell changes form as its caster's mastery of the spell's element grows. Stage 1 (✦) comes one mastery level above the level needed to cast it, stage 2 (✦✦) three levels above: tier 2 spells at mastery 4 and 6, tier 3 at 6 and 8. Each form adds effects and about 10% / 25% more power: lava burns, lightning pierces armor and stuns, ice freezes, storm strikes several times, obsidian shields the caster, and healing fusions cleanse and turn overhealing into a shield. The weakest component of a compound element sets the mastery. The Academy shows each spell's forms."),
            dict(name="Party sparring", text="Academy > Sparring: pick two full parties at home and they fight each other as teams (non-lethal, loser left low on health) for a flat 3 white gel and 3 hours. Every member gains fighting-style XP and class proficiency in the chosen arena, and every pair inside each party grows closer, which raises that party's synergy (shown in the result). A single duel between two slimes costs 2."),
            dict(name="Waking, training and mood", text="Waking a sleeping slime costs mood (6 morale and a flash of anger) - unless it has already slept past half its energy, then it wakes for free; a confirm warns you before you wake a tired one. Sparring, drilling or hunting with a sleeper wakes it first (and is refused if it is too tired); a slime at a job leaves the job (the current shift is lost); a slime below half health is too hurt to spar and drills for 60%. The pickers tag sleeping, working and hurt slimes. A brawl now also costs both fighters 15 morale and stirs their anger. A duel costs 2 white gel; a party-vs-party spar (two full parties fight as teams) a flat 3."),
            dict(name="Fusing purple gel", text="Gacha tab: 100 white gel fuse into 1 purple gel (one, ten, or as many as you can afford)."),
            dict(name="Total power", text="The power number on a slime's card adds what it is (class, level, rarity, stars, stage, gear, relics, potions) and what it can do: its skills (scaled by the stat they use; capstones count double, spell forms count extra), star attributes, elemental mastery, fighting styles and class proficiency - then multiplies by its current mood and morale. The card shows each part; a party's power is its members' total times its synergy. Beside every slime's figure in the Colony a three-digit tag (001 to 999, a square-root scale where 999 is a top-end slime) shows the same power at a glance."),
            dict(name="Bulk pulls", text="A pull costs 10 gel (white or purple). Pulling 10 or more at once is 10% cheaper: 90 gel for ten."),
            dict(name="Foraging and hunts", text="Hunting (Dungeons > Hunts & foraging) costs no resources, only time and a little health: slimes bring back white gel, food and essence (and rarely purple gel), now and then a herb, scrap or a common stone. There are four zones, from the one-hour Dewdrop Pond to the Crust Road. Every hunt also gives a mild amount of XP, worked out like the Gloop Pit's: the XP a level costs spread over the hunts it should take (about 20 three-hour hunts per level for a common slime, +50% more for each rarity step, shorter or longer zones pro rata), so it keeps up with level and rarity. It also sharpens the hunter's class proficiency, and a party that hunts together grows closer (bonds, so party synergy rises). With foraging on, slimes that belong to no party, hold no post and have nothing to do hunt by themselves in the best zone they can clear safely (power at least 1.5x the zone's danger), as long as they are healthy (70% HP), rested (energy 50+) and fed (35+). Appointed chefs, blacksmiths, brewers and doctors forage for a 3-hour shift when their post has nothing to do. Anyone out can be called back at once. Slimes in a party, grounded, or the Vice Keeper never forage."),
            dict(name="Rest Area", text="The Rest Area restores energy fast (14 per hour at level 1, 40 at level 5) but HP heals only at the normal sleeping rate (8% per hour). To get health back quickly build a Hospital and appoint a medic doctor."),
            dict(name="Slime colour", text="The ring around a slime always shows its rarity; the body colour is separate. By default it follows the class, but open a slime and use the colour swatch beside its name to pick any colour (the arrow resets it)."),
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
