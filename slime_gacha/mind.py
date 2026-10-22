"""The mind of a slime (phase 2 of the memory work): goals, decisions with reasons, requests to the Keeper, trust and drift.

  GOAL      Every few days a slime picks something it wants, from its memories, bonds and state: get stronger, beat a rival,
            be near a friend, be left alone, or never go back into the dungeons after a friend fell there. Idle slimes act on it.
  DECISION  Idle slimes at home act on their goal on their own (train, visit, sulk) and say why in the journal. A slime that
            cannot face the dungeons refuses them and says why (see Game.refusal).
  REQUEST   A slime may ask the Keeper for something: a rest day, to join a friend's party, to be moved away from someone it
            holds a grudge against, or for a post it fits. Granting or refusing moves its TRUST in the Keeper.
  TRUST     0-100 (starts at 50). Slimes that trust the Keeper put up with more (their mood threshold for refusing drops).
  DRIFT     Experience slowly rewrites traits: many knock-outs make a slime timid, many wins proud, much healing kind.
"""
import random
from typing import List

from . import config, jobs, memory, sanity
from .errors import InvalidAction
from .growth import add_xp

DRIFT_TRAITS = {"ko": "timid", "win": "proud", "heal": "kind"}


# ---- goals -------------------------------------------------------------------------------------------------------
def choose_goal(g, s) -> dict:
    """Pick the slime's goal from what it remembers and how it is."""
    for m in sorted(s.memories, key=lambda m: -m["weight"]):                 # a friend fell: it cannot face the dungeons
        if m["kind"] == "lost" and m["weight"] >= config.GOAL_AVOID_MIN and "battle" in (m.get("note") or ""):
            return dict(kind="avoid_dungeons", target=m["other"], day=g.day,
                        text=f"can't face the dungeons after {m['name']} fell")
    if sanity.frac(s) < 0.4:
        return dict(kind="calm", target=0, day=g.day, text="wants to be left alone for a while")
    best = None
    for m in s.memories:                                                        # the strongest living grudge: beat that rival
        if memory.KINDS[m["kind"]][0] < 0 and m["other"] in g.roster and (best is None or m["weight"] > best["weight"]):
            best = m
    if best and best["weight"] >= config.GOAL_RIVAL_MIN:
        return dict(kind="rival", target=best["other"], day=g.day, text=f"wants to prove themself against {best['name']}")
    friend, score = None, 0.0
    for o in g.slimes():
        if o.id == s.id:
            continue
        sc = memory.opinion(s, o)["gratitude"] + max(0.0, g.social.bond(s, o)) / 10.0
        if sc > score:
            friend, score = o, sc
    if friend and score >= config.GOAL_FRIEND_MIN:
        return dict(kind="friend", target=friend.id, day=g.day, text=f"wants to spend time with {friend.name}")
    return dict(kind="stronger", target=0, day=g.day, text="wants to get stronger")


def _rng(g, s, salt: int = 0) -> random.Random:
    """A dice stream per slime and day, so a saved game and its reload decide exactly the same."""
    return random.Random(((g.seed or 0) * 1000003 + g.day * 9176 + s.id * 31 + salt) & 0xFFFFFFFF)


def _free_at_home(g, s) -> bool:
    return s.state == "idle" and not s.in_dungeon and not s.job and not s.grounded and s.hp > 0


def decide(g, s, events: List[str]) -> bool:
    """An idle slime acts on its goal. Returns True if it did something worth a journal line."""
    goal = s.goal
    if not goal or not _free_at_home(g, s) or _rng(g, s, 1).random() > config.DECIDE_CHANCE:
        return False
    other = g.roster.get(goal.get("target", 0))
    k = goal["kind"]
    if k in ("stronger", "rival") and s.needs.get("energy") >= 40 and s.mood() >= 0.3:
        xp = max(4, int(s.level * config.GOAL_TRAIN_XP))
        add_xp(s, xp)
        s.needs.add("energy", -8)
        why = f"to beat {other.name}" if k == "rival" and other else "to get stronger"
        events.append(f"🎯 {s.name} trains on their own {why} (+{xp} XP).")
    elif k == "friend" and other and _free_at_home(g, other):
        g.social.add_bond(s, other, 3)
        for x in (s, other):
            x.needs.add("belonging", 8)
        events.append(f"🤝 {s.name} spends the day with {other.name}.")
    elif k in ("calm", "avoid_dungeons"):
        sanity.heal(s, 3)
        events.append(f"🫧 {s.name} {goal['text']} and keeps to themself (+3 sanity).")
    else:
        return False
    return True


