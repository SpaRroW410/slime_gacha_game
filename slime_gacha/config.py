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
# WHITE gel = common currency, PURPLE gel = rare currency (boosts rare pulls). Both buy pulls 1:1.
RESOURCES = ["white_gel", "purple_gel", "food", "essence"]       # add a name here to add a resource
STARTING_WALLET = {"white_gel": 100, "purple_gel": 10, "food": 15, "essence": 0}
PULL_COST = 10          # of white OR purple gel per single pull
PURPLE_RARITY_BOOST = 5.0 # multiplies rare/epic/legendary weights when paying with purple gel
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

# ---- Dungeons -----------------------------------------------------------------
# Main dungeon ("The Hollow Descent"): floor after floor, brutal, permadeath, rare purple gel.
MAIN_BOSS_EVERY = 5
MAIN_STAT_STEP = 0.15           # enemy stats +15% per floor (compounding on tier pools)
MAIN_LOOT_STEP = 0.25           # loot ranges +25% per floor
MAIN_PURPLE_STEP = 0.15         # purple-gel drop chance +15% (relative) per floor, capped
MAIN_PURPLE_CAP = 0.5
MAIN_BOSS_FIRST_CLEAR_PURPLE = 3
MAIN_FLOOR_TICKS = 3            # hours that pass per floor attempt
# Grinding dungeon ("The Gloop Pit"): safe, repeatable XP farm tuned to your party's level.
GRIND_DEPTHS = 5                # depth 1..5 = enemies (party avg level - 2) .. (+2)
GRIND_STAT_STEP = 0.12          # enemy stats +12% per level above the tier's base level
GRIND_TIER_BASE_LEVEL = {1: 1, 2: 8, 3: 18}
GRIND_XP_MULT = 0.35            # every survivor gets this share of the FULL wave XP (not split)
GRIND_LOOT_MULT = 0.5           # little loot, no purple gel
GRIND_TICKS = 2
GRIND_MIN_HP = 0.4              # auto-grind stops when anyone drops below this HP fraction

# ---- Training grounds, library, elemental mastery -----------------------------------
TRAIN_COST = {"white_gel": 2}
TRAIN_TICKS = 4
TRAIN_GAIN = 1.0                # base stat points per session (before weights/diminishing returns)
TRAIN_AFFINITY_MULT = 1.5       # training the discipline that matches your class
TRAIN_CAP_BASE = 2.0            # max trained bonus per stat = BASE + PER_LEVEL * level
TRAIN_CAP_PER_LEVEL = 0.6
TRAIN_DECAY_MULT = {"energy": 1.6, "food": 1.3}
TASK_MIN_ENERGY = 25
MASTERY_MIN_STARS = 3           # elemental mastery unlocks at 3 stars, for ANY class
MASTERY_XP = [20, 60, 120, 200, 320, 480, 700, 1000]     # cumulative xp for mastery level 1..8
MASTERY_PER_CAST_XP = 1
MASTERY_SPELL_BONUS = 0.06      # +6% spell power per effective mastery level
MAGE_SLOT_BONUS = 1             # mages can attune one extra element
MAGE_STUDY_MULT = 1.5
STUDY_COST = {"white_gel": 3}
STUDY_TICKS = 4
STUDY_XP = 30
MAX_SPELLS = 4                  # learned spells per slime (class abilities are separate)
SPELL_TIER_MASTERY = {1: 1, 2: 3, 3: 5}                  # effective mastery needed per spell/element tier
SPELL_LEARN_COST = {1: {"white_gel": 20}, 2: {"white_gel": 50, "essence": 10},
                    3: {"white_gel": 100, "essence": 30, "purple_gel": 1}}
RESEARCH_COST = {2: {"white_gel": 20, "essence": 15}, 3: {"white_gel": 40, "essence": 40, "purple_gel": 2}}
RESEARCH_TICKS = {2: 6, 3: 10}
RESEARCH_MIN_HP = 0.5
RESEARCH_BACKFIRE = 0.35        # fraction of max HP lost when an experiment fizzles
IMBUE_ATK_FACTOR = 0.85         # non-mages channel elements through brute force: max(mag, 0.85 * atk)
ELEMENT_ADVANTAGE = 1.5
ELEMENT_DISADVANTAGE = 0.7

MIN_HUNT_HP = 0.3           # fraction of max HP needed to be sent on a hunt

# ---- Persistence ----------------------------------------------------------
SAVE_VERSION = 4
DEFAULT_SAVE = "savegame.json"
