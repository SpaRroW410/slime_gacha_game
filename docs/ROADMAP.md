# Roadmap & Checklist

Legend: `[x]` done · `[ ]` todo

## M0 — Foundations (docs & scaffolding)
- [x] README
- [x] Story / lore (`STORY.md`)
- [x] Software design document (`SDD.md`)
- [x] Roadmap (this file)
- [x] Package skeleton, registry, config

## M1 — Core model
- [x] Slime, Stats, Needs, Personality
- [x] Archetype registry + 6 starting classes
- [x] Ability registry + built-in abilities
- [x] ResourceManager
- [x] JSON save / load

## M2 — Gacha
- [x] Rarity tiers + rates
- [x] Pity system (epic 10 / legendary 50)
- [x] Single and ×10 pulls
- [x] Rarity/class stat scaling with per-slime variance

## M3 — Living slimes (AI)
- [x] Maslow needs engine (energy, food, safety, belonging, esteem)
- [x] Sleep cycle (auto-sleep / wake / manual)
- [x] Feeding (auto & manual)
- [x] Mood → power multiplier
- [x] Personality traits
- [x] Internal conflicts + mediation
- [x] Behaviour stances (attack / heal / defend / explore)

## M4 — Activities
- [x] Auto-hunt zones and timed hunts
- [x] Hunt rewards (gel / food / essence) + XP
- [x] Turn-based battle system with abilities, statuses, summons
- [x] Enemy registry + difficulty tiers
- [x] Battle loot & XP

## M5 — Growth
- [x] XP / levels
- [x] Ability unlocks by level
- [x] Evolution stages (Essence cost)
- [x] Merge with % XP transfer

## M6 — Interface & quality
- [x] Text menu UI
- [x] `--demo` scripted tour
- [x] Unit tests
- [x] Seeded determinism

## M7 — v0.2 rules update
- [x] Permadeath (starvation, hunts, brawls, battle) + graveyard / Memorial Pond
- [x] Colony grief on death
- [x] Rarity rates 90 / 9 / 0.9 / 0.09
- [x] 1–5★ rating, exponential falloff, steeper for higher rarity
- [x] Two gel currencies: white and purple (10 per pull, either)
- [x] Purple gel boosts rare odds (×5 weights)
- [x] Purple gel rare in hunts/dungeons (bosses best)
- [x] One free pull per game day
- [x] Fixed-size parties (multiple of 5), multiple parties, party hunt/battle
- [x] Save v2 with migration from v1
- [x] Tests for all of the above

## M8 — Dungeons
- [x] Rename currencies back to gel: white gel (common) / purple gel (rare)
- [x] Main dungeon "The Hollow Descent": endless floors, compounding difficulty, permadeath
- [x] Boss every 5 floors (Hollow Warden, then Parched King cycles) + first-clear purple-gel bounty
- [x] Floors cost game time; you can replay cleared floors
- [x] Grinding dungeon "The Gloop Pit": 5 depths scaled to party level, no permadeath, full XP per survivor
- [x] Multi-run grinding with optional auto-rest
- [x] Party rest command
- [x] Save v3 (`main_floor`), migration of old currency names
- [x] Tests for both dungeons

## Future (post-prototype)
- [ ] Named dungeon registry (add dungeons as data)
- [ ] Floor modifiers (poison fog, darkness) and shops between floors
- [ ] Retreat / checkpoint mid-descent
- [ ] Real-clock daily free pull (wall-time) as an option
- [ ] Resurrection items / Necromancer "revive" ability
- [ ] Star-up by merging duplicates
- [ ] Formations and front/back rows
- [ ] Offline progress by wall-clock time
- [ ] More classes: Bard, Paladin, Alchemist, Druid (via registry)
- [ ] Equipment / items
- [ ] Campaign chapters from `STORY.md`
- [ ] Slime relationships tree (best friends, rivals, couples → "budding" new slimes)
- [ ] Simple GUI (pygame/Tkinter) or ASCII animations
- [ ] Balance pass with simulation harness
- [ ] Localisation
- [ ] Mod loader (`plugins/`) with docs
