"""Memory: what a slime remembers, and what it feels about each other slime because of it.

Each slime keeps a short list of events that mattered to it (`s.memories`): who ate its snack, who tended it when it was hurt,
who fought beside it, who fell and where. Memories fade (they lose weight every game day) and the oldest are forgotten.
From them comes an OPINION of every other slime: a grudge (things that hurt) and gratitude (things that helped). Opinions
shape quarrels: the chance goes up with grudges and down with gratitude, and the REASON of a quarrel is the actual grievance
("Slip took the last snack and left Bonk hungry") instead of a random line. Phase 2 (decisions, goals) builds on this.

A memory is a dict: kind, other (slime id, 0 = nobody in particular), name (that slime's name), day, weight (0-10), note.
"""
from typing import Dict, List, Optional

from . import config

# kind -> (sign: -1 grudge / +1 gratitude / 0 neutral, text template for the owner's point of view; {n} = the other's name, {note} = detail)
KINDS: Dict[str, tuple] = {
    "snack":     (-1, "{n} ate the last snack and left them hungry{note}"),
    "quarrel":   (-1, "{n} picked a fight over {note}"),
    "brawl":     (-1, "{n} came to blows with them"),
    "abandoned": (-1, "{n} was nowhere to be found when they fell{note}"),
    "slight":    (-1, "{n} got something they wanted{note}"),
    "healed":    (+1, "{n} tended to them when they were hurt"),
    "peace":     (+1, "{n} helped them make peace{note}"),
    "made_up":   (+1, "{n} made peace with them after a quarrel"),
    "comrade":   (+1, "{n} fought beside them and won{note}"),
    "carried":   (+1, "{n} stayed close when they fell{note}"),
    "lost":      (0,  "{n} was lost{note}"),
    "ignored":   (-1, "You did not listen when they asked for help{note}"),
}


def remember(s, kind: str, other, day: int, weight: float = 3.0, note: str = "") -> None:
    """Record a memory on slime `s` about slime `other` (a Slime or None). Merges with a recent identical one."""
    if kind not in KINDS:
        return
    oid = other.id if other is not None else 0
    name = other.name if other is not None else ""
    for m in s.memories:
        if m["kind"] == kind and m["other"] == oid and day - m["day"] <= config.MEMORY_MERGE_DAYS:
            m["weight"] = min(config.MEMORY_MAX_WEIGHT, m["weight"] + weight * 0.5)
            m["day"] = day
            if note:
                m["note"] = note
            return
    s.memories.append(dict(kind=kind, other=oid, name=name, day=day, weight=min(config.MEMORY_MAX_WEIGHT, weight), note=note))
    if len(s.memories) > config.MEMORY_CAP:               # forget the faintest
        s.memories.remove(min(s.memories, key=lambda m: m["weight"]))


def fade(s) -> None:
    """Daily: every memory loses weight; faint ones vanish. Strong grudges and gratitude last for weeks."""
    keep = []
    for m in s.memories:
        m["weight"] = round(m["weight"] * config.MEMORY_FADE, 3)
        if m["weight"] >= config.MEMORY_MIN_WEIGHT:
            keep.append(m)
    s.memories = keep


def opinion(a, b) -> Dict[str, float]:
    """What `a` feels about `b` from what it remembers: {"grudge", "gratitude"} (0 and up)."""
    g = t = 0.0
    for m in a.memories:
        if m["other"] == b.id:
            sign = KINDS[m["kind"]][0]
            if sign < 0:
                g += m["weight"]
            elif sign > 0:
                t += m["weight"]
    return dict(grudge=g, gratitude=t)


def for_pair(a, b) -> tuple:
    """(quarrel-chance factor, stated reason or None) for a pair; cheap when neither remembers anything."""
    if not a.memories and not b.memories:
        return 1.0, None
    return chance_factor(a, b), grievance(a, b)


def chance_factor(a, b) -> float:
    """Multiplier on the quarrel chance between a and b from their shared history (either side's grudge, either's thanks)."""
    oa, ob = opinion(a, b), opinion(b, a)
    grudge, thanks = oa["grudge"] + ob["grudge"], oa["gratitude"] + ob["gratitude"]
    return max(0.3, min(4.0, 1 + 0.12 * grudge - 0.08 * thanks))


def text(owner, m: dict) -> str:
    sign, tpl = KINDS[m["kind"]]
    note = m.get("note") or ""
    return tpl.format(n=m.get("name") or "someone", note=(" " + note) if note and not note.startswith(("(", ",", ".")) else note)


def grievance(a, b) -> Optional[str]:
    """The strongest grudge either holds against the other, as a sentence naming who and what; None if there is none worth a fight."""
    best = None
    for owner, other in ((a, b), (b, a)):
        for m in owner.memories:
            if m["other"] == other.id and KINDS[m["kind"]][0] < 0 and m["weight"] >= config.MEMORY_GRUDGE_MIN:
                if best is None or m["weight"] > best[1]["weight"]:
                    best = (owner, m)
    if best is None:
        return None
    owner, m = best
    return f"{owner.name}'s grudge: {text(owner, m).replace(m['name'] or 'someone', m['name'] or 'someone', 1)}"


def recent(s, n: int = 6) -> List[dict]:
    """The strongest recent memories, for the slime card."""
    ms = sorted(s.memories, key=lambda m: (m["weight"] + m["day"] * 0.001), reverse=True)[:n]
    return [dict(kind=m["kind"], day=m["day"], weight=round(m["weight"], 1), text=text(s, m), sign=KINDS[m["kind"]][0]) for m in ms]
