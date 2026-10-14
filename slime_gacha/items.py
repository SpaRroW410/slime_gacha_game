"""Relics: unique, levelling, breakable equipment found in the Wayfarer's Rift (the adventure dungeon).

An Item has a base type, a RARITY (common..legendary, like slimes), STARS 1-5, a LEVEL 1-10 inside each star, a
DURABILITY (it wears out and shatters into crafting materials), MODS (crit rate, crit damage, elemental damage,
lifesteal) and a COMPATIBILITY with whoever wields it.

Growth: spend materials of the item's own tier (scrap / alloy / crystal / stardust, from salvaging relics - the
higher the level, the better the yield) to level up; at level 10 you may ASCEND a star; at 5 stars and level 10
the RARITY can be raised, which also adds a mod. A 5-star legendary relic fused with a 5-star legendary slime
becomes an EGO relic, wieldable only by 5-star legendary slimes.

Extend: register_base(Base(...)).
"""
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import config
from .errors import InvalidAction
from .registry import Registry

SLOTS = ("weapon", "armor", "charm")
MOD_KINDS = tuple(config.ITEM_MOD_RANGE)
ELEMENTS = ("fire", "water", "earth", "wind")
MOD_LABEL = {"crit_rate": "Crit rate", "crit_dmg": "Crit damage", "elem_dmg": "Elemental damage",
             "lifesteal": "Lifesteal"}


@dataclass(frozen=True)
class Base:
    key: str
    name: str
    emoji: str
    slot: str
    stats: Dict[str, float]
    fits: Tuple[str, ...]          # classes that wield it naturally (compatibility)


BASES: "Registry[Base]" = Registry("item base")


def register_base(b: Base) -> Base:
    assert b.slot in SLOTS
    return BASES.register(b, b.key)


for _b in [
    Base("iron_sword", "Iron Sword", "🗡️", "weapon", dict(atk=5, spd=1), ("barbarian", "rogue")),
    Base("war_hammer", "War Hammer", "🔨", "weapon", dict(atk=7, hp=4), ("barbarian",)),
    Base("bone_dagger", "Bone Dagger", "🔪", "weapon", dict(atk=4, spd=4), ("rogue", "necromancer")),
    Base("hunters_bow", "Hunter's Bow", "🏹", "weapon", dict(atk=4, spd=3), ("ranger", "rogue")),
    Base("oak_staff", "Oak Staff", "🪄", "weapon", dict(mag=5, hp=3), ("mage", "medic")),
    Base("spell_tome", "Spell Tome", "📖", "weapon", dict(mag=4, spd=2), ("mage", "necromancer")),
    Base("padded_vest", "Padded Vest", "🧥", "armor", dict(defense=3, hp=8), ("rogue", "ranger", "medic")),
    Base("chain_shell", "Chain Shell", "🛡️", "armor", dict(defense=5, hp=5), ("barbarian",)),
    Base("thread_robe", "Robe of Threads", "👘", "armor", dict(defense=2, mag=3, hp=6),
         ("mage", "medic", "necromancer")),
    Base("lucky_fang", "Lucky Fang", "🦷", "charm", dict(atk=2, spd=2), ("rogue", "ranger", "barbarian")),
    Base("mana_bead", "Mana Bead", "🔮", "charm", dict(mag=3, hp=4), ("mage", "necromancer", "medic")),
    Base("heartroot", "Heartroot", "🌱", "charm", dict(hp=14, defense=1), ("medic", "barbarian")),
]:
    register_base(_b)

RARITIES = config.RARITIES


def material(rarity: str) -> str:
    return config.MATERIAL_OF[rarity]


def next_rarity(rarity: str) -> Optional[str]:
    i = RARITIES.index(rarity)
    return RARITIES[i + 1] if i + 1 < len(RARITIES) else None


