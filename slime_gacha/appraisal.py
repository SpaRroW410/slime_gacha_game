"""Appraisal: the same event means different things to different slimes (docs/MINDS.md).

Every slime in a fight feels the usual things (game._after_battle: joy and pride after a win, sadness, anger and fear after a
defeat). On top of that, its personality decides what the event MEANS to it: a lost fight shames a proud slime, frightens a
timid one and spurs a brave one; a win makes a timid slime simply relieved. The first victory of its life lands harder.
"""
from typing import Dict

from . import emotions

REACT: Dict[str, Dict[str, Dict[str, float]]] = {
    "defeat": {"proud": dict(guilt=12, anger=8), "timid": dict(fear=15), "brave": dict(determination=15),
               "grumpy": dict(anger=12), "kind": dict(sadness=8), "lazy": dict(calm=5), "chatty": dict(loneliness=6),
               "gluttonous": dict(sadness=5)},
    "victory": {"proud": dict(pride=12), "kind": dict(affection=8), "brave": dict(determination=6), "timid": dict(calm=10),
                "chatty": dict(joy=6), "grumpy": dict(anger=-10), "lazy": dict(calm=5), "gluttonous": dict(joy=4)},
    "ally_fell": {"brave": dict(determination=10), "timid": dict(fear=10), "kind": dict(guilt=8), "grumpy": dict(anger=10),
                  "proud": dict(guilt=6), "chatty": dict(sadness=6)},
}
FIRST_WIN = dict(pride=15, joy=10)


def react(s, event: str, first: bool = False) -> None:
    """Add the feelings this event stirs in this particular slime (personality, and a first victory)."""
    for t in s.traits:
        for k, v in REACT.get(event, {}).get(t, {}).items():
            if v >= 0:
                emotions.feel(s, k, v)
            else:
                emotions.soothe(s, k, -v)
    if event == "victory" and first:
        for k, v in FIRST_WIN.items():
            emotions.feel(s, k, v)
