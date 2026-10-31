"""Tunable constants. Change numbers here to rebalance without touching logic."""

# ---- Rarity & stars -----------------------------------------------------------
RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]            # ordered low -> high
RARITY_RATES = {"common": 90, "uncommon": 8, "rare": 1.9, "epic": 0.09, "legendary": 0.01}   # weights, normalised on roll
RARITY_STAT_MULT = {"common": 1.0, "uncommon": 1.12, "rare": 1.25, "epic": 1.6, "legendary": 2.2}
RARITY_LOOT_MULT = {"common": 1.0, "uncommon": 1.05, "rare": 1.1, "epic": 1.25, "legendary": 1.5}
RARITY_TAG = {"common": "C", "uncommon": "U", "rare": "R", "epic": "E", "legendary": "L"}
# Star rating 1..5. P(star = k) ~ exp(-lambda * (k-1)); lambda grows with rarity, so high stars are
# exponentially rarer and the drop-off is steeper at higher ranks.
MAX_STARS = 5
RARITY_ASCEND_LEVEL = 100        # a slime may rise in rarity only at this level and at MAX_STARS stars
STAR_DECAY = {"common": 0.7, "uncommon": 0.85, "rare": 1.0, "epic": 1.3, "legendary": 1.6}
STAR_STAT_MULT = [1.0, 1.1, 1.25, 1.45, 1.7]
PITY_EPIC = 0           # 0 = disabled (stated rates are honest). Set e.g. 10 / 50 to enable pity.
PITY_LEGENDARY = 0
VARIANCE = 0.10         # +/- per-slime stat roll

# ---- Economy --------------------------------------------------------------
# WHITE gel = common currency, PURPLE gel = rare currency (boosts rare pulls). Both buy pulls 1:1.
RESOURCES = ["white_gel", "purple_gel", "food", "essence", "herb_green", "herb_red", "herb_blue", "herb_yellow", "scrap", "alloy", "crystal", "stardust", "voidglass",
             "stone_common", "stone_uncommon", "stone_rare", "stone_epic", "stone_legendary"]       # add a name here to add a resource
STARTING_WALLET = {"white_gel": 100, "purple_gel": 10, "food": 15, "essence": 0}
MATERIAL_OF = {"common": "scrap", "uncommon": "alloy", "rare": "crystal", "epic": "stardust", "legendary": "voidglass"}   # crafting materials
PULL_BULK_N, PULL_BULK_DISCOUNT = 10, 0.10     # pulling 10 or more at once costs 10% less
GEL_MERGE = 100         # white gel that fuse into one purple gel
PULL_COST = 10          # of white OR purple gel per single pull
PURPLE_RARITY_BOOST = 5.0 # multiplies rare/epic/legendary weights when paying with purple gel
DAY_TICKS = 24          # one game day; one free pull per day
FOOD_NUTRITION = 50     # food need restored per Food item
MEDIATE_SNACK_COST = 2
# Vice Keeper: a trusted slime who stands in for the Keeper (everything except merging and destroying)
VICE_MIN_STARS = 3
VICE_MEDIATE_CHANCE = 0.3        # per hour, for each quarrel the vice keeper can reach
VICE_FEED_BELOW = 25             # feeds a reachable slime that is this hungry
NAME_MAX = 24
SCHOLAR_CLASSES = ("mage", "medic", "necromancer")   # the magic classes
SCHOLAR_MIN_STARS = 3            # a pulled mage, medic or necromancer is never below this (the Library needs 3 stars)
# Training facility: solo drills in the Sword Yard, Archery Range or Mage Sanctum raise class proficiency
DRILL_TICKS = 3
DRILL_COST = {"white_gel": 1}
# Higher-tier drills unlock with the Training Grounds level: (name, grounds level needed, hours, cost, proficiency x, style XP x)
DRILL_TIERS = [("Basic drill", 1, 3, {"white_gel": 1}, 1.0, 1.0),
               ("Advanced drill", 3, 4, {"white_gel": 3, "essence": 1}, 1.8, 2.0),
               ("Master drill", 5, 6, {"white_gel": 8, "essence": 3}, 3.0, 4.0)]
PROF_DRILL = 6.0                 # base proficiency gain per drill; shrinks as proficiency nears 100
DRILL_STYLE_XP = 4.0             # a little fighting-style XP too
# Floor threat smoothing (tools/playtest.py found a few floors with 2-4x the threat of their neighbours)
FLOOR_THREAT_TARGET = 6500.0      # (sum of enemy HP) x (sum of enemy damage) / growth(floor)^2, for a party of five
FLOOR_THREAT_BAND = (0.8, 1.25)   # ordinary floors keep their flavour inside this band around the target
BOSS_THREAT_BAND = (0.9, 1.3)
LEADER_POWER = 0.03              # party synergy bonus from a good leader (scaled by the leader's morale)
LEADER_MEDIATE_CHANCE = 0.15     # per hour, a party leader settles a quarrel inside the party while they are away
VICE_HUNT_MAX_PARTIES = 3
VICE_CHALLENGE_LEVEL_GAP = 3     # a slime must out-level the Vice Keeper by this much to challenge on its own
VICE_CHALLENGE_DAILY = 0.1       # daily chance that such a proud slime asks
# Commander's gifts (purple gel): the only way to reach a party that is inside the Descent, or in a skirmish
GIFT_MORALE_COST = 1
GIFT_MORALE_GAIN = 12
GIFT_PEACE_COST = 1
GIFT_POTION_PURPLE = [1, 2, 3, 5, 8]          # purple gel for a grade 1-5 potion, bought and drunk on the spot
POTION_SLOTS_BASE = 1                          # potion slots a slime can have active at once = this + stars (2 to 6)
GEAR_SCRAP_REFUND = 0.5                        # share of a gear's price returned when it is destroyed
GEAR_MERGE_COUNT = 3                           # identical gear that merge into one of the next tier
RELIC_MERGE_MOD_CHANCE = 0.35                  # chance a merged relic inherits one of the donor's mods it lacks

