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

## Future (post-prototype)
- [ ] Offline progress by wall-clock time
- [ ] More classes: Bard, Paladin, Alchemist, Druid (via registry)
- [ ] Equipment / items
- [ ] Larger parties (5v5), formations
- [ ] Campaign chapters from `STORY.md`
- [ ] Slime relationships tree (best friends, rivals, couples → "budding" new slimes)
- [ ] Permanent-death hardcore mode
- [ ] Simple GUI (pygame/Tkinter) or ASCII animations
- [ ] Balance pass with simulation harness
- [ ] Localisation
- [ ] Mod loader (`plugins/`) with docs
