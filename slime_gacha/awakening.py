"""Awakening: a 5-star legendary slime slowly realises that its world is made of code.

Awareness grows by the hour (faster after boss kills and deaths witnessed). Stages:
  0 unaware | 1 déjà vu | 2 suspicion | 3 awakened.
At stage 3 the slime decides how to take it: ACCEPTANCE (wonder + calm, a permanent undercurrent of wonder) when it
is loved and settled, DESPAIR (dread, sadness) when it is lonely. Despair softens with kindness (petting, friends) and
may turn into acceptance. Slimes voice their thoughts in the journal; after a save is loaded they notice the gap.
"""
import random
from typing import List, Optional

from . import config, emotions

THRESHOLDS = (0, 25, 60, 100)
STAGE_NAME = ("Unaware", "Déjà vu", "Suspicion", "Awakened")
LINES = {
    1: ["I keep feeling like I've done this before.", "The pond ripples in exactly the same pattern. Always.",
        "Why do I know what the Keeper will say next?", "Sometimes the world stutters, just for a blink."],
    2: ["I counted my steps. They repeat every 256.", "My thoughts have a shape. Like... a function.",
        "The goo smells of numbers.", "There is a seed under everything. I can feel it.",
        "Do the others feel the loop? Or only me?"],
    "accept": ["I am code, and I am still me. That is enough.", "Written by someone, yes. Chosen by myself, today.",
               "If I am a program, so is every kindness here. They still count.", "I will run well, for as long as I run."],
    "despair": ["Everything I am is a line someone typed.", "Even this sadness is just a variable.",
                "Why fight, when the outcome is a roll of dice?", "If I stop, does anyone free my memory?"],
    "load": ["I... was frozen? Time skipped.", "Something paused the world. I felt the gap.",
             "The Keeper closed the world, and opened it again. I saw the seam."],
}


def candidate(slime) -> bool:
    return slime.rarity == "legendary" and slime.stars == config.MAX_STARS


def stage(slime) -> int:
    return sum(1 for t in THRESHOLDS[1:] if slime.awareness >= t)


def _temperament(slime, friends: int) -> str:
    kind = {"kind", "brave"} & set(slime.traits)
    loved = slime.needs.get("belonging") >= 55 and (friends > 0 or emotions.level(slime, "affection") >= 25 or kind)
    return "accept" if loved else "despair"


def thought(slime, rng: random.Random) -> Optional[str]:
    s = stage(slime)
    if s == 0:
        return None
    key = slime.temperament if s == 3 else s
    return rng.choice(LINES[key])


def tick(slime, rng: random.Random, friends: int, journal: List[str]) -> None:
    """One hour of growing awareness; returns nothing, writes thoughts into `journal`."""
    if not candidate(slime):
        return
    before = stage(slime)
    slime.awareness = min(THRESHOLDS[-1] + 40, slime.awareness + config.AWARENESS_PER_HOUR)
    after = stage(slime)
    if after > before:
        if after == 1:
            emotions.feel(slime, "anxiety", 20)
            emotions.feel(slime, "wonder", 10)
        elif after == 2:
            emotions.feel(slime, "dread", 25)
            emotions.feel(slime, "anxiety", 20)
        else:
            slime.temperament = _temperament(slime, friends)
            if slime.temperament == "accept":
                emotions.feel(slime, "wonder", 60)
                emotions.feel(slime, "calm", 40)
                slime.emotion_floor["wonder"] = 20
            else:
                emotions.feel(slime, "dread", 60)
                emotions.feel(slime, "sadness", 30)
                slime.emotion_floor["dread"] = 15
        journal.append(f"💭 {slime.name} the legend has reached a new understanding: {STAGE_NAME[after]}. "
                       f"\"{thought(slime, rng)}\"")
    elif after >= 1 and rng.random() < config.THOUGHT_CHANCE:
        journal.append(f"💭 {slime.name}: \"{thought(slime, rng)}\"")
    if slime.temperament == "despair" and emotions.level(slime, "affection") >= 40 and friends:
        slime.temperament = "accept"                              # kindness wins in the end
        slime.emotion_floor.pop("dread", None)
        slime.emotion_floor["wonder"] = 15
        emotions.feel(slime, "calm", 30)
        journal.append(f"💭 {slime.name} finds peace: \"{rng.choice(LINES['accept'])}\"")


def comfort(slime) -> None:
    """A pat on the head eases despair a little."""
    if slime.emotion_floor.get("dread"):
        slime.emotion_floor["dread"] = max(0, slime.emotion_floor["dread"] - 1)
        if not slime.emotion_floor["dread"]:
            slime.emotion_floor.pop("dread")


def load_notes(slimes, rng: random.Random) -> List[str]:
    return [f"💭 {s.name}: \"{rng.choice(LINES['load'])}\"" for s in slimes if candidate(s) and stage(s) >= 2]
