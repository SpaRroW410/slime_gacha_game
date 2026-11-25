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


MAX_LEVEL = 10                                   # every building climbs to level 10 (levels 6-10 grow at half the early pace)


def _costs(white: int, essence: int, purple_from: int = 4) -> List[Dict[str, int]]:
    out = []
    for lvl in range(1, MAX_LEVEL):              # upgrades 1->2 ... 9->10
        c = {"white_gel": int(white * lvl ** 1.7)}
        if lvl >= 2:
            c["essence"] = int(essence * lvl ** 1.5)
        if lvl >= purple_from:
            c["purple_gel"] = lvl - 2
        out.append(c)
    return out


register_building(Building("rest_area", "Rest Area", "🛏️", MAX_LEVEL,
                           "A warm pond where wounded slimes soak back to full health.", _costs(60, 10)))
register_building(Building("training_grounds", "Training Grounds", "🥋", MAX_LEVEL,
                           "Arenas for sparring. Higher levels teach deeper fighting styles.", _costs(80, 12)))
register_building(Building("library", "Library", "📚", MAX_LEVEL,
                           "Spells, elements and the Restricted Section.", _costs(100, 15)))
register_building(Building("barracks", "Barracks", "🏕️", MAX_LEVEL,
                           "Bunks, songs and a very shared fridge: morale, bonds and party synergy.", _costs(90, 10)))

register_building(Building("hatchery", "Hatchery", "🥚", MAX_LEVEL,
                           "Where new slimes hatch: each level above 1 hands back a share of the gel you spend on pulls.", _costs(95, 12)))
register_building(Building("armory", "Armory", "🛠️", MAX_LEVEL,
                           "Forges gear. Higher levels stock better equipment tiers.", _costs(70, 10)))
register_building(Building("reliquary", "Reliquary", "🗝️", MAX_LEVEL,
                           "Where relics are mended, ascended and reforged. A relic's next star needs the Reliquary at least as high as its stars; "
                           "raising its rarity needs level 3 (uncommon), 5 (rare), 8 (epic) or 10 (legendary).", _costs(80, 12)))

register_building(Building("chamber", "Destruction Chamber", "🔥", MAX_LEVEL,
                           "Breaks slimes down into gel and ascension stones. Higher levels yield more.", _costs(90, 12)))

register_building(Building("alchemy", "Alchemy Lab", "⚗️", MAX_LEVEL,
                           "Slimes brew potions here. The lab level caps the potion grade (1-5).", _costs(85, 12)))

register_building(Building("hospital", "Hospital", "🏥", MAX_LEVEL,
                           "Wards for the injured: a medic doctor heals everyone hurt at home. Level sets the places and the healing.", _costs(80, 12)))
register_building(Building("kitchen", "Kitchen", "🍳", MAX_LEVEL,
                           "A warm hearth where chefs cook: places for chefs and better meals.", _costs(75, 10)))
register_building(Building("cold_storage", "Cold Storage", "❄️", MAX_LEVEL,
                           "An ice cellar that keeps cooked dishes fresh: a bigger pantry, finer dishes the chef can make, and dishes parties "
                           "can carry on their trips (better than raw rations).", _costs(70, 10)))

# Training and sparring facilities: each has its own building, and its level sets how many slimes can use it at once.
register_building(Building("blade_yard", "Blade Yard", "⚔️", MAX_LEVEL, "Drill yard for sword classes: a bigger yard trains more slimes at once.", _costs(70, 10)))
register_building(Building("archery_range", "Archery Range", "🏹", MAX_LEVEL, "Drill yard for rangers: a bigger range trains more slimes at once.", _costs(70, 10)))
register_building(Building("mana_pool", "Mana Pool", "🔮", MAX_LEVEL, "Drill pool for casters: a bigger pool trains more slimes at once.", _costs(70, 10)))
register_building(Building("party_yard", "Party Training Yard", "🛡️", MAX_LEVEL, "A training yard for a whole party: everyone drills in their own field side by side, and the party grows closer. Each level holds one more party. Costs more than the single yards.",
                           _costs(160, 25, purple_from=4)))
register_building(Building("spar_sword", "Sword Arena", "🗡️", MAX_LEVEL, "Duelling ring for the sword style: a bigger ring holds more duels at once.", _costs(90, 12)))
register_building(Building("spar_archery", "Archery Arena", "🎯", MAX_LEVEL, "Duelling ring for the archery style: a bigger ring holds more duels at once.", _costs(90, 12)))
register_building(Building("spar_magic", "Spell Arena", "🪄", MAX_LEVEL, "Duelling ring for the magic style: a bigger ring holds more duels at once.", _costs(90, 12)))
register_building(Building("spar_party", "Party Arena", "🏟️", MAX_LEVEL, "A grand arena where whole parties spar as teams: each level holds one more team match at once. Costly to build.",
                           _costs(260, 40, purple_from=3)))

