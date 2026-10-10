"""Game: the façade the UI talks to. Owns state, the clock, and save/load.

One `tick()` = one game hour. Everything time-based (needs, hunts, conflicts) advances here.
"""
import json
import random
from typing import Dict, List, Optional

from . import config
from .ai import ConflictEngine, NeedsEngine, TRAITS
from .archetypes import BEHAVIORS, get_archetype
from .battle import BattleReport, BattleSystem
from .errors import InvalidAction
from .gacha import GachaSystem
from .growth import evolve, evolve_cost, merge, merge_gain
from .hunt import HuntSystem, ZONES
from .registry import load_plugins
from .resources import ResourceManager
from .slime import Slime


class Game:
    def __init__(self, seed: Optional[int] = None):
        load_plugins()
        self.seed = seed
        self.rng = random.Random(seed)
        self.tick_count = 0
        self.wallet = ResourceManager(config.STARTING_WALLET)
        self.roster: Dict[int, Slime] = {}
        self.gacha = GachaSystem(self.wallet, self.rng)
        self.needs = NeedsEngine(self.wallet, self.rng)
        self.conflicts = ConflictEngine(self.rng)
        self.hunts = HuntSystem(self.wallet, self.rng)
        self.battles = BattleSystem(self.rng, self.wallet)
        self.journal: List[str] = []

    # ---- lookup --------------------------------------------------------------
    def slime(self, sid: int) -> Slime:
        try:
            return self.roster[sid]
        except KeyError:
            raise InvalidAction(f"No slime with id #{sid}.") from None

    def slimes(self) -> List[Slime]:
        return list(self.roster.values())

    # ---- gacha -----------------------------------------------------------------
    def pull(self, n: int = 1) -> List[Slime]:
        new = self.gacha.pull(n)
        for s in new:
            self.roster[s.id] = s
        return new

    # ---- time ------------------------------------------------------------------
    def tick(self, n: int = 1) -> List[str]:
        """Advance n hours. Returns the event log for those hours."""
        events: List[str] = []
        for _ in range(n):
            self.tick_count += 1
            sl = self.slimes()
            self.needs.tick(sl, events)
            self.hunts.tick(sl, events)
            self._healer_aura(sl, events)
            self.conflicts.tick(sl, events)
        self.journal.extend(events)
        self.journal = self.journal[-200:]
        return events

    def _healer_aura(self, slimes, events) -> None:
        """Idle slimes on the 'heal' stance who know a heal patch up the most wounded idle friend."""
        from .abilities import get_ability
        for h in slimes:
            if h.state != "idle" or h.behavior != "heal":
                continue
            if not any(get_ability(k).kind == "heal" for k in h.known_abilities()):
                continue
            hurt = [o for o in slimes if o is not h and o.state != "hunting" and o.hp < o.max_hp]
            if hurt:
                t = min(hurt, key=lambda o: o.hp / o.max_hp)
                t.hp = min(t.max_hp, t.hp + max(1, int(t.max_hp * 0.1)))
                t.needs.add("belonging", 3)
                events.append(f"💚 {h.name} tends to {t.name}.")

    # ---- care ------------------------------------------------------------------
    def feed(self, sid: int) -> str:
        s = self.slime(sid)
        self.wallet.spend("food", 1)
        s.needs.add("food", config.FOOD_NUTRITION)
        s.needs.add("belonging", 3)
        return f"{s.name} nibbles happily (food {int(s.needs.get('food'))})."

    def sleep(self, sid: int) -> str:
        s = self.slime(sid)
        if s.state == "hunting":
            raise InvalidAction(f"{s.name} is out hunting.")
        s.state = "sleeping"
        return f"{s.name} dozes off."

    def wake(self, sid: int) -> str:
        s = self.slime(sid)
        if s.state == "sleeping":
            s.state = "idle"
        return f"{s.name} wakes up."

    def set_behavior(self, sid: int, stance: str) -> str:
        if stance not in BEHAVIORS:
            raise InvalidAction(f"Stance must be one of {', '.join(BEHAVIORS)}.")
        s = self.slime(sid)
        s.behavior = stance
        return f"{s.name} will now {stance}."

    def pet(self, sid: int) -> str:
        s = self.slime(sid)
        s.needs.add("belonging", 15)
        s.needs.add("esteem", 5)
        return f"You pet {s.name}. Blorp! (mood: {s.mood_label()})"

    # ---- hunting -----------------------------------------------------------------
    def hunt(self, sid: int, zone: str) -> str:
        s = self.slime(sid)
        self.hunts.start(s, zone)
        z = ZONES.get(zone)
        return f"{s.name} heads to {z.name} for {z.duration} hours."

    def recall(self, sid: int) -> str:
        s = self.slime(sid)
        self.hunts.recall(s)
        return f"{s.name} was called back."

    # ---- growth -----------------------------------------------------------------
    def evolve(self, sid: int) -> List[str]:
        return evolve(self.slime(sid), self.wallet)

    def merge(self, target_id: int, donor_id: int) -> List[str]:
        t, d = self.slime(target_id), self.slime(donor_id)
        log = merge(t, d)
        del self.roster[d.id]
        self.conflicts.forget(d.id)
        return log

    def merge_preview(self, target_id: int, donor_id: int) -> int:
        return merge_gain(self.slime(target_id), self.slime(donor_id))

    # ---- conflict -----------------------------------------------------------------
    def mediate(self, cid: int, method: str = "talk") -> str:
        c = self.conflicts.get(cid)
        if not c:
            raise InvalidAction(f"No conflict #{cid}.")
        a, b = self.slime(c.a), self.slime(c.b)
        if method == "snack":
            self.wallet.spend("food", config.MEDIATE_SNACK_COST)
            ok = True
        elif method == "talk":
            ok = self.rng.random() < self.conflicts.mediate_chance(a, b, "talk")
        else:
            raise InvalidAction("Method must be 'talk' or 'snack'.")
        self.conflicts.resolve(c, self.roster, ok)
        if ok:
            return f"{a.name} and {b.name} make up. They're friends now (fewer future quarrels)."
        return f"{a.name} and {b.name} won't hear it. Try again or offer a snack."

    # ---- battle -----------------------------------------------------------------
    def battle(self, party_ids: List[int], tier: int = 1) -> BattleReport:
        if not party_ids or len(party_ids) > config.MAX_PARTY:
            raise InvalidAction(f"Pick 1-{config.MAX_PARTY} slimes.")
        if len(set(party_ids)) != len(party_ids):
            raise InvalidAction("Duplicate slime in party.")
        party = [self.slime(i) for i in party_ids]
        for s in party:
            if s.state != "idle":
                raise InvalidAction(f"{s.name} is {s.state}.")
            if s.grounded:
                raise InvalidAction(f"{s.name} is grounded after a brawl.")
        enemies = self.battles.generate_enemies(tier, min(3, len(party) + 1))
        return self.battles.run(party, enemies)

    # ---- persistence -----------------------------------------------------------
    def to_dict(self) -> dict:
        return dict(version=config.SAVE_VERSION, seed=self.seed, tick=self.tick_count,
                    wallet=self.wallet.to_dict(), gacha=self.gacha.to_dict(),
                    slimes=[s.to_dict() for s in self.slimes()],
                    conflicts=[c.to_dict() for c in self.conflicts.conflicts],
                    conflict_next=self.conflicts._next,
                    friends=[sorted(f) for f in self.conflicts.friends],
                    auto_care=self.needs.auto_care, rng_state=self.rng.getstate()[1:],
                    journal=self.journal[-50:])

    def save(self, path: str = config.DEFAULT_SAVE) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=1)

    @classmethod
    def load(cls, path: str = config.DEFAULT_SAVE) -> "Game":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def from_dict(cls, d: dict) -> "Game":
        from .ai import Conflict
        from .archetypes import ARCHETYPES
        g = cls(d.get("seed"))
        g.tick_count = d.get("tick", 0)
        g.wallet = ResourceManager(d.get("wallet"))
        # re-point systems at the new wallet
        for sysobj in (g.gacha, g.needs, g.hunts, g.battles):
            sysobj.wallet = g.wallet
        g.gacha.load(d.get("gacha", {}))
        for sd in d.get("slimes", []):
            if sd["archetype"] not in ARCHETYPES:          # plugin removed: skip safely
                print(f"warning: skipping slime {sd['name']} (unknown class {sd['archetype']})")
                continue
            s = Slime.from_dict(sd)
            g.roster[s.id] = s
        g.conflicts.conflicts = [Conflict(**c) for c in d.get("conflicts", [])
                                 if c["a"] in g.roster and c["b"] in g.roster]
        g.conflicts._next = d.get("conflict_next", 1)
        g.conflicts.friends = {frozenset(f) for f in d.get("friends", [])}
        g.needs.auto_care = d.get("auto_care", True)
        if d.get("rng_state"):
            st = d["rng_state"]
            g.rng.setstate((3, tuple(st[0]), st[1]))
        g.journal = d.get("journal", [])
        return g
