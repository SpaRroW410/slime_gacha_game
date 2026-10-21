"""Slime attributes beyond the base stats: STAMINA, star attributes and rarity skills.

* Every slime (even 1-star common) has STAMINA: every action in battle costs some; it refills over time (faster
  asleep or in the Rest Area). An exhausted slime fights at reduced power until it catches its breath.
* Each extra STAR adds one class-specific attribute (crit, guard, evasion, regen, spell power, resist, lifesteal ...).
* Each RARITY step adds one class skill (Moon Slash, Aura Blade ...).
"""
from typing import Dict, List

from . import config
from .abilities import Ability, register_ability

# ---- stamina ---------------------------------------------------------------------------------------------------------------
from . import newclasses as _new          # Bard, Paladin, Alchemist, Druid

STAMINA_BASE = dict(barbarian=100, rogue=90, ranger=90, medic=80, mage=70, necromancer=70, **_new.STAMINA_BASE)
STAMINA_GROWTH = dict(barbarian=2.5, rogue=2.2, ranger=2.2, medic=2.0, mage=1.8, necromancer=1.8, **_new.STAMINA_GROWTH)


def max_stamina(slime) -> float:
    base = STAMINA_BASE.get(slime.archetype, 80) + STAMINA_GROWTH.get(slime.archetype, 2.0) * (config.stat_level(slime.level) - 1)
    mult = 0.6 + 0.4 * config.RARITY_STAT_MULT[slime.rarity] * config.STAR_STAT_MULT[slime.stars - 1]
    return round(base * mult * (1 + buff_value(slime, "stamina")), 1)


def regen_per_round(slime) -> float:
    """Breath caught between rounds of a fight."""
    return round(config.STAMINA_ROUND_REGEN * max_stamina(slime) / 100 * 4 * recovery_mult(slime), 2)


def recovery_mult(slime) -> float:
    return 1 + 5 * buff_value(slime, "stamina")        # a stamina potion of bonus b: recovery x(1 + 5b)


def hourly_regen(slime) -> float:
    """Fraction of max stamina regained per hour."""
    rate = config.STAMINA_HOUR_REGEN
    if slime.state in ("sleeping", "resting"):
        rate *= config.STAMINA_SLEEP_MULT
    return rate * recovery_mult(slime)


def action_cost(ability) -> float:
    if ability.kind == "utility":
        return config.STAMINA_COSTS["heal"]
    if ability.kind == "guard":
        return config.STAMINA_COSTS["guard"]
    if ability.kind == "heal":
        return config.STAMINA_COSTS["heal"] * (1.4 if ability.target == "all_allies" else 1)
    if ability.kind == "summon":
        return config.STAMINA_COSTS["summon"]
    return config.STAMINA_COSTS["attack"] + config.STAMINA_COSTS["power"] * ability.power * \
        (1.5 if ability.target == "all_enemies" else 1)


# ---- buffs (potions) --------------------------------------------------------------------------------------------------------
def potion_slots(slime) -> int:
    """How many potions a slime can have active at once: 2 at one star up to 6 at five."""
    return config.POTION_SLOTS_BASE + slime.stars


def buff_value(slime, kind: str) -> float:
    return sum(b["bonus"] for b in getattr(slime, "buffs", []) if b["kind"] == kind)


# ---- star attributes ---------------------------------------------------------------------------------------------------------
ATTR_LABEL = {"crit_rate": "Crit rate", "crit_dmg": "Crit damage", "lifesteal": "Lifesteal", "evasion": "Evasion",
              "guard": "Guard (damage taken)", "regen": "Regeneration (HP/round)", "spell_power": "Spell power",
              "resist": "Magic resist"}
