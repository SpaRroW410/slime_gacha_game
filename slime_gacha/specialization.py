"""Specializations: hybrid classes born from cross-training.

A slime's class has a *primary* discipline (sword / archery / magic). If it trains hard in a different
discipline (style level >= 3) it can specialize: a swordslime that learns magic becomes a Battlemage, a mage that
learns the blade a Spellknight, and so on. A specialization is permanent, adds a stat shift (the secondary skill
lends strength to the other stats), a signature ability, and affinity (x1.5 style xp) in BOTH disciplines.

Resolution order: (archetype, secondary) overrides, then (primary, secondary). Extend with register_spec().
"""
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from . import config, sparring
from .abilities import Ability, register_ability
from .archetypes import get_archetype
from .errors import InvalidAction


@dataclass(frozen=True)
class Spec:
    key: str
    name: str
    emoji: str
    shifts: Dict[str, Tuple[str, float]]      # target stat -> (source stat, ratio)
    ability: str
    description: str = ""


SPECS: Dict[str, Spec] = {}
BY_PAIR: Dict[Tuple[str, str], str] = {}          # (primary discipline, secondary discipline) -> spec key
BY_CLASS: Dict[Tuple[str, str], str] = {}         # (archetype key, secondary discipline) -> spec key


def register_spec(spec: Spec, pair: Optional[Tuple[str, str]] = None, cls: Optional[Tuple[str, str]] = None) -> Spec:
    SPECS[spec.key] = spec
    if pair:
        BY_PAIR[pair] = spec.key
    if cls:
        BY_CLASS[cls] = spec.key
    return spec


def _ab(key, name, kind, power, stat, target, cd, desc, duration=0, *fxs):
    return register_ability(Ability(key, name, kind, power, stat, target, cd, duration, desc, fx=tuple(fxs)))


# signature skills (one per hybrid, usable as soon as the slime specializes)
_ab("arcane_strike", "Arcane Strike", "damage", 1.9, "mag", "enemy", 2, "Steel wrapped in spellfire; cuts through half of the foe's magic resistance.", 0, ("pierce", "resist", 0.5))
_ab("mana_cleave", "Mana Cleave", "damage", 1.4, "atk", "all_enemies", 3, "A glowing sweep that hits everyone, ignoring a third of their armor.", 0, ("pierce", "def", 0.33))
_ab("seeker_arrow", "Seeker Arrow", "damage", 2.0, "mag", "enemy", 3, "An arrow that never misses.", 0, ("nomiss",))
_ab("hex_shot", "Hexing Shot", "poison", 0.7, "atk", "enemy", 2, "A cursed bolt that festers and saps the foe's strength.", 3, ("debuff", "atk", 0.2, 3))
_ab("riposte", "Riposte", "damage", 1.4, "atk", "enemy", 1, "A lightning-fast counter-stab, then a counter stance for 2 turns.", 0, ("counter_self", 2, 0.8))
_ab("shield_volley", "Shield Volley", "damage", 1.1, "atk", "all_enemies", 3, "Arrows from behind a raised shield, which soaks damage.", 0, ("shield_self", 0.8))
_ab("holy_smite", "Smite", "drain", 1.3, "atk", "enemy", 2, "A blessed blow that heals the medic and the most wounded ally.", 0, ("heal_lowest", 0.5))
_ab("soul_cleave", "Soul Cleave", "drain", 1.5, "atk", "enemy", 2, "Cuts the life out of a foe and wraps the knight in a shield.", 0, ("shield_self", 0.5))
_ab("shadow_bolt", "Shadow Bolt", "damage", 1.8, "mag", "enemy", 2, "A knife of darkness that slows its target.", 0, ("debuff", "spd", 0.25, 2))

# hybrid capstones: defined at full strength, cast at up to HYBRID_CAPSTONE_MAX of it (config), less when the
# second discipline is neglected (see attributes.hybrid_scale)
HYBRID_CAPSTONES: Dict[str, Ability] = {}
for _spec, _a in dict(
    battlemage=_ab("overload", "Overload", "damage", 2.4, "mag", "all_enemies", 5, "Steel and spell burst together on every foe, cutting through magic resistance.", 0, ("pierce", "resist", 0.5)),
    spellknight=_ab("blade_of_ether", "Blade of Ether", "damage", 3.0, "atk", "enemy", 4, "A blade of pure ether: ignores magic resistance and part of the armor.", 0, ("pierce", "resist", 1.0), ("pierce", "def", 0.5)),
    arcane_archer=_ab("starseeker", "Starseeker", "damage", 2.6, "mag", "enemy", 4, "A star-tipped arrow that cannot miss and always crits.", 0, ("nomiss",), ("crit",)),
    hexshot=_ab("curse_barrage", "Curse Barrage", "damage", 1.0, "atk", "all_enemies", 5, "A barrage of cursed shots: two hits on every foe, each weakening it.", 0, ("hits", 2), ("debuff", "atk", 0.3, 3)),
    swashbuckler=_ab("duelists_flourish", "Duelist's Flourish", "utility", 0.0, "atk", "self", 5, "A showy stance: counter every blow and dodge more for 3 turns.", 0, ("counter_self", 3, 1.0), ("buff", "evasion", 0.3, 3)),
    shieldbow=_ab("fortress_volley", "Fortress Volley", "damage", 1.6, "atk", "all_enemies", 5, "Fire from behind a fortress of shields.", 0, ("shield_self", 1.5)),
    battle_medic=_ab("martyrs_smite", "Martyr's Smite", "damage", 2.2, "atk", "enemy", 4, "Strike a foe; the most wounded ally heals for the damage dealt.", 0, ("heal_lowest", 1.0)),
    death_knight=_ab("soul_reaver", "Soul Reaver", "drain", 2.4, "atk", "enemy", 4, "Reap a foe's life and wrap the knight in a shield.", 0, ("shield_self", 0.8)),
    shadowcaster=_ab("stolen_spell", "Stolen Spell", "utility", 0.0, "mag", "enemy", 5, "Copy the last skill a foe used, at the shadowcaster's strength.", 0, ("copy",)),
).items():
    HYBRID_CAPSTONES[_spec] = _a

