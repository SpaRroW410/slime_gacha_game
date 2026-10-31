"""Archetypes (slime classes) - THE main extension point.

To add a class, build an Archetype and call register_archetype(...). Nothing else in the engine
needs to change: gacha, hunting, battle, and the UI all enumerate the registry.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple

from .registry import Registry

STAT_KEYS = ("hp", "atk", "defense", "mag", "spd")
BEHAVIORS = ("attack", "heal", "defend", "explore")


@dataclass(frozen=True)
class Archetype:
    key: str
    name: str
    emoji: str
    base_stats: Dict[str, float]            # stats at level 1, stage 0, common rarity
    growth: Dict[str, float]                # added per level
    abilities: Dict[int, str]               # level -> ability key (unlocked when reached)
    default_behavior: str = "attack"
    likes: Tuple[str, ...] = ()             # flavour text / future friendship system
    hunt_bonus: Dict[str, float] = field(default_factory=dict)   # resource -> loot multiplier
    rivals: Tuple[str, ...] = ()            # archetype keys this class clashes with
    evolve_abilities: Dict[int, str] = field(default_factory=dict)  # stage -> ability key
    pull_weight: float = 1.0                # relative chance inside a rarity bucket
    discipline: str = "sword"               # training-ground affinity: sword | archery | magic


ARCHETYPES: "Registry[Archetype]" = Registry("archetype")


def register_archetype(a: Archetype) -> Archetype:
    missing = [k for k in STAT_KEYS if k not in a.base_stats or k not in a.growth]
    if missing:
        raise ValueError(f"archetype {a.key!r} missing stats: {missing}")
    if a.default_behavior not in BEHAVIORS:
        raise ValueError(f"archetype {a.key!r} has bad default_behavior")
    return ARCHETYPES.register(a, a.key)


def get_archetype(key: str) -> Archetype:
    return ARCHETYPES.get(key)


def all_archetypes():
    return ARCHETYPES.all()


def _s(hp, atk, defense, mag, spd):
    return dict(hp=hp, atk=atk, defense=defense, mag=mag, spd=spd)


# ---- the six starting classes ----------------------------------------------
register_archetype(Archetype(
    "barbarian", "Barbarian", "🪓", _s(40, 9, 5, 1, 4), _s(6, 2, 1, 0.3, 0.5),
    {1: "splat", 3: "smash", 6: "war_cry", 8: "flame_brand", 10: "rampage"}, "attack",
    discipline="sword",
    likes=("meat", "shouting"), hunt_bonus={"white_gel": 1.3}, rivals=("mage",)))

register_archetype(Archetype(
    "mage", "Mage", "🔮", _s(24, 2, 2, 10, 5), _s(3, 0.3, 0.5, 2.2, 0.6),
    {1: "spark", 3: "fireblob", 7: "arcane_surge"}, "attack",
    discipline="magic", pull_weight=0.85,                 # a little rarer than the other magic classes (medic, necromancer, alchemist)
    likes=("shiny things", "books"), hunt_bonus={"essence": 1.4}, rivals=("barbarian",)))

register_archetype(Archetype(
    "medic", "Medic", "💚", _s(30, 3, 4, 8, 5), _s(4, 0.5, 0.9, 1.8, 0.5),
    {1: "mend", 4: "bubble_ward", 8: "soothing_mist"}, "heal",
    discipline="magic",
    likes=("tea", "naps"), hunt_bonus={"food": 1.2}, rivals=("necromancer",)))

register_archetype(Archetype(
    "rogue", "Rogue", "🗡️", _s(26, 8, 3, 2, 9), _s(3.5, 1.9, 0.6, 0.3, 1.0),
    {1: "stab", 3: "venom_dart", 6: "backstab"}, "explore",
    discipline="sword",
    likes=("borrowing", "shadows"), hunt_bonus={"white_gel": 1.4}, rivals=("ranger",)))

register_archetype(Archetype(
    "ranger", "Ranger", "🏹", _s(28, 8, 3, 2, 7), _s(4, 1.8, 0.7, 0.3, 0.8),
    {1: "arrow", 4: "volley", 8: "snipe"}, "explore",
    discipline="archery",
    likes=("forests", "snacks"), hunt_bonus={"food": 1.5}, rivals=("rogue",)))

register_archetype(Archetype(
    "necromancer", "Necromancer", "💀", _s(26, 3, 3, 9, 4), _s(3.2, 0.4, 0.6, 2.0, 0.5),
    {1: "siphon", 3: "curse", 6: "raise_bones"}, "attack",
    discipline="magic",
    likes=("tea", "quiet"), hunt_bonus={"essence": 1.3}, rivals=("medic",)))

# ---- second wave -------------------------------------------------------------
register_archetype(Archetype(
    "bard", "Bard", "🎵", _s(28, 3, 3, 8, 7), _s(3.5, 0.5, 0.7, 1.7, 0.8),
    {1: "lilt", 3: "rally_song", 7: "lullaby"}, "heal",
    discipline="archery",
    likes=("songs", "applause"), hunt_bonus={"essence": 1.2, "food": 1.1}, rivals=()))

register_archetype(Archetype(
    "paladin", "Paladin", "🛡️", _s(44, 7, 7, 3, 3), _s(6.5, 1.6, 1.4, 0.5, 0.4),
    {1: "holy_bonk", 3: "aegis", 6: "smite"}, "defend",
    discipline="sword",
    likes=("oaths", "polish"), hunt_bonus={"white_gel": 1.2}, rivals=("necromancer",)))

register_archetype(Archetype(
    "alchemist", "Alchemist", "⚗️", _s(27, 3, 3, 9, 5), _s(3.3, 0.4, 0.6, 1.9, 0.6),
    {1: "acid_flask", 3: "tonic", 6: "explosive_brew"}, "attack",
    discipline="magic",
    likes=("fumes", "tinkering"), hunt_bonus={"essence": 1.3}, rivals=()))

register_archetype(Archetype(
    "druid", "Druid", "🌿", _s(32, 3, 4, 8, 5), _s(4.5, 0.5, 0.9, 1.8, 0.5),
    {1: "thorn_lash", 3: "bloom", 6: "tangle"}, "heal",
    discipline="archery",
    likes=("moss", "rain"), hunt_bonus={"food": 1.4}, rivals=()))
