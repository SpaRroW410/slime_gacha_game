"""The Keeper (the player): levels up through play, earns skill points and spends them in four branches.

    Caretaker    gentle hands, green thumb, soothing voice, lullaby         (tending the colony)
    Tactician    battle cry, field medic, keen eye, quartermaster           (running expeditions)
    Fortune      lucky charm, stonecutter, appraiser, thrifty               (luck and thrift)
    Matchmaker   matchmaker, mentor's eye, peacemaker, midwife              (bonds and families)
plus four daily ACTIVE abilities (Rally, Soothe, Fortune's Favor, Bond Night) unlocked by the first skill of a branch.
Effects are small numbers read through `Keeper.rank(key)`; the Game applies them where they matter.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

from . import config
from .errors import InvalidAction

BRANCHES = {"caretaker": ("Caretaker", "🌿"), "tactician": ("Tactician", "🧭"), "fortune": ("Fortune", "🍀"),
            "matchmaker": ("Matchmaker", "💞")}
TITLES = [(1, "Novice Keeper"), (5, "Tender"), (10, "Steward"), (15, "Warden"), (22, "Elder Keeper"), (30, "Archkeeper")]


@dataclass(frozen=True)
class Skill:
    key: str
    branch: str
    name: str
    emoji: str
    level: int                  # Keeper level needed
    per_rank: str               # what each rank does
    max_rank: int = 3


@dataclass(frozen=True)
class Active:
    key: str
    branch: str
    name: str
    emoji: str
    needs: str                  # skill key that unlocks it
    cooldown_days: int
    desc: str


SKILLS: Dict[str, Skill] = {s.key: s for s in [
    Skill("gentle_hands", "caretaker", "Gentle Hands", "🤗", 2, "Pats and meals soothe 50% more"),
    Skill("green_thumb", "caretaker", "Green Thumb", "🌱", 3, "+20% herbs from dungeons"),
    Skill("soothing_voice", "caretaker", "Soothing Voice", "🎶", 5, "+8% mediation success; bad feelings fade 15% faster"),
    Skill("lullaby", "caretaker", "Lullaby", "🌙", 7, "Sleeping slimes recover stamina 20% faster"),
    Skill("battle_cry", "tactician", "Battle Cry", "📣", 2, "Parties start fights with +6 determination and pride"),
    Skill("field_medic", "tactician", "Field Medic", "⛑️", 4, "Camps heal +4% max HP per hour"),
    Skill("keen_eye", "tactician", "Keen Eye", "🔭", 6, "Scouts work 8% faster"),
    Skill("quartermaster", "tactician", "Quartermaster", "📦", 8, "Slimes may use +5% more of your stocks on their own"),
    Skill("lucky_charm", "fortune", "Lucky Charm", "🍀", 3, "+10% odds of rare-or-better pulls"),
    Skill("stonecutter", "fortune", "Stonecutter", "⛏️", 4, "+20% ascension stone drops"),
    Skill("appraiser", "fortune", "Appraiser", "🔍", 6, "+10% materials from salvaging relics"),
    Skill("thrifty", "fortune", "Thrifty", "🪙", 8, "Building upgrades cost 5% less"),
    Skill("matchmaker", "matchmaker", "Matchmaker", "💘", 2, "Bonds grow 25% faster; couples and mentors form 25% more often"),
    Skill("mentors_eye", "matchmaker", "Mentor's Eye", "🎓", 4, "Mentees earn +10% more XP"),
    Skill("peacemaker", "matchmaker", "Peacemaker", "🕊️", 5, "Quarrels are 10% rarer"),
    Skill("midwife", "matchmaker", "Midwife", "🥚", 7, "Budding costs 20% less; better odds of rare children"),
]}
ACTIVES: Dict[str, Active] = {a.key: a for a in [
    Active("rally", "tactician", "Rally", "📣", "battle_cry", 1, "Every free slime gains joy, determination and pride."),
    Active("soothe", "caretaker", "Soothe", "🫧", "gentle_hands", 1, "Every slime's bad feelings ease and loneliness lifts."),
    Active("favor", "fortune", "Fortune's Favor", "🌠", "lucky_charm", 3, "Your next pull has double the rare odds."),
    Active("bond_night", "matchmaker", "Bond Night", "🎇", "matchmaker", 2, "Free slimes who get along grow closer."),
]}


def xp_to_next(level: int) -> int:
    return 40 + 30 * level + 6 * level * level


def title(level: int) -> str:
    return [t for lv, t in TITLES if level >= lv][-1]


class Keeper:
    def __init__(self):
        self.xp = 0
        self.level = 1
        self.ranks: Dict[str, int] = {}
        self.cooldowns: Dict[str, int] = {}          # active key -> game day it can be used again
        self.earned: Dict[str, int] = {}             # xp earned today per source (daily caps)
        self.earned_day = -1
        self.total_xp = 0

    # ---- levelling -----------------------------------------------------------------------------------------------
    def rank(self, key: str) -> int:
        return self.ranks.get(key, 0)

    @property
    def points(self) -> int:
        return (self.level - 1) + self.level // 5 - sum(self.ranks.values())

    def gain(self, amount: int, source: str = "", day: int = 0, cap: int = 0) -> List[str]:
        """Add Keeper XP (optionally capped per source per game day). Returns level-up messages."""
        if self.earned_day != day:
            self.earned, self.earned_day = {}, day
        if cap:
            amount = min(amount, cap - self.earned.get(source, 0))
        if amount <= 0 or self.level >= config.KEEPER_MAX_LEVEL:
            return []
        self.earned[source] = self.earned.get(source, 0) + amount
        self.xp += amount
        self.total_xp += amount
        out = []
        while self.level < config.KEEPER_MAX_LEVEL and self.xp >= xp_to_next(self.level):
            self.xp -= xp_to_next(self.level)
            self.level += 1
            out.append(f"⭐ You are now a level {self.level} {title(self.level)}! "
                       f"({self.points} skill point{'s' if self.points != 1 else ''} to spend)")
        return out

    # ---- skills ----------------------------------------------------------------------------------------------------
    def why_not(self, key: str) -> Optional[str]:
        sk = SKILLS.get(key)
        if not sk:
            return f"Unknown skill '{key}'."
        r = self.rank(key)
        if r >= sk.max_rank:
            return f"{sk.name} is already at its highest rank."
        need = sk.level + 2 * r
        if self.level < need:
            return f"{sk.name} rank {r + 1} needs Keeper level {need}."
        if self.points <= 0:
            return "You have no skill points to spend."
        return None

    def learn(self, key: str) -> str:
        why = self.why_not(key)
        if why:
            raise InvalidAction(why)
        self.ranks[key] = self.rank(key) + 1
        sk = SKILLS[key]
        return f"{sk.emoji} {sk.name} rank {self.ranks[key]}: {sk.per_rank}."

    def unlocked(self, active_key: str) -> bool:
        return self.rank(ACTIVES[active_key].needs) >= 1

    def ready(self, active_key: str, day: int) -> bool:
        return self.unlocked(active_key) and self.cooldowns.get(active_key, -1) <= day

    # ---- persistence -------------------------------------------------------------------------------------------------
    def to_dict(self) -> dict:
        return dict(xp=self.xp, level=self.level, ranks=self.ranks, cooldowns=self.cooldowns, total_xp=self.total_xp,
                    earned=self.earned, earned_day=self.earned_day)

    def load(self, d: dict) -> None:
        d = d or {}
        self.xp, self.level = d.get("xp", 0), d.get("level", 1)
        self.ranks = {k: v for k, v in d.get("ranks", {}).items() if k in SKILLS}
        self.cooldowns = {k: v for k, v in d.get("cooldowns", {}).items() if k in ACTIVES}
        self.total_xp = d.get("total_xp", 0)
        self.earned, self.earned_day = d.get("earned", {}), d.get("earned_day", -1)