# which building serves which discipline (sword / archery / magic) for drills and for duels; party sparring has its own
DRILL_YARDS = {"sword": "blade_yard", "archery": "archery_range", "magic": "mana_pool"}
SPAR_ARENAS = {"sword": "spar_sword", "archery": "spar_archery", "magic": "spar_magic"}
PARTY_ARENA = "spar_party"
PARTY_YARD = "party_yard"          # a fourth training yard: a whole party trains side by side, everyone for themselves
FACILITIES = list(DRILL_YARDS.values()) + [PARTY_YARD] + list(SPAR_ARENAS.values()) + [PARTY_ARENA]

JOB_HOSTS = {"kitchen": "Chef", "armory": "Blacksmith", "reliquary": "Relicsmith", "library": "Librarian", "training_grounds": "Trainers", "alchemy": "Brewer", "hospital": "Doctor"}

REST_HEAL = [config.SLEEP_HP_REGEN] * MAX_LEVEL            # HP heals at the base sleeping rate at every level (energy is what the Rest Area improves)


def _taper(lv: int) -> float:
    """Steps above level 1, counting levels 6-10 as half steps (so the late levels add less than the early ones)."""
    lv = max(1, int(lv))
    return min(lv - 1, 4) + 0.5 * max(0, lv - 5)