# ---- Needs (Maslow) -------------------------------------------------------
# Order matters: lowest tier first. Higher tiers are suppressed while a lower one is unmet.
NEED_ORDER = ["energy", "food", "safety", "belonging", "esteem"]
NEED_THRESHOLD = 40
# Per-tick decay when idle.
NEED_DECAY = {"energy": 2.5, "food": 2.0, "safety": 0.0, "belonging": 1.5, "esteem": 1.0}
HUNT_DECAY_MULT = {"energy": 2.5, "food": 1.8}   # hunting is tiring
SLEEP_ENERGY_GAIN = 22
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
# Feuds cool off the way people's do: after a brawl both keep apart for a while, a feud brawls at most CONFLICT_MAX_BRAWLS
# times and then turns into a cold war (no more fights, no friendship either), and quarrels may mend on their own.
CONFLICT_MAX_BRAWLS = 2           # brawls in one feud before it turns into a cold war
CONFLICT_BRAWL_COOL = 24          # hours both avoid each other after a brawl (no escalation meanwhile)
COLD_WAR_HOURS = 24 * 7           # a cold war: no new quarrels and no growing closer, then they are merely civil
CONFLICT_SELF_MEND = 0.03         # per hour together, a spat may be patched up without help (/ severity; x2 while keeping apart)
SELF_MEND_TRAIT = {"kind": 2.0, "chatty": 1.3, "grumpy": 0.5, "proud": 0.6}
MEDIATE_RETRY_HOURS = 6           # after a failed talk they are "not ready yet": a talk can be tried again after this (a snack works any time)
MADE_UP_CALM_HOURS = 24           # after making up, neither starts a new quarrel for this long
APOLOGY_GUILT = 25                # guilt at which a slime may apologise (once a day, APOLOGY_CHANCE)
APOLOGY_CHANCE = 0.35
PEACEMAKER_CHANCE = 0.5           # once a day, a friend of both at home tries to make peace (succeeds like a Keeper's talk)

# ---- Growth ---------------------------------------------------------------
LEVEL_CAPS = [10, 30, 100]          # per evolution stage
STAGE_STAT_MULT = [1.0, 1.5, 2.1]
EVOLVE_ESSENCE_BASE = 50            # * (stage + 1)
MERGE_XP_RATIO = 1.0              # a merge hands over the XP the donor collected (no more, no less)
MERGE_SAME_CLASS_BONUS = 1.25
MERGE_RARITY_XP = {"common": 10, "uncommon": 20, "rare": 30, "epic": 80, "legendary": 200}   # (unused: a merge gives only the XP earned)

SOFT_LEVEL = 50                     # above this level each level adds only SOFT_LEVEL_RATE of the usual stat growth
SOFT_LEVEL_RATE = 0.6

def stat_level(level: float) -> float:
    """The level stats are computed from: linear to 50, then diminishing (level 100 counts as 80)."""
    return level if level <= SOFT_LEVEL else SOFT_LEVEL + (level - SOFT_LEVEL) * SOFT_LEVEL_RATE

PIT_RUNS_PER_LEVEL = 3.5          # Pit runs a COMMON party needs per level (rarer slimes need more, see pit_xp_per_run)
PIT_RARITY_RUNS = 0.5            # each rarity step adds this share of PIT_RUNS_PER_LEVEL (legendary: x3)


def rarity_xp_factor(rarity: str) -> float:
    """Multiplier on a fixed XP reward for a slime of this rarity: its level costs XP_RARITY_MULT times as much, and it is allowed
    (1 + PIT_RARITY_RUNS per step) times as many fights per level, exactly like the Gloop Pit. common 1, uncommon 1.33, rare 2,
    epic 3.2, legendary 5.33."""
    idx = RARITIES.index(rarity) if rarity in RARITIES else 0
    return XP_RARITY_MULT.get(rarity, 1) / (1 + PIT_RARITY_RUNS * idx)
PIT_DEPTH_XP = {1: 0.6, 2: 0.8, 3: 1.0, 4: 1.3, 5: 1.7}   # deeper Pit depths pay more

def pit_xp_per_run(mean_need: float, mean_rarity_index: float, depth: int) -> float:
    """XP each survivor earns from a won Pit run: the XP a level costs spread over the runs it should take. Tying the reward
    to the XP *need* (not the level) keeps the climb the same length for every rarity: a rarer slime needs fewer levels
    for the same floor but each costs more, and the Pit pays accordingly."""
    runs = PIT_RUNS_PER_LEVEL * (1 + PIT_RARITY_RUNS * mean_rarity_index)
    return mean_need / runs * PIT_DEPTH_XP.get(depth, 1.0)

XP_RARITY_MULT = {"common": 1, "uncommon": 2, "rare": 4, "epic": 8, "legendary": 16}   # doubles with every rarity
# Class proficiency: how sharp a slime is at its original discipline (see attributes.capstones)
PROF_START, PROF_FLOOR = 50.0, 20.0
PROF_IDLE_DAYS = 3             # days without practice before proficiency starts to fade
PROF_DECAY = 1.0               # lost per further idle day (never below PROF_FLOOR)
PROF_BATTLE_GAIN, PROF_BATTLE_CAP = 0.3, 4.0     # per action taken in a fight, at most per fight
PROF_SPAR_OWN, PROF_SPAR_OTHER, PROF_STUDY = 3.0, 1.0, 3.0
PROF_BOTH_CAPSTONES, PROF_ONE_CAPSTONE = 70.0, 30.0   # proficiency needed for both / for the first pure capstone
# Hybrid (specialized) classes: a second proficiency in the secondary discipline scales the hybrid capstone
PROF_SPEC_START = 30.0
PROF_SPEC_BATTLE_GAIN = 0.5    # per hybrid skill used in a fight (capped by PROF_BATTLE_CAP)
HYBRID_CAPSTONE_MAX = 0.6      # hybrid capstones reach at most this share of a pure capstone's strength
_STAR_LEVELS = [10, 25, 50, 80]
STAR_LEVELS = {r: list(_STAR_LEVELS) for r in ("common", "uncommon", "rare", "epic", "legendary")}   # level needed to ascend to 2 / 3 / 4 / 5 stars: the same for every rarity
STAR_STONE_MULT = {"common": 1, "uncommon": 1.5, "rare": 2, "epic": 3, "legendary": 4}   # stones for a star scale with rarity
STAR_ATTR_RARITY_BOOST = {"common": 1.0, "uncommon": 1.3, "rare": 1.7, "epic": 2.2, "legendary": 3.0}   # star attributes hit harder

