"""BattleSystem: deterministic (seeded) turn-based auto-combat.

Flow: build Combatants -> loop rounds (speed order) -> each actor's AI picks an ability from its
stance -> KIND_HANDLERS resolve it -> BattleReport (log + rewards). The UI only prints the report.
Add a new ability *kind* by writing a handler and adding it to KIND_HANDLERS.
"""
import random
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional

from . import config
from .abilities import Ability, get_ability
from . import elements, items as items_mod, terrain as terrain_mod
from . import sparring
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


ENEMIES: "Registry[Enemy]" = Registry("enemy")


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
    casts: Dict[str, int] = field(default_factory=dict)     # elemental casts this battle (mastery xp)
    style: Dict[str, int] = field(default_factory=dict)     # fighting-style levels (sparring.py)
    morale: float = 60.0
    nonlethal: bool = False         # sparring: reaching 1 HP means yielding, not dying
    yielded: bool = False
    mods: Dict[str, object] = field(default_factory=dict)   # relic mods: crit_rate, crit_dmg, lifesteal, elem

    @property
    def alive(self) -> bool:
        return self.hp > 0 and not self.yielded

    def hurt(self, amount: float) -> None:
        self.hp -= amount
        if self.nonlethal and self.hp <= 1:
            self.hp, self.yielded = 1, True

    @property
    def max_hp(self) -> float:
        return self.stats["hp"]

    def stat(self, name: str) -> float:
        v = self.stats[name]
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
        return Combatant(s.name, s.arch.emoji, side, dict(s.max_stats()), float(s.hp),
                         s.known_abilities(), s.behavior, s.power_multiplier() * morale_f * synergy, s,
                         mastery={b: elements.basic_level(s, b) for b in s.attuned},
                         style=sparring.style_levels(s), morale=s.morale, mods=items_mod.battle_mods(s))

    @staticmethod
    def from_enemy(e: Enemy) -> Combatant:
        return Combatant(e.name, e.emoji, "foes", dict(e.stats), float(e.stats["hp"]), list(e.abilities),
                         "attack", 1.0, e, element=e.element)

    # -- main loop -----------------------------------------------------------
    def run(self, party, enemies: List[Enemy], permadeath: bool = True, split_xp: bool = True,
            xp_mult: float = 1.0, synergy: float = 1.0, terrain=None) -> BattleReport:
        """party: list of Slime (HP and XP are written back). enemies: list of Enemy templates.
        permadeath=False knocks slimes out at 1 HP instead of killing them (training dungeons).
        split_xp=False gives every survivor the full wave XP instead of an equal share."""
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
        self.terrain = terrain
        log = [f"⚔ Battle begins! {', '.join(c.emoji + c.name for c in mine)}  vs  "
               f"{', '.join(c.emoji + c.name for c in foes)}"]
        if terrain:
            log.append(f"🌍 {terrain.emoji} {terrain.name}: {terrain_mod.describe(terrain)}")
        try:
            rounds, winner = self._simulate(everyone, log)
        finally:
            self.terrain = None
        report = BattleReport(log, winner, rounds)
        log.append({"party": "🏆 Victory!", "foes": "💀 Defeat...", None: "🤝 Draw - everybody is too tired."}[winner])
        self._finish(party, mine, enemies, report, permadeath, split_xp, xp_mult)
        return report

    def _simulate(self, everyone, log, cap: int = config.ROUND_CAP):
        """Round loop shared by battles and duels. Returns (rounds, winner)."""
        rounds = 0
        while rounds < cap and self._side_alive(everyone, "party") \
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
            self._hazard(everyone, log)
        if not self._side_alive(everyone, "foes"):
            winner = "party"
        elif not self._side_alive(everyone, "party"):
            winner = "foes"
        else:
            winner = None
        return rounds, winner

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
        log = [f"🥊 Sparring match: {ca.emoji}{ca.name} vs {cb.emoji}{cb.name}"]
        self.terrain = None
        rounds, winner = self._simulate([ca, cb], log, config.DUEL_ROUND_CAP)
        if winner is None:                      # round cap: the healthier slime takes it on points
            winner = "party" if ca.hp / ca.max_hp >= cb.hp / cb.max_hp else "foes"
        log.append(f"🏅 {(ca if winner == 'party' else cb).name} wins the spar!")
        for s, c in ((a, ca), (b, cb)):
            s.hp = max(1, int(c.hp))
            s.needs.add("energy", -8)
        rep = BattleReport(log, winner, rounds)
        rep.winner_slime = a if winner == "party" else b
        return rep

    @staticmethod
    def _side_alive(everyone, side) -> bool:
        return any(c.alive and c.side == side and not c.minion for c in everyone)

    # -- one turn ------------------------------------------------------------
    def _turn(self, actor: Combatant, everyone, log) -> None:
        # status tick
        if actor.poison[0] > 0:
            dmg = actor.poison[1]
            actor.hurt(dmg)
            actor.poison = (actor.poison[0] - 1, actor.poison[1])
            log.append(f"  ☠ {actor.name} takes {dmg} poison damage.")
            if not actor.alive:
                log.append(f"  {actor.name} is defeated!")
                return
        if actor.morale < config.MORALE_BROKEN and actor.side == "party" and \
                self.rng.random() < config.MORALE_FREEZE_CHANCE:
            log.append(f"  😰 {actor.name} freezes - morale is broken!")
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
        if ability.element:
            actor.casts[ability.element] = actor.casts.get(ability.element, 0) + 1
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
                weakest = min(foes, key=lambda f: f.hp)
                return (a.power * n * bonus * elements.effectiveness(a.element, weakest.element)
                        * _mastery_mult(actor, a))
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
    def _finish(self, party, mine, enemies, report: BattleReport, permadeath: bool = True,
                split_xp: bool = True, xp_mult: float = 1.0) -> None:
        win = report.winner == "party"
        survivors = []
        for s, c in zip(party, mine):
            s.hp = max(0, int(c.hp))
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
                    if b in s.attuned and elements.mastery_cap(s):
                        top = config.MASTERY_XP[elements.mastery_cap(s) - 1]
                        s.mastery_xp[b] = min(top, s.mastery_xp.get(b, 0) + n * config.MASTERY_PER_CAST_XP)
            s.needs.add("energy", -10)
            s.needs.add("esteem", 10 if win else -6)
            survivors.append(s)
        for name in report.deaths:
            report.log.append(f"☠ {name} has fallen and will not rise again.")
        if win:
            report.xp = int(sum(e.xp for e in enemies) * xp_mult)
            for e in enemies:
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
                report.log.extend(add_xp(s, share))
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
    raw = ability.power * _cast_stat(actor, ability) * _mastery_mult(actor, ability) * _terrain_mult(bs, ability) \
        - 0.5 * target.stat("defense")
    eff = elements.effectiveness(ability.element, target.element)
    raw = max(1.0, raw) * bs.rng.uniform(0.9, 1.1) * eff * _style_attack(actor, ability)
    raw *= max(0.6, 1 - config.STYLE_SWORD_GUARD * target.style.get("sword", 0))       # parrying
    crit = bs.rng.random() < (config.CRIT_CHANCE + (0.1 if actor.behavior == "explore" else 0)
                              + config.STYLE_ARCHERY_CRIT * actor.style.get("archery", 0)
                              + (bs.terrain.crit if bs.terrain else 0.0) + actor.mods.get("crit_rate", 0.0))
    if ability.element:
        raw *= 1 + actor.mods.get("elem", {}).get(ability.element, 0.0)
    if crit:
        raw *= config.CRIT_MULT + actor.mods.get("crit_dmg", 0.0)
    if target.guard > 0:
        raw *= config.GUARD_REDUCTION
    return max(1, int(raw)), crit, eff


