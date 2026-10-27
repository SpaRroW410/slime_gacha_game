# 🟢 Slime Gacha — *Pick Me Up, Little Goo!*

An **offline, text-based gacha + auto-hunt + battle prototype** in pure Python 3 (standard library only).
Inspired by the *Pick Me Up! Unlimited Gacha* comics — except your heroes are **slimes**.

> Collect slimes. Feed them, let them sleep, mediate their squabbles, send them hunting,
> merge the spares into your favourites, and carry them into battle.

## Play in the browser 🌐

```bash
python3 serve.py              # opens http://127.0.0.1:8765/ (add --no-open, --port N)
```

The whole game — gacha reveal animations, roster cards, parties, dungeons with battle reports, academy / spell lab,
buildings, armory, council and memorial — runs in the browser. The Python rules run in a tiny local server
(offline, localhost only); your colony is **auto-saved in the browser** (and Export / Import from the ⋯ menu), so
restarting the server never loses progress. Works on desktop and phones (responsive, light/dark theme).

**Static build (no server, deployable anywhere):**

```bash
python3 tools/build_web.py    # needs node/npm once, to vendor Pyodide (Python-in-WebAssembly) into dist/
python3 -m http.server -d dist 8766    # or upload dist/ to GitHub Pages / itch.io
```

`dist/` (~14 MB) runs the *same Python code* inside the page via Pyodide and works fully offline.
`python3 tools/build_web.py --cdn` skips vendoring and loads Pyodide from a CDN instead.

**Play from a link (desktop, Android, iPhone/iPad):** the repo includes a GitHub Actions workflow
(`.github/workflows/pages.yml`) that runs the tests, builds the static edition and publishes it to GitHub Pages
whenever `main` changes (or from the Actions tab: *Deploy to GitHub Pages -> Run workflow*). One-time setup: repo
**Settings -> Pages -> Source: GitHub Actions**. Then open `https://<your-user>.github.io/<repo>/`; on iPhone use
Safari -> Share -> *Add to Home Screen*. Saves live in each browser, so use *Export / Import save* in the ⋯ menu to
move a colony between devices.

## Quick start (terminal edition)

```bash
python3 main.py              # interactive menu
python3 main.py --demo       # scripted non-interactive tour of every system
python3 main.py --seed 42    # deterministic RNG (great for testing)
python3 main.py --party-size 10   # party size must be a multiple of 5 (default 5)
python3 -m unittest discover -s tests -v
```

No dependencies, no network. Saves go to `savegame.json` next to `main.py`
(override with `--save PATH`).

## Features

