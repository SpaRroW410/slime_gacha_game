"""Potions: brewed by a slime in the Alchemy Lab from coloured herbs.

Four herbs - GREEN (health), RED (strength), BLUE (armor), YELLOW (stamina) - make the four basic potions
(vigor, might, ironhide, stamina). Two different herbs combine into a further-attribute potion:
    green + red    Bloodthirst  lifesteal            green + blue   Bulwark   damage taken down
    green + yellow Renewal      HP regeneration      red + blue     Arcane    magic and spell power
    red + yellow   Fury         crit chance / damage blue + yellow  Gale      speed and evasion
Grades 1-5 raise the bonus (10/15/20/30/40%) and the lab level caps the grade.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple

from . import config


@dataclass(frozen=True)
class PotionKind:
    key: str
    name: str
    emoji: str
    effect: str
    herbs: Tuple[str, ...]
    stats: Dict[str, float] = field(default_factory=dict)    # stat -> share of the bonus (multiplier on the stat)
    mods: Dict[str, float] = field(default_factory=dict)     # combat attribute -> share of the bonus (additive)


def _k(*a, **kw):
    k = PotionKind(*a, **kw)
    return k.key, k


KINDS: Dict[str, PotionKind] = dict([
    _k("vigor", "Vigor Potion", "❤️", "max HP up", ("green",), {"hp": 1.0}),
    _k("might", "Might Potion", "💪", "attack up", ("red",), {"atk": 1.0}),
    _k("ironhide", "Ironhide Potion", "🛡️", "defense up", ("blue",), {"defense": 1.0}),
    _k("stamina", "Stamina Potion", "🧪", "max stamina up, recovery much faster", ("yellow",)),
    _k("bloodthirst", "Bloodthirst Potion", "🩸", "lifesteal", ("green", "red"), {}, {"lifesteal": 0.25}),
    _k("bulwark", "Bulwark Potion", "🏰", "less damage taken", ("green", "blue"), {}, {"guard": 0.3}),
    _k("renewal", "Renewal Potion", "🌱", "regenerate HP every round", ("green", "yellow"), {}, {"regen": 0.15}),
    _k("arcane", "Arcane Potion", "🔮", "magic and spell power up", ("red", "blue"), {"mag": 1.0}, {"spell_power": 0.5}),
    _k("fury", "Fury Potion", "🔥", "crit chance and crit damage up", ("red", "yellow"), {},
       {"crit_rate": 0.3, "crit_dmg": 0.8}),
    _k("gale", "Gale Potion", "💨", "speed and evasion up", ("blue", "yellow"), {"spd": 1.0}, {"evasion": 0.3}),
])


def key(kind: str, grade: int) -> str:
    return f"{kind}:{grade}"


def herb_key(color: str) -> str:
    return f"herb_{color}"


def cost(kind: str, grade: int) -> Dict[str, int]:
    n = config.POTION_HERBS[grade - 1]
    herbs = KINDS[kind].herbs
    each = n if len(herbs) == 1 else max(1, round(n * config.POTION_COMBO_SHARE))
    c = {herb_key(h): each for h in herbs}
    c["white_gel"] = config.POTION_GEL[grade - 1] * len(herbs)
    if config.POTION_ESSENCE[grade - 1]:
        c["essence"] = config.POTION_ESSENCE[grade - 1] * len(herbs)
    return c


def herb_total(cost_: Dict[str, int]) -> int:
    return sum(v for k, v in cost_.items() if k.startswith("herb_"))


def bonus(grade: int) -> float:
    return config.POTION_BONUS[grade - 1]


def hours(grade: int) -> int:
    return config.POTION_HOURS_BASE + config.POTION_HOURS_GRADE * grade


def brew_hours(grade: int) -> int:
    return config.BREW_HOURS_PER_GRADE * grade


def stat_mult(buffs, stat: str) -> float:
    return 1 + sum(b["bonus"] * KINDS[b["kind"]].stats.get(stat, 0.0) for b in buffs if b["kind"] in KINDS)


def combat_mods(buffs) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for b in buffs:
        k = KINDS.get(b["kind"])
        if k:
            for m, v in k.mods.items():
                out[m] = out.get(m, 0.0) + b["bonus"] * v
    return out


def success_chance(brewer, grade: int, lab_level: int, kind: str = "") -> float:
    """The brewer's magic and a roomier lab help; a medic or necromancer has a knack; combos are fiddlier."""
    mag = brewer.core_stats()["mag"]
    p = config.BREW_BASE_CHANCE + min(0.2, mag / 500) + 0.05 * (lab_level - grade) - 0.04 * (grade - 1)
    if brewer.archetype in ("medic", "necromancer"):
        p += 0.05
    if kind in KINDS and len(KINDS[kind].herbs) > 1:
        p -= 0.05
    return max(0.4, min(0.98, p))
