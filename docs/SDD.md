# Software Design Document — Slime Gacha (prototype v0.1)

> **v0.2 changes**: permadeath, rarity 90/9/0.9/0.09, 1–5★ ratings, silver/gold currencies, free daily pull, fixed-size parties (see §5.1, 5.9, 5.10).

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
- **Payment**: `pull(n, pay)` with `pay ∈ {free, silver, gold}`. Silver/gold cost 10 each per pull.
  **Gold** multiplies the rare/epic/legendary weights by `GOLD_RARITY_BOOST` (5×).
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
| attack | max-damage ability, focus lowest-HP foe | +loot (gel), +injury |
| heal | heals ally < 60 % HP if able, else attack | party recovers HP, −yield |
| defend | guards when ally low/self low, else attack | −injury |
| explore | random targets, +crit; scouts | +chance of rare finds (essence) |

Player changes it with `Game.set_behavior(id, stance)`.

### 5.5 HuntSystem (`hunt.py`)
`Zone(key, name, duration, danger, rewards{resource:(lo,hi)}, xp)` from a registry.
`start(slime, zone)` sets state `hunting`; `tick()` decrements; on completion rolls success from
`slime power vs zone danger`, grants resources scaled by archetype `hunt_bonus`, stance and rarity,
grants XP, applies damage (**can kill**). Exhausted slimes return early with half loot. Each zone has a small `gold_chance` (1–8 %, ×1.5 for explorers). Slimes below 30 % HP cannot be sent out.

### 5.6 BattleSystem (`battle.py`)
Turn-based auto-combat. `Combatant` wraps a slime snapshot or an `Enemy`. Order by speed each round.
Per turn: status ticks (poison/guard expiry) → AI picks ability by stance → resolve via kind handler.
Damage: `max(1, (power × stat) − 0.5 × defense) × rng(0.9, 1.1) × power_multiplier`, crit 8 % ×1.5.
Ends when a side is empty or round cap (30). Slimes at 0 HP are **dead** (removed by `Game._reap`). Survivors share XP and loot; enemies drop gold with a per-enemy chance (boss: guaranteed 5).
Returns a `BattleReport` (log lines, winner, rewards) — UI only prints it.

### 5.7 Growth (`growth.py`)
- `xp_to_next(level) = 20 × level^1.5`. Level caps per stage: 10 / 25 / 50.
- **Evolve** at cap: cost Essence (`50 × (stage+1)`), `stage += 1`, stat × 1.5, unlock an evolution ability.
- **Merge(target, donor)**: target gains `0.5 × donor.total_xp` (+ rarity bonus; ×1.25 same class),
  donor is consumed. Cannot merge into itself or while hunting. Total XP tracked so merges chain.
- Abilities unlock at levels listed in the archetype.

### 5.8 ResourceManager (`resources.py`)
Wallet of `silver` (common currency), `gold` (rare currency), `food`, `essence`. `add/spend/can_afford`, atomic `spend_many`.
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

## 6. Extensibility recipes
| Want | Do |
|------|----|
| New class | `register_archetype(Archetype(...))` |
| New ability | `register_ability(Ability(...))` and reference its key from an archetype |
| New ability kind | add handler in `battle.KIND_HANDLERS` |
| New zone / enemy | `register_zone(...)`, `register_enemy(...)` |
| New trait | add to `ai.TRAITS` dict (decay/conflict modifiers) |
| New resource | add to `config.RESOURCES` |
Plugins: any module placed in `slime_gacha/plugins/` is auto-imported at start (optional dir).

## 7. Persistence
`Game.save(path)` → JSON `{version 2, tick, rng_state, wallet, gacha{pity, last_free_day, next_id}, parties, graveyard, slimes[], conflicts[], friends}`. v1 saves load (gel→silver).
Versioned for forward migration. Unknown archetype keys on load are skipped with a warning (mod removal safe).

## 8. Error handling
Domain errors derive from `GameError` (`NotEnoughResources`, `InvalidAction`). The CLI catches
`GameError` and prints the message; bugs still raise.

## 9. Testing strategy
`unittest`, seeded RNG: gacha rates and pity, stat scaling, needs gating, merge XP maths,
hunt rewards, battle determinism, save/load round-trip, registry extension (adds a Bard in a test).

## 10. Open questions
Economy balance, offline progress while app closed (real-clock "day" for the free pull vs game day), revival items / necromancer resurrection, equipment, formations.
