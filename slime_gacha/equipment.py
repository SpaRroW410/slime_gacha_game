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
