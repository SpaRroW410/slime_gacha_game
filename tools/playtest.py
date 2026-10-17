#!/usr/bin/env python3
"""Floor-50 playtest harness: how strong must a party be for each floor of the Hollow Descent, and how long does
that take to reach? Simulates seeded fights (no gear, no relics, no potions: the conservative case) and prints a
markdown report.

    python3 tools/playtest.py                 # default report to stdout
    python3 tools/playtest.py --rarity rare --trials 30 --out docs/PLAYTEST_F50.md
"""
import argparse
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import attributes, config, dungeon
from slime_gacha.battle import BattleSystem
from slime_gacha.gacha import GachaSystem
from slime_gacha.growth import add_xp
from slime_gacha.resources import ResourceManager
from slime_gacha.slime import Slime

CLASSES = ("barbarian", "ranger", "mage", "medic", "rogue")      # a balanced party of five
SEED = 7


def stars_for(rarity: str, level: int) -> int:
    lv = config.STAR_LEVELS[rarity]
    return 1 + sum(1 for t in lv if level >= t)


def make_party(gacha, rarity: str, level: int, stars=None):
    party = []
    for cls in CLASSES:
        s = gacha.make_slime(rarity, cls, stars=stars or stars_for(rarity, level))
        s.stage = 0 if level <= config.LEVEL_CAPS[0] else 1 if level <= config.LEVEL_CAPS[1] else 2
        s.level = level
        s.class_prof = 100.0
        s.hp = s.max_hp
        party.append(s)
    return party


def fight(floor: int, party, intel: float, rng_seed: int) -> bool:
    for s in party:
        s.hp = s.max_hp
        s.stamina_frac = 1.0
    bs = BattleSystem(random.Random(rng_seed), ResourceManager())
    info = dungeon.floor_info(SEED, floor, len(party))
    rep = bs.run(party, info.enemies, permadeath=True, synergy=intel, terrain=info.terrain)
    return rep.victory


def win_rate(floor, rarity, level, trials, intel):
    g = GachaSystem(ResourceManager(), random.Random(level * 1000 + floor))
    wins = 0
    for t in range(trials):
        party = make_party(g, rarity, level)
        wins += fight(floor, party, intel, t + 1)
    return wins / trials


def min_level(floor, rarity, trials, intel, target=0.7, cap=100):
    lo, hi = 1, cap
    if win_rate(floor, rarity, hi, trials, intel) < target:
        return None
    while lo < hi:                                   # win rate rises with level, so bisect
        mid = (lo + hi) // 2
        if win_rate(floor, rarity, mid, trials, intel) >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo


def pit_runs_to(level_from: int, level_to: int, rarity: str, depth: int = 3) -> float:
    """Pit runs a common-pace party needs to climb levels (uses the real wave XP)."""
    rng = random.Random(3)
    theme = dungeon.pit_theme(SEED, 0)
    total = 0.0
    for lv in range(level_from, level_to):
        waves = [sum(e.xp for e in dungeon.grind_wave(lv, depth, 5, rng, theme)) for _ in range(6)]
        per_run = statistics.mean(waves) * config.GRIND_XP_MULT * config.pit_xp_boost(lv)
        total += config.xp_to_next(lv, rarity) / max(1.0, per_run)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rarity", default="common", choices=config.RARITIES)
    ap.add_argument("--trials", type=int, default=16)
    ap.add_argument("--out", default="")
    ap.add_argument("--step", type=int, default=1, help="report every Nth floor (bosses always)")
    a = ap.parse_args()
    lines = [f"# Floor playtest ({a.rarity} party of {', '.join(CLASSES)}; no gear, relics or potions)", "",
             f"Minimum party level with a >= 70% chance to win each floor ({a.trials} seeded fights per level tested; "
             f"stars follow the {a.rarity} star-level table). Pit hours = game hours of Gloop Pit depth-3 runs "
             f"({config.GRIND_TICKS}h each) to reach that level from level 1.", "",
             "| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~game hours |",
             "|---|---|---|---|---|---|"]
    rows = []
    for f in range(1, dungeon.MAX_FLOOR + 1):
        boss = dungeon.is_boss_floor(f)
        if not (boss or f % a.step == 0 or f == 1):
            continue
        blind = min_level(f, a.rarity, a.trials, 1.0)
        scouted = min_level(f, a.rarity, a.trials, 1 + config.INTEL_POWER_BONUS)
        runs = pit_runs_to(1, blind, a.rarity) if blind else None
        rows.append((f, boss, blind, scouted, runs))
        lines.append(f"| {f} | {'BOSS' if boss else ''} | {blind if blind else '>100'} | {scouted if scouted else '>100'} | "
                     f"{int(runs) if runs else '-'} | {int(runs * config.GRIND_TICKS) if runs else '-'} |")
        print(lines[-1], file=sys.stderr)
    lv = [r[2] for r in rows if r[2]]
    lines += ["", "## Reading it", ""]
    jumps = [(rows[i][0], rows[i][2] - rows[i - 1][2]) for i in range(1, len(rows)) if rows[i][2] and rows[i - 1][2]
             and rows[i][2] - rows[i - 1][2] >= 12]
    lines.append(f"- Floor 50 needs level {rows[-1][2] or '>100'} unscouted ({rows[-1][3] or '>100'} scouted).")
    lines.append("- Floors whose requirement jumps by 12+ levels over the previous row: "
                 + (", ".join(f"{f} (+{j})" for f, j in jumps) or "none") + ".")
    unwinnable = [r[0] for r in rows if r[2] is None]
    lines.append("- Floors not winnable even at level 100: " + (", ".join(map(str, unwinnable)) or "none") + ".")
    text = "\n".join(lines) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
