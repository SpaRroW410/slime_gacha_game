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
3. **Floor 50 is reachable.** (Re-run after the equal star levels and formations; 24 seeded fights per level.) A common party needs about level 57 (51 scouted), uncommon 50, rare 41, epic 31, legendary 25; none is unwinnable at level 100. Commons dropped from ~63 because every rarity now earns its stars at levels 10/25/50/80 (commons used to wait for 30/60/100).
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
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 8 | 7 | 24 | 16 |
| 10 | BOSS | 11 | 10 | 35 | 23 |
| 15 | BOSS | 18 | 18 | 59 | 39 |
| 20 | BOSS | 25 | 24 | 84 | 56 |
| 25 | BOSS | 25 | 25 | 84 | 56 |
| 30 | BOSS | 31 | 31 | 105 | 70 |
| 35 | BOSS | 45 | 45 | 154 | 102 |
| 40 | BOSS | 50 | 50 | 171 | 114 |
| 45 | BOSS | 49 | 49 | 168 | 112 |
| 50 | BOSS | 57 | 51 | 196 | 130 |

### Uncommon

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 6 | 6 | 26 | 17 |
| 10 | BOSS | 10 | 10 | 47 | 31 |
| 15 | BOSS | 15 | 15 | 73 | 49 |
| 20 | BOSS | 24 | 22 | 120 | 80 |
| 25 | BOSS | 19 | 18 | 94 | 63 |
| 30 | BOSS | 31 | 31 | 157 | 105 |
| 35 | BOSS | 44 | 42 | 225 | 150 |
| 40 | BOSS | 50 | 48 | 257 | 171 |
| 45 | BOSS | 43 | 40 | 220 | 147 |
| 50 | BOSS | 50 | 50 | 257 | 171 |

### Rare

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 5 | 4 | 28 | 18 |
| 10 | BOSS | 9 | 8 | 56 | 37 |
| 15 | BOSS | 13 | 12 | 84 | 56 |
| 20 | BOSS | 18 | 17 | 119 | 79 |
| 25 | BOSS | 16 | 14 | 105 | 70 |
| 30 | BOSS | 25 | 25 | 168 | 112 |
| 35 | BOSS | 32 | 32 | 217 | 144 |
| 40 | BOSS | 40 | 39 | 273 | 182 |
| 45 | BOSS | 35 | 34 | 238 | 158 |
| 50 | BOSS | 41 | 41 | 280 | 186 |

### Epic

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 2 | 2 | 8 | 5 |
| 10 | BOSS | 5 | 5 | 35 | 23 |
| 15 | BOSS | 11 | 11 | 87 | 58 |
| 20 | BOSS | 14 | 13 | 113 | 75 |
| 25 | BOSS | 12 | 11 | 96 | 64 |
| 30 | BOSS | 22 | 21 | 183 | 122 |
| 35 | BOSS | 31 | 31 | 262 | 175 |
| 40 | BOSS | 31 | 31 | 262 | 175 |
| 45 | BOSS | 31 | 31 | 262 | 175 |
| 50 | BOSS | 31 | 31 | 262 | 175 |

### Legendary

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 1 | 1 | - | - |
| 10 | BOSS | 1 | 1 | - | - |
| 15 | BOSS | 6 | 5 | 52 | 35 |
| 20 | BOSS | 10 | 10 | 94 | 63 |
| 25 | BOSS | 10 | 10 | 94 | 63 |
| 30 | BOSS | 12 | 11 | 115 | 77 |
| 35 | BOSS | 25 | 25 | 252 | 168 |
| 40 | BOSS | 27 | 26 | 273 | 182 |
| 45 | BOSS | 20 | 19 | 199 | 133 |
| 50 | BOSS | 25 | 25 | 252 | 168 |

## Time to floor 50 (Pit runs only, no gear)

| Rarity | Min level at floor 50 | Pit runs | ~real hours (x3) |
|---|---|---|---|
| Common | 57 (51 scouted) | ~196 | ~130 |
| Uncommon | 50 | ~257 | ~171 |
| Rare | 41 | ~280 | ~186 |
| Epic | 31 | ~262 | ~175 |
| Legendary | 25 | ~252 | ~168 |

About a week of continuous dungeon time for any rarity, as intended by task 25. With the one-day session cap (12 runs of 2 hours per session) that is roughly 8-12 farming sessions per rarity step.

## Follow-ups

- Smoothness regression (`--smoothness`): mean deviation 0.132 against the 0.22 limit, still passing after formations, equal star levels and the XP changes.
- Still to do: playtest **with gear, relics, elements and potions** (the real game); the harness covers the conservative no-gear case only.
- Decide how much of the climb should come from the Descent itself (its floor XP is small next to the Pit now).
- Re-run this harness after every balance change and run `--smoothness` as the regression check.
