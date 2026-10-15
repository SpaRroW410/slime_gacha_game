# Software Design Document — Slime Gacha (prototype v0.1)

> **v0.2 changes**: permadeath, rarity 90/9/0.9/0.09, 1–5★ ratings, white/purple gel currencies, free daily pull, fixed-size parties (§5.1, 5.9, 5.10).
> **v0.8 changes**: per-slime dungeon progress + checkpoint exits, floor-level scouting that kills incomplete parties, specialization (hybrid classes), outlook (§5.11, §5.15, §5.17).
> **v0.7 changes**: browser front-end (§5.16): JSON command API, local server, Pyodide static build.
> **v0.6 changes**: no-exit delves, scouting intel, Pit defeat penalties + gear recovery, equipment & Armory, sacrifice stress (§5.11, §5.15).
> **v0.5 changes**: sparring-based fighting styles, Rest Area, upgradable buildings, compatibility / morale / council (§5.12–5.14).
> **v0.4 changes**: library, elements, elemental mastery, spell fusion (§5.12 Library part).
> **v0.3 changes**: main + grinding dungeons (§5.11), currency naming (white/purple gel).

## 1. Goals & non-goals

**Goals**: an offline, single-process, text-UI prototype proving the loop
*pull → care → hunt → battle → upgrade → pull*, with a codebase where new slime classes,
abilities, zones and enemies are added as **data**, not by editing engine code.

**Non-goals (v0.1)**: graphics, audio, networking, real-time simulation, monetisation, balance polish.

## 2. Constraints

- Python ≥ 3.9, standard library only. Runs as `python3 main.py`.
- Deterministic when seeded (`random.Random` instance injected everywhere; never the global RNG).
- All state serialisable to JSON.
- Engine/UI separation: `cli.py` only calls the `Game` façade; no game rules in the UI.

## 3. Architecture

```
            ┌────────────┐
            │   cli.py   │  text UI (menus, printing)
            └─────┬──────┘
                  │ calls
            ┌─────▼──────┐        owns          ┌───────────────┐
            │  Game      │─────────────────────▶│ ResourceManager│
            │ (façade,   │                      └───────────────┘
            │  clock,    │──▶ GachaSystem  ──▶ ArchetypeRegistry
            │  save/load)│──▶ NeedsEngine / ConflictEngine (ai.py)
            │            │──▶ HuntSystem   ──▶ ZoneRegistry
            │            │──▶ BattleSystem ──▶ AbilityRegistry, EnemyRegistry
            │            │──▶ growth.py (xp, evolve, merge)
            └────────────┘
```

Dependency rule: lower layers (`config`, `registry`, `abilities`, `archetypes`, `slime`) never import
higher ones (`game`, `cli`).

## 4. Domain model

### 4.1 Slime (`slime.py`)
| Field | Meaning |
|-------|---------|
| `id`, `name` | unique id, generated name |
| `archetype` | key into archetype registry |
| `rarity` | `common/rare/epic/legendary` |
| `level`, `xp`, `stage` | growth; stage = evolution tier (0,1,2) |
| `variance` | per-slime ±10 % stat roll, fixed at birth (makes pulls unique) |
| `hp` | current HP (max derived) |
| `needs` | `Needs` (energy, food, safety, belonging, esteem; 0–100, higher = satisfied) |
| `personality` | list of traits modifying decay/conflict |
| `behavior` | stance: `attack / heal / defend / explore` |
| `state` | `idle / sleeping / hunting` |
| `hunt` | active hunt assignment or None |

Derived: `max_stats()` = `(archetype.base + growth·(level-1)) · rarity_mult · stage_mult · variance`;
`mood()`; `power_multiplier()` (0.6–1.1 from mood and Maslow blockage).

### 4.2 Archetype (`archetypes.py`) — *the extension point*
Frozen dataclass: `key, name, emoji, base_stats, growth, abilities{level→ability_key},
default_behavior, likes, hunt_bonus{resource→mult}, rivals`. Registered with `register_archetype`.
The gacha pool = `all_archetypes()` (optionally weighted by `pull_weight`).

### 4.3 Ability (`abilities.py`)
`Ability(key, name, kind, power, stat, target, cooldown, status, description)`.
`kind ∈ {damage, heal, guard, drain, poison, summon}`. `BattleSystem` interprets `kind`
through a dispatch table, so a new *kind* = one handler function; a new *ability* = one data row.

## 5. Systems

### 5.1 GachaSystem (`gacha.py`)
- **Rarity** weights (config): common 90 / rare 9 / epic 0.9 / legendary 0.09 (normalised by `random.choices`).
- **Stars** 1–5: `P(star=k) ∝ exp(−λ·(k−1))`, with λ per rarity `{common .7, rare 1.0, epic 1.3, legendary 1.6}`.
  Each step down the ladder costs a constant factor (exponential), and higher rarities fall off faster, so
  a 5★ common ≈ 3 % while a 5★ legendary ≈ 0.13 %. Stars multiply stats `[1.0, 1.1, 1.25, 1.45, 1.7]`.
