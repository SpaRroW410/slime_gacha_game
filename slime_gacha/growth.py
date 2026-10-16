"""Growth: XP/levelling, evolution and merging."""
from typing import List

from . import config
from .ascension import absorb
from .abilities import get_ability
from .errors import InvalidAction
from .resources import ResourceManager


def add_xp(slime, amount: int) -> List[str]:
    """Give XP, level up as needed (respecting the stage cap). Returns log lines."""
    log = []
    amount = int(amount)
    if amount <= 0:
        return log
    slime.total_xp += amount
    slime.xp += amount
    while slime.level < slime.level_cap and slime.xp >= slime.xp_needed(slime.level):
        slime.xp -= slime.xp_needed(slime.level)
        old_max = slime.max_hp
        slime.level += 1
        slime.hp += slime.max_hp - old_max            # gain the new max HP
        slime.needs.add("esteem", 15)
        log.append(f"⬆ {slime.name} reached level {slime.level}!")
        for lvl, key in slime.arch.abilities.items():
            if lvl == slime.level:
                log.append(f"   {slime.name} learned {get_ability(key).name}!")
    if slime.level >= slime.level_cap:
        slime.xp = min(slime.xp, slime.xp_needed(slime.level) - 1)   # parked at cap
    return log


def lose_xp(slime, fraction: float) -> int:
    """Lose `fraction` of the xp needed for the next level. Can drop one level (never below 1) but not further.
    Returns the xp actually lost (lifetime xp shrinks too)."""
    want = int(slime.xp_needed(slime.level) * fraction)
    lost = 0
    if slime.xp >= want:
        slime.xp -= want
        lost = want
    elif slime.level > 1:                       # slide back into the previous level
        lost = slime.xp
        slime.level -= 1
        slime.xp = max(0, slime.xp_needed(slime.level) - (want - lost))
        lost = want
        slime.hp = min(slime.hp, slime.max_hp)
    else:
        lost, slime.xp = slime.xp, 0
    slime.total_xp = max(0, slime.total_xp - lost)
    return lost


def can_evolve(slime) -> bool:
    return slime.level >= slime.level_cap and slime.stage < len(config.LEVEL_CAPS) - 1


def evolve_cost(slime) -> int:
    return config.EVOLVE_ESSENCE_BASE * (slime.stage + 1)


def evolve(slime, wallet: ResourceManager) -> List[str]:
    if slime.busy:
        raise InvalidAction(f"{slime.name} is away ({slime.state}).")
    if not can_evolve(slime):
        raise InvalidAction(f"{slime.name} must reach the level cap ({slime.level_cap}) "
                            f"and have a further stage to evolve.")
    wallet.spend("essence", evolve_cost(slime))
    old = slime.max_hp
    slime.stage += 1
    slime.hp += slime.max_hp - old
    slime.needs.add("esteem", 30)
    log = [f"🌟 {slime.name} evolved into a {slime.title()}!"]
    ab = slime.arch.evolve_abilities.get(slime.stage)
    if ab:
        log.append(f"   New ability: {get_ability(ab).name}")
    return log


def merge_gain(target, donor, compat: int = 0) -> int:
    """XP the target receives: only what the donor collected, swung +/-25% by how compatible the two are."""
    gain = donor.total_xp * config.MERGE_XP_RATIO
    gain *= 1 + config.MERGE_COMPAT_SWING * max(-100, min(100, compat)) / 100.0
    return int(gain)


def merge(target, donor, compat: int = 0) -> List[str]:
    """Consume `donor` into `target`. The caller removes the donor from the roster."""
    if target is donor:
        raise InvalidAction("A slime can't merge with itself.")
    for s in (target, donor):
        if s.busy:
            raise InvalidAction(f"{s.name} is away ({s.state}).")
    gain = merge_gain(target, donor, compat)
    target.merged += 1
    stats = absorb(target, donor)
    log = [f"🫧 {donor.name} melts into {target.name}, who absorbs {gain} XP (what {donor.name} had collected) and "
           + ", ".join(f"+{v:g} {k}" for k, v in stats.items() if v) + "."]
    log += add_xp(target, gain)
    if target.level >= target.level_cap:
        log.append(f"   {target.name} is at the level cap - consider evolving.")
    return log