def _eff_tag(eff: float) -> str:
    return " (WEAK!)" if eff > 1 else " (resisted)" if eff < 1 else ""


def _h_damage(bs, actor, ab, targets, everyone, log):
    for t in targets:
        dmg, crit, eff = _damage_value(bs, actor, ab, t)
        t.hurt(dmg)
        log.append(f"  {actor.emoji}{actor.name} uses {ab.name} on {t.name}: {dmg} dmg{' (CRIT!)' if crit else ''}{_eff_tag(eff)}"
                   f" [{max(0, int(t.hp))}/{int(t.max_hp)}]")
        ls = actor.mods.get("lifesteal", 0.0)
        if ls and actor.alive:
            actor.hp = min(actor.max_hp, actor.hp + max(1, int(dmg * ls)))


def _h_drain(bs, actor, ab, targets, everyone, log):
    for t in targets:
        dmg, _, _ = _damage_value(bs, actor, ab, t)
        t.hurt(dmg)
        heal = max(1, dmg // 2)
        actor.hp = min(actor.max_hp, actor.hp + heal)
        log.append(f"  {actor.emoji}{actor.name} siphons {dmg} from {t.name} and heals {heal}.")


def _h_heal(bs, actor, ab, targets, everyone, log):
    for t in targets:
        amt = max(1, int(ab.power * _cast_stat(actor, ab) * 1.5 * bs.rng.uniform(0.95, 1.05)
                         * _mastery_mult(actor, ab) * _style_attack(actor, ab) * _terrain_mult(bs, ab)))
        before = t.hp
        t.hp = min(t.max_hp, t.hp + amt)
        log.append(f"  💚 {actor.name} uses {ab.name} on {t.name}: +{int(t.hp - before)} HP")


def _h_guard(bs, actor, ab, targets, everyone, log):
    for t in targets:
        t.guard = max(t.guard, ab.duration or 1)
        log.append(f"  🛡 {actor.name} uses {ab.name}: {t.name} takes reduced damage for {t.guard} turn(s).")


def _h_poison(bs, actor, ab, targets, everyone, log):
    for t in targets:
        per = max(1, int(ab.power * _cast_stat(actor, ab) * _mastery_mult(actor, ab) * _terrain_mult(bs, ab)))
        t.poison = (ab.duration, per)
        log.append(f"  🧪 {actor.name} uses {ab.name} on {t.name}: poisoned ({per}/turn for {ab.duration}).")


def _h_summon(bs, actor, ab, targets, everyone, log):
    mag = actor.stat(ab.stat)
    emoji, _, mname = (ab.minion or "🦴 Bone Pal").partition(" ")
    pal = Combatant(f"{actor.name}'s {mname}", emoji, actor.side,
                    dict(hp=mag * 2.2 * ab.power + 5, atk=mag * ab.power * 1.2 + 2, defense=2,
                         mag=0, spd=5), mag * 2.2 * ab.power + 5, ["splat"], "attack", 1.0,
                    None, minion=True)
    everyone.append(pal)
    log.append(f"  {emoji} {actor.name} calls up a {mname}!")


KIND_HANDLERS: Dict[str, Callable] = {
    "damage": _h_damage, "drain": _h_drain, "heal": _h_heal,
    "guard": _h_guard, "poison": _h_poison, "summon": _h_summon,
}
