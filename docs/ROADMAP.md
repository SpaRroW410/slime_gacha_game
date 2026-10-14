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

## M9 — Academy, elements & spell fusion
- [x] ~~Solo training grounds~~ (replaced in M10 by sparring)
- [x] Four basic elements + 13-element fusion tree (data-driven recipes)
- [x] Elemental wheel in battle (weakness / resist)
- [x] Elemental mastery from 3★, any class; slots + caps by stars; mage perks
- [x] Library: study elements, tier-1 spells, learn / forget, 4-spell limit
- [x] Spell lab: fuse two spells into a new (nameable) spell; success odds, costs, backfire
- [x] Discovered spells shared via the Library
- [x] Casting builds mastery; non-mage imbuing (attack-scaled spells)
- [x] Save v4 (custom spells, mastery, training)
- [x] Tests (32 new)

## M10 — Sparring, rest, buildings, bonds
- [x] Training reworked: sparring duels develop a fighting style (no XP, separate from the Gloop Pit)
- [x] Non-lethal duels: the loser drops to 1 HP
- [x] Three arenas and styles: Swordsmanship / Marksmanship / Spellcraft with combat perks
- [x] Rest Area: heals to full, capacity + speed by level, auto-admit for the wounded
- [x] Upgradable buildings: Rest Area, Training Grounds, Library, Barracks
- [x] Library levels: spell slots, study speed, research odds, Restricted Section (tier 3)
- [x] Bonds between slimes (sparring, battles, mediation, quarrels)
- [x] Compatibility score + party synergy (±10 % power)
- [x] Morale / fight readiness (power ×0.85–1.15, freezing when broken)
- [x] Council: keep-or-sacrifice ranking + merge suggestions with colony-morale cost
- [x] Merge changes: compatibility swings XP, bonds inherited, colony mourns
- [x] Save v5 and ~40 new tests

## M11 — Commitment, intel & consequences
- [x] Merging/sacrificing lowers morale (target, bystanders, friends) with compounding **sacrifice stress**
- [x] Hollow Descent in 5-floor segments: **no exit** until the boss falls or the whole party dies
- [x] Permanent death in the Descent; short-handed parties continue; in-dungeon camping with ambushes
- [x] Exploration party scouting: knowledge grows with time in the dungeon (diminishing returns)
- [x] Staged intel (counts → types → boss → abilities → weaknesses), deterministic floors, intel power bonus
- [x] Gloop Pit as a committed session (all runs or whole party down); auto-camping
- [x] Pit defeat: XP loss, morale loss, gear dropped; synergy-based recovery; Pit lost-and-found
- [x] Equipment (weapon / armor / charm), Armory building, gear drops
- [x] Save v6 and 32 new tests

## M12 — Browser edition
- [x] JSON command API (`webapi.py`) with render-ready snapshot and error envelope
- [x] Local server (`serve.py`, stdlib only, localhost) with `/api` and static hosting
- [x] Responsive, themable UI (dark/light): colony, gacha reveal, parties, dungeons, academy, town, council, records
- [x] Battle report viewer, confirmations for irreversible actions, toasts and event log
- [x] Browser auto-save (localStorage) + export/import
- [x] Static Pyodide build (`tools/build_web.py`): same Python in the page, offline-capable
- [x] API / server tests (12) and browser smoke tests (Playwright, local)

## M13 — Rules revision: progress, checkpoints, scouting, classes
- [x] Leave the Descent only after a boss floor (checkpoints every 5); may also push on
- [x] Per-slime dungeon progress; a party's entry floor is limited by its least-travelled member
- [x] Several parties can be inside at once and re-walk the same floors; boss bounty once per boss floor
- [x] Scouting by floor range (1–10 floors): 100 % or the whole party is lost; hidden time variance; up-front supplies
- [x] Per-floor knowledge (scouting, or having walked the floor) and staged intel
- [x] Specialization: hybrid classes from cross-training (Battlemage and 8 more)
- [x] Outlook: experience shapes the slime (Duelist, Grinder, Delver, Pathfinder, Forager, Scholar)
- [x] Save v7 with migration from v6; web UI + CLI updated
- [x] 29 new tests

## Future (post-prototype)
- [ ] Reach floor 50 (the milestone before the art & sound pass)
- [ ] More spec paths (three-way hybrids, evolution of specs), outlook-driven behaviours (slimes ask for jobs)
- [ ] Rescue parties for scouts that are overdue
- [ ] Construction time for upgrades; more buildings (Pantry, Hatchery)
- [ ] Rivalries and mentorships as explicit relationships; couples -> new slimes
- [ ] Enemy resistances beyond one element; elemental dungeon floors
- [ ] Spell mutation / evolving fused spells with mastery
- [ ] Hybrid class abilities (e.g. Barbarian fire-axe imbue as a status)
- [ ] Named dungeon registry (add dungeons as data)
- [ ] Gear crafting / enchanting, set bonuses
- [ ] Several delves at once (one party per dungeon) with rescue parties
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
- [ ] Art pass: sprite sheets / animated slimes instead of CSS blobs, sound effects
- [ ] PWA manifest + service worker for installable offline play
- [ ] Web worker for Pyodide so long Pit sessions never block the UI
- [ ] Balance pass with simulation harness
- [ ] Localisation
- [ ] Mod loader (`plugins/`) with docs

## M14 — Floor-50 content
- [x] Terrain system with element effects, hazards, crit bonus
- [x] Bestiary: roles, families, ~50 monster moves, 71 monsters
- [x] Ten bosses (floors 5-50), final boss completes the Descent
- [x] Unique, mixed-family floors 1-50 (no consecutive terrain repeats)
- [x] Daily-changing Gloop Pit (terrain + featured families)
- [x] Web UI: terrain/title per floor, Today's Pit panel, victory banner
- [ ] Art & sound (after floor 50, as planned)