class Item:
    def __init__(self, uid: int, base: str, rarity: str = "common", stars: int = 1, level: int = 1,
                 mods: Optional[List[dict]] = None):
        BASES.get(base)
        self.uid = uid
        self.base = base
        self.rarity = rarity
        self.stars = stars
        self.level = level
        self.mods: List[dict] = mods or []
        self.ego: Optional[dict] = None            # {"name", "level", "archetype"} of the sacrificed soul
        self.bond = 0                               # battles fought with the current wielder (cap 40)
        self.durability = self.max_durability

    # ---- look ---------------------------------------------------------------
    @property
    def spec(self) -> Base:
        return BASES.get(self.base)

    @property
    def slot(self) -> str:
        return self.spec.slot

    @property
    def name(self) -> str:
        tag = "Ego " if self.ego else ""
        return f"{tag}{self.spec.name}"

    @property
    def max_durability(self) -> int:
        return 10**6 if self.ego else (config.ITEM_DURABILITY + 10 * self.stars + 10 * RARITIES.index(self.rarity))

    @property
    def unbreakable(self) -> bool:
        return bool(self.ego)

    def label(self) -> str:
        r = config.RARITY_TAG[self.rarity]
        return f"{self.spec.emoji}{self.name} [{r}]{'★' * self.stars}{'☆' * (config.MAX_STARS - self.stars)} Lv{self.level}"

    # ---- numbers ------------------------------------------------------------
    def power_mult(self) -> float:
        m = config.ITEM_RARITY_MULT[self.rarity] * config.ITEM_STAR_MULT[self.stars - 1] * \
            (1 + config.ITEM_LEVEL_STEP * (self.level - 1))
        if self.ego:
            m *= config.EGO_BASE_MULT + config.EGO_LEVEL_MULT * self.ego.get("level", 1)
        return m

    def base_stats(self) -> Dict[str, float]:
        m = self.power_mult()
        return {k: round(v * m, 1) for k, v in self.spec.stats.items()}

    def mod_scale(self) -> float:
        return 2.0 if self.ego else 1.0

    # ---- compatibility with a wielder ---------------------------------------
    def compat(self, slime) -> int:
        """0..100: class fit, matching elements, a stable personal chemistry and the bond built by fighting."""
        score = 25
        score += 30 if slime.archetype in self.spec.fits else 0
        elems = {m.get("element") for m in self.mods if m["kind"] == "elem_dmg"}
        if elems & set(slime.attuned):
            score += 15
        score += (hash((slime.id * 7919 + self.uid * 104729) % 1009) % 31) - 8        # -8..+22 chemistry
        score += min(20, self.bond // 2)
        return max(0, min(100, int(score)))

    def compat_mult(self, slime) -> float:
        lo, hi = config.ITEM_COMPAT_MIN, config.ITEM_COMPAT_MAX
        return lo + (hi - lo) * self.compat(slime) / 100

    def stats_for(self, slime) -> Dict[str, float]:
        k = self.compat_mult(slime)
        return {s: round(v * k, 1) for s, v in self.base_stats().items()}

    # ---- wear ---------------------------------------------------------------
    @property
    def broken(self) -> bool:
        return self.durability <= 0

    def wear(self, n: int = 1) -> bool:
        """Lose durability; returns True when the item just shattered."""
        if self.unbreakable:
            return False
        self.durability = max(0, self.durability - n)
        return self.durability <= 0

    def repair_cost(self) -> int:
        missing = self.max_durability - self.durability
        return 0 if self.unbreakable else math.ceil(missing / 4) * (1 + RARITIES.index(self.rarity))

    # ---- growth costs -------------------------------------------------------
    def level_cost(self) -> Dict[str, int]:
        n = self.level
        return {material(self.rarity): math.ceil((2 + n) * (1 + 0.5 * (self.stars - 1))), "white_gel": 5 * n}

    def star_cost(self) -> Dict[str, int]:
        c = {material(self.rarity): config.ITEM_ASCEND_STAR * self.stars, "white_gel": 25 * self.stars}
        up = next_rarity(self.rarity)
        if up:
            c[material(up)] = self.stars
        return c

    def rarity_cost(self) -> Dict[str, int]:
        up = next_rarity(self.rarity) or self.rarity
        c = {material(self.rarity): config.ITEM_ASCEND_RARITY, "purple_gel": 2 + RARITIES.index(self.rarity),
             "essence": 20}
        c[material(up)] = c.get(material(up), 0) + 25
        return c

    def grade(self) -> int:
        return (self.stars - 1) * config.ITEM_MAX_LEVEL + self.level

    def salvage_yield(self, broken: bool = False) -> Dict[str, int]:
        """Better, higher-level relics break into more - and one tier better - materials."""
        g = self.grade() + 10 * RARITIES.index(self.rarity)
        out = {material(self.rarity): config.ITEM_SALVAGE_BASE + g // 2}
        up = next_rarity(self.rarity)
        if up and self.grade() >= 12:
            out[material(up)] = self.grade() // 12
        if broken:
            out = {k: max(1, v // 2) for k, v in out.items()}
        return out

    # ---- describe / persist -------------------------------------------------
    def mod_text(self, m: dict) -> str:
        v = m["value"] * self.mod_scale()
        el = f" ({m['element']})" if m.get("element") else ""
        return f"{MOD_LABEL[m['kind']]}{el} +{v:.0%}"

    def to_dict(self) -> dict:
        return dict(uid=self.uid, base=self.base, rarity=self.rarity, stars=self.stars, level=self.level,
                    mods=self.mods, ego=self.ego, bond=self.bond, durability=self.durability)

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        it = cls(d["uid"], d["base"], d["rarity"], d["stars"], d["level"], list(d.get("mods", [])))
        it.ego = d.get("ego")
        it.bond = d.get("bond", 0)
        it.durability = d.get("durability", it.max_durability)
        return it


# ---- rolling -----------------------------------------------------------------------------------------------------
def roll_mod(rng: random.Random, have: Optional[List[dict]] = None) -> dict:
    kinds = [k for k in MOD_KINDS if k not in {m["kind"] for m in (have or [])}] or list(MOD_KINDS)
    kind = rng.choice(kinds)
    lo, hi = config.ITEM_MOD_RANGE[kind]
    m = dict(kind=kind, value=round(rng.uniform(lo, hi), 3))
    if kind == "elem_dmg":
        m["element"] = rng.choice(ELEMENTS)
    return m


def roll_rarity(rng: random.Random, lure: bool = False) -> str:
    w = [config.ITEM_RARITY_RATES[r] * (config.ADV_LURE_BOOST if lure and r != "common" else 1) for r in RARITIES]
    return rng.choices(RARITIES, w)[0]


def roll_stars(rng: random.Random, rarity: str) -> int:
    lam = config.ITEM_STAR_DECAY[rarity]
    w = [math.exp(-lam * k) for k in range(config.MAX_STARS)]
    return rng.choices(range(1, config.MAX_STARS + 1), w)[0]


def roll_item(rng: random.Random, uid: int, lure: bool = False, rarity: str = None) -> Item:
    rarity = rarity or roll_rarity(rng, lure)
    it = Item(uid, rng.choice(BASES.keys()), rarity, roll_stars(rng, rarity))
    for _ in range(RARITIES.index(rarity)):
        it.mods.append(roll_mod(rng, it.mods))
    return it


# ---- what an equipped set does -------------------------------------------------------------------------------------
def item_bonus(slime) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for it in getattr(slime, "items", {}).values():
        if it.broken:
            continue
        for stat, v in it.stats_for(slime).items():
            out[stat] = out.get(stat, 0) + v
    return out


def battle_mods(slime) -> dict:
    """Aggregated mods for the battle engine: crit_rate, crit_dmg, lifesteal and elem (element -> bonus)."""
    out = dict(crit_rate=0.0, crit_dmg=0.0, lifesteal=0.0, elem={})
    for it in getattr(slime, "items", {}).values():
        if it.broken:
            continue
        for m in it.mods:
            v = m["value"] * it.mod_scale()
            if m["kind"] == "elem_dmg":
                out["elem"][m["element"]] = out["elem"].get(m["element"], 0.0) + v
            else:
                out[m["kind"]] += v
    return out


def can_wield(slime, item: Item) -> Optional[str]:
    """None if fine, else the reason."""
    if item.broken:
        return f"{item.name} is broken."
    if item.ego and not (slime.rarity == "legendary" and slime.stars == config.MAX_STARS):
        return "Ego relics can only be wielded by 5-star legendary slimes."
    return None
