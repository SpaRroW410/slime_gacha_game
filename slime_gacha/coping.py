"""Coping and comfort: what a slime does with a bad feeling, and how friends look after each other (docs/ROADMAP.md § 5).

People handle a bad feeling in their own way. When sadness, anger, fear, anxiety, loneliness or guilt passes
config.COPE_AT and a slime is at home and free, it acts on it (once a day) in the style its personality gives it:
  seek     (chatty)      goes to find a friend and talks it out
  help     (kind)        looks after someone else, which helps itself too
  busy     (proud)       throws itself into training
  face     (brave)       sets its jaw and faces it
  sleep    (lazy)        sleeps it off
  eat      (gluttonous)  comfort food
  withdraw (timid)       keeps to itself: calmer, but lonelier
  vent     (grumpy)      snaps at someone: the anger goes, but it may start a quarrel
  dwell    (anyone else) turns it over and over: it lingers
Healthy styles ease the feeling; venting and dwelling do not (dwelling makes it worse).

COMFORT: a friend at home who sees a friend down (sadness, fear, anxiety or loneliness at config.COMFORT_AT or more)
cheers it up, once a day: the feeling eases, a little sanity returns, and it is remembered with gratitude.
"""
import random
from typing import List, Optional, Tuple

from . import config, emotions, memory, sanity

BAD = ("sadness", "anger", "fear", "anxiety", "loneliness", "guilt")
STYLE_ORDER = (("chatty", "seek"), ("kind", "help"), ("proud", "busy"), ("brave", "face"), ("lazy", "sleep"),
               ("gluttonous", "eat"), ("timid", "withdraw"), ("grumpy", "vent"))
STYLE_TEXT = dict(seek="talks it out with a friend", help="looks after others", busy="throws itself into training",
                  face="faces it head on", sleep="sleeps it off", eat="reaches for comfort food",
                  withdraw="keeps to itself", vent="snaps at whoever is near", dwell="turns it over and over")


def style(s) -> str:
    for trait, st in STYLE_ORDER:
        if trait in s.traits:
            return st
    return "dwell"


def _home(s) -> bool:
    return not s.busy and s.state == "idle" and s.hp > 0


def worst(s) -> Optional[Tuple[str, float]]:
    bad = [(k, s.emotions.get(k, 0.0)) for k in BAD]
    k, v = max(bad, key=lambda kv: kv[1])
    return (k, v) if v >= config.COPE_AT else None


def cope(g, s, rng: random.Random, events: List[str]) -> bool:
    """Act on the worst bad feeling, in this slime's style. True if it did something."""
    w = worst(s)
    if not w or not _home(s):
        return False
    feeling, _ = w
    st = style(s)
    others = [o for o in g.slimes() if o.id != s.id and _home(o)]
    name = emotions.EMOTIONS[feeling].name.lower()
    if st == "seek":
        friends = sorted(others, key=lambda o: -g.social.bond(s, o))
        if not friends:
            st = "dwell"
        else:
            f = friends[0]
            emotions.soothe(s, feeling, config.COPE_EASE)
            s.needs.add("belonging", 10)
            g.social.add_bond(s, f, 1)
            events.append(f"💬 {s.name} is feeling {name} and goes to talk it out with {f.name}.")
    if st == "help":
        target = min(others, key=lambda o: o.needs.get("belonging"), default=None)
        if target:
            target.needs.add("belonging", 8)
            emotions.feel(target, "affection", 5)
            events.append(f"🤲 {s.name} is feeling {name}, and busies itself looking after {target.name}.")
        else:
            events.append(f"🤲 {s.name} is feeling {name}, and tidies up the colony for everyone.")
        emotions.soothe(s, feeling, config.COPE_EASE)
    elif st == "busy":
        g.practise(s, 1.0)
        s.needs.add("energy", -6)
        emotions.soothe(s, feeling, config.COPE_EASE * 0.8)
        events.append(f"🥊 {s.name} is feeling {name} and throws itself into training.")
    elif st == "face":
        emotions.feel(s, "determination", 10)
        emotions.soothe(s, feeling, config.COPE_EASE)
        events.append(f"😤 {s.name} is feeling {name}, sets its jaw and faces it.")
    elif st == "sleep":
        if s.needs.get("energy") < 90:
            s.state = "sleeping"
        emotions.soothe(s, feeling, config.COPE_EASE * 0.8)
        events.append(f"😴 {s.name} is feeling {name} and sleeps it off.")
    elif st == "eat":
        if g.wallet.get("food") >= 1:
            g.wallet.spend("food", 1)
            s.needs.add("food", config.FOOD_NUTRITION / 2)
        emotions.soothe(s, feeling, config.COPE_EASE * 0.7)
        events.append(f"🍙 {s.name} is feeling {name} and reaches for some comfort food.")
    elif st == "withdraw":
        emotions.soothe(s, feeling, config.COPE_EASE * 0.6)
        s.needs.add("belonging", -5)
        sanity.heal(s, 1)
        events.append(f"🫥 {s.name} is feeling {name} and keeps to itself for a while.")
    elif st == "vent":
        emotions.soothe(s, "anger", config.COPE_EASE * 1.5)
        target = rng.choice(others) if others else None
        if target:
            g.social.add_bond(s, target, -2)
            emotions.feel(target, "anger", 8, f"snapped at by {s.name}")
            if rng.random() < config.VENT_QUARREL * g.wary(s) and not g.conflicts.has_between(s.id, target.id):   # the Keeper's shadow holds it back
                g.conflicts.start(s, target, f"{s.name} snapping at them for no reason", starter=s.id)
            events.append(f"💢 {s.name} is feeling {name} and snaps at {target.name}.")
        else:
            events.append(f"💢 {s.name} is feeling {name} and kicks a pebble across the yard.")
    if st == "dwell":
        emotions.feel(s, feeling, config.COPE_DWELL)
        events.append(f"🌧 {s.name} is feeling {name} and keeps turning it over.")
    s.cared["coped"] = g.day
    return True


