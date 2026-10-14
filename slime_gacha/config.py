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
DUEL_ROUND_CAP = 80            # sparring continues until somebody yields
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

# ---- Sparring (fighting styles), rest area, morale, bonds, buildings --------------------
# Training is NOT for XP: slimes spar against each other to develop a fighting STYLE. Spars are non-lethal
# (loser is left at 1 HP) and cost no XP; the Rest Area heals everybody back to full.
SPAR_COST = {"white_gel": 2}
SPAR_TICKS = 3
SPAR_STYLE_XP = 15              # style xp per spar (winner x1.3, own-discipline x1.5, grounds level bonus)
SPAR_WINNER_MULT = 1.3
SPAR_DUMMY_MULT = 0.5           # odd slime out trains on a dummy at half rate (no HP loss)
SPAR_MIN_HP = 0.4
SPAR_BOND = 3
STYLE_AFFINITY_MULT = 1.5       # practising the discipline that matches your class
STYLE_XP = [30, 80, 150, 250, 400, 600, 850, 1150, 1500, 2000]   # cumulative xp for style level 1..10
STYLE_SWORD_DAMAGE = 0.03       # per level: +3% attack-stat damage ...
STYLE_SWORD_GUARD = 0.02        # ... and -2% damage taken (max -40%)
STYLE_ARCHERY_CRIT = 0.02       # per level: +2% crit chance ...
STYLE_ARCHERY_SPEED = 0.03      # ... and +3% speed
STYLE_MAGIC_POWER = 0.03        # per level: +3% magic damage/healing
STUDY_DECAY_MULT = {"energy": 1.6, "food": 1.3}
# Morale = "fight readiness" (0-100). Drifts toward a target set by mood; battles, deaths and bonds move it.
MORALE_START = 60.0
MORALE_BASE_TARGET = 35.0       # target = BASE + 55 * mood (+ barracks bonus)
MORALE_MOOD_SPAN = 55.0
MORALE_DRIFT = 0.08             # fraction of the gap closed per hour (+ barracks)
MORALE_POWER_MIN, MORALE_POWER_MAX = 0.85, 1.15
MORALE_BROKEN = 20              # below this a slime may freeze in battle
MORALE_FREEZE_CHANCE = 0.25
MORALE_WIN, MORALE_BOSS_WIN, MORALE_LOSS = 8, 4, -15
MORALE_ALLY_DEATH, MORALE_FRIEND_DEATH = -4, -20
# Compatibility between two slimes (-100..100) and party synergy
SYNERGY_MAX = 0.10              # a perfectly compatible party fights +10% (discord: -10%)
COMPAT_RIVAL = -25
COMPAT_SAME_CLASS = 6
COMPAT_FRIEND = 10
COMPAT_OPEN_CONFLICT = -20
COMPAT_SHARED_ELEMENT = 8
COMPAT_FUSION_PARTNERS = 12
BOND_MIN, BOND_MAX = -40.0, 60.0
MERGE_COMPAT_SWING = 0.25       # merge xp x(1 +/- 25%) depending on compatibility
MERGE_BOND_INHERIT = 0.5        # the target inherits half of the donor's bonds
MERGE_MORALE_OTHERS, MERGE_MORALE_FRIENDS, MERGE_MORALE_TARGET = -8, -30, -10
# Sacrifice stress: every merge adds 1 stress (decays 1 per day). Stress amplifies the morale hit of the next
# sacrifice and drags down everyone's morale target, so a colony that keeps sacrificing falls apart.
SACRIFICE_STRESS_DECAY_TICKS = 24
SACRIFICE_STRESS_AMP = 0.6
SACRIFICE_TARGET_PENALTY = 6
SACRIFICE_TARGET_PENALTY_MAX = 30
# Rest Area: heals fast; capacity and speed depend on its level (see buildings.py)
REST_ENERGY_GAIN = 10
AUTO_REST_BELOW = 0.5           # auto-care sends slimes under 50% HP to the Rest Area if there is room
# Library / mastery
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

