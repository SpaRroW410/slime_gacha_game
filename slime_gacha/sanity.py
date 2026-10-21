"""Sanity: a slime's mental reserve (docs: Guide > Slimes > Sanity).

Mood is how the needs feel right now; sanity is how much a slime can take. Hard things wear it down: a friend dying, being
knocked out, losing a battle, brawls, long miserable stretches. Rest, a calm home, the Hospital and a daily talk with the
Keeper build it back slowly. Low sanity CAPS the mood, so feeding and petting alone cannot make a broken slime happy, and a
very low one refuses dungeons and then work.

Rarer slimes have a bigger reserve and lose less from each blow (config.SANITY_MAX / SANITY_RESIST).
"""
from . import config


def cap(s) -> float:
    return float(config.SANITY_MAX[s.rarity])


def frac(s) -> float:
    return max(0.0, min(1.0, s.sanity / cap(s)))


def hit(s, amount: float) -> float:
    """Wear sanity down by `amount` (reduced for rarer slimes). Returns what was lost."""
    lost = min(s.sanity, amount * config.SANITY_RESIST[s.rarity])
    s.sanity -= lost
    return lost


def heal(s, amount: float) -> None:
    s.sanity = min(cap(s), s.sanity + amount)


def mood_cap(s) -> float:
    """The best mood the slime can reach with its sanity where it is: full sanity = no cap, empty = grumpy at best."""
    return config.SANITY_MOOD_FLOOR + (1 - config.SANITY_MOOD_FLOOR) * frac(s)


def label(s) -> str:
    f = frac(s)
    return "steady" if f >= .7 else "shaken" if f >= .4 else "frayed" if f >= .2 else "breaking"
