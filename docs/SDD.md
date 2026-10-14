# Software Design Document — Slime Gacha (prototype v0.1)

> **v0.2 changes**: permadeath, rarity 90/9/0.9/0.09, 1–5★ ratings, white/purple gel currencies, free daily pull, fixed-size parties (§5.1, 5.9, 5.10).
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
| Exit rule | **no exit** until the segment boss (5 floors) falls or everyone is dead; `enter_dungeon` / `delve_next` / `delve_camp` | **commitment**: `grind(runs=N)` runs all N unless the whole party is knocked out; camps (sleeps) between runs when hurt |
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
**Delves.** The Descent is split into segments (floors 5k+1 … 5k+5, the last one a boss). `enter_dungeon(pid)` flags
every member `in_dungeon="main"` (they can't hunt, spar, study, rest, equip, merge, sleep via the colony …) and
records `delves[pid] = {floor, start, hours}`. There is deliberately **no API to leave**: `delve_next` fights the
current floor (floors are fixed by `dungeon_seed`), `delve_camp(hours)` heals by sleeping in the dungeon
(8 %/h, ambush chance `0.10 × (1+0.1·floor) × (1 − 0.6·knowledge)` per hour, damage 10–30 % max HP). The delve ends when
the boss falls (checkpoint `main_floor` advances, first clear pays 3 purple gel, flags clear) or the whole party
dies. A party that loses members keeps going short-handed; after exit it must be refilled before another fight.

**Scouting.** `scout(pid, hours 2–24)` commits a full party to the next segment. Knowledge
`k' = 100 − (100 − k)·exp(−0.10 · skill · hours)` (skill = 0.8 + 0.1 per explore-stance member + 0.15 per rogue/ranger,
max 2.0), so it is a function of time spent inside with diminishing returns. Hourly ambush chance (stronger
segments, weaker parties, less intel ⇒ more danger) can kill scouts; if all die nothing is learned. Time spent
delving or camping also adds 1.5 %/h. `dungeon.intel_view` reveals per floor: ≥20 % count & tier, ≥40 % enemy
types & elements, ≥60 % boss, ≥80 % abilities / total HP / purple odds, 100 % weaknesses & loot. Knowledge gives
the party up to +10 % power inside the Descent and fewer ambushes.

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

## 6. Extensibility recipes
| Want | Do |
|------|----|
| New class | `register_archetype(Archetype(...))` |
| New ability | `register_ability(Ability(...))` and reference its key from an archetype |
| New ability kind | add handler in `battle.KIND_HANDLERS` |
| New zone / enemy | `register_zone(...)`, `register_enemy(...)` |
| New arena / style | `register_discipline(Discipline(...))` in `sparring.py` (+ a perk in `battle._style_attack`); set `Archetype.discipline` |
| New building | `register_building(Building(...))` + an effect getter on `BuildingManager` |
| New trait chemistry | add a row to `social.TRAIT_PAIRS` |
| New element / recipe | `register_recipe(a, b, result, name, emoji)` in `elements.py` |
| New library spell | `register_ability(Ability(..., element="fire", tier=1))` - tier 1 spells go on sale automatically |
| New dungeon | write a `*_wave(...)` function in `dungeon.py` + a `Game` method that calls `BattleSystem.run(permadeath=..., split_xp=...)` |
| New trait | add to `ai.TRAITS` dict (decay/conflict modifiers) |
| New resource | add to `config.RESOURCES` |
Plugins: any module placed in `slime_gacha/plugins/` is auto-imported at start (optional dir).

## 7. Persistence
`Game.save(path)` → JSON `{version 6, tick, buildings, bonds, intel, delves, inventory, pit_lost, sacrifice_stress, dungeon_seed, main_floor, rng_state, wallet, gacha{pity, last_free_day, next_id}, parties, graveyard, slimes[], conflicts[], friends}`. older saves load (gel/silver→white_gel, gold→purple_gel).
Versioned for forward migration. Unknown archetype keys on load are skipped with a warning (mod removal safe).

## 8. Error handling
Domain errors derive from `GameError` (`NotEnoughResources`, `InvalidAction`). The CLI catches
`GameError` and prints the message; bugs still raise.

## 9. Testing strategy
`unittest`, seeded RNG: gacha rates and pity, stat scaling, needs gating, merge XP maths,
hunt rewards, battle determinism, save/load round-trip, registry extension (adds a Bard in a test).

## 10. Open questions
Economy balance, offline progress while app closed (real-clock "day" for the free pull vs game day), revival items / necromancer resurrection, equipment, formations.