- **Payment**: `pull(n, pay)` with `pay ∈ {free, white_gel, purple_gel}`. White/purple gel cost 10 each per pull.
  **Purple gel** multiplies the rare/epic/legendary weights by `PURPLE_RARITY_BOOST` (5×).
- **Free daily pull**: one per game day (`day = tick // 24`); `last_free_day` is persisted.
- **Pity** is optional and **off by default** (`PITY_* = 0`) so the published rates are honest.
- Stats = archetype base × rarity mult × star mult × stage mult × variance.

### 5.2 Needs / Maslow AI (`ai.py`)
Hierarchy (lowest tier first): **Energy → Food → Safety → Belonging → Esteem**.
- Each tick every need decays by `base_rate × state_modifier × trait_modifier`.
- `dominant_need()` = the lowest tier below `NEED_THRESHOLD` (40). Higher tiers are *suppressed*:
  while a lower tier is unmet, higher-tier needs neither decay nor count toward mood
  (hungry slimes don't care about status).
- **Autonomy** (when `auto_care` on and slime is idle): energy < 25 → go to sleep (wake ≥ 90);
  food < 30 → eat from the Food stock (+40); belonging < 40 and other idle slimes exist → cuddle (+belonging both);
  esteem < 40 → `wishes()` text asks the player for a hunt/battle.
- **Starvation/exhaustion** at 0: HP loss and mood penalty.
- Mood = weighted mean of *active* needs; maps to `power_multiplier` 0.6 – 1.1.

### 5.3 Internal conflict (`ai.py::ConflictEngine`)
Each tick, for each pair of non-sleeping slimes, chance =
`base + grumpy traits + hunger penalty + rivalry (archetype.rivals) − friendship`.
A `Conflict(a, b, severity 1–3, age)` is created. Unresolved conflicts age: belonging drains, severity
escalates; at severity 3 they **brawl** (both lose HP, refuse hunts until mediated). Player resolves via
`Game.mediate(conflict_id, method)` — `talk` (free, success odds from traits), `snack` (costs Food, safe),
`separate` (assign both to different tasks; no effect on grudge). Success raises belonging and creates
*friendship* (reduces future conflict).

### 5.4 Behaviour (stance) system
`behavior` is a per-slime policy consumed by Hunt and Battle:

| Stance | Battle AI | Hunt effect |
|--------|-----------|-------------|
| attack | max-damage ability, focus lowest-HP foe | +loot (white gel), +injury |
| heal | heals ally < 60 % HP if able, else attack | party recovers HP, −yield |
| defend | guards when ally low/self low, else attack | −injury |
| explore | random targets, +crit; scouts | +chance of rare finds (essence) |

Player changes it with `Game.set_behavior(id, stance)`.

### 5.5 HuntSystem (`hunt.py`)
`Zone(key, name, duration, danger, rewards{resource:(lo,hi)}, xp)` from a registry.
`start(slime, zone)` sets state `hunting`; `tick()` decrements; on completion rolls success from
`slime power vs zone danger`, grants resources scaled by archetype `hunt_bonus`, stance and rarity,
grants XP, applies damage (**can kill**). Exhausted slimes return early with half loot. Each zone has a small `purple_chance` (1–8 %, ×1.5 for explorers). Slimes below 30 % HP cannot be sent out.

### 5.6 BattleSystem (`battle.py`)
Turn-based auto-combat. `Combatant` wraps a slime snapshot or an `Enemy`. Order by speed each round.
Per turn: status ticks (poison/guard expiry) → AI picks ability by stance → resolve via kind handler.
Damage: `max(1, (power × stat) − 0.5 × defense) × rng(0.9, 1.1) × power_multiplier`, crit 8 % ×1.5.
Ends when a side is empty or round cap (30). Slimes at 0 HP are **dead** (removed by `Game._reap`). Survivors share XP and loot; enemies drop purple gel with a per-enemy chance (bosses 35 %).
Returns a `BattleReport` (log lines, winner, rewards) — UI only prints it.

### 5.7 Growth (`growth.py`)
- `xp_to_next(level) = 20 × level^1.5`. Level caps per stage: 10 / 25 / 50.
- **Evolve** at cap: cost Essence (`50 × (stage+1)`), `stage += 1`, stat × 1.5, unlock an evolution ability.
- **Merge(target, donor)**: target gains `0.5 × donor.total_xp` (+ rarity bonus; ×1.25 same class),
  donor is consumed. Cannot merge into itself or while hunting. Total XP tracked so merges chain.
- Abilities unlock at levels listed in the archetype.

### 5.8 ResourceManager (`resources.py`)
Wallet of `white_gel` (common currency), `purple_gel` (rare currency), `food`, `essence`. `add/spend/can_afford`, atomic `spend_many`.
New resources = new key in config; no code change.

### 5.9 Parties (`party.py`)
`PartyManager(size)`; `size` must be a positive multiple of 5 (validated; chosen per game, saved).
Any number of parties; a slime is in at most one. `Game.battle(pid, tier)` and `party_hunt` require a **full**
party; the enemy wave has one foe per party slot. Dead/merged members are removed automatically, which makes
the party incomplete until refilled (`party_autofill` picks the strongest free slimes).

### 5.10 Death (permadeath)
Engines never delete slimes; they set `hp <= 0` and `death_cause`. `Game._reap` runs after each tick phase and
after each battle: it moves the slime to `graveyard` (name, class, rarity, stars, level, hour, cause), removes it
from roster/parties/conflicts, and lowers every other slime's belonging (−8, or −25 for friends).
Causes: starvation / exhaustion (HP drains 5 %/tick at zero food or energy), killed hunting, brawl (8 % HP per
brawl round), fell in battle. Safety valves: auto-care, the 30 % HP hunt gate, and mediation.

### 5.11 Dungeons (`dungeon.py`, `Game.descend`, `Game.grind`)
Dungeons only *generate waves* (lists of scaled `Enemy` copies via `scale_enemy`); the fight is `BattleSystem.run`.

| | **The Hollow Descent** (main) | **The Gloop Pit** (grinding) |
|---|---|---|
| Purpose | progression, bosses, purple gel, essence | levelling up |
| Difficulty | floor *f*: stats ×1.15^(f−1) on tier pool 1/2/3 (floors 1–4 / 5–8 / 9+), loot +25 %/floor | depth 1–5 = enemy level (party avg −2 … +2); stats +12 %/level above the tier base |
| Death | **permadeath** (gear of the fallen is lost unless a survivor recovers it) | none: knocked-out slimes drop to 1 HP but lose XP (40 % of the next level), 25 morale and their gear |
| XP | split among survivors | every survivor gets 35 % of the wave's XP (full, not split) |
| Loot | white gel, food, essence; purple chance ×1.15^(f−1) (cap 50 %) | 50 % loot, **no purple gel** |
| Bosses | every 5th floor: Hollow Warden (f5), Parched King (f10+, +25 %/cycle) with escorts; first clear pays 3 purple gel | – |
| Time | 3 h per floor attempt | 2 h per run |
| Exit rule | walk floors **in order**; leave **only at a checkpoint** (after a boss floor); `enter_dungeon(pid, start)` / `delve_next` / `delve_camp` / `leave_dungeon` | **commitment**: `grind(runs=N)` runs all N unless the whole party is knocked out; camps (sleeps) between runs when hurt |
Time passing means hunger: long grinds need Food, or slimes starve.

### 5.12 Library, elements & spell lab (`academy.py`, `elements.py`, `spells.py`)
**Tasks.** Studying and researching are timed *tasks*: the slime's state becomes `studying`
with `slime.task = {kind, ticks_left, ...}`; `AcademySystem.tick` resolves it. Busy slimes can't hunt,
fight, merge or sleep (`Slime.busy`); a brawl or `recall` cancels the task. (Sparring is separate, §5.13.)

**Elements.** Four basics; `RECIPES` maps an unordered pair to a result element (tier 2 = two basics,
tier 3 = a compound + anything). Every element has `components` (basics). Effectiveness uses the wheel
`water > fire > wind > earth > water` on components (×1.5 / ×0.7, mixed = ×1).

**Mastery** (slime fields `attuned`, `mastery_xp`): requires **≥ 3★, any class**. Cap = 2·(stars−1);
attunement slots = stars−1 (+1 mage). Levels from cumulative XP `[20, 60, 120, 200, 320, 480, 700, 1000]`.
Study session = 30 XP (×1.5 mage); casting in battle adds 1 XP per cast. Effective mastery of a compound
element is the **weakest component**. Spell power ×(1 + 0.06 × effective mastery). Non-mages scale elemental
spells with `max(mag, 0.85·atk)`.

**Library.** Catalogue = tier-1 spells (data) + `discovered` fusions. Learning needs attunement, mastery
≥ 1/3/5 by tier, and a fee; slimes hold 4 learned spells (+1 at Library L3, +2 at L5). Tier-3 spells and
tier-3 research need Library level 3 (the Restricted Section).

**Spell lab (research).** Pick two learned elemental spells whose elements have a recipe. Needs attunement to
all components, mastery ≥ 3 (tier 2) or 5 (tier 3), HP ≥ 50 %, and a fee (15/40 essence, tier 3 also purple
gel). Takes 6/10 h; success chance `0.5 + 0.06·(mastery − need) + 0.002·cast stat (+0.1 mage)` clamped 25–95 %.
Success registers a new `Ability` (power = avg × 1.15/1.3, cooldown +1, kind by a mix table, AoE if either parent
is) and adds it to the Library; failure backfires for 35 % max HP but never kills. Fused spells are persisted
in the save (`custom_spells`, `discovered`) and re-registered on load.

### 5.13 Sparring, Rest Area & buildings (`sparring.py`, `buildings.py`)
**Training is about fighting style, not XP.** `Game.spar(a, b, discipline)` runs `BattleSystem.duel`: a non-lethal
friendly match (`Combatant.nonlethal`: reaching 1 HP = *yielded*, the match ends; nothing can die). No XP or loot.
Both fighters gain **style XP** in the arena's discipline: `15 × grounds multiplier × 1.5 (own class discipline)
× 1.3 (winner)`; an odd party member drills on a dummy at half rate without HP loss. A duel costs 2 white gel and
the group spends 3 game hours. Style levels (cumulative XP `[30, 80, 150, 250, 400, 600, 850, 1150, 1500, 2000]`)
are capped by the **Training Grounds** level (4/6/8/10/10). Perks per level — sword: +3 % attack-stat damage and
−2 % damage taken; archery: +2 % crit and +3 % speed; magic: +3 % magic damage/healing. Duels also grow bonds and
morale. Slimes below 40 % HP can't spar.

**Rest Area.** State `resting`. `buildings.rest_tick` heals `30/45/60/80/100 %` of max HP per hour by level (not
while starving), restores energy and morale, and releases the slime when full. Capacity is 5 per level. With
auto-care on, idle slimes under 50 % HP admit themselves if there is room. `party_rest` and the grind's
`auto_rest` use it first and fall back to plain sleep.

**Buildings.** Registry of `Building(key, levels, upgrade_costs)`; `BuildingManager` stores levels and exposes
effect getters: Rest Area (capacity/heal), Training Grounds (style cap, style XP ×1+0.15/lvl), Library (study ×,
research +4 %/lvl, spell slots, tier-3 gate), Barracks (morale target +2/lvl, faster drift, bonds ×1+0.25/lvl,
synergy ×1+0.2/lvl). Upgrades cost white gel (≈ 60–100 × L^1.7), essence from level 3, purple gel from level 5.

### 5.14 Compatibility, morale & the Council (`social.py`)
**Bonds** (−40..60 per pair): sparring +3, fighting side by side +2, mediation +10, quarrels −3, brawls −10.
**Compatibility** (−100..100) = trait chemistry table (±30) + class (rivals −25, same +6, complementary pairs
up to +14) + elements (shared +8 each, fusable partners +12) + friendship +10 + bond − open quarrel 20.
It scales quarrel odds (×0.4 … ×2), merge XP (±25 %) and **party synergy**: average pairwise compatibility →
±10 % power for every member (Barracks scales it).
**Morale** (0–100, default 60): drifts 8 %/h toward `35 + 55 × mood (+ barracks)`; victories +8 (+4 boss),
defeats −15, an ally dying −4 (a friend −20), brawls −15, resting +3…7/h, successful mediation +10. Battle power
× `0.85 + 0.30 × morale/100`; below 20 a party member freezes 25 % of its turns.
**Council** (`Game.council()`): every slime gets a keep score = power 35 % + quality (stars/rarity) 20 % + XP
invested 10 % + spells/mastery 10 % + social value 15 % + "in a party" 10 %. Top 40 % = KEEP, bottom 25 %
= SACRIFICE?, rest FLEX, with reasons. Merge suggestions rank `XP gained − 3 × colony morale cost`; the merge
itself transfers half of the donor's bonds to the target and lowers colony morale (friends −25, others −5).

### 5.15 Delves, scouting, gear & sacrifice stress (`Game`, `dungeon.py`, `equipment.py`)
**Delves & progress.** Every slime stores `progress` = the deepest floor it has *cleared*. A party may start at floor 1 or at
`c + 1` for any checkpoint `c` (a multiple of 5) up to its **least-travelled member** (`entry_options`) — so a
fresh slime pulls the whole party back to floor 1, and nobody is ever carried past floors they have not walked.
`enter_dungeon(pid, start)` flags every member `in_dungeon="main"` (no hunting, sparring, colony rest, equipping,
merging …) and records `delves[pid] = {floor, start, hours}`. Parties are independent: several can be inside at
once and **any party may walk the same floors again** (floors are fixed by `dungeon_seed`; the boss bounty is paid
once per boss floor for the colony). `delve_next` fights the current floor; clearing it sets `progress` for
the survivors and the colony's knowledge of that floor to 100 %. **Leaving** (`leave_dungeon`) is only possible when
`(floor − 1) % 5 == 0` — right after a boss floor (or before the first fight) — so training and the Academy happen
between segments; the party may also push on. `delve_camp(hours)` heals by sleeping inside (8 %/h; ambush chance
`0.10 × (1+0.1·floor) × (1 − 0.6·knowledge)` per hour, 10–30 % max HP). The delve also ends if the whole party dies.

**Scouting by floor.** `scout(pid, first, last, hours)` (1–10 consecutive floors, any range). Each floor needs
`3h × (1 + 0.12·(floor−1)) / skill` hours, multiplied by a hidden seeded factor in 0.85–1.20 (`dungeon.floor_hours`);
`scout_plan` shows the nominal figure, the low/high range and a safe budget. Skill = 0.8 + 0.1 per explore-stance
member + 0.15 per rogue/ranger + Pathfinder outlook. **The party must reach 100 % of every targeted floor within its
hour budget; if not, the whole party is lost** (permanent, gear gone) and only a half-finished note survives
(50 % of what it had learned). Success sets knowledge to 100 % and returns the party as soon as it is done; food
(1 per budgeted hour) is paid up front and never refunded. Scouts need `progress ≥ first − 1`. Hourly ambushes
(`0.12 × (1+0.06·floor)/strength × (1 − 0.7·knowledge)`) can kill individual scouts. `dungeon.intel_lines` reveals per
floor: ≥20 % count & tier, ≥40 % enemy types & elements, ≥60 % boss, ≥80 % abilities / HP / purple odds, 100 %
weaknesses & loot; a floor known to the party grants up to +10 % power and fewer ambushes.

**Equipment.** `Gear(key, slot, tier, stats, cost)`; the colony `Inventory` is a Counter, a slime holds
`gear {slot: key}` and `max_stats()` adds the bonuses. Armory level gates purchasable tier (1/2/3 at L1/L3/L5);
dungeons drop gear (Pit 15 %, Descent 30 %, bosses guaranteed). **Gear recovery**: when a slime falls in a dungeon
(`_drop_gear`), each item is carried back with chance
`clamp(0.5 + 5·(party synergy − 1) + compat(fallen, best survivor)/400, 0.10, 0.95)`; failures are lost for good
in the Descent, or kept in the Pit's `pit_lost` list where each later Pit victory has `15 % × synergy` per item to
dig it up. Outside dungeons a dead slime's gear returns to the inventory.

**Sacrifice stress.** `merge` adds +1 stress (decays 1/day). Morale hit = base × (1 + 0.6·stress), with base −8 for
bystanders, −30 for friends/bonded, −10 for the target (guilt). Stress also lowers every morale target by 6 per point
(max 30). The Council's cost estimates include it.

### 5.16 Web edition (`webapi.py`, `serve.py`, `web/`, `tools/build_web.py`)
**One engine, three front-ends.** The rules never touch the UI: the terminal CLI, the local web server and the
in-browser Pyodide build all call `Game`.

```
 browser UI (web/app.js) ──backend.call(cmd, args)──▶ ServerBackend ── POST /api ──▶ serve.py ─┐
        │                                      └────▶ PyodideBackend ── in-page ──────────────┤
        ▼                                                                                      ▼
  localStorage save  ◀── envelope {ok, error, log[], result, state, save} ◀──────────── webapi.Session.call
```

* **Command API** (`webapi.HANDLERS`, registered with `@command`): ~60 verbs (pull, feed, hunt, spar, scout, grind,
  enter_dungeon, delve_next, delve_camp, study, learn, research, upgrade, buy_gear, merge, council …). Each returns
  `(log lines, result)`; `GameError`s and bad input become `ok: false` with a message — the engine is never exposed to
  tracebacks. Battle reports travel as `result.battle[]` (`log`, `victory`, `rounds`, `xp`, `loot`, `deaths`).
* **Snapshot** (`webapi.snapshot`): every response carries the full render-ready state (slimes with derived values,
  parties + synergy, buildings, dungeon intel, library, gear, zones, elements …) so the UI needs no extra round trips
  and cannot drift from the engine. Static data (zones, elements, gear, classes, disciplines) comes from the same
  registries, so new content shows up in the browser without front-end changes (unknown classes get a hashed colour).
* **Persistence**: the browser keeps the last `save` (the normal `Game.to_dict()`) in `localStorage` and replays it with
  the `load` command on start-up, so the server (or a Pyodide worker) is stateless across restarts. Export / Import
  moves saves between browsers. The server holds a single `Session` guarded by a lock (single-player, localhost).
* **Transports** (`web/backend.js`): `chooseBackend()` pings `/api/ping`; if the Python server answers it uses
  `ServerBackend`, otherwise it boots `PyodideBackend` (vendored runtime first, CDN fallback), unpacks
  `slime_gacha.zip` and calls `Session.call_json`.
* **Static build**: `tools/build_web.py` copies `web/`, zips the `slime_gacha` package and vendors the five Pyodide
  files (~14 MB total), producing a self-contained, offline-capable `dist/`.
* **UI**: vanilla JS/CSS without a build step. One `render()` rebuilds the page from `S.state`; actions are
  `data-act` attributes dispatched through a table (`A`), so adding a button is one table entry plus the API verb.
  Dangerous actions (merge, enter the Descent, scout, Pit commitment) ask for confirmation and spell out the rules.

### 5.17 Specialization & outlook (`specialization.py`, `outlook.py`)
**Hybrid classes.** Every archetype has a primary discipline (sword / archery / magic). Training (sparring) in a
*different* discipline up to style level 3 — plus slime level 5 — lets the slime **specialize** for 100 white gel +
25 essence. The spec is looked up by `(archetype, secondary)` first, then `(primary, secondary)`:
Battlemage (sword+magic), Spellknight (magic+sword), Arcane Archer (archery+magic), Hexshot (magic+archery),
Swashbuckler (sword+archery), Bulwark Archer (archery+sword), Battle Medic (medic+sword), Death Knight
(necromancer+sword), Shadowcaster (rogue+magic). A spec adds stat shifts computed from the *pre-shift* stats
(e.g. `mag += 0.5 · atk`), a signature ability, a new title, and affinity (×1.5 style xp) in both disciplines. It is
permanent and stored on the slime (`spec`, `spec_disc`); `Slime.max_stats()` applies it after gear.

**Outlook.** Slimes count experiences (`exp`: spar, pit, delve, scout, hunt, study). With ≥5 and a 20 % lead over
the runner-up, the favourite becomes an outlook: Duelist (+10 % style xp), Grinder (+10 % Pit xp, KO costs 30 % less xp /
40 % less morale), Delver (+5 % party power in the Descent by share), Pathfinder (+0.1 scouting skill), Forager
(+10 % hunt loot), Scholar (+10 % study xp, +5 % research). Doing your favourite thing adds +3 esteem, and the slime
asks for it when esteem is its dominant need. First draft of the "slimes think differently depending on what they do"
idea.

### 5.18 Floor-50 content engine (`terrain.py`, `bestiary.py`, `dungeon.py`)
- **Terrains** (29, 12 kinds: valley, dunes, islands, caverns, tundra, volcano, swamp, canyon, cliffs, plains, barrens, ruins) boost or dampen elements (x1.25 / x0.8), may deal a per-round hazard (% max HP; immune elements exempt) or add crit chance. `battle.run(..., terrain=)` applies them; sparring ignores terrain.
- **Bestiary**: 8 roles (swarmer..support) x floor-derived unit stats; 71 monsters in ~20 families (goblins, direwolves, orcs, ogres, trolls, scarabs, undead, sea, golems, imps, dragonkin, ...) with ~50 monster moves and summons. 10 bosses (floors 5,10,...,50; floor 50 = the Parched King, completing the Descent).
- **Floor plan**: generated sequentially from the dungeon seed, per 10-floor palettes; terrain never repeats consecutively and no (terrain, family, pattern) signature repeats within 4 floors. Patterns: swarm, warband (leaders+followers of two families, e.g. goblins with direwolves, orcs with ogres), rabble, siege, ambush. Boss floors use the boss lair terrain.
- **Daily Pit**: `pit_theme(seed, day)` picks a terrain and two featured families, never the same as yesterday; waves are drawn from the featured families.
- **Difficulty**: `player_curve(level) x difficulty(floor)` (difficulty ramps 1.0->1.65 over floors 1-8); calibrated by simulation so an unequipped rare 3-star party wins ordinary floors ~90-100% and bosses ~50-65%.
- Intel: terrain shown from 20% knowledge, terrain advice at 100%. SAVE_VERSION 7; scouting budget up to 240 h.

### 5.19 Relics & the Wayfarer's Rift (`items.py`, `Game.adventure`, forge methods)
- **Adventure dungeon**: any 1-5 slimes (no formal party) fight waves one level above their average (foes = 0.75 x party size), themed by terrain/families like the Pit. Nobody dies; a knocked-out slime loses morale and its relics lose durability. Each defeated foe may drop a relic; XP is only 25%. A lure (1 purple gel per run) multiplies non-common odds x4.
- **Relics** are unique items: base type (12), rarity (common..legendary at 97 / 2.7 / 0.27 / 0.03 %, steeper star falloff than slimes), 1-5 stars, level 1-10 per star, durability, mods (crit rate, crit damage, elemental damage, lifesteal; rarity step = number of mods). Power = rarity x star x level multipliers.
- **Compatibility** (0-100): class fit, matching attuned element, a stable personal chemistry, and a bond that grows with battles together; scales the item's stats x0.85-1.15.
- **Durability**: -1 per fight, -8 when the wielder is knocked out; at 0 the relic shatters into half the salvage. Repair costs white gel.
- **Materials** (scrap, alloy, crystal, stardust by tier): salvaging yields more, and one tier better, from higher-level/star relics. Levelling needs own-tier materials; star ascension (level 10) needs Armory level >= current stars; at 5 stars / level 10 the rarity can be raised (Armory 5) and gains a mod.
- **Ego relics**: a 5-star legendary relic + a sacrificed 5-star legendary slime. Stats x(1.5 + 0.02 x soul level), mods doubled, unbreakable, wieldable only by 5-star legendary slimes. Each costs a soul, hence three ego slots need three sacrifices (sacrifice stress +2).
- Relics of a slime that dies in the Descent are carried back by survivors (synergy chance) or lost; elsewhere they return to the vault. Plain Armory gear still exists and works as before. SAVE_VERSION 8.

### 5.20 Slime ascension, stones, merging & the chamber (`ascension.py`)
- **Five rarities**: common, uncommon, rare, epic, legendary (gacha 90 / 8 / 1.9 / 0.09 / 0.01 %). **Rarity ascension** costs white gel to reach the next rarity: 10 / 100 / 1000 / 10000. **Star ascension** costs ascension stones: 10 / 100 / 1000 / 10000 common-stone equivalents for 1>2 ... 4>5. Both are permanent and raise stats.
- **Stones** come in the five rarities; 100 of one merge into 1 of the next (a stone is worth 100^rarity commons). Payment spends the cheapest stones first and gives change in smaller stones.
- **Sources**: the **Starfall Quarry** (1-5 slimes, monsters +1 level, no deaths, ~140 common-equivalents per run for a strong party; rates 97 / 2.6 / 0.4 / 0.01 %), small common drops in the Pit and Rift, boss hoards in the Descent, and the Destruction Chamber.
- **Merging** now gives only the XP the donor collected (+/-25% compatibility) and a share of its stats. The share is 20% at zero merge growth and falls by 0.2 per +100% growth already in that attribute (18% at +10%), flat 1% from +100% on. There is no cap, only diminishing returns.
- **Destruction Chamber** (building, 5 levels): destroys a slime for white gel (5 x 10^rarity x star factor) and stones (scaled by rarity and the stones its stars cost); a sacrifice with morale cost and sacrifice stress. Its relics return to the vault.
- Not yet built: star attributes, rarity skills, weapon proficiency, potions (see ROADMAP M16).

### 5.21 Stamina, star attributes, rarity skills, potions & weapons (`attributes.py`, `potions.py`, `items.py`)
- **Stamina** is a base attribute of every slime (class base + growth per level, scaled by rarity/stars). Each battle action costs stamina (8 + 8 x ability power, x1.5 for area attacks; guards and heals cheaper). A slime out of stamina is *winded*: its damage is x0.6 for that action. Between rounds it catches its breath; between fights it refills 10%/hour (x2.5 asleep or resting). Pit, Rift and Quarry parties camp when anyone is under 35% stamina. Sparring ignores stamina.
- **Star attributes**: every extra star adds one class-specific attribute (e.g. Barbarian: crit damage, guard, regeneration, lifesteal; Mage: spell power, resist, crit rate, crit damage). They scale slightly with rarity and combine with relic mods in battle (evasion, guard, resist, regeneration and spell power are new combat hooks).
- **Rarity skills**: one skill per rarity step above common, per class (Moon Slash, Aura Blade, Earthsplitter, Titan Break; Mana Lance, Starfall, ...). Ascending a slime's rarity unlocks the next one.
- **Herbs & potions**: four coloured herbs - green (health), red (strength), blue (armor), yellow (stamina) - make the four basic potions (vigor, might, ironhide, stamina). Two different herbs combine into a further-attribute potion: green+red Bloodthirst (lifesteal), green+blue Bulwark (guard), green+yellow Renewal (regeneration), red+blue Arcane (magic, spell power), red+yellow Fury (crit), blue+yellow Gale (speed, evasion); a combo needs 60% of the herbs of each colour. The terrain of the day decides the plentiful herb (70% of drops). The **Alchemy Lab** (building, level caps the grade) lets a slime brew (2 h per grade); grades 1-5 give +10/15/20/30/40% for 16-32 h. The stamina potion raises max stamina and multiplies recovery. A magical brewer and a roomy lab improve success (combos are 5% fiddlier); failure loses the gel and half the herbs; a brew can come out a grade better.
- **Slime autonomy** (toggle, default on): slimes help themselves to at most 66% of a stock without asking - tired ones drink stamina potions, hurt ones vigor, class-suited potions (max 2) before a Descent/Pit/Rift/Quarry trip, and worn gear is mended with up to 66% of the scrap. For potions the reserve is ceil(34% of the most ever held).
- **Weapons**: weapons belong to six families (sword, hammer, dagger, bow, staff, tome). A slime keeps up to three families in mind (a fourth makes it forget the least practised one and its proficiency); each fight with a weapon adds proficiency (+3% weapon stats per level, max 10). Each slime has a favourite family (compatibility bonus). A weapon bonded with its wielder steadies morale after fights. Weapons of rare quality and above are named. A slime can repair its own relics with scrap.

### 5.22 Emotions, awakening & wider autonomy (`emotions.py`, `awakening.py`)
- **Thirteen feelings** (joy, anger, sadness, fear, pride, calm, anxiety, loneliness, determination, affection, guilt, dread, wonder), each 0-100, fade hourly (twice as fast asleep) and are stirred by events: victory (joy, pride), defeat (sadness, anger, fear), a friend's death (grief, anger), quarrels and brawls (anger), reconciliation (calm, affection), merges and the chamber (guilt for the survivor, fear for the rest), hunger (anger), loneliness, a pat on the head. Traits shape them (grumpy: anger x1.5, timid: fear x1.5, kind: affection x1.3 ...); opposite feelings quiet each other.
- **Battle**: each feeling shifts stats and combat attributes in proportion to its intensity (anger +25% ATK -18% DEF and crit damage; sadness -20% SPD; fear -12% ATK but +evasion; calm +DEF/MAG and regeneration; dread +MAG -ATK; wonder +MAG +SPD ...). Total change per stat is capped at +-35%. A strong feeling (>= 40) is announced in the battle log. Feelings use their own dice (`mood_rng`) so they never disturb the main seeded sequence.
- **Awakening**: a 5-star legendary slime gains awareness by the hour (and from boss kills and deaths). Stages: Unaware, Deja vu, Suspicion, Awakened (about 4 / 10 / 17 days). Its thoughts - "I counted my steps, they repeat every 256", "everything I am is a line someone typed" - appear in the journal; after a save is loaded they notice the gap. On awakening it either **accepts** (wonder + calm, a permanent undercurrent of wonder) when it is loved and settled, or **despairs** (dread, sadness, a permanent undercurrent of dread) when lonely; kindness (petting, friends, affection) can turn despair into acceptance.
- **Wider autonomy** (same switch): besides potions and repairs, slimes dress themselves from the relic vault and armory stock (fill empty slots, or swap for a relic that is 25% better) while at least 34% of the most ever held is left, and once a day (06:00) a free slime brews a potion the colony is short of, using at most 66% of each ingredient. `talk` asks a slime how it feels.

### 5.23 Relationships, budding & the Keeper (`relationships.py`, `keeper.py`)
- **Ties** are reviewed once a day (12:00, own dice): **friend** (bond >= 25), **best friend** (bond >= 45 after 5 days, one each), **rival** (bond <= -12 and 2+ quarrels; rivals who make up become friends), **mentor & mentee** (8+ levels apart, same class or discipline, bond >= 15; ends when the mentee catches up), **couple** (bond >= 40, compatibility >= 20, belonging >= 60, some affection, one partner each, never kin; 20%/day). Idle slimes who get along grow closer every day (and feel affection), so ties emerge on their own over weeks.
- **Effects**: party synergy (+3% couple, +2% best friend, +1.5% mentor, +1% friend, -2% rival), feelings before a fight (couples/best friends affection and determination, rivals determination and anger, mentors pride), mentees earn +10% of the fight's XP beside their mentor, and losing a partner (sadness 55, anger, loneliness, morale) or best friend hurts far more.
- **Budding**: a couple (together 3+ days, 10-day rest between children) can have a **child** for 20 food, 10 essence, 50 gel: a level-1 slime whose name blends the parents', with one trait from each, a class from either, averaged stat variance, rarity of the lower parent (35%: the higher; 3%: one above both) and stars 1 (+1 with strong parents). Lineage (`parents`, `generation`) builds the **family tree** (units of parents with children and grandchildren; the dead stay as names).
- **The Keeper** (the player) earns XP from tending, pulling, winning, clearing floors, scouting, mediating, forging, brewing, merging, ascending, new ties and children (daily caps stop farming). Level 1-30, one skill point per level plus one every 5. Four branches x four skills (max rank 3): Caretaker (Gentle Hands, Green Thumb, Soothing Voice, Lullaby), Tactician (Battle Cry, Field Medic, Keen Eye, Quartermaster), Fortune (Lucky Charm, Stonecutter, Appraiser, Thrifty), Matchmaker (Matchmaker, Mentor's Eye, Peacemaker, Midwife), plus four daily abilities unlocked by a branch's first skill: Rally, Soothe, Fortune's Favor (double rare odds on the next pull), Bond Night. Skills feed small multipliers into the gacha, social engine, conflicts, buildings, scouting, camps, herb and stone drops, salvage and autonomy share.

## 6. Extensibility recipes
| Want | Do |
|------|----|
| New class | `register_archetype(Archetype(...))` |
| New ability | `register_ability(Ability(...))` and reference its key from an archetype |
| New ability kind | add handler in `battle.KIND_HANDLERS` |
| New zone / enemy | `register_zone(...)`, `register_enemy(...)` |
| New arena / style | `register_discipline(Discipline(...))` in `sparring.py` (+ a perk in `battle._style_attack`); set `Archetype.discipline` |
| New hybrid class | `register_spec(Spec(...), pair=(primary, secondary))` or `cls=(archetype, secondary)` |
| New outlook | add an `Outlook` to `outlook.OUTLOOKS`, count it with `outlook.bump`, and use `outlook.has` where its perk applies |
| New web verb | `@command("name")` handler in `webapi.py` + an entry in `A` (app.js) |
| New building | `register_building(Building(...))` + an effect getter on `BuildingManager` |
| New trait chemistry | add a row to `social.TRAIT_PAIRS` |
| New element / recipe | `register_recipe(a, b, result, name, emoji)` in `elements.py` |
| New library spell | `register_ability(Ability(..., element="fire", tier=1))` - tier 1 spells go on sale automatically |
| New dungeon | write a `*_wave(...)` function in `dungeon.py` + a `Game` method that calls `BattleSystem.run(permadeath=..., split_xp=...)` |
| New trait | add to `ai.TRAITS` dict (decay/conflict modifiers) |
| New resource | add to `config.RESOURCES` |
Plugins: any module placed in `slime_gacha/plugins/` is auto-imported at start (optional dir).

## 7. Persistence
`Game.save(path)` → JSON `{version 7, tick, buildings, bonds, intel{floor→%}, delves, bounties, inventory, pit_lost, sacrifice_stress, dungeon_seed, main_floor, rng_state, wallet, gacha{pity, last_free_day, next_id}, parties, graveyard, slimes[], conflicts[], friends}`. older saves load (gel/silver→white_gel, gold→purple_gel).
Versioned for forward migration. Unknown archetype keys on load are skipped with a warning (mod removal safe).

## 8. Error handling
Domain errors derive from `GameError` (`NotEnoughResources`, `InvalidAction`). The CLI catches
`GameError` and prints the message; bugs still raise.

## 9. Testing strategy
`unittest`, seeded RNG: gacha rates and pity, stat scaling, needs gating, merge XP maths,
hunt rewards, battle determinism, save/load round-trip, registry extension (adds a Bard in a test).

## 10. Open questions
Economy balance, offline progress while app closed (real-clock "day" for the free pull vs game day), revival items / necromancer resurrection, equipment, formations.
