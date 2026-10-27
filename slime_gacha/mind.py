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

from . import awakening, config, emotions, jobs, meaning, memory, outlook, sanity, sparring
from .errors import InvalidAction
from .growth import add_xp

DRIFT_TRAITS = {"ko": "timid", "win": "proud", "heal": "kind"}


# ---- goals -------------------------------------------------------------------------------------------------------
def choose_goal(g, s) -> dict:
    """Pick the slime's goal. A hard memory or a fraying mind comes first (it cannot face the dungeons, it wants to be left
    alone); otherwise it draws from the ordinary things people want - get better at something, see a friend, make a new one,
    court someone, look after a mentee, explore, make something, take it easy, be noticed - weighted by its traits, outlook,
    needs and ties. A grudge is one candidate among them, not the default."""
    for m in sorted(s.memories, key=lambda m: -m["weight"]):                 # a friend fell: it cannot face the dungeons
        if m["kind"] == "lost" and m["weight"] >= config.GOAL_AVOID_MIN and "battle" in (m.get("note") or ""):
            return dict(kind="avoid_dungeons", target=m["other"], day=g.day,
                        text=f"can't face the dungeons after {m['name']} fell")
    if sanity.frac(s) < 0.4:
        return dict(kind="calm", target=0, day=g.day, text="wants to be left alone for a while")
    options = [(w, goal) for w, goal in _goal_options(g, s) if w > 0]
    total = sum(w for w, _ in options)
    roll = _rng(g, s, 3).random() * total
    for w, goal in options:
        roll -= w
        if roll <= 0:
            return dict(goal, day=g.day)
    return dict(options[-1][1], day=g.day)


def _goal_options(g, s) -> List[tuple]:
    """(weight, goal) for every everyday goal this slime could have right now."""
    traits = set(s.traits)
    out = []
    disc = sparring.DISCIPLINES.get(s.arch.discipline)
    out.append((1.0 + 0.5 * bool(traits & {"brave", "proud"}), dict(kind="stronger", target=0, text="wants to get stronger")))
    out.append((1.0 + (1.0 if outlook.has(s, "spar") else 0.0) + 0.5 * ("brave" in traits),
                dict(kind="master", target=0, text=f"wants to master {disc.style.lower() if disc else 'its craft'}")))
    others = [o for o in g.slimes() if o.id != s.id]
    friend, score = None, 0.0
    for o in others:
        sc = memory.opinion(s, o)["gratitude"] + max(0.0, g.social.bond(s, o)) / 10.0
        if sc > score:
            friend, score = o, sc
    if friend and score >= config.GOAL_FRIEND_MIN:
        out.append((2.0 + ("chatty" in traits), dict(kind="friend", target=friend.id, text=f"wants to spend time with {friend.name}")))
    new = [o for o in others if g.social.bond(s, o) < config.FRIEND_BOND and g.social.compat(s, o) >= 10
           and frozenset((s.id, o.id)) not in g.conflicts.cold]
    if new:
        o = max(new, key=lambda o: g.social.compat(s, o))
        out.append((1.0 + 1.5 * ("chatty" in traits) + 0.5 * ("kind" in traits) - 0.5 * ("timid" in traits),
                    dict(kind="befriend", target=o.id, text=f"wants to make friends with {o.name}")))
    if not g.relations.partner(s.id):
        sweet = [o for o in others if g.social.bond(s, o) >= config.GOAL_COURT_BOND and g.social.compat(s, o) >= 25
                 and not g.relations.partner(o.id) and not g.relations.kin(s, o)]
        if sweet:
            o = max(sweet, key=lambda o: g.social.bond(s, o))
            out.append((1.5, dict(kind="court", target=o.id, text=f"is sweet on {o.name}")))
    for mid in g.relations.mentees(s.id):
        if mid in g.roster:
            out.append((2.0, dict(kind="mentor", target=mid, text=f"wants to look after {g.roster[mid].name}, its mentee")))
            break
    out.append((0.6 + 1.5 * (outlook.has(s, "scout") or outlook.has(s, "hunt")),
                dict(kind="explore", target=0, text="wants to see what lies beyond the colony")))
    out.append((0.6 + 1.0 * bool(s.job), dict(kind="craft", target=0, text="wants to make something with its own hands")))
    out.append((0.3 + 1.5 * ("lazy" in traits) + 1.0 * (s.needs.get("energy") < 40),
                dict(kind="rest", target=0, text="wants a quiet day")))
    out.append((0.3 + 1.5 * ("proud" in traits) + 1.0 * (s.needs.get("esteem") < 40),
                dict(kind="praise", target=0, text="wants to be noticed")))
    best = None
    for m in s.memories:                                                        # the strongest living grudge: beat that rival
        if memory.KINDS[m["kind"]][0] < 0 and m["other"] in g.roster and (best is None or m["weight"] > best["weight"]):
            best = m
    if best and best["weight"] >= config.GOAL_RIVAL_MIN:
        w = 0.4 * best["weight"] / config.GOAL_RIVAL_MIN
        w *= 1.5 if traits & {"grumpy", "proud"} else 0.5 if "kind" in traits else 1.0
        out.append((w, dict(kind="rival", target=best["other"], text=f"wants to prove themself against {best['name']}")))
    return out


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
    elif k == "master" and s.needs.get("energy") >= 40:
        disc = sparring.DISCIPLINES.get(s.arch.discipline)
        sparring.gain_style_xp(s, s.arch.discipline, config.GOAL_STYLE_XP, g.buildings.style_cap())
        g.practise(s, 1.0)
        s.needs.add("energy", -6)
        events.append(f"🎯 {s.name} practises {disc.style.lower() if disc else 'its craft'} on their own.")
    elif k in ("befriend", "court", "mentor") and other and _free_at_home(g, other):
        if k == "befriend":
            g.social.add_bond(s, other, 3)
            for x in (s, other):
                x.needs.add("belonging", 5)
            events.append(f"👋 {s.name} strikes up a conversation with {other.name}.")
        elif k == "court":
            g.social.add_bond(s, other, 4)
            for x in (s, other):
                emotions.feel(x, "affection", 10)
            events.append(f"🌸 {s.name} brings {other.name} a little flower.")
        else:
            add_xp(other, max(4, int(other.level * config.GOAL_TRAIN_XP)))
            g.social.add_bond(s, other, 2)
            emotions.feel(s, "pride", 8)
            events.append(f"🎓 {s.name} gives {other.name} a lesson.")
    elif k == "explore":
        emotions.feel(s, "wonder", 8)
        s.needs.add("esteem", 4)
        found = ""
        if _rng(g, s, 4).random() < 0.3:
            herb = _rng(g, s, 5).choice(config.HERBS)
            g.wallet.add(f"herb_{herb}", 1)
            found = f" and comes back with a {herb} herb"
        events.append(f"🧭 {s.name} wanders the edge of the woods, just to see what is there{found}.")
    elif k == "craft":
        what = _rng(g, s, 4).choice(("scrap", "food"))
        g.wallet.add(what, 1)
        emotions.feel(s, "pride", 6)
        events.append(f"🔧 {s.name} makes something small with their own hands (+1 {what}).")
    elif k == "rest":
        s.needs.add("energy", 15)
        sanity.heal(s, 2)
        emotions.feel(s, "calm", 8)
        events.append(f"☁ {s.name} takes it easy today.")
    elif k == "praise":
        s.needs.add("esteem", 6)
        emotions.feel(s, "pride", 8)
        events.append(f"✨ {s.name} shows off to anyone who will watch.")
    else:
        return False
    awakening.note(s, "chose")                                                   # it decided for itself
    return True


