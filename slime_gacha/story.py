"""Campaign chapters (docs/STORY.md): story beats that unlock from play and are read in People > Records.

Chapters are data: (key, title, hint, trigger kind, value, text). Triggers: "pulls" (gacha pulls), "colony" (slimes at home),
"floor" (deepest Descent floor cleared), "cleared" (the final boss has fallen).
"""
from dataclasses import dataclass
from typing import Callable, Dict, List


@dataclass(frozen=True)
class Chapter:
    key: str
    title: str
    hint: str
    kind: str
    value: int
    text: str


CHAPTERS: List[Chapter] = [
    Chapter("wake", "1. Wake Up, Goo", "Pull your first slime.", "pulls", 1,
            "The Well hiccups, and something small and confused blorps out of the dark. It is hungry. It is also, you suspect, a little offended "
            "to have been woken. Feed it, find it a bed, and it may forgive you. The Mother Gloop dreams on, one droplet lighter."),
    Chapter("squabble", "2. Squabble Season", "Grow the colony to 8 slimes.", "colony", 8,
            "Eight droplets under one roof is a recipe for opinions. Someone ate someone's snack; someone sang at night. The Council of Blorp "
            "convenes for the first time, and you learn that mediation is mostly listening while a slime explains, at length, why it was right."),
    Chapter("crust", "3. The Crust Road", "Clear floor 5 of the Hollow Descent.", "floor", 5,
            "Past the first guardian the shaft opens onto the Crust Road, where the Dry Tide has already been. The walls are cracked like old "
            "pottery. Your scouts return quiet and a little dusty. The landing is the last place the stairs will let anyone turn back."),
    Chapter("echoes", "4. Echoes of the Kings", "Clear floor 25 of the Hollow Descent.", "floor", 25,
            "Halfway down, the walls begin to speak in the Hollow Kings' voices: crowns, bottles, a promise to keep the Mother safe by keeping her "
            "small. Your slimes listen, then argue about it at dinner. Some of them remember things they were never taught."),
    Chapter("heart", "5. The Heart of the Hollow", "Defeat the Parched King on floor 50.", "cleared", 1,
            "The Parched King falls the way a dry riverbed fills: all at once, and then quietly. Below his throne the Mother Gloop stirs. The "
            "droplets you pulled one by one, hungry and opinionated and yours, hum a single note, and the Dry Tide begins to withdraw. "
            "The Well, for the first time in an age, is full."),
]


def reached(g, c: Chapter) -> bool:
    return {"pulls": lambda: g.gacha.total_pulls >= c.value, "colony": lambda: len(g.roster) >= c.value,
            "floor": lambda: g.best_floor >= c.value, "cleared": lambda: bool(g.descent_cleared)}[c.kind]()


def check(g) -> List[str]:
    out = []
    for c in CHAPTERS:
        if c.key not in g.chapters and reached(g, c):
            g.chapters.append(c.key)
            out.append(f"📖 New chapter: {c.title}. Read it in People > Records.")
    return out
