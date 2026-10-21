"""Bard, Paladin, Alchemist and Druid: their rarity skills, evolution skills, pure capstones and star attributes.

attributes.py merges these tables into its own (RARITY_SKILLS, EVOLUTION_SKILLS, PURE_CAPSTONES, STAR_ATTRS); the classes
themselves are registered in archetypes.py and their level skills in abilities.py.
"""
from .abilities import Ability


def _A(key, name, kind, power, stat, target, cd, dur, desc, *fxs):
    return Ability(key, name, kind, power, stat, target, cd, dur, desc, fx=tuple(fxs))


RARITY_SKILLS = dict(
    bard=[_A("dissonance", "Dissonance", "damage", 1.6, "mag", "enemy", 2, 0, "A jarring chord that rattles one foe and slows it.", ("debuff", "spd", 0.3, 3)),
          _A("healing_hymn", "Healing Hymn", "heal", 1.0, "mag", "all_allies", 3, 0, "A hymn mends the party and keeps healing it for 3 turns.", ("buff", "regen", 0.04, 3)),
          _A("war_anthem", "War Anthem", "utility", 0.0, "mag", "all_allies", 4, 0, "The whole party fights harder: +35% attack for 3 turns.", ("buff", "atk", 0.35, 3)),
          _A("grand_finale", "Grand Finale", "damage", 2.4, "mag", "all_enemies", 5, 0, "A thundering finale hits every foe, and the Bard may act again.", ("extra_turn",))],
    paladin=[_A("radiant_strike", "Radiant Strike", "damage", 1.7, "atk", "enemy", 2, 0, "A blow of holy light that ignores a third of armor.", ("pierce", "def", 0.35)),
             _A("bulwark_aura", "Bulwark Aura", "utility", 0.0, "atk", "all_allies", 4, 0, "A shining aura: the whole party takes 25% less damage for 3 turns.", ("buff", "guard", 0.25, 3)),
             _A("divine_shield", "Divine Shield", "utility", 1.0, "atk", "ally", 3, 0, "A holy shield absorbs the next stretch of damage on one ally.", ("shield", 3.0)),
             _A("judgement", "Judgement", "damage", 2.6, "atk", "all_enemies", 5, 0, "The heavens judge every foe; the Paladin is ready to act again.", ("extra_turn",))],
    alchemist=[_A("volatile_mixture", "Volatile Mixture", "damage", 1.9, "mag", "enemy", 2, 0, "A bubbling flask that burns through magic resistance.", ("pierce", "resist", 1.0)),
               _A("elixir_of_vigor", "Elixir of Vigor", "utility", 0.0, "mag", "ally", 3, 0, "An ally gains +40% attack and +20% crit chance for 3 turns.", ("buff", "atk", 0.4, 3), ("buff", "crit_rate", 0.2, 3)),
               _A("corrosive_cloud", "Corrosive Cloud", "poison", 0.7, "mag", "enemy", 3, 4, "An acid haze that eats at every foe.", ("spread",)),
               _A("philosophers_stone", "Philosopher's Stone", "heal", 2.4, "mag", "all_allies", 5, 0, "Pure transmuted vitality: everyone is nearly restored and cleansed.", ("cleanse",))],
    druid=[_A("thorn_whip", "Thorn Whip", "damage", 1.7, "mag", "enemy", 2, 0, "Living thorns lash a foe and leave it bleeding.", ("bleed", 3, 0.25)),
           _A("regrowth", "Regrowth", "heal", 1.3, "mag", "ally", 2, 0, "A strong heal that keeps growing: the ally regenerates for 3 turns.", ("buff", "regen", 0.05, 3)),
           _A("entangle", "Entangle", "damage", 0.9, "mag", "all_enemies", 3, 0, "Roots grab every foe and slow it.", ("debuff", "spd", 0.35, 3)),
           _A("natures_wrath", "Nature's Wrath", "damage", 2.5, "mag", "all_enemies", 5, 0, "The wild strikes back: heavy on hazardous ground.", ("terrain_boost", 0.5))],
)

