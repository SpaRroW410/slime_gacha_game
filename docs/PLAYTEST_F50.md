# Floor-50 playtest

Generated with `python3 tools/playtest.py` (seeded, repeatable). It answers: *how strong must a party be to win each floor
of the Hollow Descent, and how long does it take to get there?* The reference party is the conservative case: one each of
Barbarian, Ranger, Mage, Medic and Rogue with **no gear, relics, potions, elements, bonds or morale effects**, stars following
the rarity's star-level table, evolved to the stage its level allows, class proficiency 100 (capstones usable for legendaries).
"Min level" is the lowest party level with a >= 70% win chance over 12 seeded fights per level tested ("scouted" adds the +
intel bonus). "Pit runs" is how many Gloop Pit depth-3 runs a party needs to reach that level from level 1 at the real wave XP
(2 game hours each); the Descent's own XP is not counted, so this overstates the grind a little.

## What the playtest found

1. **A real AI bug (fixed).** At the start of a fight every slime with a set-up skill (Mark Prey, Arcane Focus, Sacred Ward,
   Berserker's Oath ...) spent its first turn buffing while the foes wiped the party in round one. Floors with several area
   attackers (five Stone Giants, four Ash Drakes) were far harder than their stats suggest. Set-up skills (buffs, marks, debuffs,
   oaths) are now skipped when the party would win in under about 2.5 rounds. Effect on the common party: floor 47 needed
   level 93 before and 60 after, floor 41 74 -> 42, floor 18 30 -> 20, floor 50 73 -> 78 (bosses now fight a longer, fairer duel).
2. **Floor 50 is reachable.** Unscouted it needs level ~78 for common slimes (69 scouted), ~43 for rare, ~22 for legendary. All within the
   level-100 cap, none unwinnable.
3. **Win rates are cliffs.** A party goes from 0% to 100% over two or three levels, so a floor is either "walk through" or
   "wall". The remaining walls: floor 32 (~63), the bosses on 35 / 40 / 45 (~60-64) and floor 50 (~78). Several are stage and star
   thresholds (levels 30 and 60 grant stars and the stage-2 multiplier) rather than pure difficulty.
4. **Enemy area attacks drive the spikes.** An area attack hits all five slimes, so a floor with four area users deals about
   twenty times a single hit per round. The "threat" of a floor is not just HP x damage: it also depends on how many enemies
   have area skills (see follow-ups).
5. **Time to floor 50 is long.** Common needs ~730 Pit runs (about 1,450 game hours, roughly 480 real hours at the x3 dungeon rate)
   to reach level 78 from scratch; rare ~1,570 runs; legendary ~2,700 runs to level 22, because of the x2-per-rarity XP rule. The
   Descent's own floor XP (about 4,100 per floor at 50) and Pit depth 4-5 shorten this, but the XP curve deserves a second look.

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
| 35 | BOSS | 60 | 60 | 550 | 1100 |
| 40 | BOSS | 60 | 59 | 550 | 1100 |
| 45 | BOSS | 64 | 61 | 590 | 1181 |
| 50 | BOSS | 78 | 69 | 726 | 1453 |

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
| 35 | BOSS | 40 | 40 | 1454 | 2909 |
| 40 | BOSS | 40 | 40 | 1454 | 2909 |
| 45 | BOSS | 40 | 40 | 1454 | 2909 |
| 50 | BOSS | 43 | 40 | 1570 | 3140 |

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
| 35 | BOSS | 24 | 23 | 3142 | 6285 |
| 40 | BOSS | 22 | 22 | 2714 | 5428 |
| 45 | BOSS | 22 | 22 | 2714 | 5428 |
| 50 | BOSS | 22 | 22 | 2714 | 5428 |

## Follow-ups

- Smooth floor threat with an area-attack-aware measure (or cap area users per floor) so floors 32, 35, 40, 45 do not wall a party that clears their neighbours.
- Re-tune Pit XP (or add depth-4/5 rewards) so reaching floor 50 takes weeks, not months, of play; decide how much of the climb should come from the Descent itself.
- Re-run this harness after every balance change; add a regression check that no floor is more than ~15 levels above its neighbours for the reference party.
- Playtest with gear, relics, elements and potions (the real game) and with `--rarity epic`.
