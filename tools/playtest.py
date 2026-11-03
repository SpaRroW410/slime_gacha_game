#!/usr/bin/env python3
"""Floor-50 playtest harness: how strong must a party be for each floor of the Hollow Descent, and how long does
that take to reach? Simulates seeded fights (no gear, no relics, no potions: the conservative case) and prints a
markdown report.

    python3 tools/playtest.py                 # default report to stdout
    python3 tools/playtest.py --rarity rare --trials 30 --out /tmp/playtest.md   # then update docs/ROADMAP.md § 6
    python3 tools/playtest.py --smoothness    # regression check: fails if some floors wall their neighbours
"""
import argparse
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import attributes, config, dungeon, places
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


def smoothness(rarity: str = "common", seeds=range(1, 7), trials: int = 6):
    """How lumpy is the climb? For every floor, compare its required level with the median of its six neighbours.
    Returns (mean |log ratio|, 90th percentile, worst [(dev, seed, floor, level, neighbours)])."""
    import math
    devs, worst = [], []
    global SEED
    keep = SEED
    try:
        for seed in seeds:
            SEED = seed
            lv = {f: (min_level(f, rarity, trials, 1.0) or 100) for f in range(1, dungeon.MAX_FLOOR + 1)}
            for f in range(4, dungeon.MAX_FLOOR - 2):
                nb = sorted(lv[g] for g in range(f - 3, f + 4) if g != f)
                ref = nb[len(nb) // 2]
                d = abs(math.log(lv[f] / ref))
                devs.append(d)
                worst.append((d, seed, f, lv[f], ref))
    finally:
        SEED = keep
    worst.sort(reverse=True)
    return statistics.mean(devs), sorted(devs)[int(0.9 * len(devs))], worst[:5]


def pit_runs_to(level_from: int, level_to: int, rarity: str, depth: int = 3) -> float:
    """Pit runs a party of that rarity needs to climb levels, from the real reward rule (config.pit_xp_per_run)."""
    idx = config.RARITIES.index(rarity)
    total = 0.0
    for lv in range(level_from, level_to):
        need = config.xp_to_next(lv, rarity)
        total += need / config.pit_xp_per_run(need, idx, depth)
    return total


def real_hours(runs: float) -> float:
    """Real hours (live time at 1x) for that many Pit runs: each run is GRIND_TICKS hours inside, and time inside the Pit runs
    places.dilation("grind") times faster than the lobby clock."""
    return runs * config.GRIND_TICKS / places.dilation("grind")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rarity", default="common", choices=config.RARITIES)
    ap.add_argument("--trials", type=int, default=16)
    ap.add_argument("--out", default="")
    ap.add_argument("--step", type=int, default=1, help="report every Nth floor (bosses always)")
    ap.add_argument("--smoothness", action="store_true", help="check how lumpy the climb is (exit 1 if it is too lumpy)")
    a = ap.parse_args()
    if a.smoothness:
        mean, p90, worst = smoothness(a.rarity, trials=a.trials)
        print(f"mean deviation from neighbours {mean:.3f}, 90th percentile {p90:.3f} (limits 0.22 / 0.45)")
        for d, s, f, l, r in worst:
            print(f"  seed {s} floor {f}: level {l} vs neighbours' {r}")
        sys.exit(0 if mean <= 0.22 and p90 <= 0.45 else 1)
    lines = [f"# Floor playtest ({a.rarity} party of {', '.join(CLASSES)}; no gear, relics or potions)", "",
             f"Minimum party level with a >= 70% chance to win each floor ({a.trials} seeded fights per level tested; "
             f"stars follow the {a.rarity} star-level table). Pit runs = Gloop Pit depth-3 runs "
             f"({config.GRIND_TICKS} game hours each) to reach that level from level 1; real hours assume the Pit's x{places.dilation('grind'):g} dungeon time at live speed 1x.", "",
             "| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |",
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
                     f"{int(runs) if runs else '-'} | {int(real_hours(runs)) if runs else '-'} |")
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
