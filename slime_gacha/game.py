"""Game: the façade the UI talks to. Owns state, the clock, and save/load.

One `tick()` = one game hour. Everything time-based (needs, hunts, conflicts) advances here.
"""
import json
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import config
from .ai import ConflictEngine, NeedsEngine, TRAITS
from .archetypes import BEHAVIORS, get_archetype
from .battle import BattleReport, BattleSystem
from . import dungeon
from .errors import InvalidAction
from .gacha import GachaSystem
from .growth import evolve, evolve_cost, merge, merge_gain
from .hunt import HuntSystem, ZONES
from .party import Party, PartyManager
from .registry import load_plugins
from .resources import ResourceManager
from .slime import Slime


@dataclass
class GrindResult:
    runs: List[BattleReport] = field(default_factory=list)
    summary: List[str] = field(default_factory=list)      # one line per run + level-ups
    stop_reason: str = ""


class Game:
    def __init__(self, seed: Optional[int] = None, party_size: int = config.PARTY_SIZE):
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
        self.parties = PartyManager(party_size)        # raises ValueError unless multiple of 5
        self.main_floor = 0                            # deepest main-dungeon floor cleared
        self.graveyard: List[dict] = []                # slimes that died, newest last
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
    @property
    def day(self) -> int:
        return self.tick_count // config.DAY_TICKS

    def free_pull_available(self) -> bool:
        return self.gacha.free_available(self.day)

    def hours_to_free_pull(self) -> int:
        return 0 if self.free_pull_available() else (self.day + 1) * config.DAY_TICKS - self.tick_count

    def pull(self, n: int = 1, pay: str = "white_gel") -> List[Slime]:
        """pay = 'free' (1 per game day) | 'white_gel' | 'purple_gel' (10 each; purple boosts rare odds)."""
        new = self.gacha.pull(n, pay, self.day)
        for s in new:
            self.roster[s.id] = s
        return new

    # ---- time ------------------------------------------------------------------
    def tick(self, n: int = 1) -> List[str]:
        """Advance n hours. Returns the event log for those hours."""
        events: List[str] = []
        for _ in range(n):
            self.tick_count += 1
            self.needs.tick(self.slimes(), events)
            self._reap(events)
            self.hunts.tick(self.slimes(), events)
            self._reap(events)
            self._healer_aura(self.slimes(), events)
            self.conflicts.tick(self.slimes(), events)
            self._reap(events)
        self.journal.extend(events)
        self.journal = self.journal[-200:]
        return events

    # ---- death -----------------------------------------------------------------------
    def _reap(self, events: List[str]) -> List[Slime]:
        """Remove every slime with hp <= 0 from the roster, bury them, and let the colony grieve."""
        dead = [s for s in self.slimes() if s.hp <= 0]
        for s in dead:
            cause = s.death_cause or "unknown causes"
            self.graveyard.append(dict(id=s.id, name=s.name, archetype=s.archetype, rarity=s.rarity,
                                       stars=s.stars, level=s.level, tick=self.tick_count, cause=cause))
            del self.roster[s.id]
            self.parties.remove(s.id)
            friends = {i for f in self.conflicts.friends if s.id in f for i in f if i != s.id}
            self.conflicts.forget(s.id)
            for o in self.slimes():                      # grief: friends hurt more
                o.needs.add("belonging", -25 if o.id in friends else -8)
            events.append(f"🪦 {s.name} the {s.title()} (Lv{s.level}) has died: {cause}.")
        return dead

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
        self.parties.remove(d.id)
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

    # ---- parties -----------------------------------------------------------------
    def create_party(self, name: str = "") -> Party:
        return self.parties.create(name)

    def party_add(self, pid: int, sid: int) -> str:
        self.slime(sid)
        self.parties.add(pid, sid)
        p = self.parties.get(pid)
        return f"{self.slime(sid).name} joins {p.name} ({len(p.members)}/{self.parties.size})."

    def party_remove(self, sid: int) -> str:
        self.parties.remove(sid)
        return f"{self.slime(sid).name} leaves their party."

    def party_disband(self, pid: int) -> None:
        self.parties.disband(pid)

    def party_autofill(self, pid: int) -> int:
        """Fill the party with the strongest free (unassigned, living) slimes. Returns number added."""
        p = self.parties.get(pid)
        free = sorted((s for s in self.slimes() if not self.parties.party_of(s.id)),
                      key=lambda s: -s.power_rating())
        added = 0
        for s in free:
            if len(p.members) >= self.parties.size:
                break
            self.parties.add(pid, s.id)
            added += 1
        return added

    def party_members(self, pid: int) -> List[Slime]:
        return [self.slime(i) for i in self.parties.get(pid).members]

    def party_hunt(self, pid: int, zone: str) -> List[str]:
        """Send every member of a full party hunting (each hunts individually)."""
        self._require_full(pid)
        out = []
        for s in self.party_members(pid):
            try:
                out.append(self.hunt(s.id, zone))
            except InvalidAction as e:
                out.append(f"✋ {e}")
        return out

    def _require_full(self, pid: int) -> None:
        p = self.parties.get(pid)
        if len(p.members) != self.parties.size:
            raise InvalidAction(f"'{p.name}' has {len(p.members)}/{self.parties.size} members - "
                                f"parties must be full.")

    # ---- battle -----------------------------------------------------------------
    def battle(self, pid: int, tier: int = 1) -> BattleReport:
        """A full party fights a wave of tier-N enemies (one foe per party slot; tier 4 = boss).
        Fallen slimes are gone for good."""
        self._require_full(pid)
        party = self._ready_party(pid)
        enemies = self.battles.generate_enemies(tier, self.parties.size)
        return self._fight(party, enemies, 0)

    def _ready_party(self, pid: int) -> List[Slime]:
        self._require_full(pid)
        party = self.party_members(pid)
        for s in party:
            if s.state != "idle":
                raise InvalidAction(f"{s.name} is {s.state}.")
            if s.grounded:
                raise InvalidAction(f"{s.name} is grounded after a brawl.")
        return party

    def _fight(self, party, enemies, hours: int, **opts) -> BattleReport:
        """Run a battle, bury the fallen, then let `hours` pass (the colony keeps living)."""
        report = self.battles.run(party, enemies, **opts)
        events: List[str] = []
        self._reap(events)
        if hours:
            events.extend(self.tick(hours))
        report.log.extend(events)
        self.journal.extend(events)
        return report

    # ---- main dungeon: The Hollow Descent (rough, permadeath) ---------------------------
    def descend(self, pid: int, floor: Optional[int] = None) -> BattleReport:
        """Fight a floor of the main dungeon (default: the next uncleared one; you may replay cleared floors).
        Every 5th floor is a boss. Slimes that fall are gone forever. Purple gel is rare; bosses pay best."""
        floor = floor or self.main_floor + 1
        if not 1 <= floor <= self.main_floor + 1:
            raise InvalidAction(f"You can enter floors 1-{self.main_floor + 1}.")
        party = self._ready_party(pid)
        enemies = dungeon.main_wave(floor, self.parties.size, self.rng)
        report = self._fight_main(party, enemies, floor)
        return report

    def _fight_main(self, party, enemies, floor) -> BattleReport:
        first_clear = floor > self.main_floor
        report = self.battles.run(party, enemies)
        report.log.insert(0, f"🕳 The Hollow Descent - floor {floor}"
                             f"{' (BOSS)' if dungeon.is_boss_floor(floor) else ''}")
        events: List[str] = []
        if report.victory and first_clear:
            self.main_floor = floor
            events.append(f"🔓 Floor {floor} cleared for the first time!")
            if dungeon.is_boss_floor(floor):
                self.wallet.add("purple_gel", config.MAIN_BOSS_FIRST_CLEAR_PURPLE)
                report.loot["purple_gel"] = report.loot.get("purple_gel", 0) + config.MAIN_BOSS_FIRST_CLEAR_PURPLE
                events.append(f"🟣 Boss bounty: +{config.MAIN_BOSS_FIRST_CLEAR_PURPLE} purple gel!")
        self._reap(events)
        events.extend(self.tick(config.MAIN_FLOOR_TICKS))
        report.log.extend(events)
        self.journal.extend(events)
        return report

    # ---- grinding dungeon: The Gloop Pit (safe XP farm) ---------------------------------
    def grind(self, pid: int, depth: int = 3, runs: int = 1, auto_rest: bool = False) -> GrindResult:
        """Repeat Pit fights. Enemy level = party average level + (depth - 3). Nobody dies (knock-outs
        drop to 1 HP); every survivor gets the full wave XP. Stops early if hurt, tired, defeated or capped,
        unless auto_rest is on, in which case the party sleeps (time passes!) until healed."""
        if not 1 <= depth <= config.GRIND_DEPTHS:
            raise InvalidAction(f"Depth must be 1-{config.GRIND_DEPTHS}.")
        res = GrindResult()
        for n in range(1, max(1, runs) + 1):
            if auto_rest:
                members = self.party_members(pid)
                if any(s.state == "sleeping" or s.hp < s.max_hp * config.GRIND_MIN_HP for s in members):
                    hours = self._rest_party_until_healed(pid)
                    res.summary.append(f"   (rested {hours}h)")
            try:
                party = self._ready_party(pid)
            except InvalidAction as e:
                if n == 1:
                    raise
                res.stop_reason = f"party not ready ({e})"
                break
            if all(s.level >= s.level_cap for s in party):
                res.stop_reason = "everyone is at their level cap - time to evolve!"
                break
            if n > 1 and any(s.hp < s.max_hp * config.GRIND_MIN_HP for s in party):
                res.stop_reason = "someone is too hurt - rest the party"
                break
            avg = sum(s.level for s in party) / len(party)
            enemies = dungeon.grind_wave(avg, depth, self.parties.size, self.rng)
            rep = self.battles.run(party, enemies, permadeath=False, split_xp=False,
                                   xp_mult=config.GRIND_XP_MULT)
            rep.log.insert(0, f"🕳 The Gloop Pit - depth {depth} (enemy lvl ~{dungeon.grind_level(avg, depth)})")
            events = self.tick(config.GRIND_TICKS)
            rep.log.extend(events)
            res.runs.append(rep)
            tag = "Victory" if rep.victory else "Defeat" if rep.winner == "foes" else "Draw"
            line = f"Run {n}: {tag} in {rep.rounds} rounds"
            if rep.victory:
                line += f", +{rep.xp} XP each"
            if rep.knocked_out:
                line += f", KO: {', '.join(rep.knocked_out)}"
            res.summary.append(line)
            res.summary.extend("   " + l.strip() for l in rep.log if "reached level" in l or "learned" in l)
            res.summary.extend("   " + e for e in events if "died" in e)
            self.journal.extend(events)
            if not rep.victory:
                res.stop_reason = "the party lost - try a lower depth"
                break
        else:
            res.stop_reason = "finished all requested runs"
        return res

    def _rest_party_until_healed(self, pid: int, max_hours: int = 24) -> int:
        """Sleep the party until everyone is at 85% HP (or max_hours pass). Returns hours spent."""
        hours = 0
        while hours < max_hours:
            members = self.party_members(pid)
            if all(s.hp >= s.max_hp * 0.85 and s.state == "idle" for s in members):
                break                                   # healed AND awake
            for s in members:
                if s.state == "idle" and s.hp < s.max_hp * 0.85:
                    s.state = "sleeping"
            self.tick(1)
            hours += 1
            if len(self.parties.get(pid).members) < self.parties.size:
                break                                   # someone died while resting
        return hours

    def party_rest(self, pid: int) -> str:
        """Put every idle member of a party to sleep (they heal and recover energy)."""
        n = 0
        for s in self.party_members(pid):
            if s.state == "idle":
                s.state = "sleeping"
                n += 1
        return f"{n} slime(s) curl up for a rest."

    # ---- persistence -----------------------------------------------------------
    def to_dict(self) -> dict:
        return dict(version=config.SAVE_VERSION, seed=self.seed, tick=self.tick_count,
                    main_floor=self.main_floor,
                    parties=self.parties.to_dict(), graveyard=self.graveyard,
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
        g = cls(d.get("seed"), d.get("parties", {}).get("size", config.PARTY_SIZE))
        g.tick_count = d.get("tick", 0)
        g.main_floor = d.get("main_floor", 0)
        wallet = dict(d.get("wallet") or {})
        for old, new in (("gel", "white_gel"), ("silver", "white_gel"), ("gold", "purple_gel")):
            if old in wallet:                                # v1/v2 saves: migrate old currency names
                wallet[new] = wallet.get(new, 0) + wallet.pop(old)
        g.wallet = ResourceManager(wallet)
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
        g.parties.load(d.get("parties", {}), set(g.roster))
        g.graveyard = d.get("graveyard", [])
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