STAR_ATTRS = {                       # class -> attributes gained at 2, 3, 4, 5 stars
    "barbarian": [("crit_dmg", .20), ("guard", .06), ("regen", .03), ("lifesteal", .08)],
    "mage": [("spell_power", .10), ("resist", .08), ("crit_rate", .06), ("crit_dmg", .30)],
    "medic": [("regen", .02), ("resist", .08), ("spell_power", .10), ("guard", .06)],
    "rogue": [("crit_rate", .06), ("evasion", .06), ("crit_dmg", .25), ("lifesteal", .06)],
    "ranger": [("crit_rate", .05), ("crit_dmg", .20), ("evasion", .05), ("lifesteal", .05)],
    "necromancer": [("lifesteal", .06), ("spell_power", .10), ("resist", .08), ("regen", .03)],
    **_new.STAR_ATTRS,
}


def star_attributes(slime) -> List[dict]:
    """Attributes unlocked by stars; the higher the rarity, the harder they hit (x1 common ... x3 legendary).
    Once unlocked they stay (even after a rarity ascension resets the stars); each star above the unlocking one adds 10%."""
    out = []
    boost = config.STAR_ATTR_RARITY_BOOST[slime.rarity]
    earned = max(slime.stars, getattr(slime, "star_peak", 1))
    for i, (key, v) in enumerate(STAR_ATTRS.get(slime.archetype, [])):
        if earned >= i + 2:
            more = 1 + 0.1 * max(0, slime.stars - (i + 2))
            out.append(dict(key=key, label=ATTR_LABEL[key], value=round(v * boost * more, 3), star=i + 2))
    return out


def battle_mods(slime) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for a in star_attributes(slime):
        out[a["key"]] = out.get(a["key"], 0.0) + a["value"]
    from . import potions                      # local import: potions -> config only, but keep the layers loose
    for k, v in potions.combat_mods(getattr(slime, "buffs", [])).items():
        out[k] = out.get(k, 0.0) + v
    return out


# ---- rarity skills --------------------------------------------------------------------------------------------------------------
def _A(key, name, kind, power, stat, target, cd, dur, desc, *fxs):
    return Ability(key, name, kind, power, stat, target, cd, dur, desc, fx=tuple(fxs))


