"""Slime AI: Maslow needs engine, personality traits, and internal conflicts.

Hierarchy (lowest first): energy -> food -> safety -> belonging -> esteem.
While a lower tier is unmet, higher tiers are suppressed (they neither decay nor affect mood).
"""
import random
from dataclasses import dataclass
from typing import Dict, List

from . import config, emotions
from .archetypes import get_archetype
from .resources import ResourceManager

# ---- personality traits (add a row to add a trait) -----------------------------
# decay: multiplier on a need's decay | conflict: added to conflict chance | mediate: bonus to talk success
TRAITS: Dict[str, dict] = {
    "gluttonous": dict(decay={"food": 1.5}, conflict=0.005, mediate=0.0),
    "lazy":       dict(decay={"energy": 1.4}, conflict=0.0, mediate=0.0),
    "brave":      dict(decay={}, conflict=0.005, mediate=0.05),
    "grumpy":     dict(decay={"belonging": 1.3}, conflict=0.02, mediate=-0.15),
    "kind":       dict(decay={}, conflict=-0.01, mediate=0.2),
    "proud":      dict(decay={"esteem": 1.5}, conflict=0.01, mediate=-0.1),
    "timid":      dict(decay={"safety": 1.0}, conflict=-0.005, mediate=0.05),
    "chatty":     dict(decay={"belonging": 1.6}, conflict=0.0, mediate=0.1),
}


def trait_mult(slime, need: str) -> float:
    m = 1.0
    for t in slime.traits:
        m *= TRAITS.get(t, {}).get("decay", {}).get(need, 1.0)
    return m


class NeedsEngine:
    """Advances needs one tick and applies autonomous behaviour (sleep / eat / cuddle)."""

    def __init__(self, wallet: ResourceManager, rng: random.Random):
        self.wallet = wallet
        self.rng = rng
        self.auto_care = True
        self.meal_hook = None            # Game sets: callable(slime) -> bool, a hungry slime eats a cooked dish from the pantry
        self.rest_hook = None            # Game sets: callable(slime) -> bool, sends a wounded slime to the Rest Area

    def tick(self, slimes: List, events: List[str]) -> None:
        slimes = [s for s in slimes if s.alive]
        idle = [s for s in slimes if s.state == "idle"]
        for s in slimes:
            self._decay(s)
            self._starve(s, events)
            if self.auto_care:
                self._autonomy(s, idle, events)
            self._safety(s)

    # -- internals ---------------------------------------------------------
    def _decay(self, s) -> None:
        n = s.needs
        active = n.active()
        for need, rate in config.NEED_DECAY.items():
            if need not in active:       # suppressed higher tier
                continue
            r = rate * trait_mult(s, need)
            if s.state == "hunting":
                r *= config.HUNT_DECAY_MULT.get(need, 1.0)
            elif s.state == "studying":
                r *= config.STUDY_DECAY_MULT.get(need, 1.0)
            if s.state in ("sleeping", "resting"):
                r = 0.0 if need == "energy" else r * 0.4
            n.add(need, -r)
        if s.state == "resting":                 # the Rest Area (buildings.rest_tick) handles healing & leaving
            return
        if s.state == "sleeping":
            n.add("energy", config.SLEEP_ENERGY_GAIN)
            s.hp = min(s.max_hp, s.hp + max(1, int(s.max_hp * config.SLEEP_HP_REGEN)))
            if n.get("energy") >= config.AUTO_WAKE_AT:
                s.state = "idle"

    def _starve(self, s, events) -> None:
        if s.needs.get("food") <= 0 or s.needs.get("energy") <= 0:
            loss = max(1, int(s.max_hp * config.STARVE_HP_LOSS))
            s.hp -= loss                     # neglect is lethal; Game reaps hp <= 0
            if s.hp <= 0:
                s.death_cause = "starvation" if s.needs.get("food") <= 0 else "exhaustion"
            elif s.hp <= s.max_hp * 0.3 < s.hp + loss:       # only warn when crossing the line
                events.append(f"{s.name} is wobbling dangerously (neglect)!")

    def _safety(self, s) -> None:
        ratio = s.hp / s.max_hp
        target = 100 * ratio if ratio < 0.5 else 100.0
        cur = s.needs.get("safety")
        s.needs.set("safety", cur + (target - cur) * 0.3)

    def _autonomy(self, s, idle, events) -> None:
        n = s.needs
        if s.state in ("working", "hunting") and n.get("food") < config.AUTO_EAT_BELOW:
            if self.meal_hook and self.meal_hook(s):
                events.append(f"🍽 {s.name} eats a cooked meal.")
            elif s.state == "working" and self.wallet.get("food") > 0:
                self.wallet.spend("food", 1)
                n.add("food", config.FOOD_NUTRITION)
                events.append(f"{s.name} takes a meal break.")
        if s.state == "idle":
            if n.get("energy") < config.AUTO_SLEEP_BELOW:
                if self.rest_hook and self.rest_hook(s):             # a free bed in the Rest Area restores energy much faster
                    events.append(f"🛏️ {s.name} is tired and heads to the Rest Area.")
                    return
                s.state = "sleeping"
                events.append(f"{s.name} curls up and falls asleep. zzz")
                return
            if (self.rest_hook and s.hp < s.max_hp * config.AUTO_REST_BELOW and self.rest_hook(s)):
                events.append(f"{s.name} limps to the Rest Area.")
                return
            if n.get("food") < config.AUTO_EAT_BELOW:
                if self.meal_hook and self.meal_hook(s):
                    events.append(f"🍽 {s.name} eats a cooked meal.")
                elif self.wallet.get("food") > 0:
                    self.wallet.spend("food", 1)
                    n.add("food", config.FOOD_NUTRITION)
                    events.append(f"{s.name} munches some food.")
            if n.get("belonging") < config.NEED_THRESHOLD and len(idle) > 1:
                buddies = [o for o in idle if o is not s]
                b = self.rng.choice(buddies)
                n.add("belonging", 20)
                b.needs.add("belonging", 10)
                events.append(f"{s.name} cuddles up to {b.name}.")


