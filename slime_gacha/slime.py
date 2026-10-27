"""Slime: the collectible hero. Pure state + derived values; rules live in the engines."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import config
from .abilities import get_ability
from .archetypes import STAT_KEYS, Archetype, get_archetype
from .equipment import gear_bonus
from . import attributes, awakening, meaning, potions, sanity
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
    group: int = 0                  # hunts organised together by the Vice Keeper share a group id

    def to_dict(self):
        return dict(zone=self.zone, ticks_left=self.ticks_left, total_ticks=self.total_ticks, group=self.group)


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
        self.class_prof = config.PROF_START       # proficiency in the original class discipline, 0-100 (attributes.capstones)
        self.prof_idle = 0                        # days since it last practised
        self.spec_prof = config.PROF_SPEC_START   # proficiency in the secondary discipline of a hybrid class
        self.spec_idle = 0
        self.job = ""                             # occupation key while state == "working" (see jobs.py)
        self.job_xp: Dict[str, int] = {}          # rounds of work done per occupation (kept when switching)
        self.job_clock = 0                        # hours into the current round
        self.star_peak = 1                        # most stars it ever had: star attributes stay unlocked after a rarity ascension
        self.color = ""                           # body colour chosen by the keeper ("" = the class colour)
        self.pure_earned = False                  # earned the pure capstones (legendary, 5 stars, never specialized)
        self.spec = ""                            # hybrid class key (see specialization.py)
        self.spec_disc = ""                       # the secondary discipline that made it (style affinity)
        self.gear: Dict[str, str] = {}            # slot -> gear key (see equipment.py)
        self.items: Dict[str, Item] = {}          # slot -> equipped relic (see items.py)
        self.emotions: Dict[str, float] = {}      # feeling -> intensity 0..100 (see emotions.py)
        self.emotion_floor: Dict[str, float] = {} # permanent undercurrents (see awakening.py)
        self.causes: Dict[str, Dict[str, float]] = {}   # feeling -> {reason: weight} (emotions.note_cause), for the card
        self.content = 50.0                       # contentment 0-100: how life has felt over the last days (emotions.settle)
        self.awareness = 0.0                      # 5-star legendaries realise they are code (see awakening.py)
        self.temperament = ""                     # how an awakened slime takes it: settled | peace | cog | despair
        self.life = None                          # its daily record (care, connection, purpose, hardship), see awakening.py
        self.grief: List[dict] = []               # losses it is still grieving (grief.py)
        self.born: Optional[int] = None           # game day it was pulled or born (rituals.py: hatch days)
        self.low_days = 0                         # consecutive days with sanity 'breaking' (mind.py: may ask to leave)
        self.parents: List[int] = []              # lineage: ids of the two parents (budding)
        self.parent_names: List[str] = []
        self.generation = 0
        self.stamina_frac = 1.0                   # stamina as a fraction of max (see attributes.py)
        self.buffs: List[dict] = []               # potion effects: {kind, grade, bonus, hours}
        self.proficiency: Dict[str, int] = {}     # weapon family -> uses (see items.FAMILIES)
        self.weapon_memory: List[str] = []        # up to config.WEAPON_MEMORY families kept in mind
        self.merge_bonus: Dict[str, float] = {}   # flat stats absorbed from merged donors (see ascension.py)
        self.in_dungeon: str = ""                 # "main" / "grind" / "scout" while committed to a dungeon
        self.style_xp: Dict[str, float] = {}      # fighting-style xp per discipline (see sparring.py)
        self.sanity: float = float(config.SANITY_MAX.get(rarity, 80))   # mental reserve (sanity.py)
        self.goal = None                                 # {"kind", "target", "text", "day"} (mind.py)
        self.request = None                              # a pending request to the Keeper
        self.trust: float = 50.0                         # trust in the Keeper, 0-100
        self.drift: Dict[str, int] = {}                  # experience that slowly rewrites traits (ko / win / heal)
        self.memories: List[dict] = []                  # what it remembers about others (memory.py)
        self.cared = {"day": -1, "talk": 0, "pet": 0}  # how often the Keeper talked to / petted it today (diminishing returns)
        self.morale: float = config.MORALE_START  # fight readiness 0-100 (see social.py)
        self.attuned: List[str] = []              # basic elements this slime has attuned to
        self.mastery_xp: Dict[str, float] = {}    # per basic element
        self.spells: List[str] = []               # learned spell keys (max config.MAX_SPELLS)
        self.task: Optional[dict] = None          # active study / research assignment (Library)
        self.behavior = self.arch.default_behavior
        self.state = "idle"            # idle | sleeping | hunting | studying | working | resting
        self.hunt: Optional[HuntAssignment] = None
        self.needs = Needs()
        self.hp = self.max_hp
        self.wins = 0
        self.merged = 0
        self.grounded = False          # set by an unresolved brawl: refuses hunts
        self.row = ""                  # formation: "front" | "back" | "" (automatic: casters and archers stand at the back)
        self.brawls = 0                # brawls this slime has been in, ever (a stat)
        self.fights: Dict[int, int] = {}   # slime id -> last day it came to blows with it, counting against it (Game.unwelcome)

    # ---- derived ---------------------------------------------------------
    @property
    def arch(self) -> Archetype:
        return get_archetype(self.archetype)

    def xp_needed(self, level: int) -> int:
        """XP to go from `level` to the next, for this slime's rarity and stars."""
        return config.xp_to_next(level, self.rarity, self.stars)

    @property
    def level_cap(self) -> int:
        return config.LEVEL_CAPS[min(self.stage, len(config.LEVEL_CAPS) - 1)]

    def core_stats(self) -> Dict[str, float]:
        """Class x level x rarity x star x stage x variance - no gear, relics or merge bonus."""
        a = self.arch
        mult = config.RARITY_STAT_MULT[self.rarity] * config.STAR_STAT_MULT[self.stars - 1] * config.STAGE_STAT_MULT[
            min(self.stage, len(config.STAGE_STAT_MULT) - 1)]
        return {k: (a.base_stats[k] + a.growth[k] * (config.stat_level(self.level) - 1)) * mult * self.variance.get(k, 1.0)
                for k in STAT_KEYS}

    def max_stats(self) -> Dict[str, float]:
        bonus = dict(gear_bonus(self.gear))
        for k, v in item_bonus(self).items():
            bonus[k] = bonus.get(k, 0.0) + v
        for k, v in self.merge_bonus.items():
            bonus[k] = bonus.get(k, 0.0) + v
        core = self.core_stats()
        out = {k: round((core[k] + bonus.get(k, 0.0)) * potions.stat_mult(self.buffs, k), 1)
               for k in STAT_KEYS}
        return apply_shifts(out, self.spec) if self.spec else out

    @property
    def max_hp(self) -> int:
        return max(1, int(self.max_stats()["hp"]))

    @property
    def max_stamina(self) -> float:
        return attributes.max_stamina(self)

    @property
    def stamina(self) -> float:
        return round(self.stamina_frac * self.max_stamina, 1)

    def needs_mood(self) -> float:
        act = self.needs.active()
        wsum = sum(config.MOOD_WEIGHTS[k] for k in act)
        return sum(self.needs.get(k) * config.MOOD_WEIGHTS[k] for k in act) / wsum / 100.0

    def mood(self) -> float:
        """How the needs feel, capped by sanity: a worn-down slime cannot be fed or petted into happiness."""
        return min(self.needs_mood(), sanity.mood_cap(self), awakening.mood_cap(self), meaning.mood_cap(self))

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
        evo = attributes.evolution_skill(self)
        if evo and evo not in keys:
            keys.append(evo)
        if self.spec in SPECS and SPECS[self.spec].ability not in keys:
            keys.append(SPECS[self.spec].ability)
        keys += [k for k in attributes.rarity_skills(self) if k not in keys]
        keys += [k for k in attributes.capstones(self) if k not in keys]
        hc = attributes.hybrid_capstone(self)
        if hc and hc not in keys:
            keys.append(hc)
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
        return self.state in ("hunting", "studying", "working") or bool(self.in_dungeon)

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
                    merged=self.merged, grounded=self.grounded, brawls=self.brawls, fights={str(k): v for k, v in self.fights.items()}, row=self.row, style_xp=self.style_xp, morale=self.morale, sanity=round(self.sanity, 2), cared=self.cared, memories=self.memories, goal=self.goal, request=self.request, trust=round(self.trust, 1), drift=self.drift,
                    gear=self.gear, items={k: v.to_dict() for k, v in self.items.items()}, merge_bonus=self.merge_bonus, stamina_frac=self.stamina_frac, buffs=self.buffs, parents=self.parents, parent_names=self.parent_names,
                    generation=self.generation, emotions=self.emotions,
                    emotion_floor=self.emotion_floor, causes=self.causes, content=self.content, awareness=self.awareness, temperament=self.temperament, life=meaning.pack(self.life), low_days=self.low_days, grief=self.grief, born=self.born,
                    proficiency=self.proficiency, weapon_memory=self.weapon_memory, in_dungeon=self.in_dungeon, progress=self.progress, exp=self.exp, spec=self.spec, spec_disc=self.spec_disc,
                    attuned=self.attuned, mastery_xp=self.mastery_xp, spells=self.spells,
                    task=self.task, class_prof=round(self.class_prof, 2), prof_idle=self.prof_idle, pure_earned=self.pure_earned, color=self.color, star_peak=self.star_peak, job=self.job, job_xp=dict(self.job_xp), job_clock=self.job_clock,
                    spec_prof=round(self.spec_prof, 2), spec_idle=self.spec_idle)

    @classmethod
    def from_dict(cls, d) -> "Slime":
        s = cls(d["id"], d["name"], d["archetype"], d["rarity"], d.get("variance"), d.get("traits"),
                d.get("stars", 1))
        for k in ("level", "xp", "total_xp", "stage", "behavior", "state", "hp", "wins",
                  "merged", "grounded", "brawls", "row", "style_xp", "morale", "sanity", "cared", "memories", "goal", "request", "trust", "drift", "gear", "in_dungeon", "merge_bonus", "stamina_frac", "buffs", "parents", "parent_names", "generation", "emotions", "emotion_floor", "causes", "content", "awareness", "temperament", "life", "low_days", "grief", "born", "proficiency", "weapon_memory", "progress", "exp", "spec", "spec_disc", "attuned", "mastery_xp", "spells", "task", "class_prof", "prof_idle", "pure_earned", "spec_prof", "spec_idle", "color", "star_peak", "job", "job_xp", "job_clock"):
            if k in d:
                setattr(s, k, d[k])
        s.life = meaning.unpack(s.life)
        s.fights = {int(k): v for k, v in (d.get("fights") or {}).items()}
        s.items = {k: Item.from_dict(v) for k, v in (d.get("items") or {}).items()}
        s.needs = Needs(d.get("needs"))
        s.hunt = HuntAssignment(**d["hunt"]) if d.get("hunt") else None
        return s
