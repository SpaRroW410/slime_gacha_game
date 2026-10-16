"""Battle effects: the status mechanics skills are built from.

An `Ability.fx` is a tuple of effect tuples, applied after the ability's main effect (`kind`). The mechanics:

  ("bleed", turns, pct)            damage over time worth `pct` of the hit, stacks up to 3
  ("stun", chance)                 chance to make the target lose its next turn (bosses resist half the time)
  ("mark", turns, bonus)           the target takes +bonus damage from everybody
  ("buff", name, amount, turns)    +amount to a stat (atk mag defense spd: multiplicative) or a combat mod (crit_rate,
  ("debuff", name, amount, turns)  crit_dmg, evasion, guard, resist, spell_power, lifesteal, regen: additive); debuff = minus
  ("rewrite", stat, value, turns)  the target's stat is *set* to value for a while (Edit Source)
  ("shield", mult)                 absorb damage worth mult x power x the caster's stat
  ("cleanse",)                     remove poison, bleed, stun and debuffs from the targets
  ("strip",)                       remove buffs, shields and stances from every foe (Debug)
  ("revive", frac)                 a fallen ally stands again with frac of its HP
  ("raise",)                       a fallen body (either side) returns as the caster's minion
  ("tithe",)                       sacrifice one of the caster's minions to heal the whole party
  ("untarget", turns)              cannot be targeted
  ("undying", turns)               HP cannot drop below 1
  ("counter", turns, power)        strike back when hit
  ("oath", amount)                 +amount attack while below 30% HP, for the rest of the fight
  ("extra_turn",)                  the caster acts again at once
  ("delay", turns)                 the main effect lands this many rounds later
  ("pierce", what, frac)           ignore frac of the target's "def", "guard" or "resist"
  ("execute", threshold, mult)     x mult damage to a target below threshold of its max HP
  ("crit",) / ("first_strike",)    always crit / crit a target that has not acted this round
  ("nomiss",)                      cannot be dodged
  ("overheal",)                    healing beyond full HP becomes a shield
  ("spread",)                      poison also lands on every other foe
  ("copy",)                        use the last skill a foe used
  ("chorus", ability_key)          the caster's classmates in the party also use that ability
  ("hits", n)                      the damage is dealt as n separate hits (each can crit)
  ("prism",)                       every hit lands with a random basic element
  ("terrain_boost", bonus)         +bonus damage on a terrain that has a hazard
  ("stack",)                       poison adds to a poison already running
  ("minion",)                      also raise one weak bone minion if the caster has none
  ("count", n)                     a summon calls n minions instead of one
"""
from dataclasses import replace
from typing import List, Optional

STAT_NAMES = ("atk", "mag", "defense", "spd")
MOD_NAMES = ("crit_rate", "crit_dmg", "evasion", "guard", "resist", "spell_power", "lifesteal", "regen")
SELF_ONLY = ("extra_turn", "oath")


def find(ab, name: str) -> Optional[tuple]:
    for f in ab.fx:
        if f[0] == name:
            return f
    return None


def strip_delay(ab):
    return replace(ab, fx=tuple(f for f in ab.fx if f[0] != "delay"))


# ---- buffs ----------------------------------------------------------------------------------------------------
def add_buff(c, name: str, amount: float, turns: int) -> None:
    kind = "stat" if name in STAT_NAMES else "mod"
    if kind == "mod":
        c.mods[name] = c.mods.get(name, 0.0) + amount
    c.buffs.append(dict(kind=kind, name=name, amount=amount, turns=turns))


def _expire(c, b: dict) -> None:
    if b["kind"] == "mod":
        c.mods[b["name"]] = c.mods.get(b["name"], 0.0) - b["amount"]


def stat_factor(c, name: str) -> float:
    return max(0.1, 1.0 + sum(b["amount"] for b in c.buffs if b["kind"] == "stat" and b["name"] == name))


def _has_bad(c) -> bool:
    return bool(c.poison[0] > 0 or c.bleed or c.stun or any(b["amount"] < 0 for b in c.buffs) or c.stat_set)


def _has_good(c) -> bool:
    return bool(c.shield > 0 or c.counter[0] > 0 or c.undying > 0 or c.untarget > 0
                or any(b["amount"] > 0 for b in c.buffs))


