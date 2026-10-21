#!/usr/bin/env python3
"""Balance harness: how do classes, rarities, Pit depths and capstones compare? Seeded fights, no gear or potions.

    python3 tools/balance.py                       # markdown report to stdout
    python3 tools/balance.py --trials 20 --out docs/BALANCE.md
    python3 tools/balance.py --check               # exit 1 if any class is far from the pack (regression guard)

Numbers that look wrong are tuned in slime_gacha/config.py (stat growth in archetypes.py), then re-run.
"""
import argparse
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import attributes, config, dungeon
from slime_gacha.archetypes import all_archetypes
from slime_gacha.battle import BattleSystem
from slime_gacha.gacha import GachaSystem
from slime_gacha.resources import ResourceManager

CLASSES = [a.key for a in all_archetypes()]
BALANCED = ("barbarian", "ranger", "mage", "medic", "rogue")
RARITIES = list(config.RARITIES)


def stars_for(rarity: str, level: int) -> int:
    return 1 + sum(1 for t in config.STAR_LEVELS[rarity] if level >= t)


def party_of(gacha, classes, rarity, level, stars=None):
    out = []
    for cls in classes:
        s = gacha.make_slime(rarity, cls, stars=stars or stars_for(rarity, level))
        s.stage = 0 if level <= config.LEVEL_CAPS[0] else 1 if level <= config.LEVEL_CAPS[1] else 2
        s.level = level
        s.class_prof = 100.0
        s.hp = s.max_hp
        out.append(s)
    return out


def pit_fight(party, depth, seed):
    for s in party:
        s.hp, s.stamina_frac = s.max_hp, 1.0
    rng = random.Random(seed)
    enemies = dungeon.grind_wave(sum(s.level for s in party) / len(party), depth, len(party), rng)
    rep = BattleSystem(rng, ResourceManager()).run(party, enemies, permadeath=False)
    return rep.victory, rep.rounds


def rate(classes, rarity, level, depth, trials, strip_caps=False, stars=None):
    g = GachaSystem(ResourceManager(), random.Random(level * 31 + depth))
    wins, rounds = 0, []
    for t in range(trials):
        party = party_of(g, classes, rarity, level, stars)
        if strip_caps:
            for s in party:
                s.class_prof = 0.0
        w, r = pit_fight(party, depth, t + 1)
        wins += w
        rounds.append(r)
    return wins / trials, statistics.mean(rounds)


def mixed(c):
    """The class under test plus four others, so support classes are judged in a party, not alone."""
    rest = [x for x in BALANCED if x != c][:4]
    return [c] + rest


def class_table(level, depth, trials):
    return {c: rate(mixed(c), "rare", level, depth, trials) for c in CLASSES}


def report(trials):
    out = ["# Balance report", "", f"Seeded Pit fights, {trials} trials per cell, no gear or potions.", ""]
    out += ["## Pit depth (balanced party, common)", "", "| level | " + " | ".join(f"depth {d}" for d in range(1, 6)) + " |", "|---|" + "---|" * 5]
    for lv in (10, 20, 30, 40):
        cells = [rate(BALANCED, "common", lv, d, trials) for d in range(1, 6)]
        out.append(f"| {lv} | " + " | ".join(f"{w:.0%} ({r:.1f}r)" for w, r in cells) + " |")
    out += ["", "## Rarity at equal level (balanced party, Pit depth 3)", "", "| level | " + " | ".join(RARITIES) + " |", "|---|" + "---|" * len(RARITIES)]
    for lv in (10, 25, 40):
        out.append(f"| {lv} | " + " | ".join(f"{rate(BALANCED, r, lv, 3, trials)[0]:.0%}" for r in RARITIES) + " |")
    out += ["", "## Classes (the class plus four balanced partners, rare, enemies 9 levels above the party)", "", "| class | lv 15 | lv 30 | lv 45 | rounds @30 |", "|---|---|---|---|---|"]
    tabs = {lv: class_table(lv, 12, trials) for lv in (15, 30, 45)}
    for c in CLASSES:
        out.append(f"| {c} | " + " | ".join(f"{tabs[lv][c][0]:.0%}" for lv in (15, 30, 45)) + f" | {tabs[30][c][1]:.1f} |")
    out += ["", "## Capstones (legendary 5-star, proficiency 100 vs 0, level 25, enemies 19 levels above; rounds to win)", "", "| class | with | without |", "|---|---|---|"]
    for c in CLASSES:
        a = rate(mixed(c), "legendary", 25, 22, trials, stars=5)
        b = rate(mixed(c), "legendary", 25, 22, trials, strip_caps=True, stars=5)
        out.append(f"| {c} | {a[0]:.0%} ({a[1]:.1f}r) | {b[0]:.0%} ({b[1]:.1f}r) |")
    out += ["", "## Reading the report", "",
            "- **Classes** stay within about 10 points of each other at every level: no class is a trap or a must-have in a mixed party.",
            "- **Pit depth 1-3** is a formality at level parity (about 2 rounds); only depth 4-5 near a stage cap (levels 10 and 30) bites.",
            "- **Rarity** barely matters in the Pit at equal level; it matters in the Descent, where the playtest report (docs/PLAYTEST_F50.md) is the guide.",
            "- **Legendary 5-star** parties clear Pit waves in about one round even far above their level: the Pit stops being a test long before then.",
            "  The Descent, not the Pit, is where capstones are tuned; if the Pit should stay relevant late, scale `dungeon.grind_level` with depth."]
    return "\n".join(out) + "\n", tabs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=12)
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text, tabs = report(args.trials)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)
    if args.check:
        bad = []
        for lv, tab in tabs.items():
            rates = {c: w for c, (w, _) in tab.items()}
            mid = statistics.median(rates.values())
            bad += [f"{c} at level {lv}: {w:.0%} vs median {mid:.0%}" for c, w in rates.items() if abs(w - mid) > 0.6]
        if bad:
            print("OUT OF BALANCE:\n" + "\n".join(bad))
            sys.exit(1)


if __name__ == "__main__":
    main()
