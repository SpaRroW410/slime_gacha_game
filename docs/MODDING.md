# Modding Slime Gacha

Content lives in registries (`slime_gacha/registry.py`). A mod is a Python module in `slime_gacha/plugins/` that registers
what it adds when it is imported. `load_plugins()` imports every module there at start-up (CLI, local server and the
Pyodide build, which packs the folder into `slime_gacha.zip`).

## The rules

- One module (or a package) per mod. Put the `register_*` calls in a `register()` function: the loader calls it at start-up
  unless the module sets `ENABLED = False`. (A module without `register()` just registers at import time and cannot be switched off.)
- A mod that raises is skipped and recorded in `registry.PLUGIN_ERRORS`; the game still starts.
- Register new content only. Replacing a built-in key raises, on purpose.

## What you can register

| Content | Call | Where |
|---|---|---|
| Class | `register_archetype(Archetype(...))` | `archetypes.py` (stats, growth, `{level: ability}`, behaviour, discipline) |
| Skill | `register_ability(Ability(...))` | `abilities.py` (kind, power, stat, target, cooldown, optional `fx` tuples, see `fx.py`) |
| Enemy | `register_enemy(Enemy(...))` | `battle.py` |
| Monster family member | `register_monster(Monster(...))` | `bestiary.py` (level band and habitats place it in floors and the Pit) |
| Hunt zone | `register_zone(Zone(...))` | `hunt.py` |
| Gear | `register_gear(Gear(...))` | `equipment.py` |
| Building | `register_building(Building(...))` | `buildings.py` |
| Dungeon (no code) | `places.load_json(path)` or `register_place(Place(...))` | `places.py`: loot table, XP, theme seed |

Rarity skills, evolutions and capstones for a class are tables in `attributes.py`; `newclasses.py` shows the shape.

## Example

`slime_gacha/plugins/example_pack.py` adds a Jester class, the Pratfall skill and a Mirthless Mime enemy. Set
`ENABLED = True` and start the game: Jesters appear in the pull pool and the Mime in fights.

A data-only dungeon:

```json
[{"key": "glow_caves", "name": "Glow Caves", "emoji": "🍄", "loot": {"essence": [0.3, 1, 2]}, "xp_mult": 0.25}]
```

Load it with `places.load_json("glow_caves.json")` from a plugin; it then appears under Dungeons > More places.

## Testing a mod

Write a unittest that imports the module, builds a `Game(seed)` and exercises the content (`tests/test_training.py::PlacesTest`
is a small model). `python -m unittest discover -s tests` must stay green.
