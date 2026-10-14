"""Bestiary: every monster of the Hollow Descent and the Gloop Pit.

Monsters are defined by *role* (how they fight), *family* (goblin, direwolf, orc, ogre ...), *habitats* (which
terrain kinds they live in) and a floor *band*. Their stats are not typed in: `build_enemy` derives them from the
floor being generated, so a goblin on floor 3 and a goblin on floor 20 are both correctly tuned.

    stats = unit(floor) x role profile x (elite factor)
    unit  : hp 26g, atk 7g, def 3.5(1+0.8(g-1)), mag 7g, spd 5(1+0.012(f-1)),  g = 1 + 0.15(f-1) + 0.0035(f-1)^2

Bosses (one per 5-floor segment) are hand-built in BOSSES. Add monsters with register_monster(...), add moves with
register_ability(...) (see abilities.py); new families simply appear in the waves of the terrains they list.
"""
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import config
from .abilities import Ability, register_ability
from .battle import Enemy
from .registry import Registry

MAX_FLOOR = 50


# ---- monster moves ---------------------------------------------------------------------------------
def _ab(key, name, kind, power, stat, target, cd, desc="", element="", duration=0, minion=""):
    register_ability(Ability(key, name, kind, power, stat, target, cd, duration, desc, element, 0, "", minion))


