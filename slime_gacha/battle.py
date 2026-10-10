"""BattleSystem: deterministic (seeded) turn-based auto-combat.

Flow: build Combatants -> loop rounds (speed order) -> each actor's AI picks an ability from its
stance -> KIND_HANDLERS resolve it -> BattleReport (log + rewards). The UI only prints the report.
Add a new ability *kind* by writing a handler and adding it to KIND_HANDLERS.
"""
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from . import config
from .abilities import Ability, get_ability
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


ENEMIES: "Registry[Enemy]" = Registry("enemy")


def register_enemy(e: Enemy) -> Enemy:
    return ENEMIES.register(e, e.key)


def _e(hp, atk, d, mag, spd):
    return dict(hp=hp, atk=atk, defense=d, mag=mag, spd=spd)


for _en in [
    Enemy("dust_bunny", "Dust Bunny", "🐇", 1, _e(22, 6, 2, 0, 5), ["splat"], 12, {"gel": (5, 12)}),
    Enemy("crust_beetle", "Crust Beetle", "🪲", 1, _e(30, 7, 5, 0, 3), ["splat", "smash"], 15, {"gel": (6, 14), "food": (0, 2)}),
    Enemy("parched_wisp", "Parched Wisp", "👻", 2, _e(32, 2, 3, 10, 6), ["spark", "curse"], 28, {"gel": (10, 22), "essence": (0, 3)}),
    Enemy("hollow_knight", "Hollow Knight", "🛡️", 2, _e(60, 11, 8, 0, 5), ["splat", "smash"], 35, {"gel": (12, 26)}),
    Enemy("thorn_sprite", "Thorn Sprite", "🧚", 2, _e(30, 10, 3, 2, 10), ["stab", "venom_dart"], 30, {"gel": (10, 20), "food": (1, 3)}),
    Enemy("dry_brute", "Dry Tide Brute", "🗿", 3, _e(130, 17, 10, 0, 5), ["smash", "rampage"], 80, {"gel": (30, 55), "essence": (2, 6)}),
    Enemy("crown_wraith", "Crown Wraith", "👑", 3, _e(95, 4, 6, 18, 7), ["arcane_surge", "siphon"], 90, {"gel": (30, 55), "essence": (3, 8)}),
    Enemy("parched_king", "The Parched King", "🏜️", 4, _e(380, 22, 12, 20, 6), ["smash", "rampage", "arcane_surge", "curse"], 400, {"gel": (150, 250), "essence": (20, 40)}),
]:
    register_enemy(_en)


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

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def max_hp(self) -> float:
        return self.stats["hp"]

    def stat(self, name: str) -> float:
        v = self.stats[name]
        return v * self.power_mult if name in ("atk", "mag") else v


@dataclass
class BattleReport:
    log: List[str]
    winner: Optional[str]           # "party" | "foes" | None (draw)
    rounds: int
    xp: int = 0
    loot: Dict[str, int] = field(default_factory=dict)

    @property
    def victory(self) -> bool:
        return self.winner == "party"


