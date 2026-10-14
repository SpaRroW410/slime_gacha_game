"""Upgradable colony buildings. Each building has levels 1..max; upgrading costs gel/essence.

  Rest Area        heals slimes (down to 1 HP in a spar -> back to full here): capacity + healing speed
  Training Grounds sparring: fighting-style level cap and style XP bonus
  Library          study speed, research odds, extra spell slots, and the Restricted Section (tier-3 spells)
  Barracks         morale recovery, bond growth and party synergy

Effects are plain functions of the level on BuildingManager so other systems just ask
`buildings.rest_capacity()` etc. Add a building: register_building(Building(...)) and add an effect getter.
"""
from dataclasses import dataclass
from typing import Dict, List

from . import ascension, config
from .errors import InvalidAction
from .registry import Registry
from .resources import ResourceManager


@dataclass(frozen=True)
class Building:
    key: str
    name: str
    emoji: str
    max_level: int
    description: str
    upgrade_costs: List[Dict[str, int]]       # cost to go from level i+1 to i+2
    start_level: int = 1


BUILDINGS: "Registry[Building]" = Registry("building")


def register_building(b: Building) -> Building:
    assert len(b.upgrade_costs) == b.max_level - 1, "need one cost per upgrade"
    return BUILDINGS.register(b, b.key)


def _costs(white: int, essence: int, purple_from: int = 4) -> List[Dict[str, int]]:
    out = []
    for lvl in range(1, 5):                      # upgrades 1->2 ... 4->5
        c = {"white_gel": int(white * lvl ** 1.7)}
        if lvl >= 2:
            c["essence"] = int(essence * lvl ** 1.5)
        if lvl >= purple_from:
            c["purple_gel"] = lvl - 2
        out.append(c)
    return out


register_building(Building("rest_area", "Rest Area", "🛏️", 5,
                           "A warm pond where wounded slimes soak back to full health.", _costs(60, 10)))
register_building(Building("training_grounds", "Training Grounds", "🥋", 5,
                           "Arenas for sparring. Higher levels teach deeper fighting styles.", _costs(80, 12)))
register_building(Building("library", "Library", "📚", 5,
                           "Spells, elements and the Restricted Section.", _costs(100, 15)))
register_building(Building("barracks", "Barracks", "🏕️", 5,
                           "Bunks, songs and a very shared fridge: morale, bonds and party synergy.", _costs(90, 10)))

register_building(Building("armory", "Armory", "🛠️", 5,
                           "Forges gear. Higher levels stock better equipment tiers.", _costs(70, 10)))

register_building(Building("chamber", "Destruction Chamber", "🔥", 5,
                           "Breaks slimes down into gel and ascension stones. Higher levels yield more.", _costs(90, 12)))

register_building(Building("alchemy", "Alchemy Lab", "⚗️", 5,
                           "Slimes brew potions here. The lab level caps the potion grade (1-5).", _costs(85, 12)))

REST_HEAL = [0.30, 0.45, 0.60, 0.80, 1.00]       # fraction of max HP healed per hour, by level


