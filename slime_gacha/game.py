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
from . import awakening, emotions, keeper as keeper_mod, relationships, buildings as bld, dungeon, terrain as terrain_mod, elements, ascension, attributes, equipment, items as items_mod, potions, outlook, sparring, spells, specialization
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
        self.keeper = keeper_mod.Keeper()
        self.relations = relationships.RelationshipEngine()
        self.emotions_mod = emotions
        self.mood_rng = random.Random(((seed or 0) ^ 0xE70) & 0xFFFFFFFF)   # feelings never disturb the main dice
        self.vault_peak = 0                            # relics: slimes leave 34% of the most ever held
        self.gear_peak: Dict[str, int] = {}
        self.autonomy = True                           # slimes may use up to 66% of the stock by themselves
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
            self._stamina_tick()
            self._emotion_tick(events)
            if self.tick_count % 24 == config.RELATIONS_HOUR:
                self._relations_day(events)
            self._autonomy_tick(events)
        self.journal.extend(events)
        self.journal = self.journal[-200:]
        return events

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
        s = self.slime(sid)
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
    def feed(self, sid: int) -> str:
        s = self.slime(sid)
        self.wallet.spend("food", 1)
        s.needs.add("food", config.FOOD_NUTRITION)
        s.needs.add("belonging", 3)
        gh = 1 + 0.5 * self.keeper.rank("gentle_hands")
        emotions.feel(s, "joy", 6 * gh)
        emotions.soothe(s, "anger", (10 if s.needs.get("food") < 60 else 0) * gh)
        self._xp("care", config.KEEPER_XP["care"])
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
        gh = 1 + 0.5 * self.keeper.rank("gentle_hands")
        emotions.feel(s, "joy", 12 * gh)
        emotions.feel(s, "affection", 8 * gh)
        emotions.soothe(s, "loneliness", 15 * gh)
        emotions.soothe(s, "anger", 6 * gh)
        awakening.comfort(s)
        self._xp("care", config.KEEPER_XP["care"])
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
            if outlook.has(s, "spar"):
                xp *= config.OUTLOOK_DUELIST_STYLE
            outlook.bump(s, "spar")
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
        syn = self.social.synergy(party) * intel * (1 + self.relations.synergy_delta(party))
        self.relations.prebattle(party, emotions)
        bc = 6 * self.keeper.rank("battle_cry")
        if bc:
            for s in party:
                emotions.feel(s, "determination", bc)
                emotions.feel(s, "pride", bc)
        report = self.battles.run(party, enemies, synergy=syn, **opts)
        report.log.insert(1, f"🤝 Party synergy {syn - 1:+.1%} (avg compatibility "
                             f"{self.social.avg_compat(party):+.0f}"
                             + (f", scouting intel {intel - 1:+.0%}" if intel != 1.0 else "") + ")")
        return report

    def _after_battle(self, party, report: BattleReport, boss: bool = False, scale: float = 1.0) -> None:
        """Morale and bonds react to the outcome (deaths are handled when the dead are reaped)."""
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
        self.wallet.spend("white_gel", ascension.rarity_cost(s))
        old = s.max_hp
        s.rarity = up
        s.hp += s.max_hp - old
        s.needs.add("esteem", 20)
        self.social.shift_morale(s, 10)
        self._xp("ascend", config.KEEPER_XP["ascend"])
        return f"✨ {s.name} ascends to {up}! (stats x{config.RARITY_STAT_MULT[up]})"

    def ascend_slime_star(self, sid: int) -> str:
        """Add a star, paid in ascension stones (10 / 100 / 1000 / 10000 common-stone equivalents)."""
        s = self._free_slime(sid)
        need = ascension.star_cost(s)
        if need is None:
            raise InvalidAction(f"{s.name} already has {config.MAX_STARS} stars.")
        ascension.pay_stones(self.wallet, need)
        old = s.max_hp
        s.stars += 1
        s.hp += s.max_hp - old
        s.needs.add("esteem", 20)
        self.social.shift_morale(s, 10)
        self._xp("ascend", config.KEEPER_XP["ascend"])
        return f"🌟 {s.name} ascends to {s.stars} stars!"

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
        y = ascension.chamber_yield(s, self.buildings.level("chamber"))
        name, label = s.name, f"{config.RARITY_TAG[s.rarity]} {s.star_str()} Lv{s.level} {s.arch.name}"
        self._consume_slime(s, config.CHAMBER_STRESS)
        self.wallet.add_many(y)
        return [f"🔥 {name} ({label}) is destroyed in the chamber: " +
                ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in y.items()) + ".",
                f"   The colony mourns. Sacrifice stress is now {self.sacrifice_stress:.1f}."]

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
        if any(b["kind"] == kind for b in s.buffs):
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

    def set_autonomy(self, on: bool) -> str:
        self.autonomy = bool(on)
        return "Slimes will help themselves to up to 66% of potions, relics, gear and materials - and brew on their own." if on else \
            "Slimes will wait for your orders."

    def potion_count(self, kind: str, grade: int) -> int:
        return self.potions.get(potions.key(kind, grade), 0)

    def brew(self, sid: int, kind: str, grade: int, wait: bool = True) -> List[str]:
        """A slime brews a potion in the Alchemy Lab (takes 2 hours per grade). Lab level caps the grade."""
        s = self._free_slime(sid)
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
            self._set_flag([s], "lab")
            try:
                self.tick(potions.brew_hours(grade))
            finally:
                self._clear_flag([s])
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
        s = self.slime(sid)
        k = potions.key(kind, grade)
        if self.potions.get(k, 0) <= 0 or kind not in potions.KINDS:
            raise InvalidAction("You have no such potion.")
        self.potions[k] -= 1
        if not self.potions[k]:
            del self.potions[k]
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
        self._set_flag([s], "lab")
        try:
            self.tick(config.SLIME_REPAIR_HOURS)
        finally:
            self._clear_flag([s])
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
                if rep.victory and kind != "quarry":
                    self._stone_side_drop("adventure", len(enemies), events)
                    for _ in enumerate(enemies):
                        if self.rng.random() < config.ADV_DROP_PER_FOE:
                            it = self.new_item(lure)
                            events.append(f"🎁 Found {it.label()}"
                                          + (" - " + ", ".join(it.mod_text(m) for m in it.mods) if it.mods else "") + "!")
                events.extend(self.tick(config.ADV_TICKS))
                rep.log.extend(events)
                res.runs.append(rep)
                tag = "Victory" if rep.victory else "Defeat" if rep.winner == "foes" else "Draw"
                line = f"Run {n}/{runs}: {tag} in {rep.rounds} rounds"
                if rep.knocked_out:
                    line += f", KO: {', '.join(rep.knocked_out)}"
                res.summary.append(line)
                res.summary.extend("   " + e for e in events if any(w in e for w in
                                   ("Found", "Mined", "stone", "herb", "shatters", "knocked", "died")))
                self.journal.extend(events)
                if rep.winner == "foes":
                    res.stop_reason = "the whole party was knocked out"
                    break
            else:
                res.stop_reason = "finished all requested runs"
        finally:
            self._clear_flag(party)
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

    def delve_next(self, pid: int) -> BattleReport:
        d = self.delves.get(pid)
        if not d:
            raise InvalidAction("That party has not entered the dungeon (enter_dungeon first).")
        party = self._members_in("main", pid)
        for s in party:
            if s.state == "sleeping":
                s.state = "idle"                      # woken by the next fight
        floor = d["floor"]
        if floor > dungeon.MAX_FLOOR:
            raise InvalidAction("The Hollow Descent ends here: there is nothing deeper than floor "
                                f"{dungeon.MAX_FLOOR}. Climb out.")
        k = self._knowledge(floor)
        info = dungeon.floor_info(self.dungeon_seed, floor, self.parties.size)
        enemies = info.enemies
        delver_share = sum(outlook.has(s, "delve") for s in party) / max(1, len(party))
        report = self._run_battle(party, enemies, intel=(1 + config.INTEL_POWER_BONUS * k / 100)
                                  * (1 + config.OUTLOOK_DELVER_POWER * delver_share), terrain=info.terrain)
        boss = dungeon.is_boss_floor(floor)
        report.log.insert(0, f"🕳 The Hollow Descent - floor {floor}{' (BOSS)' if boss else ''}: {info.title} "
                             f"[knowledge {k:.0f}%]")
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
            d["floor"] = floor + 1
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
            self.delves.pop(pid, None)
        self._reap(events)
        events.extend(self.tick(config.MAIN_FLOOR_TICKS))
        if pid in self.delves:
            self.delves[pid]["hours"] += config.MAIN_FLOOR_TICKS
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
            party = self._members_in("main", pid)
            if not party:
                break
            p = min(0.7, config.CAMP_AMBUSH_BASE * (1 + 0.1 * d["floor"]) * (1 - 0.6 * self._knowledge(d["floor"]) / 100))
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

    # ---- scouting: an exploration party must finish what it starts ------------------------------------
    @staticmethod
    def scout_skill(party) -> float:
        return min(2.0, 0.8 + 0.1 * sum(s.behavior == "explore" for s in party)
                   + 0.15 * sum(s.archetype in ("rogue", "ranger") for s in party)
                   + config.OUTLOOK_PATHFINDER_SKILL * sum(outlook.has(s, "scout") for s in party))

    def scout_plan(self, pid: int, first: int, last: int) -> dict:
        """Estimated hours to scout floors first..last to 100% (the true figure hides a 0.85-1.2x factor)."""
        party = self.party_members(pid)
        skill = self.scout_skill(party) * (1 + 0.08 * self.keeper.rank("keen_eye")) if party else 1.0
        est = dungeon.scout_estimate(self.dungeon_seed, first, last, skill)
        est.update(skill=round(skill, 2), floors=last - first + 1,
                   food=int(math.ceil(est["safe"] * config.SCOUT_FOOD_PER_HOUR)))
        return est

    def scout(self, pid: int, first: int, last: int, hours: int) -> "ScoutResult":
        """Send a full party to scout floors first..last. Scouts must reach 100% knowledge of EVERY targeted floor
        within `hours`; if they run out of time the whole party is lost (it leaves a half-finished note behind).
        They finish and return as soon as they are done. Supplies (food per hour of the budget) are paid up front.
        Every member must have cleared the floor above `first`. Ambushes can kill scouts (permanent)."""
        if not 1 <= first <= last <= dungeon.MAX_FLOOR or last - first + 1 > config.SCOUT_MAX_FLOORS:
            raise InvalidAction(f"Scout 1-{config.SCOUT_MAX_FLOORS} consecutive floors between 1 and "
                                f"{dungeon.MAX_FLOOR} (e.g. floors 3-5).")
        hours = int(hours)
        if not config.SCOUT_MIN_HOURS <= hours <= config.SCOUT_MAX_HOURS:
            raise InvalidAction(f"The budget is {config.SCOUT_MIN_HOURS}-{config.SCOUT_MAX_HOURS} hours.")
        party = self._ready_party(pid)
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
        res.log.append(f"🔭 Scouting floors {first}-{last} with a budget of {hours}h (skill x{skill:.2f}): the party must "
                       f"finish everything or it is lost.")
        self._set_flag(party, "scout")
        elapsed = 0
        for h in range(hours):
            members = self._members_in("scout", pid)
            if not members or elapsed >= total:
                break
            events = self.tick(1)
            elapsed += 1
            res.log.extend("   " + e for e in events if "died" in e)
            members = self._members_in("scout", pid)
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
        survivors = self._members_in("scout", pid)
        res.survivors = len(survivors)
        res.complete = bool(survivors) and elapsed >= total
        if res.complete:
            self._xp("scout", config.KEEPER_XP["scout"])
            for f in floors:
                self.intel[f] = 100.0
            for s in survivors:
                outlook.bump(s, "scout")
                self.social.shift_morale(s, 3)
            self._clear_flag(survivors)
            res.log.append(f"✅ Floors {first}-{last} fully explored in {elapsed}h. The party returns with everything.")
        else:
            cum = 0.0                                  # what they had learned becomes a half-finished note
            for f, hrs in zip(floors, need):
                frac = max(0.0, min(1.0, (elapsed - cum) / hrs))
                cum += hrs
                self.intel[f] = max(self.intel.get(f, 0.0), round(100 * frac * config.SCOUT_NOTE_FRACTION, 1))
            if survivors:                              # out of time and supplies: nobody comes back
                for s in survivors:
                    s.hp, s.death_cause = 0, f"lost scouting floors {first}-{last} (needed ~{total:.0f}h)"
                self._drop_gear(survivors, [], survivors, "Hollow Descent", res.log)
                self._reap(res.log)
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
        s.hp = min(s.max_hp, s.hp + 5)
        s.needs.add("esteem", 25)
        self.social.shift_morale(s, 10)
        return (f"{spec.emoji} {s.name} the {s.arch.name} has become a {spec.name}! New ability: "
                f"{get_ability(spec.ability).name}. {spec.description}")

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
        last_day = -1
        pre: List[str] = []
        self._autonomy_prepare(party, pre)
        res.summary.extend("   " + x for x in pre)
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
                avg = sum(s.level for s in members) / len(members)
                theme = dungeon.pit_theme(self.dungeon_seed, self.day)
                enemies = dungeon.grind_wave(avg, depth, self.parties.size, self.rng, theme)
                rep = self._run_battle(members, enemies, permadeath=False, split_xp=False,
                                       xp_mult=config.GRIND_XP_MULT, terrain=theme.terrain)
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
                    lost = lose_xp(s, config.GRIND_DEATH_XP_LOSS * (config.OUTLOOK_GRINDER_LOSS if grinder else 1))
                    mloss = config.GRIND_DEATH_MORALE * (config.OUTLOOK_GRINDER_MORALE if grinder else 1)
                    self.social.shift_morale(s, mloss)
                    events.append(f"💫 {s.name} was knocked out: -{lost} xp, morale {mloss:+.0f}.")
                for s in members:                               # everyone who went in gains Pit experience
                    outlook.bump(s, "pit")
                for s in standing:
                    if rep.victory and outlook.has(s, "pit"):
                        add_xp(s, int(rep.xp * config.OUTLOOK_GRINDER_XP))
                self._drop_gear(downed, standing, members, "Gloop Pit", events)
                self._ko_wear(downed, events)
                if rep.victory:
                    self._gear_drop(1 if depth <= 3 else 2, config.GEAR_DROP_PIT, events)
                    self._stone_side_drop("grind", len(enemies), events)
                    self._herb_drop("grind", len(enemies), events, theme.terrain)
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
            if not members or all(s.hp >= s.max_hp * 0.85 and s.stamina_frac >= 0.7 for s in members):
                break
            for s in members:
                if s.state == "idle":
                    s.state = "sleeping"
            self.tick(1)
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
                    vault=[i.to_dict() for i in self.vault.values()], keeper=self.keeper.to_dict(), relations=self.relations.to_dict(), potions=self.potions, potion_peak=self.potion_peak, autonomy=self.autonomy, vault_peak=self.vault_peak, gear_peak=self.gear_peak, next_item_id=self.next_item_id,
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
        g.journal = d.get("journal", [])
        g.journal.extend(awakening.load_notes(g.slimes(), g.mood_rng))
        return g
