"""Emotions: a slime's passing feelings (0-100 each), which change how it fights.

Feelings are stirred by events (victory, defeat, a friend's death, a quarrel, hunger, a pat on the head ...), fade by
the hour and are shaped by traits (a grumpy slime anger easily, a timid one fears, a kind one loves). In battle each
emotion nudges stats and combat attributes in proportion to its intensity - anger: +attack, -defense; sadness:
-speed; fear: +evasion, -attack ... Total change per stat is clamped to +-35%.
"""
import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

STATS = ("atk", "defense", "mag", "spd")


@dataclass(frozen=True)
class Emotion:
    key: str
    name: str
    emoji: str
    kind: str                                   # "good" | "bad" | "mixed"
    stats: Dict[str, float]                     # at intensity 100: multiplier change per stat
    mods: Dict[str, float]                      # at intensity 100: combat attributes (crit_rate, evasion, regen ...)
    decay: float                                # intensity lost per hour
    lines: Tuple[str, ...] = ()


def _e(*a, **kw):
    e = Emotion(*a, **kw)
    return e.key, e


EMOTIONS: Dict[str, Emotion] = dict([
    _e("joy", "Joy", "😄", "good", dict(atk=.05, defense=.05, mag=.05, spd=.08), dict(crit_rate=.03), 5.0,
       ("Everything is wonderfully squishy!", "Best. Day. Ever.")),
    _e("anger", "Anger", "😠", "mixed", dict(atk=.25, defense=-.18), dict(crit_dmg=.10), 6.0,
       ("Grrr. Don't talk to me.", "I'll flatten the next thing that blorps.")),
    _e("sadness", "Sadness", "😢", "bad", dict(spd=-.20, atk=-.08, mag=-.08), {}, 3.0,
       ("Everything feels heavy.", "I miss how things were.")),
    _e("fear", "Fear", "😨", "bad", dict(atk=-.12, defense=.05, spd=.05), dict(evasion=.10), 7.0,
       ("Did you hear that?", "I want to be somewhere small and dark.")),
    _e("pride", "Pride", "😤", "good", dict(atk=.10, defense=.06, mag=.06), {}, 3.0,
       ("Behold. Me.", "I am, frankly, magnificent.")),
    _e("calm", "Calm", "😌", "good", dict(defense=.10, mag=.12), dict(regen=.02), 3.0,
       ("Breathe in. Goo. Breathe out.", "All is still.")),
    _e("anxiety", "Anxiety", "😰", "bad", dict(spd=.10, defense=-.10, mag=-.05), dict(evasion=.05), 4.0,
       ("What if it all goes wrong?", "Too many what-ifs.")),
    _e("loneliness", "Loneliness", "🥺", "bad", dict(atk=-.06, defense=-.06, spd=-.10), {}, 1.5,
       ("Does anyone want to hang out?", "It's quiet. Too quiet.")),
    _e("determination", "Determination", "😠", "good", dict(atk=.10, defense=.10), {}, 3.0,
       ("I am not done yet.", "One more push.")),
    _e("affection", "Affection", "🥰", "good", dict(defense=.06, mag=.06), dict(regen=.01), 2.0,
       ("I like it here. With you all.", "Warm. Fuzzy. Safe.")),
    _e("guilt", "Guilt", "😔", "bad", dict(atk=-.06, defense=-.08, mag=-.06), {}, 2.5,
       ("It should have been me.", "I can't stop thinking about it.")),
    _e("dread", "Dread", "😱", "bad", dict(mag=.15, atk=-.12, spd=-.05), {}, 1.0,
       ("Nothing is real. Everything is a loop.", "I see the edges of the world.")),
    _e("wonder", "Wonder", "🤩", "good", dict(mag=.14, spd=.08), dict(crit_rate=.04), 2.0,
       ("The world is made of... patterns. Beautiful.", "I see how it all fits.")),
])

OPPOSITE = dict(joy="sadness", sadness="joy", anger="calm", calm="anger", fear="determination", determination="fear",
                pride="guilt", guilt="pride", affection="loneliness", loneliness="affection", wonder="dread", dread="wonder")
# trait -> {emotion: gain multiplier}
TRAIT_GAIN = dict(
    grumpy=dict(anger=1.5, joy=.8), brave=dict(fear=.5, determination=1.4), timid=dict(fear=1.5, anxiety=1.4),
    kind=dict(affection=1.3, anger=.7, guilt=1.2), proud=dict(pride=1.4, guilt=.8, anger=1.1),
    chatty=dict(loneliness=1.5, joy=1.2), lazy=dict(joy=.9, anxiety=.8), gluttonous=dict(anger=1.2),
)
CAP = 0.35


