"""Game: the façade the UI talks to. Owns state, the clock, and save/load.

One `tick()` = one game hour. Everything time-based (needs, hunts, conflicts) advances here.
"""
import re
import json
import math
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from . import config
from .ai import ConflictEngine, NeedsEngine, TRAITS
from .archetypes import BEHAVIORS, get_archetype
from .battle import BattleReport, BattleSystem
from . import bestiary, jobs, modifiers, awakening, emotions, keeper as keeper_mod, relationships, buildings as bld, dungeon, terrain as terrain_mod, elements, ascension, attributes, equipment, items as items_mod, potions, outlook, sparring, spells, specialization
from .academy import AcademySystem, Library
from .buildings import BUILDINGS, BuildingManager
from .social import SocialEngine
from .abilities import ABILITIES, get_ability
from .errors import GameError, InvalidAction
from .gacha import GachaSystem
from .growth import add_xp, evolve, evolve_cost, lose_xp, merge, merge_gain
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
    first: int = 1
    last: int = 1
    hours: int = 0
    required: float = 0.0          # true hours the floors needed (revealed afterwards)
    complete: bool = False
    before: float = 0.0
    after: float = 0.0
    survivors: int = 0
    stranded: bool = False
    log: List[str] = field(default_factory=list)


@dataclass
class GrindResult:
    runs: List[BattleReport] = field(default_factory=list)
    summary: List[str] = field(default_factory=list)      # one line per run + level-ups
    stop_reason: str = ""


