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


# ---- mutation: a fused spell changes form as its caster's mastery of the spell's element grows -------------------
# Stage 1 comes MUTATION_STEPS[0] levels above the mastery needed to cast it, stage 2 comes MUTATION_STEPS[1] above.
# Each form adds effects (the mechanics of fx.py) and a little power; the forms belong to the element, not the caster.
MUTATION_STEPS = (1, 3)
MUTATION_POWER = (1.0, 1.1, 1.25)
STAGE_NAMES = ("", "Awakened ", "Ascendant ")

MUTATIONS: Dict[str, tuple] = {            # element -> (stage 1, stage 2) as (description, fx added)
    "steam": (("Scalding: the target's attack falls.", (("debuff", "atk", 0.15, 2),)),
              ("Scalding: attack falls further and the foe is left bleeding.", (("debuff", "atk", 0.25, 3), ("bleed", 2, 0.15)))),
    "lava": (("Molten: leaves the foe burning (bleed).", (("bleed", 3, 0.25),)),
             ("Molten: a deeper burn that ignores a third of armor.", (("bleed", 3, 0.35), ("pierce", "def", 0.33)))),
    "lightning": (("Forked: pierces a third of the foe's armor.", (("pierce", "def", 0.33),)),
                  ("Forked: pierces half the armor and may stun.", (("pierce", "def", 0.5), ("stun", 0.25)))),
    "mud": (("Clinging: slows the target.", (("debuff", "spd", 0.25, 2),)),
            ("Clinging: slows harder, longer and softens armor.", (("debuff", "spd", 0.35, 3), ("debuff", "defense", 0.15, 3)))),
    "ice": (("Frostbite: a chance to freeze (stun) the target.", (("stun", 0.25),)),
            ("Frostbite: a stronger chance to freeze and a slow.", (("stun", 0.4), ("debuff", "spd", 0.2, 2)))),
    "sand": (("Blinding: the target's attack falls.", (("debuff", "atk", 0.2, 2),)),
             ("Blinding: attack falls, and the target cannot dodge it.", (("debuff", "atk", 0.3, 3), ("nomiss",)))),
    "plasma": (("Searing: pierces half the target's magic resistance.", (("pierce", "resist", 0.5),)),
               ("Searing: ignores all magic resistance and always crits.", (("pierce", "resist", 1.0), ("crit",)))),
    "storm": (("Tempest: strikes twice.", (("hits", 2),)),
              ("Tempest: strikes three times, each blow may stun.", (("hits", 3), ("stun", 0.15)))),
    "obsidian": (("Glassy: the caster gains a shield.", (("shield_self", 0.5),)),
                 ("Glassy: a thick shield and a counter stance.", (("shield_self", 0.9), ("counter_self", 2, 0.6)))),
    "inferno": (("Raging: leaves the foe burning.", (("bleed", 3, 0.3),)),
                ("Raging: a ferocious burn and the target takes extra damage.", (("bleed", 3, 0.4), ("mark", 2, 0.15)))),
    "blizzard": (("Whiteout: may freeze and slows.", (("stun", 0.2), ("debuff", "spd", 0.2, 2))),
                 ("Whiteout: freezes often and exposes the target.", (("stun", 0.35), ("mark", 2, 0.15)))),
    "crystal": (("Faceted: the caster gains a shield.", (("shield_self", 0.6),)),
                ("Faceted: a thick shield that reflects blows.", (("shield_self", 1.0), ("counter_self", 2, 0.5)))),
    "sandstorm": (("Scouring: slows and weakens the target.", (("debuff", "spd", 0.2, 2), ("debuff", "atk", 0.15, 2))),
                  ("Scouring: strikes twice and strips defences.", (("hits", 2), ("debuff", "defense", 0.2, 3)))),
}
_SUPPORT_FORMS = (("Purifying: also cleanses poison, bleeding and curses.", (("cleanse",),)),
                  ("Overflowing: cleanses, and healing beyond full health becomes a shield.", (("cleanse",), ("overheal",))))


def _forms(ab: Ability):
    if ab.tier < 2 or not ab.element:
        return None
    if ab.kind in ("heal", "guard"):
        return _SUPPORT_FORMS
    return MUTATIONS.get(ab.element)


def mutation_levels(ab: Ability) -> List[int]:
    """Mastery levels at which the spell changes form (empty for spells that do not mutate)."""
    if not _forms(ab):
        return []
    base = required_mastery(ab)
    return [min(8, base + s) for s in MUTATION_STEPS]


def mutation_stage(ab: Ability, mastery: int) -> int:
    return sum(1 for need in mutation_levels(ab) if mastery >= need)


def mutate(ab: Ability, mastery: int) -> Ability:
    """The form `ab` takes for a caster with this mastery of its element (the base spell below stage 1)."""
    forms = _forms(ab)
    st = mutation_stage(ab, mastery) if forms else 0
    if not st:
        return ab
    extra = tuple(f for stage in forms[:st] for f in stage[1] if f not in ab.fx)
    # a stage-2 form replaces the stage-1 version of the same effect rather than stacking both
    kept = {(f[:2] if f[0] in ("debuff", "buff", "pierce") else f[:1]): f for f in extra}
    return replace(ab, name=STAGE_NAMES[st] + ab.name, power=round(ab.power * MUTATION_POWER[st], 3),
                   fx=tuple(ab.fx) + tuple(kept.values()))


def mutation_view(ab: Ability) -> List[dict]:
    forms = _forms(ab)
    if not forms:
        return []
    return [dict(stage=i + 1, mastery=need, name=(STAGE_NAMES[i + 1] + ab.name).strip(), power=round(ab.power * MUTATION_POWER[i + 1], 2),
                 desc=forms[i][0]) for i, need in enumerate(mutation_levels(ab))]