for _row in [
    ("nip", "Nip", "damage", 0.9, "atk", "enemy", 0, "A quick bite."),
    ("bat_bite", "Leeching Bite", "drain", 0.8, "atk", "enemy", 1, "Drinks a little life."),
    ("sling_stone", "Sling Stone", "damage", 1.1, "atk", "enemy", 0, "A stone to the eye."),
    ("orc_bow", "Crude Bow", "damage", 1.3, "atk", "enemy", 0, "Arrows with feathers glued on."),
    ("rusty_stab", "Rusty Stab", "poison", 0.5, "atk", "enemy", 2, "Tetanus included.", "", 3),
    ("sting", "Venom Sting", "poison", 0.6, "atk", "enemy", 2, "A burning sting.", "", 3),
    ("web_bite", "Web Bite", "poison", 0.7, "atk", "enemy", 2, "Venom and silk.", "", 4),
    ("toxic_lash", "Toxic Lash", "poison", 0.6, "atk", "enemy", 2, "A slimy tongue.", "water", 3),
    ("goblin_rally", "Rally!", "guard", 0.0, "atk", "all_allies", 4, "Everybody shout.", "", 2),
    ("howl", "Pack Howl", "guard", 0.0, "atk", "all_allies", 4, "The pack closes ranks.", "", 2),
    ("pounce", "Pounce", "damage", 1.7, "atk", "enemy", 2, "Jaws first."),
    ("gore", "Gore", "damage", 1.6, "atk", "enemy", 1, "Tusks."),
    ("rend", "Rend", "poison", 0.6, "atk", "enemy", 2, "Claws that keep bleeding.", "", 3),
    ("club_smash", "Club Smash", "damage", 1.9, "atk", "enemy", 2, "A big stick."),
    ("ground_pound", "Ground Pound", "damage", 1.0, "atk", "all_enemies", 3, "The floor jumps."),
    ("boulder_toss", "Boulder Toss", "damage", 1.6, "atk", "enemy", 2, "Rocks fall.", "earth"),
    ("regenerate", "Regenerate", "heal", 0.9, "atk", "self", 3, "Wounds close over."),
    ("frenzy", "Frenzy", "damage", 1.9, "atk", "enemy", 2, "Teeth and fury."),
    ("gale_slash", "Gale Slash", "damage", 1.3, "atk", "enemy", 0, "A cutting wind.", "wind"),
    ("fire_bomb", "Fire Bomb", "damage", 1.3, "mag", "enemy", 1, "Lit fuse, thrown.", "fire"),
    ("flame_breath", "Flame Breath", "damage", 1.0, "mag", "all_enemies", 3, "A roaring cone.", "fire"),
    ("lava_spit", "Lava Spit", "damage", 1.5, "mag", "enemy", 1, "Molten gob.", "fire"),
    ("sand_blast", "Sand Blast", "damage", 0.9, "mag", "all_enemies", 3, "Scouring grit.", "sand"),
    ("tidal_wave", "Tidal Wave", "damage", 0.9, "mag", "all_enemies", 3, "Everybody wet.", "water"),
    ("tentacle_slam", "Tentacle Slam", "damage", 1.0, "atk", "all_enemies", 3, "Slap, slap, slap.", "water"),
    ("siren_song", "Siren Song", "drain", 1.1, "mag", "enemy", 1, "Sweet and ruinous.", "water"),
    ("frost_lance", "Frost Lance", "damage", 1.5, "mag", "enemy", 1, "A spear of ice.", "water"),
    ("frost_nova", "Frost Nova", "damage", 1.0, "mag", "all_enemies", 3, "A ring of cold.", "water"),
    ("blizzard", "Blizzard", "damage", 0.9, "mag", "all_enemies", 3, "White-out.", "blizzard"),
    ("avalanche", "Avalanche", "damage", 1.0, "atk", "all_enemies", 3, "Snow, then more snow.", "water"),
    ("lightning_bolt", "Lightning Bolt", "damage", 1.6, "mag", "enemy", 1, "Zap.", "lightning"),
    ("chain_lightning", "Chain Lightning", "damage", 0.9, "mag", "all_enemies", 3, "It jumps.", "lightning"),
    ("thunder_charge", "Thunder Charge", "damage", 1.7, "atk", "enemy", 2, "Hooves and sparks.", "lightning"),
    ("wing_buffet", "Wing Buffet", "damage", 0.9, "atk", "all_enemies", 3, "A very large flap.", "wind"),
    ("storm_dive", "Storm Dive", "damage", 2.0, "atk", "enemy", 3, "Out of the cloud, talons first.", "wind"),
    ("shard_lance", "Shard Lance", "damage", 1.5, "mag", "enemy", 1, "A spike of crystal.", "earth"),
    ("shard_burst", "Shard Burst", "damage", 0.9, "mag", "all_enemies", 3, "Shrapnel.", "earth"),
    ("hex_bolt", "Hex Bolt", "poison", 0.6, "mag", "enemy", 2, "A rotten curse.", "", 3),
    ("dry_curse", "Dry Curse", "poison", 0.5, "mag", "all_enemies", 4, "Everything cracks.", "", 3),
    ("spore_cloud", "Spore Cloud", "poison", 0.35, "mag", "all_enemies", 3, "Don't breathe.", "earth", 3),
    ("bone_club", "Bone Club", "damage", 1.0, "atk", "enemy", 0, "Someone's old leg."),
    ("ghoul_claw", "Ghoul Claw", "drain", 1.1, "atk", "enemy", 1, "Cold fingers."),
    ("needle_burst", "Needle Burst", "damage", 0.8, "atk", "all_enemies", 3, "A cactus sneeze."),
    ("pincer", "Pincer", "damage", 1.3, "atk", "enemy", 0, "Snip."),
    ("bog_slam", "Bog Slam", "damage", 1.7, "atk", "enemy", 2, "A muddy fist.", "water"),
    ("raise_dead", "Raise Dead", "summon", 0.6, "mag", "self", 5, "Up you get.", "", 0, "💀 Skeleton"),
    ("summon_whelp", "Call Whelp", "summon", 0.5, "mag", "self", 5, "Little goblin, big noise.", "", 0, "👺 Goblin Whelp"),
    ("summon_scarabs", "Scarab Swarm", "summon", 0.6, "mag", "self", 5, "They come from the sand.", "", 0, "🪲 Scarab Swarm"),
    ("summon_pack", "Call the Pack", "summon", 0.7, "atk", "self", 5, "Answering howls.", "", 0, "🐺 Pack Wolf"),
    ("summon_guards", "Summon Guards", "summon", 0.6, "atk", "self", 5, "Stone steps forward.", "", 0, "🗿 Hollow Guard"),
]:
    _ab(*_row)