_S = dict(
    barbarian=[_A("moon_slash", "Moon Slash", "damage", 1.7, "atk", "enemy", 2, 0, "A crescent of goo cuts deep and leaves the foe bleeding.", ("bleed", 3, 0.25)),
               _A("aura_blade", "Aura Blade", "damage", 1.0, "atk", "all_enemies", 3, 0, "A glowing arc sweeps every foe, slicing through 30% of their armor.", ("pierce", "def", 0.3)),
               _A("earthsplitter", "Earthsplitter", "damage", 3.0, "atk", "enemy", 4, 0, "The ground breaks: a huge hit with a good chance to stun.", ("stun", 0.4)),
               _A("titan_break", "Titan Break", "damage", 2.4, "atk", "all_enemies", 5, 0, "A world-shaking finisher; the Titan is ready to act again at once.", ("extra_turn",))],
    mage=[_A("mana_lance", "Mana Lance", "damage", 1.8, "mag", "enemy", 2, 0, "A lance of pure mana that ignores magic resistance.", ("pierce", "resist", 1.0)),
          _A("starfall", "Starfall", "damage", 1.0, "mag", "all_enemies", 3, 0, "Stars of every element rain on the foes.", ("prism",)),
          _A("void_rift", "Void Rift", "damage", 3.2, "mag", "enemy", 4, 0, "Tear a hole in one foe: huge damage, one round later.", ("delay", 1)),
          _A("cataclysm", "Cataclysm", "damage", 2.4, "mag", "all_enemies", 5, 0, "Everything burns; far worse on hazardous ground.", ("terrain_boost", 0.5))],
    medic=[_A("healing_light", "Healing Light", "heal", 2.0, "mag", "ally", 2, 0, "A strong, focused heal that also cleanses poison, bleeding and curses.", ("cleanse",)),
           _A("sanctuary_mist", "Sanctuary Mist", "heal", 1.2, "mag", "all_allies", 3, 0, "A mist mends the whole party and keeps healing it for 3 turns.", ("buff", "regen", 0.05, 3)),
           _A("aegis_bloom", "Aegis Bloom", "utility", 1.0, "mag", "ally", 3, 0, "A flower ward absorbs the next stretch of damage on one ally.", ("shield", 2.5)),
           _A("miracle_bloom", "Miracle Bloom", "heal", 2.4, "mag", "all_allies", 5, 0, "Everyone is nearly restored.")],
    rogue=[_A("shadow_stab", "Shadow Stab", "damage", 1.8, "atk", "enemy", 2, 0, "Strike from nowhere: a sure crit on a foe that has not acted yet.", ("first_strike",)),
           _A("viper_kiss", "Viper Kiss", "poison", 0.7, "atk", "enemy", 3, 4, "A vicious poison that stacks on a foe already poisoned.", ("stack",)),
           _A("death_mark", "Death Mark", "damage", 1.5, "atk", "enemy", 4, 0, "The marked foe takes 50% more damage from everyone for 3 turns.", ("mark", 3, 0.5)),
           _A("thousand_cuts", "Thousand Cuts", "damage", 0.6, "atk", "all_enemies", 5, 0, "A blur of blades: three hits on every foe, each can crit.", ("hits", 3))],
    ranger=[_A("piercing_shot", "Piercing Shot", "damage", 1.9, "atk", "enemy", 2, 0, "An arrow that ignores guard.", ("pierce", "guard", 1.0)),
            _A("rain_of_stars", "Rain of Stars", "damage", 1.0, "atk", "all_enemies", 3, 0, "Glittering arrows fall everywhere and slow the foes.", ("debuff", "spd", 0.3, 3)),
            _A("hawkeye", "Hawkeye", "damage", 3.0, "atk", "enemy", 4, 0, "One shot: it never misses and always crits.", ("nomiss",), ("crit",)),
            _A("heavens_volley", "Heaven's Volley", "damage", 2.2, "atk", "all_enemies", 5, 0, "The sky answers: every ranger in the party fires too.", ("chorus", "arrow"))],
    necromancer=[_A("bone_spear", "Bone Spear", "damage", 1.8, "mag", "enemy", 2, 0, "A javelin of old bone; a small bone pal rises if none is fighting.", ("minion",)),
                 _A("plague_cloud", "Plague Cloud", "poison", 0.7, "mag", "enemy", 3, 4, "A rotting haze that spreads to every foe.", ("spread",)),
                 _A("grave_feast", "Grave Feast", "drain", 2.0, "mag", "enemy", 4, 0, "Feast on a foe's life."),
                 _A("legion_of_bones", "Legion of Bones", "summon", 1.0, "mag", "self", 5, 0, "Three bone servants answer the call.", ("count", 3))],
)
_S.update(_new.RARITY_SKILLS)
# one signature skill per class at its first evolution; the second evolution raises it to rank II
EVOLUTION_SKILLS = dict(
    barbarian=(_A("berserkers_oath", "Berserker's Oath", "utility", 0.0, "atk", "self", 99, 0, "Swear an oath: +60% attack whenever badly hurt (below 30% HP), for the rest of the fight.", ("oath", 0.6)),
               _A("berserkers_oath_ii", "Berserker's Oath II", "utility", 0.0, "atk", "self", 99, 0, "The oath deepens: +90% attack whenever badly hurt.", ("oath", 0.9))),
    mage=(_A("arcane_focus", "Arcane Focus", "utility", 0.0, "mag", "self", 4, 0, "Focus: spell power +40% for 3 turns.", ("buff", "spell_power", 0.4, 3)),
          _A("arcane_focus_ii", "Arcane Focus II", "utility", 0.0, "mag", "self", 4, 0, "Deeper focus: spell power +60% for 3 turns.", ("buff", "spell_power", 0.6, 3))),
    medic=(_A("sacred_ward", "Sacred Ward", "utility", 0.0, "mag", "ally", 3, 0, "An ally takes 30% less damage for 3 turns.", ("buff", "guard", 0.3, 3)),
           _A("sacred_ward_ii", "Sacred Ward II", "utility", 0.0, "mag", "ally", 3, 0, "An ally takes 45% less damage for 3 turns.", ("buff", "guard", 0.45, 3))),
    rogue=(_A("vanish", "Vanish", "utility", 0.0, "atk", "self", 5, 0, "Slip out of sight: cannot be targeted for 2 turns.", ("untarget", 2)),
           _A("vanish_ii", "Vanish II", "utility", 0.0, "atk", "self", 5, 0, "Slip out of sight: cannot be targeted for 3 turns.", ("untarget", 3))),
    ranger=(_A("mark_prey", "Mark Prey", "utility", 0.0, "atk", "enemy", 4, 0, "The party focuses one foe: it takes 30% more damage for 3 turns.", ("mark", 3, 0.3)),
            _A("mark_prey_ii", "Mark Prey II", "utility", 0.0, "atk", "enemy", 4, 0, "The party focuses one foe: it takes 45% more damage for 3 turns.", ("mark", 3, 0.45))),
    necromancer=(_A("soul_tithe", "Soul Tithe", "utility", 0.0, "mag", "self", 4, 0, "Sacrifice a minion: the party heals its full HP.", ("tithe", 1.0)),
                 _A("soul_tithe_ii", "Soul Tithe II", "utility", 0.0, "mag", "self", 4, 0, "Sacrifice a minion: the party heals 150% of its HP.", ("tithe", 1.5))),
)
EVOLUTION_SKILLS.update(_new.EVOLUTION_SKILLS)
for _cls, _pair in EVOLUTION_SKILLS.items():
    for _a in _pair:
        register_ability(_a)