# ---- the system -------------------------------------------------------------------
class BattleSystem:
    def __init__(self, rng: random.Random, wallet: Optional[ResourceManager] = None):
        self.rng = rng
        self.wallet = wallet

    # -- setup ---------------------------------------------------------------
    def generate_enemies(self, tier: int, count: int = 3) -> List[Enemy]:
        pool = [e for e in ENEMIES if e.tier == tier]
        if not pool:
            raise ValueError(f"no enemies for tier {tier}")
        if tier >= 4:
            return [pool[0]]
        return [self.rng.choice(pool) for _ in range(count)]

    @staticmethod
    def from_slime(s) -> Combatant:
        return Combatant(s.name, s.arch.emoji, "party", dict(s.max_stats()), float(s.hp),
                         s.known_abilities(), s.behavior, s.power_multiplier(), s)

    @staticmethod
    def from_enemy(e: Enemy) -> Combatant:
        return Combatant(e.name, e.emoji, "foes", dict(e.stats), float(e.stats["hp"]), list(e.abilities),
                         "attack", 1.0, e)

    # -- main loop -----------------------------------------------------------
    def run(self, party, enemies: List[Enemy]) -> BattleReport:
        """party: list of Slime (HP and XP are written back). enemies: list of Enemy templates."""
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
        mine = [self.from_slime(s) for s in party]
        everyone = mine + foes
        log = [f"⚔ Battle begins! {', '.join(c.emoji + c.name for c in mine)}  vs  "
               f"{', '.join(c.emoji + c.name for c in foes)}"]
        rounds = 0
        while rounds < config.ROUND_CAP and self._side_alive(everyone, "party") \
                and self._side_alive(everyone, "foes"):
            rounds += 1
            log.append(f"--- Round {rounds} ---")
            order = sorted((c for c in everyone if c.alive),
                           key=lambda c: (-c.stat("spd"), self.rng.random()))
            for actor in order:
                if not actor.alive:
                    continue
                if not (self._side_alive(everyone, "party") and self._side_alive(everyone, "foes")):
                    break
                self._turn(actor, everyone, log)
        if not self._side_alive(everyone, "foes"):
            winner = "party"
        elif not self._side_alive(everyone, "party"):
            winner = "foes"
        else:
            winner = None
        report = BattleReport(log, winner, rounds)
        log.append({"party": "🏆 Victory!", "foes": "💀 Defeat...", None: "🤝 Draw - everybody is too tired."}[winner])
        self._finish(party, mine, enemies, report)
        return report

    @staticmethod
    def _side_alive(everyone, side) -> bool:
        return any(c.alive and c.side == side and not c.minion for c in everyone)

    # -- one turn ------------------------------------------------------------
    def _turn(self, actor: Combatant, everyone, log) -> None:
        # status tick
        if actor.poison[0] > 0:
            dmg = actor.poison[1]
            actor.hp -= dmg
            actor.poison = (actor.poison[0] - 1, actor.poison[1])
            log.append(f"  ☠ {actor.name} takes {dmg} poison damage.")
            if not actor.alive:
                log.append(f"  {actor.name} is defeated!")
                return
        for k in list(actor.cooldowns):
            actor.cooldowns[k] = max(0, actor.cooldowns[k] - 1)
        allies = [c for c in everyone if c.side == actor.side and c.alive]
        foes = [c for c in everyone if c.side != actor.side and c.alive]
        ability = self.choose_ability(actor, allies, foes)
        targets = self.choose_targets(actor, ability, allies, foes)
        if not targets:
            return
        KIND_HANDLERS[ability.kind](self, actor, ability, targets, everyone, log)
        if ability.cooldown:
            actor.cooldowns[ability.key] = ability.cooldown
        if actor.guard > 0 and ability.kind != "guard":
            actor.guard -= 1
        for c in targets:
            if not c.alive and c.side != actor.side:
                log.append(f"  {c.emoji}{c.name} is defeated!")

    # -- AI ------------------------------------------------------------------
    def choose_ability(self, actor, allies, foes) -> Ability:
        ready = [get_ability(k) for k in actor.abilities if actor.cooldowns.get(k, 0) == 0]
        offense = [a for a in ready if a.kind in ("damage", "drain", "poison")]
        summons = [a for a in ready if a.kind == "summon"]
        heals = [a for a in ready if a.kind == "heal"]
        guards = [a for a in ready if a.kind == "guard"]
        hurt = [c for c in allies if c.hp < c.max_hp * 0.6]
        stance = actor.behavior

        if stance == "heal" and hurt and heals:
            return max(heals, key=lambda a: a.power * (2 if a.target == "all_allies" and len(hurt) > 1 else 1))
        if stance == "defend":
            low = actor.hp < actor.max_hp * 0.5 or any(c.hp < c.max_hp * 0.4 for c in allies)
            if low and guards:
                return guards[0]
            if low and actor.guard == 0:
                return get_ability("defend")
        elif stance != "heal" and actor.hp < actor.max_hp * 0.3 and heals:
            return heals[0]          # panic-heal regardless of stance
        if summons and not any(c.minion and c.side == actor.side for c in allies):
            return summons[0]
        if offense:
            def score(a):
                n = len(foes) if a.target == "all_enemies" else 1
                bonus = 1.2 if a.kind == "poison" and not any(f.poison[0] for f in foes) else 1.0
                return a.power * n * bonus
            return max(offense, key=score)
        return get_ability("splat")      # everyone can bonk

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
        real = [c for c in foes if not c.minion] or foes
        return [min(real, key=lambda c: c.hp)]

    # -- aftermath: write HP back, grant XP and loot ---------------------------
    def _finish(self, party, mine, enemies, report: BattleReport) -> None:
        win = report.winner == "party"
        for s, c in zip(party, mine):
            s.hp = max(1, int(c.hp))
            s.needs.add("energy", -10)
            s.needs.add("esteem", 10 if win else -6)
            if not c.alive:
                s.needs.add("safety", -20)
        if win:
            report.xp = sum(e.xp for e in enemies)
            for e in enemies:
                for res, (lo, hi) in e.loot.items():
                    n = self.rng.randint(lo, hi)
                    if n:
                        report.loot[res] = report.loot.get(res, 0) + n
            if self.wallet:
                self.wallet.add_many(report.loot)
            share = max(1, report.xp // max(1, len(party)))
            for s, c in zip(party, mine):
                gain = share if c.alive else share // 2
                s.wins += 1
                report.log.extend(add_xp(s, gain))
            report.log.append(f"Rewards: +{report.xp} XP total, loot: "
                              + (", ".join(f"{v} {k}" for k, v in report.loot.items()) or "none"))


# ---- ability kind handlers -------------------------------------------------------
def _damage_value(bs: BattleSystem, actor, ability, target) -> int:
    raw = ability.power * actor.stat(ability.stat) - 0.5 * target.stat("defense")
    raw = max(1.0, raw) * bs.rng.uniform(0.9, 1.1)
    crit = bs.rng.random() < config.CRIT_CHANCE + (0.1 if actor.behavior == "explore" else 0)
    if crit:
        raw *= config.CRIT_MULT
    if target.guard > 0:
        raw *= config.GUARD_REDUCTION
    return max(1, int(raw)), crit


def _h_damage(bs, actor, ab, targets, everyone, log):
    for t in targets:
        dmg, crit = _damage_value(bs, actor, ab, t)
        t.hp -= dmg
        log.append(f"  {actor.emoji}{actor.name} uses {ab.name} on {t.name}: {dmg} dmg{' (CRIT!)' if crit else ''}"
                   f" [{max(0, int(t.hp))}/{int(t.max_hp)}]")


def _h_drain(bs, actor, ab, targets, everyone, log):
    for t in targets:
        dmg, _ = _damage_value(bs, actor, ab, t)
        t.hp -= dmg
        heal = max(1, dmg // 2)
        actor.hp = min(actor.max_hp, actor.hp + heal)
        log.append(f"  {actor.emoji}{actor.name} siphons {dmg} from {t.name} and heals {heal}.")


def _h_heal(bs, actor, ab, targets, everyone, log):
    for t in targets:
        amt = max(1, int(ab.power * actor.stat(ab.stat) * 1.5 * bs.rng.uniform(0.95, 1.05)))
        before = t.hp
        t.hp = min(t.max_hp, t.hp + amt)
        log.append(f"  💚 {actor.name} uses {ab.name} on {t.name}: +{int(t.hp - before)} HP")


def _h_guard(bs, actor, ab, targets, everyone, log):
    for t in targets:
        t.guard = max(t.guard, ab.duration or 1)
        log.append(f"  🛡 {actor.name} uses {ab.name}: {t.name} takes reduced damage for {t.guard} turn(s).")


def _h_poison(bs, actor, ab, targets, everyone, log):
    for t in targets:
        per = max(1, int(ab.power * actor.stat(ab.stat)))
        t.poison = (ab.duration, per)
        log.append(f"  🧪 {actor.name} uses {ab.name} on {t.name}: poisoned ({per}/turn for {ab.duration}).")


def _h_summon(bs, actor, ab, targets, everyone, log):
    mag = actor.stat(ab.stat)
    pal = Combatant(f"{actor.name}'s Bone Pal", "🦴", actor.side,
                    dict(hp=mag * 2.2 * ab.power + 5, atk=mag * ab.power * 1.2 + 2, defense=2,
                         mag=0, spd=5), mag * 2.2 * ab.power + 5, ["splat"], "attack", 1.0,
                    None, minion=True)
    everyone.append(pal)
    log.append(f"  🦴 {actor.name} raises a Bone Pal!")


KIND_HANDLERS: Dict[str, Callable] = {
    "damage": _h_damage, "drain": _h_drain, "heal": _h_heal,
    "guard": _h_guard, "poison": _h_poison, "summon": _h_summon,
}
