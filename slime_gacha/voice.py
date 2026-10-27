"""Voice: what a slime says when the Keeper talks with it (docs/ROADMAP.md § 5).

People talk about their actual lives: who they miss, who still owes them an apology, what they want, how the days feel.
A slime's answer comes, in order of how much it weighs on it, from:
  grief        the one it is mourning
  memories     its strongest recent memory of someone (a kindness, a grudge, a loss, being ignored)
  its goal     what it wants right now
  its days     burned out, or a good stretch of life
  a feeling    the strongest passing feeling (emotions.EMOTIONS lines)
It never says the same line twice within config.LINE_REPEAT_DAYS days (pick() remembers what it said).
"""
import random
from typing import List, Optional

from . import config, emotions, memory, meaning

MEMORY_LINES = {
    "lost": ["I keep thinking about {n}.", "{n} would have liked today.", "Sometimes I still look for {n}."],
    "snack": ["{n} took the last snack. I haven't forgotten.", "Next time I'm hiding my snacks from {n}."],
    "quarrel": ["{n} and I still aren't quite right.", "I'm not over what {n} said."],
    "brawl": ["{n} hasn't said sorry. Neither have I.", "I can still feel where {n} hit me."],
    "abandoned": ["Where was {n} when I went down?", "{n} left me out there."],
    "slight": ["{n} got what I wanted. Again."],
    "healed": ["{n} patched me up when I was hurt. I owe them.", "If it weren't for {n}, I'd still be limping.",
               "{n} has gentle hands.", "I should thank {n} properly one of these days."],
    "peace": ["{n} helped us make up. I'm glad."],
    "comforted": ["{n} sat with me when I couldn't stop crying.", "I don't know what I'd have done without {n}."],
    "cheered": ["{n} cheered me up the other day. That meant a lot.", "{n} always knows when I'm down."],
    "made_up": ["{n} and I talked it out. We're good now.", "Turns out {n} isn't so bad."],
    "comrade": ["{n} had my back out there.", "I'd fight beside {n} any day."],
    "carried": ["{n} stayed with me when I fell.", "{n} carried me home. I won't forget it."],
    "ignored": ["You didn't listen, last time I asked.", "I asked you for something once. Remember?"],
}
GOAL_LINES = {
    "stronger": ["I want to get stronger.", "One day I'll be the strongest slime here."],
    "master": ["I'm going to master {style} if it takes me all year."],
    "friend": ["I'd like to spend more time with {n}.", "Have you seen {n}? I was hoping to catch them."],
    "befriend": ["{n} seems nice. Maybe we could be friends?", "I've been meaning to say hello to {n}."],
    "court": ["Do you think {n} likes me?", "{n} has the nicest wobble, don't you think?"],
    "mentor": ["{n} is coming along nicely.", "I'm teaching {n} everything I know."],
    "explore": ["I wonder what's past the woods.", "There has to be more out there."],
    "craft": ["I want to make something. With my own goo.", "I've got an idea for something."],
    "rest": ["I could use a quiet day.", "Is it nap time yet?"],
    "praise": ["Did you see what I did?", "I've been doing really well, you know."],
    "rival": ["I'll show {n}.", "Next time, {n} won't know what hit them."],
    "calm": ["I just need some quiet.", "Please, not today."],
    "avoid_dungeons": ["I can't go back down there. Not after {n}.", "Don't ask me to go down there again."],
}
DAY_LINES = {
    "burnt": ["Same as yesterday. Same as tomorrow.", "It's fine. I do the work.", "Nothing much. Just... nothing much."],
    "good": ["Life's good here.", "I like it here. I really do.", "Today was a good day."],
}


def pick(s, pool: List[str], rng: random.Random, day: int, **fmt) -> str:
    """A line from `pool` this slime has not said in the last week (else the one said longest ago)."""
    said = meaning.life(s)["said"]
    lines = [p.format(**fmt) for p in pool]
    fresh = [l for l in lines if day - said.get(l, -99) >= config.LINE_REPEAT_DAYS]
    line = rng.choice(fresh) if fresh else min(lines, key=lambda l: said.get(l, -99))
    said[line] = day
    if len(said) > config.SAID_KEEP:
        for k in sorted(said, key=said.get)[:len(said) - config.SAID_KEEP]:
            del said[k]
    return line


def _candidates(g, s) -> List[tuple]:
    """(weight, pool, format) for everything it might talk about."""
    out = []
    if s.grief:
        x = max(s.grief, key=lambda x: x["depth"])
        out.append((3.0 + x["depth"] / 20, ["I miss {n}.", "I keep expecting {n} to come home.", "Everything reminds me of {n}."], dict(n=x["name"])))
    strong = sorted((m for m in s.memories if m["weight"] >= config.VOICE_MEMORY_MIN and m["kind"] in MEMORY_LINES),
                    key=lambda m: -m["weight"] * (0.5 if m["kind"] == "healed" else 1.0))[:1]   # being patched up is everyday
    for m in strong:
        out.append((0.8 + m["weight"] / 10, MEMORY_LINES[m["kind"]], dict(n=m.get("name") or "someone")))
    goal = s.goal or {}
    if goal.get("kind") in GOAL_LINES:
        other = g.roster.get(goal.get("target") or 0)
        from . import sparring
        disc = sparring.DISCIPLINES.get(s.arch.discipline)
        out.append((1.5, GOAL_LINES[goal["kind"]], dict(n=other.name if other else "them",
                                                       style=disc.style.lower() if disc else "my craft")))
    if meaning.burned_out(s):
        out.append((3.0, DAY_LINES["burnt"], {}))
    elif getattr(s, "content", 50) >= 70:
        out.append((1.0, DAY_LINES["good"], {}))
    top = emotions.dominant(s, 1)
    if top:
        out.append((1.0 + top[0][1] / 50, list(emotions.EMOTIONS[top[0][0]].lines), {}))
    return out


def say(g, s, rng: random.Random) -> str:
    """What the slime says about itself today."""
    cands = _candidates(g, s)
    if not cands:
        return pick(s, ["...", "Just vibing.", "Nothing much. Goo things.", "Same old, same old."], rng, g.day)
    total = sum(w for w, _, _ in cands)
    roll = rng.random() * total
    for w, pool, fmt in cands:
        roll -= w
        if roll <= 0:
            return pick(s, pool, rng, g.day, **fmt)
    w, pool, fmt = cands[-1]
    return pick(s, pool, rng, g.day, **fmt)