def xp_to_next(level: int, rarity: str = "common", stars: int = 1) -> int:
    """XP needed to go from `level` to `level + 1`: doubles with each rarity (common 1x ... legendary 16x). Stars do not change it."""
    return int(20 * level ** 1.5 * XP_RARITY_MULT.get(rarity, 1))

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
GRIND_LOOT_MULT = 0.5           # little loot, no purple gel
GRIND_TICKS = 2
GRIND_MIN_HP = 0.4              # auto-grind stops when anyone drops below this HP fraction

# ---- Sparring (fighting styles), rest area, morale, bonds, buildings --------------------
# Training is NOT for XP: slimes spar against each other to develop a fighting STYLE. Spars are non-lethal
# (loser is left at 1 HP) and cost no XP; the Rest Area heals everybody back to full.
SPAR_COST = {"white_gel": 2}          # one duel
SPAR_PARTY_COST = {"white_gel": 3}    # a whole party session, flat (not per pair)
SPAR_TICKS = 3
SPAR_STYLE_XP = 15              # style xp per spar (winner x1.3, own-discipline x1.5, grounds level bonus)
SPAR_WINNER_MULT = 1.3
SPAR_DUMMY_MULT = 0.5           # odd slime out trains on a dummy at half rate (no HP loss)
SPAR_MIN_HP = 0.4
SPAR_BOND = 3
WAVE_PROF, WAVE_BOND, WAVE_TICKS = 2.0, 1.0, 2
WAVE_MAX_LEVEL, WAVE_MAX_WAVES, WAVE_XP_MULT = 50, 5, 1.0   # wave simulation: top monster level, most waves, XP vs the monsters' worth   # wave simulation: class proficiency per member (x(1+0.5 per tier above 1)), bond per pair, hours
# A TROUBLEMAKER (merging or destroying it costs no morale and no sacrifice stress): a slime that came to blows with more
# different slimes in the last NUISANCE_DAYS days than NUISANCE_SHARE of the colony (rounded down, never under NUISANCE_MIN),
# or one most of the colony dislikes. A slime that was only snapped at does not count the fight against it.
NUISANCE_SHARE = 0.05
NUISANCE_MIN = 1                   # 5% of a small colony rounds down to 0: a single fight should not make a troublemaker
NUISANCE_DAYS = 30                 # older fights are forgiven
NUISANCE_GRIEF = 0.5               # a troublemaker's partner and best friend still grieve it, at this strength; nobody else does
RELIEF_ANGER, RELIEF_CALM, RELIEF_CONTENT = 30, 15, 5   # those it fought with when it goes: anger eased, calm, contentment
RELIEF_GRUDGE_FADE = 0.5           # ... and their grudges against it weigh this much
# THE KEEPER'S SHADOW: after a troublemaker is removed the colony quarrels less for SHADOW_HOURS, fading back to normal.
SHADOW_HOURS = 24 * 7
SHADOW_FACTOR = 0.5                # quarrel chance for everyone right after a removal
SHADOW_FEAR_FACTOR = 0.3           # ... for a slime with fights of its own on record ("I could be next")
SHADOW_FEAR_TRAIT = {"timid": 1.5, "grumpy": 0.5, "proud": 0.5, "brave": 0.1}   # how much that fear holds it back
SHADOW_FEAR = 15                   # fear felt by those with fights on record
SHADOW_ANXIETY = 15                # a second removal within SHADOW_HOURS: they grow anxious too
SHADOW_FLOOR = 0.3                 # the shadow never cuts the quarrel chance below this
RESPECT_DAYS = 3                   # a slime the Keeper talked with, or made peace for, in the last few days ...
RESPECT_FACTOR = 0.8               # ... starts quarrels this much as often
ROW_BACK_MELEE = 0.75          # a melee fighter standing in the back row hits for this much
ROW_BACK_GUARD = 0.80          # a unit in the back row takes this much of any damage that reaches it
PARTY_TRAIN_BOND = 3.0         # every pair inside a party that trains together in the Party Arena grows this much closer
SPAR_PARTY_BOND = 4             # every pair inside a party that spars as a team grows this much closer
STYLE_AFFINITY_MULT = 1.5       # practising the discipline that matches your class
STYLE_XP = [30, 80, 150, 250, 400, 600, 850, 1150, 1500, 2000]   # cumulative xp for style level 1..10
STYLE_SWORD_DAMAGE = 0.03       # per level: +3% attack-stat damage ...
STYLE_SWORD_GUARD = 0.02        # ... and -2% damage taken (max -40%)
STYLE_ARCHERY_CRIT = 0.02       # per level: +2% crit chance ...
STYLE_ARCHERY_SPEED = 0.03      # ... and +3% speed
STYLE_MAGIC_POWER = 0.03        # per level: +3% magic damage/healing
STUDY_DECAY_MULT = {"energy": 1.6, "food": 1.3}
WORK_DECAY_MULT = {"belonging": 0.5}   # a slime at a post has colleagues: belonging fades half as fast
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
POWER_DISPLAY_MAX = 20000       # total power that shows as 999 on the roster (a square-root scale: weak slimes still read 001-050)
REST_ENERGY = [26, 34, 42, 52, 64]      # energy per hour in the Rest Area by level (HP heals at the base sleeping rate)
AUTO_REST_BELOW = 0.5           # auto-care sends slimes under 50% HP to the Rest Area if there is room
# Library / mastery
TASK_MIN_ENERGY = 25
PULLBACK_MORALE, PULLBACK_ANGER = 6, 12   # calling a slime back from a post, foraging, a hunt, a drill or the Rest Area for a trip: nobody likes it
WAKE_MORALE, WAKE_ANGER = 6, 10       # waking a sleeping slime (to train, hunt, or on request) costs mood ...
REFUSE_ENERGY = 10                  # a slime below this energy refuses any post or expedition (and is skipped by 'wake everyone')
REFUSE_HP = {"job": 0.25, "dungeon": 0.40}   # ... one hurt below this share of its HP refuses (a post / an expedition)
REFUSE_MOOD = 0.20                  # ... one in a bleak mood (miserable) refuses
REFUSE_ANGER = 80                   # ... and one in a rage
WAKE_FREE_ABOVE = 50                  # ... unless it is already rested: energy above this share wakes for free
BRAWL_MORALE, BRAWL_ANGER = 15, 20    # a brawl leaves both fighters sour
WOUNDED_BELOW, WOUNDED_DRILL = 0.5, 0.6   # a drill started below this share of max HP is worth this much

