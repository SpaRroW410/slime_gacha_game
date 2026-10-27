"""Rituals: the days that give a colony's year its shape (docs: Guide > Slimes > Hatch days and feasts, docs/MINDS.md).

  HATCH DAY    every config.HATCH_EVERY days after a slime was pulled (or born). The first time the Keeper talks with it, pets
               or praises it that day, it notices it was remembered: joy, trust, and the care counts double. Forgetting costs
               nothing - but remembering is noticed.
  ANNIVERSARY  a couple marks every config.HATCH_EVERY days together: affection and joy for both.
  FEAST        after a boss falls in the Hollow Descent, the next dinner is a feast: everyone at home eats together, is glad,
               and grows a little closer to everyone else at the table.
"""
from typing import List

from . import config, emotions, meaning


def born(s) -> int:
    """The game day it was pulled or born (older saves did not record it: spread over a month by id)."""
    return s.born if s.born is not None else -(s.id % config.HATCH_EVERY)


def is_hatch_day(g, s) -> bool:
    age = g.day - born(s)
    return age > 0 and age % config.HATCH_EVERY == 0


def next_hatch_in(g, s) -> int:
    """Days until its next hatch day (0 = today)."""
    age = g.day - born(s)
    if age > 0 and age % config.HATCH_EVERY == 0:
        return 0
    return config.HATCH_EVERY - age % config.HATCH_EVERY


def remembered(g, s) -> str:
    """Called on the Keeper's talk, pat or praise: on its hatch day the first one is noticed. Returns a note or ''."""
    if not is_hatch_day(g, s) or s.cared.get("hatch") == g.day:
        return ""
    s.cared["hatch"] = g.day
    emotions.feel(s, "joy", config.HATCH_JOY)
    emotions.feel(s, "affection", 10)
    s.trust = min(100.0, s.trust + config.HATCH_TRUST)
    meaning.note(s, "care", 0.3)
    return f" 🎂 You remembered it's {s.name}'s hatch day! They light up."


def daily(g, events: List[str]) -> None:
    """Announce hatch days and couple anniversaries."""
    hatch = [s for s in g.slimes() if is_hatch_day(g, s)]
    if hatch:
        names = ", ".join(f"{s.name} ({(g.day - born(s)) // config.HATCH_EVERY} month{'s' if (g.day - born(s)) // config.HATCH_EVERY > 1 else ''})"
                          for s in hatch[:5])
        events.append(f"🎂 Hatch day today: {names}{' and more' if len(hatch) > 5 else ''}. A word from you would mean a lot.")
    for k, r in g.relations.rel.items():
        if r["kind"] != "couple":
            continue
        together = g.day - r.get("since", g.day)
        if together > 0 and together % config.HATCH_EVERY == 0:
            a, b = (g.roster.get(i) for i in k)
            if a and b:
                for x in (a, b):
                    emotions.feel(x, "affection", 10)
                    emotions.feel(x, "joy", 8)
                events.append(f"💘 {a.name} and {b.name} have been together {together // config.HATCH_EVERY} month(s) today.")


def feast(g, events: List[str]) -> bool:
    """At dinner after a boss fell: everyone at home eats together and is glad. True if a feast was held."""
    if not g.feast:
        return False
    guests = [s for s in g.slimes() if not s.busy and s.hp > 0 and s.state in ("idle", "resting")]
    if not guests:
        return False
    for s in guests:
        if g.wallet.get("food") >= 1:
            g.wallet.spend("food", 1)
            s.needs.add("food", config.FOOD_NUTRITION)
        s.needs.add("belonging", 10)
        emotions.feel(s, "joy", config.FEAST_JOY)
    for i, a in enumerate(guests):
        for b in guests[i + 1:]:
            g.social.add_bond(a, b, config.FEAST_BOND)
    events.append(f"🎉 A feast for {g.feast}! {len(guests)} slimes eat, sing and tell the story again.")
    g.feast = ""
    return True