# ---- the turn tick --------------------------------------------------------------------------------------------
def tick(c, log: List[str]) -> str:
    """Start of c's turn: bleed hurts, timers run down. Returns "dead", "skip" (stunned) or ""."""
    if c.bleed:
        dmg = sum(d for _, d in c.bleed)
        c.hurt(dmg)
        c.bleed = [(t - 1, d) for t, d in c.bleed if t - 1 > 0]
        log.append(f"  🩸 {c.name} bleeds for {dmg}.")
        if not c.alive:
            log.append(f"  {c.name} is defeated!")
            return "dead"
    if c.marked[0] > 0:
        c.marked = (c.marked[0] - 1, c.marked[1])
    if c.untarget > 0:
        c.untarget -= 1
    if c.undying > 0:
        c.undying -= 1
    if c.counter[0] > 0:
        c.counter = (c.counter[0] - 1, c.counter[1])
    for b in list(c.buffs):
        b["turns"] -= 1
        if b["turns"] <= 0:
            _expire(c, b)
            c.buffs.remove(b)
    for k in list(c.stat_set):
        v, t = c.stat_set[k]
        if t - 1 <= 0:
            del c.stat_set[k]
        else:
            c.stat_set[k] = (v, t - 1)
    if c.stun > 0:
        c.stun -= 1
        log.append(f"  💫 {c.emoji}{c.name} is stunned and loses the turn!")
        return "skip"
    return ""


def statuses(c) -> List[str]:
    """Short labels for the battle view."""
    out = []
    if c.shield > 0:
        out.append(f"🔰{int(c.shield)}")
    if c.stun:
        out.append("💫")
    if c.bleed:
        out.append(f"🩸{len(c.bleed)}")
    if c.marked[0] > 0:
        out.append("🎯")
    if c.untarget:
        out.append("🫥")
    if c.undying:
        out.append("♾")
    if c.counter[0] > 0:
        out.append("↩")
    for b in c.buffs:
        out.append(("⬆" if b["amount"] > 0 else "⬇") + b["name"][:3])
    if c.stat_set:
        out.append("✎")
    return out