# ---- Occupations (jobs.py) ------------------------------------------------------------------
JOB_XP_STEP = 5                # rounds of work for level 2; level n needs JOB_XP_STEP * (n-1)^2
JOB_MAX_LEVEL = 10
JOB_ENERGY_PER_HOUR = 0.5      # a working slime tires slowly (on top of normal decay)
CHEF_GUESTS, CHEF_MEAL_SHARE = 2, 0.6      # hungry slimes fed per round (+1 per 3 levels); share of a Food item each gets
SMITH_ITEMS, SMITH_MEND_SHARE = 3, 0.15    # items mended per round (+1 per 2 levels); share of max durability restored
FORAGE_MIN_HP, FORAGE_MIN_ENERGY, FORAGE_MIN_FOOD = 0.7, 50, 35   # an idle slime sets out only when this rested and fed
FORAGE_SAFETY = 1.5            # ... and only in a zone whose danger is at most power / this
TRAINER_BONUS, TRAINER_BONUS_PER_LEVEL = 0.15, 0.03   # a trainer's proficiency / style gain bonus (+ per level above 1)
TRAINER_LESSON_GAIN, TRAINER_LESSON_OTHER = 0.15, 0.05  # a trainer's own proficiency gain per lesson given (teaching sharpens the teacher a little)
CRAFT_SHIFTS, CRAFT_COST_SHARE = 4, 0.6       # a blacksmith forges every 4 shifts, at this share of the shop price
CRAFT_RELIC_COST = {"scrap": 6, "white_gel": 15}
PANTRY_PER_LEVEL, HUNGRY_BELOW = 12, 50       # servings the pantry holds per Kitchen level; food need below which a slime counts as hungry
HOSPITAL_BEDS = [2, 4, 6, 8, 10]                 # slimes the Hospital ward holds, by level
WARD_DOCTOR_BONUS, WARD_NO_DOCTOR_BONUS = 0.30, 0.05   # patients in the ward heal this much faster than in the Rest Area (with / without a doctor on duty)
HOSPITAL_HEAL = [0.04, 0.06, 0.08, 0.10, 0.12]    # share of max HP a doctor heals every injured slime each hour, by Hospital level
LIBRARIAN_LORE_XP = 6.0         # mastery XP a round of cataloguing gives one attuned slime (x power)
TRAINER_PUPILS, TRAINER_GAIN = 1, 3.0      # pupils per round (+1 per 4 levels); base class-proficiency gain
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
CAMP_HEAL_PER_HOUR = 0.08       # share of max HP a sleeping party recovers per hour of camp
CAMP_AMBUSH_BASE = 0.10         # per hour of camping inside the Descent (scaled by floor, cut by intel)
CAMP_RELIEF_MAX = 0.5          # ambush chance falls by up to this share while another party closes in from below
CAMP_RELIEF_REACH = 3          # ... starting this many floors below
STOP_REST_HEAL, STOP_REST_HOURS = 0.5, 3   # a wayside stop's safe rest: share of max HP healed, hours taken
RETREAT_PURPLE_BASE, RETREAT_AMBUSH, RETREAT_MORALE = 2, 0.35, 12   # emergency retreat: purple gel base fee (+1 per 5 floors), ambush chance, morale lost
CAMP_AMBUSH_DAMAGE = (0.10, 0.30)      # fraction of max HP, x(1 + 0.05 * floor)
RESCUE_DEADLINE_HOURS, RESCUE_BASE_HOURS, RESCUE_BASE_CHANCE = 24, 4, 0.35   # the deadline is in LOBBY hours, the trip in dungeon hours
# ---- passive skills (passives.py) -------------------------------------------------------------------------------------------------
HEARTH_HEAL = 0.25               # Hearth (fire mastered): the party mends this much more at each camp hour
WELLSPRING_CUT = 0.20            # Wellspring (water mastered): the party burns this much less food and energy inside dungeons
BEDROCK_CUT = 0.30               # Bedrock (earth mastered): ambushes hurt the party this much less
TRADE_PASSIVE_BOOST = 0.25       # a trade passive (trade level 10): that post's output is this much bigger
DISTILLER_CHANCE = 0.25          # Distiller: chance a brew makes one more potion
MASTER_TRAINER_BOOST = 0.5       # Master Trainer: the trainer's bonus is this much bigger
SYNERGY_SOULBOUND = 0.03         # Soulbound: party synergy while its partner is in the party
SYNERGY_HEART = 0.02             # Heart of the Party: party synergy for a slime with HEART_TIES or more ties
HEART_TIES = 4
SYNERGY_PASSIVE_MAX = 0.08       # all synergy passives of a party together
PROFICIENCY_FULL = 100.0         # class (or second) proficiency that earns a mastery passive: the gold (or teal) star on the avatar
STYLE_FULL = 10                  # fighting-style level that earns a style passive

