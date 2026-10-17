"""Sparring: slimes pit themselves against each other to develop a fighting STYLE (not XP).

Three disciplines (arenas): Blade Yard (sword), Archery Range, Mana Pool (magic). A spar is a non-lethal duel:
the loser is left at 1 HP (the Rest Area heals them), nobody gains XP, both gain style XP (winner more, your
class's own discipline more). Style levels give permanent combat perks:
    sword   +3%/lvl attack-stat damage, -2%/lvl damage taken
    archery +2%/lvl crit chance, +3%/lvl speed
    magic   +3%/lvl magic damage & healing
The Training Grounds building caps how high a style can go and boosts style XP. Sparring also builds bonds.
"""
import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from . import config
from .archetypes import get_archetype
from .errors import InvalidAction
from .registry import Registry


@dataclass(frozen=True)
class Discipline:
    key: str
    name: str            # the arena
    emoji: str
    style: str           # the fighting style it teaches
    perk: str
    description: str = ""


DISCIPLINES: "Registry[Discipline]" = Registry("discipline")


def register_discipline(d: Discipline) -> Discipline:
    return DISCIPLINES.register(d, d.key)


register_discipline(Discipline("sword", "Blade Yard", "⚔️", "Swordsmanship",
                               "+3% attack damage, -2% damage taken per level",
                               "Wooden swords, bruised egos."))
register_discipline(Discipline("archery", "Archery Range", "🏹", "Marksmanship",
                               "+2% crit, +3% speed per level", "Moving targets. Mind the fingers."))
register_discipline(Discipline("magic", "Mana Pool", "🔮", "Spellcraft",
                               "+3% magic damage & healing per level",
                               "Duels where everybody glows."))


def style_level(slime, discipline: str) -> int:
    xp = slime.style_xp.get(discipline, 0)
    return sum(1 for t in config.STYLE_XP if xp >= t)


def style_levels(slime) -> Dict[str, int]:
    return {d.key: style_level(slime, d.key) for d in DISCIPLINES}


def style_label(slime) -> str:
    lv = style_levels(slime)
    best = max(lv, key=lv.get)
    return f"{DISCIPLINES.get(best).style} {lv[best]}" if lv[best] else "untrained"


def gain_style_xp(slime, discipline: str, amount: float, cap_level: int) -> int:
    """Add style xp (clamped at the building's level cap). Returns new level."""
    top = config.STYLE_XP[cap_level - 1]
    slime.style_xp[discipline] = round(min(top, slime.style_xp.get(discipline, 0) + amount), 2)
    return style_level(slime, discipline)


TRAINABLE_STATES = ("idle", "sleeping", "working")


def check_ready(slime) -> None:
    if slime.state not in TRAINABLE_STATES or slime.in_dungeon:       # a sleeper can be woken, a worker pulled off the job
        raise InvalidAction(f"{slime.name} is {slime.in_dungeon and 'inside a dungeon' or slime.state}, not available.")
    if slime.grounded:
        raise InvalidAction(f"{slime.name} is grounded after a brawl. Mediate first.")
    if slime.needs.get("energy") < config.TASK_MIN_ENERGY:
        raise InvalidAction(f"{slime.name} is too tired to spar.")
    if slime.hp < slime.max_hp * config.SPAR_MIN_HP:
        raise InvalidAction(f"{slime.name} is too hurt to spar - visit the Rest Area.")


def check_ready_basic(slime) -> None:
    """A drill's gate: like sparring, but a wounded slime may still drill (for less)."""
    if slime.state not in TRAINABLE_STATES or slime.in_dungeon:
        raise InvalidAction(f"{slime.name} is {slime.in_dungeon and 'inside a dungeon' or slime.state}, not available.")
    if slime.grounded:
        raise InvalidAction(f"{slime.name} is grounded after a brawl. Mediate first.")
    if slime.needs.get("energy") < config.TASK_MIN_ENERGY:
        raise InvalidAction(f"{slime.name} is too tired.")


def style_xp_for(slime, discipline: str, won: Optional[bool], grounds_mult: float, dummy: bool = False) -> float:
    xp = config.SPAR_STYLE_XP * grounds_mult
    if get_archetype(slime.archetype).discipline == discipline or slime.spec_disc == discipline:
        xp *= config.STYLE_AFFINITY_MULT
    if won:
        xp *= config.SPAR_WINNER_MULT
    if dummy:
        xp *= config.SPAR_DUMMY_MULT
    return xp