# ---- applying an ability's effects -------------------------------------------------------------------------------
def apply(bs, actor, ab, targets, everyone, log, cast_stat) -> None:
    """Run every effect of `ab` (after its main effect). `cast_stat` is the caster's scaling stat value."""
    from .battle import Combatant          # local: battle imports this module
    foes = [c for c in everyone if c.side != actor.side and c.alive]
    allies = [c for c in everyone if c.side == actor.side and c.alive]
    for f in ab.fx:
        kind = f[0]
        if kind in SELF_ONLY:
            if kind == "extra_turn":
                actor.extra_turns += 1
                log.append(f"  ⚡ {actor.name} is ready to act again!")
            elif kind == "oath":
                actor.oath = f[1]
                log.append(f"  🔥 {actor.name} swears an oath: +{f[1]:.0%} attack while badly hurt.")
            continue
        if kind == "bleed":
            for t in targets:
                if t.alive and t.side != actor.side:
                    hit = bs.last_hits.get(id(t)) or max(1, int(ab.power * cast_stat))
                    t.bleed = (t.bleed + [(f[1], max(1, int(hit * f[2])))])[-3:]
                    log.append(f"  🩸 {t.name} is bleeding.")
        elif kind == "stun":
            for t in targets:
                if t.alive and t.side != actor.side:
                    chance = f[1] * (0.5 if getattr(t.source, "boss", False) else 1.0)
                    if bs.rng.random() < chance:
                        t.stun = 1
                        log.append(f"  💫 {t.name} is stunned!")
        elif kind == "mark":
            for t in targets:
                if t.alive:
                    t.marked = (f[1], f[2])
                    log.append(f"  🎯 {t.name} is marked: +{f[2]:.0%} damage taken for {f[1]} turns.")
        elif kind in ("buff", "debuff"):
            amt = abs(f[2]) * (1 if kind == "buff" else -1)
            for t in targets:
                if t.alive:
                    add_buff(t, f[1], amt, f[3])
            log.append(f"  {'⬆' if amt > 0 else '⬇'} {f[1]} {amt:+.0%} on " +
                       (targets[0].name if len(targets) == 1 else f"{len(targets)} targets") + f" for {f[3]} turns.")
        elif kind == "rewrite":
            for t in targets:
                if t.alive:
                    t.stat_set[f[1]] = (f[2], f[3])
                    log.append(f"  ✎ {actor.name} rewrites {t.name}'s {f[1]} to {f[2]} for {f[3]} turns!")
        elif kind == "shield":
            for t in targets:
                if t.alive:
                    amt = max(1, int(f[1] * ab.power * cast_stat))
                    t.shield += amt
                    log.append(f"  🔰 {t.name} gains a {amt} point shield.")
        elif kind == "cleanse":
            for t in targets:
                t.poison, t.bleed, t.stun = (0, 0), [], 0
                t.stat_set = {}
                for b in [b for b in t.buffs if b["amount"] < 0]:
                    _expire(t, b)
                    t.buffs.remove(b)
            log.append(f"  ✨ {actor.name}'s {ab.name} cleanses {len(targets)} target(s).")
        elif kind == "strip":
            for t in foes:
                for b in [b for b in t.buffs if b["amount"] > 0]:
                    _expire(t, b)
                    t.buffs.remove(b)
                t.shield, t.counter, t.undying, t.untarget = 0.0, (0, 0.0), 0, 0
            log.append(f"  🧹 {actor.name} strips every foe's buffs and shields.")
        elif kind == "revive":
            fallen = [c for c in everyone if c.side == actor.side and not c.alive and not c.minion and not c.yielded]
            if not fallen:
                log.append(f"  {actor.name}'s {ab.name} finds nobody to revive.")
            else:
                c = max(fallen, key=lambda x: x.max_hp)
                c.hp = max(1.0, c.max_hp * f[1])
                c.poison, c.bleed, c.stun = (0, 0), [], 0
                log.append(f"  🌟 {c.emoji}{c.name} rises again with {int(c.hp)} HP!")
        elif kind == "raise":
            fallen = [c for c in everyone if not c.alive and not c.minion and not c.yielded]
            if not fallen:
                log.append(f"  {actor.name} finds no body to raise.")
            else:
                c = max(fallen, key=lambda x: x.max_hp)
                everyone.remove(c)
                everyone.append(Combatant(f"{actor.name}'s thrall ({c.name})", "💀", actor.side,
                                          dict(hp=c.max_hp * 0.5, atk=max(c.stats["atk"], c.stats["mag"]) * 0.6,
                                               defense=c.stats["defense"] * 0.5, mag=0, spd=c.stats["spd"]),
                                          c.max_hp * 0.5, ["splat"], "attack", 1.0, None, minion=True))
                log.append(f"  💀 {c.name} is raised as {actor.name}'s thrall!")
        elif kind == "tithe":
            pals = [c for c in allies if c.minion]
            if not pals:
                log.append(f"  {actor.name} has no minion to sacrifice.")
            else:
                pal = pals[0]
                heal = int(pal.max_hp * (f[1] if len(f) > 1 else 1.0))
                pal.hp = 0
                for c in allies:
                    if not c.minion and c.alive:
                        c.hp = min(c.max_hp, c.hp + heal)
                log.append(f"  🩸 {actor.name} sacrifices {pal.name}: the party heals {heal}.")
        elif kind == "untarget":
            for t in targets:
                t.untarget = f[1]
            log.append(f"  🫥 {targets[0].name} slips out of sight for {f[1]} turns.")
        elif kind == "undying":
            for t in targets:
                t.undying = f[1]
            log.append(f"  ♾ {targets[0].name} refuses to fall for {f[1]} turns.")
        elif kind == "counter":
            for t in targets:
                t.counter = (f[1], f[2])
            log.append(f"  ↩ {targets[0].name} takes a counter stance for {f[1]} turns.")
        elif kind == "minion":
            if not any(c.minion and c.side == actor.side and c.alive for c in everyone):
                from .abilities import Ability
                from .battle import _h_summon
                _h_summon(bs, actor, Ability("_pal", "Bone Pal", "summon", 0.4, "mag", "self"), [actor], everyone, log)
        elif kind == "spread" and ab.kind == "poison":
            for t in targets:
                for o in foes:
                    if o is not t and o.alive and o.poison[0] < t.poison[0]:
                        o.poison = (t.poison[0], max(1, int(t.poison[1] * 0.6)))
            log.append("  🧪 The poison spreads to every foe.")
        elif kind == "chorus":
            from .abilities import get_ability
            sub = get_ability(f[1])
            mates = [c for c in allies if c is not actor and not c.minion and c.source is not None
                     and getattr(c.source, "archetype", None) == getattr(actor.source, "archetype", "?")]
            for c in mates:
                foes_now = [x for x in everyone if x.side != c.side and x.alive]
                if foes_now:
                    from .battle import KIND_HANDLERS
                    KIND_HANDLERS[sub.kind](bs, c, sub, bs.choose_targets(c, sub, allies, foes_now), everyone, log)
