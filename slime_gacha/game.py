"""Game: the façade the UI talks to. Owns state, the clock, and save/load.

One `tick()` = one game hour. Everything time-based (needs, hunts, conflicts) advances here.
"""
import json
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import config
from .ai import ConflictEngine, NeedsEngine, TRAITS
from .archetypes import BEHAVIORS, get_archetype
from .battle import BattleReport, BattleSystem
from . import buildings as bld, dungeon, elements, equipment, sparring, spells
from .academy import AcademySystem, Library
from .buildings import BUILDINGS, BuildingManager
from .social import SocialEngine
from .abilities import ABILITIES
from .errors import GameError, InvalidAction
from .gacha import GachaSystem
from .growth import evolve, evolve_cost, lose_xp, merge, merge_gain
from .hunt import HuntSystem, ZONES
from .party import Party, PartyManager
from .registry import load_plugins
from .resources import ResourceManager
from .slime import Slime


@dataclass
class SparResult:
    reports: List[BattleReport] = field(default_factory=list)
    summary: List[str] = field(default_factory=list)


@dataclass
class ScoutResult:
    segment: int = 0
    before: float = 0.0
    after: float = 0.0
    hours: int = 0
    survivors: int = 0
    log: List[str] = field(default_factory=list)


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
        self.buildings = BuildingManager(self.wallet)
        self.library = Library(self.wallet, self.buildings)
        self.academy = AcademySystem(self.wallet, self.rng, self.library, self.buildings)
        self.social = SocialEngine(self.conflicts, self.buildings)
        self.needs.rest_hook = self._auto_rest                    # wounded slimes self-admit to the Rest Area
        self.conflicts.compat_fn = lambda a, b: self.social.compat(a, b)
        self.conflicts.hook = self._social_hook
        self.parties = PartyManager(party_size)        # raises ValueError unless multiple of 5
        self.main_floor = 0                            # last cleared BOSS floor = checkpoint of the Descent
        self.best_floor = 0                            # deepest floor ever cleared
        self.delves: Dict[int, dict] = {}              # party id -> active delve {floor, start, hours}
        self.intel: Dict[int, float] = {}              # segment index -> knowledge 0-100 (from scouting)
        self.dungeon_seed = (random.Random((seed or 0) ^ 0x5EED).randrange(2 ** 31) if seed is not None
                             else random.SystemRandom().randrange(2 ** 31))
        self.inventory = equipment.Inventory()
        self.pit_lost: List[str] = []                  # gear left behind in the Gloop Pit
        self.sacrifice_stress = 0.0                    # recent merges; decays 1/day
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
            bld.rest_tick(self.slimes(), self.buildings, events)
            self.sacrifice_stress = max(0.0, self.sacrifice_stress - 1.0 / config.SACRIFICE_STRESS_DECAY_TICKS)
            self.social.morale_tick(self.slimes(), self.sacrifice_stress)
            self.hunts.tick(self.slimes(), events)
            self._reap(events)
            self.academy.tick(self.slimes(), events)
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
            for key in s.gear.values():                  # outside a dungeon the gear goes back to the colony
                self.inventory.add(key)
            s.gear = {}
            del self.roster[s.id]
            self.parties.remove(s.id)
            friends = {i for f in self.conflicts.friends if s.id in f for i in f if i != s.id}
            self.conflicts.forget(s.id)
            friends |= {i for k, v in self.social.bonds.items() if s.id in k and v >= 20 for i in k if i != s.id}
            self.social.forget(s.id)
            for o in self.slimes():                      # grief: friends hurt more
                o.needs.add("belonging", -25 if o.id in friends else -8)
                self.social.shift_morale(o, config.MORALE_FRIEND_DEATH if o.id in friends
                                         else config.MORALE_ALLY_DEATH)
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
        if s.busy:
            raise InvalidAction(f"{s.name} is away ({s.state}).")
        s.state = "sleeping"
        return f"{s.name} dozes off."

    def wake(self, sid: int) -> str:
        s = self.slime(sid)
        if s.state in ("sleeping", "resting"):
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
        self.academy.cancel(s)
        return f"{s.name} was called back."

    # ---- sparring (fighting styles) -------------------------------------------------
    def spar(self, a_id: int, b_id: int, discipline: str) -> SparResult:
        """Two slimes duel non-lethally in the chosen arena (sword / archery / magic) to develop a fighting
        STYLE. No XP; the loser is left at 1 HP (use the Rest Area). Costs 2 white gel and 3 hours."""
        return self._spar_group([(self.slime(a_id), self.slime(b_id))], None, discipline)

    def spar_party(self, pid: int, discipline: str) -> SparResult:
        """Everyone in a full party spars in random pairs; an odd slime out trains on a dummy."""
        self._require_full(pid)
        members = self.party_members(pid)
        self.rng.shuffle(members)
        pairs = [(members[i], members[i + 1]) for i in range(0, len(members) - 1, 2)]
        odd = members[-1] if len(members) % 2 else None
        return self._spar_group(pairs, odd, discipline)

    def _spar_group(self, pairs, dummy_slime, discipline: str) -> SparResult:
        d = sparring.DISCIPLINES.get(discipline)
        cap = self.buildings.style_cap()
        everyone = [s for p in pairs for s in p] + ([dummy_slime] if dummy_slime else [])
        if len({s.id for s in everyone}) != len(everyone):
            raise InvalidAction("A slime can't spar with themselves.")
        for s in everyone:
            sparring.check_ready(s)
        if all(sparring.style_level(s, d.key) >= cap for s in everyone):
            raise InvalidAction(f"Everyone is already at the {d.style} ceiling (level {cap}) - upgrade the "
                                f"Training Grounds.")
        self.wallet.spend_many({k: v * (len(pairs) + (1 if dummy_slime else 0))
                                for k, v in config.SPAR_COST.items()})
        res = SparResult()
        mult = self.buildings.style_mult()

        def reward(s, won, dummy=False):
            before = sparring.style_level(s, d.key)
            xp = sparring.style_xp_for(s, d.key, won, mult, dummy)
            after = sparring.gain_style_xp(s, d.key, xp, cap)
            self.social.shift_morale(s, 2 + (2 if won else 0))
            note = f"+{xp:.0f} {d.style} xp"
            if after > before:
                note += f" ⬆ {d.style} level {after}!"
            elif after >= cap and sparring.style_level(s, d.key) >= cap:
                note += " (Training Grounds ceiling)"
            res.summary.append(f"   {s.name}: {note}")

        for a, b in pairs:
            rep = self.battles.duel(a, b)
            res.reports.append(rep)
            win, lose = (a, b) if rep.winner == "party" else (b, a)
            res.summary.append(f"{d.emoji} {win.name} beat {lose.name} in {rep.rounds} rounds "
                               f"({lose.name} left at {lose.hp} HP)")
            reward(win, True)
            reward(lose, False)
            self.social.add_bond(a, b, config.SPAR_BOND)
        if dummy_slime:
            res.summary.append(f"{d.emoji} {dummy_slime.name} drills on a training dummy")
            reward(dummy_slime, None, dummy=True)
            dummy_slime.needs.add("energy", -4)
        events = self.tick(config.SPAR_TICKS)
        res.summary.extend("   " + e for e in events if "died" in e)
        self.journal.extend(events)
        return res

    # ---- rest area -------------------------------------------------------------------------
    def resting_count(self) -> int:
        return sum(1 for s in self.slimes() if s.state == "resting")

    def _auto_rest(self, s) -> bool:
        if s.state == "idle" and not s.in_dungeon and self.resting_count() < self.buildings.rest_capacity():
            s.state = "resting"
            return True
        return False

    def rest(self, sid: int) -> str:
        """Send a slime to the Rest Area: heals a fraction of max HP per hour (see Rest Area level)."""
        s = self.slime(sid)
        if s.busy:
            raise InvalidAction(f"{s.name} is away ({s.state}).")
        if s.state == "resting":
            return f"{s.name} is already resting."
        if self.resting_count() >= self.buildings.rest_capacity():
            raise InvalidAction(f"The Rest Area is full ({self.buildings.rest_capacity()}). Upgrade it for more room.")
        s.state = "resting"
        return f"{s.name} sinks into the Rest Area."

    def party_rest(self, pid: int) -> str:
        """Rest every unavailable-for-nothing member: Rest Area first, then plain sleep if it is full."""
        rested = slept = 0
        for s in self.party_members(pid):
            if s.state not in ("idle", "sleeping"):
                continue
            try:
                self.rest(s.id)
                rested += 1
            except InvalidAction:
                s.state = "sleeping"
                slept += 1
        return f"{rested} slime(s) soak in the Rest Area, {slept} curl up to sleep."

    # ---- buildings ---------------------------------------------------------------------------
    def upgrade_building(self, key: str) -> str:
        if key not in BUILDINGS:
            raise InvalidAction(f"Unknown building '{key}'. Options: {', '.join(BUILDINGS.keys())}.")
        return self.buildings.upgrade(key)

    def building_report(self) -> List[dict]:
        out = []
        for b in BUILDINGS:
            lv = self.buildings.level(b.key)
            nxt = self.buildings.next_cost(b.key)
            out.append(dict(key=b.key, name=b.name, emoji=b.emoji, level=lv, max=b.max_level,
                            now=self.buildings.describe(b.key), cost=nxt,
                            nxt=self.buildings.describe(b.key, lv + 1) if nxt else None))
        return out

    # ---- social: morale, compatibility, council -----------------------------------------------
    def _social_hook(self, kind: str, a, b, success: bool = None) -> None:
        if kind == "quarrel":
            self.social.add_bond(a, b, -3)
            for s in (a, b):
                self.social.shift_morale(s, -3)
        elif kind == "brawl":
            self.social.add_bond(a, b, -10)
            for s in (a, b):
                self.social.shift_morale(s, -15)
        elif kind == "resolved":
            if success:
                self.social.add_bond(a, b, 10)
                for s in (a, b):
                    self.social.shift_morale(s, 10)
            else:
                self.social.add_bond(a, b, -2)

    def compat(self, a_id: int, b_id: int) -> dict:
        a, b = self.slime(a_id), self.slime(b_id)
        parts = self.social.compat_parts(a, b)
        total = self.social.compat(a, b)
        return dict(total=total, label=self.social.compat_label(total), parts=parts)

    def party_synergy(self, pid: int) -> float:
        return self.social.synergy(self.party_members(pid))

    def council(self) -> dict:
        """Keep-vs-sacrifice advice: ranked roster plus the best merge suggestions."""
        in_party = {i for p in self.parties.parties.values() for i in p.members}
        rows = self.social.keep_scores(self.slimes(), in_party)
        sugg = []
        if len(rows) >= 2:
            half = max(1, len(rows) // 2)
            targets = [r["slime"] for r in rows[:half]][:5]
            donors = [r["slime"] for r in rows[::-1][:half]][:5]
            for t in targets:
                for d in donors:
                    if t is d:
                        continue
                    c = self.social.compat(t, d)
                    gain = merge_gain(t, d, c)
                    grief = self.social.grief(d, self.slimes(), 1 + config.SACRIFICE_STRESS_AMP * self.sacrifice_stress)
                    sugg.append(dict(target=t, donor=d, xp=gain, compat=c, grief=grief,
                                     net=gain - 3 * grief))
            sugg.sort(key=lambda x: -x["net"])
        return dict(rows=rows, merges=sugg[:5])

    def study(self, sid: int, element: str) -> str:
        """Attune to / study a basic element at the Library (3-star+ slimes of ANY class)."""
        return self.academy.start_study(self.slime(sid), element)

    def learn_spell(self, sid: int, spell_key: str) -> str:
        return self.library.learn(self.slime(sid), spell_key)

    def forget_spell(self, sid: int, spell_key: str) -> str:
        return self.library.forget(self.slime(sid), spell_key)

    def research(self, sid: int, spell_a: str, spell_b: str, name: Optional[str] = None) -> str:
        """Fuse two learned spells of different elements into a new one (fire + wind = lightning...)."""
        return self.academy.start_research(self.slime(sid), spell_a, spell_b, name)

    def research_preview(self, sid: int, spell_a: str, spell_b: str) -> dict:
        a, b, el, cost, ticks, chance = self.academy.plan_research(self.slime(sid), spell_a, spell_b)
        return dict(element=el, cost=cost, hours=ticks, chance=chance, a=a, b=b)

    def cancel_task(self, sid: int) -> str:
        s = self.slime(sid)
        self.academy.cancel(s)
        return f"{s.name} leaves early."

    # ---- growth -----------------------------------------------------------------
    def evolve(self, sid: int) -> List[str]:
        return evolve(self.slime(sid), self.wallet)

    def merge(self, target_id: int, donor_id: int) -> List[str]:
        t, d = self.slime(target_id), self.slime(donor_id)
        compat = self.social.compat(t, d)
        amp = 1 + config.SACRIFICE_STRESS_AMP * self.sacrifice_stress
        grief = self.social.grief(d, self.slimes(), amp)
        log = merge(t, d, compat)
        log.append(f"   (compatibility {compat:+d}, {self.social.compat_label(compat)}: "
                   f"{'a warm' if compat >= 30 else 'an awkward' if compat < 0 else 'an ordinary'} merge)")
        friends = {i for f in self.conflicts.friends if d.id in f for i in f if i != d.id}
        friends |= {i for k, v in self.social.bonds.items() if d.id in k and v >= 20 for i in k if i != d.id}
        self.social.inherit(d, t, self.slimes())               # the target keeps half the donor's friendships
        del self.roster[d.id]
        self.conflicts.forget(d.id)
        self.parties.remove(d.id)
        self.social.forget(d.id)
        for o in self.slimes():                               # the colony mourns the sacrifice
            base = config.MERGE_MORALE_FRIENDS if o.id in friends else config.MERGE_MORALE_OTHERS
            if o.id == t.id:
                base = config.MERGE_MORALE_TARGET            # the survivor carries the guilt
            self.social.shift_morale(o, base * amp)
        self.sacrifice_stress += 1.0
        log.append(f"   The colony's morale falls (-{grief} total). Sacrifice stress is now "
                   f"{self.sacrifice_stress:.1f}" + (" - the colony is wearing thin!" if self.sacrifice_stress >= 2 else "."))
        return log

    def merge_preview(self, target_id: int, donor_id: int) -> int:
        t, d = self.slime(target_id), self.slime(donor_id)
        return merge_gain(t, d, self.social.compat(t, d))

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
            if s.state != "idle" or s.in_dungeon:
                raise InvalidAction(f"{s.name} is {s.in_dungeon and 'inside a dungeon' or s.state}.")
            if s.grounded:
                raise InvalidAction(f"{s.name} is grounded after a brawl.")
        return party

    def _run_battle(self, party, enemies, intel: float = 1.0, **opts) -> BattleReport:
        """BattleSystem.run with party synergy (compatibility) and scouting intel applied."""
        syn = self.social.synergy(party) * intel
        report = self.battles.run(party, enemies, synergy=syn, **opts)
        report.log.insert(1, f"🤝 Party synergy {syn - 1:+.1%} (avg compatibility "
                             f"{self.social.avg_compat(party):+.0f}"
                             + (f", scouting intel {intel - 1:+.0%}" if intel != 1.0 else "") + ")")
        return report

    def _after_battle(self, party, report: BattleReport, boss: bool = False, scale: float = 1.0) -> None:
        """Morale and bonds react to the outcome (deaths are handled when the dead are reaped)."""
        alive = [s for s in party if s.hp > 0]
        if report.victory:
            for s in alive:
                self.social.shift_morale(s, scale * (config.MORALE_WIN + (config.MORALE_BOSS_WIN if boss else 0)))
            for i, a in enumerate(alive):
                for b in alive[i + 1:]:
                    self.social.add_bond(a, b, 2 * scale)
        elif report.winner == "foes":
            for s in alive:
                self.social.shift_morale(s, scale * config.MORALE_LOSS)

    def _fight(self, party, enemies, hours: int, **opts) -> BattleReport:
        """Run a battle, bury the fallen, then let `hours` pass (the colony keeps living)."""
        report = self._run_battle(party, enemies, **opts)
        events: List[str] = []
        self._after_battle(party, report)
        self._reap(events)
        if hours:
            events.extend(self.tick(hours))
        report.log.extend(events)
        self.journal.extend(events)
        return report

    # ---- equipment ----------------------------------------------------------------------------
    def gear_shop(self) -> List[equipment.Gear]:
        """Gear the Armory sells (tier limited by Armory level)."""
        tier = self.buildings.gear_tier()
        return [g for g in equipment.GEAR if g.tier <= tier]

    def buy_gear(self, key: str) -> str:
        if key not in equipment.GEAR:
            raise InvalidAction(f"Unknown gear '{key}'.")
        g = equipment.GEAR.get(key)
        if g.tier > self.buildings.gear_tier():
            raise InvalidAction(f"{g.name} is tier {g.tier}; upgrade the Armory (sells up to tier "
                                f"{self.buildings.gear_tier()}).")
        self.wallet.spend_many(g.cost)
        self.inventory.add(key)
        return f"🛠️ Bought {g.emoji}{g.name}."

    def equip(self, sid: int, key: str) -> str:
        s = self.slime(sid)
        if s.busy:
            raise InvalidAction(f"{s.name} is away ({s.in_dungeon or s.state}).")
        return self.inventory.equip(s, key)

    def unequip(self, sid: int, slot: str) -> str:
        s = self.slime(sid)
        if s.busy:
            raise InvalidAction(f"{s.name} is away ({s.in_dungeon or s.state}).")
        return self.inventory.unequip(s, slot)

    def _gear_drop(self, tier: int, chance: float, log: List[str], guaranteed: bool = False) -> None:
        if not guaranteed and self.rng.random() >= chance:
            return
        pool = [g for g in equipment.GEAR if g.tier == max(1, min(3, tier))]
        if pool:
            g = self.rng.choice(pool)
            self.inventory.add(g.key)
            log.append(f"🎁 The party found {g.emoji}{g.name}!")

    def _drop_gear(self, fallen, survivors, party, where: str, log: List[str]) -> None:
        """A fallen slime drops its gear. A survivor may carry it back: chance rises with PARTY SYNERGY (and
        friendship with the fallen). Unrecovered gear is lost (Pit: stays in the Pit's lost-and-found)."""
        syn = self.social.synergy(party) if len(party) > 1 else 1.0
        for f in fallen:
            items = list(f.gear.values())
            f.gear = {}
            for key in items:
                g = equipment.GEAR.get(key)
                if survivors:
                    best = max(survivors, key=lambda s: self.social.compat(f, s))
                    c = (config.GEAR_RECOVERY_BASE + config.GEAR_RECOVERY_SYNERGY_SLOPE * (syn - 1)
                         + self.social.compat(f, best) / 400.0)
                    c = max(config.GEAR_RECOVERY_MIN, min(config.GEAR_RECOVERY_MAX, c))
                else:
                    best, c = None, 0.0
                if self.rng.random() < c:
                    self.inventory.add(key)
                    log.append(f"🎒 {best.name} carries {f.name}'s {g.emoji}{g.name} back ({c:.0%} chance).")
                elif where == "Gloop Pit":
                    self.pit_lost.append(key)
                    log.append(f"💨 {f.name}'s {g.emoji}{g.name} is left behind in the Pit.")
                else:
                    log.append(f"💨 {f.name}'s {g.emoji}{g.name} is lost in the {where} forever.")

    def _recover_pit_gear(self, party, log: List[str]) -> None:
        syn = self.social.synergy(party) if len(party) > 1 else 1.0
        for key in list(self.pit_lost):
            if self.rng.random() < config.PIT_LOST_RECOVER * syn:
                self.pit_lost.remove(key)
                self.inventory.add(key)
                g = equipment.GEAR.get(key)
                log.append(f"🎒 The party digs up the lost {g.emoji}{g.name}!")

    # ---- dungeons (common) ---------------------------------------------------------------------
    def _members_in(self, kind: str, pid: int) -> List[Slime]:
        return [s for s in self.party_members(pid) if s.in_dungeon == kind]

    def _set_flag(self, party, kind: str) -> None:
        for s in party:
            s.in_dungeon = kind

    @staticmethod
    def _clear_flag(party) -> None:
        for s in party:
            s.in_dungeon = ""

    def _knowledge(self, seg: int) -> float:
        return self.intel.get(seg, 0.0)

    def _add_knowledge(self, seg: int, amount: float) -> None:
        self.intel[seg] = round(min(100.0, self.intel.get(seg, 0.0) + amount), 2)

    # ---- main dungeon: The Hollow Descent (rough, permadeath, no way out) ----------------------
    @property
    def current_segment(self) -> int:
        return dungeon.segment_of(self.main_floor + 1)

    def intel_report(self, seg: Optional[int] = None) -> List[dict]:
        seg = self.current_segment if seg is None else seg
        return dungeon.intel_view(self.dungeon_seed, seg, self._knowledge(seg), self.parties.size)

    def enter_dungeon(self, pid: int) -> str:
        """Enter the next segment of the Hollow Descent (5 floors ending in a boss). THERE IS NO WAY OUT until
        the boss is beaten or the whole party is dead. Members cannot do anything else meanwhile."""
        if pid in self.delves:
            raise InvalidAction("That party is already inside the dungeon.")
        party = self._ready_party(pid)
        first = self.main_floor + 1
        self._set_flag(party, "main")
        self.delves[pid] = dict(floor=first, start=first, hours=0)
        seg = dungeon.segment_of(first)
        return (f"🕳 {self.parties.get(pid).name} enters the Hollow Descent at floor {first} "
                f"(segment {seg + 1}, knowledge {self._knowledge(seg):.0f}%). The way out is the boss on floor "
                f"{dungeon.segment_floors(seg)[-1]} - or death.")

    def delve_status(self, pid: int) -> dict:
        d = self.delves.get(pid)
        if not d:
            raise InvalidAction("That party is not inside the dungeon.")
        seg = dungeon.segment_of(d["floor"])
        return dict(floor=d["floor"], start=d["start"], boss_floor=dungeon.segment_floors(seg)[-1],
                    hours=d["hours"], knowledge=self._knowledge(seg), members=self._members_in("main", pid))

    def descend(self, pid: int, floor: Optional[int] = None) -> BattleReport:
        """Convenience: enter the dungeon if needed, then fight the party's current floor."""
        if floor is not None and floor != (self.delves.get(pid, {}).get("floor") or self.main_floor + 1):
            raise InvalidAction("Floors must be taken in order, and you cannot skip or leave.")
        if pid not in self.delves:
            self.enter_dungeon(pid)
        return self.delve_next(pid)

    def delve_next(self, pid: int) -> BattleReport:
        d = self.delves.get(pid)
        if not d:
            raise InvalidAction("That party has not entered the dungeon (enter_dungeon first).")
        party = self._members_in("main", pid)
        for s in party:
            if s.state == "sleeping":
                s.state = "idle"                      # woken by the next fight
        floor = d["floor"]
        seg = dungeon.segment_of(floor)
        k = self._knowledge(seg)
        enemies = dungeon.floor_plan(self.dungeon_seed, floor, self.parties.size)
        report = self._run_battle(party, enemies, intel=1 + config.INTEL_POWER_BONUS * k / 100)
        boss = dungeon.is_boss_floor(floor)
        report.log.insert(0, f"🕳 The Hollow Descent - floor {floor}{' (BOSS)' if boss else ''} "
                             f"[knowledge {k:.0f}%]")
        self._after_battle(party, report, boss=boss)
        survivors = [s for s in party if s.hp > 0]
        events: List[str] = []
        self._drop_gear([s for s in party if s.hp <= 0], survivors, party, "Hollow Descent", events)
        if report.victory:
            self.best_floor = max(self.best_floor, floor)
            self._gear_drop(1 + (floor - 1) // config.MAIN_BOSS_EVERY, config.GEAR_DROP_MAIN, events, boss)
            if boss:
                first_clear = floor > self.main_floor
                self.main_floor = max(self.main_floor, floor)
                events.append(f"🔓 Boss of floor {floor} defeated - the Descent lets the party out!")
                if first_clear:
                    self.wallet.add("purple_gel", config.MAIN_BOSS_FIRST_CLEAR_PURPLE)
                    report.loot["purple_gel"] = report.loot.get("purple_gel", 0) + config.MAIN_BOSS_FIRST_CLEAR_PURPLE
                    events.append(f"🟣 Boss bounty: +{config.MAIN_BOSS_FIRST_CLEAR_PURPLE} purple gel!")
                self._clear_flag(survivors)
                del self.delves[pid]
            else:
                d["floor"] = floor + 1
                events.append(f"➡ Floor {floor} cleared. The party must go on: floor {floor + 1}.")
        elif report.winner == "foes":
            events.append("☠ The whole party has fallen in the Hollow Descent.")
            self.delves.pop(pid, None)
        self._reap(events)
        events.extend(self.tick(config.MAIN_FLOOR_TICKS))
        if pid in self.delves:
            self.delves[pid]["hours"] += config.MAIN_FLOOR_TICKS
            self._add_knowledge(seg, config.DELVE_PASSIVE_INTEL * config.MAIN_FLOOR_TICKS)
            if not self._members_in("main", pid):          # everyone starved / died in the meantime
                self.delves.pop(pid, None)
        report.log.extend(events)
        self.journal.extend(events)
        return report

    def delve_camp(self, pid: int, hours: int = 4) -> List[str]:
        """Rest INSIDE the dungeon (sleep: ~8%/h healing, eats food). Ambushes can strike; intel reduces them."""
        d = self.delves.get(pid)
        if not d:
            raise InvalidAction("That party is not inside the dungeon.")
        hours = max(1, min(config.CAMP_HEAL_HOURS_MAX, int(hours)))
        seg = dungeon.segment_of(d["floor"])
        out: List[str] = []
        for _ in range(hours):
            party = self._members_in("main", pid)
            if not party:
                break
            for s in party:
                if s.state == "idle":
                    s.state = "sleeping"
            events = self.tick(1)
            out.extend(e for e in events if "died" in e or "starv" in e)
            d["hours"] += 1
            self._add_knowledge(seg, config.DELVE_PASSIVE_INTEL)
            party = self._members_in("main", pid)
            if not party:
                break
            p = config.CAMP_AMBUSH_BASE * (1 + 0.1 * d["floor"]) * (1 - 0.6 * self._knowledge(seg) / 100)
            if self.rng.random() < p:
                v = self.rng.choice(party)
                dmg = max(1, int(v.max_hp * self.rng.uniform(*config.CAMP_AMBUSH_DAMAGE) * (1 + 0.05 * d["floor"])))
                v.hp -= dmg
                out.append(f"⚠ An ambush at camp! {v.name} takes {dmg} damage.")
                if v.hp <= 0:
                    v.death_cause = "ambushed while camping in the Hollow Descent"
                    self._drop_gear([v], [s for s in party if s is not v and s.hp > 0], party, "Hollow Descent", out)
                    self._reap(out)
                    self._shift_morale_party(self._members_in("main", pid), -6)
        if not self._members_in("main", pid):
            out.append("☠ The whole party has fallen in the Hollow Descent.")
            self.delves.pop(pid, None)
        for s in self._members_in("main", pid):
            if s.state == "sleeping":
                s.state = "idle"
        self.journal.extend(out)
        return out

    def _shift_morale_party(self, party, delta: float) -> None:
        for s in party:
            self.social.shift_morale(s, delta)

    # ---- scouting: an exploration party gathers knowledge about the next segment ------------------
    def scout(self, pid: int, hours: int = 8) -> "ScoutResult":
        """Send a (full) party into the next dungeon segment for `hours`. Knowledge gained grows with time spent
        in the dungeon (diminishing returns). Once inside they cannot come back early; ambushes can kill scouts
        (permanent). If the whole party dies, nothing is learned."""
        if not config.SCOUT_MIN_HOURS <= hours <= config.SCOUT_MAX_HOURS:
            raise InvalidAction(f"Scouting takes {config.SCOUT_MIN_HOURS}-{config.SCOUT_MAX_HOURS} hours.")
        party = self._ready_party(pid)
        seg = self.current_segment
        before = self._knowledge(seg)
        res = ScoutResult(segment=seg, before=before, after=before, hours=hours)
        self._set_flag(party, "scout")
        skill = min(2.0, 0.8 + 0.1 * sum(s.behavior == "explore" for s in party)
                    + 0.15 * sum(s.archetype in ("rogue", "ranger") for s in party))
        danger = 1 + 0.3 * seg
        for h in range(hours):
            members = self._members_in("scout", pid)
            if not members:
                break
            events = self.tick(1)
            res.log.extend("   " + e for e in events if "died" in e)
            members = self._members_in("scout", pid)
            if not members:
                break
            strength = sum(s.power_rating() for s in members) / len(members) / (25 * danger)
            p = min(0.6, config.SCOUT_AMBUSH_BASE * danger / max(0.5, strength)
                    * (1 - 0.7 * self._knowledge(seg) / 100))
            if self.rng.random() < p:
                v = self.rng.choice(members)
                dmg = max(1, int(v.max_hp * self.rng.uniform(0.15, 0.40) * danger))
                v.hp -= dmg
                res.log.append(f"   hour {h + 1}: ambushed! {v.name} takes {dmg} damage.")
                if v.hp <= 0:
                    v.death_cause = "killed while scouting the Hollow Descent"
                    self._drop_gear([v], [s for s in members if s is not v and s.hp > 0], members,
                                    "Hollow Descent", res.log)
                    self._reap(res.log)
        survivors = self._members_in("scout", pid)
        res.survivors = len(survivors)
        if survivors:
            k = 100 - (100 - before) * math.exp(-config.SCOUT_RATE * skill * hours)
            self.intel[seg] = round(k, 2)
            res.after = self.intel[seg]
            self._clear_flag(survivors)
            for s in survivors:
                self.social.shift_morale(s, 3)
        else:
            res.log.append("☠ The whole exploration party never came back. Nothing was learned.")
        res.log.insert(0, f"🔭 Scouting segment {seg + 1} for {hours}h (skill x{skill:.2f}): knowledge "
                          f"{before:.0f}% -> {res.after:.0f}%")
        self.journal.extend(res.log)
        return res

    # ---- grinding dungeon: The Gloop Pit (committed session of N runs) -----------------------------
    def grind(self, pid: int, depth: int = 3, runs: int = 1, auto_rest: bool = True) -> GrindResult:
        """Commit the party to `runs` Pit fights at `depth` (enemy level = party average + depth - 3).
        Once in, they only leave when all runs are done or the whole party is knocked out; they camp (sleep,
        eat) between runs when hurt. A slime that goes down is not dead, but loses XP and morale and DROPS ITS
        GEAR: survivors may bring it back (chance from party synergy), else it stays in the Pit's lost-and-found
        until a later victory digs it up. (`auto_rest` is kept for compatibility: camping is always automatic.)"""
        if not 1 <= depth <= config.GRIND_DEPTHS:
            raise InvalidAction(f"Depth must be 1-{config.GRIND_DEPTHS}.")
        party = self._ready_party(pid)
        if all(s.level >= s.level_cap for s in party):
            raise InvalidAction("Everyone is at their level cap - time to evolve!")
        res = GrindResult()
        self._set_flag(party, "grind")
        try:
            for n in range(1, max(1, runs) + 1):
                members = [s for s in party if s.id in self.roster]
                if not members:
                    res.stop_reason = "the whole party is gone"
                    break
                if any(s.hp < s.max_hp * config.GRIND_MIN_HP for s in members):
                    hours = self._camp(members)
                    res.summary.append(f"   (camped {hours}h)")
                    members = [s for s in party if s.id in self.roster]
                    if not members:
                        res.stop_reason = "the whole party is gone"
                        break
                for s in members:
                    if s.state in ("sleeping", "resting"):
                        s.state = "idle"
                avg = sum(s.level for s in members) / len(members)
                enemies = dungeon.grind_wave(avg, depth, self.parties.size, self.rng)
                rep = self._run_battle(members, enemies, permadeath=False, split_xp=False,
                                       xp_mult=config.GRIND_XP_MULT)
                rep.log.insert(0, f"🕳 The Gloop Pit - depth {depth} (enemy lvl ~{dungeon.grind_level(avg, depth)})")
                self._after_battle(members, rep, scale=0.4)
                events: List[str] = []
                downed = list(rep.fallen)
                standing = [s for s in members if s not in downed]
                for s in downed:
                    lost = lose_xp(s, config.GRIND_DEATH_XP_LOSS)
                    self.social.shift_morale(s, config.GRIND_DEATH_MORALE)
                    events.append(f"💫 {s.name} was knocked out: -{lost} xp, morale {config.GRIND_DEATH_MORALE}.")
                self._drop_gear(downed, standing, members, "Gloop Pit", events)
                if rep.victory:
                    self._gear_drop(1 if depth <= 3 else 2, config.GEAR_DROP_PIT, events)
                    self._recover_pit_gear(members, events)
                events.extend(self.tick(config.GRIND_TICKS))
                rep.log.extend(events)
                res.runs.append(rep)
                tag = "Victory" if rep.victory else "Defeat" if rep.winner == "foes" else "Draw"
                line = f"Run {n}/{runs}: {tag} in {rep.rounds} rounds"
                if rep.victory:
                    line += f", +{rep.xp} XP each"
                if rep.knocked_out:
                    line += f", KO: {', '.join(rep.knocked_out)}"
                res.summary.append(line)
                res.summary.extend("   " + l.strip() for l in rep.log if "reached level" in l or "learned" in l)
                res.summary.extend("   " + e for e in events if any(w in e for w in
                                   ("knocked", "carries", "left behind", "digs", "found", "died")))
                self.journal.extend(events)
                if rep.winner == "foes":
                    res.stop_reason = "the whole party was knocked out"
                    break
            else:
                res.stop_reason = "finished all requested runs"
        finally:
            self._clear_flag(party)
        return res

    def _camp(self, members, max_hours: int = 24) -> int:
        """Inside a dungeon: sleep (no Rest Area) until everyone is >= 85% HP."""
        hours = 0
        while hours < max_hours:
            members = [s for s in members if s.id in self.roster]
            if not members or all(s.hp >= s.max_hp * 0.85 for s in members):
                break
            for s in members:
                if s.state == "idle":
                    s.state = "sleeping"
            self.tick(1)
            hours += 1
        for s in members:
            if s.id in self.roster and s.state == "sleeping" and s.needs.get("energy") >= config.AUTO_WAKE_AT - 10:
                s.state = "idle"
        return hours

    def _rest_party_until_healed(self, pid: int, max_hours: int = 24) -> int:
        """Rest the party until everyone is at 85% HP (or max_hours pass). Returns hours spent."""
        hours = 0
        while hours < max_hours:
            members = self.party_members(pid)
            if all(s.hp >= s.max_hp * 0.85 and s.state == "idle" for s in members):
                break                                   # healed AND awake
            for s in members:
                if s.state == "idle" and s.hp < s.max_hp * 0.85:
                    try:
                        self.rest(s.id)                      # Rest Area first ...
                    except InvalidAction:
                        s.state = "sleeping"                 # ... plain sleep if it is full
            self.tick(1)
            hours += 1
            if len(self.parties.get(pid).members) < self.parties.size:
                break                                   # someone died while resting
        return hours

    # ---- persistence -----------------------------------------------------------
    def to_dict(self) -> dict:
        return dict(version=config.SAVE_VERSION, seed=self.seed, tick=self.tick_count,
                    main_floor=self.main_floor, custom_spells=spells.custom_records(),
                    buildings=self.buildings.to_dict(), best_floor=self.best_floor,
                    delves={str(k): v for k, v in self.delves.items()},
                    intel={str(k): v for k, v in self.intel.items()}, dungeon_seed=self.dungeon_seed,
                    inventory=self.inventory.to_dict(), pit_lost=self.pit_lost,
                    sacrifice_stress=round(self.sacrifice_stress, 3),
                    bonds=[[*sorted(k), round(v, 2)] for k, v in self.social.bonds.items()],
                    discovered=sorted(self.library.discovered),
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
        for sysobj in (g.gacha, g.needs, g.hunts, g.battles, g.academy, g.library, g.buildings):
            sysobj.wallet = g.wallet
        g.gacha.load(d.get("gacha", {}))
        g.buildings.load(d.get("buildings"))
        g.best_floor = d.get("best_floor", 0)
        g.intel = {int(k): v for k, v in d.get("intel", {}).items()}
        g.dungeon_seed = d.get("dungeon_seed", g.dungeon_seed)
        g.inventory.load(d.get("inventory"))
        g.pit_lost = [k for k in d.get("pit_lost", []) if k in equipment.GEAR]
        g.sacrifice_stress = d.get("sacrifice_stress", 0.0)
        spells.load_custom(d.get("custom_spells", []))
        g.library.discovered = {k for k in d.get("discovered", []) if k in ABILITIES}
        for sd in d.get("slimes", []):
            if sd["archetype"] not in ARCHETYPES:          # plugin removed: skip safely
                print(f"warning: skipping slime {sd['name']} (unknown class {sd['archetype']})")
                continue
            s = Slime.from_dict(sd)
            s.spells = [k for k in s.spells if k in ABILITIES]      # drop spells from removed mods
            g.roster[s.id] = s
        g.parties.load(d.get("parties", {}), set(g.roster))
        g.graveyard = d.get("graveyard", [])
        g.conflicts.conflicts = [Conflict(**c) for c in d.get("conflicts", [])
                                 if c["a"] in g.roster and c["b"] in g.roster]
        g.delves = {int(k): v for k, v in d.get("delves", {}).items()
                    if any(s.in_dungeon == "main" for s in g.roster.values())}
        g.social.bonds = {frozenset(b[:2]): b[2] for b in d.get("bonds", [])
                          if b[0] in g.roster and b[1] in g.roster}
        g.conflicts._next = d.get("conflict_next", 1)
        g.conflicts.friends = {frozenset(f) for f in d.get("friends", [])}
        g.needs.auto_care = d.get("auto_care", True)
        if d.get("rng_state"):
            st = d["rng_state"]
            g.rng.setstate((3, tuple(st[0]), st[1]))
        g.journal = d.get("journal", [])
        return g