# ---- roles: (hp, atk, def, mag, spd, xp, loot) multipliers on the floor's unit stats ----------------------
ROLES: Dict[str, Tuple[float, ...]] = {
    "swarmer":    (0.75, 0.80, 0.50, 0.00, 1.20, 0.7, 0.7),
    "skirmisher": (0.90, 1.10, 0.60, 0.20, 1.50, 1.0, 1.0),
    "hunter":     (1.20, 1.50, 0.80, 0.00, 1.60, 1.4, 1.2),
    "bruiser":    (1.60, 1.30, 1.20, 0.00, 0.80, 1.4, 1.2),
    "brute":      (2.50, 1.80, 1.00, 0.00, 0.50, 2.0, 1.5),
    "tank":       (2.20, 0.90, 2.00, 0.00, 0.50, 1.5, 1.2),
    "caster":     (0.90, 0.30, 0.60, 1.50, 1.00, 1.3, 1.2),
    "support":    (1.10, 0.50, 0.80, 1.10, 0.90, 1.2, 1.1),
}
LEADERS = ("bruiser", "brute", "tank", "caster", "support")
FOLLOWERS = ("swarmer", "skirmisher", "hunter")


@dataclass(frozen=True)
class Monster:
    key: str
    name: str
    emoji: str
    family: str
    role: str
    element: str
    habitats: Tuple[str, ...]
    lo: int
    hi: int
    abilities: Tuple[str, ...]


MONSTERS: "Registry[Monster]" = Registry("monster")


def register_monster(m: Monster) -> Monster:
    assert m.role in ROLES, f"unknown role {m.role}"
    return MONSTERS.register(m, m.key)


