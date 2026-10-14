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


# ---- main dungeon: segments, deterministic floors and scouting intel ------------------------
def segment_of(floor: int) -> int:
    """Segment index (0-based): floors 1-5 are segment 0, 6-10 segment 1 ... each ends in a boss."""
    return (floor - 1) // config.MAIN_BOSS_EVERY


def segment_floors(seg: int) -> range:
    return range(seg * config.MAIN_BOSS_EVERY + 1, (seg + 1) * config.MAIN_BOSS_EVERY + 1)


def floor_plan(seed: int, floor: int, party_size: int) -> List[Enemy]:
    """The enemies of a floor are FIXED by the dungeon seed, so scouts report what is really down there."""
    return main_wave(floor, party_size, random.Random(seed * 7919 + floor))


def intel_level(knowledge: float) -> int:
    return sum(1 for t in config.INTEL_LEVELS if knowledge >= t)


def _counts(enemies: List[Enemy]) -> str:
    out: dict = {}
    for e in enemies:
        out[e.name] = out.get(e.name, 0) + 1
    return ", ".join(f"{n}x {name}" if n > 1 else name for name, n in out.items())


def intel_view(seed: int, seg: int, knowledge: float, party_size: int) -> List[dict]:
    """What the colony knows about a segment: more knowledge reveals more about each floor.
        >=20 enemy count & tier | >=40 enemy types & elements | >=60 boss identity |
        >=80 abilities, total HP, purple-gel odds | 100 weaknesses and loot outlook."""
    from . import elements
    lvl = intel_level(knowledge)
    rows = []
    for f in segment_floors(seg):
        enemies = floor_plan(seed, f, party_size)
        lines = []
        boss = is_boss_floor(f)
        if lvl >= 1:
            mobs = [e for e in enemies if e.key not in ("hollow_warden", "parched_king")] or enemies
            lines.append(f"{len(enemies)} foes, tier {max(e.tier for e in mobs)}" +
                         (" - a guardian waits" if boss else ""))
        else:
            lines.append("unknown")
        if lvl >= 2:
            lines.append("foes: " + _counts([e for e in enemies if e.tier < 4 and e.key != "hollow_warden"
                                             and e.key != "parched_king"] or enemies))
            els = sorted({e.element for e in enemies if e.element})
            lines.append("elements: " + (", ".join(elements.get(x).emoji + elements.get(x).name for x in els) or "none"))
        if lvl >= 3 and boss:
            b = enemies[0]
            lines.append(f"BOSS: {b.emoji}{b.name} ({elements.get(b.element).name if b.element else 'neutral'})")
        if lvl >= 4:
            abil = sorted({a for e in enemies for a in e.abilities})
            lines.append("abilities: " + ", ".join(abil))
            lines.append(f"total HP ~{int(sum(e.stats['hp'] for e in enemies))}, "
                         f"purple gel chance ~{max(e.purple_chance for e in enemies):.0%} per foe")
        if lvl >= 5:
            weak = {}
            for e in enemies:
                if e.element:
                    for a, d in elements.BEATS.items():
                        if d == e.element:
                            weak[a] = weak.get(a, 0) + 1
            best = max(weak, key=weak.get) if weak else None
            lines.append("weakness: " + (f"{elements.get(best).emoji}{elements.get(best).name} spells" if best
                                         else "none") +
                         f"; loot ~{sum(hi for e in enemies for (_, hi) in e.loot.values())} gel/essence max")
        rows.append(dict(floor=f, boss=boss, lines=lines))
    return rows