RARITY_SKILLS: Dict[str, List[str]] = {}
for _cls, _abs in _S.items():
    RARITY_SKILLS[_cls] = [a.key for a in _abs]
    for _a in _abs:
        register_ability(_a)


# Pure capstones: two per class, earned by a legendary 5-star that never specialized. They need class proficiency
# (>= 30 for the first, >= 70 for the second) and fade when the slime stops practising (see capstones()).
PURE_CAPSTONES = dict(
    barbarian=(_A("warlords_cry", "Warlord's Cry", "utility", 0.0, "atk", "all_allies", 5, 0, "A roar that fires up the whole party: +40% attack for 3 turns.", ("buff", "atk", 0.4, 3)),
               _A("undying_rage", "Undying Rage", "utility", 0.0, "atk", "self", 6, 0, "Cannot fall below 1 HP for 2 turns, and hits 30% harder.", ("undying", 2), ("buff", "atk", 0.3, 2))),
    mage=(_A("edit_source", "Edit Source", "utility", 0.0, "mag", "enemy", 5, 0, "Rewrite the foe's strongest stat to 1 for 3 turns (half as long on bosses).", ("rewrite", "best", 1, 3)),
          _A("debug", "Debug", "utility", 0.0, "mag", "all_allies", 5, 0, "Cleanse the whole party and strip every foe of buffs and shields.", ("cleanse",), ("strip",))),
    medic=(_A("resurrection", "Resurrection", "utility", 0.0, "mag", "self", 99, 0, "Once per fight: a fallen ally stands again with half its HP.", ("revive", 0.5)),
           _A("overheal_shield", "Overheal Shield", "heal", 1.5, "mag", "all_allies", 4, 0, "Heal the party; healing beyond full HP becomes a shield.", ("overheal",))),
    rogue=(_A("assassinate", "Assassinate", "damage", 2.5, "atk", "enemy", 4, 0, "A killing blow: triple damage to a foe below 25% HP.", ("execute", 0.25, 3.0)),
           _A("smoke_bomb", "Smoke Bomb", "utility", 0.0, "atk", "all_allies", 5, 0, "The whole party gains +30% evasion for 3 turns.", ("buff", "evasion", 0.3, 3))),
    ranger=(_A("trapfield", "Trapfield", "utility", 0.0, "atk", "all_enemies", 5, 0, "Snares everywhere: every foe loses half its speed for 3 turns.", ("debuff", "spd", 0.5, 3)),
            _A("eagle_eye", "Eagle Eye", "utility", 0.0, "atk", "all_allies", 5, 0, "The whole party gains +30% crit chance for 3 turns.", ("buff", "crit_rate", 0.3, 3))),
    necromancer=(_A("raise_fallen", "Raise Fallen", "utility", 0.0, "mag", "self", 5, 0, "A fallen foe or ally rises as your thrall.", ("raise",)),
                 _A("soul_harvest", "Soul Harvest", "drain", 1.2, "mag", "all_enemies", 5, 0, "Drain every foe; the party heals half of everything taken.", ("harvest", 0.5))),
)
PURE_CAPSTONES.update(_new.PURE_CAPSTONES)
for _cls, _pair in PURE_CAPSTONES.items():
    for _a in _pair:
        register_ability(_a)