RESCUE_TAILWIND_SPEED, RESCUE_TAILWIND_MAX = 0.25, 0.50   # each slime with the Tailwind passive (passives.py: wind mastered) shortens a rescue trip by 25%, at most 50% together
RESCUE_KNOWN_FLOOR_HOURS = 0.25     # a floor that is already scouted costs rescuers only this many hours to cross   # overdue scouts wait this long; trip = base + floor hours; base success chance
SCOUT_MIN_HOURS, SCOUT_MAX_HOURS = 2, 240
SCOUT_RATE = 0.10               # knowledge: k' = 100 - (100 - k) * exp(-RATE * skill * hours)
SCOUT_AMBUSH_BASE = 0.12        # per hour in the segment, vs party strength, cut by what is already known
DELVE_PASSIVE_INTEL = 1.5       # % knowledge gained per hour spent inside the dungeon
INTEL_POWER_BONUS = 0.10        # fully scouted segment: +10% power and safer camps
INTEL_LEVELS = [20, 40, 60, 80, 100]
# Grinding-dungeon defeat: lose morale (never XP - it is an XP farm) and drop equipment (survivors may bring it back)
GRIND_DEATH_XP_LOSS = 0.4       # (unused by the Pit now; kept for the lose_xp helper's tests)
GRIND_DEATH_MORALE = -25
GEAR_RECOVERY_BASE = 0.5
GEAR_RECOVERY_SYNERGY_SLOPE = 5.0       # chance = 0.5 + 5 * (party synergy - 1) (+ friendship with the fallen)
GEAR_RECOVERY_MIN, GEAR_RECOVERY_MAX = 0.10, 0.95
PIT_LOST_RECOVER = 0.15         # a later Pit victory may find one item left behind earlier
GEAR_DROP_PIT, GEAR_DROP_MAIN = 0.15, 0.30
FARM_LOOT_CHANCE = 0.05          # per defeated foe in a farming dungeon (Pit, Rift, Quarry): a little of another resource
FARM_LOOT = {"white_gel": (1, 3), "food": (1, 3), "essence": (1, 1), "scrap": (1, 2)}
PIT_LURE_COST = 1               # purple gel per Pit run for a lure ...
PIT_LURE_XP, PIT_LURE_GEAR = 1.5, 3.0    # ... which brings out richer prey: x XP and x gear-drop chance

# ---- Per-slime dungeon progress, exits, scouting by floor ---------------------------------
# Every slime tracks the deepest floor it has CLEARED (`progress`). To enter floor f every member needs
# progress >= f - 1 (you cannot be carried past floors you have not walked). A delve may be left only at a
# checkpoint (just after a boss floor: 5, 10, 15 ...), so training and the academy happen between segments.
# Other parties can walk the same floors again at any time.
# Scouting is per floor range: the exploration party must reach 100% knowledge of every floor it targets
# before its supplies run out - otherwise the whole party is lost (a half-finished note survives).
SCOUT_HOURS_PER_FLOOR = 3.0     # nominal hours to fully scout floor 1 (grows with depth, shrinks with skill)
SCOUT_DEPTH_GROWTH = 0.05       # +5% hours per floor of depth (floor 50: ~10h per floor)
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

HUNT_PROF_OWN, HUNT_BOND = 1.5, 1.5          # a hunt sharpens class proficiency (x0.4 if it went badly); hunters in one group grow this much closer per pair
HUNT_RUNS_PER_LEVEL = 20.0     # three-hour hunts a COMMON slime needs per level (mild); rarer slimes need more, as in the Pit
HUNT_SIDE_CHANCE = 0.18        # chance a successful hunt also brings a little of another material (herbs, scrap, a common stone)
MIN_HUNT_HP = 0.3           # fraction of max HP needed to be sent on a hunt

# ---- Persistence ----------------------------------------------------------
VERSION = "1.001"               # the game's version, shown on the About page
SAVE_VERSION = 16
DEFAULT_SAVE = "savegame.json"


# ---- adventure dungeon & relics (items.py) ---------------------------------------------------------------------
ADV_MAX_PARTY = 5
ADV_XP_MULT = 0.25               # the Rift is for loot, not xp
ADV_MONSTER_LEVEL = 1            # monsters are this many levels above the party average
ADV_FOE_RATIO = 0.75             # foes per slime (a small party meets proportionally fewer)
ADV_TICKS = 2
SESSION_MAX_HOURS = 24            # no farming session (Pit, Rift, Quarry) lasts longer than one game day, camping included
FIELD_REST_ENERGY = 80            # a session party that has to sleep (anyone under AUTO_SLEEP_BELOW energy) rests until everyone has this much
ADV_MAX_RUNS = SESSION_MAX_HOURS // ADV_TICKS     # = 12 runs of 2 hours
GRIND_MAX_RUNS = SESSION_MAX_HOURS // GRIND_TICKS
ADV_DROP_PER_FOE = 0.45          # chance per defeated foe to drop a relic
ADV_LURE_COST = 1                # purple gel per run for a lure ...
ADV_LURE_BOOST = 4.0             # ... which multiplies the non-common relic weights
ADV_KO_WEAR = 8                  # extra durability lost by a relic whose wearer was knocked out
ITEM_RARITY_RATES = {"common": 97, "uncommon": 2.5, "rare": 0.45, "epic": 0.045, "legendary": 0.005}   # slime odds, made drastic
ITEM_STAR_DECAY = {"common": 1.0, "uncommon": 1.2, "rare": 1.4, "epic": 1.9, "legendary": 2.4}      # steeper than slimes
ITEM_RARITY_MULT = {"common": 1.0, "uncommon": 1.25, "rare": 1.6, "epic": 2.3, "legendary": 3.2}
ITEM_STAR_MULT = [1.0, 1.25, 1.55, 1.9, 2.3]
ITEM_LEVEL_STEP = 0.03           # +3% per level (level 1..10 inside a star)
ITEM_MAX_LEVEL = 10
ITEM_DURABILITY = 30             # + 10 per star + 10 per rarity step
ITEM_SALVAGE_BASE = 2
ITEM_ASCEND_STAR = 15            # materials of the item's own tier = this x current star ...
ITEM_ASCEND_RARITY = 150         # ... and for a rarity step
ITEM_MOD_RANGE = {"crit_rate": (0.03, 0.06), "crit_dmg": (0.10, 0.25), "elem_dmg": (0.08, 0.18),
                  "lifesteal": (0.03, 0.08)}
ITEM_COMPAT_MIN, ITEM_COMPAT_MAX = 0.85, 1.15    # stat multiplier from slime <-> item compatibility
EGO_BASE_MULT = 1.5              # an ego relic is a 5-star legendary fused with a 5-star legendary slime
EGO_LEVEL_MULT = 0.02            # + 2% per level of the sacrificed slime
EGO_MORALE_STRESS = 2.0


