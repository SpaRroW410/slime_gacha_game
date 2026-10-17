# Floor-50 playtest

Generated with `python3 tools/playtest.py` (seeded, repeatable). It answers: *how strong must a party be to win each floor
of the Hollow Descent, and how long does it take to get there?* The reference party is the conservative case: one each of
Barbarian, Ranger, Mage, Medic and Rogue with **no gear, relics, potions, elements, bonds or morale effects**, stars following
the rarity's star-level table, evolved to the stage its level allows, class proficiency 100 (capstones usable for legendaries).
"Min level" is the lowest party level with a >= 70% win chance over 12 seeded fights per level tested ("scouted" adds the
intel bonus). "Pit runs" is how many Gloop Pit depth-3 runs a party needs to reach that level from level 1 under the real reward rule
(`config.pit_xp_per_run`, 2 game hours each); "real hours" assumes the x3 dungeon rate. The Descent's own XP is not counted,
so this overstates the grind a little.

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
6. **Time to floor 50 (fixed, task 25).** Pit XP used to follow the *level*, so a legendary at level 22 earned tiny rewards
   against an XP bill 16x larger: common needed ~580 runs (~390 real hours at x3) and legendary ~2,700 runs. A won Pit run now
   pays the XP a level costs divided by the runs a level should take (`PIT_RUNS_PER_LEVEL` = 3.5 for a common, +50% per rarity
   step, deeper depths pay more: 0.6 / 0.8 / 1 / 1.3 / 1.7). Result for floor 50: common ~217 runs (~144 real hours),
   rare ~273 (~182 h), legendary ~220 (~147 h): about a week of continuous dungeon time for any rarity (live mode keeps parties
   working while the page is closed), instead of months.

## Tables (floors 1, 5, 10 ... 50; run with `--step 1` for every floor)

### Common

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |
|---|---|---|---|---|---|
| 1 |  | 2 | 1 | 3 | 2 |
| 5 | BOSS | 9 | 8 | 28 | 18 |
| 10 | BOSS | 11 | 11 | 35 | 23 |
| 15 | BOSS | 23 | 21 | 77 | 51 |
| 20 | BOSS | 30 | 30 | 101 | 67 |
| 25 | BOSS | 30 | 30 | 101 | 67 |
| 30 | BOSS | 31 | 31 | 105 | 70 |
| 35 | BOSS | 52 | 48 | 178 | 119 |
| 40 | BOSS | 60 | 57 | 206 | 137 |
| 45 | BOSS | 61 | 60 | 210 | 140 |
| 50 | BOSS | 63 | 60 | 217 | 144 |

### Rare

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 6 | 5 | 35 | 23 |
| 10 | BOSS | 9 | 8 | 56 | 37 |
| 15 | BOSS | 16 | 15 | 105 | 70 |
| 20 | BOSS | 20 | 20 | 133 | 88 |
| 25 | BOSS | 20 | 20 | 133 | 88 |
| 30 | BOSS | 25 | 25 | 168 | 112 |
| 35 | BOSS | 38 | 37 | 259 | 172 |
| 40 | BOSS | 40 | 40 | 273 | 182 |
| 45 | BOSS | 39 | 39 | 266 | 177 |
| 50 | BOSS | 40 | 40 | 273 | 182 |

### Legendary

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 1 | 1 | - | - |
| 10 | BOSS | 2 | 1 | 10 | 7 |
| 15 | BOSS | 5 | 5 | 42 | 28 |
| 20 | BOSS | 11 | 11 | 105 | 70 |
| 25 | BOSS | 10 | 10 | 94 | 63 |
| 30 | BOSS | 12 | 11 | 115 | 77 |
| 35 | BOSS | 22 | 22 | 220 | 147 |
| 40 | BOSS | 22 | 22 | 220 | 147 |
| 45 | BOSS | 22 | 21 | 220 | 147 |
| 50 | BOSS | 22 | 22 | 220 | 147 |

## Follow-ups

- Decide how much of the climb should come from the Descent itself (its floor XP is small next to the Pit now).
- Re-run this harness after every balance change and run `--smoothness` as the regression check.
- Playtest with gear, relics, elements and potions (the real game) and with `--rarity epic`.
