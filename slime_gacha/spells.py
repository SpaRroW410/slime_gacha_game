"""Spells: elemental Abilities. Tier-1 spells are sold in the Library; higher tiers are created by FUSING two
learned spells of different elements (spell research). Fused spells are registered at runtime, so the Game
persists them (`custom_spells`) and re-registers on load.

A spell is just an `Ability` with `element` and `tier` set - the BattleSystem needs no special cases beyond
element effectiveness and mastery scaling.
"""
from dataclasses import asdict, replace
from typing import Dict, List, Optional

from . import config, elements
from .abilities import ABILITIES, Ability, get_ability, register_ability
from .errors import InvalidAction

# ---- tier-1 spells sold at the Library (2 per basic element) ----------------------------------
for _s in [
    Ability("ember", "Ember", "damage", 1.3, "mag", "enemy", 0, 0, "A flicking fire blob.", "fire", 1),
    Ability("flame_wave", "Flame Wave", "damage", 0.8, "mag", "all_enemies", 3, 0, "Fire sweeps the field.", "fire", 1),
    Ability("water_jet", "Water Jet", "damage", 1.2, "mag", "enemy", 0, 0, "Pressurised splash.", "water", 1),
    Ability("rain_mend", "Rain Mend", "heal", 0.7, "mag", "all_allies", 3, 0, "Soft healing rain.", "water", 1),
    Ability("rock_toss", "Rock Toss", "damage", 1.5, "mag", "enemy", 1, 0, "Hurl a boulder.", "earth", 1),
    Ability("stone_skin", "Stone Skin", "guard", 0.0, "mag", "ally", 3, 2, "Harden an ally.", "earth", 1),
    Ability("gust", "Gust", "damage", 1.1, "mag", "enemy", 0, 0, "A biting wind.", "wind", 1),
    Ability("cutting_wind", "Cutting Wind", "damage", 0.75, "mag", "all_enemies", 2, 0, "Razor breeze.", "wind", 1),
]:
    register_ability(_s)

_MIX_KIND = {frozenset(["damage", "heal"]): "drain", frozenset(["damage", "guard"]): "poison",
             frozenset(["heal", "guard"]): "guard"}
_SUFFIX = {"damage": "Lance", "drain": "Siphon", "heal": "Mending", "guard": "Ward", "poison": "Blight"}
_AOE_SUFFIX = {"damage": "Burst", "drain": "Vortex", "heal": "Bloom", "guard": "Dome", "poison": "Cloud"}

CUSTOM: Dict[str, dict] = {}        # key -> serialisable record of fused spells (saved with the game)


def base_spells() -> List[Ability]:
    """Spells always on sale: every registered tier-1 elemental ability."""
    return [a for a in ABILITIES if a.tier == 1 and a.element]


def spell_cost(spell: Ability) -> Dict[str, int]:
    return dict(config.SPELL_LEARN_COST[min(3, max(1, spell.tier))])


def components_of(spell: Ability):
    return elements.components(spell.element)


def required_mastery(spell: Ability) -> int:
    return config.SPELL_TIER_MASTERY[min(3, max(1, spell.tier))]


def fused_key(a: str, b: str) -> str:
    return "fx_" + "__".join(sorted((a, b)))


def design_fusion(a: Ability, b: Ability, name: Optional[str] = None, creator: str = "") -> Ability:
    """Build (but don't register) the spell produced by fusing a and b."""
    if not a.element or not b.element:
        raise InvalidAction("Only elemental spells can be fused.")
    el = elements.combine(a.element, b.element)
    if el is None:
        raise InvalidAction(f"{elements.get(a.element).name} and {elements.get(b.element).name} "
                            f"have no known fusion.")
    kind = a.kind if a.kind == b.kind else _MIX_KIND.get(frozenset((a.kind, b.kind)), a.kind)
    aoe = a.target.startswith("all_") or b.target.startswith("all_")
    target = {"damage": "enemy", "drain": "enemy", "poison": "enemy", "heal": "ally", "guard": "ally"}[kind]
    if aoe:
        target = "all_enemies" if target == "enemy" else "all_allies"
    power = (a.power + b.power) / 2 * (1.15 if el.tier == 2 else 1.3)
    if kind in ("heal", "guard"):
        power = max(power, 0.0)
    suffix = (_AOE_SUFFIX if aoe else _SUFFIX)[kind]
    return Ability(fused_key(a.key, b.key), name or f"{el.name} {suffix}", kind, round(power, 2), "mag",
                   target, max(a.cooldown, b.cooldown) + 1, max(a.duration, b.duration, 2 if kind in
                   ("poison", "guard") else 0),
                   f"Fusion of {a.name} and {b.name}.", el.key, el.tier, creator)


def register_custom(ab: Ability) -> Ability:
    register_ability(ab)
    CUSTOM[ab.key] = asdict(ab)
    return ab


def custom_records() -> List[dict]:
    return list(CUSTOM.values())


def load_custom(records: List[dict]) -> None:
    for r in records:
        if r.get("element") in elements.ELEMENTS:
            register_custom(Ability(**r))


def forget_custom(key: str) -> None:
    CUSTOM.pop(key, None)
    ABILITIES.unregister(key)