# ---- slime ascension, stones, merging, destruction (ascension.py) ---------------------------------------------------
RARITY_ASCEND_GEL = {"uncommon": 10, "rare": 100, "epic": 1000, "legendary": 10000}   # white gel to REACH that rarity
STAR_ASCEND_STONES = {2: 10, 3: 100, 4: 1000, 5: 10000}      # common-stone equivalents to REACH that star count
STONE_MERGE = 100                                            # 100 stones of a rarity make 1 of the next
STONE_RATES = {"common": 97.0, "uncommon": 2.6, "rare": 0.4, "epic": 0.01}   # Starfall Quarry drop odds
STONE_COMMON_QTY = (1, 4)
QUARRY_DROP_PER_FOE = 0.6
QUARRY_XP_MULT = 0.15
STONE_SIDE_DROP = {"grind": 0.03, "adventure": 0.05}          # per foe, common stones only (other dungeons)
MERGE_STAT_SHARE = 0.20          # the target gains this share of the donor's stats ...
MERGE_SHARE_SLOPE = 0.20         # ... falling by 0.2 per 1.0 (100%) of merge growth already in that attribute ...
MERGE_SHARE_FLOOR = 0.01         # ... down to this flat share
CHAMBER_GEL_BASE = 5             # destruction chamber: gel = base x 10^rarity x star factor x chamber factor
CHAMBER_STONE_BASE = 5           # stone equivalents = (base + 50% of stones invested in its stars) x (1 + rarity step)
CHAMBER_STRESS = 1.0


# ---- stamina, potions, weapons (attributes.py, potions.py, items.py) -----------------------------------------------------
STAMINA_COSTS = {"attack": 8, "power": 8, "guard": 4, "heal": 8, "summon": 12}   # cost = attack + power x ability power
STAMINA_ROUND_REGEN = 1.5        # breath caught per round, per 100 max stamina x 4 (see attributes.regen_per_round)
STAMINA_HOUR_REGEN = 0.10        # fraction of max stamina per hour awake ...
STAMINA_SLEEP_MULT = 2.5         # ... faster asleep / in the Rest Area
STAMINA_WINDED_MULT = 0.6        # damage and healing of an exhausted slime
STAMINA_CAMP_AT = 0.35           # a Pit / Rift / Quarry party camps when anyone is below this
HERB_DROP = {"grind": 0.35, "adventure": 0.10, "quarry": 0.10}   # per foe, 1-3 herbs
POTION_BONUS = [0.10, 0.15, 0.20, 0.30, 0.40]                    # grade 1..5
POTION_HERBS = [3, 8, 20, 50, 120]
POTION_GEL = [5, 20, 80, 320, 1280]
POTION_ESSENCE = [0, 0, 5, 15, 40]
POTION_HOURS_BASE, POTION_HOURS_GRADE = 12, 4                    # lasts 12 + 4 x grade hours
BREW_HOURS_PER_GRADE = 2
BREW_BASE_CHANCE = 0.75
BREW_CRIT = 0.10                 # chance the brew comes out one grade better
WEAPON_MEMORY = 3                # weapon families a slime keeps in mind
PROFICIENCY_PER_LEVEL = 10       # uses per proficiency level (max 10)
PROFICIENCY_BONUS = 0.03         # weapon stats +3% per proficiency level
FAVOURITE_COMPAT = 12            # compatibility bonus for a slime's favourite weapon family
BOND_MORALE_AT = 20              # a weapon bonded this far lifts its wielder's morale after each fight
SLIME_REPAIR_HOURS = 1

# ---- coloured herbs & slime autonomy ---------------------------------------------------------------------------------------
HERBS = ("green", "red", "blue", "yellow")      # health, strength, armor, stamina
TERRAIN_HERB = {"valley": "green", "plains": "green", "swamp": "green", "volcano": "red", "barrens": "red",
                "ruins": "red", "islands": "blue", "tundra": "blue", "caverns": "blue", "dunes": "yellow",
                "canyon": "yellow", "cliffs": "yellow"}
HERB_LOCAL_SHARE = 0.7           # share of herbs that match the terrain's colour (the rest is random)
POTION_COMBO_SHARE = 0.6         # a two-herb potion needs this share of the herbs of each colour
AUTONOMY_SHARE = 0.66            # slimes may use up to this share of a stock by themselves (the rest is yours)
AUTONOMY_STAMINA_BELOW = 0.35    # a tired slime drinks a stamina potion by itself
AUTONOMY_HP_BELOW = 0.5
AUTONOMY_REPAIR_BELOW = 0.35     # a slime mends its own gear when durability is below this share
AUTONOMY_MAX_BUFFS = 2           # potions a slime drinks by itself before a trip

