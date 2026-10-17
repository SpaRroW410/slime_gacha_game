# Floor-50 playtest

Generated with `python3 tools/playtest.py` (seeded, repeatable). It answers: *how strong must a party be to win each floor
of the Hollow Descent, and how long does it take to get there?* The reference party is the conservative case: one each of
Barbarian, Ranger, Mage, Medic and Rogue with **no gear, relics, potions, elements, bonds or morale effects**, stars following
the rarity's star-level table, evolved to the stage its level allows, class proficiency 100 (capstones usable for legendaries).
"Min level" is the lowest party level with a >= 70% win chance over 12 seeded fights per level tested ("scouted" adds the
intel bonus). "Pit runs" is how many Gloop Pit depth-3 runs a party needs to reach that level from level 1 at the real wave XP
(2 game hours each); the Descent's own XP is not counted, so this overstates the grind a little.

## What the playtest found (and what was done)

1. **A real AI bug (fixed).** At the start of a fight every slime with a set-up skill (Mark Prey, Arcane Focus, Sacred Ward,
   Berserker's Oath ...) spent its first turn buffing while the foes wiped the party in round one. Set-up skills (buffs, marks,
   debuffs, oaths) are now skipped when the party would win in under about 2.5 rounds. Floor 47 needed level 93 before and ~60
   after, floor 41 74 -> 42, floor 18 30 -> 20.
2. **Floor threat was lumpy (fixed in part).** Monster families differ wildly (five Stone Giants were several times a normal
   floor). Each floor's threat, (sum of enemy HP) x (sum of enemy damage), is now pulled into a band around a curve
   (`config.FLOOR_THREAT_TARGET`, bands 0.8-1.25 for ordinary floors, 0.9-1.3 for bosses; the enemy mix is unchanged, only stats
   are rescaled). Floor 32 went from ~63-82 to ~45, floor 50 from ~78 to ~63 for the common party.
3. **Floor 50 is reachable.** A common party needs about level 63 (60 scouted), rare ~40, legendary ~22; none is unwinnable at level 100.
4. **Win rates are cliffs.** A party goes from 0% to 100% over two or three levels, and the late bosses (35, 40, 45, 50) sit at
   level ~52-63 for commons because levels 30 and 60 grant stars and the stage-2 multiplier: that is a design step, not a
   threat spike. Mean deviation of a floor from its neighbours is 0.16 (limit 0.22): `python3 tools/playtest.py --smoothness`.
5. **Enemy area attacks matter.** An area attack hits all five slimes, so a floor with four area users deals about twenty times
   a single hit per round. An "area-aware" threat measure did not predict the required level better than HP x damage, so the
   simple one is used.
6. **Time to floor 50 is long.** Common needs ~580 Pit runs (about 1,160 game hours, roughly 390 real hours at the x3 dungeon rate)
   to reach level 63 from scratch; rare ~1,450 runs; legendary ~2,700 runs to level 22, because of the x2-per-rarity XP rule. The
   Descent's own floor XP (about 4,100 per floor at 50) and Pit depth 4-5 shorten this, but the XP curve deserves a second look
   (see task 25).

## Tables (floors 1, 5, 10 ... 50; run with `--step 1` for every floor)

### Common

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~game hours |
|---|---|---|---|---|---|
| 1 |  | 2 | 1 | 0 | 1 |
| 5 | BOSS | 9 | 8 | 36 | 72 |
| 10 | BOSS | 11 | 11 | 53 | 107 |
| 15 | BOSS | 23 | 21 | 182 | 364 |
| 20 | BOSS | 30 | 30 | 272 | 545 |
| 25 | BOSS | 30 | 30 | 272 | 545 |
| 30 | BOSS | 31 | 31 | 284 | 568 |
| 35 | BOSS | 52 | 48 | 475 | 950 |
| 40 | BOSS | 60 | 57 | 550 | 1100 |
| 45 | BOSS | 61 | 60 | 560 | 1121 |
| 50 | BOSS | 63 | 60 | 581 | 1163 |

### Rare

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~game hours |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 6 | 5 | 60 | 121 |
| 10 | BOSS | 9 | 8 | 144 | 289 |
| 15 | BOSS | 16 | 15 | 391 | 782 |
| 20 | BOSS | 20 | 20 | 571 | 1142 |
| 25 | BOSS | 20 | 20 | 571 | 1142 |
| 30 | BOSS | 25 | 25 | 831 | 1662 |
| 35 | BOSS | 38 | 37 | 1383 | 2767 |
| 40 | BOSS | 40 | 40 | 1454 | 2909 |
| 45 | BOSS | 39 | 39 | 1420 | 2840 |
| 50 | BOSS | 40 | 40 | 1454 | 2909 |

### Legendary

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~game hours |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 1 | 1 | - | - |
| 10 | BOSS | 2 | 1 | 12 | 25 |
| 15 | BOSS | 5 | 5 | 158 | 316 |
| 20 | BOSS | 11 | 11 | 861 | 1722 |
| 25 | BOSS | 10 | 10 | 706 | 1412 |
| 30 | BOSS | 12 | 11 | 989 | 1979 |
| 35 | BOSS | 22 | 22 | 2714 | 5428 |
| 40 | BOSS | 22 | 22 | 2714 | 5428 |
| 45 | BOSS | 22 | 21 | 2714 | 5428 |
| 50 | BOSS | 22 | 22 | 2714 | 5428 |

## Follow-ups

- Re-tune Pit XP (or add depth-4/5 rewards) so reaching floor 50 takes weeks, not months, of play; decide how much of the climb should come from the Descent itself (task 25).
- Re-run this harness after every balance change and run `--smoothness` as the regression check.
- Playtest with gear, relics, elements and potions (the real game) and with `--rarity epic`.
