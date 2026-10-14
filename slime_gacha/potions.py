"""Potions: brewed by a slime in the Alchemy Lab from herbs (dropped in the daily Pit and other dungeons).

Six kinds - stamina, vigor (HP), might (ATK), ironhide (DEF), arcane (MAG), swift (SPD) - in five grades. A potion
temporarily raises an attribute by 10/15/20/30/40%; a STAMINA potion raises max stamina and speeds its recovery.
The lab level caps the brewable grade.
"""
from dataclasses import dataclass
from typing import Dict

from . import config


@dataclass(frozen=True)
class PotionKind:
    key: str
    name: str
    emoji: str
    effect: str


KINDS: Dict[str, PotionKind] = {k.key: k for k in [
    PotionKind("stamina", "Stamina Potion", "🧪", "max stamina up, recovery much faster"),
    PotionKind("vigor", "Vigor Potion", "❤️", "max HP up"),
    PotionKind("might", "Might Potion", "💪", "attack up"),
    PotionKind("ironhide", "Ironhide Potion", "🛡️", "defense up"),
    PotionKind("arcane", "Arcane Potion", "🔮", "magic up"),
    PotionKind("swift", "Swift Potion", "💨", "speed up"),
]}


def key(kind: str, grade: int) -> str:
    return f"{kind}:{grade}"


def cost(grade: int) -> Dict[str, int]:
    c = {"herb": config.POTION_HERBS[grade - 1], "white_gel": config.POTION_GEL[grade - 1]}
    if config.POTION_ESSENCE[grade - 1]:
        c["essence"] = config.POTION_ESSENCE[grade - 1]
    return c


def bonus(grade: int) -> float:
    return config.POTION_BONUS[grade - 1]


def hours(grade: int) -> int:
    return config.POTION_HOURS_BASE + config.POTION_HOURS_GRADE * grade


def brew_hours(grade: int) -> int:
    return config.BREW_HOURS_PER_GRADE * grade


def success_chance(brewer, grade: int, lab_level: int) -> float:
    """The brewer's magic and a roomier lab help; a medic or necromancer has a knack."""
    mag = brewer.core_stats()["mag"]
    p = config.BREW_BASE_CHANCE + min(0.2, mag / 500) + 0.05 * (lab_level - grade) - 0.04 * (grade - 1)
    if brewer.archetype in ("medic", "necromancer"):
        p += 0.05
    return max(0.4, min(0.98, p))