def level(slime, key: str) -> float:
    return slime.emotions.get(key, 0.0)


def feel(slime, key: str, amount: float) -> None:
    """Stir an emotion (scaled by the slime's traits); its opposite is quieted a little."""
    if key not in EMOTIONS or amount == 0:
        return
    g = 1.0
    for t in slime.traits:
        g *= TRAIT_GAIN.get(t, {}).get(key, 1.0)
    amount *= g if amount > 0 else 1.0
    slime.emotions[key] = max(0.0, min(100.0, slime.emotions.get(key, 0.0) + amount))
    if amount > 0 and key in OPPOSITE:
        o = OPPOSITE[key]
        if o in slime.emotions:
            slime.emotions[o] = max(0.0, slime.emotions[o] - amount * 0.3)
    if slime.emotions[key] <= 0:
        slime.emotions.pop(key, None)


def soothe(slime, key: str, amount: float) -> None:
    feel(slime, key, -abs(amount))


def tick(slime, rng: random.Random, sleeping: bool = False, fade: float = 1.0) -> None:
    """One hour: feelings fade (faster asleep) and needs stir new ones."""
    n = slime.needs
    drift = []
    if n.get("food") < 30:
        drift.append(("anger", 8))
    if n.get("energy") < 30:
        drift.append(("sadness", 4))
    if n.get("belonging") < 35:
        drift.append(("loneliness", 4))
    elif n.get("belonging") > 75:
        drift.append(("affection", 1))
    if n.get("esteem") > 75:
        drift.append(("pride", 1))
    if n.get("safety") < 40:
        drift.append(("fear", 9)), drift.append(("anxiety", 6))
    if slime.morale < 25:
        drift.append(("sadness", 4)), drift.append(("anger", 7))
    elif slime.morale > 65 and min(n.v.values()) > 55:
        drift.append(("calm", 2)), drift.append(("joy", 1))
    if rng.random() < 0.03:                                       # an ambient mood swing
        drift.append((rng.choice(list(EMOTIONS)[:9]), 6))
    for k, a in drift:
        feel(slime, k, a)
    mult = 2.0 if sleeping else 1.0
    floor = getattr(slime, "emotion_floor", {})
    for k in list(slime.emotions):
        f = fade if EMOTIONS[k].kind == "bad" else 1.0
        slime.emotions[k] = max(floor.get(k, 0.0), slime.emotions[k] - EMOTIONS[k].decay * mult * f)
        if slime.emotions[k] < 1:
            slime.emotions.pop(k)
    for k, f in floor.items():                                    # a permanent undercurrent (see awakening.py)
        if slime.emotions.get(k, 0.0) < f:
            slime.emotions[k] = float(f)


def modifiers(slime) -> Tuple[Dict[str, float], Dict[str, float]]:
    """(stat multipliers, combat attribute bonuses) from the current feelings."""
    mult = {s: 1.0 for s in STATS}
    mods: Dict[str, float] = {}
    for k, v in slime.emotions.items():
        e = EMOTIONS.get(k)
        if not e or v <= 0:
            continue
        f = v / 100.0
        for s, d in e.stats.items():
            mult[s] += d * f
        for m, d in e.mods.items():
            mods[m] = mods.get(m, 0.0) + d * f
    return {s: max(1 - CAP, min(1 + CAP, m)) for s, m in mult.items()}, mods


def dominant(slime, n: int = 3) -> List[Tuple[str, float]]:
    return sorted(((k, v) for k, v in slime.emotions.items() if v >= 8), key=lambda kv: -kv[1])[:n]


def battle_note(slime) -> str:
    """One line for the battle log when a strong feeling is steering the fight ('' if none)."""
    top = dominant(slime, 1)
    if not top or top[0][1] < 40:
        return ""
    k, v = top[0]
    e = EMOTIONS[k]
    mult, _ = modifiers(slime)
    eff = ", ".join(f"{s.upper()[:3]} {100 * (mult[s] - 1):+.0f}%" for s in STATS if abs(mult[s] - 1) >= 0.01)
    return f"{e.emoji} {slime.name} feels {e.name.lower()} ({int(v)}){' - ' + eff if eff else ''}"


def say(slime, rng: random.Random) -> str:
    top = dominant(slime, 1)
    if not top:
        return rng.choice(["...", "Just vibing.", "Nothing much. Goo things."])
    return rng.choice(EMOTIONS[top[0][0]].lines)
