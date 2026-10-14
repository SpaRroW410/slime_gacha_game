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
STAMINA_BASE = dict(barbarian=100, rogue=90, ranger=90, medic=80, mage=70, necromancer=70)
STAMINA_GROWTH = dict(barbarian=2.5, rogue=2.2, ranger=2.2, medic=2.0, mage=1.8, necromancer=1.8)


def max_stamina(slime) -> float:
    base = STAMINA_BASE.get(slime.archetype, 80) + STAMINA_GROWTH.get(slime.archetype, 2.0) * (slime.level - 1)
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
    if ability.kind == "guard":
        return config.STAMINA_COSTS["guard"]
    if ability.kind == "heal":
        return config.STAMINA_COSTS["heal"] * (1.4 if ability.target == "all_allies" else 1)
    if ability.kind == "summon":
        return config.STAMINA_COSTS["summon"]
    return config.STAMINA_COSTS["attack"] + config.STAMINA_COSTS["power"] * ability.power * \
        (1.5 if ability.target == "all_enemies" else 1)


# ---- buffs (potions) --------------------------------------------------------------------------------------------------------
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
}


def star_attributes(slime) -> List[dict]:
    """Attributes unlocked by stars (value grows a little with rarity)."""
    out = []
    boost = 1 + 0.1 * (config.RARITIES.index(slime.rarity))
    for i, (key, v) in enumerate(STAR_ATTRS.get(slime.archetype, [])):
        if slime.stars >= i + 2:
            out.append(dict(key=key, label=ATTR_LABEL[key], value=round(v * boost, 3), star=i + 2))
    return out


def battle_mods(slime) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for a in star_attributes(slime):
        out[a["key"]] = out.get(a["key"], 0.0) + a["value"]
    return out


# ---- rarity skills --------------------------------------------------------------------------------------------------------------
_S = dict(
    barbarian=[Ability("moon_slash", "Moon Slash", "damage", 1.7, "atk", "enemy", 2, 0, "A crescent of goo cuts one foe."),
               Ability("aura_blade", "Aura Blade", "damage", 1.0, "atk", "all_enemies", 3, 0, "A glowing arc sweeps every foe."),
               Ability("earthsplitter", "Earthsplitter", "damage", 3.0, "atk", "enemy", 4, 0, "The ground itself breaks."),
               Ability("titan_break", "Titan Break", "damage", 2.4, "atk", "all_enemies", 5, 0, "A world-shaking finisher.")],
    mage=[Ability("mana_lance", "Mana Lance", "damage", 1.8, "mag", "enemy", 2, 0, "A lance of pure mana."),
          Ability("starfall", "Starfall", "damage", 1.0, "mag", "all_enemies", 3, 0, "Stars rain on the foes."),
          Ability("void_rift", "Void Rift", "damage", 3.2, "mag", "enemy", 4, 0, "Tear a hole in one foe."),
          Ability("cataclysm", "Cataclysm", "damage", 2.4, "mag", "all_enemies", 5, 0, "Everything burns.")],
    medic=[Ability("healing_light", "Healing Light", "heal", 2.0, "mag", "ally", 2, 0, "A strong, focused heal."),
           Ability("sanctuary_mist", "Sanctuary Mist", "heal", 1.2, "mag", "all_allies", 3, 0, "A mist mends the whole party."),
           Ability("aegis_bloom", "Aegis Bloom", "guard", 0.0, "mag", "ally", 3, 3, "A flower ward halves damage for 3 turns."),
           Ability("miracle_bloom", "Miracle Bloom", "heal", 2.4, "mag", "all_allies", 5, 0, "Everyone is nearly restored.")],
    rogue=[Ability("shadow_stab", "Shadow Stab", "damage", 1.8, "atk", "enemy", 2, 0, "Strike from nowhere."),
           Ability("viper_kiss", "Viper Kiss", "poison", 0.7, "atk", "enemy", 3, 4, "A lingering, vicious poison."),
           Ability("death_mark", "Death Mark", "damage", 3.0, "atk", "enemy", 4, 0, "A marked foe takes a killing blow."),
           Ability("thousand_cuts", "Thousand Cuts", "damage", 1.4, "atk", "all_enemies", 5, 0, "A blur of blades.")],
    ranger=[Ability("piercing_shot", "Piercing Shot", "damage", 1.9, "atk", "enemy", 2, 0, "An arrow that ignores the odds."),
            Ability("rain_of_stars", "Rain of Stars", "damage", 1.0, "atk", "all_enemies", 3, 0, "Glittering arrows fall everywhere."),
            Ability("hawkeye", "Hawkeye", "damage", 3.0, "atk", "enemy", 4, 0, "One shot, never missed."),
            Ability("heavens_volley", "Heaven's Volley", "damage", 2.2, "atk", "all_enemies", 5, 0, "The sky answers.")],
    necromancer=[Ability("bone_spear", "Bone Spear", "damage", 1.8, "mag", "enemy", 2, 0, "A javelin of old bone."),
                 Ability("plague_cloud", "Plague Cloud", "poison", 0.7, "mag", "enemy", 3, 4, "A rotting haze."),
                 Ability("grave_feast", "Grave Feast", "drain", 2.0, "mag", "enemy", 4, 0, "Feast on a foe's life."),
                 Ability("legion_of_bones", "Legion of Bones", "summon", 1.0, "mag", "self", 5, 0, "A greater bone servant answers.")],
)
RARITY_SKILLS: Dict[str, List[str]] = {}
for _cls, _abs in _S.items():
    RARITY_SKILLS[_cls] = [a.key for a in _abs]
    for _a in _abs:
        register_ability(_a)


def rarity_skills(slime) -> List[str]:
    """One skill per rarity step above common (uncommon unlocks the 1st ... legendary the 4th)."""
    n = config.RARITIES.index(slime.rarity)
    return RARITY_SKILLS.get(slime.archetype, [])[:n]