def comfort(g, s, rng: random.Random, events: List[str]) -> bool:
    """A friend at home notices this slime is down and cheers it up (once a day per slime)."""
    if not _home(s):
        return False
    down = [(k, s.emotions.get(k, 0.0)) for k in ("sadness", "fear", "anxiety", "loneliness")]
    k, v = max(down, key=lambda kv: kv[1])
    if v < config.COMFORT_AT:
        return False
    friends = [o for o in g.slimes() if o.id != s.id and _home(o) and g.social.bond(s, o) >= config.FRIEND_BOND
               and o.emotions.get(k, 0.0) < config.COMFORT_AT]
    if not friends:
        return False
    f = max(friends, key=lambda o: g.social.bond(s, o))
    emotions.soothe(s, k, config.COMFORT_EASE)
    sanity.heal(s, config.COMFORT_SANITY)
    emotions.feel(s, "affection", 6)
    emotions.feel(f, "affection", 4)
    memory.remember(s, "cheered", f, g.day, 2.0)
    s.cared["comforted"] = g.day
    events.append(f"🫂 {f.name} notices {s.name} is down and cheers them up.")
    return True


def contagion(g) -> None:
    """Strong moods spread a little among slimes away together in one party (fear in a dungeon, joy after a win)."""
    groups = {}
    for s in g.slimes():
        p = g.parties.party_of(s.id)
        if p and s.in_dungeon:
            groups.setdefault((p.id, s.in_dungeon), []).append(s)
    for members in groups.values():
        for k, gain in config.CONTAGION.items():
            if any(m.emotions.get(k, 0.0) >= config.CONTAGION_AT for m in members):
                for m in members:
                    if m.emotions.get(k, 0.0) < config.CONTAGION_AT:
                        emotions.feel(m, k, gain)


def hourly(g, events: List[str]) -> None:
    """Each hour: moods spread inside parties away together, friends comfort those who are down, and slimes act on a bad
    feeling (each at most once a day)."""
    rng = g.mood_rng
    contagion(g)
    lines = 0
    for s in g.slimes():
        if lines >= config.COPE_LINES_PER_HOUR:
            break
        out: List[str] = []
        if s.cared.get("comforted") != g.day and comfort(g, s, rng, out):
            pass
        elif s.cared.get("coped") != g.day:
            cope(g, s, rng, out)
        if out and g.coping_today < config.COPE_LINES_PER_DAY:
            events.extend(out)
            g.coping_today += len(out)
            lines += len(out)