def ids_of(slimes) -> set:
    return {s.id for s in slimes}


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
        self.hunts.on_finish = lambda s, ok, group: self._hunt_done(s, ok, group)
        self.battles = BattleSystem(self.rng, self.wallet)
        self.flow = None                       # the manual-capable battle in progress (memory only, never saved)
        self.buildings = BuildingManager(self.wallet)
        self.library = Library(self.wallet, self.buildings)
        self.academy = AcademySystem(self.wallet, self.rng, self.library, self.buildings)
        self.academy.trainer_mult = lambda discipline: jobs.trainer_bonus(self, discipline)
        self.needs.meal_hook = lambda s: jobs.eat_from_pantry(self, s)
        self.social = SocialEngine(self.conflicts, self.buildings)
        self.needs.rest_hook = self._auto_rest                    # wounded slimes self-admit to the Rest Area
        self.conflicts.compat_fn = lambda a, b: self.social.compat(a, b)
        self.conflicts.hook = self._social_hook
        self.conflicts.together_fn = self._together
        self.parties = PartyManager(party_size)        # raises ValueError unless multiple of 5
        self.best_floor = 0                            # deepest floor ever cleared by anyone
        self.descent_cleared = False                   # the final boss (floor 50) has fallen
        self.bounties: set = set()                     # boss floors whose purple-gel bounty is already paid
        self.delves: Dict[int, dict] = {}              # party id -> active delve {floor, start, hours}
        self.intel: Dict[int, float] = {}              # floor -> knowledge 0-100 (scouting / having walked it)
        self.dungeon_seed = (random.Random((seed or 0) ^ 0x5EED).randrange(2 ** 31) if seed is not None
                             else random.SystemRandom().randrange(2 ** 31))
        self.inventory = equipment.Inventory()
        self.pit_lost: List[str] = []                  # gear left behind in the Gloop Pit
        self.potions: Dict[str, int] = {}              # 'kind:grade' -> count
        self.potion_peak: Dict[str, int] = {}          # most of each ever held: slimes leave 34% of it alone
        self.time_mode = "turn"                        # 'turn' (you decide when time passes) | 'live' (wall-clock with dilation)
        self.time_scale = 1.0
        self.wall_last: Optional[float] = None
        self.wall_frac = 0.0
        self.expeditions: List[dict] = []              # live mode: parties away until a game tick
        self.pantry: Dict[str, int] = {}               # cooked servings by recipe (jobs.py: chef and kitchen)
        self.recipe_pref = "auto"                      # the recipe the chef cooks ("auto" = the best one)
        self.forge_progress, self.forge_next = 0, "weapon"   # the blacksmith's slow forging (jobs._craft)
        self.stranded: List[dict] = []                 # overdue scouts waiting for a rescue party (see scout / rescue)
        self.next_stranded = 1
        self._owed = 0.0                               # hours the current session still has to pay (live mode)
        self.clock_fn = time.time
        self.keeper = keeper_mod.Keeper()
        self.relations = relationships.RelationshipEngine()
        self.emotions_mod = emotions
        self.mood_rng = random.Random(((seed or 0) ^ 0xE70) & 0xFFFFFFFF)   # feelings never disturb the main dice
        self.vault_peak = 0                            # relics: slimes leave 34% of the most ever held
        self.gear_peak: Dict[str, int] = {}
        self.forage = False                            # slimes with no party and nothing to do go foraging (a new web/CLI game turns it on)
        self.autonomy = True                           # slimes may use up to 66% of the stock by themselves
        self.vice: Optional[int] = None                # id of the Vice Keeper, if one is appointed
        self.vice_challenge: Optional[dict] = None     # {"challenger": id} waiting for the Keeper's approval
        self.hunt_group = 0                            # counter for hunts organised by the Vice Keeper
        self.vault: Dict[int, items_mod.Item] = {}     # unequipped relics (see items.py)
        self.next_item_id = 1
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

    # ---- the Keeper ------------------------------------------------------------------------------------
    @property
    def share(self) -> float:
        """How much of a stock slimes may use on their own."""
        return min(0.95, config.AUTONOMY_SHARE + 0.05 * self.keeper.rank("quartermaster"))

    def _xp(self, source: str, amount: int, quiet: bool = False) -> List[str]:
        msgs = self.keeper.gain(amount, source, self.day, config.KEEPER_DAILY_CAP.get(source, 0))
        self.journal.extend(msgs)
        return msgs

    def _apply_keeper(self) -> None:
        """Push the Keeper's skills into the systems they touch."""
        k = self.keeper
        self.gacha.luck = 1 + 0.10 * k.rank("lucky_charm")
        self.social.bond_boost = 1 + 0.25 * k.rank("matchmaker")
        self.conflicts.calm = 1 - 0.10 * k.rank("peacemaker")
        self.buildings.discount = 0.05 * k.rank("thrifty")

    def keeper_learn(self, key: str) -> str:
        msg = self.keeper.learn(key)
        self._apply_keeper()
        return msg

    def keeper_use(self, key: str) -> str:
        """Use one of the Keeper's daily abilities."""
        k = self.keeper
        if key not in keeper_mod.ACTIVES:
            raise InvalidAction(f"Unknown ability '{key}'.")
        ab = keeper_mod.ACTIVES[key]
        if not k.unlocked(key):
            raise InvalidAction(f"{ab.name} needs the skill {keeper_mod.SKILLS[ab.needs].name}.")
        if not k.ready(key, self.day):
            raise InvalidAction(f"{ab.name} is recovering (ready on day {k.cooldowns[key] + 1}).")
        free = [s for s in self.slimes() if not s.busy]
        if key == "rally":
            for s in free:
                emotions.feel(s, "joy", 15)
                emotions.feel(s, "determination", 25)
                emotions.feel(s, "pride", 10)
                self.social.shift_morale(s, 8)
            msg = f"📣 You rally the colony! {len(free)} slimes feel ready for anything."
        elif key == "soothe":
            for s in self.slimes():
                for e in ("anger", "sadness", "fear", "anxiety", "loneliness", "guilt"):
                    emotions.soothe(s, e, 30)
                s.needs.add("belonging", 5)
            msg = "🫧 You hum to the colony. Bad feelings ease."
        elif key == "favor":
            self.gacha.favor = True
            msg = "🌠 Fortune smiles: your next pull has double the rare odds."
        else:
            n = 0
            for i, a in enumerate(free):
                for b in free[i + 1:]:
                    if self.social.compat(a, b) >= 0:
                        self.social.add_bond(a, b, 3)
                        n += 1
            for s in free:
                emotions.feel(s, "joy", 12)
                emotions.feel(s, "affection", 10)
            msg = f"🎇 Bond Night! {n} friendships deepen."
        k.cooldowns[key] = self.day + ab.cooldown_days
        self._xp("ability", 2)
        return msg

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
        self.gacha.favor = False
        for s in new:
            self.roster[s.id] = s
        self._xp("pull", config.KEEPER_XP["pull"] * len(new))
        return new

    # ---- time: turn-based or live (wall clock, dilated) ----------------------------------------------------
    @property
    def live(self) -> bool:
        return self.time_mode == "live"

    def set_time_mode(self, mode: str, scale: float = None) -> str:
        if mode not in ("turn", "live"):
            raise InvalidAction("Time mode must be 'turn' or 'live'.")
        if scale is not None:
            if scale not in config.LIVE_SCALES:
                raise InvalidAction(f"Speed must be one of {', '.join(str(x) + 'x' for x in config.LIVE_SCALES)}.")
            self.time_scale = float(scale)
        if mode == "live" and not self.live:
            self.wall_last, self.wall_frac = self.clock_fn(), 0.0
        self.time_mode = mode
        if mode == "turn":
            self.expeditions_flush()
            return "Turn-based time: time passes when you say so."
        return (f"Live time: {config.LIVE_LOBBY_RATE * self.time_scale:g} game hour(s) per real hour at home, "
                f"{config.LIVE_DUNGEON_RATE * self.time_scale:g} while a party is in a dungeon.")

    def expeditions_flush(self) -> None:
        """Leaving live mode: everyone who was away comes home at once."""
        for e in self.expeditions:
            self._clear_flag([self.roster[i] for i in e["ids"] if i in self.roster])
        self.expeditions = []
        for d in self.delves.values():
            d.pop("ready_tick", None)

    def clock_rate(self) -> float:
        """Game hours per real hour right now: faster while a party is away in a dungeon."""
        busy = bool(self.expeditions or self.delves)
        return (config.LIVE_DUNGEON_RATE if busy else config.LIVE_LOBBY_RATE) * self.time_scale

    def sync(self) -> List[str]:
        """Live mode: turn elapsed wall-clock time into game hours (at most a capped catch-up). No-op in turn mode."""
        if not self.live:
            return []
        now = self.clock_fn()
        if self.wall_last is None:
            self.wall_last = now
        dt = max(0.0, now - self.wall_last)
        self.wall_last = now
        self.wall_frac += dt / 3600.0 * self.clock_rate()
        n = int(self.wall_frac + 1e-9)
        self.wall_frac = max(0.0, self.wall_frac - n)
        n = min(n, config.LIVE_CATCHUP_MAX_HOURS)
        events: List[str] = []
        for _ in range(n):                       # hour by hour so parties return, tasks finish and the rate can change
            events.extend(self.tick(1))
        return events

    def _spend(self, hours: float) -> List[str]:
        """Pay the time a dungeon activity takes: turn mode ticks the colony now; live mode keeps the party away
        and lets the wall clock bring the colony forward."""
        if not self.live:
            return self.tick(int(hours)) if hours >= 1 else []
        self._owed += hours
        return []

    def _occupy(self, slimes, hours: float, kind: str) -> List[str]:
        """A home activity that takes time: turn mode lets the colony live those hours now; live mode keeps the
        slimes busy until the wall clock has paid for them."""
        if not self.live:
            return self.tick(int(hours))
        self._set_flag(slimes, kind)
        self._owed = hours
        self._release(slimes)
        return []

    def _release(self, party) -> None:
        """End of a session: free the party now (turn mode) or when its time has been paid (live mode)."""
        owed, self._owed = int(math.ceil(self._owed)), 0.0
        alive = [s for s in party if s.id in self.roster]
        if self.live and owed > 0 and alive:
            self.expeditions.append(dict(ids=[s.id for s in alive], until=self.tick_count + owed, hours=owed))
        else:
            self._clear_flag(party)

    def _return_expeditions(self, events: List[str]) -> None:
        for e in list(self.expeditions):
            if self.tick_count >= e["until"]:
                self.expeditions.remove(e)
                back = [self.roster[i] for i in e["ids"] if i in self.roster]
                self._clear_flag(back)
                if back:
                    events.append("🏠 " + ", ".join(s.name for s in back[:5]) + (" and friends" if len(back) > 5 else "")
                                  + " return from the dungeon.")

    def _stranded_tick(self, events: List[str]) -> None:
        """Overdue scouts who are not reached in time are lost."""
        for e in list(self.stranded):
            members = [self.roster[i] for i in e["ids"] if i in self.roster and self.roster[i].in_dungeon == "stranded"]
            if not members:
                self.stranded.remove(e)
            elif self.tick_count >= e["deadline"]:
                self.stranded.remove(e)
                for s in members:
                    s.hp, s.death_cause = 0, f"lost scouting floors {e['first']}-{e['last']} (stranded on floor {e['stuck']})"
                self._drop_gear(members, [], members, "Hollow Descent", events)
                self._reap(events)
                events.append(f"☠ Nobody came for the stranded scouts on floor {e['stuck']}. They are lost.")

    def stranded_left(self, e: dict) -> int:
        return max(0, e["deadline"] - self.tick_count)

    def rescue_path(self, e: dict) -> List[int]:
        """Floors a rescue party actually has to cross to reach the stranded scouts: the ones not yet fully scouted, down to
        the floor they are stuck on. Floors already scouted are a known road and are skipped."""
        path = [f for f in range(1, e["stuck"] + 1) if self._knowledge(f) < 100.0]
        return path or [e["stuck"]]

    def rescue_hours(self, e: dict) -> int:
        scouted = e["stuck"] - len(self.rescue_path(e))
        return config.RESCUE_BASE_HOURS + len(self.rescue_path(e)) + int(math.ceil(scouted * config.RESCUE_KNOWN_FLOOR_HOURS))

    def rescue_food(self, e: dict) -> int:
        return int(math.ceil(self.rescue_hours(e) * config.SCOUT_FOOD_PER_HOUR))

    def rescue(self, pid: Optional[int], sid: int, ids: Optional[Sequence[int]] = None) -> List[str]:
        """Send slimes (one is enough, or a party's members) to bring overdue scouts home. The trip takes hours (it must beat
        the deadline), costs food, and can be ambushed. Floors already scouted are a known road: rescuers only need to have
        cleared the floor above the first unscouted floor on the way, and the trip is shorter. Success depends on the
        rescuers' strength against the depth; a failed attempt leaves the scouts waiting (if time is left) and can cost a
        rescuer's life."""
        e = next((x for x in self.stranded if x["id"] == sid), None)
        if not e:
            raise InvalidAction("Nobody is waiting to be rescued.")
        hours = self.rescue_hours(e)
        if hours >= self.stranded_left(e):
            raise InvalidAction(f"It would take {hours}h to reach them, but they only have {self.stranded_left(e)}h left.")
        party = self._explorers(pid, ids, limit=False)             # any number of rescuers, several parties together
        if not party:
            raise InvalidAction("Nobody is there to go.")
        for s in party:
            self._check_explorer(s)
        unscouted = [f for f in range(1, e["stuck"]) if self._knowledge(f) < 100.0]
        need = max(unscouted, default=0)                   # scouted floors are a known road: only the unscouted ones must have been walked
        laggard = min(party, key=lambda s: s.progress)
        if laggard.progress < need:
            raise InvalidAction(f"{laggard.name} has only cleared floor {laggard.progress}; rescuers must have walked every "
                                f"unscouted floor on the way (up to floor {need}).")
        self.wallet.spend("food", self.rescue_food(e))
        stuck = e["stuck"]
        danger = 1 + 0.06 * stuck
        strength = sum(s.power_rating() for s in party) / len(party) / (25 * danger)
        strength *= 1 + 0.1 * max(0.0, len(party) / self.parties.size - 1)       # a bigger force (several parties) breaks through more easily
        k = self._knowledge(stuck) / 100
        p_ok = min(0.95, config.RESCUE_BASE_CHANCE + 0.4 * min(1.5, strength) + 0.2 * k)
        who = self.parties.get(pid).name if pid is not None and not ids else ", ".join(s.name for s in party)
        out = [f"🛟 {who} sets out to rescue the scouts stranded on floor {stuck} ({hours}h)."]
        self._owed = 0.0
        self._set_flag(party, "rescue")
        out.extend("   " + x for x in self._spend(hours) if "died" in x)
        members = [s for s in party if s.id in self.roster]
        p_hit = min(0.6, config.SCOUT_AMBUSH_BASE * 2 * danger / max(0.5, strength) * (1 - 0.7 * k))
        if members and self.rng.random() < p_hit:
            v = self.rng.choice(members)
            dmg = max(1, int(v.max_hp * self.rng.uniform(0.15, 0.40) * danger))
            v.hp -= dmg
            out.append(f"   ambushed on the way! {v.name} takes {dmg} damage.")
            if v.hp <= 0:
                v.death_cause = "killed on a rescue mission in the Hollow Descent"
                self._drop_gear([v], [s for s in members if s is not v and s.hp > 0], members, "Hollow Descent", out)
                self._reap(out)
        members = [s for s in party if s.id in self.roster]
        scouts = [self.roster[i] for i in e["ids"] if i in self.roster and self.roster[i].in_dungeon == "stranded"]
        if members and scouts and self.rng.random() < p_ok:
            self.stranded.remove(e)
            for s in scouts:
                s.hp = max(1, s.hp)
                self.social.shift_morale(s, 5)
                emotions.feel(s, "joy", 15)
            for s in members:
                self.social.shift_morale(s, 6)
                outlook.bump(s, "delve")
            self._xp("scout", config.KEEPER_XP["scout"])
            out.append(f"✅ The rescuers reach the scouts and bring {len(scouts)} slime(s) home.")
            self._set_flag(scouts, "rescue")
            self._owed = hours
            self._release(members + scouts)
        else:
            out.append("✖ The rescuers could not break through to the scouts." if members else "☠ The rescue party is gone.")
            self._owed = hours
            self._release(members)
        self.journal.extend(out)
        return out

    def remaining_hours(self, ready_tick: int) -> float:
        return max(0.0, ready_tick - self.tick_count - self.wall_frac)

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
            jobs.tick(self, events)
            self._healer_aura(self.slimes(), events)
            self.conflicts.tick(self.slimes(), events)
            self._reap(events)
            self._return_expeditions(events)
            self._stranded_tick(events)
            self._stamina_tick()
            self._emotion_tick(events)
            if self.tick_count % 24 == config.RELATIONS_HOUR:
                self._relations_day(events)
                self._proficiency_day(events)
                self._vice_challenge_day(events)
            self._autonomy_tick(events)
            self._forage_tick()
            self._leaders_tick(events)
            self._vice_tick(events)
        self.journal.extend(events)
        self.journal = self.journal[-200:]
        return events

    @staticmethod
    def practise(s: Slime, amount: float) -> None:
        """Class practice sharpens proficiency and resets the idle counter."""
        s.class_prof = min(100.0, s.class_prof + amount)
        s.prof_idle = 0

    @staticmethod
    def practise_discipline(s: Slime, discipline: str, own: float, other: float) -> None:
        """Training in a discipline: the class's own discipline feeds class proficiency, a hybrid's secondary one feeds
        its second proficiency, anything else is only a little general practice."""
        attributes.practise(s, discipline, own, other)

    def _proficiency_day(self, events: List[str]) -> None:
        """A slime that stops practising its original discipline slowly loses its edge (and, in time, its pure capstones)."""
        for s in self.slimes():
            if s.in_dungeon:                 # out fighting in a dungeon counts as practice
                s.prof_idle = 0
                s.spec_idle = 0
                continue
            if s.spec:
                s.spec_idle += 1
                if s.spec_idle > config.PROF_IDLE_DAYS and s.spec_prof > config.PROF_FLOOR:
                    s.spec_prof = max(config.PROF_FLOOR, s.spec_prof - config.PROF_DECAY)
            s.prof_idle += 1
            if s.prof_idle > config.PROF_IDLE_DAYS and s.class_prof > config.PROF_FLOOR:
                before = len(attributes.capstones(s))
                s.class_prof = max(config.PROF_FLOOR, s.class_prof - config.PROF_DECAY)
                if len(attributes.capstones(s)) < before and attributes.pure_earned(s):
                    events.append(f"📉 {s.name} is out of practice: a capstone skill is now beyond them "
                                  f"(proficiency {s.class_prof:.0f}). Train or fight to win it back.")

    def _emotion_tick(self, events: List[str]) -> None:
        """Feelings fade and are stirred by needs; legendary 5-star slimes slowly realise they are code."""
        for s in self.slimes():
            emotions.tick(s, self.mood_rng, s.state in ("sleeping", "resting"), 1 + 0.15 * self.keeper.rank("soothing_voice"))
            if awakening.candidate(s):
                friends = sum(1 for k, v in self.social.bonds.items() if s.id in k and v >= 20)
                friends += sum(1 for f in self.conflicts.friends if s.id in f)
                awakening.tick(s, self.mood_rng, friends, events)

    def talk(self, sid: int) -> str:
        """Ask a slime how it feels. Aware legendaries may say something unsettling."""
        s = self._tend(sid)
        line = awakening.thought(s, self.mood_rng) if awakening.stage(s) and self.mood_rng.random() < 0.6 else None
        line = line or emotions.say(s, self.mood_rng)
        top = emotions.dominant(s, 1)
        feel = f" ({emotions.EMOTIONS[top[0][0]].emoji} {emotions.EMOTIONS[top[0][0]].name.lower()})" if top else ""
        emotions.feel(s, "affection", 3)
        return f'{s.name}{feel}: "{line}"'

    def _relations_day(self, events: List[str]) -> None:
        before = len(self.relations.rel)
        self.relations.daily(self, self.mood_rng, events, self.day)
        if len(self.relations.rel) > before:
            self._xp("relation", config.KEEPER_XP["relation"] * (len(self.relations.rel) - before))

    def _lose_ties(self, s: Slime, merged: bool = False) -> None:
        """A slime is gone: partners and best friends take it hard, then the ties are forgotten."""
        for r in self.relations.of(s.id):
            o = self.roster.get(r["other"])
            if not o or o.id == s.id:
                continue
            k = r["kind"]
            if k == "couple":
                emotions.feel(o, "sadness", 55)
                emotions.feel(o, "anger", 15)
                emotions.feel(o, "loneliness", 25)
                self.social.shift_morale(o, -15)
            elif k == "best_friend":
                emotions.feel(o, "sadness", 30)
            elif k == "mentor":
                emotions.feel(o, "sadness", 20)
                emotions.feel(o, "determination", 15)
            elif k == "rival":
                emotions.feel(o, "guilt", 12)
                emotions.feel(o, "sadness", 10)
        self.relations.forget(s.id)

    def bud(self, a_id: int, b_id: int) -> List[str]:
        """A couple has a child ('budding'): a new level-1 slime with a name, traits, class and rarity drawn from both
        parents. Costs food, essence and gel; each couple needs time together and a long rest between children."""
        a, b = self.slime(a_id), self.slime(b_id)
        r = self.relations.rel.get(relationships.key(a, b))
        if not r or r["kind"] != "couple":
            raise InvalidAction(f"{a.name} and {b.name} are not a couple.")
        if a.busy or b.busy:
            raise InvalidAction("Both parents must be at home.")
        if self.day - r["since"] < config.BUD_MIN_DAYS:
            raise InvalidAction(f"They have only just got together - wait {config.BUD_MIN_DAYS - (self.day - r['since'])} more day(s).")
        wait = r.get("last_bud", -999) + config.BUD_COOLDOWN_DAYS - self.day
        if wait > 0:
            raise InvalidAction(f"They need {wait} more day(s) before another child.")
        mid = self.keeper.rank("midwife")
        cost = {k: max(1, round(v * (1 - 0.2 * mid))) for k, v in config.BUD_COST.items()}
        self.wallet.spend_many(cost)
        rng = self.mood_rng
        rarity = relationships.child_rarity(a, b, rng, mid)
        stars = relationships.child_stars(a, b, rng)
        arch = rng.choice([a.archetype, b.archetype])
        kid = self.gacha.make_slime(rarity, arch, stars)
        kid.name = relationships.child_name(a, b, rng)
        kid.traits = [rng.choice(a.traits or ["kind"]), rng.choice(b.traits or ["brave"])]
        if kid.traits[0] == kid.traits[1]:
            kid.traits = kid.traits[:1] + [t for t in sorted(TRAITS) if t != kid.traits[0]][:1]
        kid.variance = {k: round((a.variance.get(k, 1) + b.variance.get(k, 1)) / 2 + rng.uniform(-0.04, 0.04), 3)
                        for k in kid.variance}
        kid.parents, kid.parent_names = [a.id, b.id], [a.name, b.name]
        kid.generation = max(a.generation, b.generation) + 1
        kid.hp = kid.max_hp
        emotions.feel(kid, "wonder", 30)
        emotions.feel(kid, "joy", 30)
        self.roster[kid.id] = kid
        r["last_bud"] = self.day
        for p in (a, b):
            emotions.feel(p, "joy", 40)
            emotions.feel(p, "pride", 30)
            emotions.feel(p, "affection", 30)
            p.needs.add("energy", -30)
            p.needs.add("esteem", 20)
            self.social.shift_morale(p, 12)
            self.social.add_bond(p, kid, 20)
        self._xp("bud", config.KEEPER_XP["bud"])
        return [f"🥚 {a.name} and {b.name} welcome a child: {kid.name} the {kid.arch.name} "
                f"[{config.RARITY_TAG[kid.rarity]}]{kid.star_str()} (generation {kid.generation})!",
                f"   Traits: {', '.join(kid.traits)}. Cost: " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in cost.items())]

    def family_tree(self) -> dict:
        """Everything the relationship tree needs: ties by kind and the lineage of every family."""
        names = {s.id: s.name for s in self.slimes()}
        names.update({g["id"]: g["name"] for g in self.graveyard})
        alive = set(self.roster)
        ties: Dict[str, list] = {k: [] for k in relationships.KINDS}
        for k, r in self.relations.rel.items():
            a, b = sorted(k)
            ties[r["kind"]].append(dict(a=a, b=b, a_name=names.get(a, "?"), b_name=names.get(b, "?"), since=r["since"],
                                        mentor=r.get("mentor"), bond=round(self.social.bonds.get(k, 0)),
                                        bud_in=(max(0, r.get("last_bud", -999) + config.BUD_COOLDOWN_DAYS - self.day)
                                                if r["kind"] == "couple" else None)))
        units: Dict[frozenset, list] = {}
        for s_ in self.slimes():
            if s_.parents:
                units.setdefault(frozenset(s_.parents), []).append(s_.id)
        children = {c for cs in units.values() for c in cs}

        def unit(p: frozenset) -> dict:
            ids = sorted(p)
            return dict(ids=ids, names=[names.get(i, "?") for i in ids], alive=[i in alive for i in ids],
                        children=[child(c) for c in sorted(units[p])])

        def child(c: int) -> dict:
            return dict(id=c, name=names.get(c, "?"), alive=c in alive,
                        families=[unit(q) for q in units if c in q])
        roots = [unit(p) for p in units if not (p & children)]
        return dict(ties=ties, families=roots)

    def _stamina_tick(self) -> None:
        """Stamina refills by the hour (faster asleep); potions wear off."""
        for s in self.slimes():
            lull = 1 + 0.2 * self.keeper.rank("lullaby") if s.state in ("sleeping", "resting") else 1.0
            s.stamina_frac = min(1.0, s.stamina_frac + attributes.hourly_regen(s) * lull)
            if s.buffs:
                for b in s.buffs:
                    b["hours"] -= 1
                s.buffs = [b for b in s.buffs if b["hours"] > 0]
                s.hp = min(s.hp, s.max_hp)

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
            for it in s.items.values():
                self.vault[it.uid] = it
            s.items = {}
            del self.roster[s.id]
            self.parties.remove(s.id)
            friends = {i for f in self.conflicts.friends if s.id in f for i in f if i != s.id}
            self.conflicts.forget(s.id)
            friends |= {i for k, v in self.social.bonds.items() if s.id in k and v >= 20 for i in k if i != s.id}
            self._lose_ties(s)
            self.social.forget(s.id)
            for o in self.slimes():                      # grief: friends hurt more
                o.needs.add("belonging", -25 if o.id in friends else -8)
                emotions.feel(o, "sadness", 35 if o.id in friends else 8)
                if o.id in friends:
                    emotions.feel(o, "anger", 15)
                    emotions.feel(o, "guilt", 8)
                emotions.feel(o, "fear", 6)
                if awakening.candidate(o):
                    o.awareness += 2.0
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
    def _tend(self, sid: int) -> Slime:
        """Care (feeding, petting, sleeping, talking, potions) is impossible while a slime is inside a dungeon -
        unless the Vice Keeper is in there with them."""
        s = self.slime(sid)
        if s.in_dungeon in ("main", "grind", "scout", "adventure", "quarry", "stranded") and not self.vice_reaches(s):
            raise InvalidAction(f"{s.name} is inside a dungeon - you cannot tend to them until they are back.")
        return s

    # ---- names -------------------------------------------------------------------
    @staticmethod
    def _clean_name(name: str) -> str:
        n = " ".join(str(name).split())
        if not n or len(n) > config.NAME_MAX or any(c in n for c in "<>&\"'`"):
            raise InvalidAction(f"A name must be 1-{config.NAME_MAX} characters, without < > & or quotes.")
        return n

    def rename_slime(self, sid: int, name: str) -> str:
        s = self.slime(sid)
        n = self._clean_name(name)
        if any(o.id != s.id and o.name.lower() == n.lower() for o in self.slimes()):
            raise InvalidAction(f"Another slime is already called {n}.")
        old, s.name = s.name, n
        return f"{old} is now called {n}."

    def set_color(self, sid: int, color: str) -> str:
        s = self.slime(sid)
        c = (color or "").strip().lower()
        if c and not re.fullmatch(r"#[0-9a-f]{6}", c):
            raise InvalidAction("A colour looks like #5be0a0.")
        s.color = c
        return f"{s.name} {'takes on a new colour' if c else 'is back to its class colour'}."

    def rename_party(self, pid: int, name: str) -> str:
        p = self.parties.get(pid)
        n = self._clean_name(name)
        if any(o.id != p.id and o.name.lower() == n.lower() for o in self.parties.parties.values()):
            raise InvalidAction(f"Another party is already called {n}.")
        old, p.name = p.name, n
        return f"Party {old} is now {n}."

    # ---- the Vice Keeper ---------------------------------------------------------------
    def vice_slime(self) -> Optional[Slime]:
        if self.vice is not None and self.vice not in self.roster:
            self.vice = None                              # died or was lost
        return self.roster.get(self.vice) if self.vice is not None else None

    def appoint_vice(self, sid: int) -> str:
        """A trusted slime (3 stars or more) stands in for the Keeper: it can mediate, feed and tend slimes the Keeper
        cannot reach (it must be in the same group), and settles quarrels by itself. It may not merge or destroy."""
        s = self.slime(sid)
        if s.stars < config.VICE_MIN_STARS:
            raise InvalidAction(f"A Vice Keeper must have at least {config.VICE_MIN_STARS} stars.")
        if s.busy and s.state != "working":                 # a Vice Keeper may hold a post in town too
            raise InvalidAction(f"{s.name} is away ({s.in_dungeon or s.state}).")
        old = self.vice_slime()
        self.vice = s.id
        self.social.shift_morale(s, 8)
        emotions.feel(s, "pride", 25)
        return f"🎖 {s.name} is now the Vice Keeper" + (f" (replacing {old.name})." if old and old.id != s.id else ".")

    def dismiss_vice(self) -> str:
        v = self.vice_slime()
        if not v:
            raise InvalidAction("There is no Vice Keeper.")
        self.vice = None
        return f"{v.name} steps down as Vice Keeper."

    def vice_reaches(self, s: Slime) -> bool:
        """Can the Vice Keeper act for this slime? At home always; away only when they are in the same group
        (same party and the same dungeon / task)."""
        v = self.vice_slime()
        if v is None or v.id == s.id:
            return False
        v_away = v.busy and v.state != "working"           # a Vice Keeper at a post in town is still at home
        if not s.busy and not v_away:
            return True
        if not (s.busy and v_away):
            return False
        if v.hunt and s.hunt and v.hunt.group and v.hunt.group == s.hunt.group:
            return True                                    # one hunt, several parties: the Vice Keeper leads them all
        pv, ps = self.parties.party_of(v.id), self.parties.party_of(s.id)
        return pv is not None and pv is ps and (v.in_dungeon or v.state) == (s.in_dungeon or s.state)

    def _together(self, a: Slime, b: Slime) -> bool:
        """Do two slimes share a place? Both at home, or away together (same party doing the same thing, or one hunt group)."""
        if not a.busy and not b.busy:
            return True
        if not (a.busy and b.busy):
            return False
        if a.hunt and b.hunt and a.hunt.group and a.hunt.group == b.hunt.group:
            return True
        pa = self.parties.party_of(a.id)
        return pa is not None and pa is self.parties.party_of(b.id) and (a.in_dungeon or a.state) == (b.in_dungeon or b.state)

    # ---- party leaders ------------------------------------------------------------------
    def party_leader(self, pid: int) -> Optional[Slime]:
        """The leader the Keeper chose, else the highest-level (then best-morale) member."""
        p = self.parties.get(pid)
        members = [self.roster[i] for i in p.members if i in self.roster]
        if not members:
            return None
        if p.leader in p.members and p.leader in self.roster:
            return self.roster[p.leader]
        return max(members, key=lambda s: (s.level, s.morale))

    def set_party_leader(self, pid: int, sid: int) -> str:
        p = self.parties.get(pid)
        if sid not in p.members:
            raise InvalidAction("The leader must be a member of the party.")
        s = self.slime(sid)
        if s.busy:
            raise InvalidAction(f"{s.name} is away.")
        p.leader = sid
        self.social.shift_morale(s, 4)
        emotions.feel(s, "pride", 12)
        return f"👑 {s.name} now leads {p.name}."

    def _leader_bonus(self, members: List[Slime]) -> float:
        """A party fights a little better under a confident leader."""
        if not members:
            return 0.0
        p = self.parties.party_of(members[0].id)
        if p is None or any(self.parties.party_of(m.id) is not p for m in members):
            return 0.0
        lead = self.party_leader(p.id)
        return config.LEADER_POWER * (0.5 + 0.5 * lead.morale / 100.0) if lead else 0.0

    def leader_reaches(self, s: Slime) -> bool:
        """Away from home, a party's leader can mediate for members doing the same thing."""
        if not s.busy:
            return False
        p = self.parties.party_of(s.id)
        lead = self.party_leader(p.id) if p else None
        return bool(lead and lead.id != s.id and lead.busy and (lead.in_dungeon or lead.state) == (s.in_dungeon or s.state))

    def vice_organize_hunt(self, zone: str, parties: int = 1) -> List[str]:
        """The Vice Keeper forms up to `parties` full parties from the free slimes and leads them all on one hunt.
        The Vice Keeper joins and leads the first party (and, as head of the hunt, can act for every party in it)."""
        v = self.vice_slime()
        if v is None:
            raise InvalidAction("Appoint a Vice Keeper first.")
        if v.busy or v.state != "idle":
            raise InvalidAction(f"{v.name} is not free to lead a hunt ({v.in_dungeon or v.state}).")
        if zone not in [z.key for z in ZONES]:
            raise InvalidAction(f"Unknown hunting zone '{zone}'.")
        parties = max(1, min(config.VICE_HUNT_MAX_PARTIES, int(parties)))
        cur = self.parties.party_of(v.id)
        if cur and cur.id in self.delves:
            raise InvalidAction(f"{v.name} is inside the Hollow Descent with {cur.name}.")
        size = self.parties.size
        free = [s for s in self.slimes() if s.id != v.id and s.state == "idle" and not s.in_dungeon and not s.grounded
                and not self.parties.party_of(s.id) and s.hp >= s.max_hp * config.MIN_HUNT_HP and s.needs.get("energy") >= 20]
        free.sort(key=lambda s: -s.power_rating())
        n_full = min(parties, (len(free) + 1) // size) if size > 1 else parties
        if n_full < 1:
            raise InvalidAction(f"Not enough free, rested slimes to form a party of {size} around {v.name} "
                                f"({len(free) + 1} available).")
        self.parties.remove(v.id)
        self.hunt_group += 1
        out = [f"🎖 {v.name} organises a hunt in {next(z.name for z in ZONES if z.key == zone)}: {n_full} part{'ies' if n_full > 1 else 'y'}."]
        pool = list(free)
        for i in range(n_full):
            p = self.parties.create(f"Hunt {self.hunt_group}{chr(65 + i)}")
            p.temp = True
            first = [v] if i == 0 else []
            for s in first + [pool.pop(0) for _ in range(size - len(first))]:
                self.parties.add(p.id, s.id)
            lead = v if i == 0 else max((self.roster[m] for m in p.members), key=lambda s: (s.level, s.morale))
            p.leader = lead.id
            for line in self.party_hunt(p.id, zone, self.hunt_group):
                out.append("   " + line)
            for m in p.members:
                s = self.roster.get(m)
                if s and s.hunt:
                    s.hunt.group = self.hunt_group
        return out

    def _leaders_tick(self, events: List[str]) -> None:
        """Hourly: party leaders settle quarrels inside their party while away; spent hunt parties disband."""
        for c in list(self.conflicts.conflicts):
            a, b = self.roster.get(c.a), self.roster.get(c.b)
            if not a or not b or not (a.busy or b.busy):
                continue
            pa, pb = self.parties.party_of(a.id), self.parties.party_of(b.id)
            if pa is None or pa is not pb:
                continue
            lead = self.party_leader(pa.id)
            if lead and lead.id not in (a.id, b.id) and self.leader_reaches(a) and self.leader_reaches(b) \
                    and self.mood_rng.random() < config.LEADER_MEDIATE_CHANCE:
                self.conflicts.resolve(c, self.roster, True)
                events.append(f"👑 {lead.name} settles the quarrel between {a.name} and {b.name}.")
        for p in list(self.parties.parties.values()):
            if p.temp and p.id not in self.delves and all(
                    (m in self.roster and not self.roster[m].busy) for m in p.members):
                self.parties.disband(p.id)
                events.append(f"👥 {p.name} disbands: the hunt is over.")

    # ---- challenging the Vice Keeper -----------------------------------------------------------------
    def challenge_vice(self, sid: int) -> str:
        """Ask for the Vice Keeper's post. The Keeper must approve before the contest (a friendly duel) happens."""
        v = self.vice_slime()
        if v is None:
            raise InvalidAction("There is no Vice Keeper to challenge.")
        s = self.slime(sid)
        if s.id == v.id:
            raise InvalidAction("The Vice Keeper cannot challenge themselves.")
        if s.stars < config.VICE_MIN_STARS:
            raise InvalidAction(f"A challenger must have at least {config.VICE_MIN_STARS} stars.")
        if self.vice_challenge:
            raise InvalidAction("A challenge is already waiting for your decision.")
        self.vice_challenge = dict(challenger=s.id)
        return f"⚔ {s.name} challenges {v.name} for the Vice Keeper's post. Approve or reject it in People > Keeper."

    def resolve_challenge(self, approve: bool) -> List[str]:
        """The Keeper's decision. Approved: the two settle it in a friendly (non-lethal) duel; the winner holds the post."""
        ch = self.vice_challenge
        if not ch:
            raise InvalidAction("There is no challenge waiting.")
        v, s = self.vice_slime(), self.roster.get(ch["challenger"])
        if v is None or s is None:                         # either is gone: the challenge lapses
            self.vice_challenge = None
            raise InvalidAction("The challenge has lapsed (someone is gone).")
        if not approve:
            self.vice_challenge = None
            emotions.feel(s, "anger", 12)
            self.social.shift_morale(s, -3)
            return [f"🚫 You turn down {s.name}'s challenge. {v.name} keeps the post."]
        for x in (v, s):
            if x.busy:
                raise InvalidAction(f"{x.name} is away ({x.in_dungeon or x.state}); wait until they are home.")
        rep = self.battles.duel(v, s)
        self.vice_challenge = None
        winner = rep.winner_slime
        loser = s if winner is v else v
        self.social.shift_morale(winner, 8)
        self.social.shift_morale(loser, -5)
        emotions.feel(winner, "pride", 20)
        emotions.feel(loser, "sadness", 10)
        out = list(rep.log[-3:])
        if winner is s:
            self.vice = s.id
            out.append(f"🎖 {s.name} wins and becomes the new Vice Keeper; {v.name} steps back.")
        else:
            out.append(f"🎖 {v.name} holds the post against {s.name}.")
        return out

    def _vice_challenge_day(self, events: List[str]) -> None:
        """A proud, stronger slime may ask for the post by itself; the Keeper still decides."""
        v = self.vice_slime()
        if v is None or self.vice_challenge:
            return
        cands = [s for s in self.slimes() if s.id != v.id and not s.busy and s.stars >= config.VICE_MIN_STARS
                 and s.level >= v.level + config.VICE_CHALLENGE_LEVEL_GAP
                 and s.emotions.get("pride", 0) + s.emotions.get("determination", 0) >= 40]
        if cands and self.mood_rng.random() < config.VICE_CHALLENGE_DAILY:
            s = self.mood_rng.choice(cands)
            events.append(self.challenge_vice(s.id))

    def _vice_tick(self, events: List[str]) -> None:
        """Hourly: the Vice Keeper settles quarrels it can reach and feeds hungry slimes in its group."""
        v = self.vice_slime()
        if v is None:
            return
        for c in list(self.conflicts.conflicts):
            a, b = self.roster.get(c.a), self.roster.get(c.b)
            if not a or not b or not (self.vice_reaches(a) or a.id == v.id) or not (self.vice_reaches(b) or b.id == v.id):
                continue
            away = a.busy or b.busy
            if not away and c.severity > 2:
                continue                                   # at home the serious ones are left to the Keeper
            if self.mood_rng.random() < config.VICE_MEDIATE_CHANCE:
                self.conflicts.resolve(c, self.roster, True)
                events.append(f"🎖 {v.name} settles the quarrel between {a.name} and {b.name}.")
        if v.busy:
            for s in self.slimes():
                if s.id != v.id and s.busy and s.needs.get("food") < config.VICE_FEED_BELOW and self.wallet.get("food") >= 1 \
                        and self.vice_reaches(s):
                    events.append("🎖 " + self.feed(s.id))

    def feed(self, sid: int) -> str:
        s = self._tend(sid)
        self.wallet.spend("food", 1)
        s.needs.add("food", config.FOOD_NUTRITION)
        s.needs.add("belonging", 3)
        gh = 1 + 0.5 * self.keeper.rank("gentle_hands")
        emotions.feel(s, "joy", 6 * gh)
        emotions.soothe(s, "anger", (10 if s.needs.get("food") < 60 else 0) * gh)
        self._xp("care", config.KEEPER_XP["care"])
        return f"{s.name} nibbles happily (food {int(s.needs.get('food'))})."

    def serve(self, sid: int, dish: Optional[str] = None) -> str:
        """Serve a cooked dish from the pantry to one slime (the best one, or `dish`)."""
        s = self._tend(sid)
        if not self.pantry:
            raise InvalidAction("The pantry is empty: appoint a chef in the Kitchen.")
        if dish is not None and self.pantry.get(dish, 0) <= 0:
            raise InvalidAction("That dish is not in the pantry.")
        if s.needs.get("food") >= 100:
            raise InvalidAction(f"{s.name} is already full.")
        jobs.eat_from_pantry(self, s, dish)
        s.needs.add("belonging", 2)
        return f"🍽 {s.name} is served a hot meal (food {int(s.needs.get('food'))})."

    def serve_hungry(self) -> List[str]:
        """Serve every hungry slime at home a dish from the pantry, the hungriest first, while it lasts."""
        out = []
        for s in sorted(jobs.hungry(self), key=lambda o: o.needs.get("food")):
            if not self.pantry:
                out.append("The pantry ran out.")
                break
            out.append(self.serve(s.id))
        return out or ["Nobody is hungry."]

    def sleep(self, sid: int) -> str:
        s = self._tend(sid)
        if s.busy:
            raise InvalidAction(f"{s.name} is away ({s.state}).")
        s.state = "sleeping"
        return f"{s.name} dozes off."

    def refusal(self, s: Slime, kind: str = "job") -> str:
        """Why this slime would refuse a post (kind "job") or an expedition (kind "dungeon": the Descent, Pit, Rift, Quarry,
        hunts, scouting, rescues) right now: exhaustion, injury, a bleak mood or a rage. "" = it agrees. Merging and
        sacrifice are the keeper's call and never ask."""
        if s.needs.get("energy") < config.REFUSE_ENERGY:
            return "is exhausted and refuses"
        if s.hp < s.max_hp * config.REFUSE_HP[kind]:
            return "is too hurt and refuses"
        if s.mood() < config.REFUSE_MOOD:
            return "is in too bleak a mood and refuses"
        if s.emotions.get("anger", 0) >= config.REFUSE_ANGER:
            return "is in a rage and refuses"
        return ""

    def wake_all(self) -> List[str]:
        """Wake every sleeper at home, except those below REFUSE_ENERGY (they need the sleep). Tired ones are grumpy."""
        out = []
        skipped = 0
        for s in self.slimes():
            if s.state != "sleeping" or s.in_dungeon:
                continue
            if s.needs.get("energy") < config.REFUSE_ENERGY:
                skipped += 1
                continue
            out.append(self._rouse(s))
        if skipped:
            out.append(f"💤 {skipped} slime(s) with under {config.REFUSE_ENERGY}% energy were left asleep.")
        if not out:
            out.append("Nobody to wake.")
        return out

    def _rouse(self, s: Slime) -> str:
        """Wake a sleeper. A slime that has already slept past half its energy wakes for free; one still tired is
        not pleased (mood cost)."""
        s.state = "idle"
        if s.needs.get("energy") >= config.WAKE_FREE_ABOVE:
            return f"{s.name} wakes up, well rested."
        self.social.shift_morale(s, -config.WAKE_MORALE)
        emotions.feel(s, "anger", config.WAKE_ANGER)
        return f"😠 {s.name} is woken up while still tired and is grumpy about it (morale -{config.WAKE_MORALE})."

    def wake(self, sid: int) -> str:
        s = self._tend(sid)
        if s.state == "sleeping":
            return self._rouse(s)
        if s.state == "resting":
            s.state = "idle"
        return f"{s.name} wakes up."

    def _prepare_trainees(self, slimes: List[Slime]) -> List[str]:
        """Before sparring or a drill: sleepers are woken (mood cost) and workers leave their job (the shift is lost)."""
        out = []
        for s in slimes:
            if s.state == "sleeping":
                out.append(self._rouse(s))
            elif s.state == "working":
                out.append(f"{s.name} leaves the {jobs.JOBS[s.job].name.lower() if s.job in jobs.JOBS else 'job'} for training. " + jobs.stop(self, s))
        return out

    def set_behavior(self, sid: int, stance: str) -> str:
        if stance not in BEHAVIORS:
            raise InvalidAction(f"Stance must be one of {', '.join(BEHAVIORS)}.")
        s = self.slime(sid)
        s.behavior = stance
        return f"{s.name} will now {stance}."

    def pet(self, sid: int) -> str:
        s = self._tend(sid)
        s.needs.add("belonging", 15)
        s.needs.add("esteem", 5)
        gh = 1 + 0.5 * self.keeper.rank("gentle_hands")
        emotions.feel(s, "joy", 12 * gh)
        emotions.feel(s, "affection", 8 * gh)
        emotions.soothe(s, "loneliness", 15 * gh)
        emotions.soothe(s, "anger", 6 * gh)
        awakening.comfort(s)
        self._xp("care", config.KEEPER_XP["care"])
        return f"You pet {s.name}. Blorp! (mood: {s.mood_label()})"

    # ---- hunting -----------------------------------------------------------------
    def hunt(self, sid: int, zone: str, group: int = 0) -> str:
        s = self.slime(sid)
        ZONES.get(zone)
        self.hunts.check(s)
        if (why := self.refusal(s, "dungeon")):
            raise InvalidAction(f"{s.name} {why}.")
        notes = self._prepare_trainees([s])                     # a sleeper is woken (mood cost if still tired), a worker leaves the post
        self.hunts.start(s, zone)
        if group:
            s.hunt.group = group
        z = ZONES.get(zone)
        return " ".join(notes + [f"{s.name} heads to {z.name} for {z.duration} hours."])

    def _hunt_done(self, s: Slime, ok: bool, group: int) -> None:
        """A hunt is practice too: class proficiency for the hunter, and hunters of one group (a party, or the Vice
        Keeper's hunt) grow closer, which lifts their party synergy."""
        self.practise_discipline(s, s.arch.discipline, config.HUNT_PROF_OWN * (1.0 if ok else 0.4), 0.0)
        if group:
            for o in self.slimes():
                if o.id != s.id and o.hunt and o.hunt.group == group:
                    self.social.add_bond(s, o, config.HUNT_BOND)

    def recall(self, sid: int) -> str:
        s = self.slime(sid)
        if s.job and s.state == "hunting":
            return jobs.recall(self, s)                       # a worker out foraging goes straight back to the post
        self.hunts.recall(s)
        self.academy.cancel(s)
        return f"{s.name} was called back."

    # ---- sparring (fighting styles) -------------------------------------------------
    def spar(self, a_id: int, b_id: int, discipline: str) -> SparResult:
        """Two slimes duel non-lethally in the chosen arena (sword / archery / magic) to develop a fighting
        STYLE. No XP; the loser is left at 1 HP (use the Rest Area). Costs 2 white gel and 3 hours (a whole party session is a flat 3)."""
        return self._spar_group([(self.slime(a_id), self.slime(b_id))], None, discipline, config.SPAR_COST)

    def spar_parties(self, pid_a: int, pid_b: int, discipline: str) -> SparResult:
        """Two full parties fight each other (non-lethal) to knit together and sharpen their class: every member
        earns fighting-style XP and class proficiency, and the members of each party grow closer (bonds, so party
        synergy rises). Costs a flat 3 white gel and 3 hours for the whole session."""
        if pid_a == pid_b:
            raise InvalidAction("Pick two different parties.")
        d = sparring.DISCIPLINES.get(discipline)
        for pid in (pid_a, pid_b):
            self._require_full(pid)
        team_a, team_b = self.party_members(pid_a), self.party_members(pid_b)
        everyone = team_a + team_b
        for s in everyone:
            sparring.check_ready(s)
        cap = self.buildings.style_cap()
        if all(sparring.style_level(s, d.key) >= cap for s in everyone):
            raise InvalidAction(f"Everyone is already at the {d.style} ceiling (level {cap}) - upgrade the Training Grounds.")
        self.wallet.spend_many(config.SPAR_PARTY_COST)
        res = SparResult()
        res.summary.extend(self._prepare_trainees(everyone))
        syn_a, syn_b = self.social.synergy(team_a), self.social.synergy(team_b)
        rep = self.battles.team_spar(team_a, team_b, syn_a, syn_b)
        res.reports.append(rep)
        names = (self.parties.get(pid_a).name, self.parties.get(pid_b).name)
        winner = 0 if rep.winner == "party" else 1
        res.summary.append(f"{d.emoji} {names[winner]} beat {names[1 - winner]} in {rep.rounds} rounds")
        for i, team in enumerate((team_a, team_b)):
            before = self.social.synergy(team)
            for x in range(len(team)):                    # teamwork: every pair in the party grows closer
                for y in range(x + 1, len(team)):
                    self.social.add_bond(team[x], team[y], config.SPAR_PARTY_BOND)
            for s in team:
                self._spar_reward(res, s, d, i == winner, cap)
            res.summary.append(f"   {names[i]}'s synergy {before - 1:+.1%} -> {self.social.synergy(team) - 1:+.1%}")
        events = self._occupy([x for x in everyone if x.id in self.roster], config.SPAR_TICKS, "train")
        res.summary.extend("   " + e for e in events if "died" in e)
        self.journal.extend(events)
        return res

    def _spar_reward(self, res: SparResult, s: Slime, d, won: Optional[bool], cap: int, dummy: bool = False) -> None:
        """Style XP, class proficiency and a little morale for one sparring slime."""
        mult = self.buildings.style_mult() * jobs.trainer_bonus(self, d.key)        # an appointed trainer speeds it up
        before = sparring.style_level(s, d.key)
        xp = sparring.style_xp_for(s, d.key, won, mult, dummy)
        if outlook.has(s, "spar"):
            xp *= config.OUTLOOK_DUELIST_STYLE
        outlook.bump(s, "spar")
        tb = jobs.trainer_bonus(self, d.key)
        self.practise_discipline(s, d.key, config.PROF_SPAR_OWN * tb, config.PROF_SPAR_OTHER)
        after = sparring.gain_style_xp(s, d.key, xp, cap)
        self.social.shift_morale(s, 2 + (2 if won else 0))
        note = f"+{xp:.0f} {d.style} xp"
        if after > before:
            note += f" ⬆ {d.style} level {after}!"
        elif after >= cap and sparring.style_level(s, d.key) >= cap:
            note += " (Training Grounds ceiling)"
        res.summary.append(f"   {s.name}: {note}")

    def _spar_group(self, pairs, dummy_slime, discipline: str, cost: Dict[str, int]) -> SparResult:
        d = sparring.DISCIPLINES.get(discipline)
        cap = self.buildings.style_cap()
        everyone = [s for p in pairs for s in p]
        if len({s.id for s in everyone}) != len(everyone):
            raise InvalidAction("A slime can't spar with themselves.")
        for s in everyone:
            sparring.check_ready(s)
        notes = self._prepare_trainees(everyone)
        if all(sparring.style_level(s, d.key) >= cap for s in everyone):
            raise InvalidAction(f"Everyone is already at the {d.style} ceiling (level {cap}) - upgrade the "
                                f"Training Grounds.")
        self.wallet.spend_many(cost)
        res = SparResult()
        res.summary.extend(notes)
        for a, b in pairs:
            rep = self.battles.duel(a, b)
            res.reports.append(rep)
            win, lose = (a, b) if rep.winner == "party" else (b, a)
            res.summary.append(f"{d.emoji} {win.name} beat {lose.name} in {rep.rounds} rounds "
                               f"({lose.name} left at {lose.hp} HP)")
            self._spar_reward(res, win, d, True, cap)
            self._spar_reward(res, lose, d, False, cap)
            self.social.add_bond(a, b, config.SPAR_BOND)
        events = self._occupy([x for x in everyone if x.id in self.roster], config.SPAR_TICKS, "train")
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
        if kind in ("quarrel", "brawl"):
            self.relations.note_quarrel(a, b)
        if kind == "quarrel":
            self.social.add_bond(a, b, -3)
            for s in (a, b):
                self.social.shift_morale(s, -3)
                emotions.feel(s, "anger", 18)
        elif kind == "brawl":
            self.social.add_bond(a, b, -10)
            for s in (a, b):
                self.social.shift_morale(s, -15)
                emotions.feel(s, "anger", 40)
                emotions.feel(s, "sadness", 10)
                emotions.feel(s, "guilt", 8)
        elif kind == "resolved":
            if success:
                self.social.add_bond(a, b, 10)
                for s in (a, b):
                    self.social.shift_morale(s, 10)
                    emotions.feel(s, "calm", 20)
                    emotions.feel(s, "joy", 12)
                    emotions.feel(s, "affection", 15)
                    emotions.soothe(s, "anger", 30)
            else:
                self.social.add_bond(a, b, -2)
                for s in (a, b):
                    emotions.feel(s, "anger", 10)

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
            targets = [r["slime"] for r in rows[:half] if not r["slime"].busy][:5]      # only slimes at home can be merged
            donors = [r["slime"] for r in rows[::-1][:half] if r["slime"].id != self.vice and not r["slime"].busy][:5]
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

    def assign_job(self, sid: int, key: str) -> str:
        """Put a slime to work in town (Chef, Blacksmith, Trainer). Switching jobs is free; places are limited by the Workshops."""
        return jobs.assign(self, self.slime(sid), key)

    def stop_job(self, sid: int) -> str:
        return jobs.stop(self, self.slime(sid))

    def drill(self, sid: int, discipline: str, tier: int = 1) -> str:
        """Send a slime to drill (sword / archery / magic) for proficiency. See AcademySystem.start_drill."""
        s = self.slime(sid)
        sparring.check_ready_basic(s)
        wound = config.WOUNDED_DRILL if s.hp < s.max_hp * config.WOUNDED_BELOW else 1.0
        notes = self._prepare_trainees([s])
        msg = self.academy.start_drill(s, discipline, tier, wound)
        return " ".join(notes + [msg]) + (" (hurt: this drill is worth less)" if wound < 1.0 else "")

    def drill_party(self, pid: int, discipline: str, tier: int = 1) -> List[str]:
        self.academy.drill_tier(tier)                       # refuse early if the tier is locked
        out = []
        for s in self.party_members(pid):
            try:
                out.append(self.drill(s.id, discipline, tier))
            except InvalidAction as e:
                out.append(f"✋ {e}")
        return out

    def study(self, sid: int, element: str) -> str:
        """Attune to / study a basic element at the Library (3-star+ slimes of ANY class)."""
        s = self.slime(sid)
        msg = self.academy.start_study(s, element)
        self.practise_discipline(s, "magic", config.PROF_STUDY, 0.0)
        return msg

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
        t, d = self._free_slime(target_id), self._free_slime(donor_id)
        if d.id == self.vice:
            raise InvalidAction(f"{d.name} is the Vice Keeper and cannot be merged away. Dismiss them first.")
        compat = self.social.compat(t, d)
        amp = 1 + config.SACRIFICE_STRESS_AMP * self.sacrifice_stress
        grief = self.social.grief(d, self.slimes(), amp)
        log = merge(t, d, compat)
        self._xp("merge", config.KEEPER_XP["merge"])
        self._return_gear(d)
        log.append(f"   (compatibility {compat:+d}, {self.social.compat_label(compat)}: "
                   f"{'a warm' if compat >= 30 else 'an awkward' if compat < 0 else 'an ordinary'} merge)")
        friends = {i for f in self.conflicts.friends if d.id in f for i in f if i != d.id}
        friends |= {i for k, v in self.social.bonds.items() if d.id in k and v >= 20 for i in k if i != d.id}
        self.social.inherit(d, t, self.slimes())               # the target keeps half the donor's friendships
        del self.roster[d.id]
        self.conflicts.forget(d.id)
        self.parties.remove(d.id)
        self._lose_ties(d)
        self.social.forget(d.id)
        for o in self.slimes():                               # the colony mourns the sacrifice
            base = config.MERGE_MORALE_FRIENDS if o.id in friends else config.MERGE_MORALE_OTHERS
            if o.id == t.id:
                base = config.MERGE_MORALE_TARGET            # the survivor carries the guilt
            self.social.shift_morale(o, base * amp)
            self._mourn_sacrifice(o, o.id in friends, o.id == t.id)
        self.sacrifice_stress += 1.0
        log.append(f"   The colony's morale falls (-{grief} total). Sacrifice stress is now "
                   f"{self.sacrifice_stress:.1f}" + (" - the colony is wearing thin!" if self.sacrifice_stress >= 2 else "."))
        return log

    def merge_preview(self, target_id: int, donor_id: int) -> int:
        t, d = self.slime(target_id), self.slime(donor_id)
        return merge_gain(t, d, self.social.compat(t, d))

    def sacrifice_preview(self, target_id: int, donor_id: int) -> dict:
        """What a manual merge would cost and give, before the player commits."""
        t, d = self.slime(target_id), self.slime(donor_id)
        if t.id == d.id:
            raise InvalidAction("A slime can't merge with itself.")
        compat = self.social.compat(t, d)
        amp = 1 + config.SACRIFICE_STRESS_AMP * self.sacrifice_stress
        return dict(xp=merge_gain(t, d, compat), compat=compat, label=self.social.compat_label(compat),
                    grief=self.social.grief(d, self.slimes(), amp), stress=round(self.sacrifice_stress, 2),
                    away=[s.name for s in (t, d) if s.busy])

    # ---- the commander's gifts (purple gel) ---------------------------------------------------------
    def gift_party(self, pid: Optional[int] = None) -> Optional[int]:
        """The party the commander may send gifts to right now: one inside the Descent, or in an open Descent /
        skirmish battle. (Care is otherwise refused for slimes that are away; purple gel is the way in.)"""
        f = self.flow
        if f and f["kind"] in ("delve", "skirmish") and f.get("pid") is not None and pid in (None, f["pid"]):
            return f["pid"]
        if pid is not None and pid in self.delves:
            return pid
        return None

    def commander_gift(self, pid: int, kind: str, sid: Optional[int] = None, potion: str = "", grade: int = 1) -> List[str]:
        """kind: 'morale' (+morale for the whole party), 'peace' (settle the party's quarrels) or 'potion'
        (a bought potion drunk by slime `sid`). Paid in purple gel; only for a Descent party or a skirmish."""
        if self.gift_party(pid) != pid:
            raise InvalidAction("Gifts can only reach a party inside the Hollow Descent, or fighting a skirmish.")
        party = self.party_members(pid)
        run = self.battle_run()
        if kind == "morale":
            self.wallet.spend("purple_gel", config.GIFT_MORALE_COST)
            for s in party:
                self.social.shift_morale(s, config.GIFT_MORALE_GAIN)
                emotions.feel(s, "joy", 8)
                if run:
                    run.refresh(s)
            return [f"🎁 The commander's gift lifts the party's spirits (+{config.GIFT_MORALE_GAIN} morale)."]
        if kind == "peace":
            ids = {s.id for s in party}
            qs = [c for c in self.conflicts.conflicts if c.a in ids and c.b in ids]
            if not qs:
                raise InvalidAction("There is no quarrel inside this party.")
            self.wallet.spend("purple_gel", config.GIFT_PEACE_COST)
            for c in qs:
                self.conflicts.resolve(c, self.roster, True)
            return [f"🎁 A gift settles {len(qs)} quarrel{'s' if len(qs) > 1 else ''} in the party."]
        if kind == "potion":
            if sid not in ids_of(party):
                raise InvalidAction("That slime is not in this party.")
            s = self.slime(sid)
            if potion not in potions.KINDS or not 1 <= grade <= 5:
                raise InvalidAction("Unknown potion or grade.")
            self._check_potion_slot(s, potion)
            self.wallet.spend("purple_gel", config.GIFT_POTION_PURPLE[grade - 1])
            msg = self._drink(s, potion, grade)
            if run:
                run.refresh(s)
            return ["🎁 " + msg]
        raise InvalidAction("Gift must be 'morale', 'peace' or 'potion'.")

    # ---- conflict -----------------------------------------------------------------
    def mediate(self, cid: int, method: str = "talk") -> str:
        c = self.conflicts.get(cid)
        if not c:
            raise InvalidAction(f"No conflict #{cid}.")
        a, b = self.slime(c.a), self.slime(c.b)
        vice = self.vice_slime()
        for s in (a, b):
            if s.busy and not (self.vice_reaches(s) or (vice and s.id == vice.id) or self.leader_reaches(s)):   # the Keeper cannot reach them
                raise InvalidAction(f"{s.name} is away ({s.in_dungeon or s.state}) - this quarrel is out of your hands "
                                    f"until they are home.")
        if method == "snack":
            self.wallet.spend("food", config.MEDIATE_SNACK_COST)
            ok = True
        elif method == "talk":
            ok = self.rng.random() < min(0.97, self.conflicts.mediate_chance(a, b, "talk") + 0.08 * self.keeper.rank("soothing_voice"))
        else:
            raise InvalidAction("Method must be 'talk' or 'snack'.")
        self.conflicts.resolve(c, self.roster, ok)
        if ok:
            self._xp("mediate", config.KEEPER_XP["mediate"])
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

    def party_hunt(self, pid: int, zone: str, group: int = 0) -> List[str]:
        """Send every member of a full party hunting (each hunts individually, but as one group: its members bond)."""
        self._require_full(pid)
        out = []
        if not group:
            self.hunt_group += 1
            group = self.hunt_group
        for s in self.party_members(pid):
            try:
                out.append(self.hunt(s.id, zone, group))
            except InvalidAction as e:
                out.append(f"✋ {e}")
        return out

    def _require_full(self, pid: int) -> None:
        p = self.parties.get(pid)
        if len(p.members) != self.parties.size:
            raise InvalidAction(f"'{p.name}' has {len(p.members)}/{self.parties.size} members - "
                                f"parties must be full.")

    # ---- battle -----------------------------------------------------------------
    def battle(self, pid: int, tier: int = 1, manual: bool = False, lo: Optional[int] = None, hi: Optional[int] = None,
               waves: int = 1):
        """The wave simulation: a full party fights `waves` waves of monsters (one per party slot) as a drill. Nobody dies
        and there is no loot. Monsters are of a level between `lo` and `hi` (a floor-equivalent, 1-50); the XP is fixed by
        the monsters and their level (no randomness, no rarity factor). Without lo/hi it uses the monsters of `tier` (4 is a
        boss). It also trains battle proficiency and teamwork. With manual=True it pauses for orders (returns None until
        it ends)."""
        return self._play(self._skirmish_gen(pid, tier, lo, hi, waves), "skirmish", manual, pid)

    def wave_enemies(self, tier: int, lo: Optional[int], hi: Optional[int]):
        if lo is None and hi is None:
            return self.battles.generate_enemies(tier, self.parties.size)
        lo = max(1, min(config.WAVE_MAX_LEVEL, lo or 1))
        hi = max(lo, min(config.WAVE_MAX_LEVEL, hi or lo))
        out = []
        for _ in range(self.parties.size):
            lvl = self.rng.randint(lo, hi)
            pool = bestiary.pool_for_any(lvl)
            out.append(bestiary.build_enemy(self.rng.choice(pool), lvl, pit=True))
        return out

    def _skirmish_gen(self, pid: int, tier: int, lo: Optional[int] = None, hi: Optional[int] = None, waves: int = 1):
        self._require_full(pid)
        waves = max(1, min(config.WAVE_MAX_WAVES, int(waves)))
        party = self._ready_party(pid)
        total_xp, won, log = 0, 0, []
        report = None
        for w in range(waves):
            enemies = self.wave_enemies(tier, lo, hi)
            report = yield from self._battle_gen(party, enemies, permadeath=False, split_xp=True, xp_mult=config.WAVE_XP_MULT, loot=False)
            self._after_battle(party, report, scale=0.5, wear=False)     # morale and feelings react; gear is not worn by a drill
            total_xp += report.xp
            log.extend([f"🌊 Wave {w + 1}/{waves}"] + report.log if waves > 1 else report.log)
            for s in party:
                if s.id in self.roster:
                    s.hp = max(1, s.hp)                             # a simulation: nobody is lost
            if not report.victory:
                break
            won += 1
        report.log = log
        report.xp = total_xp
        events: List[str] = []
        level_f = 1 + 0.5 * (tier - 1) if lo is None else 1 + (((lo or 1) + (hi or lo or 1)) / 2 - 1) / 20
        for s in party:
            if s.id not in self.roster:
                continue
            attributes.practise(s, s.arch.discipline, config.WAVE_PROF * level_f * won, 0.0)
            s.needs.add("esteem", 3 if won else 0)
        for i, a in enumerate(party):                               # fighting side by side builds teamwork
            for b in party[i + 1:]:
                self.social.add_bond(a, b, config.WAVE_BOND * won)
        report.log.append(f"🧪 Simulation over ({won}/{waves} waves won): nobody is hurt for real - {total_xp} XP and battle proficiency gained.")
        events.extend(self._spend(config.WAVE_TICKS * waves))
        report.log.extend(events)
        self.journal.extend(events)
        return report

    def _ready_party(self, pid: int) -> List[Slime]:
        self._require_full(pid)
        party = self.party_members(pid)
        for s in party:
            if s.state != "idle" or s.in_dungeon:
                raise InvalidAction(f"{s.name} is {s.in_dungeon and 'inside a dungeon' or s.state}.")
            if s.grounded:
                raise InvalidAction(f"{s.name} is grounded after a brawl.")
            if (why := self.refusal(s, "dungeon")):
                raise InvalidAction(f"{s.name} {why}.")
        return party

    def _battle_gen(self, party, enemies, intel: float = 1.0, allow_manual: bool = True, **opts):
        """One fight as a generator: party synergy (compatibility) and scouting intel applied. Under a manual flow it
        yields at every party slime's turn; the generator returns the BattleReport."""
        syn = self.social.synergy(party) * intel * (1 + self.relations.synergy_delta(party)) * (1 + self._leader_bonus(party))
        self.relations.prebattle(party, emotions)
        bc = 6 * self.keeper.rank("battle_cry")
        if bc:
            for s in party:
                emotions.feel(s, "determination", bc)
                emotions.feel(s, "pride", bc)
        flow = self.flow if allow_manual else None
        run = self.battles.start(party, enemies, synergy=syn, manual=bool(flow and flow["manual"]), **opts)
        run.log.insert(1, f"🤝 Party synergy {syn - 1:+.1%} (avg compatibility "
                          f"{self.social.avg_compat(party):+.0f}"
                          + (f", scouting intel {intel - 1:+.0%}" if intel != 1.0 else "") + ")")
        if flow is not None:
            flow["run"] = run
        run.advance()
        while not run.done:
            yield run
        if flow is not None:
            flow["run"] = None
        return run.report

    def _run_battle(self, party, enemies, intel: float = 1.0, **opts) -> BattleReport:
        """An automatic fight (no pausing): used by the activities that cannot be commanded by hand."""
        gen = self._battle_gen(party, enemies, intel, allow_manual=False, **opts)
        try:
            next(gen)
        except StopIteration as stop:
            return stop.value
        raise RuntimeError("an automatic battle paused")

    # ---- manual battles ("take command") -------------------------------------------------------------
    # Only the Hollow Descent, the Gloop Pit and skirmishes can be fought by hand. Each is a generator that yields
    # whenever a party slime must choose; `flow` is the one battle in progress (kept in memory, never saved: the
    # slimes' HP is only written back when the fight ends, so an abandoned battle simply never happened).
    def _play(self, gen, kind: str, manual: bool, pid: Optional[int] = None):
        if self.flow is not None:
            raise InvalidAction("A battle is already under way - finish it first.")
        self.flow = dict(kind=kind, gen=gen, manual=bool(manual), run=None, pid=pid)
        return self._pump()

    def _pump(self):
        """Resume the current flow. Returns its result when it finishes, or None while it waits for orders."""
        f = self.flow
        try:
            next(f["gen"])
            return None
        except StopIteration as stop:
            self.flow = None
            return stop.value
        except BaseException:
            self.flow = None
            raise

    def battle_run(self):
        """The BattleRun waiting for orders, or None."""
        f = self.flow
        return f["run"] if f and f["run"] is not None and not f["run"].done else None

    def battle_act(self, ability: str, target=None):
        run = self.battle_run()
        if run is None or run.waiting is None:
            raise InvalidAction("No slime is waiting for orders.")
        try:
            run.act(ability, target)
        except ValueError as e:
            raise InvalidAction(str(e))
        return self._pump()

    def battle_auto_turn(self):
        run = self.battle_run()
        if run is None or run.waiting is None:
            raise InvalidAction("No slime is waiting for orders.")
        run.auto_turn()
        return self._pump()

    def battle_set_manual(self, manual: bool):
        """Switch between commanding by hand and letting the slimes fight on their own - for the rest of this
        session (every later fight of a Pit session too)."""
        if self.flow is None:
            raise InvalidAction("There is no battle to take command of.")
        self.flow["manual"] = bool(manual)
        run = self.battle_run()
        if run is not None:
            run.set_manual(manual)
        return self._pump()

    def abandon_battle(self) -> None:
        """Drop a battle nobody will finish (a session restore): no HP was written, so nothing happened."""
        f, self.flow = self.flow, None
        if f:
            f["gen"].close()

    def _after_battle(self, party, report: BattleReport, boss: bool = False, scale: float = 1.0, wear: bool = True) -> None:
        """Morale and bonds react to the outcome (deaths are handled when the dead are reaped)."""
        if wear:
            report.log.extend(self._wear_items(party))
        alive = [s for s in party if s.hp > 0]
        lost = [s for s in party if s.hp <= 0 or s in report.fallen]
        if report.victory:
            self._xp("win", config.KEEPER_XP["boss"] if boss else config.KEEPER_XP["win"])
            bonus = self.relations.mentee_xp(party, report.xp)
            mx = 1 + self.keeper.rank("mentors_eye")
            for sid, xp_ in bonus.items():
                if sid in self.roster and self.roster[sid].hp > 0:
                    report.log.extend(add_xp(self.roster[sid], int(xp_ * mx)))
            for s in alive:
                emotions.feel(s, "joy", 14 * scale + 4)
                emotions.feel(s, "pride", (10 + (15 if boss else 0)) * scale + 2)
                emotions.soothe(s, "fear", 10)
                emotions.soothe(s, "anxiety", 8)
                if boss and awakening.candidate(s):
                    s.awareness += 3.0
        elif report.winner == "foes":
            for s in alive:
                emotions.feel(s, "sadness", 18 * scale + 4)
                emotions.feel(s, "anger", 12 * scale + 2)
                emotions.feel(s, "fear", 12 * scale + 2)
                emotions.feel(s, "determination", 10)
        for s in alive:
            if lost and s not in lost:
                emotions.feel(s, "sadness", 8 * len(lost))
                emotions.feel(s, "determination", 8)
        if report.victory:
            for s in alive:
                self.social.shift_morale(s, scale * (config.MORALE_WIN + (config.MORALE_BOSS_WIN if boss else 0)))
            for i, a in enumerate(alive):
                for b in alive[i + 1:]:
                    self.social.add_bond(a, b, 2 * scale)
        elif report.winner == "foes":
            for s in alive:
                self.social.shift_morale(s, scale * config.MORALE_LOSS)

    def _fight_gen(self, party, enemies, hours: int, **opts):
        """Run a battle, bury the fallen, then let `hours` pass (the colony keeps living)."""
        report = yield from self._battle_gen(party, enemies, **opts)
        events: List[str] = []
        self._after_battle(party, report)
        self._reap(events)
        if hours:
            events.extend(self._spend(hours))
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
        slot = equipment.GEAR.get(key).slot
        if slot in s.items:
            self.unequip_item(sid, slot)
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
            for it in ([] if where == "Gloop Pit" else list(f.items.values())):
                f.items.pop(it.slot, None)
                best = max(survivors, key=lambda x: self.social.compat(f, x)) if survivors else None
                c = max(config.GEAR_RECOVERY_MIN, min(config.GEAR_RECOVERY_MAX, config.GEAR_RECOVERY_BASE
                        + config.GEAR_RECOVERY_SYNERGY_SLOPE * (syn - 1) + self.social.compat(f, best) / 400.0)) \
                    if best else 0.0
                if self.rng.random() < c:
                    self.vault[it.uid] = it
                    log.append(f"🎒 {best.name} carries {f.name}'s {it.label()} back ({c:.0%} chance).")
                else:
                    log.append(f"💨 {f.name}'s {it.label()} is lost in the {where} forever.")
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

    # ---- slime ascension, stones, chamber (ascension.py) ------------------------------------------------
    def _free_slime(self, sid: int) -> Slime:
        s = self.slime(sid)
        if s.busy:
            raise InvalidAction(f"{s.name} is away ({s.in_dungeon or s.state}).")
        return s

    def ascend_slime_rarity(self, sid: int) -> str:
        """Common > uncommon > rare > epic > legendary, paid in white gel (10 / 100 / 1000 / 10000)."""
        s = self._free_slime(sid)
        up = ascension.next_rarity(s.rarity)
        if not up:
            raise InvalidAction(f"{s.name} is already legendary.")
        if s.level < config.RARITY_ASCEND_LEVEL or s.stars < config.MAX_STARS:
            raise InvalidAction(f"{s.name} must reach level {config.RARITY_ASCEND_LEVEL} and {config.MAX_STARS} stars "
                                f"to rise in rarity (now level {s.level}, {s.stars} stars).")
        self.wallet.spend("white_gel", ascension.rarity_cost(s))
        old = s.max_hp
        s.rarity = up
        s.star_peak = max(s.star_peak, s.stars)  # unlocked star attributes are kept
        s.stars = 1                              # a new rarity starts again at one star
        s.hp = max(1, min(s.max_hp, s.hp + s.max_hp - old))
        s.needs.add("esteem", 20)
        self.social.shift_morale(s, 10)
        self._xp("ascend", config.KEEPER_XP["ascend"])
        return (f"✨ {s.name} ascends to {up}! (stats x{config.RARITY_STAT_MULT[up]}) Stars reset to 1, but the star attributes "
                f"it unlocked are kept (and hit harder at the new rarity); more stars strengthen them further.")

    def unground(self, sid: int) -> str:
        """Let a grounded slime out. The quarrel stays; it can brawl again if it is left to escalate."""
        s = self.slime(sid)
        if not s.grounded:
            raise InvalidAction(f"{s.name} is not grounded.")
        s.grounded = False
        s.needs.add("belonging", 5)
        return f"{s.name} is let out. The quarrel is still unresolved."

    def ascend_slime_star(self, sid: int) -> str:
        """Add a star, paid in ascension stones (10 / 100 / 1000 / 10000 common-stone equivalents)."""
        s = self._free_slime(sid)
        need = ascension.star_cost(s)
        if need is None:
            raise InvalidAction(f"{s.name} already has {config.MAX_STARS} stars.")
        lv = ascension.star_level(s)
        if s.level < lv:
            raise InvalidAction(f"{s.name} must reach level {lv} to ascend to {s.stars + 1} stars (now level {s.level}).")
        ascension.pay_stones(self.wallet, need)
        old = s.max_hp
        s.stars += 1
        s.star_peak = max(s.star_peak, s.stars)
        s.hp += s.max_hp - old
        s.needs.add("esteem", 20)
        self.social.shift_morale(s, 10)
        self._xp("ascend", config.KEEPER_XP["ascend"])
        return f"🌟 {s.name} ascends to {s.stars} stars!"

    def merge_gel(self, n: int = 1) -> str:
        """Fuse white gel into purple gel: GEL_MERGE white gel per purple."""
        n = int(n)
        if n < 1:
            raise InvalidAction("Merge at least one.")
        self.wallet.spend("white_gel", config.GEL_MERGE * n)
        self.wallet.add("purple_gel", n)
        return f"🟣 {config.GEL_MERGE * n} white gel fuse into {n} purple gel."

    def merge_stone_rarity(self, rarity: str) -> str:
        if rarity not in config.RARITIES:
            raise InvalidAction(f"Unknown rarity '{rarity}'.")
        n = ascension.merge_stones(self.wallet, rarity)
        return f"💎 {n * config.STONE_MERGE} {rarity} stones fuse into {n} {ascension.next_rarity(rarity)}."

    def _consume_slime(self, s: Slime, stress: float) -> None:
        """Remove a slime sacrificed by the player: gear comes home, the colony mourns, stress rises."""
        amp = 1 + config.SACRIFICE_STRESS_AMP * self.sacrifice_stress
        friends = {i for f in self.conflicts.friends if s.id in f for i in f if i != s.id}
        friends |= {i for k, v in self.social.bonds.items() if s.id in k and v >= 20 for i in k if i != s.id}
        self._return_gear(s)
        del self.roster[s.id]
        self.conflicts.forget(s.id)
        self.parties.remove(s.id)
        self._lose_ties(s)
        self.social.forget(s.id)
        for o in self.slimes():
            base = config.MERGE_MORALE_FRIENDS if o.id in friends else config.MERGE_MORALE_OTHERS
            self.social.shift_morale(o, base * amp)
            self._mourn_sacrifice(o, o.id in friends, False)
        self.sacrifice_stress += stress

    @staticmethod
    def _mourn_sacrifice(o: Slime, friend: bool, target: bool) -> None:
        """Feelings after a merge / chamber / ego fusion: friends grieve and rage, the survivor feels guilty,
        everyone else wonders whether they are next."""
        if friend:
            emotions.feel(o, "sadness", 30)
            emotions.feel(o, "anger", 20)
        if target:
            emotions.feel(o, "guilt", 28)
            emotions.feel(o, "sadness", 10)
        else:
            emotions.feel(o, "fear", 8)
            emotions.feel(o, "anxiety", 6)

    def chamber_preview(self, sid: int) -> Dict[str, int]:
        return ascension.chamber_yield(self.slime(sid), self.buildings.level("chamber"))

    def destroy_slime(self, sid: int) -> List[str]:
        """The Destruction Chamber breaks a slime into white gel and ascension stones (more for rarity and stars)."""
        s = self._free_slime(sid)
        if s.id == self.vice:
            raise InvalidAction(f"{s.name} is the Vice Keeper and cannot be destroyed. Dismiss them first.")
        y = ascension.chamber_yield(s, self.buildings.level("chamber"))
        name, label = s.name, f"{config.RARITY_TAG[s.rarity]} {s.star_str()} Lv{s.level} {s.arch.name}"
        self._consume_slime(s, config.CHAMBER_STRESS)
        self.wallet.add_many(y)
        return [f"🔥 {name} ({label}) is destroyed in the chamber: " +
                ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in y.items()) + ".",
                f"   The colony mourns. Sacrifice stress is now {self.sacrifice_stress:.1f}."]

    def _farm_loot(self, foes: int, log: List[str]) -> None:
        """Every farming dungeon (Pit, Rift, Quarry) also hands out a little of the other resources, rarely."""
        got: Dict[str, int] = {}
        for _ in range(foes):
            if self.rng.random() < config.FARM_LOOT_CHANCE:
                key = self.rng.choice(list(config.FARM_LOOT))
                lo, hi = config.FARM_LOOT[key]
                got[key] = got.get(key, 0) + self.rng.randint(lo, hi)
        if got:
            self.wallet.add_many(got)
            log.append("🎁 Also found " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in got.items()) + ".")

    def _stone_side_drop(self, where: str, foes: int, log: List[str]) -> None:
        """Other dungeons hide the odd common stone."""
        n = sum(1 for _ in range(foes) if self.rng.random() < config.STONE_SIDE_DROP.get(where, 0) * (1 + 0.2 * self.keeper.rank("stonecutter")))
        if n:
            self.wallet.add("stone_common", n)
            log.append(f"💎 Found {n} common stone{'s' if n > 1 else ''}.")

    # ---- potions & herbs (potions.py) -----------------------------------------------------------------
    def _herb_drop(self, where: str, foes: int, log: List[str], terrain=None) -> None:
        """Coloured herbs for the Alchemy Lab. The terrain decides the main colour (so the daily Pit's herb changes
        with its theme); plentiful in the Pit, a few elsewhere."""
        p = config.HERB_DROP.get(where, 0)
        got: Dict[str, int] = {}
        local = config.TERRAIN_HERB.get(terrain.kind) if terrain else None
        for _ in range(foes):
            if self.rng.random() < p:
                color = local if local and self.rng.random() < config.HERB_LOCAL_SHARE else self.rng.choice(config.HERBS)
                got[color] = got.get(color, 0) + max(1, round(self.rng.randint(1, 3) * (1 + 0.2 * self.keeper.rank("green_thumb"))))
        if got:
            self.wallet.add_many({potions.herb_key(c): n for c, n in got.items()})
            log.append("🌿 Gathered " + ", ".join(f"{n} {c} herb{'s' if n > 1 else ''}" for c, n in got.items()) + ".")

    # ---- autonomy: slimes help themselves to (at most) 66% of a stock ------------------------------------
    def _potion_free(self, k: str) -> bool:
        """May a slime take one of these by itself? Only while more than 34% of the most ever held remains."""
        stock = self.potions.get(k, 0)
        peak = max(self.potion_peak.get(k, 0), stock)
        return stock > math.ceil(peak * (1 - self.share))

    def _auto_drink(self, s: Slime, kind: str, log: List[str]) -> bool:
        if any(b["kind"] == kind for b in s.buffs) or len(s.buffs) >= attributes.potion_slots(s):
            return False
        grades = sorted(g for (kk, g) in ((k.split(":")[0], int(k.split(":")[1])) for k in self.potions) if kk == kind)
        for g in grades:                                     # the humblest grade that is free to take
            if self._potion_free(potions.key(kind, g)):
                log.append("🧃 " + self.use_potion(s.id, kind, g))
                return True
        return False

    _LIKES = dict(barbarian=("might", "ironhide", "bulwark"), mage=("arcane", "renewal"), medic=("renewal", "arcane", "bulwark"),
                  rogue=("fury", "gale", "might"), ranger=("fury", "gale", "might"),
                  necromancer=("bloodthirst", "arcane", "renewal"))

    def _relic_free(self) -> bool:
        self.vault_peak = max(self.vault_peak, len(self.vault))
        return len(self.vault) > math.ceil(self.vault_peak * (1 - self.share))

    def _gear_free(self, key: str) -> bool:
        have = self.inventory.items.get(key, 0)
        self.gear_peak[key] = peak = max(self.gear_peak.get(key, 0), have)
        return have > math.ceil(peak * (1 - self.share))

    @staticmethod
    def _relic_score(s: Slime, it) -> float:
        st = it.stats_for(s)
        return sum(st.values()) * (1 + 0.5 * sum(m["value"] for m in it.mods) * it.mod_scale())

    def _auto_equip(self, s: Slime, log: List[str]) -> None:
        """A slime dresses itself from the vault / armory stock: fills empty slots, or swaps for a clearly better
        relic - but only while at least 34% of what you have ever held is left untouched."""
        for slot in items_mod.SLOTS:
            cur, legacy = s.items.get(slot), s.gear.get(slot)
            cur_score = self._relic_score(s, cur) if cur else (
                sum(equipment.GEAR.get(legacy).stats.values()) if legacy else 0.0)
            best, best_sc = None, 0.0
            for it in self.vault.values():
                if it.slot != slot or items_mod.can_wield(s, it):
                    continue
                sc = self._relic_score(s, it)
                if sc > best_sc:
                    best, best_sc = it, sc
            if best and best_sc > cur_score * 1.25 and (cur is not None or self._relic_free()):
                log.append("🎒 " + self.equip_item(s.id, best.uid).splitlines()[0])
                continue
            if not cur and not legacy:                          # plain armory gear for an empty slot
                keys = [k for k in self.inventory.items if equipment.GEAR.get(k).slot == slot and self._gear_free(k)]
                if keys:
                    k = max(keys, key=lambda k: sum(equipment.GEAR.get(k).stats.values()))
                    log.append("🎒 " + self.inventory.equip(s, k))

    def brew_for_post(self, brewer: Slime) -> List[str]:
        """The appointed brewer's shift: brew the basic or mixed potion the colony is shortest of, within its means
        (at most 66% of each ingredient stock, like slimes helping themselves)."""
        lab = self.buildings.level("alchemy")
        wanted = []
        for s in self.slimes():
            wanted += list(self._LIKES.get(s.archetype, ()))
        wanted += list(potions.KINDS)[:4]
        stock = lambda k: sum(n for kk, n in self.potions.items() if kk.split(":")[0] == k)
        for kind in sorted(set(wanted), key=lambda k: (stock(k), k)):
            if stock(kind) >= config.AUTONOMY_BREW_STOCK + 2:
                continue
            for grade in range(lab, 0, -1):
                c = potions.cost(kind, grade)
                if all(v <= self.wallet.get(k) * self.share for k, v in c.items()):
                    return ["⚗️ " + x for x in self._brew_core(brewer, kind, grade, wait=False)]
        return []

    def _auto_brew(self, log: List[str]) -> None:
        """Once a day a free slime (magical ones first) brews a potion the colony is short of, spending at most 66%
        of each ingredient stock."""
        lab = self.buildings.level("alchemy")
        free = [s for s in self.slimes() if not s.busy and s.state == "idle" and s.hp > 0]
        if not free:
            return
        brewer = max(free, key=lambda s: s.core_stats()["mag"] + (50 if s.archetype in ("medic", "necromancer") else 0))
        wanted = []
        for s in self.slimes():
            wanted += list(self._LIKES.get(s.archetype, ()))
        stock = lambda k: sum(n for kk, n in self.potions.items() if kk.split(":")[0] == k)
        for kind in sorted(set(wanted), key=lambda k: (stock(k), k)):
            if stock(kind) >= config.AUTONOMY_BREW_STOCK:
                continue
            for grade in range(lab, 0, -1):
                c = potions.cost(kind, grade)
                if all(v <= self.wallet.get(k) * self.share for k, v in c.items()):
                    log.extend("⚗️ " + x for x in self.brew(brewer.id, kind, grade, wait=False))
                    return

    def _autonomy_prepare(self, members: List[Slime], log: List[str]) -> None:
        """Before a trip the slimes pick the potions that suit their class (a couple each)."""
        if not self.autonomy:
            return
        for s in members:
            self._auto_equip(s, log)
            n = 0
            for kind in self._LIKES.get(s.archetype, ()):
                if n >= config.AUTONOMY_MAX_BUFFS:
                    break
                if self._auto_drink(s, kind, log):
                    n += 1

    def _autonomy_tick(self, log: List[str]) -> None:
        """Hourly: tired slimes drink stamina potions, hurt ones vigor, worn gear gets mended - all unasked."""
        if not self.autonomy:
            return
        for s in self.slimes():
            if s.busy or s.hp <= 0:
                continue
            if s.stamina_frac < config.AUTONOMY_STAMINA_BELOW:
                self._auto_drink(s, "stamina", log)
            if s.hp < s.max_hp * config.AUTONOMY_HP_BELOW:
                self._auto_drink(s, "vigor", log)
            self._auto_repair(s, log)
            self._auto_equip(s, log)
        if self.tick_count % 24 == config.AUTONOMY_BREW_HOUR:
            self._auto_brew(log)

    def _auto_repair(self, s: Slime, log: List[str]) -> None:
        for it in list(s.items.values()):
            if it.unbreakable or it.durability >= it.max_durability * config.AUTONOMY_REPAIR_BELOW:
                continue
            m = items_mod.material(it.rarity)
            need = math.ceil((it.max_durability - it.durability) / 6) * (1 + config.RARITIES.index(it.rarity))
            if need <= self.wallet.get(m) * self.share:
                self.wallet.add(m, -need)
                it.durability = it.max_durability
                log.append(f"🔧 {s.name} mends {it.label()} by itself ({need} {m}).")

    def set_forage(self, on: bool) -> str:
        self.forage = bool(on)
        return ("Slimes with no party and nothing to do will go foraging on their own." if on else
                "Slimes will wait at home until you send them out.")

    def _forage_tick(self) -> None:
        """Idle slimes that belong to no party go and gather resources by themselves, in the most rewarding zone they can
        clear comfortably. Only rested, fed, healthy slimes set out; they come home to sleep when tired."""
        if not self.forage:
            return
        zones = sorted(ZONES, key=lambda z: -z.duration)
        for s in self.slimes():
            if (s.state != "idle" or s.job or s.in_dungeon or s.grounded or s.id == self.vice or s.hp <= 0
                    or self.parties.party_of(s.id) or s.hp < s.max_hp * config.FORAGE_MIN_HP
                    or s.needs.get("energy") < config.FORAGE_MIN_ENERGY or s.needs.get("food") < config.FORAGE_MIN_FOOD):
                continue
            zone = next((z for z in zones if s.power_rating() >= z.danger * config.FORAGE_SAFETY), None)
            if zone:
                self.hunts.start(s, zone.key)

    def set_autonomy(self, on: bool) -> str:
        self.autonomy = bool(on)
        return "Slimes will help themselves to up to 66% of potions, relics, gear and materials - and brew on their own." if on else \
            "Slimes will wait for your orders."

    def potion_count(self, kind: str, grade: int) -> int:
        return self.potions.get(potions.key(kind, grade), 0)

    def brew(self, sid: int, kind: str, grade: int, wait: bool = True) -> List[str]:
        """A slime brews a potion in the Alchemy Lab (takes 2 hours per grade). Lab level caps the grade."""
        s = self._free_slime(sid)
        return self._brew_core(s, kind, grade, wait)

    def _brew_core(self, s: Slime, kind: str, grade: int, wait: bool = True) -> List[str]:
        if kind not in potions.KINDS:
            raise InvalidAction(f"Unknown potion '{kind}'.")
        if not 1 <= grade <= 5:
            raise InvalidAction("Grade must be 1-5.")
        lab = self.buildings.level("alchemy")
        if grade > lab:
            raise InvalidAction(f"The Alchemy Lab is level {lab}: it brews up to grade {lab}.")
        c = potions.cost(kind, grade)
        self.wallet.spend_many(c)
        chance = potions.success_chance(s, grade, lab, kind)
        ok = self.rng.random() < chance
        crit = ok and grade < 5 and grade + 1 <= lab and self.rng.random() < config.BREW_CRIT
        if wait:
            self._occupy([s], potions.brew_hours(grade), "lab")
        pk = potions.KINDS[kind]
        if not ok:
            self.wallet.add_many({k: v // 2 for k, v in c.items() if k.startswith("herb_")})
            return [f"💥 {s.name}'s brew fails ({chance:.0%} chance). Half the herbs are saved."]
        g = grade + 1 if crit else grade
        k = potions.key(kind, g)
        self.potions[k] = self.potions.get(k, 0) + 1
        self.potion_peak[k] = max(self.potion_peak.get(k, 0), self.potions[k])
        if wait:
            self._xp("brew", config.KEEPER_XP["brew"])
        s.needs.add("esteem", 8)
        return [f"{pk.emoji} {s.name} brews a grade {g} {pk.name}" + (" - a masterwork!" if crit else ".")]

    def use_potion(self, sid: int, kind: str, grade: int) -> str:
        s = self._tend(sid)
        k = potions.key(kind, grade)
        if self.potions.get(k, 0) <= 0 or kind not in potions.KINDS:
            raise InvalidAction("You have no such potion.")
        self._check_potion_slot(s, kind)
        self.potions[k] -= 1
        if not self.potions[k]:
            del self.potions[k]
        return self._drink(s, kind, grade)

    @staticmethod
    def _check_potion_slot(s: Slime, kind: str) -> None:
        if not any(b["kind"] == kind for b in s.buffs) and len(s.buffs) >= attributes.potion_slots(s):
            raise InvalidAction(f"{s.name} can only have {attributes.potion_slots(s)} potion(s) active at once "
                                f"({s.stars}-star). Wait for one to wear off.")

    def _drink(self, s: Slime, kind: str, grade: int) -> str:
        s.buffs = [b for b in s.buffs if b["kind"] != kind]
        s.buffs.append(dict(kind=kind, grade=grade, bonus=potions.bonus(grade), hours=potions.hours(grade)))
        pk = potions.KINDS[kind]
        if kind == "stamina":
            s.stamina_frac = min(1.0, s.stamina_frac + 0.25)
        elif kind == "vigor":
            s.hp += int(s.max_hp * potions.bonus(grade) / (1 + potions.bonus(grade)))
        return (f"{pk.emoji} {s.name} drinks a grade {grade} {pk.name}: {pk.effect} "
                f"(+{potions.bonus(grade):.0%} for {potions.hours(grade)}h).")

    # ---- weapons: proficiency, memory, repairs ----------------------------------------------------------
    def _learn_family(self, s: Slime, family: str) -> Optional[str]:
        """A slime keeps up to three weapon families in mind; a fourth makes it forget the least practised."""
        if not family or family in s.weapon_memory:
            return None
        msg = None
        if len(s.weapon_memory) >= config.WEAPON_MEMORY:
            gone = min(s.weapon_memory, key=lambda f: s.proficiency.get(f, 0))
            s.weapon_memory.remove(gone)
            s.proficiency.pop(gone, None)
            msg = f"   {s.name} forgets how to use a {gone}."
        s.weapon_memory.append(family)
        s.proficiency.setdefault(family, 0)
        return msg

    def slime_repair(self, sid: int) -> List[str]:
        """The slime mends its own relics with scrap (cheaper than gel, a little time, and a proud morale lift)."""
        s = self._free_slime(sid)
        worn = [it for it in s.items.values() if not it.unbreakable and it.durability < it.max_durability]
        if not worn:
            raise InvalidAction(f"{s.name} has nothing to repair.")
        need = {}
        for it in worn:
            m = items_mod.material(it.rarity)
            need[m] = need.get(m, 0) + math.ceil((it.max_durability - it.durability) / 6) * \
                (1 + config.RARITIES.index(it.rarity))
        self.wallet.spend_many(need)
        for it in worn:
            it.durability = it.max_durability
        self._occupy([s], config.SLIME_REPAIR_HOURS, "lab")
        self.social.shift_morale(s, 3)
        s.needs.add("esteem", 6)
        return [f"🔧 {s.name} repairs " + ", ".join(it.label() for it in worn) + " (" +
                ", ".join(f"{v} {k}" for k, v in need.items()) + "). Morale up."]

    # ---- relics: forge, repair, salvage, ego (items.py) ---------------------------------------------
    def _return_gear(self, s: Slime) -> None:
        """A slime leaves the colony (merged, fused): everything it wore goes back to the colony."""
        for key in s.gear.values():
            self.inventory.add(key)
        for it in s.items.values():
            self.vault[it.uid] = it
        s.gear, s.items = {}, {}

    def new_item(self, lure: bool = False, rarity: str = None) -> items_mod.Item:
        it = items_mod.roll_item(self.rng, self.next_item_id, lure, rarity)
        self.next_item_id += 1
        self.vault[it.uid] = it
        return it

    def find_item(self, uid: int):
        """(item, holder) - holder is the Slime wearing it, or None when it is in the vault."""
        if uid in self.vault:
            return self.vault[uid], None
        for s in self.slimes():
            for it in s.items.values():
                if it.uid == uid:
                    return it, s
        raise InvalidAction(f"No relic #{uid}.")

    def _item_ready(self, uid: int):
        it, holder = self.find_item(uid)
        if holder is not None and holder.busy:
            raise InvalidAction(f"{holder.name} is away ({holder.in_dungeon or holder.state}).")
        return it, holder

    def equip_item(self, sid: int, uid: int) -> str:
        s = self.slime(sid)
        if s.busy:
            raise InvalidAction(f"{s.name} is away ({s.in_dungeon or s.state}).")
        it, holder = self._item_ready(uid)
        why = items_mod.can_wield(s, it)
        if why:
            raise InvalidAction(why)
        if holder is s:
            raise InvalidAction(f"{s.name} already wields it.")
        if holder is not None:
            holder.items.pop(it.slot, None)
        else:
            del self.vault[uid]
        if it.slot in s.items:
            self.unequip_item(sid, it.slot)
        if it.slot in s.gear:
            self.inventory.add(s.gear.pop(it.slot))
        s.items[it.slot] = it
        it.bond = 0
        forgot = self._learn_family(s, it.spec.family)
        s.hp = min(s.hp + int(it.stats_for(s).get("hp", 0)), s.max_hp)
        return (f"{s.name} wields {it.label()} (compatibility {it.compat(s)}%, "
                f"x{it.compat_mult(s):.2f} stats)." + (f"\n{forgot}" if forgot else ""))

    def unequip_item(self, sid: int, slot: str) -> str:
        s = self.slime(sid)
        if s.busy:
            raise InvalidAction(f"{s.name} is away ({s.in_dungeon or s.state}).")
        it = s.items.pop(slot, None)
        if not it:
            raise InvalidAction(f"{s.name} wields no relic in the {slot} slot.")
        self.vault[it.uid] = it
        s.hp = min(s.hp, s.max_hp)
        return f"{s.name} puts away {it.label()}."

    def level_item(self, uid: int) -> str:
        it, _ = self._item_ready(uid)
        if it.level >= config.ITEM_MAX_LEVEL:
            raise InvalidAction(f"{it.name} is at level {config.ITEM_MAX_LEVEL} - ascend a star.")
        self.wallet.spend_many(it.level_cost())
        it.level += 1
        return f"🔨 {it.label()} grows stronger."

    def ascend_star(self, uid: int) -> str:
        it, _ = self._item_ready(uid)
        if it.level < config.ITEM_MAX_LEVEL:
            raise InvalidAction("Only a level-10 relic can ascend a star.")
        if it.stars >= config.MAX_STARS:
            raise InvalidAction("Already five stars - try raising its rarity.")
        if self.buildings.level("armory") < it.stars:
            raise InvalidAction(f"The Armory must be level {it.stars} to forge {it.stars + 1} stars.")
        self.wallet.spend_many(it.star_cost())
        it.stars += 1
        it.level = 1
        it.durability = it.max_durability
        return f"🌟 {it.label()} ascends to {it.stars} stars and is fully mended!"

    def ascend_rarity(self, uid: int) -> str:
        it, _ = self._item_ready(uid)
        up = items_mod.next_rarity(it.rarity)
        if it.ego:
            raise InvalidAction("Ego relics cannot be reforged.")
        if not up:
            raise InvalidAction("It is already legendary.")
        if it.stars < config.MAX_STARS or it.level < config.ITEM_MAX_LEVEL:
            raise InvalidAction("Rarity can be raised only at 5 stars and level 10.")
        if self.buildings.level("armory") < 5:
            raise InvalidAction("The Armory must be level 5 to raise a relic's rarity.")
        self.wallet.spend_many(it.rarity_cost())
        it.rarity = up
        if items_mod.wants_title(it):
            it.title = items_mod.make_title(self.rng)
        mod = items_mod.roll_mod(self.rng, it.mods)
        it.mods.append(mod)
        it.durability = it.max_durability
        return f"💎 {it.label()} is reborn as {up}! New mod: {it.mod_text(mod)}."

    def repair_item(self, uid: int) -> str:
        it, _ = self._item_ready(uid)
        cost = it.repair_cost()
        if cost <= 0:
            raise InvalidAction("It needs no repair.")
        self.wallet.spend("white_gel", cost)
        it.durability = it.max_durability
        return f"🛠️ {it.label()} is mended for {cost} white gel."

    def salvage_item(self, uid: int) -> str:
        it, holder = self._item_ready(uid)
        if it.ego:
            raise InvalidAction("An ego relic holds a soul - it cannot be broken down.")
        y = {k: max(1, int(v * (1 + 0.1 * self.keeper.rank("appraiser")))) for k, v in it.salvage_yield().items()}
        self._xp("forge", config.KEEPER_XP["forge"])
        if holder is not None:
            holder.items.pop(it.slot, None)
            holder.hp = min(holder.hp, holder.max_hp)
        else:
            del self.vault[uid]
        self.wallet.add_many(y)
        return f"♻️ {it.label()} is broken down: " + ", ".join(f"{v} {k}" for k, v in y.items()) + "."

    def merge_items(self, target_uid: int, donor_uid: int) -> str:
        """Feed one relic to another of the same kind of slot: the donor is consumed, the target gains levels
        (its star and rarity are untouched), is fully mended, and may inherit one of the donor's mods."""
        if target_uid == donor_uid:
            raise InvalidAction("A relic can't merge with itself.")
        t, th = self._item_ready(target_uid)
        d, dh = self._item_ready(donor_uid)
        if t.ego or d.ego:
            raise InvalidAction("An ego relic holds a soul - it cannot be merged.")
        if t.slot != d.slot:
            raise InvalidAction(f"Only relics of the same slot merge ({t.slot} vs {d.slot}).")
        gain = max(1, d.grade() // 3)
        before = t.level
        t.level = min(config.ITEM_MAX_LEVEL, t.level + gain)
        t.durability = t.max_durability
        have = {m["kind"] for m in t.mods}
        extra = [m for m in d.mods if m["kind"] not in have]
        note = ""
        if extra and len(t.mods) < items_mod.RARITIES.index(t.rarity) + 1 and self.rng.random() < config.RELIC_MERGE_MOD_CHANCE:
            m = dict(self.rng.choice(extra))
            t.mods.append(m)
            note = f" It inherits {t.mod_text(m)}."
        if dh is not None:
            dh.items.pop(d.slot, None)
            dh.hp = min(dh.hp, dh.max_hp)
        else:
            del self.vault[donor_uid]
        self._xp("forge", config.KEEPER_XP["forge"])
        return (f"🫧 {d.label()} melts into {t.label()}: level {before} -> {t.level}, fully mended.{note}")

    def destroy_gear(self, key: str, n: int = 1) -> str:
        """Scrap spare gear (not equipped) for half of its price."""
        g = equipment.GEAR.get(key)
        n = max(1, int(n))
        if self.inventory.items[key] < n:
            raise InvalidAction(f"You do not have {n} spare {g.name}.")
        for _ in range(n):
            self.inventory.take(key)
        back = {k: max(1, int(v * config.GEAR_SCRAP_REFUND)) * n for k, v in g.cost.items()}
        self.wallet.add_many(back)
        return f"♻️ {n} x {g.emoji}{g.name} scrapped: " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in back.items()) + "."

    def merge_gear(self, key: str, into: str) -> str:
        """Merge GEAR_MERGE_COUNT identical spare gear into one piece of the next tier (same slot)."""
        g, up = equipment.GEAR.get(key), equipment.GEAR.get(into)
        if up.slot != g.slot or up.tier != g.tier + 1:
            raise InvalidAction(f"{g.name} can only merge into a tier {g.tier + 1} {g.slot}.")
        n = config.GEAR_MERGE_COUNT
        if self.inventory.items[key] < n:
            raise InvalidAction(f"Merging needs {n} spare {g.name} (you have {self.inventory.items[key]}).")
        for _ in range(n):
            self.inventory.take(key)
        self.inventory.add(into)
        return f"🫧 {n} x {g.emoji}{g.name} fuse into {up.emoji}{up.name}!"

    def fuse_ego(self, uid: int, sid: int) -> List[str]:
        """Sacrifice a 5-star legendary slime into a 5-star legendary relic: it becomes an EGO relic, wieldable only
        by 5-star legendary slimes. The higher the sacrificed slime's level, the stronger the ego."""
        s = self.slime(sid)
        it, holder = self._item_ready(uid)
        if s.busy:
            raise InvalidAction(f"{s.name} is away ({s.in_dungeon or s.state}).")
        if it.ego:
            raise InvalidAction("It is already an ego relic.")
        if not (it.rarity == "legendary" and it.stars == config.MAX_STARS):
            raise InvalidAction("Only a 5-star legendary relic can be fused.")
        if not (s.rarity == "legendary" and s.stars == config.MAX_STARS):
            raise InvalidAction("Only a 5-star legendary slime can be the soul.")
        if holder is s:
            holder.items.pop(it.slot, None)
            self.vault[it.uid] = it
        elif holder is not None:
            holder.items.pop(it.slot, None)
            self.vault[it.uid] = it
        it.ego = dict(name=s.name, level=s.level, archetype=s.archetype)
        it.durability = it.max_durability
        self._consume_slime(s, config.EGO_MORALE_STRESS)
        return [f"👁️ {s.name} (Lv{s.level} {s.arch.name}) pours their soul into {it.spec.emoji}{it.spec.name}.",
                f"   {it.label()} awakens - stats x{it.power_mult():.1f}, mods doubled, unbreakable. "
                f"Only a 5-star legendary slime can wield it.",
                f"   The colony mourns. Sacrifice stress is now {self.sacrifice_stress:.1f}."]

    def _wear_items(self, party) -> List[str]:
        """Every relic worn into a fight loses a point of durability and grows closer to its wielder."""
        out = []
        for s in party:
            for slot, it in list(s.items.items()):
                it.bond = min(40, it.bond + 1)
                fam = it.spec.family
                if fam:
                    s.proficiency[fam] = s.proficiency.get(fam, 0) + 1
                if it.bond >= config.BOND_MORALE_AT and s.hp > 0:
                    self.social.shift_morale(s, 1)           # trusting your own weapon steadies the nerves
                if it.wear(1):
                    out.append(self._shatter(s, slot, it))
        return out

    def _ko_wear(self, downed, log: List[str]) -> None:
        """A slime knocked out (not killed) keeps its relics, but they take a beating."""
        for s in downed:
            for slot, it in list(s.items.items()):
                if it.wear(config.ADV_KO_WEAR):
                    log.append(self._shatter(s, slot, it))

    def _shatter(self, s: Slime, slot: str, it: items_mod.Item) -> str:
        s.items.pop(slot, None)
        y = it.salvage_yield(broken=True)
        self.wallet.add_many(y)
        s.hp = min(s.hp, s.max_hp)
        return f"💥 {s.name}'s {it.label()} shatters! (" + ", ".join(f"{v} {k}" for k, v in y.items()) + ")"

    # ---- adventure dungeon: the Wayfarer's Rift --------------------------------------------------
    def adventure(self, sids: List[int], runs: int = 5, lure: bool = False) -> GrindResult:
        return self._expedition("adventure", sids, runs, lure)

    def quarry(self, sids: List[int], runs: int = 5) -> GrindResult:
        """The Starfall Quarry: same rules as the Rift (1-5 slimes, monsters one level up, nobody dies) but the prize
        is ASCENSION STONES (and a little XP), not relics."""
        return self._expedition("quarry", sids, runs, False)

    def _expedition(self, kind: str, sids: List[int], runs: int, lure: bool) -> GrindResult:
        """A party of 1-5 slimes (any slimes, no formal party needed) fights waves one level ABOVE their average,
        hunting relics. Nobody dies (like the Pit): a knocked-out slime loses morale and its relics are damaged.
        Rarity odds are far harsher than the gacha's; a lure (1 purple gel per run) multiplies them."""
        sids = list(dict.fromkeys(sids))
        if not 1 <= len(sids) <= config.ADV_MAX_PARTY:
            raise InvalidAction(f"An adventuring party has 1-{config.ADV_MAX_PARTY} slimes.")
        if not 1 <= runs <= config.ADV_MAX_RUNS:
            raise InvalidAction(f"Runs must be 1-{config.ADV_MAX_RUNS}.")
        party = [self.slime(i) for i in sids]
        for s in party:
            if s.state != "idle" or s.in_dungeon:
                raise InvalidAction(f"{s.name} is {s.in_dungeon and 'inside a dungeon' or s.state}.")
            if s.grounded:
                raise InvalidAction(f"{s.name} is grounded after a brawl.")
        res = GrindResult()
        pre: List[str] = []
        self._autonomy_prepare(party, pre)
        res.summary.extend("   " + x for x in pre)
        self._owed = 0.0
        self._set_flag(party, kind)
        try:
            for n in range(1, runs + 1):
                members = [s for s in party if s.id in self.roster]
                if not members:
                    res.stop_reason = "the whole party is gone"
                    break
                if any(s.hp < s.max_hp * config.GRIND_MIN_HP or s.stamina_frac < config.STAMINA_CAMP_AT for s in members):
                    res.summary.append(f"   (camped {self._camp(members)}h)")
                    members = [s for s in party if s.id in self.roster]
                for s in members:
                    if s.state in ("sleeping", "resting"):
                        s.state = "idle"
                if lure:
                    try:
                        self.wallet.spend("purple_gel", config.ADV_LURE_COST)
                    except Exception:
                        lure = False
                        res.summary.append("   (out of purple gel - the lure is spent)")
                avg = sum(s.level for s in members) / len(members)
                theme = dungeon.pit_theme(self.dungeon_seed ^ (0xA11 if kind == "adventure" else 0x57A), self.day * 8 + (n % 8))
                enemies = dungeon.grind_wave(avg, 3 + config.ADV_MONSTER_LEVEL,
                                           max(1, round(len(members) * config.ADV_FOE_RATIO)), self.rng, theme)
                rep = self._run_battle(members, enemies, permadeath=False, split_xp=False,
                                       xp_mult=(config.ADV_XP_MULT if kind == "adventure" else config.QUARRY_XP_MULT),
                                       terrain=theme.terrain)
                place = "🧭 The Wayfarer's Rift" if kind == "adventure" else "💎 The Starfall Quarry"
                rep.log.insert(0, f"{place} (monsters ~lvl {dungeon.grind_level(avg, 4)}) - "
                                  f"{theme.terrain.emoji} {theme.terrain.name}")
                self._after_battle(members, rep, scale=0.4)
                events: List[str] = []
                downed = list(rep.fallen)
                for s in downed:
                    self.social.shift_morale(s, config.GRIND_DEATH_MORALE)
                    events.append(f"💫 {s.name} was knocked out: morale {config.GRIND_DEATH_MORALE:+.0f}.")
                self._ko_wear(downed, events)
                if rep.victory and kind == "quarry":
                    for _ in enemies:
                        if self.rng.random() < config.QUARRY_DROP_PER_FOE * (1 + 0.2 * self.keeper.rank("stonecutter")):
                            got = ascension.roll_stone(self.rng)
                            self.wallet.add_many(got)
                            events.append("💎 Mined " + ", ".join(
                                f"{v} {k.replace('_', ' ')}" for k, v in got.items()) + "!")
                if rep.victory:
                    self._herb_drop(kind, len(enemies), events, theme.terrain)
                    self._farm_loot(len(enemies), events)
                if rep.victory and kind != "quarry":
                    self._stone_side_drop("adventure", len(enemies), events)
                    for _ in enumerate(enemies):
                        if self.rng.random() < config.ADV_DROP_PER_FOE:
                            it = self.new_item(lure)
                            events.append(f"🎁 Found {it.label()}"
                                          + (" - " + ", ".join(it.mod_text(m) for m in it.mods) if it.mods else "") + "!")
                events.extend(self._spend(config.ADV_TICKS))
                rep.log.extend(events)
                res.runs.append(rep)
                tag = "Victory" if rep.victory else "Defeat" if rep.winner == "foes" else "Draw"
                line = f"Run {n}/{runs}: {tag} in {rep.rounds} rounds"
                if rep.knocked_out:
                    line += f", KO: {', '.join(rep.knocked_out)}"
                res.summary.append(line)
                res.summary.extend("   " + e for e in events if any(w in e for w in
                                   ("Found", "Mined", "stone", "herb", "shatters", "knocked", "died", "Also found")))
                self.journal.extend(events)
                if rep.winner == "foes":
                    res.stop_reason = "the whole party was knocked out"
                    break
            else:
                res.stop_reason = "finished all requested runs"
        finally:
            self._release(party)
        return res

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

    def _knowledge(self, floor: int) -> float:
        return self.intel.get(floor, 0.0)

    def floor_horizon(self) -> int:
        """How many floors the colony lists: a little beyond the deepest cleared, in whole segments."""
        h = max(10, self.best_floor + 6)
        return min(dungeon.MAX_FLOOR, -(-h // config.MAIN_BOSS_EVERY) * config.MAIN_BOSS_EVERY)

    def intel_report(self, first: int = 1, last: Optional[int] = None) -> List[dict]:
        last = last or self.floor_horizon()
        return dungeon.intel_view(self.dungeon_seed, range(first, last + 1), self.intel, self.parties.size)

    # ---- main dungeon: The Hollow Descent --------------------------------------------------------
    # Rules: floors are walked in order and every slime must have CLEARED the floor above to enter a floor
    # (per-slime `progress`). A party can only LEAVE at a checkpoint (the boss floors 5, 10, 15 ...), so
    # training and the academy happen between segments. Any number of parties can walk the same floors again.
    def entry_options(self, pid: int) -> List[int]:
        """Floors a party may start from: 1, or the floor after any checkpoint every member has cleared."""
        members = self.party_members(pid)
        low = min((s.progress for s in members), default=0)
        return [1] + [c + 1 for c in range(config.MAIN_BOSS_EVERY, low + 1, config.MAIN_BOSS_EVERY)
                      if c < dungeon.MAX_FLOOR]

    def enter_dungeon(self, pid: int, start: Optional[int] = None) -> str:
        """Enter the Hollow Descent at `start` (default: as deep as every member's progress allows).
        Inside, you may only leave at a checkpoint (after a boss floor)."""
        if pid in self.delves:
            raise InvalidAction("That party is already inside the dungeon.")
        party = self._ready_party(pid)
        options = self.entry_options(pid)
        start = options[-1] if start is None else int(start)
        if start not in options:
            laggard = min(party, key=lambda s: s.progress)
            raise InvalidAction(f"The party can start at floor {', '.join(map(str, options))}. {laggard.name} has only "
                                f"cleared floor {laggard.progress}; every member must have walked the floors above.")
        pre: List[str] = []
        self._autonomy_prepare(party, pre)
        self._set_flag(party, "main")
        self.delves[pid] = dict(floor=start, start=start, hours=0)
        nxt = self._checkpoint_after(start)
        return (f"🕳 {self.parties.get(pid).name} enters the Hollow Descent at floor {start} "
                f"(knowledge {self._knowledge(start):.0f}%). The next exit is after the boss on floor {nxt}."
                + "".join("\n   " + x for x in pre))

    @staticmethod
    def _checkpoint_after(floor: int) -> int:
        """The boss floor that ends the segment containing `floor`."""
        return -(-floor // config.MAIN_BOSS_EVERY) * config.MAIN_BOSS_EVERY

    def can_leave(self, pid: int) -> bool:
        d = self.delves.get(pid)
        return bool(d) and (d["floor"] - 1) % config.MAIN_BOSS_EVERY == 0

    def leave_dungeon(self, pid: int) -> str:
        """Climb out. Only possible at a checkpoint: right after a boss floor (or before the first fight)."""
        d = self.delves.get(pid)
        if not d:
            raise InvalidAction("That party is not inside the dungeon.")
        if not self.can_leave(pid):
            raise InvalidAction(f"There is no way out until the boss of floor {self._checkpoint_after(d['floor'])} "
                                f"falls - or the whole party does.")
        party = self._members_in("main", pid)
        self._clear_flag(party)
        del self.delves[pid]
        for s in party:
            self.social.shift_morale(s, 2)
        return f"{self.parties.get(pid).name} climbs out of the Hollow Descent after {d['hours']}h."

    def retreat_cost(self, pid: int) -> int:
        """Purple gel an emergency retreat costs: a base fee plus one per segment of depth."""
        d = self.delves[pid]
        return config.RETREAT_PURPLE_BASE + d["floor"] // config.MAIN_BOSS_EVERY

    def retreat_ambush_chance(self, pid: int) -> float:
        d = self.delves[pid]
        return min(0.7, config.RETREAT_AMBUSH * (1 + 0.05 * d["floor"]) * (1 - 0.6 * self._knowledge(d["floor"]) / 100))

    def retreat(self, pid: int) -> List[str]:
        """Break off and flee mid-segment: the Descent's one costed way out (the checkpoint exit stays free).
        Costs purple gel and morale, leaves the party shaken (stamina drained), and the flight can be ambushed -
        deaths are permanent. Every floor the party cleared stays cleared for each slime; to go back down they must
        enter again from a checkpoint (floor 1 or the floor after a boss)."""
        d = self.delves.get(pid)
        if not d:
            raise InvalidAction("That party is not inside the dungeon.")
        if self.can_leave(pid):
            raise InvalidAction("The party stands at a checkpoint: it can simply leave for free.")
        self._delve_wait(d)
        party = self._members_in("main", pid)
        cost = self.retreat_cost(pid)
        self.wallet.spend("purple_gel", cost)
        out = [f"🏃 {self.parties.get(pid).name} breaks off and flees the Hollow Descent from floor {d['floor']} ({cost} purple gel)."]
        if self.rng.random() < self.retreat_ambush_chance(pid):
            self._ambush_strike(pid, party, d["floor"], out, "Ambushed during the retreat!", "killed fleeing the Hollow Descent")
        survivors = self._members_in("main", pid)
        for s in survivors:
            self.social.shift_morale(s, -config.RETREAT_MORALE)
            s.needs.add("esteem", -10)
            s.stamina_frac = min(s.stamina_frac, 0.3)
        self._clear_flag(survivors)
        self.delves.pop(pid, None)
        if survivors:
            out.append(f"   {len(survivors)} slime(s) stumble out, shaken and exhausted.")
        else:
            out.append("☠ Nobody made it out.")
        self.journal.extend(out)
        return out

    def delve_status(self, pid: int) -> dict:
        d = self.delves.get(pid)
        if not d:
            raise InvalidAction("That party is not inside the dungeon.")
        return dict(floor=d["floor"], start=d["start"], boss_floor=self._checkpoint_after(d["floor"]),
                    hours=d["hours"], knowledge=self._knowledge(d["floor"]), can_leave=self.can_leave(pid),
                    members=self._members_in("main", pid))

    def descend(self, pid: int, floor: Optional[int] = None) -> BattleReport:
        """Convenience: enter the dungeon if needed, then fight the party's current floor."""
        d = self.delves.get(pid)
        if floor is not None and floor != (d["floor"] if d else None) and (d or floor not in self.entry_options(pid)):
            raise InvalidAction("Floors are taken in order; you cannot skip ahead.")
        if not d:
            self.enter_dungeon(pid, floor)
        return self.delve_next(pid)

    def _delve_wait(self, d: dict) -> None:
        """Live mode: a party that has just cleared a floor (or camped) is busy until the clock catches up."""
        left = d.get("ready_tick", 0) - self.tick_count
        if self.live and left > 0:
            real_min = left / max(1e-9, self.clock_rate()) * 60
            raise InvalidAction(f"The party is still busy: about {left} game hour(s), roughly "
                                f"{real_min:.0f} real minute(s) at the current speed.")

    def delve_next(self, pid: int, manual: bool = False, join: Sequence[int] = ()):
        """Fight the next floor. With manual=True the fight pauses for orders (returns None until it ends).
        `join` lists other parties standing on the same floor: they fight together as one force."""
        return self._play(self._delve_gen(pid, join), "delve", manual, pid)

    def joinable(self, pid: int) -> List[int]:
        """Other parties inside the Descent on the very floor this one stands on (and ready to fight)."""
        d = self.delves.get(pid)
        if not d:
            return []
        return [q for q, e in self.delves.items() if q != pid and e["floor"] == d["floor"]
                and not (self.live and e.get("ready_tick", 0) > self.tick_count) and self._members_in("main", q)]

    def _delve_gen(self, pid: int, join: Sequence[int] = ()):
        d = self.delves.get(pid)
        if not d:
            raise InvalidAction("That party has not entered the dungeon (enter_dungeon first).")
        self._delve_wait(d)
        pids = [pid]
        for q in dict.fromkeys(int(x) for x in join):
            if q == pid:
                continue
            if q not in self.joinable(pid):
                raise InvalidAction(f"{self.parties.get(q).name} is not on floor {d['floor']} of the Descent, ready to fight.")
            self._delve_wait(self.delves[q])
            pids.append(q)
        party = [s for q in pids for s in self._members_in("main", q)]
        for s in party:
            if s.state == "sleeping":
                s.state = "idle"                      # woken by the next fight
        floor = d["floor"]
        if floor > dungeon.MAX_FLOOR:
            raise InvalidAction("The Hollow Descent ends here: there is nothing deeper than floor "
                                f"{dungeon.MAX_FLOOR}. Climb out.")
        k = self._knowledge(floor)
        avg_level = sum(s.level for s in party) / max(1, len(party))
        info = dungeon.floor_info(self.dungeon_seed, floor, self.parties.size)
        enemies = info.enemies
        delver_share = sum(outlook.has(s, "delve") for s in party) / max(1, len(party))
        boons = [tuple(b) for q in pids for b in self.delves[q].get("boons", [])]
        for q in pids:
            self.delves[q]["boons"] = []                      # supplies from a wayside stop last one fight
        report = yield from self._battle_gen(party, enemies, intel=(1 + config.INTEL_POWER_BONUS * k / 100)
                                             * (1 + config.OUTLOOK_DELVER_POWER * delver_share), terrain=info.terrain,
                                             modifier=modifiers.get(info.modifier), boons=boons, rarity_xp=True)
        boss = dungeon.is_boss_floor(floor)
        report.log.insert(0, f"🕳 The Hollow Descent - floor {floor}{' (BOSS)' if boss else ''}: {info.title} "
                             f"[knowledge {k:.0f}%]" + (f" - {len(pids)} parties fight together" if len(pids) > 1 else ""))
        self._after_battle(party, report, boss=boss)
        survivors = [s for s in party if s.hp > 0]
        events: List[str] = []
        self._drop_gear([s for s in party if s.hp <= 0], survivors, party, "Hollow Descent", events)
        if report.victory:
            self.best_floor = max(self.best_floor, floor)
            self.intel[floor] = 100.0                       # having walked it, the colony knows the floor
            for s in survivors:
                s.progress = max(s.progress, floor)         # they have now visited this floor
                outlook.bump(s, "delve")
            self._gear_drop(1 + (floor - 1) // config.MAIN_BOSS_EVERY, config.GEAR_DROP_MAIN, events, boss)
            if boss:                                           # a guardian's hoard holds ascension stones
                n = self.rng.randint(3, 6) * (1 + (floor - 1) // config.MAIN_BOSS_EVERY)
                self.wallet.add("stone_common", n)
                events.append(f"💎 The guardian's hoard: {n} common stones.")
                if self.rng.random() < 0.15:
                    self.wallet.add("stone_uncommon", 1)
                    events.append("💎 ...and an uncommon stone!")
            for q in pids:
                self.delves[q]["floor"] = floor + 1
                self.delves[q]["camped"] = 0
            self._xp("floor", config.KEEPER_XP["floor"] + floor // 5)
            if floor == dungeon.MAX_FLOOR:
                self.descent_cleared = True
                events.append("👑 THE PARCHED KING FALLS! The Dry Tide shudders and begins to recede - the Mother Gloop "
                              "stirs. You have cleared the Hollow Descent.")
            if boss:
                events.append(f"🔓 The boss of floor {floor} is down. This is a checkpoint: the party may climb out "
                              f"or push on to floor {floor + 1}.")
                if floor not in self.bounties:
                    self.bounties.add(floor)
                    self.wallet.add("purple_gel", config.MAIN_BOSS_FIRST_CLEAR_PURPLE)
                    report.loot["purple_gel"] = report.loot.get("purple_gel", 0) + config.MAIN_BOSS_FIRST_CLEAR_PURPLE
                    events.append(f"🟣 First boss bounty for floor {floor}: +{config.MAIN_BOSS_FIRST_CLEAR_PURPLE} purple gel!")
            else:
                events.append(f"➡ Floor {floor} cleared. The party must go on: floor {floor + 1} "
                              f"(exit after the boss on floor {self._checkpoint_after(floor + 1)}).")
        elif report.winner == "foes":
            events.append("☠ The whole party has fallen in the Hollow Descent.")
            for q in pids:
                self.delves.pop(q, None)
        self._reap(events)
        spent = dungeon.clear_hours(floor, avg_level, k, len(party))
        self._owed = 0.0
        events.extend(self._spend(spent))
        for q in pids:
            if q in self.delves:
                self.delves[q]["hours"] += spent
                if self.live:
                    self.delves[q]["ready_tick"] = self.tick_count + spent
                if not self._members_in("main", q):        # everyone starved / died in the meantime
                    self.delves.pop(q, None)
        self._owed = 0.0
        report.log.extend(events)
        self.journal.extend(events)
        return report

    # ---- wayside stops: a little shop and a safe rest between floors ------------------------------------------
    STOP_ITEMS = {
        "salve": ("Healing Salve", 8, "Heals the whole party for 35% of max HP."),
        "ration": ("Trail Ration", 4, "5 Food for the colony's stores."),
        "ward": ("Ward Charm", 10, "+15% defense for the next fight."),
        "whetstone": ("Whetstone", 10, "+15% attack for the next fight."),
    }

    def _stop(self, pid: int) -> dict:
        d = self.delves.get(pid)
        if not d:
            raise InvalidAction("That party is not inside the dungeon.")
        if not dungeon.has_stop(d["floor"]):
            raise InvalidAction(f"There is no wayside stop on floor {d['floor']}.")
        st = d.get("stop")
        if not st or st.get("floor") != d["floor"]:
            st = d["stop"] = dict(floor=d["floor"], bought=[], rested=False)
        return st

    def stop_price(self, pid: int, item: str) -> int:
        d = self.delves[pid]
        return max(1, int(self.STOP_ITEMS[item][1] * (1 + d["floor"] / 10)))

    def stop_view(self, pid: int) -> Optional[dict]:
        d = self.delves.get(pid)
        if not d or not dungeon.has_stop(d["floor"]):
            return None
        st = self._stop(pid)
        return dict(rested=st["rested"], items=[dict(key=k, name=v[0], desc=v[2], cost=self.stop_price(pid, k), bought=k in st["bought"])
                                                for k, v in self.STOP_ITEMS.items()])

    def stop_rest(self, pid: int) -> str:
        """A safe rest at the wayside stop (once per stop): the party mends half its health for 3 hours, no ambush."""
        st = self._stop(pid)
        self._delve_wait(self.delves[pid])
        if st["rested"]:
            raise InvalidAction("The party has already rested at this stop.")
        party = self._members_in("main", pid)
        for s in party:
            s.hp = min(s.max_hp, s.hp + int(s.max_hp * config.STOP_REST_HEAL))
            s.stamina_frac = min(1.0, s.stamina_frac + 0.3)
        st["rested"] = True
        self._owed = 0.0
        self._spend(config.STOP_REST_HOURS)
        self.delves[pid]["hours"] += config.STOP_REST_HOURS
        if self.live:
            self.delves[pid]["ready_tick"] = self.tick_count + config.STOP_REST_HOURS
        return f"🏕 {self.parties.get(pid).name} rests safely at the wayside stop ({config.STOP_REST_HOURS}h)."

    def stop_buy(self, pid: int, item: str) -> str:
        st = self._stop(pid)
        if item not in self.STOP_ITEMS:
            raise InvalidAction(f"The stop does not sell '{item}'.")
        if item in st["bought"]:
            raise InvalidAction("Sold out: the stop has one of each.")
        name = self.STOP_ITEMS[item][0]
        self.wallet.spend("white_gel", self.stop_price(pid, item))
        st["bought"].append(item)
        party = self._members_in("main", pid)
        if item == "salve":
            for s in party:
                s.hp = min(s.max_hp, s.hp + int(s.max_hp * 0.35))
        elif item == "ration":
            self.wallet.add("food", 5)
        else:
            self.delves[pid].setdefault("boons", []).append(("defense", 0.15) if item == "ward" else ("atk", 0.15))
        return f"🛒 Bought a {name}."

    def camp_limit(self, pid: int) -> int:
        """Hours a party may camp on its current floor: the floor number, stretched by how well the floor is known."""
        d = self.delves[pid]
        return max(1, int(d["floor"] * (1 + self._knowledge(d["floor"]) / 100.0)))

    def camp_left(self, pid: int) -> int:
        return max(0, self.camp_limit(pid) - self.delves[pid].get("camped", 0))

    def relief(self, pid: int) -> float:
        """0-1: how close another party is to reaching this one. The nearer the floors below are to being cleared,
        the fewer things lurk around the camp."""
        d = self.delves[pid]
        near = 0.0
        for q, e in self.delves.items():
            if q != pid and e["floor"] <= d["floor"]:
                near = max(near, min(1.0, max(0.0, (e["floor"] - (d["floor"] - config.CAMP_RELIEF_REACH)) / config.CAMP_RELIEF_REACH)))
        return near

    def callers(self, pid: int) -> List[Slime]:
        """Members who can call reinforcements: 5-star mages attuned to at least two elements."""
        return [s for s in self._members_in("main", pid)
                if s.archetype == "mage" and s.stars >= config.MAX_STARS and len(s.attuned) >= 2]

    def call_cost(self, floor: int) -> int:
        return 1 + floor // config.MAIN_BOSS_EVERY

    def call_reinforcements(self, pid: int, rid: int) -> str:
        """A 5-star mage calls party `rid` (at home) straight to the floor `pid` stands on, for purple gel.
        The called party needs no prior clearing of the floors above: the call skips that rule."""
        d = self.delves.get(pid)
        if not d:
            raise InvalidAction("That party is not inside the dungeon.")
        if rid == pid or rid in self.delves:
            raise InvalidAction("Pick a party that is at home.")
        mages = self.callers(pid)
        if not mages:
            raise InvalidAction("Only a 5-star mage attuned to two elements can call reinforcements.")
        floor = d["floor"]
        party = self._ready_party(rid)
        cost = self.call_cost(floor)
        self.wallet.spend("purple_gel", cost)
        pre: List[str] = []
        self._autonomy_prepare(party, pre)
        self._set_flag(party, "main")
        self.delves[rid] = dict(floor=floor, start=floor, hours=0, camped=0)
        return (f"📯 {mages[0].name} calls {self.parties.get(rid).name} to floor {floor} ({cost} purple gel). "
                f"The two parties can now fight together.")

    def delve_camp(self, pid: int, hours: int = 4) -> List[str]:
        """Rest INSIDE the dungeon (sleep: ~8%/h healing, eats food). Ambushes can strike; intel reduces them."""
        d = self.delves.get(pid)
        if not d:
            raise InvalidAction("That party is not inside the dungeon.")
        self._delve_wait(d)
        left = self.camp_left(pid)
        if left <= 0:
            raise InvalidAction(f"The party cannot camp on floor {d['floor']} any longer ({self.camp_limit(pid)}h at most here): "
                                f"fight on, or call reinforcements.")
        hours = max(1, min(config.CAMP_HEAL_HOURS_MAX, int(hours), left))
        d["camped"] = d.get("camped", 0) + hours
        out: List[str] = []
        self._owed = 0.0
        for _ in range(hours):
            party = self._members_in("main", pid)
            if not party:
                break
            for s in party:
                if s.state == "idle":
                    s.state = "sleeping"
            events = self._camp_hour(party)
            out.extend(e for e in events if "died" in e or "starv" in e)
            d["hours"] += 1
            party = self._members_in("main", pid)
            if not party:
                break
            p = min(0.7, config.CAMP_AMBUSH_BASE * (1 + 0.1 * d["floor"]) * (1 - 0.6 * self._knowledge(d["floor"]) / 100)
                    * (1 - config.CAMP_RELIEF_MAX * self.relief(pid)))
            if self.rng.random() < p:
                self._ambush_strike(pid, party, d["floor"], out, "An ambush at camp!", "ambushed while camping in the Hollow Descent")
        if not self._members_in("main", pid):
            out.append("☠ The whole party has fallen in the Hollow Descent.")
            self.delves.pop(pid, None)
        for s in self._members_in("main", pid):
            if s.state == "sleeping":
                s.state = "idle"
        if self.live and pid in self.delves:
            self.delves[pid]["ready_tick"] = self.tick_count + int(math.ceil(self._owed))
        self._owed = 0.0
        self.journal.extend(out)
        return out

    def _ambush_strike(self, pid: int, party: List[Slime], floor: int, out: List[str], headline: str, cause: str) -> None:
        """Something strikes one member of a party inside the Descent. It can be fatal (deaths are permanent)."""
        v = self.rng.choice(party)
        dmg = max(1, int(v.max_hp * self.rng.uniform(*config.CAMP_AMBUSH_DAMAGE) * (1 + 0.05 * floor)))
        v.hp -= dmg
        out.append(f"⚠ {headline} {v.name} takes {dmg} damage.")
        if v.hp <= 0:
            v.death_cause = cause
            self._drop_gear([v], [s for s in party if s is not v and s.hp > 0], party, "Hollow Descent", out)
            self._reap(out)
            self._shift_morale_party(self._members_in("main", pid), -6)

    def _shift_morale_party(self, party, delta: float) -> None:
        for s in party:
            self.social.shift_morale(s, delta)

    # ---- scouting: an exploration party must finish what it starts ------------------------------------
    @staticmethod
    def scout_skill(party) -> float:
        return min(2.0, 0.8 + 0.1 * sum(s.behavior == "explore" for s in party)
                   + 0.15 * sum(s.archetype in ("rogue", "ranger") for s in party)
                   + config.OUTLOOK_PATHFINDER_SKILL * sum(outlook.has(s, "scout") for s in party))

    def _explorers(self, pid: Optional[int] = None, ids: Optional[Sequence[int]] = None, limit: bool = True) -> List[Slime]:
        """Who goes: the given slimes (one is enough, at most a party's worth unless `limit` is off), or the members of a party."""
        if ids:
            ids = list(dict.fromkeys(int(i) for i in ids))
            if limit and len(ids) > self.parties.size:
                raise InvalidAction(f"At most {self.parties.size} slimes can go together.")
            return [self.slime(i) for i in ids]
        if pid is None:
            raise InvalidAction("Choose who goes: one slime is enough.")
        return self.party_members(pid)

    def _check_explorer(self, s: Slime) -> None:
        if s.state != "idle" or s.in_dungeon:
            raise InvalidAction(f"{s.name} is {s.in_dungeon and 'inside a dungeon' or s.state}, not available.")
        if s.grounded:
            raise InvalidAction(f"{s.name} is grounded after a brawl.")
        if s.hp <= 0:
            raise InvalidAction(f"{s.name} is down.")
        if (why := self.refusal(s, "dungeon")):
            raise InvalidAction(f"{s.name} {why}.")

    def scout_plan(self, pid: Optional[int], first: int, last: int, ids: Optional[Sequence[int]] = None) -> dict:
        """Estimated hours to scout floors first..last to 100% (the true figure hides a 0.85-1.2x factor)."""
        party = self._explorers(pid, ids) if (pid is not None or ids) else []
        skill = self.scout_skill(party) * (1 + 0.08 * self.keeper.rank("keen_eye")) if party else 1.0
        est = dungeon.scout_estimate(self.dungeon_seed, first, last, skill)
        est.update(skill=round(skill, 2), floors=last - first + 1,
                   food=int(math.ceil(est["safe"] * config.SCOUT_FOOD_PER_HOUR)))
        return est

    def scout(self, pid: Optional[int], first: int, last: int, hours: int = 0, ids: Optional[Sequence[int]] = None) -> "ScoutResult":
        """Send slimes (one is enough; or a party's members) to scout floors first..last. Scouts must reach 100% knowledge of
        EVERY targeted floor within `hours` (0 = the safe budget the estimate recommends); floors they finish stay known. If they
        run out of time they are stranded and need a rescue (see `rescue`). They return as soon as they are done. Supplies (food
        per hour of the budget) are paid up front. Every scout must have cleared the floor above `first`. Ambushes can kill scouts
        (permanent)."""
        if not 1 <= first <= last <= dungeon.MAX_FLOOR or last - first + 1 > config.SCOUT_MAX_FLOORS:
            raise InvalidAction(f"Scout 1-{config.SCOUT_MAX_FLOORS} consecutive floors between 1 and "
                                f"{dungeon.MAX_FLOOR} (e.g. floors 3-5).")
        party = self._explorers(pid, ids)
        if not party:
            raise InvalidAction("Nobody is there to go.")
        for s in party:
            self._check_explorer(s)
        hours = int(hours)
        if hours <= 0:
            hours = max(config.SCOUT_MIN_HOURS, int(self.scout_plan(pid, first, last, ids)["safe"]))
        if not config.SCOUT_MIN_HOURS <= hours <= config.SCOUT_MAX_HOURS:
            raise InvalidAction(f"The budget is {config.SCOUT_MIN_HOURS}-{config.SCOUT_MAX_HOURS} hours.")
        laggard = min(party, key=lambda s: s.progress)
        if laggard.progress < first - 1:
            raise InvalidAction(f"{laggard.name} has only cleared floor {laggard.progress}; scouts must have walked "
                                f"the floors above floor {first}.")
        self.wallet.spend("food", int(math.ceil(hours * config.SCOUT_FOOD_PER_HOUR)))
        skill = self.scout_skill(party) * (1 + 0.08 * self.keeper.rank("keen_eye"))
        floors = list(range(first, last + 1))
        need = [dungeon.floor_hours(self.dungeon_seed, f, skill)[1] for f in floors]
        total = sum(need)
        before = sum(self._knowledge(f) for f in floors) / len(floors)
        res = ScoutResult(first=first, last=last, hours=hours, required=round(total, 1), before=before, after=before)
        res.log.append(f"🔭 Scouting floors {first}-{last} with a budget of {hours}h (skill x{skill:.2f}): the scouts must "
                       f"finish everything or they are stranded.")
        self._owed = 0.0
        self._set_flag(party, "scout")
        alive_scouts = lambda: [s for s in party if s.id in self.roster and s.in_dungeon == "scout"]
        elapsed, now = 0, first
        for h in range(hours):
            members = alive_scouts()
            if not members or elapsed >= total:
                break
            events = self._spend(1)
            elapsed += 1
            res.log.extend("   " + e for e in events if "died" in e)
            members = alive_scouts()
            if not members:
                break
            cum, now = 0.0, last                       # which floor are they exploring this hour?
            for f, hrs in zip(floors, need):
                cum += hrs
                if elapsed <= cum:
                    now = f
                    break
            danger = 1 + 0.06 * now
            strength = sum(s.power_rating() for s in members) / len(members) / (25 * danger)
            p = min(0.6, config.SCOUT_AMBUSH_BASE * danger / max(0.5, strength)
                    * (1 - 0.7 * self._knowledge(now) / 100))
            if self.rng.random() < p:
                v = self.rng.choice(members)
                dmg = max(1, int(v.max_hp * self.rng.uniform(0.15, 0.40) * danger))
                v.hp -= dmg
                res.log.append(f"   hour {elapsed}: ambushed on floor {now}! {v.name} takes {dmg} damage.")
                if v.hp <= 0:
                    v.death_cause = "killed while scouting the Hollow Descent"
                    self._drop_gear([v], [s for s in members if s is not v and s.hp > 0], members,
                                    "Hollow Descent", res.log)
                    self._reap(res.log)
        survivors = alive_scouts()
        res.survivors = len(survivors)
        res.complete = bool(survivors) and elapsed >= total
        if res.complete:
            self._xp("scout", config.KEEPER_XP["scout"])
            for f in floors:
                self.intel[f] = 100.0
            for s in survivors:
                outlook.bump(s, "scout")
                self.social.shift_morale(s, 3)
            self._release(survivors)
            res.log.append(f"✅ Floors {first}-{last} fully explored in {elapsed}h. The party returns with everything.")
        else:
            cum = 0.0                                  # what they had learned becomes a half-finished note
            for f, hrs in zip(floors, need):
                frac = max(0.0, min(1.0, (elapsed - cum) / hrs))
                cum += hrs
                # a floor they finished is fully known; only the one they were still exploring becomes a half-finished note
                self.intel[f] = max(self.intel.get(f, 0.0), 100.0 if frac >= 1.0 else round(100 * frac * config.SCOUT_NOTE_FRACTION, 1))
            if survivors:                              # out of time and supplies: overdue - a rescue party may still reach them
                owed = int(math.ceil(self._owed)) if self.live else 0
                self._owed = 0.0
                self._set_flag(survivors, "stranded")
                self.stranded.append(dict(id=self.next_stranded, ids=[s.id for s in survivors], first=first, last=last,
                                          stuck=now, needed=round(total), deadline=self.tick_count + owed + config.RESCUE_DEADLINE_HOURS))
                self.next_stranded += 1
                res.stranded = True
                res.log.append(f"🆘 The scouts are overdue: out of supplies on floor {now} (they needed ~{total:.0f}h, "
                               f"they had {hours}h). What they finished stays known. Send rescuers within "
                               f"{config.RESCUE_DEADLINE_HOURS}h or they are lost.")
            else:
                res.log.append(f"☠ The exploration party never came back. Their half-finished note survives "
                               f"(they needed ~{total:.0f}h, they had {hours}h).")
        res.after = sum(self._knowledge(f) for f in floors) / len(floors)
        self.journal.extend(res.log)
        return res

    # ---- specialization ---------------------------------------------------------------------------------
    def specialize(self, sid: int, discipline: str) -> str:
        """Turn cross-training into a hybrid class (swordslime + magic style = Battlemage ...). Permanent."""
        s = self.slime(sid)
        if s.busy:
            raise InvalidAction(f"{s.name} is away ({s.in_dungeon or s.state}).")
        spec = specialization.check(s, discipline)
        self.wallet.spend_many(config.SPEC_COST)
        s.spec, s.spec_disc = spec.key, discipline
        s.spec_prof, s.spec_idle = config.PROF_SPEC_START, 0
        s.hp = min(s.max_hp, s.hp + 5)
        s.needs.add("esteem", 25)
        self.social.shift_morale(s, 10)
        return (f"{spec.emoji} {s.name} the {s.arch.name} has become a {spec.name}! New ability: "
                f"{get_ability(spec.ability).name}. {spec.description}")

    # ---- grinding dungeon: The Gloop Pit (committed session of N runs) -----------------------------
    def grind(self, pid: int, depth: int = 3, runs: int = 1, auto_rest: bool = True, manual: bool = False, lure: bool = False):
        """Commit the party to a Pit session (see _grind_gen). With manual=True it pauses for orders in every
        fight (returns None until the whole session ends); you can hand it back to the slimes at any time."""
        return self._play(self._grind_gen(pid, depth, runs, lure), "pit", manual, pid)

    def _grind_gen(self, pid: int, depth: int = 3, runs: int = 1, lure: bool = False):
        """Commit the party to `runs` Pit fights at `depth` (enemy level = party average + depth - 3).
        Once in, they only leave when all runs are done or the whole party is knocked out; they camp (sleep,
        eat) between runs when hurt. A slime that goes down is not dead: it loses morale (never XP) and DROPS ITS
        GEAR: survivors may bring it back (chance from party synergy), else it stays in the Pit's lost-and-found
        until a later victory digs it up. (`auto_rest` is kept for compatibility: camping is always automatic.)"""
        if not 1 <= depth <= config.GRIND_DEPTHS:
            raise InvalidAction(f"Depth must be 1-{config.GRIND_DEPTHS}.")
        party = self._ready_party(pid)
        if all(s.level >= s.level_cap for s in party):
            raise InvalidAction("Everyone is at their level cap - time to evolve!")
        res = GrindResult()
        last_day = -1
        pre: List[str] = []
        self._autonomy_prepare(party, pre)
        res.summary.extend("   " + x for x in pre)
        self._owed = 0.0
        self._set_flag(party, "grind")
        try:
            for n in range(1, max(1, runs) + 1):
                members = [s for s in party if s.id in self.roster]
                if not members:
                    res.stop_reason = "the whole party is gone"
                    break
                if any(s.hp < s.max_hp * config.GRIND_MIN_HP or s.stamina_frac < config.STAMINA_CAMP_AT for s in members):
                    hours = self._camp(members)
                    res.summary.append(f"   (camped {hours}h)")
                    members = [s for s in party if s.id in self.roster]
                    if not members:
                        res.stop_reason = "the whole party is gone"
                        break
                for s in members:
                    if s.state in ("sleeping", "resting"):
                        s.state = "idle"
                lured = False
                if lure:                                        # 1 purple gel per run; the lure stops when the gel runs out
                    if self.wallet.get("purple_gel") >= config.PIT_LURE_COST:
                        self.wallet.spend("purple_gel", config.PIT_LURE_COST)
                        lured = True
                    else:
                        lure = False
                        res.summary.append("   (out of purple gel: no more lures)")
                avg = sum(s.level for s in members) / len(members)
                theme = dungeon.pit_theme(self.dungeon_seed, self.day)
                enemies = dungeon.grind_wave(avg, depth, self.parties.size, self.rng, theme)
                want = config.pit_xp_per_run(sum(s.xp_needed(s.level) for s in members) / len(members),
                                             sum(config.RARITIES.index(s.rarity) for s in members) / len(members), depth)
                rep = yield from self._battle_gen(members, enemies, permadeath=False, split_xp=False,
                                                  xp_mult=want * (config.PIT_LURE_XP if lured else 1.0) / max(1.0, sum(e.xp for e in enemies)), terrain=theme.terrain)
                rep.log.insert(0, f"🕳 The Gloop Pit - depth {depth} (enemy lvl ~{dungeon.grind_level(avg, depth)}) - "
                                  f"today: {theme.title}")
                if n == 1 or theme.day != last_day:
                    res.summary.append(f"   Today's Pit (day {theme.day + 1}): {theme.terrain.emoji} {theme.title} - "
                                       f"{terrain_mod.describe(theme.terrain)}")
                last_day = theme.day
                self._after_battle(members, rep, scale=0.4)
                events: List[str] = []
                downed = list(rep.fallen)
                standing = [s for s in members if s not in downed]
                for s in downed:
                    grinder = outlook.has(s, "pit")
                    mloss = config.GRIND_DEATH_MORALE * (config.OUTLOOK_GRINDER_MORALE if grinder else 1)
                    self.social.shift_morale(s, mloss)                          # an XP farm: a knock-out costs morale, never XP
                    events.append(f"💫 {s.name} was knocked out: morale {mloss:+.0f}.")
                for s in members:                               # everyone who went in gains Pit experience
                    outlook.bump(s, "pit")
                for s in standing:
                    if rep.victory and outlook.has(s, "pit"):
                        add_xp(s, int(rep.xp * config.OUTLOOK_GRINDER_XP))
                self._drop_gear(downed, standing, members, "Gloop Pit", events)
                self._ko_wear(downed, events)
                if rep.victory:
                    self._gear_drop(1 if depth <= 3 else 2, config.GEAR_DROP_PIT * (config.PIT_LURE_GEAR if lured else 1.0), events)
                    self._stone_side_drop("grind", len(enemies), events)
                    self._herb_drop("grind", len(enemies), events, theme.terrain)
                    self._farm_loot(len(enemies), events)
                    self._recover_pit_gear(members, events)
                events.extend(self._spend(config.GRIND_TICKS))
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
                                   ("knocked", "carries", "left behind", "digs", "found", "died", "Also found")))
                self.journal.extend(events)
                if rep.winner == "foes":
                    res.stop_reason = "the whole party was knocked out"
                    break
            else:
                res.stop_reason = "finished all requested runs"
        finally:
            self._release(party)
        return res

    def _camp_hour(self, members) -> List[str]:
        """One hour of rest in the field. Turn mode lets the colony live that hour; live mode applies the rest to
        the party directly (the colony only moves with the wall clock) and charges the hour to the session."""
        if not self.live:
            return self.tick(1)
        for s in members:
            if s.id in self.roster:
                s.hp = min(s.max_hp, s.hp + int(s.max_hp * config.CAMP_HEAL_PER_HOUR))
                s.stamina_frac = min(1.0, s.stamina_frac + 0.1 * config.STAMINA_SLEEP_MULT)
        return self._spend(1)

    def _camp(self, members, max_hours: int = 24) -> int:
        """Inside a dungeon: sleep (no Rest Area) until everyone is >= 85% HP."""
        hours = 0
        while hours < max_hours:
            members = [s for s in members if s.id in self.roster]
            if not members or all(s.hp >= s.max_hp * 0.85 and s.stamina_frac >= 0.7 for s in members):
                break
            for s in members:
                if s.state == "idle":
                    s.state = "sleeping"
            self._camp_hour(members)
            hours += 1
            fm = 0.04 * self.keeper.rank("field_medic")
            if fm:
                for s in members:
                    if s.id in self.roster:
                        s.hp = min(s.max_hp, s.hp + int(s.max_hp * fm))
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
                    bounties=sorted(self.bounties), descent_cleared=self.descent_cleared, custom_spells=spells.custom_records(),
                    buildings=self.buildings.to_dict(), best_floor=self.best_floor,
                    delves={str(k): v for k, v in self.delves.items()},
                    intel={str(k): v for k, v in self.intel.items()}, dungeon_seed=self.dungeon_seed,
                    inventory=self.inventory.to_dict(), pit_lost=self.pit_lost,
                    vault=[i.to_dict() for i in self.vault.values()], time_mode=self.time_mode, time_scale=self.time_scale, wall_last=self.wall_last, wall_frac=self.wall_frac,
                    expeditions=self.expeditions, pantry=self.pantry, recipe_pref=self.recipe_pref, forge_progress=self.forge_progress, forge_next=self.forge_next, stranded=self.stranded, next_stranded=self.next_stranded, keeper=self.keeper.to_dict(), relations=self.relations.to_dict(), potions=self.potions, potion_peak=self.potion_peak, autonomy=self.autonomy, forage=self.forage, vice=self.vice, vice_challenge=self.vice_challenge, hunt_group=self.hunt_group, vault_peak=self.vault_peak, gear_peak=self.gear_peak, next_item_id=self.next_item_id,
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
        g.bounties = set(d.get("bounties", range(config.MAIN_BOSS_EVERY, d.get("main_floor", 0) + 1,
                                               config.MAIN_BOSS_EVERY)))
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
        g.descent_cleared = d.get("descent_cleared", False)
        g.intel = {int(k): v for k, v in d.get("intel", {}).items()}
        if d.get("version", 0) < 7:                          # v6 knew intel per 5-floor segment, progress globally
            seg_intel = g.intel
            g.intel = {f: v for seg, v in seg_intel.items() for f in dungeon.segment_floors(seg)}
        g.dungeon_seed = d.get("dungeon_seed", g.dungeon_seed)
        g.inventory.load(d.get("inventory"))
        g.pit_lost = [k for k in d.get("pit_lost", []) if k in equipment.GEAR]
        g.sacrifice_stress = d.get("sacrifice_stress", 0.0)
        g.vault = {i["uid"]: items_mod.Item.from_dict(i) for i in d.get("vault", [])}
        g.next_item_id = d.get("next_item_id", 1)
        g.potions = {k: v for k, v in d.get("potions", {}).items() if v > 0 and k.split(":")[0] in potions.KINDS}
        g.potion_peak = {k: max(v, g.potions.get(k, 0)) for k, v in d.get("potion_peak", {}).items()}
        for k, v in g.potions.items():
            g.potion_peak[k] = max(g.potion_peak.get(k, 0), v)
        g.autonomy = d.get("autonomy", True)
        g.forage = d.get("forage", True)
        g.vice = d.get("vice")
        g.vice_challenge = d.get("vice_challenge")                # checked when resolved (the roster loads below)
        g.hunt_group = d.get("hunt_group", 0)
        g.time_mode, g.time_scale = d.get("time_mode", "turn"), d.get("time_scale", 1.0)
        g.wall_last, g.wall_frac = d.get("wall_last"), d.get("wall_frac", 0.0)
        g.keeper.load(d.get("keeper"))
        g._apply_keeper()
        g.vault_peak = d.get("vault_peak", 0)
        g.gear_peak = dict(d.get("gear_peak", {}))
        g.mood_rng = random.Random((((g.seed or 0) ^ 0xE70) + d.get("tick", 0)) & 0xFFFFFFFF)
        if g.wallet.get("herb"):                              # v10 saves had one kind of herb: share it out
            n = g.wallet.get("herb")
            g.wallet.add("herb", -n)
            for i, color in enumerate(config.HERBS):
                g.wallet.add(potions.herb_key(color), n // 4 + (1 if i < n % 4 else 0))
        spells.load_custom(d.get("custom_spells", []))
        g.library.discovered = {k for k in d.get("discovered", []) if k in ABILITIES}
        for sd in d.get("slimes", []):
            if sd["archetype"] not in ARCHETYPES:          # plugin removed: skip safely
                print(f"warning: skipping slime {sd['name']} (unknown class {sd['archetype']})")
                continue
            s = Slime.from_dict(sd)
            s.spells = [k for k in s.spells if k in ABILITIES]      # drop spells from removed mods
            if d.get("version", 0) < 7:
                s.progress = max(s.progress, d.get("main_floor", 0))
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
        g.relations.load(d.get("relations"), set(g.roster))
        g.expeditions = [dict(e, ids=[i for i in e["ids"] if i in g.roster]) for e in d.get("expeditions", [])]
        g.expeditions = [e for e in g.expeditions if e["ids"]]
        g.pantry = {k: int(v) for k, v in d.get("pantry", {}).items()}
        g.recipe_pref = d.get("recipe_pref", "auto")
        g.forge_progress, g.forge_next = d.get("forge_progress", 0), d.get("forge_next", "weapon")
        g.stranded = [e for e in d.get("stranded", []) if any(i in g.roster for i in e["ids"])]
        g.next_stranded = d.get("next_stranded", 1)
        g.journal = d.get("journal", [])
        g.journal.extend(awakening.load_notes(g.slimes(), g.mood_rng))
        if d.get("version", 0) < 16:                              # one-time amnesty: the scouting bugs of older versions stranded
            g.stranded = []                                       # parties unfairly; everybody still stranded is freed on load
            for sl in g.slimes():
                if sl.in_dungeon in ("stranded", "rescue", "scout"):
                    sl.in_dungeon = ""
                    if sl.state in ("hunting", "studying") and not sl.hunt and not sl.task:
                        sl.state = "idle"
        away = {i for e in g.expeditions for i in e["ids"]}      # a battle that was open when the game was saved is gone:
        for sl in g.slimes():                                     # free its party (the Descent keeps its own delve flags)
            if sl.in_dungeon in ("grind", "scout", "adventure", "quarry", "rescue") and sl.id not in away:
                sl.in_dungeon = ""
        return g