class BuildingManager:
    def __init__(self, wallet: ResourceManager):
        self.wallet = wallet
        self.levels: Dict[str, int] = {b.key: b.start_level for b in BUILDINGS}

    # ---- generic ---------------------------------------------------------------
    def level(self, key: str) -> int:
        return self.levels.get(key, BUILDINGS.get(key).start_level)

    def next_cost(self, key: str):
        b, lv = BUILDINGS.get(key), self.level(key)
        return None if lv >= b.max_level else dict(b.upgrade_costs[lv - 1])

    def upgrade(self, key: str) -> str:
        b = BUILDINGS.get(key)
        cost = self.next_cost(key)
        if cost is None:
            raise InvalidAction(f"{b.name} is already at its maximum level ({b.max_level}).")
        self.wallet.spend_many(cost)
        self.levels[key] = self.level(key) + 1
        return f"{b.emoji} {b.name} upgraded to level {self.levels[key]}!"

    def describe(self, key: str, level: int = None) -> str:
        lv = level or self.level(key)
        return {
            "rest_area": lambda: f"holds {self.rest_capacity(lv)} slimes, heals {int(REST_HEAL[lv - 1] * 100)}% HP/hour",
            "training_grounds": lambda: f"style level cap {self.style_cap(lv)}, style XP x{self.style_mult(lv):.2f}",
            "library": lambda: (f"study x{self.study_mult(lv):.2f}, research +{int(self.research_bonus(lv) * 100)}%, "
                                f"{config.MAX_SPELLS + self.extra_spell_slots(lv)} spell slots"
                                f"{', Restricted Section open' if self.tier3_open(lv) else ''}"),
            "chamber": lambda: f"destroyed slimes yield x{ascension.chamber_factor(lv):.1f}",
            "alchemy": lambda: f"brews potions up to grade {lv}",
            "armory": lambda: f"sells gear up to tier {self.gear_tier(lv)}",
            "barracks": lambda: (f"morale +{self.morale_target_bonus(lv)}, drift {self.morale_drift(lv):.2f}/h, "
                                 f"bonds x{self.bond_mult(lv):.2f}, synergy x{self.synergy_mult(lv):.2f}"),
        }.get(key, lambda: BUILDINGS.get(key).description)()

    # ---- Rest Area ---------------------------------------------------------------
    def rest_capacity(self, lv: int = None) -> int:
        return 5 * (lv or self.level("rest_area"))

    def rest_heal(self, lv: int = None) -> float:
        return REST_HEAL[(lv or self.level("rest_area")) - 1]

    # ---- Training Grounds ----------------------------------------------------------
    def style_cap(self, lv: int = None) -> int:
        return min(len(config.STYLE_XP), 2 + 2 * (lv or self.level("training_grounds")))

    def style_mult(self, lv: int = None) -> float:
        return 1 + 0.15 * ((lv or self.level("training_grounds")) - 1)

    # ---- Library -----------------------------------------------------------------------
    def study_mult(self, lv: int = None) -> float:
        return 1 + 0.15 * ((lv or self.level("library")) - 1)

    def research_bonus(self, lv: int = None) -> float:
        return 0.04 * ((lv or self.level("library")) - 1)

    def extra_spell_slots(self, lv: int = None) -> int:
        return ((lv or self.level("library")) - 1) // 2

    def tier3_open(self, lv: int = None) -> bool:
        return (lv or self.level("library")) >= 3

    # ---- Barracks ------------------------------------------------------------------------
    def morale_target_bonus(self, lv: int = None) -> int:
        return 2 * (lv or self.level("barracks"))

    def morale_drift(self, lv: int = None) -> float:
        return config.MORALE_DRIFT + 0.02 * ((lv or self.level("barracks")) - 1)

    def bond_mult(self, lv: int = None) -> float:
        return 1 + 0.25 * ((lv or self.level("barracks")) - 1)

    def synergy_mult(self, lv: int = None) -> float:
        return 1 + 0.2 * ((lv or self.level("barracks")) - 1)

    # ---- Armory ----------------------------------------------------------------------------
    def gear_tier(self, lv: int = None) -> int:
        return min(3, 1 + ((lv or self.level("armory")) - 1) // 2)

    # ---- persistence ---------------------------------------------------------------------
    def to_dict(self) -> Dict[str, int]:
        return dict(self.levels)

    def load(self, d: Dict[str, int]) -> None:
        for k, v in (d or {}).items():
            if k in BUILDINGS:
                self.levels[k] = max(1, min(int(v), BUILDINGS.get(k).max_level))


def rest_tick(slimes: List, buildings: BuildingManager, events: List[str]) -> None:
    """Slimes in the Rest Area recover a share of max HP per hour; they leave once healed and rested."""
    for s in slimes:
        if s.state != "resting" or not s.alive:
            continue
        if s.needs.get("food") > 0:                       # a starving slime cannot heal
            s.hp = min(s.max_hp, s.hp + max(1, int(round(s.max_hp * buildings.rest_heal()))))
        s.needs.add("energy", config.REST_ENERGY_GAIN)
        s.morale = min(100.0, s.morale + 2 + buildings.level("rest_area"))
        if s.needs.get("food") <= 0:                      # hungry slimes get kicked out to find food
            s.state = "idle"
            events.append(f"{s.name} leaves the Rest Area - too hungry to heal!")
        elif s.hp >= s.max_hp and s.needs.get("energy") >= config.AUTO_WAKE_AT:
            s.state = "idle"
            events.append(f"🛏️ {s.name} leaves the Rest Area fully healed.")
