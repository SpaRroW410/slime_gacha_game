"""Total power: one number for how strong a slime is, with the parts that make it up.

Stat power already carries class, level, rarity, stars, stage, gear, relics, potions and merges (they all live in
`max_stats`). On top of it count what the slime can DO - its skills (scaled by the stat they use, capstones and
spell forms count extra), its star attributes, elemental mastery, fighting styles and class proficiency - and then
multiply by the mood and morale the slime is in right now. It is a guide for comparing slimes and parties, not a
battle formula.
"""
from typing import Dict

from . import attributes, config, elements, spells
from .abilities import get_ability
from .social import SocialEngine

KIND_WEIGHT = {"damage": 1.0, "drain": 1.1, "poison": 0.8, "heal": 0.9, "guard": 0.5, "utility": 0.4}


def base_power(slime) -> float:
    s = slime.max_stats()
    return s["hp"] / 4 + s["atk"] + s["mag"] + s["defense"] + s["spd"] / 2


def total_power(slime) -> Dict[str, object]:
    """{"total", "multiplier", "parts": {...}} - parts are before the mood / morale multiplier."""
    st = slime.max_stats()
    base = base_power(slime)
    capstones = set(attributes.capstones(slime)) | ({attributes.hybrid_capstone(slime)} - {None})
    skills = 0.0
    for key in slime.known_abilities():
        ab = get_ability(key)
        stat = st.get(ab.stat, 0.0)
        pw = max(0.4, ab.power) if ab.kind in ("damage", "drain", "poison", "heal") else 0.6
        v = 0.25 * pw * stat * KIND_WEIGHT.get(ab.kind, 0.6)
        if key in capstones:
            v *= 2.0
        if ab.element and ab.tier >= 2:
            v *= 1 + 0.1 * spells.mutation_stage(ab, elements.slime_mastery(slime, ab.element))
        skills += v
    attrs = sum(a["value"] for a in attributes.star_attributes(slime)) * base * 0.5
    mastery = sum(elements.basic_level(slime, b) for b in slime.attuned) * 0.03 * base
    from . import sparring
    style = sum(sparring.style_levels(slime).values()) * 0.02 * base
    proficiency = base * slime.class_prof / 1000.0
    parts = dict(stats=base, skills=skills, attributes=attrs, mastery=mastery, styles=style, proficiency=proficiency)
    mult = slime.power_multiplier() * SocialEngine.morale_factor(slime.morale)
    return dict(total=round(sum(parts.values()) * mult, 1), multiplier=round(mult, 2),
                parts={k: round(v, 1) for k, v in parts.items()})


def display(total: float) -> int:
    """The three-digit number shown beside a slime: 1 to 999 on a square-root scale of total power."""
    return max(1, min(999, round(999 * (max(0.0, total) / config.POWER_DISPLAY_MAX) ** 0.5)))