# ---- emotions & awakening, wider autonomy (emotions.py, awakening.py) ------------------------------------------------------
AWARENESS_PER_HOUR = 0.25        # a 5-star legendary: stage 1 at ~4 days, 2 at ~10, 3 at ~17
THOUGHT_CHANCE = 0.04            # per hour, once aware
# How an awakened legendary takes it comes from its life over the last LIFE_DAYS days (awakening.py)
LIFE_DAYS = 14                   # days of record kept
LIFE_HARD_DAYS = 7               # hardship counts over the last week only
LIFE_REVIEW_DAYS = 3             # the outcome is reviewed this often, so a changed life changes it
LIFE_HURT_SCALE = 0.25           # a day that costs this share of the sanity reserve is a day of full hardship
KEEPER_CARE_SHARE = 0.7          # the Keeper's care can make up at most 70% of connection and purpose
DESPAIR_HARDSHIP = 0.45          # recent hardship at or above this -> despair
DESPAIR_CONNECTION = 0.3         # connection (with care counted) below this -> despair
COG_PURPOSE = 0.35               # purpose (with care counted) below this -> a cog
PEACE_AT, PEACE_OWN = 0.6, 0.5   # peace needs both at PEACE_AT, and one of its own (not the Keeper's) at PEACE_OWN
COG_POST_DAYS = 5                # days at the same post and nothing else before purpose halves
COG_FEELING_CAP = 30             # a cog's joy, pride and wonder never rise above this
COG_MOOD_CAP = 0.6
COG_CHANGE_DAYS = 7              # a cog asks for a change after this many days
DESPAIR_DREAD, DESPAIR_DREAD_MAX = 15, 35   # the dread undercurrent, deepening 2 a day
DESPAIR_NEGLECT_DAY = 5          # from this day of despair it leaves its food half the time
DESPAIR_BREAKDOWN_DAY = 10       # ... from this day it eats only from the Keeper's hand, refuses work, may break down
DESPAIR_MOOD_CAP = (0.5, 0.4, 0.3)          # mood cap by despair stage (withdrawal, self-neglect, breakdowns)
BREAKDOWN_CHANCE = 0.3           # per day in the breakdown stage
BREAKDOWN_SANITY = 4
LEAVE_DESPAIR_DAYS = 12          # a slime this long in despair asks to leave the colony (the Keeper decides)
LEAVE_COG_DAYS = 21              # ... or this long a cog
LEAVE_SANITY_DAYS = 7            # any slime: this many days 'breaking' (sanity under 20%) with little trust asks to leave
LEAVE_TRUST = 30
LEAVE_ASK_AGAIN_DAYS = 3        # after being turned down it waits this long before asking again
DEPART_SADNESS = 20            # friends of a slime that leaves feel this (less than a death)
# Grief (grief.py): depth by tie (partner 90, best friend 70, mentor 50, friend 45), fading over one to three weeks
GRIEF_ACQUAINTANCE, GRIEF_BOND = 25, 20     # someone it merely got on with (bond 20+) is mourned a little
GRIEF_FADE = 4                   # grief lost per day ...
GRIEF_COMFORT = 3                # ... plus this with a friend at home to sit with it
GRIEF_TALK = 2                   # ... plus this on a day the Keeper talked with it
GRIEF_SADNESS, GRIEF_LONELY = 0.5, 0.15     # grief holds the sadness / loneliness baseline at this share of its depth
GRIEF_WAVE = 0.4                 # each weekly anniversary stirs sadness by this share of the depth
GRIEF_PLACE = 0.3                # ... and so does being back in the dungeon where it happened (once a day)
GRIEF_DEPART_SCALE = 0.5        # a slime that leaves is missed at half the depth of a death
GRIEF_LINES = 3                  # journal lines about grief per day
GRIEF_GATHER_DAYS = 7            # a gathering at the Memorial Pond can be held within this many days of a death
GRIEF_GATHER, GRIEF_GATHER_SANITY, GRIEF_GATHER_BOND = 15, 4, 3
# Coping and comfort (coping.py)
COPE_AT = 50                     # a bad feeling this strong makes a slime at home act on it (once a day)
COPE_EASE = 20                   # how much a healthy way of coping eases it (styles differ: 0.6x to 1.5x)
COPE_DWELL = 4                   # dwelling on it makes it this much worse
VENT_QUARREL = 0.3               # chance that snapping at someone starts a quarrel
COMFORT_AT = 45                  # a friend at home notices sadness, fear, anxiety or loneliness this strong
COMFORT_EASE, COMFORT_SANITY = 18, 2
CONTAGION = {"fear": 3, "joy": 2}            # per hour, to party-mates away together, from a member at CONTAGION_AT or more
CONTAGION_AT = 60
COPE_LINES_PER_HOUR, COPE_LINES_PER_DAY = 2, 8   # journal lines about coping and comfort
# A day at home (routine.py)
MEAL_HOURS = (8, 13, 19)         # breakfast, lunch, dinner: slimes at home getting hungry eat together
MEAL_BELOW = 60                  # food need under which a slime joins a meal
TABLE_SIZE = 6                   # slimes per table (each pair at a table grows a little closer)
MEAL_BOND = 0.5
HOBBY_HOUR = 20                  # every free slime at home spends the evening on its hobby
HOBBY_JOY, HOBBY_BOND = 4, 1.0
HOBBY_MIN_ENERGY = 40           # below this a slime is too worn out for its hobby
EVENING_LINE_PARTS = 4           # hobby groups named in the evening journal line
# Relationships with texture (relationships.py, memory.py, game._peacemaking)
BOND_FADE, BOND_FADE_FROM = 0.3, 5.0   # a bond of 5+ fades this much on a day the two did not share (apart, or not both home)
JEALOUS_GAP, JEALOUS_CHANCE = 10, 0.15 # a partner much closer to someone else (by this much) may stir jealousy (per day)
GRUDGE_APOLOGY_MIN = 3.0         # a grudge this heavy may earn an apology from a kind or guilty slime (APOLOGY_CHANCE a day)
FORGIVE_FADE = 0.92              # a kind slime's grudges fade this much more each day
# Rituals (rituals.py)
HATCH_EVERY = 30                 # a hatch day (and a couple's anniversary) every this many days
HATCH_JOY, HATCH_TRUST = 15, 3   # when the Keeper remembers it
FEAST_JOY, FEAST_BOND = 12, 1.0  # the feast after a boss falls
MEANING_DAYS = 7                 # days of record every other slime keeps (meaning.py)
BURNOUT_DAYS = 5                 # flat days (purpose low, not lonely) before a slime burns out
BURNOUT_PURPOSE = 0.35           # purpose (with care counted) below this is a flat day
BURNOUT_FEELING_CAP = 40         # a burned-out slime's joy and pride stay at or below this
BURNOUT_MOOD_CAP = 0.7
PRAISE_ESTEEM, PRAISE_PRIDE = 12, 12
PRAISE_PURPOSE = 0.15           # being noticed adds this to the day's purpose (besides counting as an achievement)   # the Keeper's praise (the first of the day; each more counts half)
SAID_KEEP = 30                   # lines a slime remembers having said (for not repeating itself)
VOICE_MEMORY_MIN = 2.0           # a memory this strong may come up in conversation
LINE_REPEAT_DAYS = 7             # a slime never says the same thought twice within a week
AUTONOMY_BREW_HOUR = 6           # slimes may brew by themselves once a day at this hour
AUTONOMY_BREW_STOCK = 2          # ... when they hold fewer than this many of a class-suited potion
EMOTION_BATTLE_NOTE = 40         # intensity at which a feeling is mentioned in the battle log

