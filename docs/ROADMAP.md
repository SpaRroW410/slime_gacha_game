# Roadmap & Checklist

Legend: `[x]` done · `[ ]` todo.  The remaining work is tracked task by task in [`TASKS.md`](TASKS.md); the floor-50 playtest is in [`PLAYTEST_F50.md`](PLAYTEST_F50.md).

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
- [x] Rivalries and mentorships as explicit relationships; couples -> new slimes (M18)
- [ ] Enemy resistances beyond one element; elemental dungeon floors
- [ ] Spell mutation / evolving fused spells with mastery
- [ ] Hybrid class abilities (e.g. Barbarian fire-axe imbue as a status)
- [ ] Named dungeon registry (add dungeons as data)
- [~] Gear crafting / enchanting done (relic forge, mods); set bonuses still todo
- [ ] Several delves at once (one party per dungeon) with rescue parties
- [ ] Floor modifiers (poison fog, darkness) and shops between floors
- [ ] Retreat / checkpoint mid-descent
- [~] Real-clock daily free pull: the live clock makes the daily pull follow real time at x1 (M19)
- [ ] Resurrection items / Necromancer "revive" ability
- [x] Star-up (done as stone-based star ascension, M16)
- [ ] Formations and front/back rows
- [x] Offline progress by wall-clock time (live mode, M19)
- [ ] More classes: Bard, Paladin, Alchemist, Druid (via registry)
- [x] Equipment / items (relics, M15)
- [ ] Campaign chapters from `STORY.md`
- [x] Slime relationships tree (best friends, rivals, couples -> budding) (M18)
- [ ] Art pass: sprite sheets / animated slimes instead of CSS blobs, sound effects
- [ ] PWA manifest + service worker for installable offline play
- [x] Web worker for Pyodide so long Pit sessions never block the UI
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

## M15 — Relics & the Wayfarer's Rift
- [x] Adventure dungeon: 1-5 slimes, monsters at party average + 1
- [x] Relic drops with harsh rarity odds, stars, mods
- [x] Durability, repair, shatter into materials
- [x] Levelling, star ascension (Lv10), rarity ascension with a new mod (5 stars, Lv10)
- [x] Slime-relic compatibility
- [x] Salvage: higher level = better materials
- [x] Ego relics (5-star legendary relic + 5-star legendary slime)
- [x] Web Rift tab, CLI menu [w], tests

## M16 — Slime ascension & economy
- [x] Uncommon rarity (five rarities)
- [x] Rarity ascension with white gel (10 / 100 / 1000 / 10000)
- [x] Star ascension with ascension stones (10 / 100 / 1000 / 10000), stones merge 100 > 1
- [x] Starfall Quarry, side drops, boss hoards
- [x] Merge rework: collected XP + diminishing stat share (20% > 1%)
- [x] Destruction Chamber building
- [x] Stamina attribute, star attributes per class
- [x] Rarity skills per class (Moon Slash, Aura Blade, ...)
- [x] Weapon proficiency, three-family memory, favourite weapon, named weapons, slimes repairing gear
- [x] Potions: Alchemy Lab, grades 1-5, temporary boosts, stamina potion, herbs
- [x] Four coloured herbs, combination potions, terrain-driven herb drops
- [x] Slime autonomy: 66% of stocks usable without asking

## M17 — Emotions & awakening
- [x] Thirteen emotions with battle effects (anger +ATK -DEF, sadness -SPD ...)
- [x] Events, needs and traits drive feelings; they fade; own RNG
- [x] 5-star legendaries awaken: they realise they are code (accept / despair)
- [x] Autonomy covers relics, gear and brewing
- [ ] Art & sound (after floor 50)

## M18 — Relationships, budding & the Keeper
- [x] Explicit ties: friend, best friend, rival, mentor/mentee, couple (daily review)
- [x] Ties affect synergy, pre-battle feelings, mentee XP and grief
- [x] Budding: couples have children; lineage and family tree
- [x] Keeper levels, XP sources with daily caps
- [x] 16 Keeper skills in 4 branches, 4 daily abilities
- [x] Web Bonds and Keeper tabs, CLI [y] and [h]
- [ ] Keeper achievements / titles, skill respec

## M19 — Time dilation, calmer UI, booklet
- [x] No feeding / petting / sleeping / talking / potions inside dungeons
- [x] Live (wall-clock) time: home x1, dungeons x3, presets, offline cap
- [x] Dungeon activities keep parties away on the wall clock; floor clear time from depth, level and knowledge
- [x] (i) tooltips, death-only dungeon subheadings, eight tabs with sub-tabs, tabbed slime card
- [x] Guide tab (booklet of attributes, with what raises / lowers them)

## M20 — Manual battles
- [x] Steppable battle engine; each party slime acts on its own turn
- [x] Hollow Descent, Gloop Pit and skirmishes (not Rift / Quarry / sparring)
- [x] Switch between manual and auto at any time (whole fight, one turn, later Pit runs)
- [x] Mini battle arena in the browser (text; renderer isolated for later animation)
- [x] Town > Merge & destroy: manual merge of any two free slimes (with preview) and the Destruction Chamber
- [x] No mediation for quarrels involving a slime that is away
- [x] Commander's gifts (purple gel) for Descent and skirmish parties; potion slots 2-6 by stars
- [x] Relic merge, gear scrap and gear merge in Town > Merge & destroy
- [x] Battle effect mechanics (bleed, stun, mark, shield, revive, delay, ...) - step 1 of the 60-skill plan
- [x] 24 rarity skills rebuilt on the new mechanics + 6 evolution skills (rank II at the second evolution) - step 2
- [x] Pure capstones (12) with class proficiency and decay - step 3
- [x] Hybrid signature upgrades and 9 hybrid capstones, second proficiency, drift from pure to hybrid - step 4 (60 skills complete)
- [x] Rename slimes and parties; Vice Keeper (delegated mediation and care inside groups, never merge/destroy)
- [x] Party leaders; Vice Keeper organises multi-party hunts and leads the group; challenges for the post (Keeper approves, duel decides)
- [x] Quarrels only between slimes that share a place (both home, or one party away together); they wait while one is away
- [x] Big colonies: Colony shows the top 10 as cards and the rest as a compact searchable list
- [x] Training facility (solo drills in the Blade Yard / Archery Range / Mana Pool for class proficiency, no star requirement); mages, medics and necromancers pulled at 3+ stars; rarity ascension keeps earned elemental mastery (growth paused)
- [x] Drill tiers (Basic / Advanced / Master) unlocked by the Training Grounds level
- [x] UI: the slime icon (three dots in a triangle) is the menu button; compact one-row header and tabs stay pinned while scrolling
- [ ] Animated arena (after floor 50), CLI turn prompts, optional flee