# ---- requests ----------------------------------------------------------------------------------------------------
def make_request(g, s):
    """A request this slime would make to the Keeper right now, or None."""
    party = g.parties.party_of(s.id)
    if party and not g.party_activity(party.id):                              # a grudge against a party-mate
        for o in g.party_members(party.id):
            if o.id != s.id and memory.opinion(s, o)["grudge"] >= config.REQUEST_GRUDGE:
                return dict(kind="separate", target=o.id, day=g.day, party=party.id,
                            text=f"asks to be moved out of {party.name}: {o.name} is still on their mind")
    if sanity.frac(s) < 0.5 and s.state == "idle" and not s.in_dungeon:
        return dict(kind="rest", target=0, day=g.day, text="asks for a rest day: \"I can't keep going like this.\"")
    if not party and _free_at_home(g, s):
        for o in g.slimes():
            p = g.parties.party_of(o.id)
            if p and not g.party_activity(p.id) and len(p.members) < g.parties.size and \
                    memory.opinion(s, o)["gratitude"] + max(0.0, g.social.bond(s, o)) / 10.0 >= config.REQUEST_FRIEND:
                return dict(kind="join_party", target=o.id, day=g.day, party=p.id, text=f"asks to join {o.name}'s party, {p.name}")
    if _free_at_home(g, s):
        for key, job in jobs.JOBS.items():
            if job.classes and s.archetype in job.classes and len(jobs.workers(g, key)) < jobs.slots(g, key) and not jobs.why_not(g, s, key):
                return dict(kind="post", target=0, day=g.day, job=key, text=f"asks for the {job.name.lower()} post")
    return None


def _replacement(g, pid: int, leaver):
    """The best free, healthy slime at home to fill the place the leaver left, avoiding anyone the party-mates hold a grudge against."""
    p = g.parties.get(pid)
    if len(p.members) >= g.parties.size or g.party_activity(pid):
        return None
    mates = [g.roster[i] for i in p.members if i in g.roster]
    ok = [o for o in g.slimes() if o.id != leaver.id and not g.parties.party_of(o.id) and _free_at_home(g, o) and not g.refusal(o, "dungeon")
          and o.hp >= o.max_hp * 0.6 and all(memory.opinion(m, o)["grudge"] < config.REQUEST_GRUDGE and memory.opinion(o, m)["grudge"] < config.REQUEST_GRUDGE for m in mates)]
    return max(ok, key=lambda o: (o.level, o.power_rating()), default=None)


def answer(g, sid: int, accept: bool) -> str:
    s = g.slime(sid)
    r = s.request
    if not r:
        raise InvalidAction(f"{s.name} has no request.")
    s.request = None
    if not accept:
        s.trust = max(0.0, s.trust - (config.TRUST_DENY_REST if r["kind"] == "rest" else config.TRUST_DENY))
        if r["kind"] == "rest":
            sanity.hit(s, 3)
        memory.remember(s, "ignored", None, g.day, 2.0, f" ({r['text'].split(':')[0].replace('asks', 'asked')})")
        return f"You turned {s.name} down. They will remember it. (trust {int(s.trust)})"
    k = r["kind"]
    if k == "rest":
        sanity.heal(s, 12)
        s.needs.add("energy", 25)
        msg = f"{s.name} takes a rest day (+12 sanity)."
    elif k == "join_party":
        p = g.parties.get(r["party"])
        if g.party_activity(p.id) or len(p.members) >= g.parties.size:
            raise InvalidAction(f"{p.name} has no room right now.")
        g.parties.add(p.id, s.id)
        msg = f"{s.name} joins {p.name}."
    elif k == "separate":
        pid = r.get("party")
        g.party_remove(s.id)
        sanity.heal(s, 4)
        msg = f"{s.name} leaves the party, relieved."
        sub = _replacement(g, pid, s) if pid in g.parties.parties else None       # a party needs a full roster to go anywhere
        if sub:
            g.parties.add(pid, sub.id)
            msg += f" {sub.name} takes the empty place in {g.parties.get(pid).name}."
        else:
            msg += f" {g.parties.get(pid).name} is one short now: fill the place from the Parties tab." if pid in g.parties.parties else ""
    else:
        msg = jobs.assign(g, s, r["job"])
    s.trust = min(100.0, s.trust + config.TRUST_GRANT)
    return f"{msg} They trust you more (trust {int(s.trust)})."


# ---- drift -------------------------------------------------------------------------------------------------------
def note(s, what: str, n: int = 1) -> None:
    s.drift[what] = s.drift.get(what, 0) + n


def drift(g, s, events: List[str]) -> None:
    for what, trait in DRIFT_TRAITS.items():
        if s.drift.get(what, 0) >= config.DRIFT_AT[what] and trait not in s.traits:
            old = s.traits[-1]
            s.traits[-1] = trait
            s.drift[what] = 0
            why = {"ko": "being knocked out so often", "win": "all those victories", "heal": "tending so many others"}[what]
            events.append(f"🌱 {s.name} has become {trait} after {why} (no longer {old}).")


# ---- the daily round ---------------------------------------------------------------------------------------------
def daily(g, events: List[str]) -> None:
    acted = 0
    for s in g.slimes():
        if s.goal is None or g.day - s.goal.get("day", 0) >= config.GOAL_DAYS:
            s.goal = choose_goal(g, s)
        if acted < config.DECIDE_MAX_EVENTS and decide(g, s, events):
            acted += 1
        if s.request and g.day - s.request["day"] >= config.REQUEST_DAYS:
            s.request = None
            s.trust = max(0.0, s.trust - 1)                           # unanswered: a little hurt
        if s.request is None and _rng(g, s, 2).random() < config.REQUEST_CHANCE:
            r = make_request(g, s)
            if r:
                s.request = r
                events.append(f"💬 {s.name} {r['text']}.")
        drift(g, s, events)
