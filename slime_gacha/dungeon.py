"""Dungeons: wave generators layered on the BattleSystem.

Main dungeon (The Hollow Descent): endless floors, deliberately ROUGH, permadeath, purple gel is rare but
bosses are the best source. Grinding dungeon (The Gloop Pit): safe repeatable XP farm that scales to your
party's level (knocked-out slimes survive). Both only build lists of (scaled) Enemy templates; the fight
itself is BattleSystem.run. Add a new dungeon by writing another wave function + a Game method.
"""
import random
from dataclasses import replace
from typing import List

from . import config
from .battle import ENEMIES, Enemy


def scale_enemy(e: Enemy, stat_mult: float = 1.0, loot_mult: float = 1.0,
                purple_mult: float = 1.0, purple_cap: float = 1.0) -> Enemy:
    """Return a stronger/weaker copy of a template (same key, so names/letters still work)."""
    stats = dict(e.stats)
    for k in ("hp", "atk", "defense", "mag"):
        stats[k] = round(stats[k] * stat_mult, 1)
    stats["spd"] = round(stats["spd"] * (1 + (stat_mult - 1) * 0.3), 1)
    loot = {r: (int(lo * loot_mult), max(int(lo * loot_mult), int(round(hi * loot_mult))))
            for r, (lo, hi) in e.loot.items()}
    return replace(e, stats=stats, xp=max(1, int(e.xp * stat_mult)), loot=loot,
                   purple_chance=min(purple_cap, e.purple_chance * purple_mult))


def _tier_pool(tier: int) -> List[Enemy]:
    return [e for e in ENEMIES if e.tier == tier]


# ---- main dungeon ----------------------------------------------------------------------
def is_boss_floor(floor: int) -> bool:
    return floor % config.MAIN_BOSS_EVERY == 0


def main_wave(floor: int, party_size: int, rng: random.Random) -> List[Enemy]:
    tier = min(3, 1 + (floor - 1) // 4)
    mult = (1 + config.MAIN_STAT_STEP) ** (floor - 1)                  # compounding: gets nasty quickly
    loot = 1 + config.MAIN_LOOT_STEP * (floor - 1)
    purple = 1 + config.MAIN_PURPLE_STEP * (floor - 1)

    def mob():
        return scale_enemy(rng.choice(_tier_pool(tier)), mult, loot, purple, config.MAIN_PURPLE_CAP)

    if not is_boss_floor(floor):
        return [mob() for _ in range(party_size)]
    k = floor // config.MAIN_BOSS_EVERY
    if k == 1:
        boss = ENEMIES.get("hollow_warden")
    else:                                                             # the Parched King, stronger each cycle
        boss = scale_enemy(ENEMIES.get("parched_king"), 1 + 0.25 * (k - 2))
    return [boss] + [mob() for _ in range(2 * (party_size // 5))]


# ---- grinding dungeon --------------------------------------------------------------------
def grind_level(avg_level: float, depth: int) -> int:
    return max(1, int(round(avg_level)) + depth - 3)


def grind_wave(avg_level: float, depth: int, party_size: int, rng: random.Random) -> List[Enemy]:
    target = grind_level(avg_level, depth)
    tier = 1 if target <= 8 else 2 if target <= 20 else 3
    base = config.GRIND_TIER_BASE_LEVEL[tier]
    mult = max(0.6, 1 + config.GRIND_STAT_STEP * (target - base))
    xp_scale = 1 + 0.1 * (target - 1)                                  # deeper levels pay better
    out = []
    for _ in range(party_size):
        e = scale_enemy(rng.choice(_tier_pool(tier)), mult, config.GRIND_LOOT_MULT, 0.0)
        out.append(replace(e, xp=max(1, int(e.xp * xp_scale / mult))))
    return out
