"""BattleSystem: deterministic (seeded) turn-based auto-combat.

Flow: build Combatants -> loop rounds (speed order) -> each actor's AI picks an ability from its
stance -> KIND_HANDLERS resolve it -> BattleReport (log + rewards). The UI only prints the report.
Add a new ability *kind* by writing a handler and adding it to KIND_HANDLERS.
"""
import random
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional, Tuple

from . import config
from .abilities import Ability, get_ability
from . import attributes, elements, emotions, fx, items as items_mod, terrain as terrain_mod
from . import modifiers, pools, sparring, spells
from .archetypes import STAT_KEYS
from .growth import add_xp
from .registry import Registry
from .resources import ResourceManager


# ---- enemies (data) -------------------------------------------------------------
@dataclass(frozen=True)
class Enemy:
    key: str
    name: str
    emoji: str
    tier: int
    stats: Dict[str, float]
    abilities: List[str]
    xp: int
    loot: Dict[str, tuple]       # resource -> (lo, hi)
    purple_chance: float = 0.0     # purple gel is rare: chance per kill to drop `purple_amount`
    purple_amount: int = 1
    element: str = ""            # defensive element: weak to what beats it, resists what it beats
    family: str = ""             # goblin, direwolf, orc ... (see bestiary.py)
    role: str = ""
    boss: bool = False
    weak: Tuple[str, ...] = ()       # extra elements it is weak to (family traits, see bestiary.FAMILY_TRAITS)
    resists: Tuple[str, ...] = ()    # extra elements it resists


ENEMIES: "Registry[Enemy]" = Registry("enemy")

# ---- formations: front and back rows ----------------------------------------------------------------------------
# Melee single-target attacks can only reach the front row while a front-row foe stands; arrows, spells, area attacks and
# backstabs reach anyone. A melee fighter in the back row hits for less; whoever stands in the back row takes less damage.
RANGED_WORDS = ("arrow", "shot", "volley", "snipe", "dart", "bolt", "barrage", "shadows", "backstab", "stab_back")
BACK_ROLES = ("caster", "support", "hunter")           # monsters that fight from the back row
BACK_DISCIPLINES = ("archery", "magic")                # classes that default to the back row


def is_melee(ab) -> bool:
    """A single-target physical attack that has to be struck from close up."""
    return (ab.target == "enemy" and ab.kind in ("damage", "drain", "poison") and ab.stat == "atk" and not ab.element
            and not any(w in ab.key for w in RANGED_WORDS))


def default_row(slime) -> str:
    return "back" if slime.arch.discipline in BACK_DISCIPLINES else "front"


def register_enemy(e: Enemy) -> Enemy:
    return ENEMIES.register(e, e.key)


def _e(hp, atk, d, mag, spd):
    return dict(hp=hp, atk=atk, defense=d, mag=mag, spd=spd)


for _en in [
    Enemy("dust_bunny", "Dust Bunny", "🐇", 1, _e(22, 6, 2, 0, 5), ["splat"], 12, {"white_gel": (0, 2)}, 0.01),
    Enemy("crust_beetle", "Crust Beetle", "🪲", 1, _e(30, 7, 5, 0, 3), ["splat", "smash"], 15, {"white_gel": (1, 2), "food": (0, 2)}, 0.01),
    Enemy("parched_wisp", "Parched Wisp", "👻", 2, _e(32, 2, 3, 10, 6), ["spark", "curse"], 28, {"white_gel": (1, 3), "essence": (0, 3)}, 0.03),
    Enemy("hollow_knight", "Hollow Knight", "🛡️", 2, _e(60, 11, 8, 0, 5), ["splat", "smash"], 35, {"white_gel": (2, 4)}, 0.03),
    Enemy("thorn_sprite", "Thorn Sprite", "🧚", 2, _e(30, 10, 3, 2, 10), ["stab", "venom_dart"], 30, {"white_gel": (1, 3), "food": (1, 3)}, 0.03),
    Enemy("dry_brute", "Dry Tide Brute", "🗿", 3, _e(130, 17, 10, 0, 5), ["smash", "rampage"], 80, {"white_gel": (3, 6), "essence": (2, 6)}, 0.08),
    Enemy("crown_wraith", "Crown Wraith", "👑", 3, _e(95, 4, 6, 18, 7), ["arcane_surge", "siphon"], 90, {"white_gel": (3, 6), "essence": (3, 8)}, 0.08),
    Enemy("parched_king", "The Parched King", "🏜️", 4, _e(700, 22, 12, 20, 6), ["smash", "rampage", "arcane_surge", "curse"], 400, {"white_gel": (30, 50), "essence": (20, 40)}, 0.35, 1),
]:
    register_enemy(_en)

_ELEMENT_OF = {"dust_bunny": "wind", "crust_beetle": "earth", "parched_wisp": "fire", "hollow_knight": "earth",
               "thorn_sprite": "wind", "dry_brute": "fire", "crown_wraith": "water", "parched_king": "fire"}
for _k, _el in _ELEMENT_OF.items():
    ENEMIES.register(replace(ENEMIES.get(_k), element=_el), _k)

# Mid-boss of the main dungeon (tier 5 = never picked by generate_enemies, only by dungeon.py)
register_enemy(Enemy("hollow_warden", "The Hollow Warden", "🗝️", 5, _e(260, 16, 9, 8, 6),
                     ["smash", "rampage", "war_cry"], 150, {"white_gel": (12, 20), "essence": (6, 12)}, 0.35, 1,
                     "earth"))


def _merge_mods(a: dict, b: dict) -> dict:
    out = dict(a)
    out["elem"] = dict(a.get("elem", {}))
    for k, v in b.items():
        out[k] = out.get(k, 0.0) + v
    return out