# ---- Delves, scouting, gear --------------------------------------------------------------
# The Hollow Descent is delved in SEGMENTS of 5 floors ending in a boss (the checkpoint). Once a party enters,
# it cannot leave until the segment's boss is beaten or the whole party is dead. The Gloop Pit is a committed
# session of N runs: also no leaving until finished or the whole party is knocked out.
CAMP_HEAL_HOURS_MAX = 24
CAMP_AMBUSH_BASE = 0.10         # per hour of camping inside the Descent (scaled by floor, cut by intel)
CAMP_AMBUSH_DAMAGE = (0.10, 0.30)      # fraction of max HP, x(1 + 0.05 * floor)
SCOUT_MIN_HOURS, SCOUT_MAX_HOURS = 2, 24
SCOUT_RATE = 0.10               # knowledge: k' = 100 - (100 - k) * exp(-RATE * skill * hours)
SCOUT_AMBUSH_BASE = 0.12        # per hour in the segment, vs party strength, cut by what is already known
DELVE_PASSIVE_INTEL = 1.5       # % knowledge gained per hour spent inside the dungeon
INTEL_POWER_BONUS = 0.10        # fully scouted segment: +10% power and safer camps
INTEL_LEVELS = [20, 40, 60, 80, 100]
# Grinding-dungeon defeat: lose xp and morale, drop equipment (survivors may bring it back)
GRIND_DEATH_XP_LOSS = 0.4       # fraction of the xp needed for the next level
GRIND_DEATH_MORALE = -25
GEAR_RECOVERY_BASE = 0.5
GEAR_RECOVERY_SYNERGY_SLOPE = 5.0       # chance = 0.5 + 5 * (party synergy - 1) (+ friendship with the fallen)
GEAR_RECOVERY_MIN, GEAR_RECOVERY_MAX = 0.10, 0.95
PIT_LOST_RECOVER = 0.15         # a later Pit victory may find one item left behind earlier
GEAR_DROP_PIT, GEAR_DROP_MAIN = 0.15, 0.30

# ---- Per-slime dungeon progress, exits, scouting by floor ---------------------------------
# Every slime tracks the deepest floor it has CLEARED (`progress`). To enter floor f every member needs
# progress >= f - 1 (you cannot be carried past floors you have not walked). A delve may be left only at a
# checkpoint (just after a boss floor: 5, 10, 15 ...), so training and the academy happen between segments.
# Other parties can walk the same floors again at any time.
# Scouting is per floor range: the exploration party must reach 100% knowledge of every floor it targets
# before its supplies run out - otherwise the whole party is lost (a half-finished note survives).
SCOUT_HOURS_PER_FLOOR = 3.0     # nominal hours to fully scout floor 1 (grows with depth, shrinks with skill)
SCOUT_DEPTH_GROWTH = 0.12       # +12% hours per floor of depth
SCOUT_VARIANCE = (0.85, 1.20)   # hidden per-floor factor: the estimate is never exact
SCOUT_MAX_FLOORS = 10
SCOUT_FOOD_PER_HOUR = 1.0      # supplies are paid up front for the whole hour budget (unused food is not refunded)
SCOUT_NOTE_FRACTION = 0.5       # a lost party leaves half of what it had learned
SCOUT_HOUR_AMBUSH_DEPTH = 0.04  # ambush chance grows 4% (relative) per floor of depth
BOUNTY_BOSS_FLOORS_ONCE = True  # purple-gel boss bounty is paid once per boss floor, for the colony

# ---- Specialization (hybrid classes) and outlook ----------------------------------------------
SPEC_MIN_STYLE = 3             # style level in the second discipline
SPEC_MIN_LEVEL = 5
SPEC_COST = {"white_gel": 100, "essence": 25}
SPEC_STAT_RATIO = 0.5          # the new stat gets this share of the source stat
OUTLOOK_MIN = 5                # experiences before a slime develops an outlook
OUTLOOK_LEAD = 1.2             # the favourite activity must lead the runner-up by this factor
OUTLOOK_DUELIST_STYLE = 1.10   # style xp
OUTLOOK_GRINDER_XP = 0.10      # extra Pit xp share
OUTLOOK_GRINDER_LOSS = 0.7     # KO xp loss factor
OUTLOOK_GRINDER_MORALE = 0.6   # KO morale loss factor
OUTLOOK_DELVER_POWER = 0.05    # party power inside the Descent, scaled by the share of Delvers
OUTLOOK_PATHFINDER_SKILL = 0.1 # scouting skill per Pathfinder
OUTLOOK_FORAGER_LOOT = 1.10
OUTLOOK_SCHOLAR_STUDY = 1.10
OUTLOOK_SCHOLAR_RESEARCH = 0.05
OUTLOOK_ESTEEM = 3             # esteem gained doing your favourite thing

MIN_HUNT_HP = 0.3           # fraction of max HP needed to be sent on a hunt

# ---- Persistence ----------------------------------------------------------
SAVE_VERSION = 7
DEFAULT_SAVE = "savegame.json"
