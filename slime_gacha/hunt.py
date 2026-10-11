"""HuntSystem: slimes wander off to gather resources while the player does other things."""
import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from . import config
from .errors import InvalidAction
from .growth import add_xp
from .registry import Registry
from .resources import ResourceManager
from .slime import HuntAssignment


@dataclass(frozen=True)
class Zone:
    key: str
    name: str
    duration: int                               # ticks
    danger: float                               # compare to slime power_rating
    rewards: Dict[str, Tuple[int, int]]         # resource -> (lo, hi)
    xp: int = 20
    description: str = ""
    purple_chance: float = 0.0                    # purple gel is rare: chance of +1 on a successful hunt


ZONES: "Registry[Zone]" = Registry("zone")


def register_zone(z: Zone) -> Zone:
    return ZONES.register(z, z.key)


for _z in [
    Zone("meadow", "Sunny Meadow", 3, 15, {"white_gel": (1, 3), "food": (1, 3)}, 15,
         "Gentle hills, fat bugs.", 0.01),
    Zone("grove", "Mushroom Grove", 5, 28, {"white_gel": (2, 5), "food": (2, 5), "essence": (0, 3)}, 30,
         "Glowing fungi. Something giggles.", 0.03),
    Zone("crust", "The Crust Road", 8, 45, {"white_gel": (4, 9), "food": (1, 4), "essence": (2, 8)}, 60,
         "Dry Tide territory. Bring snacks.", 0.08),
]:
    register_zone(_z)

STANCE_LOOT = {"attack": {"white_gel": 1.25}, "explore": {"essence": 1.5},
               "heal": {"white_gel": 0.8, "food": 0.8, "essence": 0.8}}
STANCE_INJURY = {"attack": 1.3, "explore": 1.0, "defend": 0.5, "heal": 0.8}


class HuntSystem:
    def __init__(self, wallet: ResourceManager, rng: random.Random):
        self.wallet = wallet
        self.rng = rng

    def start(self, slime, zone_key: str) -> None:
        zone = ZONES.get(zone_key)
        if slime.state != "idle":
            raise InvalidAction(f"{slime.name} is {slime.state}, not available.")
        if slime.grounded:
            raise InvalidAction(f"{slime.name} is grounded after a brawl. Mediate first.")
        if slime.hp < slime.max_hp * config.MIN_HUNT_HP:
            raise InvalidAction(f"{slime.name} is too wounded to hunt - rest first.")
        if slime.needs.get("energy") < 20:
            raise InvalidAction(f"{slime.name} is too tired to hunt.")
        slime.state = "hunting"
        slime.hunt = HuntAssignment(zone.key, zone.duration, zone.duration)

    def recall(self, slime) -> None:
        if slime.state == "hunting":
            slime.state, slime.hunt = "idle", None

    def tick(self, slimes: List, events: List[str]) -> None:
        for s in slimes:
            if s.state != "hunting" or not s.hunt:
                continue
            s.hunt.ticks_left -= 1
            exhausted = s.needs.get("energy") <= 5
            if s.hunt.ticks_left <= 0 or exhausted:
                self._finish(s, exhausted, events)

    def _finish(self, s, early: bool, events: List[str]) -> None:
        zone = ZONES.get(s.hunt.zone)
        progress = 1.0 - max(0, s.hunt.ticks_left) / s.hunt.total_ticks
        factor = 0.5 * progress if early else 1.0
        s.state, s.hunt = "idle", None
        # success odds: slime power versus zone danger
        ratio = s.power_rating() / zone.danger
        win_p = max(0.1, min(0.97, 0.35 + 0.4 * ratio))
        ok = self.rng.random() < win_p
        stance = s.behavior
        # injury first: a hunt can kill, and the dead bring nothing home
        injury = zone.danger * (0.5 if ok else 1.2) * STANCE_INJURY.get(stance, 1.0) / 10
        s.hp -= max(1, int(injury * self.rng.uniform(0.5, 1.5)))
        if s.hp <= 0:
            s.death_cause = f"killed hunting in {zone.name}"
            events.append(f"☠ {s.name} never returned from {zone.name}...")
            return
        gains: Dict[str, int] = {}
        for res, (lo, hi) in zone.rewards.items():
            amt = self.rng.randint(lo, hi) * factor
            amt *= s.arch.hunt_bonus.get(res, 1.0) * STANCE_LOOT.get(stance, {}).get(res, 1.0)
            amt *= config.RARITY_LOOT_MULT[s.rarity]
            if not ok:
                amt *= 0.3
            amt = int(amt + self.rng.random())          # stochastic rounding keeps small hauls fair
            if amt >= 1:
                gains[res] = amt
        purple_p = zone.purple_chance * (1.5 if stance == "explore" else 1.0) * factor
        if ok and self.rng.random() < purple_p:
            gains["purple_gel"] = 1
        self.wallet.add_many(gains)
        s.needs.add("esteem", 12 if ok else -8)
        xp = int(zone.xp * (1.0 if ok else 0.4) * factor)
        lv = add_xp(s, xp)
        loot = ", ".join(f"{v} {k}" for k, v in gains.items()) or "nothing"
        verb = "returned early" if early else ("returned victorious" if ok else "limped back")
        events.append(f"🏞 {s.name} {verb} from {zone.name}: {loot}, +{xp} XP."
                      + (" 🟣 PURPLE GEL!" if "purple_gel" in gains else ""))
        events.extend(lv)
