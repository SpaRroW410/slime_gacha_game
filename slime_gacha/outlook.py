"""Outlook: how a slime comes to see itself, shaped by what it actually does.

Every slime counts its experiences (sparring, Pit runs, dungeon floors, scouting, hunting, studying). Once one
kind clearly dominates it becomes the slime's *outlook*, a small passive perk, and the thing it asks for when it
wants to feel proud (esteem). A first draft of the "slimes think differently depending on training / Pit /
dungeons" idea; extend OUTLOOKS to add more.
"""
from dataclasses import dataclass
from typing import Optional

from . import config


@dataclass(frozen=True)
class Outlook:
    key: str          # also the experience counter it comes from
    name: str
    emoji: str
    perk: str
    wish: str         # what it wants to do when it needs esteem


OUTLOOKS = {o.key: o for o in [
    Outlook("spar", "Duelist", "🥊", "+10% fighting-style xp", "wants to spar"),
    Outlook("pit", "Grinder", "🫧", "+10% Pit xp; knock-outs cost 30% less xp and 40% less morale", "wants to hit the Pit"),
    Outlook("delve", "Delver", "🕳", "+5% party power in the Hollow Descent (by share of Delvers)", "wants to delve deeper"),
    Outlook("scout", "Pathfinder", "🔭", "+0.1 scouting skill", "wants to explore"),
    Outlook("hunt", "Forager", "🏞", "+10% hunt loot", "wants to go hunting"),
    Outlook("study", "Scholar", "📖", "+10% study xp, +5% research odds", "wants to study"),
]}


def bump(slime, kind: str, n: int = 1) -> None:
    """Record experience; doing your favourite thing also lifts esteem."""
    before = outlook_key(slime)
    slime.exp[kind] = slime.exp.get(kind, 0) + n
    if before == kind:
        slime.needs.add("esteem", config.OUTLOOK_ESTEEM)


def outlook_key(slime) -> Optional[str]:
    ranked = sorted(((v, k) for k, v in slime.exp.items() if k in OUTLOOKS), reverse=True)
    if not ranked or ranked[0][0] < config.OUTLOOK_MIN:
        return None
    if len(ranked) > 1 and ranked[0][0] < ranked[1][0] * config.OUTLOOK_LEAD:
        return None
    return ranked[0][1]


def outlook_of(slime) -> Optional[Outlook]:
    k = outlook_key(slime)
    return OUTLOOKS[k] if k else None


def has(slime, kind: str) -> bool:
    return outlook_key(slime) == kind
