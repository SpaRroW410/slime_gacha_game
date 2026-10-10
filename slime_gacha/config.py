"""Tunable constants. Change numbers here to rebalance without touching logic."""

# ---- Rarity & stars -----------------------------------------------------------
RARITIES = ["common", "rare", "epic", "legendary"]            # ordered low -> high
RARITY_RATES = {"common": 90, "rare": 9, "epic": 0.9, "legendary": 0.09}   # weights, normalised on roll
RARITY_STAT_MULT = {"common": 1.0, "rare": 1.25, "epic": 1.6, "legendary": 2.2}
RARITY_LOOT_MULT = {"common": 1.0, "rare": 1.1, "epic": 1.25, "legendary": 1.5}
RARITY_TAG = {"common": "C", "rare": "R", "epic": "E", "legendary": "L"}
# Star rating 1..5. P(star = k) ~ exp(-lambda * (k-1)); lambda grows with rarity, so high stars are
# exponentially rarer and the drop-off is steeper at higher ranks.
MAX_STARS = 5
STAR_DECAY = {"common": 0.7, "rare": 1.0, "epic": 1.3, "legendary": 1.6}
STAR_STAT_MULT = [1.0, 1.1, 1.25, 1.45, 1.7]
PITY_EPIC = 0           # 0 = disabled (stated rates are honest). Set e.g. 10 / 50 to enable pity.
PITY_LEGENDARY = 0
VARIANCE = 0.10         # +/- per-slime stat roll

# ---- Economy --------------------------------------------------------------
# silver = common currency, gold = rare currency (boosts rare pulls). Both buy pulls 1:1.
RESOURCES = ["silver", "gold", "food", "essence"]       # add a name here to add a resource
STARTING_WALLET = {"silver": 100, "gold": 10, "food": 15, "essence": 0}
PULL_COST = 10          # of silver OR gold per single pull
GOLD_RARITY_BOOST = 5.0 # multiplies rare/epic/legendary weights when paying with gold
DAY_TICKS = 24          # one game day; one free pull per day
FOOD_NUTRITION = 50     # food need restored per Food item
MEDIATE_SNACK_COST = 2

# ---- Needs (Maslow) -------------------------------------------------------
# Order matters: lowest tier first. Higher tiers are suppressed while a lower one is unmet.
NEED_ORDER = ["energy", "food", "safety", "belonging", "esteem"]
NEED_THRESHOLD = 40
# Per-tick decay when idle.
NEED_DECAY = {"energy": 2.5, "food": 2.0, "safety": 0.0, "belonging": 1.5, "esteem": 1.0}
HUNT_DECAY_MULT = {"energy": 2.5, "food": 1.8}   # hunting is tiring
SLEEP_ENERGY_GAIN = 14
SLEEP_HP_REGEN = 0.08       # fraction of max HP per tick while sleeping
AUTO_SLEEP_BELOW = 25
AUTO_WAKE_AT = 90
AUTO_EAT_BELOW = 30
STARVE_HP_LOSS = 0.05       # fraction of max HP per tick at zero food/energy - slimes can die
MOOD_WEIGHTS = {"energy": 1.0, "food": 1.0, "safety": 0.8, "belonging": 0.6, "esteem": 0.5}
MOOD_POWER_MIN, MOOD_POWER_MAX = 0.6, 1.1

# ---- Conflict -------------------------------------------------------------
CONFLICT_BASE_CHANCE = 0.0004     # per pair per tick
CONFLICT_MAX_SEVERITY = 3
CONFLICT_ESCALATE_TICKS = 8
BRAWL_HP_LOSS = 0.08       # brawls can kill an already wounded slime

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
PARTY_SIZE = 5           # fixed party size: must be a multiple of 5 (5, 10, 15 ...)
GUARD_REDUCTION = 0.5

MIN_HUNT_HP = 0.3           # fraction of max HP needed to be sent on a hunt

# ---- Persistence ----------------------------------------------------------
SAVE_VERSION = 2
DEFAULT_SAVE = "savegame.json"