| Area | What you get |
|------|--------------|
| Gacha | Rarity 90 / 8 / 1.9 / 0.09 / 0.01 % (common to legendary), plus a **1–5 ★ rating** (exponential falloff, steeper at higher rarity; pulled mages, medics and necromancers are never below 3★). **1 free pull per real day**; otherwise 10 ⚪ white gel **or** 10 🟣 purple gel per pull — purple gel multiplies the rare+ weights ×5 (about ×3.6 on the chance of anything above common). The exact odds are shown on the Gacha tab |
| Economy | ⚪ **White gel** (common) and 🟣 **Purple gel** (rare: small drop chance in hunts/dungeons, bosses are the best source), Food, Essence |
| Main dungeon | **The Hollow Descent** — rough, permanent death. Walk the floors **in order** and **leave only after a boss floor** (every 5), so there is time to train and study between segments. **Progress is per slime**: to enter floor *f* every member must have cleared floor *f−1*, so nobody can be carried and a rookie drags a veteran party back to floor 1. Other parties may walk the same floors again. Boss bounty is paid once per boss floor |
| Floors 1-50 | 29 terrains (valleys, dunes, islands, caverns, tundra, volcano...) boost/dampen elements or hurt each round; 71 monsters in mixed warbands (goblins + direwolves, orcs + ogres...); 10 bosses, the Parched King on floor 50. No two floors repeat. The **Gloop Pit changes theme every day** |
| Wayfarer's Rift | An adventure dungeon for **relics**: 1-5 slimes, monsters one level above their average. Relics have rarity (far rarer than the gacha), 1-5 stars, level, durability, mods (crit, elemental damage...) and **compatibility** with their wielder. Salvage them for materials to level, ascend stars (Lv10) and raise rarity (5 stars). A 5-star legendary relic + a 5-star legendary slime make an **ego relic** |
| Ascension | Slimes climb **common > uncommon > rare > epic > legendary** by spending white gel (10 / 100 / 1000 / 10000) and gain **stars** with ascension stones (10 / 100 / 1000 / 10000; 100 stones merge into 1 of the next rarity). Stones come from the **Starfall Quarry**, other dungeons and the **Destruction Chamber**. Merging gives only collected XP plus a shrinking share of stats (20% down to 1%, no cap) |
| Stamina, stars & skills | Every slime has **stamina** (actions cost it, it refills by the hour; exhausted slimes hit weaker). Each **star** adds a class attribute (crit, guard, evasion, regen, spell power...), each **rarity** a class skill (Moon Slash, Aura Blade...). **Potions** (Alchemy Lab, grades 1-5) from four coloured herbs - green health, red strength, blue armor, yellow stamina - and their combinations (lifesteal, guard, regen, crit, speed...). **Slime autonomy**: slimes may use up to 66% of your potions and scrap on their own. Weapons come in six families with proficiency, a three-family memory and a favourite; slimes repair their own gear |
| Emotions | Slimes have **13 feelings** (anger, sadness, fear, joy, pride, calm, anxiety, loneliness, determination, affection, guilt, dread, wonder) stirred by victories, defeats, deaths, quarrels, hunger and kindness. They change battle stats: anger +ATK -DEF, sadness -SPD, fear +evasion -ATK... Feelings settle back to each slime's usual mood, and contentment follows how life has felt for days. A **5-star legendary** slowly realises it is just code, and takes it the way its last two weeks allow: settled, at peace, a cog in the machine, or in despair (which deepens, and may end with it asking to leave). See `docs/MINDS.md`. Slime autonomy now also covers relics, gear and brewing |
| Bonds & Keeper | Slimes form **friendships, best friends, rivalries, mentorships and couples**; a couple can have a **child** (traits, class and rarity from both parents) and the **family tree** grows. **You** level up as the Keeper and spend skill points in four branches (Caretaker, Tactician, Fortune, Matchmaker) and use daily abilities like Rally and Bond Night |
| Battles | Automatic by default. Switch **🎮 Take command** on (Hollow Descent, Gloop Pit, wave simulations) to play turn by turn: every slime acts on its own turn in a battle arena, and you can hand the fight back to the slimes at any moment |
| Time | Two modes: **turn-based** (you decide when time passes) and **live** (the wall clock moves the colony: x1 at home so study and hunts take real time, x3 while a party is in a dungeon; speed presets). Clearing a floor takes game time that depends on depth, party level and scouting. Slimes inside a dungeon cannot be fed, petted or given potions. The **Guide** tab is an in-game booklet of every attribute |
| Scouting | An **exploration party** scouts any 1–10 floors (not only multiples of 5). It must reach **100% knowledge of every targeted floor within its hour budget or the whole party is lost** (a half-finished note survives). Time needed grows with depth, hides a 0.85–1.2× factor (an estimate is never exact), and supplies are paid up front. Scouts must have cleared the floors above. Knowledge reveals more per floor: counts → types → boss → abilities → weaknesses; a fully known floor gives +10 % power |
| Specialization | Cross-training makes **hybrid classes**: a swordslime who trains in magic becomes a **Battlemage** (also Spellknight, Arcane Archer, Hexshot, Swashbuckler, Battle Medic, Death Knight, Shadowcaster …). Style level 3 in a discipline outside your class + level 5, then specialize: stat shift, signature ability, affinity in both disciplines. Permanent |
| Outlook | What a slime *does* shapes how it thinks: sparring → Duelist, Pit → Grinder, dungeon → Delver, scouting → Pathfinder, hunting → Forager, studying → Scholar. Each gives a small perk and the slime asks for that activity when it needs esteem (first draft) |
| Grinding dungeon | **The Gloop Pit** — a *committed* XP-farming session of N runs at depth 1–5 (no leaving until done or the whole party is knocked out; the party camps when hurt). Nobody dies, but a **downed slime loses XP and morale and drops its equipment** — survivors may carry it back (chance from **party synergy**), else it is left in the Pit until a later victory digs it up |
| Equipment | Weapon / armor / charm, any class. Bought at the 🛠️ **Armory** (tier gated by its level) or found in dungeons. In dungeons a fallen slime's gear is lost unless a survivor recovers it |
| Sacrifice stress | Every merge adds stress (−1 per day). It amplifies the morale cost of the next sacrifice and drags the whole colony's morale target down — merging too much breaks the colony |
| Sparring (fighting style) | Training is **not** for XP and not for the Gloop Pit: slimes **duel each other** in the ⚔️ Blade Yard, 🏹 Archery Range or 🔮 Mana Pool to develop a *style* (Swordsmanship, Marksmanship, Spellcraft) with permanent combat perks. Non-lethal: the loser is left at **1 HP** |
| Rest Area | Heals wounded slimes back to **full** (30 → 100 %/hour by level). Auto-care sends the wounded there. Starving slimes can't heal |
| Buildings | Five upgradable buildings (incl. 🛠️ Armory): 🛏️ Rest Area (capacity, healing), 🥋 Training Grounds (style ceiling + XP), 📚 Library (study speed, spell slots, research odds, Restricted Section for tier-3 spells), 🏕️ Barracks (morale, bonds, party synergy) |
| Compatibility & bonds | Every pair has a **compatibility** score (traits, class chemistry, shared / fusable elements, friendship, sparring/battle history, open quarrels). It shapes quarrel odds, merge XP (±25 %) and **party synergy** (±10 % power) |
| Morale | Per-slime "fight readiness": wins and rests raise it, defeats, brawls and deaths of friends lower it. Scales power ×0.85–1.15; a broken slime may freeze in battle |
| Council | Keep-or-sacrifice advisor: ranks the roster (KEEP / FLEX / SACRIFICE?), shows how loved each slime is, and suggests the best merges (the donor is consumed, friends grieve) |
| Elements | 🔥 Fire, 💧 Water, 🪨 Earth, 🌪️ Wind and their **fusions**: Fire+Wind = ⚡Lightning, Lightning+Fire = 🔆Plasma, Fire+Earth = 🌋Lava, Ice, Steam, Mud, Sand … (13 elements; add recipes in data). Wheel: Water > Fire > Wind > Earth > Water |
| Elemental mastery | Unlocks at **3★, for any class** (barbarians can cast too — they channel through attack). Mastery cap 4/6/8 and 2/3/4 element slots at 3/4/5★ (mages get +1 slot and study faster) |
| Library | Study elements, buy tier-1 spells, learn up to 4 spells per slime |
| Spell lab | **Fuse two learned spells** of different elements into a brand-new, nameable spell. Costs essence, takes hours, can fizzle and backfire. Discovered spells join the Library for everyone |
| Parties | Fixed-size parties (multiple of 5; default 5), as many parties as you like, one slime per party. Only full parties battle; parties can hunt together |
| Permadeath | Slimes **die** — starvation/exhaustion, failed hunts, brawls, battle. Dead slimes go to the Memorial Pond (graveyard); friends grieve |
| Classes | Barbarian, Mage, Medic, Rogue, Ranger, Necromancer — **data-driven & plugin-style** |
| Needs AI | Maslow-style needs: Energy → Food → Safety → Belonging → Esteem, plus mood & personality |
| Conflict | Slimes quarrel (hungry/grumpy/rival temperaments); you mediate or let it simmer |
| Auto-hunt | Assign slimes to hunt zones; they return with resources over game "ticks" |
| Behaviours | Per-slime stance: attack / heal / defend / explore (changes battle & hunt behaviour) |
| Growth | XP, levels, evolution stages, abilities unlocked by level |
| Merge | Fuse a slime into another; target gains a % of the fodder's XP (and bonus for same class) |
| Battle | Turn-based auto-combat, party vs a wave of foes (one per party slot), abilities, status effects, loot |
| Persistence | JSON save/load (v1 saves migrate), fully offline |

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
  party.py               PartyManager (fixed-size parties)
  resources.py           ResourceManager (wallet: white_gel/purple_gel/food/essence)
  gacha.py               GachaSystem (rarity, stars, free daily pull)
  hunt.py                HuntSystem (auto-hunt zones)
  dungeon.py             wave generators for the Hollow Descent and the Gloop Pit
  elements.py            elements, fusion recipes, wheel, mastery rules
  spells.py              elemental spells + spell fusion
  academy.py             library, study / research tasks
  sparring.py            fighting styles, arenas, sparring rules
  buildings.py           upgradable buildings + rest-area healing
  equipment.py           gear, inventory
  specialization.py      hybrid classes from cross-training
  outlook.py             experience-driven mindset (Duelist, Grinder, Delver ...)
  social.py              bonds, compatibility, synergy, morale, council advice
  battle.py              BattleSystem (turn-based auto-combat)
  game.py                Game façade: state, ticking, save/load
  cli.py                 text UI
  webapi.py              JSON command API + render-ready state snapshot (used by the browser)
serve.py                 local web server (static files + POST /api)
web/                     browser front-end: index.html, style.css, app.js, backend.js
tools/build_web.py       builds the static Pyodide edition into dist/
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

## Version

The current version is **1.001** (shown on the in-game **About** tab, which also summarises the game and lists the remaining roadmap).

## Documentation

- [`docs/STORY.md`](docs/STORY.md) – the world of Gloop Hollow
- [`docs/SDD.md`](docs/SDD.md) – architecture & design decisions
- [`docs/ROADMAP.md`](docs/ROADMAP.md) – milestones and checklist

## License

Prototype – choose a license before distributing.
