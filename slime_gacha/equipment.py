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


def _g(key, name, emoji, slot, tier, stats):
    cost = {1: {"white_gel": 30}, 2: {"white_gel": 120, "essence": 10},
            3: {"white_gel": 400, "essence": 40, "purple_gel": 1}}[tier]
    register_gear(Gear(key, name, emoji, slot, tier, stats, cost))


_g("wooden_club", "Wooden Club", "🏏", "weapon", 1, dict(atk=3))
_g("apprentice_wand", "Apprentice Wand", "🪄", "weapon", 1, dict(mag=3))
_g("hunting_bow", "Hunting Bow", "🏹", "weapon", 1, dict(atk=2, spd=2))
_g("goo_blade", "Goo Blade", "🗡️", "weapon", 2, dict(atk=6, spd=1))
_g("crystal_staff", "Crystal Staff", "🔮", "weapon", 2, dict(mag=6, hp=4))
_g("kings_edge", "King's Edge", "⚔️", "weapon", 3, dict(atk=11, spd=2))
_g("storm_staff", "Storm Staff", "⚡", "weapon", 3, dict(mag=11, spd=2))
_g("leather_wrap", "Leather Wrap", "🧥", "armor", 1, dict(defense=2, hp=6))
_g("gel_mail", "Gel Mail", "🛡️", "armor", 2, dict(defense=4, hp=14))
_g("obsidian_plate", "Obsidian Plate", "⚫", "armor", 3, dict(defense=8, hp=30))
_g("lucky_pebble", "Lucky Pebble", "🪨", "charm", 1, dict(spd=1, hp=4))
_g("moss_charm", "Moss Charm", "🍀", "charm", 2, dict(hp=10, mag=2, atk=2))
_g("heart_shard", "Heart Shard", "💜", "charm", 3, dict(atk=3, mag=3, defense=3, spd=3, hp=10))


def gear_bonus(equipped: Dict[str, str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
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