class BuildingManager:
    def __init__(self, wallet: ResourceManager):
        self.wallet = wallet
        self.levels: Dict[str, int] = {b.key: b.start_level for b in BUILDINGS}
        self.discount = 0.0              # Keeper skill (Thrifty)

    # ---- generic ---------------------------------------------------------------
    def level(self, key: str) -> int:
        return self.levels.get(key, BUILDINGS.get(key).start_level)

    def next_cost(self, key: str):
        b, lv = BUILDINGS.get(key), self.level(key)
        if lv >= b.max_level:
            return None
        return {k: max(1, int(v * (1 - self.discount))) for k, v in b.upgrade_costs[lv - 1].items()}

    def pay(self, key: str) -> None:
        b = BUILDINGS.get(key)
        cost = self.next_cost(key)
        if cost is None:
            raise InvalidAction(f"{b.name} is already at its maximum level ({b.max_level}).")
        self.wallet.spend_many(cost)

    def build_hours(self, key: str) -> int:
        return config.CONSTRUCTION_HOURS[self.level(key) - 1]

    def hatch_refund(self, lv: int = None) -> float:
        return config.HATCHERY_REFUND * _taper(lv or self.level("hatchery"))

    def upgrade(self, key: str) -> str:
        b = BUILDINGS.get(key)
        self.pay(key)
        self.levels[key] = self.level(key) + 1
        return f"{b.emoji} {b.name} upgraded to level {self.levels[key]}!"

    def upgrade_free(self, key: str) -> str:
        b = BUILDINGS.get(key)
        self.levels[key] = min(b.max_level, self.level(key) + 1)
        return f"{b.emoji} {b.name} upgraded to level {self.levels[key]}!"

    def describe(self, key: str, level: int = None) -> str:
        lv = level or self.level(key)
        base = {
            "rest_area": lambda: f"holds {self.rest_capacity(lv)} slimes, restores {config.REST_ENERGY[lv - 1]} energy/hour (HP heals at the normal rate)",
            "training_grounds": lambda: f"style level cap {self.style_cap(lv)}, style XP x{self.style_mult(lv):.2f}",
            "library": lambda: (f"study x{self.study_mult(lv):.2f}, research +{int(self.research_bonus(lv) * 100)}%, "
                                f"{config.MAX_SPELLS + self.extra_spell_slots(lv)} spell slots"
                                f"{', Restricted Section open' if self.tier3_open(lv) else ''}"),
            "chamber": lambda: f"destroyed slimes yield x{ascension.chamber_factor(lv):.1f}",
            "alchemy": lambda: f"brews potions up to grade {min(lv, 5)}" + (f", better odds (+{(lv - 5) * 5}%)" if lv > 5 else ""),
            "hatchery": lambda: f"{round(self.hatch_refund(lv) * 100, 1):g}% of the gel of every pull comes back",
            **{k: (lambda lv=lv: f"trains {2 * lv} slimes at once") for k in DRILL_YARDS.values()},
            **{k: (lambda lv=lv: f"{lv} duel{'s' if lv > 1 else ''} at once ({2 * lv} slimes)") for k in SPAR_ARENAS.values()},
            PARTY_YARD: lambda: f"trains {lv} part{'ies' if lv > 1 else 'y'} at once",
            PARTY_ARENA: lambda: f"{lv} team match{'es' if lv > 1 else ''} at once ({lv} x 2 parties)",
            "kitchen": lambda: f"pantry holds {config.PANTRY_PER_LEVEL * lv} servings",
            "cold_storage": lambda: (f"+{config.COLD_SERVINGS_PER_LEVEL * lv} pantry servings, parties carry up to {config.COLD_PACK_PER_LEVEL * lv} "
                                     f"dishes a trip" + (", Smoked Fish Platter" if lv >= 2 else "") + (", Royal Banquet" if lv >= 4 else "")),
            "hospital": lambda: f"{config.HOSPITAL_BEDS[lv - 1]} ward beds (patients heal +{int(config.WARD_NO_DOCTOR_BONUS * 100)}%, +{int(config.WARD_DOCTOR_BONUS * 100)}% with a doctor); a doctor heals the injured at home {int(config.HOSPITAL_HEAL[lv - 1] * 100)}% HP/hour",
            "armory": lambda: f"sells gear up to tier {self.gear_tier(lv)}",
            "reliquary": lambda: f"relics ascend to {min(5, lv + 1)} stars, rarity up to {self.relic_rarity_max(lv) or 'none yet (level 3: uncommon)'}",
            "barracks": lambda: (f"morale +{self.morale_target_bonus(lv)}, drift {self.morale_drift(lv):.2f}/h, "
                                 f"bonds x{self.bond_mult(lv):.2f}, synergy x{self.synergy_mult(lv):.2f}"),
        }.get(key, lambda: BUILDINGS.get(key).description)()
        if key in JOB_HOSTS:
            n = 3 if key == "training_grounds" else self.job_slots(key, lv)
            base += f" · {n} {JOB_HOSTS[key].lower()} place{'s' if n > 1 else ''}, posts x{self.job_mult(key, lv):.1f}"
        return base

    def job_slots(self, key: str, lv: int = None) -> int:
        """Slimes that can work at once in this building (see jobs.py): one per building level."""
        return lv or self.level(key)

    def job_mult(self, key: str, lv: int = None) -> float:
        return 1 + 0.1 * ((lv or self.level(key)) - 1)

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
        return int(2 + 2 * _taper(lv or self.level("barracks")))

    def morale_drift(self, lv: int = None) -> float:
        return config.MORALE_DRIFT + 0.02 * ((lv or self.level("barracks")) - 1)

    def bond_mult(self, lv: int = None) -> float:
        return 1 + 0.25 * _taper(lv or self.level("barracks"))

    def synergy_mult(self, lv: int = None) -> float:
        return 1 + 0.2 * _taper(lv or self.level("barracks"))

    # ---- Armory ----------------------------------------------------------------------------
    def gear_tier(self, lv: int = None) -> int:
        """Levels 1-2 sell tier 1, 3-4 tier 2, 5-6 tier 3, 7-8 tier 4 and 9-10 tier 5."""
        return min(5, 1 + ((lv or self.level("armory")) - 1) // 2)

    # ---- Reliquary ----------------------------------------------------------------------------
    def relic_rarity_max(self, lv: int = None) -> str:
        """The highest rarity a relic can be raised to at this Reliquary level ('' = none yet)."""
        lv = lv or self.level("reliquary")
        ok = [r for r, need in config.RELIC_RARITY_LEVEL.items() if lv >= need]
        return ok[-1] if ok else ""

    # ---- persistence ---------------------------------------------------------------------
    def to_dict(self) -> Dict[str, int]:
        return dict(self.levels)

    def load(self, d: Dict[str, int]) -> None:
        for k, v in (d or {}).items():
            if k in BUILDINGS:
                self.levels[k] = max(1, min(int(v), BUILDINGS.get(k).max_level))


def rest_tick(slimes: List, buildings: BuildingManager, events: List[str], ward=(), doctor_on: bool = False) -> None:
    """Slimes in the Rest Area recover a share of max HP per hour; they leave once healed and rested. Patients in the
    Hospital ward heal faster than in the Rest Area (a little with nobody on duty, much more with a doctor) and leave once healed."""
    for s in slimes:
        if s.state != "resting" or not s.alive:
            continue
        if s.id in ward:
            bonus = config.WARD_DOCTOR_BONUS if doctor_on else config.WARD_NO_DOCTOR_BONUS
            if s.needs.get("food") > 0:
                s.hp = min(s.max_hp, s.hp + max(1, int(round(s.max_hp * buildings.rest_heal() * (1 + bonus)))))
            s.needs.add("energy", config.REST_ENERGY[0])
            s.morale = min(100.0, s.morale + 2)
            if s.needs.get("food") <= 0:
                s.state = "idle"
                events.append(f"{s.name} leaves the Hospital - too hungry to heal!")
            elif s.hp >= s.max_hp:
                s.state = "idle"
                events.append(f"🏥 {s.name} leaves the Hospital fully healed.")
            continue
        if s.needs.get("food") > 0:                       # a starving slime cannot heal
            s.hp = min(s.max_hp, s.hp + max(1, int(round(s.max_hp * buildings.rest_heal()))))
        s.needs.add("energy", config.REST_ENERGY[buildings.level("rest_area") - 1])
        s.morale = min(100.0, s.morale + 2 + buildings.level("rest_area"))
        if s.needs.get("food") <= 0:                      # hungry slimes get kicked out to find food
            s.state = "idle"
            events.append(f"{s.name} leaves the Rest Area - too hungry to heal!")
        elif s.hp >= s.max_hp and s.needs.get("energy") >= config.AUTO_WAKE_AT:
            s.state = "idle"
            events.append(f"🛏️ {s.name} leaves the Rest Area fully healed.")
