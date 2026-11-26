"""Combat resources: three POOLS and ACTION POINTS.

Pools (what a skill burns):
* STAMINA - physical skills (attack, defense or speed based, no element). Persists between fights (attributes.py).
* MANA    - magic without an element: heals, wards, curses, summons, Explosive Brew ... Persists between fights.
* NATURE  - any skill that carries an element. Drawn from the surroundings: every fight starts with it half full.
The plain bonk (Splat) and Defend are free. A pool refills a little every round and more on a turn spent Defending.

Action points (how much a fighter does in one turn): every turn brings AP_PER_TURN points, unspent ones are saved up
to AP_MAX. A plain skill costs a whole turn's points, a heavy one more, a big area skill two turns' worth, so a turn
can hold a light skill and a Defend, two plain attacks from saved points, or one big spell that was saved for.
Cooldowns are cut to the minimum: a strong skill can't be repeated in the same turn; once-a-fight skills stay so.
Monsters follow the same rules (a flat 100 in each pool).
"""
from . import config

POOLS = ("stamina", "mana", "nature")
ICON = {"stamina": "⚡", "mana": "🔷", "nature": "🍃"}
FREE = ("splat", "defend")                 # always affordable: the fallbacks when every pool is dry

# pool sizes at level 1 for a 1-star common, before rarity, stars and level (stamina: attributes.STAMINA_BASE)
MANA_BASE = dict(barbarian=40, rogue=50, ranger=55, medic=120, mage=130, necromancer=120,
                 bard=110, paladin=70, alchemist=120, druid=100)
NATURE_BASE = dict(barbarian=55, rogue=55, ranger=75, medic=70, mage=95, necromancer=70,
                   bard=75, paladin=60, alchemist=85, druid=125)


def pool_of(ab) -> str:
    """Which pool a skill burns ('' = free)."""
    if ab.key in FREE:
        return ""
    if ab.element:
        return "nature"
    if ab.stat == "mag" or ab.kind in ("heal", "summon"):
        return "mana"
    return "stamina"


def ap_cost(ab) -> int:
    """Action points a skill needs: a plain skill is one turn's worth, heavier ones more, a big area skill two turns."""
    if ab.key == "defend":
        return config.AP_DEFEND
    if ab.key == "splat":
        return config.AP_PER_TURN
    cd = ab.cooldown
    area = ab.target.startswith("all_")
    if ab.kind in ("utility", "guard"):               # buffs, wards, marks: quick to do, so a turn can hold one and a blow
        names = {f[0] for f in ab.fx}
        if names & {"revive", "raise"}:
            return 5
        base = 2 if ab.target == "self" else 4 if area else 3     # a buff on oneself is quick, on a friend or everyone less so
        return min(config.AP_MAX, base + (1 if cd >= 6 else 0))
    if cd >= 6:                                       # once-a-fight and other rare capstones
        return config.AP_MAX
    ap = 3 if cd <= 1 else 4 if cd <= 3 else 5
    if area:
        ap += 1
    return max(1, min(config.AP_MAX, ap))


def pool_cost(ab) -> float:
    """Pool units a skill burns (before the fighter's level scale)."""
    if not pool_of(ab):
        return 0.0
    return float(config.POOL_PER_AP * ap_cost(ab) * (config.HEAL_POOL_MULT if ab.kind == "heal" else 1.0))


def cooldown(ab) -> int:
    """Cooldowns cut to the minimum now that AP paces the big skills: not twice in one turn, once-a-fight stays."""
    cd = ab.cooldown
    if cd <= 1:
        return 0
    if cd <= 5:
        return 1
    return cd if cd >= 99 else cd - 4


def level_scale(slime) -> float:
    """Pools and costs both grow with level (as stamina always has), so the number of casts stays a class trait."""
    return 1 + config.POOL_LEVEL_GROWTH * (config.stat_level(slime.level) - 1)


def rank_mult(slime) -> float:
    return 0.6 + 0.4 * config.RARITY_STAT_MULT[slime.rarity] * config.STAR_STAT_MULT[slime.stars - 1]


def _buff(slime, kind: str) -> float:
    return sum(b["bonus"] for b in getattr(slime, "buffs", []) if b["kind"] == kind)


def max_mana(slime) -> float:
    return round(MANA_BASE.get(slime.archetype, 80) * rank_mult(slime) * level_scale(slime) * (1 + _buff(slime, "arcane")), 1)


def max_nature(slime) -> float:
    top = max([0] + _mastery_levels(slime))
    return round(NATURE_BASE.get(slime.archetype, 70) * rank_mult(slime) * level_scale(slime)
                 * (1 + config.NATURE_PER_MASTERY * top) * (1 + _buff(slime, "renewal")), 1)


def _mastery_levels(slime):
    from . import elements
    return [elements.basic_level(slime, b) for b in getattr(slime, "attuned", [])]


def describe(ab) -> str:
    p = pool_of(ab)
    return f"{ap_cost(ab)} AP" + (f", {ICON[p]} {int(pool_cost(ab))} {p}" if p else ", free")
