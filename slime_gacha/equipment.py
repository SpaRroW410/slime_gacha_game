"""Equipment: three slots (weapon, armor, charm), flat stat bonuses, usable by any class.

Gear is fungible: the colony inventory is a Counter of gear keys; a slime stores `gear = {slot: key}`.
Sources: the Armory (white gel / essence, tier gated by the Armory level) and dungeon drops. In dungeons,
a fallen slime drops its gear; survivors may carry it back (chance from party synergy), otherwise it is lost.

Extend: register_gear(Gear(...)).
"""
from collections import Counter
from dataclasses import dataclass
from typing import Dict

from .errors import InvalidAction
from .registry import Registry

SLOTS = ("weapon", "armor", "charm")


@dataclass(frozen=True)
class Gear:
    key: str
    name: str
    emoji: str
    slot: str
    tier: int
    stats: Dict[str, float]
    cost: Dict[str, int]


GEAR: "Registry[Gear]" = Registry("gear")


def register_gear(g: Gear) -> Gear:
    assert g.slot in SLOTS
    return GEAR.register(g, g.key)


MAX_TIER = 5          # the Armory sells tier 4 from level 7 and tier 5 from level 9; merging and the Deep Hollow make them too


def _g(key, name, emoji, slot, tier, stats):
    cost = {1: {"white_gel": 30}, 2: {"white_gel": 120, "essence": 10},
            3: {"white_gel": 400, "essence": 40, "purple_gel": 1},
            4: {"white_gel": 1200, "essence": 120, "purple_gel": 3},           # Armory level 7+
            5: {"white_gel": 3600, "essence": 360, "purple_gel": 9}}[tier]
    register_gear(Gear(key, name, emoji, slot, tier, stats, cost))


_g("wooden_club", "Wooden Club", "🏏", "weapon", 1, dict(atk=3))
_g("apprentice_wand", "Apprentice Wand", "🪄", "weapon", 1, dict(mag=3))
_g("hunting_bow", "Wooden Bow", "🏹", "weapon", 1, dict(atk=2, spd=2))
_g("goo_blade", "Goo Blade", "🗡️", "weapon", 2, dict(atk=6, spd=1))
_g("crystal_staff", "Crystal Staff", "🔮", "weapon", 2, dict(mag=6, hp=4))
_g("kings_edge", "King's Edge", "⚔️", "weapon", 3, dict(atk=11, spd=2))
_g("storm_staff", "Storm Staff", "⚡", "weapon", 3, dict(mag=11, spd=2))
_g("leather_wrap", "Leather Wrap", "🧥", "armor", 1, dict(defense=2, hp=6))
_g("gel_mail", "Gel Mail", "🛡️", "armor", 2, dict(defense=4, hp=14))
_g("obsidian_plate", "Obsidian Plate", "⚫", "armor", 3, dict(defense=8, hp=30))
_g("lucky_pebble", "River Pebble", "🪨", "charm", 1, dict(spd=1, hp=4))
_g("moss_charm", "Moss Charm", "🍀", "charm", 2, dict(hp=10, mag=2, atk=2))
_g("heart_shard", "Dawn Shard", "💜", "charm", 3, dict(atk=3, mag=3, defense=3, spd=3, hp=10))
_g("sling", "Leather Sling", "🪃", "weapon", 1, dict(atk=1, spd=3))
_g("cloth_robe", "Cloth Tunic", "👚", "armor", 1, dict(defense=1, mag=2, hp=4))
_g("bone_charm", "Bone Charm", "🦴", "charm", 1, dict(atk=1, mag=1, hp=2))
_g("composite_bow", "Composite Bow", "🎯", "weapon", 2, dict(atk=4, spd=3))
_g("scout_leathers", "Scout Leathers", "🥾", "armor", 2, dict(defense=3, spd=2, hp=10))
_g("silk_robe", "Silk Vestment", "🧵", "armor", 2, dict(defense=2, mag=3, hp=10))
_g("ember_locket", "Ember Pendant", "🔥", "charm", 2, dict(atk=2, mag=2, spd=1, hp=4))
_g("sunfire_bow", "Sunfire Bow", "🌅", "weapon", 3, dict(atk=8, spd=5))
_g("archmage_mantle", "Archmage Mantle", "🌌", "armor", 3, dict(defense=5, mag=6, hp=22))
_g("phoenix_plume", "Phoenix Plume", "🪽", "charm", 3, dict(hp=20, spd=2, defense=2))
# tier 4 and 5: made by merging three of the tier below (or found deep in the Hollow)
_g("titan_cleaver", "Titan Cleaver", "🪓", "weapon", 4, dict(atk=18, spd=3))
_g("astral_scepter", "Astral Scepter", "🌠", "weapon", 4, dict(mag=18, spd=3))
_g("windrunner_bow", "Windrunner Bow", "🎐", "weapon", 4, dict(atk=13, spd=8))
_g("dragonscale_armor", "Dragonscale Armor", "🐲", "armor", 4, dict(defense=13, hp=50))
_g("starweave_raiment", "Starweave Raiment", "🌟", "armor", 4, dict(defense=8, mag=10, hp=36))
_g("sunstone_amulet", "Sunstone Amulet", "🔆", "charm", 4, dict(atk=5, mag=5, defense=5, spd=4, hp=18))
_g("worldsplitter", "Worldsplitter", "⚔️", "weapon", 5, dict(atk=28, spd=4))
_g("eternity_staff", "Eternity Staff", "♾️", "weapon", 5, dict(mag=28, spd=4))
_g("starfall_bow", "Starfall Bow", "🌌", "weapon", 5, dict(atk=20, spd=13))
_g("celestial_aegis", "Celestial Aegis", "🛡️", "armor", 5, dict(defense=20, hp=80))
_g("mothers_veil", "Mother's Veil", "🫧", "armor", 5, dict(defense=12, mag=16, hp=55))
_g("hollow_heart", "Heart of the Hollow", "💗", "charm", 5, dict(atk=8, mag=8, defense=8, spd=6, hp=30))


