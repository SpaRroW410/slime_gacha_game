"""Keeper achievements: milestones checked against the colony; each can grant a title the Keeper may wear."""
from dataclasses import dataclass
from typing import Callable, Dict, List


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
]}


def check(g) -> List[str]:
    """Record newly earned achievements; returns messages."""
    out = []
    for a in ACHIEVEMENTS.values():
        if a.key not in g.keeper.achieved and a.check(g):
            g.keeper.achieved.append(a.key)
            out.append(f"🏆 Achievement: {a.name}!" + (f" You may now wear the title “{a.title}”." if a.title else ""))
    return out