# ---- relationships & budding (relationships.py) -----------------------------------------------------------------------------
FRIEND_BOND, BEST_FRIEND_BOND, COUPLE_BOND = 25, 45, 40
COUPLE_CHANCE = 0.20             # per day for a suitable pair
MENTOR_CHANCE = 0.30
MENTOR_XP = 0.10                 # a mentee fighting beside its mentor earns this much extra XP
RELATIONS_HOUR = 12              # relationships are reviewed once a day at this hour
BUD_COST = {"food": 20, "essence": 10, "white_gel": 50}
BUD_COOLDOWN_DAYS = 10
BUD_MIN_DAYS = 3                 # a couple must be together this long
BUD_TOP_PARENT = 0.35            # chance the child takes the better parent's rarity (else the lower)
BUD_BLESSING = 0.03              # chance of one rarity above both parents

# ---- the Keeper (keeper.py) ---------------------------------------------------------------------------------------------------
KEEPER_MAX_LEVEL = 30
KEEPER_XP = {"pull": 2, "care": 1, "win": 3, "boss": 12, "mediate": 4, "brew": 3, "forge": 2, "ascend": 6,
             "relation": 5, "bud": 25, "floor": 4, "scout": 10, "merge": 2, "quarry": 2}
KEEPER_DAILY_CAP = {"care": 10, "win": 45, "pull": 12, "forge": 10}

# ---- time: turn-based or LIVE (wall-clock) with dilation (game.py: sync) ------------------------------------------------------------
CLEAR_BASE_HOURS = 1.5           # game hours to clear floor 0 ...
CLEAR_HOURS_PER_FLOOR = 0.08     # ... plus this per floor (floor 50: ~5.5h before level and knowledge)
CLEAR_KNOWLEDGE_CUT = 0.40       # a fully scouted floor is cleared 40% faster
LIVE_LOBBY_RATE = 1.0            # game hours per REAL hour at home (study, hunts ... take wall-clock time)
# Time inside a dungeon runs faster than the lobby's: each Place (places.py) carries its own `dilation` (dungeon hours that pass per
# lobby hour). An activity measured in dungeon hours costs ceil(hours / dilation) lobby hours (at least 1); the party inside burns food,
# energy and stamina and grows closer at the dungeon rate. The live clock itself always runs at the lobby rate.
AWAY_BOND_PER_HOUR = 0.05        # bond a pair of party members gain per dungeon hour spent away together (travelling and camping)
LIVE_SCALES = (1, 6, 60)         # speed presets multiplying both rates
LIVE_CATCHUP_MAX_HOURS = 48      # offline progress is capped (game hours)

# upgrades take game time when time passes for real (live / deferred turns); instant in the CLI and tests
CONSTRUCTION_HOURS = [6, 12, 24, 36]            # building level 1->2 ... 4->5
HATCHERY_REFUND = 0.05                           # per Hatchery level above 1: share of the gel of a pull given back

# Phoenix Feather: a consumable that lifts a slime that would die in battle back to its feet
FEATHER_COST = {"purple_gel": 2, "essence": 20}
FEATHER_HP = 0.3

# bounds that keep replies and saves small on a phone
PULL_MAX_N = 100                 # pulls in one action
COLONY_MAX = 400                 # slimes the colony can hold

# sanity (sanity.py): a mental reserve that caps the mood; rarer slimes have more and lose less per blow
SANITY_MAX = {"common": 60, "uncommon": 70, "rare": 80, "epic": 90, "legendary": 100}
SANITY_RESIST = {"common": 1.3, "uncommon": 1.15, "rare": 1.0, "epic": 0.85, "legendary": 0.7}   # x every loss
SANITY_MOOD_FLOOR = 0.3          # mood cap at zero sanity (grumpy at best)
SANITY_HIT = {"friend_died": 18, "slime_died": 3, "partner_died": 28, "knocked_out": 5, "battle_lost": 6, "brawl": 2.5, "quarrel": 1,
              "miserable_hour": 0.5}
SANITY_REST = {"sleeping": 0.8, "resting": 1.0, "ward": 1.5, "calm": 0.3}   # per hour; "calm" = idle at home in a good mood
SANITY_WIN = 1.0                 # a won fight steadies a little
SANITY_TALK = 6                  # the first talk of the day
SANITY_SOOTHE = 8                # the Keeper's Soothe, for everyone
SANITY_REFUSE = {"dungeon": 0.2, "job": 0.1}   # below this share of its reserve a slime refuses

# memory (memory.py): what slimes remember about each other
MEMORY_CAP = 14                  # memories a slime keeps
MEMORY_MAX_WEIGHT = 10.0
MEMORY_FADE = 0.93               # weight kept per game day (a strong memory lasts a few weeks)
MEMORY_MIN_WEIGHT = 0.4
MEMORY_MERGE_DAYS = 3            # the same thing happening again within this many days strengthens one memory
MEMORY_GRUDGE_MIN = 2.0          # a grudge this strong can be the stated reason of a quarrel

# the mind (mind.py): goals, decisions, requests, trust, drift
GOAL_DAYS = 5                    # a goal is reconsidered after this many days
GOAL_AVOID_MIN = 3.0             # memory weight of a fallen friend that makes a slime unable to face the dungeons
GOAL_RIVAL_MIN = 3.0
GOAL_FRIEND_MIN = 3.0
GOAL_COURT_BOND = 30             # bond at which a slime may set its heart on someone (no partner on either side, not kin)
GOAL_STYLE_XP = 3.0              # fighting-style xp from practising alone
DECIDE_CHANCE = 0.4              # per day, for an idle slime at home
DECIDE_MAX_EVENTS = 3            # journal lines per day, so the log stays readable
GOAL_TRAIN_XP = 0.6              # self-training XP per level
REQUEST_CHANCE = 0.18            # per day per slime without a request
REQUEST_DAYS = 3                 # an unanswered request lapses
REQUEST_GRUDGE = 3.0
REQUEST_FRIEND = 3.0
TRUST_GRANT, TRUST_DENY, TRUST_DENY_REST = 6.0, 4.0, 8.0
TRUST_REFUSE_SHIFT = 0.10        # at trust 100 the mood below which a slime refuses is this much lower (at 0: this much higher)
DRIFT_AT = {"ko": 6, "win": 25, "heal": 15}
