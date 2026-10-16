"""Ability definitions (pure data). BattleSystem interprets `kind` via KIND_HANDLERS.

kind:   damage | heal | guard | drain | poison | summon | utility   (add handlers in battle.py; utility = effects only)
fx:     extra effects, see fx.py (bleed, stun, mark, buff, shield, revive ...)
stat:   which stat scales the effect: atk | mag | spd | defense | hp
target: enemy | all_enemies | ally | all_allies | self
"""
from dataclasses import dataclass

from .registry import Registry


@dataclass(frozen=True)
class Ability:
    key: str
    name: str
    kind: str
    power: float = 1.0
    stat: str = "atk"
    target: str = "enemy"
    cooldown: int = 0
    duration: int = 0          # for statuses (poison / guard)
    description: str = ""
    element: str = ""          # "" = non-elemental; spells carry an element key (see elements.py)
    tier: int = 0              # spell tier (1 basic, 2/3 fused); 0 = class ability
    creator: str = ""          # who researched it (custom spells)
    minion: str = ""           # summon: "emoji Name" of what appears (default: a Bone Pal)
    fx: tuple = ()             # status effects applied after the main effect (see fx.py)


ABILITIES: "Registry[Ability]" = Registry("ability")


def register_ability(ab: Ability) -> Ability:
    return ABILITIES.register(ab, ab.key)


def get_ability(key: str) -> Ability:
    return ABILITIES.get(key)


# ---- built-ins -------------------------------------------------------------
for _a in [
    Ability("splat", "Splat", "damage", 1.0, "atk", "enemy", 0, 0, "Basic slimy bonk."),
    Ability("smash", "Gloop Smash", "damage", 1.8, "atk", "enemy", 2, 0, "Heavy hit."),
    Ability("war_cry", "War Cry", "guard", 0.0, "atk", "self", 3, 2, "Brace up: halve damage taken."),
    Ability("rampage", "Rampage", "damage", 1.1, "atk", "all_enemies", 4, 0, "Hit every foe."),
    Ability("spark", "Spark", "damage", 1.3, "mag", "enemy", 0, 0, "A zappy blob of magic."),
    Ability("fireblob", "Fire Blob", "damage", 1.0, "mag", "all_enemies", 3, 0, "Burning goo splash."),
    Ability("arcane_surge", "Arcane Surge", "damage", 2.4, "mag", "enemy", 4, 0, "Big magic."),
    Ability("mend", "Mend", "heal", 1.4, "mag", "ally", 1, 0, "Heal the most wounded ally."),
    Ability("soothing_mist", "Soothing Mist", "heal", 0.8, "mag", "all_allies", 3, 0, "Heal everyone a bit."),
    Ability("bubble_ward", "Bubble Ward", "guard", 0.0, "mag", "ally", 3, 2, "Shield an ally."),
    Ability("stab", "Gooey Stab", "damage", 1.2, "atk", "enemy", 0, 0, "Quick jab."),
    Ability("venom_dart", "Venom Dart", "poison", 0.4, "atk", "enemy", 2, 3, "Poison over time."),
    Ability("backstab", "Backstab", "damage", 2.2, "atk", "enemy", 3, 0, "Strikes the weakest foe."),
    Ability("arrow", "Goo Arrow", "damage", 1.1, "atk", "enemy", 0, 0, "Ranged shot."),
    Ability("volley", "Volley", "damage", 0.8, "atk", "all_enemies", 3, 0, "Rain of arrows."),
    Ability("snipe", "Snipe", "damage", 2.6, "atk", "enemy", 5, 0, "One perfect shot."),
    Ability("siphon", "Soul Siphon", "drain", 1.0, "mag", "enemy", 1, 0, "Steal life from a foe."),
    Ability("raise_bones", "Raise Bones", "summon", 0.6, "mag", "self", 5, 0, "Summon a Bone Pal."),
    Ability("curse", "Wilting Curse", "poison", 0.5, "mag", "enemy", 2, 4, "Strong poison."),
    Ability("defend", "Defend", "guard", 0.0, "defense", "self", 0, 1, "Basic guard (everyone has it)."),
    Ability("blorp_blast", "Blorp Blast", "damage", 2.0, "atk", "all_enemies", 4, 0, "Evolved: screen-wide goo."),
]:
    register_ability(_a)
