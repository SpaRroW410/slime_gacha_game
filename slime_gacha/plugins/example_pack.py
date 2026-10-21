"""Example mod: a class (Jester), a skill (Pratfall) and an enemy (Mirthless Mime).

It ships switched off so it never changes a normal game. To try it, set ENABLED = True (docs/MODDING.md explains each call).
"""
from ..abilities import Ability, register_ability
from ..archetypes import Archetype, register_archetype
from ..battle import Enemy, register_enemy

ENABLED = False

def register():
    register_ability(Ability("pratfall", "Pratfall", "damage", 1.2, "atk", "enemy", 0, 0, "Trip over, somehow hitting the foe.",
                             fx=(("stun", 0.3),)))
    register_archetype(Archetype(
        "jester", "Jester", "🃏", dict(hp=27, atk=6, defense=3, mag=4, spd=8), dict(hp=3.6, atk=1.2, defense=0.6, mag=0.9, spd=0.9),
        {1: "pratfall"}, "attack", discipline="sword", likes=("laughter",), pull_weight=0.5))
    register_enemy(Enemy("mirthless_mime", "Mirthless Mime", "🤡", 2, dict(hp=40, atk=7, defense=3, mag=2, spd=6), ["pratfall"], 18,
                         {"white_gel": (2, 5)}))