# ---- conflicts ------------------------------------------------------------------
@dataclass
class Conflict:
    id: int
    a: int
    b: int
    severity: int = 1
    age: int = 0
    reason: str = ""

    def to_dict(self):
        return dict(id=self.id, a=self.a, b=self.b, severity=self.severity, age=self.age,
                    reason=self.reason)


class ConflictEngine:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.conflicts: List[Conflict] = []
        self.friends: set = set()       # frozenset({id, id}) pairs that resolved a quarrel
        self.memory_fn = None           # Game sets: callable(a, b) -> (chance factor, stated reason or None) from shared history
        self.compat_fn = None           # Game sets: callable(a, b) -> compatibility; shapes quarrel odds
        self.together_fn = None         # Game sets: callable(a, b) -> are they in the same place (both home, or the same group away)?
        self.hook = None                # Game sets: callable(kind, a, b[, success]) for bonds / morale
        self.calm = 1.0                 # Keeper skill (Peacemaker): multiplies the quarrel chance
        self._next = 1
        self._idx, self._idx_key = set(), None
        self._open = None               # set of open pairs, only while tick() scans for new quarrels

    # -- helpers -----------------------------------------------------------
    def open_between(self, a_id: int, b_id: int):
        return next((c for c in self.conflicts if {c.a, c.b} == {a_id, b_id}), None)

    def has_between(self, a_id: int, b_id: int) -> bool:
        """Like open_between, but O(1) while a tick scans every pair (the index is rebuilt at the start of each scan)."""
        if self._open is not None:
            return frozenset((a_id, b_id)) in self._open
        key = (len(self.conflicts), self.conflicts[-1].id if self.conflicts else 0, self._next)     # ids only grow: any add or remove changes this
        if self._idx_key != key:
            self._idx, self._idx_key = {frozenset((c.a, c.b)) for c in self.conflicts}, key
        return frozenset((a_id, b_id)) in self._idx

    def get(self, cid: int):
        return next((c for c in self.conflicts if c.id == cid), None)

    def chance(self, a, b) -> float:
        p = config.CONFLICT_BASE_CHANCE
        for s in (a, b):
            p += sum(TRAITS.get(t, {}).get("conflict", 0) for t in s.traits)
            if s.needs.get("food") < config.NEED_THRESHOLD:
                p += 0.003
            if s.needs.get("energy") < config.NEED_THRESHOLD:
                p += 0.002
        if b.archetype in get_archetype(a.archetype).rivals or a.archetype in get_archetype(b.archetype).rivals:
            p += 0.004
        if frozenset((a.id, b.id)) in self.friends:
            p *= 0.3
        if self.compat_fn:                          # incompatible slimes quarrel more, soulmates much less
            p *= max(0.4, min(2.0, 1 - self.compat_fn(a, b) / 120.0))
        if self.memory_fn:                          # a history of grudges makes a fight likelier, shared thanks make it rarer
            p *= self.memory_fn(a, b)[0]
        return max(0.0, p * self.calm)

    def reason(self, a, b) -> str:
        if self.memory_fn:
            why = self.memory_fn(a, b)[1]
            if why:
                return why
        if a.needs.get("food") < config.NEED_THRESHOLD or b.needs.get("food") < config.NEED_THRESHOLD:
            return "the last snack"
        if b.archetype in get_archetype(a.archetype).rivals:
            return f"a {a.arch.name}-vs-{b.arch.name} rivalry"
        return self.rng.choice(["who gets the comfy spot", "a very rude blorp", "borrowed goo"
                                " that was never returned", "snoring"])

    # -- main tick ---------------------------------------------------------
    def tick(self, slimes: List, events: List[str]) -> None:
        by_id = {s.id: s for s in slimes}
        # escalate existing
        for c in list(self.conflicts):
            if c.a not in by_id or c.b not in by_id:       # a participant was merged away
                self.conflicts.remove(c)
                continue
            if self.together_fn and not self.together_fn(by_id[c.a], by_id[c.b]):
                continue                                   # one of them is away: the quarrel waits until they meet again
            c.age += 1
            for sid in (c.a, c.b):
                by_id[sid].needs.add("belonging", -2 * c.severity)
            if c.age % config.CONFLICT_ESCALATE_TICKS == 0:
                if c.severity < config.CONFLICT_MAX_SEVERITY:
                    c.severity += 1
                    events.append(f"The quarrel between {by_id[c.a].name} and {by_id[c.b].name} "
                                  f"is getting worse (severity {c.severity}).")
                else:
                    self._brawl(c, by_id, events)
        # new conflicts
        awake = [s for s in slimes if s.state not in ("sleeping", "resting") and s.alive]
        busy = {i for c in self.conflicts for i in (c.a, c.b)}      # one quarrel at a time per slime
        self._open = {frozenset((c.a, c.b)) for c in self.conflicts}
        try:
            self._scan(awake, busy, events)
        finally:
            self._open = None

    def _scan(self, awake, busy, events) -> None:
        for i, a in enumerate(awake):
            for b in awake[i + 1:]:
                if a.id in busy or b.id in busy:
                    continue
                if self.together_fn and not self.together_fn(a, b):
                    continue                               # slimes only quarrel when they share a place
                if self.rng.random() < self.chance(a, b):
                    c = Conflict(self._next, a.id, b.id, 1, 0, self.reason(a, b))
                    self._next += 1
                    self.conflicts.append(c)
                    self._open.add(frozenset((a.id, b.id)))
                    busy.update((a.id, b.id))
                    events.append(f"⚡ Conflict #{c.id}: {a.name} and {b.name} are fighting over {c.reason}!")
                    if self.hook:
                        self.hook("quarrel", a, b)

    def _brawl(self, c, by_id, events) -> None:
        for sid in (c.a, c.b):
            s = by_id[sid]
            s.hp -= max(1, int(s.max_hp * config.BRAWL_HP_LOSS))
            if s.hp <= 0:
                s.death_cause = f"died in a brawl with {by_id[c.b if sid == c.a else c.a].name}"
            s.needs.add("esteem", -10)
            s.morale = max(0.0, s.morale - config.BRAWL_MORALE)            # a brawl leaves both sour
            emotions.feel(s, "anger", config.BRAWL_ANGER)
            s.grounded = True
            s.brawls += 1
            if s.busy:                   # a brawl cuts a hunt / lesson short
                s.state, s.hunt, s.task = "idle", None, None
        events.append(f"💥 {by_id[c.a].name} and {by_id[c.b].name} brawl! Both are grounded until mediated.")
        if self.hook:
            self.hook("brawl", by_id[c.a], by_id[c.b])

    # -- player action -----------------------------------------------------
    def resolve(self, c: Conflict, slimes_by_id: Dict[int, object], success: bool) -> None:
        a, b = slimes_by_id[c.a], slimes_by_id[c.b]
        if self.hook:
            self.hook("resolved", a, b, success)
        if success:
            self.conflicts.remove(c)
            self.friends.add(frozenset((a.id, b.id)))
            for s in (a, b):
                s.needs.add("belonging", 25)
                s.grounded = self._other_brawl(s.id)
        else:
            for s in (a, b):
                s.needs.add("belonging", -5)

    def _other_brawl(self, sid: int) -> bool:
        return any(c.severity >= config.CONFLICT_MAX_SEVERITY and sid in (c.a, c.b) for c in self.conflicts)

    def forget(self, sid: int) -> None:
        """Remove a slime (e.g. merged away) from all conflicts and friendships."""
        self.conflicts = [c for c in self.conflicts if sid not in (c.a, c.b)]
        self.friends = {f for f in self.friends if sid not in f}

    def mediate_chance(self, a, b, method: str) -> float:
        if method == "snack":
            return 1.0
        base = 0.55 + sum(TRAITS.get(t, {}).get("mediate", 0) for s in (a, b) for t in s.traits)
        return max(0.1, min(0.95, base))