register_spec(Spec("battlemage", "Battlemage", "🗡️✨", {"mag": ("atk", 0.5)}, "arcane_strike",
                   "Steel and spells in one swing."), pair=("sword", "magic"))
register_spec(Spec("spellknight", "Spellknight", "🔮⚔️", {"atk": ("mag", 0.5)}, "mana_cleave",
                   "A mage who learned to hit things."), pair=("magic", "sword"))
register_spec(Spec("arcane_archer", "Arcane Archer", "🏹✨", {"mag": ("atk", 0.5)}, "seeker_arrow",
                   "Every arrow hums with magic."), pair=("archery", "magic"))
register_spec(Spec("hexshot", "Hexshot", "🔮🏹", {"atk": ("mag", 0.5)}, "hex_shot",
                   "Curses delivered at range."), pair=("magic", "archery"))
register_spec(Spec("swashbuckler", "Swashbuckler", "🗡️🏹", {"spd": ("atk", 0.5)}, "riposte",
                   "Quick feet, quicker blade."), pair=("sword", "archery"))
register_spec(Spec("shieldbow", "Bulwark Archer", "🏹🛡️", {"defense": ("atk", 0.5)}, "shield_volley",
                   "Shoots from behind a shield."), pair=("archery", "sword"))
register_spec(Spec("battle_medic", "Battle Medic", "💚⚔️", {"atk": ("mag", 0.5)}, "holy_smite",
                   "Heals with one hand, hits with the other."), cls=("medic", "sword"))
register_spec(Spec("death_knight", "Death Knight", "💀⚔️", {"atk": ("mag", 0.4), "defense": ("mag", 0.3)},
                   "soul_cleave", "Necromancy with armor on."), cls=("necromancer", "sword"))
register_spec(Spec("shadowcaster", "Shadowcaster", "🗡️🌑", {"mag": ("atk", 0.5), "spd": ("atk", 0.2)},
                   "shadow_bolt", "A rogue who steals spells."), cls=("rogue", "magic"))


def primary_discipline(slime) -> str:
    return get_archetype(slime.archetype).discipline


def spec_for(slime, secondary: str) -> Optional[Spec]:
    key = BY_CLASS.get((slime.archetype, secondary)) or BY_PAIR.get((primary_discipline(slime), secondary))
    return SPECS.get(key) if key else None


def options(slime) -> list:
    """One row per other discipline: the spec it would give and whether the slime qualifies right now."""
    rows = []
    for d in sparring.DISCIPLINES:
        if d.key == primary_discipline(slime):
            continue
        sp = spec_for(slime, d.key)
        if not sp:
            continue
        lvl = sparring.style_level(slime, d.key)
        reason = ""
        if slime.spec:
            reason = "already specialized"
        elif lvl < config.SPEC_MIN_STYLE:
            reason = f"needs {d.style} level {config.SPEC_MIN_STYLE} (has {lvl})"
        elif slime.level < config.SPEC_MIN_LEVEL:
            reason = f"needs level {config.SPEC_MIN_LEVEL}"
        rows.append(dict(discipline=d.key, style=d.style, spec=sp, ok=not reason, reason=reason, level=lvl))
    return rows


def check(slime, discipline: str) -> Spec:
    for r in options(slime):
        if r["discipline"] == discipline:
            if not r["ok"]:
                raise InvalidAction(f"{slime.name} can't specialize yet: {r['reason']}.")
            return r["spec"]
    raise InvalidAction(f"No specialization exists for {slime.arch.name} + {discipline}.")


def apply_shifts(stats: Dict[str, float], spec_key: str) -> Dict[str, float]:
    """Add the specialization's stat shifts (computed from the stats BEFORE any shift)."""
    sp = SPECS.get(spec_key)
    if not sp:
        return stats
    base = dict(stats)
    for tgt, (src, ratio) in sp.shifts.items():
        stats[tgt] = round(stats[tgt] + base[src] * ratio, 1)
    return stats
