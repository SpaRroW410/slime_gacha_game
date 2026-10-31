"""Passive skills: perks a slime earns by mastering something. They are always on (nothing to cast or equip) and show on the
slime's Fight tab, locked until earned with what it takes to unlock them.

A `Passive` is data: a key, a name, a description, a plain-words requirement and a test `earned(slime)`. Add one with
register_passive(...); nothing else needs to change for it to show up and be asked about (`has(slime, key)`).

The first one is TAILWIND: a slime that has mastered the wind element to the top level hastens a rescue party it joins
(Game.rescue_speed).  More passives for other slimes are on the roadmap (docs/ROADMAP.md, § 2).
"""
from dataclasses import dataclass
from typing import Callable, List

from . import config, elements
from .registry import Registry


@dataclass(frozen=True)
class Passive:
    key: str
    name: str
    emoji: str
    desc: str                              # what it does
    need: str                              # what it takes, in plain words
    earned: Callable[[object], bool]       # does this slime have it?


PASSIVES: "Registry[Passive]" = Registry("passive")


def register_passive(p: Passive) -> Passive:
    return PASSIVES.register(p, p.key)


def max_mastery() -> int:
    return len(config.MASTERY_XP)


def has(slime, key: str) -> bool:
    return key in PASSIVES and PASSIVES.get(key).earned(slime)


def earned(slime) -> List[Passive]:
    return [p for p in PASSIVES if p.earned(slime)]


register_passive(Passive(
    "tailwind", "Tailwind", "🌪️",
    f"Hastens a rescue party it goes with: the way to stranded scouts is {round(config.RESCUE_TAILWIND_SPEED * 100)}% shorter "
    f"(up to {round(config.RESCUE_TAILWIND_MAX * 100)}% with more than one).",
    "Master the wind element to the top level (level 8: 5 stars, attuned to wind).",
    lambda s: elements.basic_level(s, "wind") >= max_mastery()))
