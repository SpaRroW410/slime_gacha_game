# 🟢 Slime Gacha — *Pick Me Up, Little Goo!*

An **offline, text-based gacha + auto-hunt + battle prototype** in pure Python 3 (standard library only).
Inspired by the *Pick Me Up! Unlimited Gacha* comics — except your heroes are **slimes**.

> Collect slimes. Feed them, let them sleep, mediate their squabbles, send them hunting,
> merge the spares into your favourites, and carry them into battle.

## Quick start

```bash
python3 main.py              # interactive menu
python3 main.py --demo       # scripted non-interactive tour of every system
python3 main.py --seed 42    # deterministic RNG (great for testing)
python3 -m unittest discover -s tests -v
```

No dependencies, no network. Saves go to `savegame.json` next to `main.py`
(override with `--save PATH`).

## Features

| Area | What you get |
|------|--------------|
| Gacha | Common / Rare / Epic / Legendary pulls, pity counter, single & ×10 pulls |
| Classes | Barbarian, Mage, Medic, Rogue, Ranger, Necromancer — **data-driven & plugin-style** |
| Needs AI | Maslow-style needs: Energy → Food → Safety → Belonging → Esteem, plus mood & personality |
| Conflict | Slimes quarrel (hungry/grumpy/rival temperaments); you mediate or let it simmer |
| Auto-hunt | Assign slimes to hunt zones; they return with resources over game "ticks" |
| Behaviours | Per-slime stance: attack / heal / defend / explore (changes battle & hunt behaviour) |
| Growth | XP, levels, evolution stages, abilities unlocked by level |
| Merge | Fuse a slime into another; target gains a % of the fodder's XP (and bonus for same class) |
| Battle | Turn-based auto-combat (3v3 style) with abilities, status effects, loot |
| Economy | Gel (gacha currency), Food, Essence (upgrades/evolution) |
| Persistence | JSON save/load, fully offline |

## Repository layout

```
main.py                  entry point (CLI args)
slime_gacha/
  config.py              tunable constants: rarities, rates, needs, growth curves
  registry.py            tiny plugin registry (archetypes, abilities)
  abilities.py           Ability objects + built-in abilities
  archetypes.py          Archetype definitions for the 6 starting classes
  slime.py               Slime, Stats, Needs, Personality
  ai.py                  NeedsEngine (Maslow) + ConflictEngine + Behavior stances
  growth.py              levelling, evolution, merging
  resources.py           ResourceManager (wallet)
  gacha.py               GachaSystem
  hunt.py                HuntSystem (auto-hunt zones)
  battle.py              BattleSystem (turn-based auto-combat)
  game.py                Game façade: state, ticking, save/load
  cli.py                 text UI
docs/
  SDD.md                 software design document
  ROADMAP.md             milestones + checklist
  STORY.md               lore & narrative hooks
tests/                   unittest suite
```

## Adding a new slime class (the 30-second version)

```python
# slime_gacha/archetypes.py  (or any module imported at startup)
from .registry import register_archetype
from .archetypes import Archetype

register_archetype(Archetype(
    key="bard", name="Bard", emoji="🎵",
    base_stats=dict(hp=18, atk=5, defense=4, mag=8, spd=7),
    growth=dict(hp=3, atk=1, defense=1, mag=2, spd=1),
    abilities={1: "inspire", 5: "lullaby"},   # level -> ability key
    default_behavior="heal",
    likes=("music",), hunt_bonus={"essence": 1.3},
))
```

The gacha pool, UI, hunting and battle all discover it automatically. See `docs/SDD.md` §6.

## Documentation

- [`docs/STORY.md`](docs/STORY.md) – the world of Gloop Hollow
- [`docs/SDD.md`](docs/SDD.md) – architecture & design decisions
- [`docs/ROADMAP.md`](docs/ROADMAP.md) – milestones and checklist

## License

Prototype – choose a license before distributing.
