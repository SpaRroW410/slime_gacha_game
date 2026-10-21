# Balance report

Seeded Pit fights, 12 trials per cell, no gear or potions.

## Pit depth (balanced party, common)

| level | depth 1 | depth 2 | depth 3 | depth 4 | depth 5 |
|---|---|---|---|---|---|
| 10 | 100% (2.3r) | 100% (2.4r) | 100% (2.9r) | 33% (4.0r) | 33% (6.7r) |
| 20 | 100% (2.5r) | 100% (2.8r) | 100% (2.8r) | 92% (2.8r) | 100% (3.1r) |
| 30 | 100% (2.2r) | 100% (2.2r) | 100% (2.2r) | 67% (3.3r) | 58% (3.3r) |
| 40 | 100% (2.2r) | 100% (2.4r) | 100% (2.8r) | 100% (2.6r) | 100% (2.8r) |

## Rarity at equal level (balanced party, Pit depth 3)

| level | common | uncommon | rare | epic | legendary |
|---|---|---|---|---|---|
| 10 | 100% | 100% | 100% | 100% | 100% |
| 25 | 100% | 100% | 100% | 100% | 100% |
| 40 | 100% | 100% | 100% | 100% | 100% |

## Classes (the class plus four balanced partners, rare, enemies 9 levels above the party)

| class | lv 15 | lv 30 | lv 45 | rounds @30 |
|---|---|---|---|---|
| barbarian | 100% | 75% | 92% | 2.8 |
| mage | 100% | 83% | 100% | 3.0 |
| medic | 100% | 83% | 100% | 2.8 |
| rogue | 100% | 83% | 92% | 2.8 |
| ranger | 100% | 83% | 92% | 2.8 |
| necromancer | 100% | 75% | 92% | 3.2 |
| bard | 100% | 75% | 100% | 3.3 |
| paladin | 100% | 83% | 92% | 2.6 |
| alchemist | 100% | 83% | 92% | 3.3 |
| druid | 100% | 83% | 100% | 3.4 |

## Capstones (legendary 5-star, proficiency 100 vs 0, level 25, enemies 19 levels above; rounds to win)

| class | with | without |
|---|---|---|
| barbarian | 100% (1.0r) | 100% (1.0r) |
| mage | 100% (1.0r) | 100% (1.0r) |
| medic | 100% (1.0r) | 100% (1.0r) |
| rogue | 100% (1.0r) | 100% (1.0r) |
| ranger | 100% (1.0r) | 100% (1.0r) |
| necromancer | 100% (1.3r) | 100% (1.3r) |
| bard | 100% (1.0r) | 100% (1.0r) |
| paladin | 100% (1.0r) | 100% (1.0r) |
| alchemist | 100% (1.0r) | 100% (1.1r) |
| druid | 100% (1.0r) | 100% (1.0r) |

## Reading the report

- **Classes** stay within about 10 points of each other at every level: no class is a trap or a must-have in a mixed party.
- **Pit depth 1-3** is a formality at level parity (about 2 rounds); only depth 4-5 near a stage cap (levels 10 and 30) bites.
- **Rarity** barely matters in the Pit at equal level; it matters in the Descent, where the playtest report (docs/PLAYTEST_F50.md) is the guide.
- **Legendary 5-star** parties clear Pit waves in about one round even far above their level: the Pit stops being a test long before then.
  The Descent, not the Pit, is where capstones are tuned; if the Pit should stay relevant late, scale `dungeon.grind_level` with depth.
