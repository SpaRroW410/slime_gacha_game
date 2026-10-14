"""Elements: four basics (fire, water, earth, wind), combined into new elements via recipes.

Tier 1 = basic. Tier 2 = two basics mixed (fire+wind = lightning). Tier 3 = a tier-2 element mixed with
another element (lightning+fire = plasma). Every element knows its basic COMPONENTS; mastery is tracked per
basic element and the mastery you have in a compound element is your weakest component ("min rule").

Extend: register_element(...) and register_recipe(a, b, result).
Mastery rules (from 3 stars, any class):
  * cap = 2 * (stars - 1)           -> 3* max 4, 4* max 6, 5* max 8
  * attunement slots = stars - 1    -> 3* 2 elements, 4* 3, 5* 4 (mages get +1)
"""
from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Tuple

from . import config
from .registry import Registry


@dataclass(frozen=True)
class Element:
    key: str
    name: str
    emoji: str
    tier: int
    components: FrozenSet[str]          # basic elements it is made of
    parents: Tuple[str, ...] = ()


ELEMENTS: "Registry[Element]" = Registry("element")
RECIPES: Dict[FrozenSet[str], str] = {}
BASICS = ("fire", "water", "earth", "wind")
# attacker beats defender: water > fire > wind > earth > water
BEATS = {"water": "fire", "fire": "wind", "wind": "earth", "earth": "water"}


def register_element(e: Element) -> Element:
    return ELEMENTS.register(e, e.key)


def register_recipe(a: str, b: str, result: str, name: str = "", emoji: str = "✨") -> Element:
    """Define `a + b -> result`. Creates the result element if it doesn't exist yet."""
    ea, eb = ELEMENTS.get(a), ELEMENTS.get(b)
    if result not in ELEMENTS:
        tier = 2 if ea.tier == eb.tier == 1 else 3
        register_element(Element(result, name or result.title(), emoji, tier,
                                 ea.components | eb.components, (a, b)))
    RECIPES[frozenset((a, b))] = result
    return ELEMENTS.get(result)


def get(key: str) -> Element:
    return ELEMENTS.get(key)


def combine(a: str, b: str) -> Optional[Element]:
    r = RECIPES.get(frozenset((a, b)))
    return ELEMENTS.get(r) if r else None


def components(key: str) -> FrozenSet[str]:
    return ELEMENTS.get(key).components if key in ELEMENTS else frozenset()


def effectiveness(attacker: str, defender: str) -> float:
    """Damage multiplier for an attacker element vs a defender element (components decide)."""
    if not attacker or not defender:
        return 1.0
    ac, dc = components(attacker), components(defender)
    adv = any(BEATS.get(a) == d for a in ac for d in dc)
    dis = any(BEATS.get(d) == a for a in ac for d in dc)
    if adv and not dis:
        return config.ELEMENT_ADVANTAGE
    if dis and not adv:
        return config.ELEMENT_DISADVANTAGE
    return 1.0


# ---- mastery rules (functions of a slime's stars/class) ------------------------------------
def can_master(slime) -> bool:
    return slime.stars >= config.MASTERY_MIN_STARS


def mastery_cap(slime) -> int:
    return 2 * (slime.stars - 1) if can_master(slime) else 0


def slot_count(slime) -> int:
    if not can_master(slime):
        return 0
    return min(len(BASICS), slime.stars - 1 + (config.MAGE_SLOT_BONUS if slime.archetype == "mage" else 0))


def level_from_xp(xp: float) -> int:
    return sum(1 for t in config.MASTERY_XP if xp >= t)


def basic_level(slime, basic: str) -> int:
    """Mastery level in one basic element (0 if not attuned)."""
    if basic not in slime.attuned:
        return 0
    return min(mastery_cap(slime), level_from_xp(slime.mastery_xp.get(basic, 0)))


def effective_mastery(levels: Dict[str, int], element: str) -> int:
    """Mastery in any element from per-basic levels: the weakest component wins."""
    comps = components(element)
    return min((levels.get(c, 0) for c in comps), default=0)


def slime_mastery(slime, element: str) -> int:
    return effective_mastery({b: basic_level(slime, b) for b in slime.attuned}, element)


# ---- built-in elements & recipes --------------------------------------------------------------
for _k, _n, _e in [("fire", "Fire", "🔥"), ("water", "Water", "💧"), ("earth", "Earth", "🪨"),
                   ("wind", "Wind", "🌪️")]:
    register_element(Element(_k, _n, _e, 1, frozenset([_k])))

for _a, _b, _r, _n, _e in [
    ("fire", "water", "steam", "Steam", "♨️"), ("fire", "earth", "lava", "Lava", "🌋"),
    ("fire", "wind", "lightning", "Lightning", "⚡"), ("water", "earth", "mud", "Mud", "🟤"),
    ("water", "wind", "ice", "Ice", "❄️"), ("earth", "wind", "sand", "Sand", "🏜️"),
]:
    register_recipe(_a, _b, _r, _n, _e)

for _a, _b, _r, _n, _e in [
    ("lightning", "fire", "plasma", "Plasma", "🔆"), ("lightning", "water", "storm", "Storm", "⛈️"),
    ("lava", "water", "obsidian", "Obsidian", "⚫"), ("lava", "fire", "inferno", "Inferno", "☄️"),
    ("ice", "wind", "blizzard", "Blizzard", "🌨️"), ("ice", "earth", "crystal", "Crystal", "💎"),
    ("sand", "wind", "sandstorm", "Sandstorm", "🌫️"),
]:
    register_recipe(_a, _b, _r, _n, _e)