# Matching sets: wear two or three pieces of one set for a bonus (flat stats, on top of the pieces).
GEAR_SETS = {
    "scrapper": dict(name="Scrapper", emoji="🧷", pieces=("wooden_club", "leather_wrap", "lucky_pebble"),
                     bonus={2: dict(atk=1, defense=1), 3: dict(atk=3, defense=2, hp=8)}),
    "tinkerer": dict(name="Tinkerer", emoji="🔧", pieces=("apprentice_wand", "hunting_bow", "leather_wrap", "lucky_pebble"),
                     bonus={2: dict(mag=1, spd=1), 3: dict(mag=3, spd=2, hp=6)}),
    "gooey": dict(name="Gooey Guard", emoji="💧", pieces=("goo_blade", "gel_mail", "moss_charm"),
                  bonus={2: dict(atk=2, hp=8), 3: dict(atk=4, defense=3, hp=20)}),
    "arcane": dict(name="Arcane Weave", emoji="🔮", pieces=("crystal_staff", "gel_mail", "moss_charm"),
                   bonus={2: dict(mag=3, hp=6), 3: dict(mag=6, defense=2, hp=16)}),
    "novice": dict(name="Novice Robes", emoji="📜", pieces=("apprentice_wand", "cloth_robe", "bone_charm"),
                   bonus={2: dict(mag=2, hp=4), 3: dict(mag=4, spd=1, hp=10)}),
    "wayfarer": dict(name="Wayfarer Kit", emoji="🧭", pieces=("composite_bow", "scout_leathers", "ember_locket"),
                     bonus={2: dict(atk=2, spd=2), 3: dict(atk=4, spd=3, hp=14)}),
    "titan": dict(name="Titan's Arms", emoji="🗿", pieces=("titan_cleaver", "dragonscale_armor", "sunstone_amulet"),
                  bonus={2: dict(atk=6, defense=4, hp=20), 3: dict(atk=12, defense=8, hp=50)}),
    "astral": dict(name="Astral Court", emoji="🌠", pieces=("astral_scepter", "starweave_raiment", "sunstone_amulet"),
                   bonus={2: dict(mag=6, spd=2, hp=16), 3: dict(mag=12, spd=4, hp=40)}),
    "mother": dict(name="The Mother's Gifts", emoji="💗", pieces=("worldsplitter", "eternity_staff", "starfall_bow", "celestial_aegis", "mothers_veil", "hollow_heart"),
                   bonus={2: dict(atk=8, mag=8, hp=30), 3: dict(atk=16, mag=16, defense=10, spd=4, hp=80)}),
    "royal": dict(name="Royal Regalia", emoji="👑", pieces=("kings_edge", "storm_staff", "obsidian_plate", "heart_shard"),
                  bonus={2: dict(atk=3, mag=3, hp=15), 3: dict(atk=6, mag=6, defense=5, hp=40)}),
}


def set_status(equipped: Dict[str, str]) -> list:
    """For each set the slime wears at least one piece of: how many, the bonus now, and what the next piece gives."""
    worn = set(equipped.values())
    out = []
    for key, s in GEAR_SETS.items():
        n = sum(1 for p in set(s["pieces"]) if p in worn)
        if n:
            n = min(n, 3)
            bonus = s["bonus"].get(n) if n >= 2 else None
            out.append(dict(key=key, name=s["name"], emoji=s["emoji"], count=n, bonus=bonus or {},
                            next=s["bonus"].get(n + 1) if n < 3 else None))
    return out


def set_bonus(equipped: Dict[str, str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for st in set_status(equipped):
        for stat, v in st["bonus"].items():
            out[stat] = out.get(stat, 0) + v
    return out


def gear_bonus(equipped: Dict[str, str]) -> Dict[str, float]:
    if not equipped:
        return {}
    out: Dict[str, float] = dict(set_bonus(equipped))
    for key in equipped.values():
        if key in GEAR:
            for stat, v in GEAR.get(key).stats.items():
                out[stat] = out.get(stat, 0) + v
    return out


class Inventory:
    """Unequipped gear owned by the colony."""

    def __init__(self):
        self.items: Counter = Counter()

    def add(self, key: str, n: int = 1) -> None:
        GEAR.get(key)
        self.items[key] += n

    def take(self, key: str) -> None:
        if self.items[key] <= 0:
            raise InvalidAction(f"You have no {GEAR.get(key).name if key in GEAR else key}.")
        self.items[key] -= 1
        if self.items[key] == 0:
            del self.items[key]

    def equip(self, slime, key: str) -> str:
        g = GEAR.get(key)
        self.take(key)
        old = slime.gear.get(g.slot)
        if old:
            self.add(old)
        slime.gear[g.slot] = key
        slime.hp = min(slime.hp + int(g.stats.get("hp", 0)), slime.max_hp)
        return f"{slime.name} equips {g.emoji}{g.name}" + (f" (swapping out {GEAR.get(old).name})" if old else "") + "."

    def unequip(self, slime, slot: str) -> str:
        key = slime.gear.pop(slot, None)
        if not key:
            raise InvalidAction(f"{slime.name} has nothing in the {slot} slot.")
        self.add(key)
        slime.hp = min(slime.hp, slime.max_hp)
        return f"{slime.name} takes off {GEAR.get(key).name}."

    def to_dict(self):
        return dict(self.items)

    def load(self, d):
        self.items = Counter({k: v for k, v in (d or {}).items() if k in GEAR and v > 0})