# ---- requests ----------------------------------------------------------------------------------------------------
LEAVE_TEXT = {"despair": "asks to leave the colony: \"I can't stay here any more. Please let me go.\"",
              "cog": "asks to leave the colony: \"There has to be more than this somewhere.\"",
              "low": "asks to leave the colony: \"I'm breaking here, and I don't trust it will change.\""}


def urgent_request(g, s):
    """A request that does not wait for the daily chance: to leave the colony (long despair, a long stretch as a cog, or days
    of breaking sanity without trust), or a cog asking for a change of routine."""
    asked = any(m["kind"] == "ignored" and "asked to leave" in (m.get("note") or "") and g.day - m["day"] < config.LEAVE_ASK_AGAIN_DAYS
                for m in s.memories)                                         # turned down: it waits a few days before asking again
    if awakening.wants_to_leave(s) and not asked:
        why = "despair" if awakening.outcome(s) == "despair" else "cog"
        return dict(kind="leave", target=0, day=g.day, why=why, text=LEAVE_TEXT[why])
    if s.low_days >= config.LEAVE_SANITY_DAYS and s.trust < config.LEAVE_TRUST and not asked:
        return dict(kind="leave", target=0, day=g.day, why="low", text=LEAVE_TEXT["low"])
    if (awakening.wants_change(s) or meaning.burned_out(s)) and s.job:
        return dict(kind="change", target=0, day=g.day,
                    text="asks to be taken off their post: \"I'd like to choose what I do for a while.\"")
    return None


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


def answer(g, sid: int, accept: bool) -> str:
    s = g.slime(sid)
    r = s.request
    if not r:
        raise InvalidAction(f"{s.name} has no request.")
    s.request = None
    if not accept:
        s.trust = max(0.0, s.trust - (config.TRUST_DENY_REST if r["kind"] in ("rest", "leave") else config.TRUST_DENY))
        if r["kind"] in ("rest", "leave"):
            sanity.hit(s, 3)
        if r["kind"] == "leave":
            memory.remember(s, "ignored", None, g.day, 3.0, " (asked to leave)")
            return f"{s.name} stays, because you asked. They will remember it. (trust {int(s.trust)})"
        memory.remember(s, "ignored", None, g.day, 2.0, f" ({r['text'].split(':')[0].replace('asks', 'asked')})")
        return f"You turned {s.name} down. They will remember it. (trust {int(s.trust)})"
    k = r["kind"]
    if k == "leave":
        return " ".join(g.depart(s, r.get("why", "")))
    awakening.note(s, "care", 0.3)                                              # being listened to
    awakening.note(s, "chose")
    if k == "change":
        msg = jobs.stop(g, s) if s.job else f"{s.name} is free to choose."
        if getattr(s, "life", None):
            s.life["post_streak"] = 0
            s.life["cog_days"] = 0
        msg += " They will choose what to do for a while."
    elif k == "rest":
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
        g.party_remove(s.id)
        sanity.heal(s, 4)
        msg = f"{s.name} leaves the party, relieved."
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
        s.low_days = s.low_days + 1 if sanity.frac(s) < 0.2 else 0
        urgent = urgent_request(g, s) if s.request is None or s.request["kind"] not in ("leave", "change") else None
        if urgent and (s.request is None or urgent["kind"] == "leave"):
            s.request = urgent
            events.append(f"💬 {s.name} {urgent['text']}.")
        elif s.request is None and _rng(g, s, 2).random() < config.REQUEST_CHANCE:
            r = make_request(g, s)
            if r:
                s.request = r
                events.append(f"💬 {s.name} {r['text']}.")
        drift(g, s, events)