def pure_earned(slime) -> bool:
    """A legendary 5-star that never specialized earns the pure capstones for good (specializing later keeps them)."""
    if not slime.pure_earned and slime.rarity == "legendary" and slime.stars >= config.MAX_STARS and not slime.spec \
            and slime.archetype in PURE_CAPSTONES:
        slime.pure_earned = True
    return slime.pure_earned


def capstones(slime) -> List[str]:
    """The pure capstones the slime can use right now: both at proficiency >= 70, the first at >= 30."""
    if not pure_earned(slime):
        return []
    first, second = (a.key for a in PURE_CAPSTONES[slime.archetype])
    p = slime.class_prof
    if p >= config.PROF_BOTH_CAPSTONES:
        return [first, second]
    return [first] if p >= config.PROF_ONE_CAPSTONE else []


def practise(slime, discipline: str, own: float, other: float = 0.0) -> str:
    """Training in a discipline: the class's own discipline raises class proficiency, a hybrid's secondary one raises
    its second proficiency, anything else only a little general practice. Returns which one grew."""
    if discipline == slime.arch.discipline:
        slime.class_prof = min(100.0, slime.class_prof + own)
        slime.prof_idle = 0
        return "class"
    if slime.spec and discipline == slime.spec_disc:
        slime.spec_prof = min(100.0, slime.spec_prof + own)
        slime.spec_idle = 0
        return "spec"
    if other:
        slime.class_prof = min(100.0, slime.class_prof + other)
        slime.prof_idle = 0
    return "other"


def hybrid_capstone(slime):
    """The hybrid capstone's key once a specialized slime is legendary 5-star, else None."""
    from .specialization import HYBRID_CAPSTONES
    if slime.spec and slime.rarity == "legendary" and slime.stars >= config.MAX_STARS and slime.spec in HYBRID_CAPSTONES:
        return HYBRID_CAPSTONES[slime.spec].key
    return None


def hybrid_keys(slime) -> set:
    """Signature skill and capstone of the slime's hybrid class (what counts as practising the second discipline)."""
    from .specialization import SPECS, HYBRID_CAPSTONES
    out = set()
    if slime.spec in SPECS:
        out.add(SPECS[slime.spec].ability)
    if slime.spec in HYBRID_CAPSTONES:
        out.add(HYBRID_CAPSTONES[slime.spec].key)
    return out


def hybrid_scale(slime) -> float:
    """Strength of the hybrid capstone: up to 60% of a pure one at full second-discipline proficiency, 30% at none."""
    return round(config.HYBRID_CAPSTONE_MAX * (0.5 + 0.5 * slime.spec_prof / 100.0), 3)


def evolution_skill(slime):
    """The class's signature skill for the slime's evolution stage (rank I at stage 1, rank II from stage 2), or None."""
    pair = EVOLUTION_SKILLS.get(slime.archetype)
    if not pair or slime.stage < 1:
        return None
    return pair[min(1, slime.stage - 1)].key


def rarity_skills(slime) -> List[str]:
    """One skill per rarity step above common (uncommon unlocks the 1st ... legendary the 4th)."""
    n = config.RARITIES.index(slime.rarity)
    return RARITY_SKILLS.get(slime.archetype, [])[:n]