EVOLUTION_SKILLS = dict(
    bard=(_A("inspire", "Inspire", "utility", 0.0, "mag", "ally", 3, 0, "An ally gains +20% crit chance and +15% evasion for 3 turns.", ("buff", "crit_rate", 0.2, 3), ("buff", "evasion", 0.15, 3)),
          _A("inspire_ii", "Inspire II", "utility", 0.0, "mag", "ally", 3, 0, "An ally gains +30% crit chance and +25% evasion for 3 turns.", ("buff", "crit_rate", 0.3, 3), ("buff", "evasion", 0.25, 3))),
    paladin=(_A("oath_of_light", "Oath of Light", "utility", 0.0, "atk", "self", 4, 0, "Swear an oath: take 35% less damage for 3 turns.", ("buff", "guard", 0.35, 3)),
             _A("oath_of_light_ii", "Oath of Light II", "utility", 0.0, "atk", "self", 4, 0, "The oath deepens: take 50% less damage for 3 turns.", ("buff", "guard", 0.5, 3))),
    alchemist=(_A("transmute_armor", "Transmute Armor", "utility", 0.0, "mag", "ally", 4, 0, "An ally's armor turns to alloy: 35% less damage and +30% attack for 3 turns.", ("buff", "guard", 0.35, 3), ("buff", "atk", 0.3, 3)),
               _A("transmute_armor_ii", "Transmute Armor II", "utility", 0.0, "mag", "ally", 4, 0, "An ally takes 50% less damage and gains +45% attack for 3 turns.", ("buff", "guard", 0.5, 3), ("buff", "atk", 0.45, 3))),
    druid=(_A("bark_skin", "Bark Skin", "utility", 0.0, "mag", "ally", 3, 0, "An ally's skin hardens: 30% less damage and light regeneration for 3 turns.", ("buff", "guard", 0.3, 3), ("buff", "regen", 0.03, 3)),
           _A("bark_skin_ii", "Bark Skin II", "utility", 0.0, "mag", "ally", 3, 0, "An ally takes 45% less damage and regenerates for 3 turns.", ("buff", "guard", 0.45, 3), ("buff", "regen", 0.05, 3))),
)

PURE_CAPSTONES = dict(
    bard=(_A("symphony", "Symphony", "utility", 0.0, "mag", "all_allies", 5, 0, "The whole party plays as one: +30% attack and +30% speed for 3 turns.", ("buff", "atk", 0.3, 3), ("buff", "spd", 0.3, 3)),
          _A("requiem", "Requiem", "heal", 1.6, "mag", "all_allies", 5, 0, "A song for the fallen and the weary: heal the party and cleanse it.", ("cleanse",))),
    paladin=(_A("sanctuary", "Sanctuary", "utility", 0.0, "atk", "all_allies", 5, 0, "Holy ground: every ally gets a shield soaking damage.", ("shield", 2.0)),
             _A("divine_intervention", "Divine Intervention", "utility", 0.0, "atk", "all_allies", 6, 0, "The whole party cannot fall below 1 HP for 1 turn, and is cleansed.", ("undying", 1), ("cleanse",))),
    alchemist=(_A("great_work", "The Great Work", "heal", 2.0, "mag", "all_allies", 5, 0, "The masterwork elixir: heal the party and grant +25% spell power for 3 turns.", ("buff", "spell_power", 0.25, 3)),
               _A("chain_reaction", "Chain Reaction", "poison", 1.0, "mag", "all_enemies", 5, 0, "A volatile chain: poison on every foe and a burst of damage that spreads.", ("spread",), ("hits", 2))),
    druid=(_A("wild_gale", "Wild Gale", "utility", 0.0, "mag", "all_enemies", 5, 0, "A howling gale: every foe loses half its speed and 25% of its attack for 3 turns.", ("debuff", "spd", 0.5, 3), ("debuff", "atk", 0.25, 3)),
           _A("verdant_renewal", "Verdant Renewal", "heal", 1.4, "mag", "all_allies", 5, 0, "The grove heals the party and keeps healing it for 4 turns.", ("buff", "regen", 0.05, 4))),
)

STAR_ATTRS = dict(
    bard=[("evasion", .05), ("spell_power", .08), ("regen", .02), ("crit_rate", .05)],
    paladin=[("guard", .06), ("regen", .03), ("resist", .06), ("lifesteal", .06)],
    alchemist=[("spell_power", .08), ("crit_rate", .05), ("resist", .06), ("regen", .02)],
    druid=[("regen", .03), ("spell_power", .08), ("guard", .05), ("resist", .08)],
)
STAMINA_BASE = dict(bard=80, paladin=100, alchemist=75, druid=85)
STAMINA_GROWTH = dict(bard=2.0, paladin=2.5, alchemist=1.9, druid=2.1)
