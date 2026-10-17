"""Floor modifiers: a condition that lies over a whole floor of the Hollow Descent and changes the fight for it.

A modifier is a handful of the battle's own status mechanics (fx.py buffs / debuffs, poison) applied to the party and /
or the foes when the fight begins. Scouting a floor (knowledge 40%+) reveals its modifier. Modifiers are drawn from the
dungeon seed, so a scouted floor always plays as reported. Boss floors never have one.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import fx

WHOLE_FIGHT = 99                       # turns: a modifier lasts the whole fight


@dataclass(frozen=True)
class Modifier:
    key: str
    name: str
    emoji: str
    desc: str
    party: Tuple[tuple, ...] = ()      # ("buff" | "debuff", name, amount) applied to the party at the start
    foes: Tuple[tuple, ...] = ()       # ... and to the foes
    poison: float = 0.0                # share of max HP lost per turn for 4 turns, everyone starts poisoned
    boon: bool = False                 # a kindness rather than a hardship


MODIFIERS: Dict[str, Modifier] = {m.key: m for m in (
    Modifier("poison_fog", "Poison Fog", "☠️", "A sickly green fog: everyone starts the fight poisoned.", poison=0.03),
    Modifier("darkness", "Darkness", "🌑", "Nobody sees well: everyone is harder to hit.",
             party=(("buff", "evasion", 0.18),), foes=(("buff", "evasion", 0.18),)),
    Modifier("thin_air", "Thin Air", "🌬️", "Breathless going: everyone is slower.",
             party=(("debuff", "spd", 0.2),), foes=(("debuff", "spd", 0.2),)),
    Modifier("brittle", "Brittle Ground", "🪨", "Cracked, shifting stone: everyone's armor counts for less.",
             party=(("debuff", "defense", 0.2),), foes=(("debuff", "defense", 0.2),)),
    Modifier("bloodlust", "Bloodlust", "🩸", "The air smells of blood: the foes hit harder and the party crits more.",
             party=(("buff", "crit_rate", 0.1),), foes=(("buff", "atk", 0.2),)),
    Modifier("sacred_spring", "Sacred Spring", "⛲", "A clear spring: the party mends a little every round.",
             party=(("buff", "regen", 0.04),), boon=True),
)}
ORDER = list(MODIFIERS)


def get(key: str) -> Optional[Modifier]:
    return MODIFIERS.get(key)


def apply(mod: Modifier, party_side: List, foe_side: List) -> List[str]:
    """Put the modifier's statuses on the combatants; returns log lines."""
    for c in party_side:
        for kind, name, amount in mod.party:
            fx.add_buff(c, name, amount if kind == "buff" else -amount, WHOLE_FIGHT)
    for c in foe_side:
        for kind, name, amount in mod.foes:
            fx.add_buff(c, name, amount if kind == "buff" else -amount, WHOLE_FIGHT)
    if mod.poison:
        for c in party_side + foe_side:
            c.poison = (4, max(1, int(c.max_hp * mod.poison)))
    return [f"{mod.emoji} {mod.name}: {mod.desc}"]


def describe(mod: Modifier) -> str:
    return f"{mod.emoji} {mod.name}: {mod.desc}"