# key | name | emoji | family | role | element | habitats | floors | abilities
_ROSTER = """
dust_bunny|Dust Bunny|🐇|critter|swarmer|wind|valley,plains,dunes|1-9|splat,nip
crust_beetle|Crust Beetle|🪲|critter|bruiser|earth|valley,dunes,canyon|1-16|splat,smash
snow_hare|Snow Hare|🐰|critter|swarmer|water|tundra,plains|3-24|nip,splat
goblin_scout|Goblin Scout|👺|goblin|skirmisher||valley,caverns,canyon,plains,dunes,ruins|1-24|rusty_stab,sling_stone
goblin_slinger|Goblin Slinger|👺|goblin|skirmisher||valley,caverns,plains,canyon,cliffs|1-26|sling_stone
goblin_bruiser|Goblin Bruiser|👺|goblin|bruiser||valley,caverns,canyon,swamp,plains|3-28|club_smash,goblin_rally
goblin_shaman|Goblin Shaman|👺|goblin|caster|fire|valley,caverns,swamp,canyon,dunes|3-30|fire_bomb,summon_whelp,mend
goblin_sapper|Goblin Sapper|👺|goblin|swarmer|fire|dunes,volcano,caverns,canyon|5-27|fire_bomb,nip
goblin_buccaneer|Goblin Buccaneer|👺|goblin|skirmisher|water|islands,swamp,tundra|7-34|rusty_stab,fire_bomb
goblin_wolfrider|Goblin Wolfrider|👺|goblin|hunter||plains,valley,dunes,cliffs|8-34|pounce,sling_stone
wolf_pup|Wolf Pup|🐺|direwolf|swarmer||valley,tundra,plains,cliffs|1-16|nip,howl
direwolf|Direwolf|🐺|direwolf|hunter||valley,tundra,plains,cliffs,canyon,swamp|4-38|pounce,howl
alpha_wolf|Alpha Wolf|🐺|direwolf|bruiser||valley,tundra,plains,cliffs|12-44|pounce,howl,rend
frost_wolf|Frost Wolf|🐺|direwolf|hunter|water|tundra,cliffs|14-50|pounce,frost_lance
dire_boar|Dire Boar|🐗|beast|bruiser||valley,swamp,plains,canyon|3-32|gore,pounce
giant_spider|Giant Spider|🕷️|beast|skirmisher||caverns,swamp,canyon,ruins,barrens|6-42|web_bite,rend
cave_bat|Cave Bat|🦇|beast|swarmer||caverns,canyon,barrens,ruins,cliffs|1-30|bat_bite,nip
orc_grunt|Orc Grunt|👹|orc|bruiser||canyon,valley,volcano,plains,dunes,tundra|10-36|club_smash,war_cry
orc_archer|Orc Archer|👹|orc|skirmisher||canyon,plains,cliffs,valley,tundra|10-36|orc_bow
orc_hexer|Orc Hexer|👹|orc|caster|earth|canyon,valley,swamp,volcano,dunes|11-38|hex_bolt,mend,boulder_toss
orc_berserker|Orc Berserker|👹|orc|hunter||volcano,canyon,plains,dunes|13-40|frenzy,rend
orc_warlord|Orc Warlord|👹|orc|brute||canyon,volcano,plains,valley,tundra|16-46|club_smash,war_cry,goblin_rally
ogre_brute|Ogre Brute|🧌|ogre|brute||valley,canyon,swamp,caverns,tundra|16-48|club_smash,ground_pound
ogre_mauler|Ogre Mauler|🧌|ogre|bruiser||valley,canyon,plains,volcano|15-46|club_smash,boulder_toss
ogre_magus|Ogre Magus|🧌|ogre|caster|fire|volcano,canyon,valley,dunes,ruins|18-50|fire_bomb,mend,flame_breath
cave_troll|Cave Troll|🧌|troll|tank||caverns,swamp,canyon,tundra|14-46|regenerate,club_smash
swamp_troll|Swamp Troll|🧌|troll|tank|water|swamp,islands|14-46|regenerate,bog_slam
sand_scarab|Sand Scarab|🪲|scarab|swarmer|earth|dunes,canyon,barrens|8-38|nip,sting
dune_stalker|Dune Stalker|🦂|scarab|hunter|earth|dunes,canyon|10-44|sting,pounce
mummy|Mummy|🧟|undead|tank|earth|dunes,barrens,ruins|14-48|curse,club_smash
dust_djinn|Dust Djinn|🌪️|spirit|caster|wind|dunes,cliffs,plains|12-50|sand_blast,gale_slash,mend
cactus_spriggan|Cactus Spriggan|🌵|spirit|support|earth|dunes,valley,canyon|8-40|needle_burst,mend
crab_knight|Crab Knight|🦀|sea|tank|water|islands,swamp,tundra|9-40|pincer,war_cry
jelly_swarm|Jelly Swarm|🪼|sea|swarmer|water|islands,swamp,caverns|4-34|sting,nip
siren|Siren|🧜|sea|caster|water|islands,swamp,tundra|12-46|siren_song,mend
sea_drake|Sea Drake|🐉|sea|hunter|water|islands,tundra|14-50|pounce,tidal_wave
kraken_tendril|Kraken Tendril|🐙|sea|bruiser|water|islands,swamp|20-50|tentacle_slam,pincer
snow_yeti|Snow Yeti|🦣|giant|brute|water|tundra,cliffs|16-48|club_smash,avalanche
ice_golem|Ice Golem|🧊|golem|tank|water|tundra,cliffs,caverns|14-50|frost_nova,club_smash
frost_witch|Frost Witch|🧙|spirit|caster|water|tundra,cliffs,islands|14-50|frost_lance,blizzard,mend
fire_imp|Fire Imp|😈|imp|swarmer|fire|volcano,dunes,ruins,caverns|6-40|fire_bomb,nip
magma_slug|Magma Slug|🐌|elemental|bruiser|fire|volcano|10-46|lava_spit,gore
lava_golem|Lava Golem|🌋|golem|tank|fire|volcano|18-50|ground_pound,lava_spit
ash_drake|Ash Drake|🐲|dragonkin|hunter|fire|volcano,cliffs,dunes|20-50|pounce,flame_breath
flame_ogre|Flame Ogre|🧌|ogre|brute|fire|volcano|24-50|club_smash,flame_breath
bog_toad|Bog Toad|🐸|swamp|bruiser|water|swamp,islands,valley|3-34|toxic_lash,gore
mire_hag|Mire Hag|🧙|swamp|caster|water|swamp,caverns|10-44|hex_bolt,mend,siren_song
leech_swarm|Leech Swarm|🪱|swamp|swarmer|water|swamp,islands,caverns|5-36|bat_bite,nip
swamp_gator|Swamp Gator|🐊|swamp|hunter|water|swamp,islands|8-40|pounce,rend
crystal_golem|Crystal Golem|💎|golem|tank|earth|canyon,caverns|12-46|shard_burst,ground_pound
gem_spider|Gem Spider|🕷️|beast|skirmisher|earth|canyon,caverns|8-42|web_bite,shard_lance
shard_wraith|Shard Wraith|👻|spirit|caster|earth|canyon,caverns,ruins|16-50|shard_lance,shard_burst
stone_giant|Stone Giant|🗿|giant|brute|earth|valley,canyon,cliffs|20-50|boulder_toss,ground_pound
harpy|Harpy|🦅|aerial|skirmisher|wind|cliffs,islands,plains|7-44|gale_slash,nip
thunderbird|Thunderbird|🦤|aerial|caster|wind|cliffs,plains|20-50|lightning_bolt,storm_dive
roc|Roc|🦅|aerial|brute|wind|cliffs,islands|26-50|wing_buffet,storm_dive
storm_hawk|Storm Hawk|🦅|aerial|hunter|wind|plains,cliffs|12-48|gale_slash,pounce
thunder_boar|Thunder Boar|🐗|beast|bruiser|wind|plains,cliffs|10-44|thunder_charge,gore
lightning_elemental|Lightning Elemental|⚡|elemental|caster|wind|plains,cliffs|22-50|lightning_bolt,chain_lightning
skeleton|Skeleton|💀|undead|swarmer||barrens,ruins,caverns,dunes|10-50|bone_club,nip
ghoul|Ghoul|🧟|undead|bruiser||barrens,ruins,caverns|14-50|ghoul_claw,club_smash
wraith|Wraith|👻|undead|caster||barrens,ruins,caverns|18-50|shadow_bolt,hex_bolt
bone_knight|Bone Knight|☠️|undead|tank||barrens,ruins|22-50|club_smash,war_cry
necromage|Necromage|🧛|undead|support||barrens,ruins|26-50|raise_dead,hex_bolt,curse
hollow_guard|Hollow Guard|🗿|hollow|tank||ruins,valley,caverns|1-50|smash,war_cry
hollow_archer|Hollow Archer|🗿|hollow|skirmisher||ruins,canyon,valley|5-50|orc_bow
hollow_mage|Hollow Mage|🗿|hollow|caster||ruins,caverns|8-50|spark,arcane_surge
dry_husk|Dry Husk|🏺|hollow|swarmer|fire|ruins,volcano,dunes,barrens|28-50|nip,bone_club
parched_wraith|Parched Wraith|👻|hollow|caster|fire|ruins,volcano,dunes|38-50|dry_curse,hex_bolt
spore_shroom|Spore Shroom|🍄|fungus|support|earth|caverns,swamp,valley|4-40|spore_cloud,mend
shroom_brute|Shroom Brute|🍄|fungus|bruiser|earth|caverns,swamp,valley|8-40|club_smash,spore_cloud
"""
for _line in _ROSTER.strip().splitlines():
    k, n, e, fam, role, el, hab, band, ab = _line.split("|")
    lo, hi = (int(x) for x in band.split("-"))
    register_monster(Monster(k, n, e, fam, role, el, tuple(hab.split(",")), lo, hi, tuple(ab.split(","))))


