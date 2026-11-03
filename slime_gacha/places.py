"""Named dungeons as data. Every place a party can go is a `Place`: add one with register_place(...) or load a JSON
file of definitions with load_json(path) - an "expedition" place needs no code (it runs the same wave rules as the
Rift and Quarry: any 1-5 slimes, monsters a level above them, nobody dies).

  drop   "relics"  Rift-style relic finds        "stones"  ascension stones         "loot"  the place's own `loot` table
  loot   {resource: [chance per foe, min, max]}
"""
import json
from dataclasses import dataclass, field
from typing import Dict, Tuple

from . import config
from .registry import Registry


@dataclass(frozen=True)
class Place:
    key: str                      # also the slime's `in_dungeon` flag while inside
    name: str
    emoji: str
    kind: str = "expedition"      # descent | pit | expedition (data-driven) | job (a flag only)
    blurb: str = ""
    salt: int = 0                 # seeds the place's daily theme
    xp_mult: float = 0.2
    drop: str = "loot"
    loot: Dict[str, Tuple[float, int, int]] = field(default_factory=dict)
    herb: float = 0.0             # chance of a herb per foe
    dilation: float = 1.0         # dungeon hours that pass per lobby hour while a party is here (1 = no dilation)

    @property
    def title(self) -> str:
        return f"{self.emoji} {self.name}"


PLACES: "Registry[Place]" = Registry("place")


def register_place(p: Place) -> Place:
    return PLACES.register(p, p.key)


def place_from_dict(d: dict) -> Place:
    return Place(key=d["key"], name=d["name"], emoji=d.get("emoji", "🕳"), kind=d.get("kind", "expedition"),
                 blurb=d.get("blurb", ""), salt=int(d.get("salt", sum(map(ord, d["key"])))), xp_mult=float(d.get("xp_mult", 0.2)),
                 drop=d.get("drop", "loot"), loot={k: tuple(v) for k, v in d.get("loot", {}).items()}, herb=float(d.get("herb", 0)),
                 dilation=float(d.get("dilation", 3.0 if d.get("kind", "expedition") == "expedition" else 1.0)))


def load_json(path: str) -> int:
    """Register every place in a JSON list; returns how many."""
    with open(path, encoding="utf-8") as f:
        defs = json.load(f)
    for d in defs:
        register_place(place_from_dict(d))
    return len(defs)


# Each place sets its own dilation (dungeon hours per lobby hour) - change one number to retune one place. Hunting and foraging are not
# places and stay on lobby time; so do the home flags below.
register_place(Place("main", "Hollow Descent", "🕳", "descent", "Fifty floors, a boss every ten.", dilation=3.0))
register_place(Place("grind", "Gloop Pit", "🫧", "pit", "Daily-themed XP farm; nobody dies.", herb=config.HERB_DROP.get("grind", 0), dilation=3.0))
register_place(Place("adventure", "Wayfarer's Rift", "🧭", "expedition", "Relics for the vault.", 0xA11, config.ADV_XP_MULT, "relics",
                     herb=config.HERB_DROP.get("adventure", 0), dilation=3.0))
register_place(Place("quarry", "Starfall Quarry", "💎", "expedition", "Ascension stones.", 0x57A, config.QUARRY_XP_MULT, "stones",
                     herb=config.HERB_DROP.get("quarry", 0), dilation=3.0))
register_place(Place("mossy_burrows", "Mossy Burrows", "🍄", "expedition",
                     "Damp tunnels where fat critters guard food and a little essence.", 0xB07, 0.25, "loot",
                     loot={"food": (0.5, 1, 3), "essence": (0.15, 1, 2)}, herb=0.2, dilation=3.0))
for _k, _n, _e, _d in [("scout", "Scouting", "🔭", 1.0),      # scouting budgets stay in lobby hours (no balance work wanted there)
                       ("rescue", "Rescue mission", "🛟", 3.0), ("wave", "Wave simulation", "🧪", 3.0),
                       ("stranded", "Stranded", "🆘", 1.0),     # waiting for rescue: the 24-hour deadline assumes lobby-rate hunger
                       ("train", "Training Grounds", "🥊", 1.0), ("lab", "Alchemy Lab", "⚗️", 1.0)]:
    register_place(Place(_k, _n, _e, "job", dilation=_d))


def dilation(kind: str) -> float:
    """Dungeon hours per lobby hour for a slime flagged `kind` (1.0 for no flag or an unknown one)."""
    return PLACES.get(kind).dilation if kind and kind in PLACES else 1.0


def away_kinds() -> Tuple[str, ...]:
    """Flags that keep a slime out of the colony and are cleared when a save is restored without their session."""
    return tuple(p.key for p in PLACES if p.kind in ("descent", "pit", "expedition")) + ("scout", "stranded")


def session_kinds() -> Tuple[str, ...]:
    """Flags of short sessions: a restored save without the session's record frees these slimes."""
    return tuple(p.key for p in PLACES if p.kind in ("pit", "expedition")) + ("scout", "rescue", "wave")
