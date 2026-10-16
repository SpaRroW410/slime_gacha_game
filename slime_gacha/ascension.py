"""Slime ascension: rarity (white gel), stars (ascension stones), stone economy, merge stat-share and the chamber.

Rarity ladder: common > uncommon > rare > epic > legendary. Reaching a rarity costs white gel (10 / 100 / 1000 /
10000). Stars 1..5 cost ascension STONES (10 / 100 / 1000 / 10000 common-stone equivalents). Stones come in the same
five rarities; 100 stones of one rarity merge into 1 of the next, so one stone is worth 100^rarity commons.
"""
import random
from typing import Dict, List, Optional

from . import config
from .errors import InvalidAction

R = config.RARITIES


def stone_key(rarity: str) -> str:
    return f"stone_{rarity}"


def stone_value(rarity: str) -> int:
    return config.STONE_MERGE ** R.index(rarity)


def stone_total(wallet) -> int:
    """All stones the colony holds, in common-stone equivalents."""
    return sum(wallet.get(stone_key(r)) * stone_value(r) for r in R)


def next_rarity(rarity: str) -> Optional[str]:
    i = R.index(rarity)
    return R[i + 1] if i + 1 < len(R) else None


# ---- costs ------------------------------------------------------------------------------------------------------------
def rarity_cost(slime) -> Optional[int]:
    up = next_rarity(slime.rarity)
    return config.RARITY_ASCEND_GEL[up] if up else None


def star_cost(slime) -> Optional[int]:
    return config.STAR_ASCEND_STONES.get(slime.stars + 1)


def stones_invested(stars: int) -> int:
    return sum(v for k, v in config.STAR_ASCEND_STONES.items() if k <= stars)


# ---- stones: paying with change, merging, splitting ---------------------------------------------------------------------
def denominate(equiv: int) -> Dict[str, int]:
    """Common-stone equivalents -> the fewest stones, as {wallet key: count}."""
    out: Dict[str, int] = {}
    for r in reversed(R):
        v = stone_value(r)
        n, equiv = divmod(equiv, v)
        if n:
            out[stone_key(r)] = n
    return out


def pay_stones(wallet, need: int) -> None:
    """Spend `need` common-stone equivalents, cheapest stones first; change comes back in smaller stones."""
    if stone_total(wallet) < need:
        raise InvalidAction(f"Not enough ascension stones: need {need} (common equivalents), you hold "
                            f"{stone_total(wallet)}.")
    spent = 0
    for r in R:                                         # commons first, then ever bigger stones
        key, v = stone_key(r), stone_value(r)
        while wallet.get(key) > 0 and spent < need:
            wallet.add(key, -1)
            spent += v
    change = spent - need
    if change:
        wallet.add_many(denominate(change))


def merge_stones(wallet, rarity: str) -> int:
    """Combine as many 100s of `rarity` stones as possible into the next rarity. Returns how many were made."""
    up = next_rarity(rarity)
    if not up:
        raise InvalidAction("Legendary stones cannot be merged further.")
    n = wallet.get(stone_key(rarity)) // config.STONE_MERGE
    if n <= 0:
        raise InvalidAction(f"You need {config.STONE_MERGE} {rarity} stones for one {up} stone.")
    wallet.add(stone_key(rarity), -n * config.STONE_MERGE)
    wallet.add(stone_key(up), n)
    return n


def roll_stone(rng: random.Random) -> Dict[str, int]:
    """One stone drop from the Quarry (commons come in small handfuls)."""
    w = [config.STONE_RATES.get(r, 0.0) for r in R]
    r = rng.choices(R, w)[0]
    n = rng.randint(*config.STONE_COMMON_QTY) if r == "common" else 1
    return {stone_key(r): n}


# ---- merging -------------------------------------------------------------------------------------------------------------
def merge_share(growth: float) -> float:
    """Share of the donor's stat the target absorbs. 20% at zero merge growth, 18% once the attribute has grown 10%,
    ... never below a flat 1%. `growth` = merge bonus / the target's own base value (1.0 = +100%)."""
    return max(config.MERGE_SHARE_FLOOR, config.MERGE_STAT_SHARE - config.MERGE_SHARE_SLOPE * max(0.0, growth))


def absorb(target, donor) -> Dict[str, float]:
    """Add the donor's shared stats to the target; returns the gains."""
    tb, db = target.core_stats(), donor.core_stats()
    gains = {}
    for k, v in db.items():
        base = max(1e-9, tb[k])
        share = merge_share(target.merge_bonus.get(k, 0.0) / base)
        g = round(v * share, 2)
        target.merge_bonus[k] = round(target.merge_bonus.get(k, 0.0) + g, 2)
        gains[k] = g
    return gains


# ---- the destruction chamber ---------------------------------------------------------------------------------------------
def chamber_factor(level: int) -> float:
    return 0.6 + 0.1 * level


def chamber_yield(slime, level: int = 1) -> Dict[str, int]:
    """Gel and stones for a destroyed slime. More for higher rarity and stars."""
    idx = R.index(slime.rarity)
    f = chamber_factor(level)
    gel = int(config.CHAMBER_GEL_BASE * 10 ** idx * (1 + 0.5 * (slime.stars - 1)) * f)
    equiv = int((config.CHAMBER_STONE_BASE + 0.5 * stones_invested(slime.stars)) * (1 + idx) * f)
    out = {"white_gel": gel}
    out.update(denominate(equiv))
    return out
