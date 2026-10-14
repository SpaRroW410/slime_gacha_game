"""Terrain: the ground a fight happens on. Every floor of the Hollow Descent (and each day's Gloop Pit) has one.

A terrain changes the fight for BOTH sides:
  * element boosts / dampens - spells of that element hit harder / softer (compound elements use their best/worst
    component, e.g. Lightning is boosted by a Fire or Wind boost),
  * a hazard - every round everyone loses a % of max HP unless they have an immune element (slimes: attuned to it;
    monsters: their own element),
  * a crit bonus.
Terrains belong to a `kind` (valley, dunes, islands ...); monsters name the kinds they live in, so the terrain
decides who shows up. Add one with register_terrain(Terrain(...)).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from . import elements
from .registry import Registry


@dataclass(frozen=True)
class Terrain:
    key: str
    name: str
    kind: str
    emoji: str
    desc: str = ""
    boosts: Dict[str, float] = field(default_factory=dict)       # element -> damage/heal multiplier (> 1)
    dampens: Dict[str, float] = field(default_factory=dict)      # element -> multiplier (< 1)
    hazard_pct: float = 0.0                                        # fraction of max HP lost per round
    hazard_label: str = ""
    hazard_immune: Tuple[str, ...] = ()                            # elements that shrug the hazard off
    crit: float = 0.0


TERRAINS: "Registry[Terrain]" = Registry("terrain")
KINDS = ("valley", "dunes", "islands", "caverns", "tundra", "volcano", "swamp", "canyon", "cliffs", "plains",
         "barrens", "ruins")


def register_terrain(t: Terrain) -> Terrain:
    return TERRAINS.register(t, t.key)


def get(key: str) -> Terrain:
    return TERRAINS.get(key)


def of_kind(kind: str) -> List[Terrain]:
    return [t for t in TERRAINS if t.kind == kind]


def element_factor(t: Terrain, element: str) -> float:
    """Multiplier a terrain applies to an ability of `element` ('' = non-elemental = 1.0)."""
    if t is None or not element:
        return 1.0
    keys = [element] + sorted(elements.components(element))
    up = max([t.boosts.get(k, 1.0) for k in keys])
    down = min([t.dampens.get(k, 1.0) for k in keys])
    return up * down


def describe(t: Terrain) -> str:
    bits = [f"{elements.get(e).name} +{round((m - 1) * 100)}%" for e, m in t.boosts.items()]
    bits += [f"{elements.get(e).name} -{round((1 - m) * 100)}%" for e, m in t.dampens.items()]
    if t.hazard_pct:
        imm = "/".join(elements.get(e).name for e in t.hazard_immune)
        bits.append(f"{t.hazard_label or 'hazard'} {round(t.hazard_pct * 100)}%/round" + (f" (immune: {imm})" if imm else ""))
    if t.crit:
        bits.append(f"crit +{round(t.crit * 100)}%")
    return ", ".join(bits) or "no special effects"


def _t(key, name, kind, emoji, desc, boosts=None, dampens=None, hazard=0.0, label="", immune=(), crit=0.0):
    register_terrain(Terrain(key, name, kind, emoji, desc, boosts or {}, dampens or {}, hazard, label, immune, crit))


# ---- valleys ----
_t("mossy_valley", "Mossy Valley", "valley", "🌿", "Soft hills and fat ferns.", {"earth": 1.10, "wind": 1.10})
_t("echo_valley", "Echo Valley", "valley", "🏞️", "Every shout comes back twice.", {"wind": 1.15}, crit=0.03)
_t("ember_valley", "Ember Valley", "valley", "🔥", "A valley that never stopped smouldering.", {"fire": 1.15}, {"water": 0.90})
_t("fern_gorge", "Fern Gorge", "valley", "🌱", "A narrow gorge, wet and green.", {"water": 1.10, "earth": 1.05})
# ---- dunes ----
_t("dune_sea", "Dune Sea", "dunes", "🏜️", "Endless gold, shimmering heat.", {"fire": 1.15, "earth": 1.05}, {"water": 0.80},
   0.02, "scorching heat", ("fire", "earth"))
_t("glass_desert", "Glass Desert", "dunes", "🔆", "Sand fused to mirrors; light is a weapon.", {"fire": 1.10, "wind": 1.10},
   crit=0.06)
_t("oasis_flats", "Oasis Flats", "dunes", "🌴", "Palm shade and a suspiciously still pond.", {"water": 1.15})
# ---- islands ----
_t("coral_isles", "Coral Isles", "islands", "🏝️", "Warm shallows between sharp coral.", {"water": 1.20}, {"fire": 0.80})
_t("floating_isles", "Floating Isles", "islands", "☁️", "Rocks adrift in a wind that never rests.", {"wind": 1.20},
   {"earth": 0.85}, crit=0.03)
_t("tidal_flats", "Tidal Flats", "islands", "🌊", "The sea keeps coming and going.", {"water": 1.15, "earth": 1.05})
# ---- caverns ----
_t("fungal_caverns", "Fungal Caverns", "caverns", "🍄", "Spores drift in the glow.", {"earth": 1.05}, {},
   0.02, "spore cloud", ("earth", "water"))
_t("glowworm_grotto", "Glowworm Grotto", "caverns", "🪱", "A starry ceiling of glowworms.", {"water": 1.10, "earth": 1.10})
_t("crystal_vault", "Crystal Vault", "caverns", "💠", "Gems hum at a pitch that rattles teeth.", {"earth": 1.15}, crit=0.05)
# ---- tundra ----
_t("frozen_tundra", "Frozen Tundra", "tundra", "❄️", "White to the horizon.", {"water": 1.10, "wind": 1.10}, {"fire": 0.85},
   0.02, "frostbite", ("fire",))
_t("glacier_hall", "Glacier Hall", "tundra", "🧊", "Blue ice, slick as soap.", {"water": 1.20}, {"fire": 0.75}, crit=0.04)
# ---- volcano ----
_t("ashlands", "Ashlands", "volcano", "🌋", "Black ash and red cracks.", {"fire": 1.20}, {"water": 0.75},
   0.02, "choking ash", ("fire", "earth"))
_t("magma_shelf", "Magma Shelf", "volcano", "🔥", "A ledge over a lake of fire.", {"fire": 1.25, "earth": 1.05}, {"water": 0.70},
   0.03, "radiant heat", ("fire",))
# ---- swamp ----
_t("mire", "The Mire", "swamp", "🐊", "Knee-deep, and something is watching.", {"water": 1.10, "earth": 1.10}, {"fire": 0.90},
   0.02, "bog stench", ("water", "earth"))
_t("mangrove_maze", "Mangrove Maze", "swamp", "🌳", "Roots like cages.", {"water": 1.10}, {"wind": 0.90})
# ---- canyon ----
_t("crystal_canyon", "Crystal Canyon", "canyon", "💎", "Walls of living crystal.", {"earth": 1.20}, crit=0.08)
_t("red_mesa", "Red Mesa", "canyon", "⛰️", "Stone shelves under a hot sky.", {"earth": 1.10, "fire": 1.10})
# ---- cliffs ----
_t("sky_cliffs", "Sky Cliffs", "cliffs", "🪽", "A ledge in the clouds.", {"wind": 1.20}, {"earth": 0.85}, crit=0.04)
_t("thunder_peaks", "Thunder Peaks", "cliffs", "🏔️", "Lightning loves the high ground.", {"lightning": 1.25, "wind": 1.10})
# ---- plains ----
_t("storm_plains", "Storm Plains", "plains", "⛈️", "Flat as a plate, and every cloud is angry.",
   {"lightning": 1.25, "water": 1.10}, crit=0.05)
_t("golden_steppe", "Golden Steppe", "plains", "🌾", "Grass to the knees, riders on the wind.", {"wind": 1.10, "earth": 1.05})
# ---- barrens (undead) ----
_t("bone_barrens", "Bone Barrens", "barrens", "💀", "Everything here has been dead a long time.", {"earth": 1.05}, {},
   0.02, "grave chill", ("earth",))
_t("ruined_crypt", "Ruined Crypt", "barrens", "⚰️", "Sarcophagi sealed with something worse than wax.", {}, {"fire": 0.90},
   0.015, "grave chill", ("earth", "wind"), crit=0.04)
# ---- ruins ----
_t("hollow_halls", "Hollow Halls", "ruins", "🏛️", "The Hollow Kings' corridors, cold and empty.")
_t("dust_throne", "The Dust Throne", "ruins", "🪑", "Where the Dry Tide began.", {"fire": 1.10, "earth": 1.10}, {"water": 0.80},
   0.03, "the Dry Tide", ("fire", "earth"), crit=0.05)