# ---- bosses ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Boss:
    key: str
    name: str
    emoji: str
    floor: int
    element: str
    terrain: str                       # terrain key of its lair
    mult: Tuple[float, float, float, float, float]    # hp, atk, def, mag, spd vs the floor's unit
    abilities: Tuple[str, ...]
    escorts: Tuple[str, ...]           # monster families that follow it
    xp: float = 8.0
    purple: float = 0.35
    purple_amount: int = 1
    lore: str = ""


BOSSES: Dict[int, Boss] = {}


def _boss(b: Boss) -> Boss:
    BOSSES[b.floor] = b
    return b


_boss(Boss("hollow_warden", "The Hollow Warden", "🗝️", 5, "earth", "hollow_halls", (6.0, 1.4, 1.5, 1.0, 1.0),
           ("smash", "rampage", "war_cry", "summon_guards"), ("hollow",),
           lore="The first guardian: a stone knight that forgot why it guards."))
_boss(Boss("grumpus", "Grumpus the Gobbo King", "👺", 10, "fire", "ember_valley", (6.5, 1.5, 1.2, 1.4, 1.1),
           ("club_smash", "goblin_rally", "summon_whelp", "fire_bomb"), ("goblin", "direwolf"),
           lore="Crowned with a cooking pot. Rides a direwolf called Biscuit."))
