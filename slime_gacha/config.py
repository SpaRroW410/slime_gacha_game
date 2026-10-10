"""Tunable constants. Change numbers here to rebalance without touching logic."""

# ---- Rarity ---------------------------------------------------------------
RARITIES = ["common", "rare", "epic", "legendary"]            # ordered low -> high
RARITY_RATES = {"common": 60, "rare": 28, "epic": 9, "legendary": 3}   # percent-ish weights
RARITY_STAT_MULT = {"common": 1.0, "rare": 1.25, "epic": 1.6, "legendary": 2.2}
RARITY_LOOT_MULT = {"common": 1.0, "rare": 1.1, "epic": 1.25, "legendary": 1.5}
RARITY_COLOR = {"common": "·", "rare": "★", "epic": "★★", "legendary": "★★★"}
PITY_EPIC = 10          # guaranteed epic-or-better within this many pulls
PITY_LEGENDARY = 50     # guaranteed legendary within this many pulls
VARIANCE = 0.10         # +/- per-slime stat roll

# ---- Economy --------------------------------------------------------------
RESOURCES = ["gel", "food", "essence"]       # add a name here to add a resource
STARTING_WALLET = {"gel": 1000, "food": 10, "essence": 0}
PULL_COST = 100
PULL10_COST = 900
FOOD_NUTRITION = 40     # food need restored per Food item
MEDIATE_SNACK_COST = 2

# ---- Needs (Maslow) -------------------------------------------------------
# Order matters: lowest tier first. Higher tiers are suppressed while a lower one is unmet.
NEED_ORDER = ["energy", "food", "safety", "belonging", "esteem"]
NEED_THRESHOLD = 40
# Per-tick decay when idle.
NEED_DECAY = {"energy": 3.0, "food": 3.5, "safety": 0.0, "belonging": 1.5, "esteem": 1.0}
HUNT_DECAY_MULT = {"energy": 2.5, "food": 1.8}   # hunting is tiring
SLEEP_ENERGY_GAIN = 14
SLEEP_HP_REGEN = 0.08       # fraction of max HP per tick while sleeping
AUTO_SLEEP_BELOW = 25
AUTO_WAKE_AT = 90
AUTO_EAT_BELOW = 30
STARVE_HP_LOSS = 0.05       # fraction of max HP per tick at zero food
MOOD_WEIGHTS = {"energy": 1.0, "food": 1.0, "safety": 0.8, "belonging": 0.6, "esteem": 0.5}
MOOD_POWER_MIN, MOOD_POWER_MAX = 0.6, 1.1

# ---- Conflict -------------------------------------------------------------
CONFLICT_BASE_CHANCE = 0.002      # per pair per tick
CONFLICT_MAX_SEVERITY = 3
CONFLICT_ESCALATE_TICKS = 6
BRAWL_HP_LOSS = 0.15

# ---- Growth ---------------------------------------------------------------
LEVEL_CAPS = [10, 25, 50]           # per evolution stage
STAGE_STAT_MULT = [1.0, 1.5, 2.1]
EVOLVE_ESSENCE_BASE = 50            # * (stage + 1)
MERGE_XP_RATIO = 0.5
MERGE_SAME_CLASS_BONUS = 1.25
MERGE_RARITY_XP = {"common": 10, "rare": 30, "epic": 80, "legendary": 200}

def xp_to_next(level: int) -> int:
    """XP needed to go from `level` to `level + 1`."""
    return int(20 * level ** 1.5)

# ---- Battle ---------------------------------------------------------------
CRIT_CHANCE = 0.08
CRIT_MULT = 1.5
ROUND_CAP = 30
MAX_PARTY = 3
GUARD_REDUCTION = 0.5

# ---- Persistence ----------------------------------------------------------
SAVE_VERSION = 1
DEFAULT_SAVE = "savegame.json"
