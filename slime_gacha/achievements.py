"""Keeper achievements: milestones checked against the colony; each can grant a title the Keeper may wear."""
from dataclasses import dataclass
from typing import Callable, Dict, List

from . import config

GRADES = (("gold", "🥇"), ("silver", "🥈"), ("bronze", "🥉"))


@dataclass(frozen=True)
class Achievement:
    key: str
    name: str
    emoji: str
    desc: str
    title: str                       # worn-title unlocked by it ("" for none)
    check: Callable                  # game -> bool


def _count(g, pred) -> int:
    return sum(1 for s in g.slimes() if pred(s))


# ---- Gentle Keeper badges: a milestone floor cleared with few slimes merged or destroyed ---------------------------------------------------
def gentle_grade(floor: int, sacrifices: int) -> str:
    """"gold", "silver", "bronze" or "" for clearing `floor` (a milestone in config.GENTLE_FLOORS) after `sacrifices` sacrifices."""
    limits = config.GENTLE_FLOORS.get(floor)
    if not limits or sacrifices < 0:
        return ""
    return next((name for (name, _), most in zip(GRADES, limits) if sacrifices <= most), "")


def gentle_badges(g) -> List[dict]:
    """One row per milestone floor: the sacrifices when it was first cleared (None: not yet; -1: before the colony counted them),
    the grade it earned and the limits for each grade."""
    out = []
    for floor, limits in sorted(config.GENTLE_FLOORS.items()):
        n = g.milestones.get(floor)
        grade = gentle_grade(floor, n) if n is not None else ""
        out.append(dict(floor=floor, sacrifices=n, grade=grade, emoji=dict(GRADES).get(grade, ""),
                        limits=dict(zip((x for x, _ in GRADES), limits))))
    return out


def _gentle(g, grade: str) -> bool:
    return any(b["grade"] == grade for b in gentle_badges(g))


ACHIEVEMENTS: Dict[str, Achievement] = {a.key: a for a in [
    Achievement("first_pulls", "Hatching Season", "🥚", "Pull 50 slimes.", "the Hatcher", lambda g: g.gacha.total_pulls >= 50),
    Achievement("big_colony", "Full House", "🏠", "Keep 25 slimes at once.", "the Host", lambda g: len(g.roster) >= 25),
    Achievement("legend", "A Legend Hatches", "🌟", "Own a legendary slime.", "Legend-Keeper", lambda g: _count(g, lambda s: s.rarity == "legendary") > 0),
    Achievement("floor_10", "Ten Floors Down", "🕳️", "Clear floor 10 of the Descent.", "the Delver", lambda g: g.best_floor >= 10),
    Achievement("floor_30", "Deep Delver", "⛏️", "Clear floor 30 of the Descent.", "Deepwalker", lambda g: g.best_floor >= 30),
    Achievement("floor_50", "Bottom of the Hollow", "👑", "Defeat the final boss of the Descent.", "Hollow-Breaker", lambda g: bool(g.descent_cleared)),
    Achievement("friends", "Good Friends", "💞", "Have 10 pairs of slimes who are close friends.", "the Matchmaker", lambda g: sum(1 for v in g.social.bonds.values() if v >= 20) >= 10),
    Achievement("builder", "Master Builder", "🏗️", "Raise any building to level 5.", "the Builder", lambda g: any(g.buildings.level(k) >= 5 for k in g.buildings.levels)),
    Achievement("keeper_15", "Seasoned Keeper", "🧙", "Reach Keeper level 15.", "", lambda g: g.keeper.level >= 15),
    Achievement("grave", "Remembered", "🪦", "Lose 10 slimes. They are remembered.", "the Mourner", lambda g: len(g.graveyard) >= 10),
    Achievement("gentle_bronze", "A Light Hand", "🥉", "Clear a milestone floor (10, 20, 30, 40, 50) with few slimes merged or destroyed: a bronze Gentle Keeper badge.",
                "", lambda g: any(b["grade"] for b in gentle_badges(g))),
    Achievement("gentle_gold", "Gentle Keeper", "🥇", "Earn a gold Gentle Keeper badge: a milestone floor cleared with almost no slime merged or destroyed.",
                "the Gentle", lambda g: _gentle(g, "gold")),
]}


def check(g) -> List[str]:
    """Record newly earned achievements; returns messages."""
    out = []
    for a in ACHIEVEMENTS.values():
        if a.key not in g.keeper.achieved and a.check(g):
            g.keeper.achieved.append(a.key)
            out.append(f"🏆 Achievement: {a.name}!" + (f" You may now wear the title “{a.title}”." if a.title else ""))
    return out