_boss(Boss("fenrisk", "Fenrisk, Alpha of the Pack", "🐺", 15, "water", "frozen_tundra", (6.5, 1.7, 1.1, 0.8, 1.5),
           ("pounce", "howl", "rend", "summon_pack"), ("direwolf", "goblin"),
           lore="Every wolf in the valley answers to it."))
_boss(Boss("bruntar", "Bruntar the Ogre Chieftain", "🧌", 20, "earth", "red_mesa", (8.0, 1.9, 1.3, 0.6, 0.7),
           ("club_smash", "ground_pound", "regenerate", "war_cry"), ("ogre", "orc"),
           lore="Eats orcs for breakfast and is still somehow their chieftain."))
_boss(Boss("scarab_queen", "The Scarab Queen", "👑", 25, "earth", "dune_sea", (7.0, 1.5, 1.2, 1.6, 1.0),
           ("sand_blast", "sting", "summon_scarabs", "curse"), ("scarab", "undead"),
           lore="Mother of the dunes. The sand itself is her brood."))
_boss(Boss("marrow_kraken", "The Marrow Kraken", "🐙", 30, "water", "coral_isles", (9.0, 1.7, 1.3, 1.5, 0.9),
           ("tentacle_slam", "tidal_wave", "siren_song", "toxic_lash"), ("sea", "goblin"),
           lore="Wrecked a hundred ships and kept the bones."))
_boss(Boss("glacial_jarl", "The Glacial Jarl", "🧊", 35, "water", "glacier_hall", (9.5, 1.8, 1.8, 1.5, 0.7),
           ("frost_nova", "frost_lance", "avalanche", "regenerate"), ("giant", "direwolf", "golem"),
           lore="A frost giant who thinks the whole world should be ice."))
_boss(Boss("thunderwing", "Thunderwing", "🦤", 40, "wind", "thunder_peaks", (9.0, 1.9, 1.2, 1.9, 1.5),
           ("lightning_bolt", "chain_lightning", "storm_dive", "wing_buffet"), ("aerial", "elemental"),
           lore="Every thunderstorm on the continent is its mood."))
_boss(Boss("morrowhex", "Morrowhex the Lich Regent", "🧛", 45, "", "ruined_crypt", (10.0, 1.4, 1.5, 2.2, 1.0),
           ("raise_dead", "ghoul_claw", "curse", "shadow_bolt"), ("undead",),
           lore="Reigned from the grave for so long it forgot it was dead.", purple=0.4))
_boss(Boss("parched_king", "The Parched King", "🏜️", 50, "fire", "dust_throne", (12.0, 2.0, 1.6, 2.0, 1.1),
           ("smash", "rampage", "arcane_surge", "dry_curse", "summon_guards"), ("hollow", "ogre", "undead"),
           xp=12.0, purple=0.5, purple_amount=2, lore="The Dry Tide's avatar. Beat him and the Mother may wake."))


def boss_for(floor: int) -> Optional[Boss]:
    return BOSSES.get(floor)


# ---- stat builder -------------------------------------------------------------------------------------------
def player_curve(level: float) -> float:
    """How strong a typical slime of this level is, relative to level 1 (atk and hp averaged). It follows the real
    progression: +2 atk / +6 hp per level, with the stage multipliers (x1 / x1.5 / x2.1) kicking in above the level
    caps (10 / 25), so the dungeon steps up where evolution lets the player step up."""
    stage = 0 if level <= config.LEVEL_CAPS[0] else 1 if level <= config.LEVEL_CAPS[1] else 2
    sm = config.STAGE_STAT_MULT[stage]
    atk, hp = (9 + 2 * (level - 1)) * sm, (40 + 6 * (level - 1)) * sm
    return (atk / 9 + hp / 40) / 2


