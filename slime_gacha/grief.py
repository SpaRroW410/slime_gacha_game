"""Grief: losing someone lasts (docs: Guide > Slimes > Grief, docs/MINDS.md).

When a slime dies (or is sacrificed, or leaves the colony), everyone who was close to it starts grieving. How deep depends on
the tie: a partner most, then a best friend, a mentor or mentee, a friend, and a little for someone it merely got on with.
Grief holds a slime's sadness and loneliness up (emotions.baseline) and fades over one to three weeks:
  - faster with company: a friend at home sits with it (and is remembered for it), and the Keeper's daily talk helps;
  - in waves: it comes back on each weekly anniversary, and when the slime walks into the dungeon where the loss happened;
  - a gathering at the Memorial Pond (the Keeper's call, within a week of a death) eases everyone grieving that slime and
    brings the mourners closer.
"""
from typing import List

from . import config, emotions, memory, sanity

DEPTH = {"couple": 90, "best_friend": 70, "mentor": 50, "friend": 45}


def depth_for(g, o, lost) -> float:
    kind = g.relations.kind(o, lost)
    if kind in DEPTH:
        return float(DEPTH[kind])
    return float(config.GRIEF_ACQUAINTANCE) if g.social.bond(o, lost) >= config.GRIEF_BOND else 0.0


def start(g, lost, where: str = "", scale: float = 1.0) -> None:
    """Everyone close to `lost` begins to grieve it. Call before the ties are forgotten."""
    for o in g.slimes():
        if o.id == lost.id:
            continue
        d = depth_for(g, o, lost) * scale
        if d > 0:
            o.grief = [x for x in o.grief if x["other"] != lost.id] + [
                dict(other=lost.id, name=lost.name, depth=round(d, 1), start=round(d, 1), day=g.day, where=where, gathered=False)]


weight = emotions.grief_weight


def _at_home(s) -> bool:
    return not s.busy and s.state in ("idle", "resting", "sleeping")


def daily(g, events: List[str]) -> None:
    """Once a day: grief fades (faster with company), and anniversaries and places bring it back."""
    lines = 0
    for s in g.slimes():
        if not s.grief:
            continue
        comforter = None
        if _at_home(s):
            friends = [f for f in g.slimes() if f.id != s.id and _at_home(f) and g.social.bond(s, f) >= config.FRIEND_BOND]
            comforter = max(friends, key=lambda f: g.social.bond(s, f), default=None)
        talked = s.cared.get("day") == g.day and s.cared.get("talk")
        for x in list(s.grief):
            x["depth"] = round(x["depth"] - config.GRIEF_FADE - (config.GRIEF_COMFORT if comforter else 0.0)
                               - (config.GRIEF_TALK if talked else 0.0), 1)
            age = g.day - x["day"]
            if x["depth"] <= 0:
                s.grief.remove(x)
                if x["start"] >= DEPTH["friend"] and lines < config.GRIEF_LINES:
                    events.append(f"🕯 {s.name} has made some peace with losing {x['name']}.")
                    lines += 1
                continue
            if age > 0 and age % 7 == 0:                                       # a week ago today
                emotions.feel(s, "sadness", config.GRIEF_WAVE * x["depth"], f"{x['name']}'s anniversary")
                if lines < config.GRIEF_LINES:
                    events.append(f"🕯 {s.name} remembers {x['name']}: it was {age // 7} week{'s' if age > 7 else ''} ago today.")
                    lines += 1
            if x["where"] and s.in_dungeon == x["where"]:                     # back where it happened
                emotions.feel(s, "sadness", config.GRIEF_PLACE * x["depth"], f"back where {x['name']} was lost")
                emotions.feel(s, "fear", 5)
        if comforter and s.grief:
            memory.remember(s, "comforted", comforter, g.day, 2.0)
            emotions.feel(comforter, "affection", 5)
            if lines < config.GRIEF_LINES:
                events.append(f"🫂 {comforter.name} sits with {s.name} for a while.")
                lines += 1


def gather(g, entry: dict) -> List[str]:
    """A gathering at the Memorial Pond for one who died: everyone at home grieving them is eased, and the mourners grow closer."""
    lost = entry["id"]
    mourners = [s for s in g.slimes() if _at_home(s) and any(x["other"] == lost and not x["gathered"] for x in s.grief)]
    if not mourners:
        return []
    for s in mourners:
        for x in s.grief:
            if x["other"] == lost:
                x["depth"] = max(0.0, round(x["depth"] - config.GRIEF_GATHER, 1))
                x["gathered"] = True
        s.grief = [x for x in s.grief if x["depth"] > 0]
        sanity.heal(s, config.GRIEF_GATHER_SANITY)
        emotions.feel(s, "calm", 12)
        emotions.feel(s, "affection", 8)
    for i, a in enumerate(mourners):
        for b in mourners[i + 1:]:
            g.social.add_bond(a, b, config.GRIEF_GATHER_BOND)
    names = ", ".join(s.name for s in mourners[:6]) + (f" and {len(mourners) - 6} more" if len(mourners) > 6 else "")
    return [f"🕯 The colony gathers at the Memorial Pond for {entry['name']}. {names} share what they remember."]