# ---- combatants -----------------------------------------------------------------
@dataclass
class Combatant:
    name: str
    emoji: str
    side: str                       # "party" | "foes"
    stats: Dict[str, float]
    hp: float
    abilities: List[str]
    behavior: str = "attack"
    power_mult: float = 1.0
    source: object = None           # Slime or Enemy template
    minion: bool = False
    cooldowns: Dict[str, int] = field(default_factory=dict)
    guard: int = 0
    poison: tuple = (0, 0)          # (turns, dmg per turn)
    mastery: Dict[str, int] = field(default_factory=dict)   # basic element -> mastery level (slimes)
    element: str = ""               # enemy's own element
    weak: tuple = ()                # enemy's extra weaknesses / resistances (elements)
    resists: tuple = ()
    casts: Dict[str, int] = field(default_factory=dict)     # elemental casts this battle (mastery xp)
    style: Dict[str, int] = field(default_factory=dict)     # fighting-style levels (sparring.py)
    morale: float = 60.0
    nonlethal: bool = False         # sparring: reaching 1 HP means yielding, not dying
    yielded: bool = False
    mods: Dict[str, object] = field(default_factory=dict)   # relic + star mods: crit_rate, crit_dmg, lifesteal, elem, evasion, guard, regen, spell_power, resist
    spell_names: Dict[str, str] = field(default_factory=dict)   # slimes only: its own names for its spells (spells.class_name)
    stamina: float = 0.0            # slimes only: current stamina, max, and breath caught per round (attributes.py)
    stamina_max: float = 0.0
    sta_regen: float = 0.0
    winded: bool = False            # set for the action when stamina ran dry
    mana: float = 0.0               # magic without an element (pools.py); persists between fights for slimes
    mana_max: float = 0.0
    mana_regen: float = 0.0
    nature: float = 0.0             # elemental skills; every fight starts it at config.NATURE_START
    nature_max: float = 0.0
    nature_regen: float = 0.0
    pool_scale: float = 1.0         # skill costs grow with level like the pools do (monsters: 1)
    ap: int = 0                     # action points saved (pools.py): +AP_PER_TURN a turn, up to AP_MAX
    buffed: bool = False            # has used a buff / hex this turn (the AI allows itself one)
    # --- status mechanics (fx.py) ---
    shield: float = 0.0             # damage soaked before HP
    bleed: List[tuple] = field(default_factory=list)       # (turns left, damage per turn), up to 3 stacks
    stun: int = 0                   # turns still to lose
    marked: tuple = (0, 0.0)        # (turns, extra damage taken)
    buffs: List[dict] = field(default_factory=list)        # temporary stat / mod changes
    stat_set: Dict[str, tuple] = field(default_factory=dict)   # stat -> (forced value, turns)
    untarget: int = 0
    undying: int = 0
    counter: tuple = (0, 0.0)       # (turns, power) strike back when hit
    oath: float = 0.0               # extra attack while below 30% HP
    extra_turns: int = 0
    acted: bool = False             # has acted this round
    last_ability: str = ""
    uses: int = 0                   # class-line actions taken this fight (class practice)
    spec_uses: int = 0              # hybrid skills used this fight (second-discipline practice)
    cap_scale: Dict[str, float] = field(default_factory=dict)   # ability key -> strength factor (hybrid capstones)
    hybrid: frozenset = frozenset() # keys that count as hybrid practice
    imbue: tuple = ("", 0)          # (element, turns) weapon imbue: physical hits strike as that element (fx "imbue")
    row: str = "front"              # formation: "front" | "back" (see BattleSystem.reachable)

    @property
    def alive(self) -> bool:
        return self.hp > 0 and not self.yielded

    def matchup(self, element: str) -> float:
        """Damage multiplier an attack of `element` gets against this combatant."""
        return elements.matchup(element, self.element, self.weak, self.resists)

    def hurt(self, amount: float) -> None:
        if self.shield > 0:
            soaked = min(self.shield, amount)
            self.shield -= soaked
            amount -= soaked
        self.hp -= amount
        if self.undying > 0 and self.hp < 1:
            self.hp = 1
        if self.nonlethal and self.hp <= 1:
            self.hp, self.yielded = 1, True

    @property
    def max_hp(self) -> float:
        return self.stats["hp"]

    def stat(self, name: str) -> float:
        v = self.stat_set[name][0] if name in self.stat_set else self.stats[name]
        if self.buffs:
            v *= fx.stat_factor(self, name)
        if self.oath and name == "atk" and self.hp < self.max_hp * 0.3:
            v *= 1 + self.oath
        if name == "spd":
            return v * (1 + config.STYLE_ARCHERY_SPEED * self.style.get("archery", 0))
        return v * self.power_mult if name in ("atk", "mag") else v


@dataclass
class BattleReport:
    log: List[str]
    winner: Optional[str]           # "party" | "foes" | None (draw)
    rounds: int
    xp: int = 0
    loot: Dict[str, int] = field(default_factory=dict)
    deaths: List[str] = field(default_factory=list)
    knocked_out: List[str] = field(default_factory=list)
    winner_slime: object = None            # duels only
    fallen: List[object] = field(default_factory=list)   # slimes at 0 HP after the fight (dead or knocked out)

    @property
    def victory(self) -> bool:
        return self.winner == "party"