def difficulty(floor: float, pit: bool = False) -> float:
    """The Descent is deliberately rough: monsters reach 1.65x the power of a typical same-level slime by floor 8
    (simulated: an unequipped, un-scouted party of the right level wins ordinary floors with a loss or two and
    loses to bosses about half the time; gear, styles, elements, synergy and intel tip it). The Pit is a fair fight."""
    return 1.0 if pit else 1 + 0.65 * min(1.0, (floor - 1) / 7)


def growth(floor: float, pit: bool = False) -> float:
    """The depth curve g(f) = difficulty x typical slime power at level f (floor f is built for level-f slimes)."""
    return difficulty(floor, pit) * player_curve(floor)


def unit(floor: float, pit: bool = False) -> Dict[str, float]:
    g = growth(floor, pit)
    return dict(g=g, hp=26 * g, atk=7 * g, defense=3.5 * (1 + 0.8 * (g - 1)), mag=7 * g, spd=5 * (1 + 0.012 * (floor - 1)))


def _loot(floor: float, mult: float, pit: bool) -> Dict[str, tuple]:
    step = (1 + config.MAIN_LOOT_STEP * (floor - 1)) * mult * (config.GRIND_LOOT_MULT if pit else 1.0)
    lo = max(0, int(0.5 * step))
    loot = {"white_gel": (lo, max(lo, int(round(2.0 * step))))}
    if floor >= 8:
        loot["essence"] = (0, 1 + int(floor // 8))
    loot["food"] = (0, 2)
    return loot


def build_enemy(m: Monster, floor: int, elite: float = 1.0, pit: bool = False) -> Enemy:
    """A monster as it exists on `floor` (elite > 1 for leaders)."""
    hp, atk, d, mag, spd, xp, loot = ROLES[m.role]
    u = unit(floor, pit)
    stats = dict(hp=round(u["hp"] * hp * elite, 1), atk=round(u["atk"] * atk * elite, 1),
                 defense=round(u["defense"] * d * (elite ** 0.5), 1), mag=round(u["mag"] * mag * elite, 1),
                 spd=round(u["spd"] * spd, 1))
    purple = 0.0 if pit else min(0.4, (0.01 + 0.0012 * floor) * loot)
    return Enemy(m.key, m.name, m.emoji, 1 + (floor - 1) // 10, stats, list(m.abilities),
                 max(1, int(12 * xp * u["g"] ** 0.9 * elite)), _loot(floor, loot, pit), purple, 1, m.element,
                 m.family, m.role, False)


def build_boss(b: Boss, floor: Optional[int] = None) -> Enemy:
    floor = floor or b.floor
    u = unit(floor)
    hp, atk, d, mag, spd = b.mult
    stats = dict(hp=round(u["hp"] * hp, 1), atk=round(u["atk"] * atk, 1), defense=round(u["defense"] * d, 1),
                 mag=round(u["mag"] * mag, 1), spd=round(u["spd"] * spd, 1))
    lo = max(1, int(3 * (1 + config.MAIN_LOOT_STEP * (floor - 1))))
    loot = {"white_gel": (lo, lo * 2), "essence": (2 + floor // 5, 4 + floor // 3)}
    return Enemy(b.key, b.name, b.emoji, 1 + (floor - 1) // 10, stats, list(b.abilities),
                 int(12 * b.xp * u["g"] ** 0.9), loot, b.purple, b.purple_amount, b.element, "boss", "boss", True)


def pool_for(kind: str, floor: int, families: Optional[Tuple[str, ...]] = None, slack: int = 0) -> List[Monster]:
    """Monsters living in a terrain kind within the floor band (optionally limited to families)."""
    out = [m for m in MONSTERS if kind in m.habitats and m.lo - slack <= floor <= m.hi + slack]
    if families:
        out = [m for m in out if m.family in families]
    return out
