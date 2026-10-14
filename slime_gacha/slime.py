"""Slime: the collectible hero. Pure state + derived values; rules live in the engines."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import config
from .abilities import get_ability
from .archetypes import STAT_KEYS, Archetype, get_archetype
from .equipment import gear_bonus
from .items import Item, item_bonus
from .specialization import SPECS, apply_shifts

STAGE_TITLES = ["", "Greater ", "Prime "]


class Needs:
    """Maslow-style needs, 0..100 where higher = more satisfied."""

    def __init__(self, values: Optional[Dict[str, float]] = None):
        self.v = {k: 100.0 for k in config.NEED_ORDER}
        self.v["belonging"] = 70.0
        self.v["esteem"] = 60.0
        if values:
            self.v.update(values)

    def get(self, k: str) -> float:
        return self.v[k]

    def add(self, k: str, amount: float) -> None:
        self.v[k] = max(0.0, min(100.0, self.v[k] + amount))

    def set(self, k: str, value: float) -> None:
        self.v[k] = max(0.0, min(100.0, value))

    def dominant(self) -> Optional[str]:
        """Lowest-tier unmet need (below threshold), or None if all are fine."""
        for k in config.NEED_ORDER:
            if self.v[k] < config.NEED_THRESHOLD:
                return k
        return None

    def active(self) -> List[str]:
        """Tiers that currently matter: everything up to and including the first unmet tier."""
        out = []
        for k in config.NEED_ORDER:
            out.append(k)
            if self.v[k] < config.NEED_THRESHOLD:
                break
        return out

    def to_dict(self):
        return dict(self.v)


@dataclass
class HuntAssignment:
    zone: str
    ticks_left: int
    total_ticks: int

    def to_dict(self):
        return dict(zone=self.zone, ticks_left=self.ticks_left, total_ticks=self.total_ticks)


class Slime:
    def __init__(self, id: int, name: str, archetype: str, rarity: str,
                 variance: Optional[Dict[str, float]] = None, traits: Optional[List[str]] = None,
                 stars: int = 1):
        self.id = id
        self.name = name
        self.archetype = archetype
        self.rarity = rarity
        self.stars = stars             # 1..5, rolled at birth (see GachaSystem.roll_stars)
        self.death_cause = ""          # set by engines when hp drops to 0; Game reaps the slime
        self.variance = variance or {k: 1.0 for k in STAT_KEYS}
        self.traits = traits or []
        self.level = 1
        self.xp = 0                    # xp toward next level
        self.total_xp = 0              # lifetime xp (used by merging)
        self.stage = 0
        # --- fighting style / elemental mastery (see sparring.py, elements.py, spells.py)
        self.progress = 0                         # deepest Hollow Descent floor this slime has cleared
        self.exp: Dict[str, int] = {}             # experience counters -> outlook (see outlook.py)
        self.spec = ""                            # hybrid class key (see specialization.py)
        self.spec_disc = ""                       # the secondary discipline that made it (style affinity)
        self.gear: Dict[str, str] = {}            # slot -> gear key (see equipment.py)
        self.items: Dict[str, Item] = {}          # slot -> equipped relic (see items.py)
        self.merge_bonus: Dict[str, float] = {}   # flat stats absorbed from merged donors (see ascension.py)
        self.in_dungeon: str = ""                 # "main" / "grind" / "scout" while committed to a dungeon
        self.style_xp: Dict[str, float] = {}      # fighting-style xp per discipline (see sparring.py)
        self.morale: float = config.MORALE_START  # fight readiness 0-100 (see social.py)
        self.attuned: List[str] = []              # basic elements this slime has attuned to
        self.mastery_xp: Dict[str, float] = {}    # per basic element
        self.spells: List[str] = []               # learned spell keys (max config.MAX_SPELLS)
        self.task: Optional[dict] = None          # active study / research assignment (Library)
        self.behavior = self.arch.default_behavior
        self.state = "idle"            # idle | sleeping | hunting
        self.hunt: Optional[HuntAssignment] = None
        self.needs = Needs()
        self.hp = self.max_hp
        self.wins = 0
        self.merged = 0
        self.grounded = False          # set by an unresolved brawl: refuses hunts

    # ---- derived ---------------------------------------------------------
    @property
    def arch(self) -> Archetype:
        return get_archetype(self.archetype)

    @property
    def level_cap(self) -> int:
        return config.LEVEL_CAPS[min(self.stage, len(config.LEVEL_CAPS) - 1)]

    def core_stats(self) -> Dict[str, float]:
        """Class x level x rarity x star x stage x variance - no gear, relics or merge bonus."""
        a = self.arch
        mult = config.RARITY_STAT_MULT[self.rarity] * config.STAR_STAT_MULT[self.stars - 1] * config.STAGE_STAT_MULT[
            min(self.stage, len(config.STAGE_STAT_MULT) - 1)]
        return {k: (a.base_stats[k] + a.growth[k] * (self.level - 1)) * mult * self.variance.get(k, 1.0)
                for k in STAT_KEYS}

    def max_stats(self) -> Dict[str, float]:
        bonus = dict(gear_bonus(self.gear))
        for k, v in item_bonus(self).items():
            bonus[k] = bonus.get(k, 0.0) + v
        for k, v in self.merge_bonus.items():
            bonus[k] = bonus.get(k, 0.0) + v
        core = self.core_stats()
        out = {k: round(core[k] + bonus.get(k, 0.0), 1) for k in STAT_KEYS}
        return apply_shifts(out, self.spec) if self.spec else out

    @property
    def max_hp(self) -> int:
        return max(1, int(self.max_stats()["hp"]))

    def mood(self) -> float:
        act = self.needs.active()
        wsum = sum(config.MOOD_WEIGHTS[k] for k in act)
        return sum(self.needs.get(k) * config.MOOD_WEIGHTS[k] for k in act) / wsum / 100.0

    def mood_label(self) -> str:
        m = self.mood()
        return "ecstatic" if m > .85 else "happy" if m > .65 else "okay" if m > .45 else \
            "grumpy" if m > .25 else "miserable"

    def power_multiplier(self) -> float:
        return config.MOOD_POWER_MIN + (config.MOOD_POWER_MAX - config.MOOD_POWER_MIN) * self.mood()

    def known_abilities(self) -> List[str]:
        a = self.arch
        keys = [k for lvl, k in sorted(a.abilities.items()) if lvl <= self.level]
        keys += [k for st, k in sorted(a.evolve_abilities.items()) if st <= self.stage]
        if self.spec in SPECS and SPECS[self.spec].ability not in keys:
            keys.append(SPECS[self.spec].ability)
        return keys + [k for k in self.spells if k not in keys]

    def title(self) -> str:
        base = SPECS[self.spec].name if self.spec in SPECS else self.arch.name
        return f"{STAGE_TITLES[min(self.stage, len(STAGE_TITLES) - 1)]}{base}"

    def power_rating(self) -> float:
        s = self.max_stats()
        return (s["hp"] / 4 + s["atk"] + s["mag"] + s["defense"] + s["spd"] / 2) * self.power_multiplier()

    @property
    def busy(self) -> bool:
        """Away from the colony on a task (hunting or at the training grounds / library)."""
        return self.state in ("hunting", "studying") or bool(self.in_dungeon)

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def star_str(self) -> str:
        return "★" * self.stars + "☆" * (config.MAX_STARS - self.stars)

    def summary(self) -> str:
        dom = self.needs.dominant()
        return (f"#{self.id:<3} {self.arch.emoji} {self.name:<10} {self.title():<18} "
                f"[{config.RARITY_TAG[self.rarity]}]{self.star_str()} Lv{self.level:<2} "
                f"HP {self.hp}/{self.max_hp} [{self.behavior}] {self.state}"
                f"{' @' + self.in_dungeon if self.in_dungeon else ''}"
                f"{' (wants: ' + dom + ')' if dom else ''}")

    # ---- persistence -----------------------------------------------------
    def to_dict(self):
        return dict(id=self.id, name=self.name, archetype=self.archetype, rarity=self.rarity, stars=self.stars,
                    variance=self.variance, traits=self.traits, level=self.level, xp=self.xp,
                    total_xp=self.total_xp, stage=self.stage, behavior=self.behavior,
                    state=self.state, hunt=self.hunt.to_dict() if self.hunt else None,
                    needs=self.needs.to_dict(), hp=self.hp, wins=self.wins,
                    merged=self.merged, grounded=self.grounded, style_xp=self.style_xp, morale=self.morale,
                    gear=self.gear, items={k: v.to_dict() for k, v in self.items.items()}, merge_bonus=self.merge_bonus, in_dungeon=self.in_dungeon, progress=self.progress, exp=self.exp, spec=self.spec, spec_disc=self.spec_disc,
                    attuned=self.attuned, mastery_xp=self.mastery_xp, spells=self.spells,
                    task=self.task)

    @classmethod
    def from_dict(cls, d) -> "Slime":
        s = cls(d["id"], d["name"], d["archetype"], d["rarity"], d.get("variance"), d.get("traits"),
                d.get("stars", 1))
        for k in ("level", "xp", "total_xp", "stage", "behavior", "state", "hp", "wins",
                  "merged", "grounded", "style_xp", "morale", "gear", "in_dungeon", "merge_bonus", "progress", "exp", "spec", "spec_disc", "attuned", "mastery_xp", "spells", "task"):
            if k in d:
                setattr(s, k, d[k])
        s.items = {k: Item.from_dict(v) for k, v in (d.get("items") or {}).items()}
        s.needs = Needs(d.get("needs"))
        s.hunt = HuntAssignment(**d["hunt"]) if d.get("hunt") else None
        return s