# ---- the system -------------------------------------------------------------------
class BattleSystem:
    def __init__(self, rng: random.Random, wallet: Optional[ResourceManager] = None):
        self.rng = rng
        self.wallet = wallet
        self.terrain = None              # set per fight (see run); a terrain.Terrain or None
        self.last_hits: Dict[int, int] = {}    # damage dealt by the latest ability, per target (for bleed)
        self.delayed: List[dict] = []          # abilities that land in a later round
        self.round = 0

    # -- setup ---------------------------------------------------------------
    def generate_enemies(self, tier: int, count: int = 3) -> List[Enemy]:
        pool = [e for e in ENEMIES if e.tier == tier]
        if not pool:
            raise ValueError(f"no enemies for tier {tier}")
        if tier >= 4:
            return [pool[0]]
        return [self.rng.choice(pool) for _ in range(count)]

    @staticmethod
    def from_slime(s, synergy: float = 1.0, side: str = "party") -> Combatant:
        """power = mood x morale x party synergy; style levels and elemental mastery come along."""
        morale_f = config.MORALE_POWER_MIN + (config.MORALE_POWER_MAX - config.MORALE_POWER_MIN) * s.morale / 100
        stats = dict(s.max_stats())
        emult, emods = emotions.modifiers(s)               # feelings colour the fight (anger: +ATK -DEF ...)
        for k, m in emult.items():
            stats[k] = round(stats[k] * m, 1)
        return Combatant(s.name, s.arch.emoji, side, stats, float(s.hp),
                         s.known_abilities(), s.behavior, s.power_multiplier() * morale_f * synergy, s,
                         mastery={b: elements.basic_level(s, b) for b in s.attuned},
                         cap_scale=({attributes.hybrid_capstone(s): attributes.hybrid_scale(s)} if attributes.hybrid_capstone(s) else {}),
                         hybrid=frozenset(attributes.hybrid_keys(s)),
                         style=sparring.style_levels(s), morale=s.morale, mods=_merge_mods(_merge_mods(_merge_mods(items_mod.battle_mods(s), attributes.battle_mods(s)), emods), getattr(s, "passive_mods", {})),
                         stamina=s.stamina, stamina_max=s.max_stamina, sta_regen=attributes.regen_per_round(s),
                         row=(s.row if s.row in ("front", "back") else default_row(s)), spell_names=spells.names_for(s),
                         **BattleSystem._slime_pools(s))

    @staticmethod
    def _slime_pools(s) -> dict:
        mana_max, nature_max = pools.max_mana(s), pools.max_nature(s)
        return dict(mana=round(mana_max * max(0.0, min(1.0, getattr(s, "mana_frac", 1.0))), 1), mana_max=mana_max,
                    mana_regen=round(mana_max * config.MANA_ROUND_REGEN, 2),
                    nature=round(nature_max * config.NATURE_START, 1), nature_max=nature_max,
                    nature_regen=round(nature_max * config.NATURE_ROUND_REGEN, 2), pool_scale=pools.level_scale(s))

    @staticmethod
    def from_enemy(e: Enemy) -> Combatant:
        full = config.FOE_POOL
        return Combatant(e.name, e.emoji, "foes", dict(e.stats), float(e.stats["hp"]), list(e.abilities),
                         "attack", 1.0, e, element=e.element, weak=tuple(e.weak), resists=tuple(e.resists),
                         row=("back" if e.role in BACK_ROLES else "front"),
                         stamina=full, stamina_max=full, sta_regen=full * config.STAMINA_ROUND_REGEN * 4 / 100,
                         mana=full, mana_max=full, mana_regen=full * config.MANA_ROUND_REGEN,
                         nature=full * config.NATURE_START, nature_max=full, nature_regen=full * config.NATURE_ROUND_REGEN)

    # -- pools and action points (pools.py) --------------------------------------------
    @staticmethod
    def pool_cost(c, ab) -> float:
        """What this skill would burn from the fighter's pool (0 when free, or for a fighter without that pool)."""
        p = pools.pool_of(ab)
        if not p or not getattr(c, p + "_max"):
            return 0.0
        return round(pools.pool_cost(ab) * c.pool_scale, 1)

    @classmethod
    def can_pay(cls, c, ab) -> bool:
        p = pools.pool_of(ab)
        return not p or getattr(c, p) + 1e-9 >= cls.pool_cost(c, ab)

    @classmethod
    def short_of(cls, c, ab) -> str:
        """Why the fighter cannot use this skill right now ('' = it can)."""
        if pools.ap_cost(ab) > c.ap:
            return f"needs {pools.ap_cost(ab)} AP"
        if not cls.can_pay(c, ab):
            return f"not enough {pools.pool_of(ab)}"
        return ""

    @classmethod
    def pay(cls, c, ab) -> None:
        c.ap = max(0, c.ap - pools.ap_cost(ab))
        p = pools.pool_of(ab)
        if p:
            setattr(c, p, max(0.0, getattr(c, p) - cls.pool_cost(c, ab)))

    @staticmethod
    def catch_breath(c, share: float) -> None:
        for p in pools.POOLS:
            m = getattr(c, p + "_max")
            if m:
                setattr(c, p, min(m, getattr(c, p) + m * share))

    # -- main loop -----------------------------------------------------------
    def run(self, party, enemies: List[Enemy], permadeath: bool = True, split_xp: bool = True,
            xp_mult: float = 1.0, synergy: float = 1.0, terrain=None) -> BattleReport:
        """party: list of Slime (HP and XP are written back). enemies: list of Enemy templates.
        permadeath=False knocks slimes out at 1 HP instead of killing them (training dungeons).
        split_xp=False gives every survivor the full wave XP instead of an equal share."""
        run = self.start(party, enemies, permadeath, split_xp, xp_mult, synergy, terrain, manual=False)
        run.advance()
        return run.report

    def start(self, party, enemies: List[Enemy], permadeath: bool = True, split_xp: bool = True,
              xp_mult: float = 1.0, synergy: float = 1.0, terrain=None, manual: bool = False,
              modifier=None, boons=(), rarity_xp: bool = False, loot: bool = True) -> "BattleRun":
        """Set a battle up and return it un-advanced; BattleRun.advance() plays it until a manual slime must choose."""
        self.fx_events = []                                   # the arena's animation queue starts over with each fight
        totals: Dict[str, int] = {}
        for e in enemies:
            totals[e.key] = totals.get(e.key, 0) + 1
        seen: Dict[str, int] = {}
        foes = []
        for e in enemies:
            n = seen.get(e.key, 0)
            seen[e.key] = n + 1
            c = self.from_enemy(e)
            if totals[e.key] > 1:          # "Dust Bunny A", "Dust Bunny B"
                c.name = f"{e.name} {chr(65 + n)}"
            foes.append(c)
        mine = [self.from_slime(s, synergy) for s in party]
        everyone = mine + foes
        log = [f"⚔ Battle begins! {', '.join(c.emoji + c.name for c in mine)}  vs  "
               f"{', '.join(c.emoji + c.name for c in foes)}"]
        if terrain:
            log.append(f"🌍 {terrain.emoji} {terrain.name}: {terrain_mod.describe(terrain)}")
        if modifier:
            log.extend(modifiers.apply(modifier, mine, foes))
        for name, amount in boons:                          # bought at a wayside stop: lasts this fight
            for c in mine:
                fx.add_buff(c, name, amount, modifiers.WHOLE_FIGHT)
        if boons:
            log.append("🎒 Supplies from the wayside stop: " + ", ".join(f"{n} +{round(a * 100)}%" for n, a in boons))
        for s_ in party:
            note = emotions.battle_note(s_)
            if note:
                log.append(note)
        run = BattleRun(self, party, mine, enemies, everyone, log, terrain, manual,
                        dict(permadeath=permadeath, split_xp=split_xp, xp_mult=xp_mult, rarity_xp=rarity_xp, loot=loot))
        run.synergy = synergy
        return run

    def _simulate(self, everyone, log, cap: int = config.ROUND_CAP, stall: int = 0):
        """Round loop shared by battles and duels. Returns (rounds, winner). With `stall`, a fight in which no HP has
        changed at the end of that many rounds in a row stops early with no winner (a stalemate)."""
        gen = self._sim_gen(everyone, log, cap, None, stall)
        try:
            while True:
                next(gen)                      # no BattleRun: nothing ever pauses
        except StopIteration as stop:
            return stop.value

    def _sim_gen(self, everyone, log, cap: int, run: Optional["BattleRun"], stall: int = 0):
        """The round loop as a generator: it yields whenever `run` is in manual mode and a party slime must choose.
        The generator's return value is (rounds, winner)."""
        rounds = 0
        history = []                                          # end-of-round HP of every fighter (stalemate check)
        self.delayed, self.last_hits, self.round = [], {}, 0
        self._everyone = everyone
        while rounds < cap and self._side_alive(everyone, "party") \
                and self._side_alive(everyone, "foes"):
            rounds += 1
            self.round = rounds
            log.append(f"--- Round {rounds} ---")
            for c in everyone:
                c.acted = False
            self._land_delayed(everyone, log)
            order = sorted((c for c in everyone if c.alive),
                           key=lambda c: (-c.stat("spd"), self.rng.random()))
            if run:
                run.round, run.order, run.turn_index = rounds, order, 0
            for i, actor in enumerate(order):
                if run:
                    run.turn_index = i
                if not actor.alive:
                    continue
                if not (self._side_alive(everyone, "party") and self._side_alive(everyone, "foes")):
                    break
                yield from self._turn_gen(actor, everyone, log, run)
                actor.acted = True
                while actor.extra_turns > 0 and actor.alive and self._side_alive(everyone, "party") \
                        and self._side_alive(everyone, "foes"):
                    actor.extra_turns -= 1
                    yield from self._turn_gen(actor, everyone, log, run)
            self._hazard(everyone, log)
            for c in everyone:
                if c.alive and not c.minion:
                    if c.stamina_max:
                        c.stamina = min(c.stamina_max, c.stamina + c.sta_regen)
                    if c.mana_max:
                        c.mana = min(c.mana_max, c.mana + c.mana_regen)
                    if c.nature_max:
                        c.nature = min(c.nature_max, c.nature + c.nature_regen)
                if c.alive and c.side == "party" and not c.minion:
                    rg = c.mods.get("regen", 0.0)
                    if rg and c.hp < c.max_hp:
                        c.hp = min(c.max_hp, c.hp + max(1, int(c.max_hp * rg)))
            if stall:                                         # a stalemate: in `stall` rounds nobody has been worn down
                fighters = [c for c in everyone if not c.minion]          # health and every pool: while a healer still
                history.append([(c.hp, c.stamina, c.mana, c.nature) for c in fighters])   # burns mana, it is no stalemate
                if len(history) > stall:
                    then = history[-1 - stall]
                    tops = lambda c: (c.stamina_max, c.mana_max, c.nature_max)
                    steady = all(abs(v - h) <= max(1.0, config.SPAR_STALL_SHARE * m)        # no pool still draining ...
                                 for c, hs in zip(fighters, then) for v, h, m in zip((c.stamina, c.mana, c.nature), hs[1:], tops(c)))
                    left = cap - rounds                                                 # ... and at this pace nobody
                    safe = all(c.hp - 1 > (hs[0] - c.hp) / stall * left for c, hs in zip(fighters, then))   # falls in time
                    if steady and safe:
                        log.append(f"🤝 {stall} rounds and nobody is really wearing down: neither side can break the other.")
                        return rounds, None
        if not self._side_alive(everyone, "foes"):
            winner = "party"
        elif not self._side_alive(everyone, "party"):
            winner = "foes"
        else:
            winner = None
        return rounds, winner

    def _land_delayed(self, everyone, log) -> None:
        """Abilities cast with a delay land at the start of the round they are due."""
        due = [d for d in self.delayed if d["round"] <= self.round]
        self.delayed = [d for d in self.delayed if d["round"] > self.round]
        for d in due:
            actor, ab = d["actor"], d["ability"]
            foes = [c for c in everyone if c.side != actor.side and c.alive]
            targets = [t for t in d["targets"] if t.alive] or self.choose_targets(
                actor, ab, [c for c in everyone if c.side == actor.side and c.alive], foes)
            if not targets:
                continue
            log.append(f"  ⏳ {actor.name}'s {ab.name} lands!")
            KIND_HANDLERS[ab.kind](self, actor, ab, targets, everyone, log)
            fx.apply(self, actor, ab, targets, everyone, log, _cast_stat(actor, ab))
            for t in targets:
                if not t.alive and t.side != actor.side:
                    log.append(f"  {t.emoji}{t.name} is defeated!")

    @staticmethod
    def reachable(actor, ab, foes):
        """Foes this attack can reach: a melee blow only the front row (summoned minions count as front), unless nobody stands there."""
        if not is_melee(ab):
            return foes
        front = [c for c in foes if c.row == "front" or c.minion]
        return front or foes

    @staticmethod
    def targetable(foes):
        """Foes that can be picked (hidden ones only if nobody else is left)."""
        return [c for c in foes if not c.untarget] or foes

    def _hazard(self, everyone, log) -> None:
        """End of round: the terrain's hazard hurts everybody who isn't immune (an attuned / native element)."""
        t = self.terrain
        if not t or not t.hazard_pct or not (self._side_alive(everyone, "party") and self._side_alive(everyone, "foes")):
            return
        hit = {"party": [], "foes": []}
        for c in everyone:
            if not c.alive or c.minion:
                continue
            own = set(c.mastery) | ({c.element} if c.element else set())
            own |= {b for e in own for b in elements.components(e)}
            if own & set(t.hazard_immune):
                continue
            dmg = max(1, int(c.max_hp * t.hazard_pct))
            c.hurt(dmg)
            hit[c.side].append(f"{c.name} -{dmg}")
            if not c.alive:
                log.append(f"  {c.emoji}{c.name} succumbs to the {t.hazard_label or 'terrain'}!")
        for side, who in hit.items():
            if who:
                log.append(f"  🌫 {t.hazard_label or 'hazard'} ({'party' if side == 'party' else 'foes'}): " + ", ".join(who[:6])
                           + (f" +{len(who) - 6} more" if len(who) > 6 else ""))

    def duel(self, a, b) -> "BattleReport":
        """Non-lethal friendly match between two slimes (sparring). No XP, no loot; the loser is left at 1 HP
        (reaching 1 HP = yielding). HP is written back; the caller handles style XP, bonds and morale."""
        ca, cb = self.from_slime(a, 1.0, "party"), self.from_slime(b, 1.0, "foes")
        for c in (ca, cb):
            c.nonlethal = True
            c.stamina, c.mana = c.stamina_max, c.mana_max      # a spar starts fresh (and nothing is written back)
        log = [f"🥊 Sparring match: {ca.emoji}{ca.name} vs {cb.emoji}{cb.name}"]
        self.terrain = None
        rounds, winner = self._simulate([ca, cb], log, config.DUEL_ROUND_CAP, config.SPAR_STALL_ROUNDS)
        if winner is None and rounds >= config.DUEL_ROUND_CAP:     # round cap: the healthier slime takes it on points
            winner = "party" if ca.hp / ca.max_hp >= cb.hp / cb.max_hp else "foes"
        log.append(f"🏅 {(ca if winner == 'party' else cb).name} wins the spar!" if winner else f"🤝 {ca.name} and {cb.name} call it a draw.")
        for s, c in ((a, ca), (b, cb)):
            s.hp = max(1, int(c.hp))
            s.needs.add("energy", -8)
        rep = BattleReport(log, winner, rounds)
        rep.winner_slime = a if winner == "party" else b if winner == "foes" else None
        return rep

    def team_spar(self, party_a, party_b, syn_a: float = 1.0, syn_b: float = 1.0) -> "BattleReport":
        """Non-lethal friendly match between two whole parties. No XP, no loot; whoever reaches 1 HP yields, and
        everybody's HP is written back (losers are left low). The caller handles style XP, proficiency and bonds."""
        ca = [self.from_slime(s, syn_a, "party") for s in party_a]
        cb = [self.from_slime(s, syn_b, "foes") for s in party_b]
        for c in ca + cb:
            c.nonlethal = True
            c.stamina, c.mana = c.stamina_max, c.mana_max
        log = ["🥊 Party spar: " + ", ".join(c.emoji + c.name for c in ca) + "  vs  " + ", ".join(c.emoji + c.name for c in cb)]
        self.terrain = None
        rounds, winner = self._simulate(ca + cb, log, config.DUEL_ROUND_CAP, config.SPAR_STALL_ROUNDS)
        if winner is None and rounds >= config.DUEL_ROUND_CAP:     # round cap: the healthier side takes it on points
            share = lambda cs: sum(c.hp for c in cs) / max(1.0, sum(c.max_hp for c in cs))
            winner = "party" if share(ca) >= share(cb) else "foes"
        log.append(f"🏅 {'The first' if winner == 'party' else 'The second'} party wins the spar!" if winner else "🤝 The two parties call it a draw.")
        for s, c in list(zip(party_a, ca)) + list(zip(party_b, cb)):
            s.hp = max(1, int(c.hp))
            s.needs.add("energy", -8)
        return BattleReport(log, winner, rounds)

    @staticmethod
    def _side_alive(everyone, side) -> bool:
        return any(c.alive and c.side == side and not c.minion for c in everyone)

    # -- one turn ------------------------------------------------------------
    def _turn(self, actor: Combatant, everyone, log) -> None:
        gen = self._turn_gen(actor, everyone, log, None)
        for _ in gen:
            pass

    def _turn_gen(self, actor: Combatant, everyone, log, run: Optional["BattleRun"]):
        # status tick
        if actor.poison[0] > 0:
            dmg = actor.poison[1]
            actor.hurt(dmg)
            actor.poison = (actor.poison[0] - 1, actor.poison[1])
            log.append(f"  ☠ {actor.name} takes {dmg} poison damage.")
            if not actor.alive:
                log.append(f"  {actor.name} is defeated!")
                return
        state = fx.tick(actor, log)
        if state == "dead":
            return
        if state == "skip":
            return
        if actor.morale < config.MORALE_BROKEN and actor.side == "party" and \
                self.rng.random() < config.MORALE_FREEZE_CHANCE:
            log.append(f"  😰 {actor.name} freezes - morale is broken!")
            return
        for k in list(actor.cooldowns):
            actor.cooldowns[k] = max(0, actor.cooldowns[k] - 1)
        actor.ap = min(config.AP_MAX, actor.ap + config.AP_PER_TURN)
        actor.buffed = False
        worn = False                                       # the guard wears off at the first other action this turn
        for _ in range(config.AP_TURN_ACTIONS):
            if actor.ap <= 0 or not actor.alive or actor.stun or not (
                    self._side_alive(everyone, "party") and self._side_alive(everyone, "foes")):
                break
            allies = [c for c in everyone if c.side == actor.side and c.alive]
            foes = self.targetable([c for c in everyone if c.side != actor.side and c.alive])
            if not foes:
                break
            choice = None
            if run and run.manual and actor.side == "party" and not actor.minion and run.auto_actor is not actor:
                run.waiting = actor                     # hand control to the player
                while run.waiting is not None and run.manual:
                    yield run
                choice, run.choice = run.choice, None
                if choice == "end":
                    break
            if choice:
                ability, targets = choice
                targets = [t for t in targets if t.alive] or self.choose_targets(actor, ability, allies, foes)
            else:
                ability = self.ai_pick(actor, allies, foes)
                if ability is None:                     # saving its points for something bigger
                    break
                targets = self.choose_targets(actor, ability, allies, foes)
            if ability.kind != "guard" and not worn:
                worn = True
                if actor.guard > 0:
                    actor.guard -= 1
            self._act(actor, ability, targets, allies, foes, everyone, log)
            if ability.kind == "utility":
                actor.buffed = True
            if ability.key == "defend":                 # bracing ends the turn; the breath caught refills the pools
                self.catch_breath(actor, config.POOL_DEFEND)
                break
        if run and run.auto_actor is actor:
            run.auto_actor = None

    def _act(self, actor, ability, targets, allies, foes, everyone, log) -> None:
        """One action: pay its AP and pool, then resolve it."""
        orig_key = ability.key
        self.pay(actor, ability)
        if fx.find(ability, "copy"):                       # Stolen Spell: use the last skill a foe used
            seen = [c.last_ability for c in foes if c.last_ability and not fx.find(get_ability(c.last_ability), "copy")]
            if not seen:
                log.append(f"  {actor.emoji}{actor.name}'s {ability.name} has nothing to copy.")
                return
            log.append(f"  🪞 {actor.name} copies {get_ability(seen[0]).name}!")
            ability = get_ability(seen[0])
            targets = self.choose_targets(actor, ability, allies, foes)
        if not targets:
            return
        actor.winded = bool(actor.stamina_max and actor.stamina < config.WINDED_BELOW * actor.stamina_max
                            and ability.kind in ("damage", "drain", "poison"))
        if actor.winded:
            log.append(f"  😮‍💨 {actor.emoji}{actor.name} is winded!")
        sc = actor.cap_scale.get(ability.key) or (actor.cap_scale.get(orig_key) if orig_key in actor.cap_scale else None)
        if sc:
            ability = fx.scale(ability, sc)
        if orig_key in actor.spell_names:
            ability = replace(ability, name=actor.spell_names[orig_key])
        if ability.element and ability.tier >= 2:
            ability = spells.mutate(ability, elements.effective_mastery(actor.mastery, ability.element))
        actor.last_ability = ability.key
        if orig_key in actor.hybrid:
            actor.spec_uses += 1
        else:
            actor.uses += 1
        delay = fx.find(ability, "delay")
        if delay and ability.kind in ("damage", "drain", "poison"):
            self.delayed.append(dict(round=self.round + delay[1], actor=actor, ability=fx.strip_delay(ability), targets=list(targets)))
            log.append(f"  ⏳ {actor.emoji}{actor.name} gathers power for {ability.name}...")
        else:
            self.last_hits = {}
            KIND_HANDLERS[ability.kind](self, actor, ability, targets, everyone, log)
            if ability.fx:
                fx.apply(self, actor, ability, targets, everyone, log, _cast_stat(actor, ability))
        actor.winded = False
        if ability.element:
            actor.casts[ability.element] = actor.casts.get(ability.element, 0) + 1
        cd = pools.cooldown(get_ability(orig_key)) if orig_key in actor.abilities else pools.cooldown(ability)
        if cd:
            actor.cooldowns[orig_key] = cd
        for c in targets:
            if not c.alive and c.side != actor.side:
                log.append(f"  {c.emoji}{c.name} is defeated!")

    # -- AI ------------------------------------------------------------------
    def ai_pick(self, actor, allies, foes) -> Optional[Ability]:
        """What the AI does with the points it has: its favourite skill if affordable; else something that still leaves
        enough for that skill next turn; else a Defend when hurt or drained; else it ends the turn and saves (None)."""
        ready = [a for a in (get_ability(k) for k in actor.abilities)
                 if actor.cooldowns.get(a.key, 0) == 0 and self.can_pay(actor, a)
                 and (a.kind != "utility" or self._buff_ok(actor, a))]
        want = self.choose_ability(actor, allies, foes, ready)
        need = pools.ap_cost(want)
        if need <= actor.ap:
            return want
        keep = lambda a: pools.ap_cost(a) <= actor.ap and actor.ap - pools.ap_cost(a) + config.AP_PER_TURN >= need
        fill = [a for a in ready if a.key != want.key and keep(a)]
        if fill:
            f = self.choose_ability(actor, allies, foes, fill, fallback=False)
            if f is not None and keep(f):
                return f
        defend = get_ability("defend")
        if keep(defend) and actor.guard == 0 and want.key != "defend":   # brace while saving a point or two
            return defend
        drained = any(getattr(actor, p + "_max") and getattr(actor, p) < 0.3 * getattr(actor, p + "_max") for p in pools.POOLS)
        if keep(defend) and (actor.hp < actor.max_hp * 0.5 or drained) and actor.guard == 0:
            return defend
        return None

    URGENT = {"revive", "raise", "cleanse", "shield", "untarget", "undying", "tithe"}

    @classmethod
    def _buff_ok(cls, actor, ab) -> bool:
        """The AI's buff budget: never save up just to buff, one buff or hex a turn, and only while a blow still fits in
        the turn after it - unless it is a rescue (revive, cleanse, shield, hide)."""
        cost = pools.ap_cost(ab)
        if cost > actor.ap:
            return False
        if {f[0] for f in ab.fx} & cls.URGENT:
            return True
        return not actor.buffed and actor.ap - cost >= config.AP_PER_TURN

    def choose_ability(self, actor, allies, foes, ready=None, fallback: bool = True) -> Optional[Ability]:
        """The skill this fighter would most like to use (cost in AP decides between attacks: damage per point)."""
        if ready is None:
            ready = [a for a in (get_ability(k) for k in actor.abilities)
                     if actor.cooldowns.get(a.key, 0) == 0 and self.can_pay(actor, a)]
        offense = [a for a in ready if a.kind in ("damage", "drain", "poison")]
        summons = [a for a in ready if a.kind == "summon"]
        heals = [a for a in ready if a.kind == "heal"]
        guards = [a for a in ready if a.kind == "guard"]
        hurt = [c for c in allies if c.hp < c.max_hp * 0.6]
        stance = actor.behavior

        heal_score = lambda a: a.power * (len(hurt) if a.target == "all_allies" and len(hurt) > 1 else 1) / pools.ap_cost(a)
        if stance == "heal" and hurt and heals:
            return max(heals, key=heal_score)
        if stance == "defend":
            low = actor.hp < actor.max_hp * 0.5 or any(c.hp < c.max_hp * 0.4 for c in allies)
            if low and guards:
                return guards[0]
            if low and actor.guard == 0:
                return get_ability("defend")
        elif stance != "heal" and actor.hp < actor.max_hp * 0.3 and heals:
            return max(heals, key=heal_score)          # panic-heal regardless of stance
        for a in [a for a in ready if a.kind == "utility"]:
            if _utility_worth(self, actor, a, allies, foes):
                return a
        if summons and not any(c.minion and c.side == actor.side for c in allies):
            return summons[0]
        if offense:
            def score(a):
                n = len(foes) if a.target == "all_enemies" else 1
                bonus = 1.2 if a.kind == "poison" and not any(f.poison[0] for f in foes) else 1.0
                weakest = min(foes, key=lambda f: f.hp)
                return (a.power * n * bonus * weakest.matchup(a.element)
                        * _mastery_mult(actor, a)) / pools.ap_cost(a)
            return max(offense, key=score)
        return get_ability("splat") if fallback else None      # everyone can bonk

    def choose_targets(self, actor, ability, allies, foes) -> List[Combatant]:
        t = ability.target
        if t == "self":
            return [actor]
        if t == "all_enemies":
            return foes
        if t == "all_allies":
            return allies
        if t == "ally":
            pool = [c for c in allies if not c.minion] or allies
            if ability.kind == "guard":
                pool = [c for c in pool if c.guard == 0] or pool
            return [min(pool, key=lambda c: c.hp / c.max_hp)]
        # enemy
        if not foes:
            return []
        if actor.behavior == "explore":
            return [self.rng.choice(foes)]
        if ability.key == "backstab":
            return [min(foes, key=lambda c: c.hp)]
        foes = self.reachable(actor, ability, foes)
        real = [c for c in foes if not c.minion] or foes
        if ability.kind == "utility":                       # debuffs, marks and stuns go to the most dangerous foe
            return [max(real, key=lambda c: c.stat("atk") + c.stat("mag"))]
        return [min(real, key=lambda c: c.hp)]

    # -- aftermath: write HP back, grant XP and loot ---------------------------
    def _finish(self, party, mine, enemies, report: BattleReport, permadeath: bool = True,
                split_xp: bool = True, xp_mult: float = 1.0, rarity_xp: bool = False, loot: bool = True) -> None:
        win = report.winner == "party"
        survivors = []
        for s, c in zip(party, mine):
            s.hp = max(0, int(c.hp))
            if c.stamina_max:
                s.stamina_frac = max(0.0, min(1.0, c.stamina / c.stamina_max))
            if c.mana_max:
                s.mana_frac = max(0.0, min(1.0, c.mana / c.mana_max))
            if not c.alive:
                report.fallen.append(s)
            if not c.alive and permadeath:        # Game._reap removes them
                s.death_cause = "fell in battle"
                report.deaths.append(s.name)
                continue
            if not c.alive:                       # Pit: knocked out, not killed (Game applies the penalties)
                report.knocked_out.append(s.name)
                s.hp = 1
                continue
            s.hp = max(1, s.hp)
            for el, n in c.casts.items():                      # casting builds elemental mastery
                for b in elements.components(el):
                    if b in s.attuned:
                        elements.add_mastery_xp(s, b, n * config.MASTERY_PER_CAST_XP)
            if c.uses:
                s.class_prof = min(100.0, s.class_prof + min(config.PROF_BATTLE_CAP, c.uses * config.PROF_BATTLE_GAIN))
                s.prof_idle = 0
            if c.spec_uses:
                s.spec_prof = min(100.0, s.spec_prof + min(config.PROF_BATTLE_CAP, c.spec_uses * config.PROF_SPEC_BATTLE_GAIN))
                s.spec_idle = 0
            s.needs.add("energy", -10)
            s.needs.add("esteem", 10 if win else -6)
            survivors.append(s)
        for name in report.deaths:
            report.log.append(f"☠ {name} has fallen and will not rise again.")
        if win:
            report.xp = int(sum(e.xp for e in enemies) * xp_mult)
            for e in (enemies if loot else []):
                for res, (lo, hi) in e.loot.items():
                    n = self.rng.randint(lo, hi)
                    if n:
                        report.loot[res] = report.loot.get(res, 0) + n
                if self.rng.random() < e.purple_chance:        # purple gel is rare
                    report.loot["purple_gel"] = report.loot.get("purple_gel", 0) + e.purple_amount
            if self.wallet:
                self.wallet.add_many(report.loot)
            share = max(1, report.xp // max(1, len(survivors))) if split_xp else report.xp
            for s in survivors:
                s.wins += 1
                report.log.extend(add_xp(s, int(share * (config.rarity_xp_factor(s.rarity) if rarity_xp else 1.0))))
            report.log.append(f"Rewards: +{report.xp} XP total, loot: "
                              + (", ".join(f"{v} {k}" for k, v in report.loot.items()) or "none"))


# ---- ability kind handlers -------------------------------------------------------
def _mastery_mult(actor, ability) -> float:
    """Spells grow with the caster's mastery of the spell's element (weakest component)."""
    if not ability.element:
        return 1.0
    return 1 + config.MASTERY_SPELL_BONUS * elements.effective_mastery(actor.mastery, ability.element)


def _style_attack(actor, ability) -> float:
    """Fighting-style perks: swordsmanship boosts attack-stat moves, spellcraft boosts magic-stat moves."""
    if ability.stat == "atk":
        return 1 + config.STYLE_SWORD_DAMAGE * actor.style.get("sword", 0)
    if ability.stat == "mag":
        return 1 + config.STYLE_MAGIC_POWER * actor.style.get("magic", 0)
    return 1.0


def _cast_stat(actor, ability) -> float:
    """Elemental spells scale with magic - or, for non-mages, with raw attack (imbuing)."""
    if ability.element and ability.stat == "mag":
        return max(actor.stat("mag"), config.IMBUE_ATK_FACTOR * actor.stat("atk"))
    return actor.stat(ability.stat)


def _terrain_mult(bs, ability) -> float:
    return terrain_mod.element_factor(bs.terrain, ability.element) if bs.terrain else 1.0


def _damage_value(bs: BattleSystem, actor, ability, target):
    pierce = {f[1]: f[2] for f in ability.fx if f[0] == "pierce"}
    raw = ability.power * _cast_stat(actor, ability) * _mastery_mult(actor, ability) * _terrain_mult(bs, ability) \
        - 0.5 * target.stat("defense") * (1 - pierce.get("def", 0.0))
    eff = target.matchup(ability.element)
    raw = max(1.0, raw) * bs.rng.uniform(0.9, 1.1) * eff * _style_attack(actor, ability)
    raw *= max(0.6, 1 - config.STYLE_SWORD_GUARD * target.style.get("sword", 0))       # parrying
    if actor.winded:
        raw *= config.STAMINA_WINDED_MULT
    if ability.stat == "mag":
        raw *= 1 + actor.mods.get("spell_power", 0.0)
        raw *= 1 - min(0.5, target.mods.get("resist", 0.0)) * (1 - pierce.get("resist", 0.0))
    raw *= 1 - min(0.5, target.mods.get("guard", 0.0)) * (1 - pierce.get("guard", 0.0))
    if target.row == "back":
        raw *= config.ROW_BACK_GUARD                       # (formation) the back row is sheltered
    if actor.row == "back" and is_melee(ability):
        raw *= config.ROW_BACK_MELEE                       # (formation) a melee fighter in the back row cannot swing properly
    if target.marked[0] > 0:
        raw *= 1 + target.marked[1]
    tb = fx.find(ability, "terrain_boost")
    if tb and bs.terrain and bs.terrain.hazard_pct:
        raw *= 1 + tb[1]
    ex = fx.find(ability, "execute")
    if ex and target.hp < target.max_hp * ex[1]:
        raw *= ex[2]
    crit = bs.rng.random() < (config.CRIT_CHANCE + (0.1 if actor.behavior == "explore" else 0)
                              + config.STYLE_ARCHERY_CRIT * actor.style.get("archery", 0)
                              + (bs.terrain.crit if bs.terrain else 0.0) + actor.mods.get("crit_rate", 0.0))
    if fx.find(ability, "crit") or (fx.find(ability, "first_strike") and not target.acted):
        crit = True
    if ability.element:
        raw *= 1 + actor.mods.get("elem", {}).get(ability.element, 0.0)
    if crit:
        raw *= config.CRIT_MULT + actor.mods.get("crit_dmg", 0.0)
    if target.guard > 0:
        raw *= 1 - (1 - config.GUARD_REDUCTION) * (1 - pierce.get("guard", 0.0))
    return max(1, int(raw)), crit, eff


def _fxev(bs, everyone, actor, t, kind: str, element: str = "", crit: bool = False, amount: int = 0, area: bool = False) -> None:
    """Record one action for the arena to animate (who, on whom, what kind, which element). Display only: the rules
    never read it. Kept short; each event carries a running number so the page plays only the new ones."""
    try:
        a, b = everyone.index(actor), everyone.index(t)
    except ValueError:
        return
    bs.fx_seq = getattr(bs, "fx_seq", 0) + 1
    ev = getattr(bs, "fx_events", None)
    if ev is None:
        ev = bs.fx_events = []
    ev.append(dict(n=bs.fx_seq, a=a, t=b, k=kind, el=element or "", c=bool(crit), v=int(amount), ar=bool(area)))
    del ev[:-24]


def _needs_flags(s) -> dict:
    """A party slime's food and energy for the arena: a warning when either is low."""
    food, energy = s.needs.get("food"), s.needs.get("energy")
    return dict(food=int(food), energy=int(energy), hungry=food < config.FIGHT_WARN_BELOW, tired=energy < config.FIGHT_WARN_BELOW)


def _eff_tag(eff: float) -> str:
    return " (WEAK!)" if eff > 1 else " (resisted)" if eff < 1 else ""


def _h_damage(bs, actor, ab, targets, everyone, log):
    n_hits = (fx.find(ab, "hits") or (0, 1))[1]
    plan = [(t, h) for t in targets for h in range(n_hits)]
    for t, _h in plan:
        if not t.alive:
            continue
        ev = 0.0 if fx.find(ab, "nomiss") else min(0.5, t.mods.get("evasion", 0.0))
        if ev and bs.rng.random() < ev:
            log.append(f"  {t.emoji}{t.name} dodges {actor.name}'s {ab.name}!")
            _fxev(bs, everyone, actor, t, "dodge", ab.element)
            continue
        hit_ab = replace(ab, element=bs.rng.choice(elements.BASICS)) if fx.find(ab, "prism") else ab
        if actor.imbue[1] > 0 and not hit_ab.element and hit_ab.stat == "atk":
            hit_ab = replace(hit_ab, element=actor.imbue[0])
        dmg, crit, eff = _damage_value(bs, actor, hit_ab, t)
        t.hurt(dmg)
        bs.last_hits[id(t)] = bs.last_hits.get(id(t), 0) + dmg
        _fxev(bs, everyone, actor, t, "spell" if hit_ab.element or hit_ab.stat == "mag" else "hit", hit_ab.element, crit, dmg,
              ab.target.startswith("all_"))
        log.append(f"  {actor.emoji}{actor.name} uses {ab.name} on {t.name}: {dmg} dmg{' (CRIT!)' if crit else ''}{_eff_tag(eff)}"
                   f" [{max(0, int(t.hp))}/{int(t.max_hp)}]")
        ls = actor.mods.get("lifesteal", 0.0)
        if ls and actor.alive:
            actor.hp = min(actor.max_hp, actor.hp + max(1, int(dmg * ls)))
        if t.alive and t.counter[0] > 0 and actor.alive and t.side != actor.side:
            back = max(1, int(t.counter[1] * t.stat("atk") - 0.5 * actor.stat("defense")))
            actor.hurt(back)
            log.append(f"  ↩ {t.emoji}{t.name} counters for {back}!")


def _h_drain(bs, actor, ab, targets, everyone, log):
    for t in targets:
        dmg, _, _ = _damage_value(bs, actor, ab, t)
        t.hurt(dmg)
        bs.last_hits[id(t)] = dmg
        _fxev(bs, everyone, actor, t, "drain", ab.element, False, dmg)
        heal = max(1, dmg // 2)
        actor.hp = min(actor.max_hp, actor.hp + heal)
        log.append(f"  {actor.emoji}{actor.name} siphons {dmg} from {t.name} and heals {heal}.")


def _h_heal(bs, actor, ab, targets, everyone, log):
    for t in targets:
        amt = max(1, int(ab.power * _cast_stat(actor, ab) * 1.5 * bs.rng.uniform(0.95, 1.05)
                         * _mastery_mult(actor, ab) * _style_attack(actor, ab) * _terrain_mult(bs, ab)))
        before = t.hp
        t.hp = min(t.max_hp, t.hp + amt)
        _fxev(bs, everyone, actor, t, "heal", ab.element, False, int(t.hp - before), ab.target.startswith("all_"))
        log.append(f"  💚 {actor.name} uses {ab.name} on {t.name}: +{int(t.hp - before)} HP")
        extra = amt - (t.hp - before)
        if extra > 0 and fx.find(ab, "overheal"):
            t.shield += extra
            log.append(f"  🔰 The overflow becomes a {int(extra)} point shield on {t.name}.")


def _h_guard(bs, actor, ab, targets, everyone, log):
    for t in targets:
        t.guard = max(t.guard, ab.duration or 1)
        _fxev(bs, everyone, actor, t, "guard", ab.element)
        log.append(f"  🛡 {actor.name} uses {ab.name}: {t.name} takes reduced damage for {t.guard} turn(s).")


def _h_poison(bs, actor, ab, targets, everyone, log):
    for t in targets:
        per = max(1, int(ab.power * _cast_stat(actor, ab) * _mastery_mult(actor, ab) * _terrain_mult(bs, ab)))
        if fx.find(ab, "stack") and t.poison[0] > 0:
            per += t.poison[1]
        t.poison = (ab.duration, per)
        _fxev(bs, everyone, actor, t, "poison", ab.element, area=ab.target.startswith("all_"))
        log.append(f"  🧪 {actor.name} uses {ab.name} on {t.name}: poisoned ({per}/turn for {ab.duration}).")


def _h_summon(bs, actor, ab, targets, everyone, log):
    mag = actor.stat(ab.stat)
    emoji, _, mname = (ab.minion or "🦴 Bone Pal").partition(" ")
    n = (fx.find(ab, "count") or (0, 1))[1]
    share = 1.0 if n == 1 else 0.6                       # a legion is many, each weaker
    for i in range(n):
        pal = Combatant(f"{actor.name}'s {mname}" + (f" {i + 1}" if n > 1 else ""), emoji, actor.side,
                        dict(hp=(mag * 2.2 * ab.power + 5) * share, atk=(mag * ab.power * 1.2 + 2) * share, defense=2,
                             mag=0, spd=5), (mag * 2.2 * ab.power + 5) * share, ["splat"], "attack", 1.0,
                        None, minion=True)
        everyone.append(pal)
        _fxev(bs, everyone, actor, pal, "summon")
    log.append(f"  {emoji} {actor.name} calls up {'a ' + mname if n == 1 else str(n) + ' ' + mname + 's'}!")


def _h_utility(bs, actor, ab, targets, everyone, log):
    log.append(f"  ✨ {actor.emoji}{actor.name} uses {ab.name}.")
    for t in targets or [actor]:                              # a blessing on friends, a hex on foes
        _fxev(bs, everyone, actor, t, "buff" if t.side == actor.side else "debuff", ab.element, area=ab.target.startswith("all_"))


KIND_HANDLERS: Dict[str, Callable] = {
    "damage": _h_damage, "drain": _h_drain, "heal": _h_heal,
    "guard": _h_guard, "poison": _h_poison, "summon": _h_summon, "utility": _h_utility,
}


def _rounds_to_win(allies, foes) -> float:
    """Rough number of rounds the party needs to kill every foe (HP left over what the party hits for per round)."""
    dps = sum(max(c.stat("atk"), 1.5 * c.stat("mag")) * 1.4 for c in allies if not c.minion) or 1.0
    return sum(f.hp for f in foes) / dps


def _utility_worth(bs, actor, ab, allies, foes) -> bool:
    """Simple AI: is it worth spending this utility skill now? Pure set-up skills (buffs, marks, debuffs) are skipped
    when the fight will be over in a round or two: hitting is better than buffing."""
    t = ab.target
    names = {f[0] for f in ab.fx}
    if names <= {"buff", "debuff", "mark", "rewrite", "oath"} and _rounds_to_win(allies, foes) < 2.5:
        return False
    fallen = [c for c in bs._everyone if c.side == actor.side and not c.alive and not c.minion] if hasattr(bs, "_everyone") else []
    if "revive" in names:
        return bool(fallen)
    if "raise" in names:
        return bool([c for c in bs._everyone if not c.alive and not c.minion]) if hasattr(bs, "_everyone") else False
    if "tithe" in names:
        return any(c.minion for c in allies) and any(c.hp < c.max_hp * 0.6 for c in allies if not c.minion)
    if "cleanse" in names:
        return any(fx._has_bad(c) for c in allies) or ("strip" in names and any(fx._has_good(c) for c in foes))
    if "strip" in names:
        return any(fx._has_good(c) for c in foes)
    if "shield" in names:
        return any(c.shield == 0 and c.hp < c.max_hp * 0.75 for c in allies)
    if names & {"untarget", "undying", "counter"}:
        return actor.hp < actor.max_hp * 0.5 and not (actor.untarget or actor.undying or actor.counter[0] > 0)
    if "imbue" in names:                                      # not while the weapon still burns, nor against foes it can't hurt
        el = next(f for f in ab.fx if f[0] == "imbue")[1]
        return actor.imbue[1] <= 0 and sum(c.matchup(el) for c in foes) >= len(foes)
    if "oath" in names:
        return not actor.oath
    if "copy" in names:
        return any(c.last_ability for c in foes)
    if names & {"buff"}:
        key = next(f for f in ab.fx if f[0] == "buff")[1]
        return not any(b["name"] == key for c in allies for b in c.buffs)
    if names & {"debuff", "mark", "rewrite", "stun"}:
        strongest = max(foes, key=lambda c: c.stat("atk") + c.stat("mag"))
        return not (strongest.marked[0] or strongest.stun or strongest.stat_set or any(b["amount"] < 0 for b in strongest.buffs))
    return True


# ---- a battle you can step through ------------------------------------------------------
class BattleRun:
    """One battle in progress. In auto mode `advance()` plays it to the end. In manual mode it pauses whenever a
    party slime's turn comes (`waiting`); answer with `act()` (own choice) or `auto_turn()` (let the AI choose for
    this one turn), or hand the whole fight back to the AI with `set_manual(False)`. The player can flip
    between manual and auto at any moment. `view()` is the data a battle area (text now, animation later) draws."""

    def __init__(self, bs: BattleSystem, party, mine, enemies, everyone, log, terrain, manual: bool, opts: dict):
        self.bs, self.party, self.mine, self.enemies = bs, party, mine, enemies
        self.everyone, self.log, self.terrain, self.manual, self.opts = everyone, log, terrain, manual, opts
        self.round, self.order, self.turn_index = 0, [], 0
        self.waiting: Optional[Combatant] = None
        self.choice = None
        self.auto_actor: Optional[Combatant] = None      # "auto this turn": the AI finishes this fighter's turn
        self.report: Optional[BattleReport] = None
        self._gen = None

    @property
    def done(self) -> bool:
        return self.report is not None

    # -- driving ----------------------------------------------------------------
    def advance(self) -> None:
        """Play until a manual slime must choose, or the battle ends (then `report` is set)."""
        if self.done:
            return
        bs = self.bs
        bs.terrain = self.terrain
        try:
            if self._gen is None:
                self._gen = bs._sim_gen(self.everyone, self.log, config.ROUND_CAP, self)
            try:
                next(self._gen)
                return
            except StopIteration as stop:
                rounds, winner = stop.value
        finally:
            bs.terrain = None
        report = BattleReport(self.log, winner, rounds)
        self.log.append({"party": "🏆 Victory!", "foes": "💀 Defeat...", None: "🤝 Draw - everybody is too tired."}[winner])
        bs._finish(self.party, self.mine, self.enemies, report, **self.opts)
        self.report = report
        self.waiting = None

    def refresh(self, slime) -> None:
        """A potion or a morale gift changed this slime mid-fight: rebuild its stats, keeping its current HP."""
        c = next((c for c in self.mine if c.source is slime), None)
        if c is None or not c.alive:
            return
        n = self.bs.from_slime(slime, getattr(self, "synergy", 1.0))
        old_max = c.max_hp
        c.stats, c.mods, c.power_mult, c.morale = n.stats, n.mods, n.power_mult, n.morale
        c.hp = min(c.max_hp, c.hp + max(0.0, c.max_hp - old_max))
        c.stamina_max, c.sta_regen = n.stamina_max, n.sta_regen
        c.stamina = min(c.stamina_max, c.stamina)
        c.mana_max, c.mana_regen, c.nature_max, c.nature_regen = n.mana_max, n.mana_regen, n.nature_max, n.nature_regen
        c.mana, c.nature = min(c.mana_max, c.mana), min(c.nature_max, c.nature)

    def set_manual(self, manual: bool) -> None:
        self.manual = manual
        if not manual and self.waiting is not None:
            self.waiting = None            # the pending turn is decided by the AI
        self.advance()

    def auto_turn(self) -> None:
        """Let the AI take this one turn, then carry on (stops again at the next manual slime)."""
        if self.waiting is None:
            return
        self.auto_actor = self.waiting
        self.choice, self.waiting = None, None
        self.advance()

    def end_turn(self) -> None:
        """The waiting slime stops here and saves its remaining action points."""
        if self.waiting is None:
            return
        self.choice, self.waiting = "end", None
        self.advance()

    def legal_abilities(self, actor: Optional[Combatant] = None) -> List[dict]:
        actor = actor or self.waiting
        out = []
        foes = [(i, c) for i, c in enumerate(self.everyone) if c.side != actor.side and c.alive]
        for k in self.offered(actor):
            a = get_ability(k)
            cd = actor.cooldowns.get(k, 0)
            short = BattleSystem.short_of(actor, a)
            out.append(dict(key=a.key, name=actor.spell_names.get(k, a.name), kind=a.kind, element=a.element, power=a.power,
                            target=a.target, cooldown=cd, ap=pools.ap_cost(a), pool=pools.pool_of(a),
                            cost=BattleSystem.pool_cost(actor, a), short=short or (f"cooldown {cd}" if cd else ""),
                            fx=sorted({f[0] for f in a.fx}), desc=a.description, ready=cd == 0 and not short,
                            eff=({i: round(c.matchup(a.element), 2) for i, c in foes}
                                 if a.element and a.target in ("enemy", "all_enemies") else {}),
                            reach=([i for i, c in foes if c in BattleSystem.reachable(actor, a, [x for _, x in foes])]
                                   if a.target == "enemy" else None)))
        return out

    @staticmethod
    def offered(actor) -> List[str]:
        """The skills a commanded slime can pick: what it knows, plus the free bonk and Defend."""
        return list(actor.abilities) + [k for k in pools.FREE if k not in actor.abilities]

    def act(self, ability_key: str, target: Optional[int] = None) -> None:
        """The waiting slime uses `ability_key` on combatant index `target` (into `everyone`) when it needs one."""
        actor = self.waiting
        if actor is None:
            raise ValueError("Nobody is waiting for orders.")
        if ability_key not in self.offered(actor):
            raise ValueError(f"{actor.name} does not know that ability.")
        ab = get_ability(ability_key)
        if actor.cooldowns.get(ability_key, 0):
            raise ValueError(f"{ab.name} is on cooldown for {actor.cooldowns[ability_key]} more turn(s).")
        short = BattleSystem.short_of(actor, ab)
        if short:
            raise ValueError(f"{actor.spell_names.get(ability_key, ab.name)} {short}.")
        allies = [c for c in self.everyone if c.side == actor.side and c.alive]
        foes = self.bs.targetable([c for c in self.everyone if c.side != actor.side and c.alive])
        if ab.target in ("enemy", "ally"):
            pool = self.bs.reachable(actor, ab, foes) if ab.target == "enemy" else [c for c in allies if not c.minion] or allies
            if target is None:
                tgt = None
            else:
                if not 0 <= target < len(self.everyone) or self.everyone[target] not in pool:
                    raise ValueError("That is not a valid target.")
                tgt = self.everyone[target]
            targets = [tgt] if tgt else self.bs.choose_targets(actor, ab, allies, foes)
        else:
            targets = self.bs.choose_targets(actor, ab, allies, foes)
        self.choice, self.waiting = (ab, targets), None
        self.advance()

    # -- what a battle area draws --------------------------------------------------------
    def _unit(self, i: int, c: Combatant) -> dict:
        return dict(i=i, name=c.name, emoji=c.emoji, side=c.side, hp=max(0, int(c.hp)), max_hp=int(c.max_hp),
                    alive=c.alive, minion=c.minion, element=c.element or "", guard=c.guard,
                    poison=c.poison[0] if c.poison[0] > 0 else 0,
                    stamina=int(c.stamina) if c.stamina_max else None, stamina_max=int(c.stamina_max) or None,
                    mana=int(c.mana) if c.mana_max else None, mana_max=int(c.mana_max) or None,
                    nature=int(c.nature) if c.nature_max else None, nature_max=int(c.nature_max) or None,
                    ap=c.ap, ap_max=config.AP_MAX,
                    winded=c.winded, status=fx.statuses(c), row=c.row,
                    sid=(getattr(c.source, "id", None) if c.side == "party" and not c.minion and hasattr(c.source, "archetype") else None),
                    **(_needs_flags(c.source) if c.side == "party" and not c.minion and hasattr(c.source, "needs") else {}))

    def view(self, tail: int = 40) -> dict:
        t = self.terrain
        w = self.waiting
        return dict(manual=self.manual, done=self.done, round=self.round,
                    terrain=dict(name=t.name, emoji=t.emoji, text=terrain_mod.describe(t)) if t else None,
                    units=[self._unit(i, c) for i, c in enumerate(self.everyone)],
                    order=[self.everyone.index(c) for c in self.order if c.alive],
                    current=self.everyone.index(self.order[self.turn_index]) if self.order and self.turn_index < len(self.order) else None,
                    waiting=self.everyone.index(w) if w is not None else None,
                    abilities=self.legal_abilities() if w is not None else [],
                    fx=list(getattr(self.bs, "fx_events", []) or []),
                    log=self.log[-tail:])
