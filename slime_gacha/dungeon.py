"""Dungeons: floor plans for the Hollow Descent (50 floors) and daily themes for the Gloop Pit.

Every floor has a TERRAIN (valleys, dunes, islands, volcano ash, swamp ...) and a MIXED wave of monsters
(goblins riding with direwolves, orcs and ogres, undead and scarabs ...). Floors are generated once per dungeon
seed, in order, and never repeat a terrain on consecutive floors nor a wave recently seen - so scouts can report
what is really down there, every party meets the same floor, and no two neighbouring floors feel alike.
Every 5th floor is a hand-built boss in a lair of its own (bestiary.BOSSES).

The Gloop Pit changes with the DAY: each game day has a terrain and two featured monster families (never
yesterday's), and every run inside a day draws a different mix.
"""
import random
from collections import Counter
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple

from . import bestiary, config, elements, terrain as terr
from .battle import Enemy
from .bestiary import MAX_FLOOR, Monster

# ---- floors & segments -----------------------------------------------------------------------------
PATTERNS = ("swarm", "warband", "rabble", "siege", "ambush")
SEGMENT_TERRAINS: List[Tuple[str, ...]] = [
    ("mossy_valley", "echo_valley", "glowworm_grotto", "fern_gorge"),                     # 1-5
    ("ember_valley", "echo_valley", "fungal_caverns", "oasis_flats", "mossy_valley"),      # 6-10
    ("coral_isles", "floating_isles", "dune_sea", "mangrove_maze", "tidal_flats"),         # 11-15
    ("mire", "red_mesa", "fungal_caverns", "crystal_vault", "fern_gorge"),                 # 16-20
    ("dune_sea", "glass_desert", "red_mesa", "oasis_flats", "bone_barrens"),               # 21-25
    ("coral_isles", "tidal_flats", "mangrove_maze", "floating_isles", "mire"),             # 26-30
    ("frozen_tundra", "glacier_hall", "sky_cliffs", "crystal_canyon", "crystal_vault"),    # 31-35
    ("sky_cliffs", "thunder_peaks", "storm_plains", "golden_steppe", "echo_valley"),       # 36-40
    ("bone_barrens", "ruined_crypt", "ashlands", "glass_desert", "mire"),                  # 41-45
    ("ashlands", "magma_shelf", "hollow_halls", "ruined_crypt", "bone_barrens"),           # 46-50
]


def is_boss_floor(floor: int) -> bool:
    return floor % config.MAIN_BOSS_EVERY == 0


def segment_of(floor: int) -> int:
    return (floor - 1) // config.MAIN_BOSS_EVERY


def segment_floors(seg: int) -> range:
    return range(seg * config.MAIN_BOSS_EVERY + 1, (seg + 1) * config.MAIN_BOSS_EVERY + 1)


@dataclass
class FloorInfo:
    floor: int
    terrain: terr.Terrain
    enemies: List[Enemy]
    pattern: str
    title: str
    signature: tuple
    boss: bool = False
    affinity: str = ""             # element an elemental floor favours ("" = an ordinary floor)


def _pool(kind: str, floor: int, families: Optional[Tuple[str, ...]] = None, need: int = 5) -> List[Monster]:
    """Monsters of a terrain kind near the floor; widen the band until there is enough variety."""
    for slack in (0, 4, 8, 14, 24, 40):
        pool = bestiary.pool_for(kind, floor, families, slack)
        if len(pool) >= need and len({m.family for m in pool}) >= (1 if families else 2):
            return pool
    return bestiary.pool_for(kind, floor, families, 60) or list(bestiary.MONSTERS)


def _pick(rng: random.Random, cands: List[Monster], fallback: List[Monster]) -> Monster:
    return rng.choice(cands or fallback)


def _fill(rng: random.Random, cands: List[Monster], fallback: List[Monster], n: int) -> List[Tuple[Monster, float]]:
    """n followers drawn from up to two different monster types (so a swarm still has some variety)."""
    base = cands or fallback
    kinds = rng.sample(base, min(2, len(base)))
    return [(kinds[i % len(kinds)], 1.0) for i in range(n)]


def _compose(rng: random.Random, floor: int, pool: List[Monster], size: int) -> Tuple[str, List[Tuple[Monster, float]]]:
    """A wave of `size` monsters as (monster, elite factor) using one of five patterns."""
    fams = sorted({m.family for m in pool})
    role_in = lambda ms, roles: [m for m in ms if m.role in roles]
    pattern = rng.choice(PATTERNS)
    out: List[Tuple[Monster, float]] = []
    if pattern == "swarm":
        fam = rng.choice(fams)
        mine = [m for m in pool if m.family == fam]
        leaders = max(1, size // 4)
        for i in range(leaders):
            out.append((_pick(rng, role_in(mine, LEAD), pool), 1.25 if i == 0 else 1.0))
        out += _fill(rng, role_in(mine, FOLLOW) or mine, pool, size - len(out))
    elif pattern == "warband":
        a = rng.choice(fams)
        b = rng.choice([f for f in fams if f != a] or fams)
        pa = [m for m in pool if m.family == a]
        pb = [m for m in pool if m.family == b]
        for i in range(max(1, size // 3)):
            out.append((_pick(rng, role_in(pa, LEAD), pool), 1.25 if i == 0 else 1.0))
        out += _fill(rng, role_in(pb, FOLLOW) or pb, pool, size - len(out))
    elif pattern == "rabble":
        picks = rng.sample(pool, min(len(pool), max(3, min(5, size))))
        for i in range(size):
            out.append((picks[i % len(picks)], 1.0))
        out[0] = (out[0][0], 1.15)
    elif pattern == "siege":
        out.append((_pick(rng, role_in(pool, ("tank", "brute")), pool), 1.25))
        out.append((_pick(rng, role_in(pool, ("caster", "support")), pool), 1.0))
        out += _fill(rng, role_in(pool, FOLLOW), pool, size - len(out))
    else:  # ambush
        out.append((_pick(rng, role_in(pool, ("caster", "support")), pool), 1.0))
        out += _fill(rng, role_in(pool, ("hunter", "skirmisher")), pool, size - len(out))
    return pattern, out[:size]


LEAD, FOLLOW = bestiary.LEADERS, bestiary.FOLLOWERS


def _family_name(key: str) -> str:
    return {"direwolf": "Direwolf", "undead": "Undead"}.get(key, key.capitalize())


_PLURALS = {"direwolf": "Direwolves", "undead": "Undead", "hollow": "Hollow Guardians", "critter": "Critters",
            "goblin": "Goblins", "orc": "Orcs", "ogre": "Ogres", "troll": "Trolls", "beast": "Beasts",
            "scarab": "Scarabs", "spirit": "Spirits", "sea": "Sea Monsters", "giant": "Giants", "golem": "Golems",
            "imp": "Imps", "elemental": "Elementals", "dragonkin": "Dragonkin", "swamp": "Swamp Dwellers",
            "aerial": "Flyers", "fungus": "Fungi"}


def family_plural(key: str) -> str:
    return _PLURALS.get(key, key.capitalize() + "s")


def _title(t: terr.Terrain, pattern: str, enemies: List[Enemy]) -> str:
    fams = [f for f, _ in Counter(e.family for e in enemies if e.family).most_common(2)]
    who = " & ".join(_family_name(f) for f in fams) or "Hollow"
    return f"{t.name} - {who} {pattern}"


_PLANS: Dict[Tuple[int, int], List[FloorInfo]] = {}


def threat(enemies: List[Enemy]) -> float:
    """(sum of HP) x (sum of damage): what a party has to chew through times what it must survive."""
    return sum(e.stats["hp"] for e in enemies) * sum(max(e.stats["atk"], e.stats["mag"]) for e in enemies)


def threat_ratio(enemies: List[Enemy], floor: int, size: int) -> float:
    """Threat relative to the target curve for this floor (1.0 = on the curve)."""
    return threat(enemies) / (config.FLOOR_THREAT_TARGET * bestiary.growth(floor) ** 2 * (size / 5.0) ** 2)


def _smooth(enemies: List[Enemy], floor: int, size: int, boss: bool) -> List[Enemy]:
    """Pull floors whose total threat is far from the curve back into a band (monster families differ wildly: five
    stone giants were several times a normal floor). Variety is kept inside the band."""
    lo, hi = config.BOSS_THREAT_BAND if boss else config.FLOOR_THREAT_BAND
    ratio = threat_ratio(enemies, floor, size)
    wanted = min(hi, max(lo, ratio))
    if abs(wanted - ratio) < 1e-9:
        return enemies
    s = (wanted / ratio) ** 0.5                       # HP and damage each move by the square root of the correction
    out = []
    for e in enemies:
        st = dict(e.stats)
        st["hp"] = float(max(1, int(st["hp"] * s)))
        for k in ("atk", "mag"):
            st[k] = round(st[k] * s, 1)
        out.append(replace(e, stats=st))
    return out


ELEMENTAL_EVERY, ELEMENTAL_OFFSET = 6, 3          # every 6th floor from floor 3 (3, 9, 21, 27 ...), except boss floors
ELEMENTAL_BOOST, ELEMENTAL_DAMPEN = 1.25, 0.8


def is_elemental_floor(floor: int) -> bool:
    return floor % ELEMENTAL_EVERY == ELEMENTAL_OFFSET and not is_boss_floor(floor)


def _attune(t: terr.Terrain, el: str) -> terr.Terrain:
    """The same ground on an elemental floor: spells of the floor's element hit harder, the element that beats it softer
    - for both sides."""
    foe = next((a for a, d in elements.BEATS.items() if d == el), "")
    boosts = dict(t.boosts)
    boosts[el] = max(boosts.get(el, 1.0), ELEMENTAL_BOOST)
    dampens = dict(t.dampens)
    if foe:
        dampens[foe] = min(dampens.get(foe, 1.0), ELEMENTAL_DAMPEN)
    return replace(t, name=f"{elements.get(el).name} {t.name}", boosts=boosts, dampens=dampens)


def _generate_floors(seed: int, size: int) -> List[FloorInfo]:
    plans: List[FloorInfo] = []
    recent: List[tuple] = []
    prev_terrain = ""
    for f in range(1, MAX_FLOOR + 1):
        boss = bestiary.boss_for(f)
        if boss:
            t = terr.get(boss.terrain)
            enemies = [bestiary.build_boss(boss, f)]
            pool = _pool(t.kind, f, boss.escorts, need=3)
            rng = random.Random(seed * 1000003 + f * 7919 + size)
            for _ in range(2 * (size // 5)):
                enemies.append(bestiary.build_enemy(rng.choice(pool), f))
            enemies = _smooth(enemies, f, size, True)
            sig = (t.key, tuple(sorted(Counter(e.key for e in enemies).items())))
            plans.append(FloorInfo(f, t, enemies, "boss", f"{boss.name}'s lair - {t.name}", sig, True))
            prev_terrain = t.key
            recent = (recent + [sig])[-4:]
            continue
        next_boss = bestiary.boss_for(f + 1)                 # don't arrive at the boss's lair on the same ground
        palette = [k for k in SEGMENT_TERRAINS[segment_of(f)]
                   if k != prev_terrain and not (next_boss and k == next_boss.terrain)]
        best = None
        for attempt in range(40):
            rng = random.Random(seed * 1000003 + f * 7919 + attempt * 104729 + size)
            t = terr.get(rng.choice(palette))
            pool = _pool(t.kind, f)
            affinity = ""
            if is_elemental_floor(f):
                affinity = rng.choice(elements.BASICS)
                kin = [m for m in pool if m.element == affinity or affinity in elements.components(m.element or "")]
                pool = kin if len(kin) >= 2 else pool          # the floor's own creatures lead the waves
            pattern, picks = _compose(rng, f, pool, size)
            enemies = []
            for m, el in picks:
                enemies.append(bestiary.build_enemy(m, f, el))
            sig = (t.key, tuple(sorted(Counter(e.key for e in enemies).items())))
            best = (t, pattern, enemies, sig, affinity)
            if sig not in recent and len({e.key for e in enemies}) >= 2:
                break
        t, pattern, enemies, sig, affinity = best
        enemies = _smooth(enemies, f, size, False)
        shown = _attune(t, affinity) if affinity else t
        plans.append(FloorInfo(f, shown, enemies, pattern, _title(shown, pattern, enemies), sig, False, affinity))
        prev_terrain = t.key
        recent = (recent + [sig])[-4:]
    return plans


def floor_info(seed: int, floor: int, party_size: int) -> FloorInfo:
    if not 1 <= floor <= MAX_FLOOR:
        raise ValueError(f"floor must be 1-{MAX_FLOOR}")
    key = (seed, party_size)
    if key not in _PLANS:
        _PLANS[key] = _generate_floors(seed, party_size)
    return _PLANS[key][floor - 1]


def floor_plan(seed: int, floor: int, party_size: int) -> List[Enemy]:
    """The enemies of a floor are FIXED by the dungeon seed, so scouts report what is really down there."""
    return floor_info(seed, floor, party_size).enemies


# ---- the Gloop Pit: a new theme every day --------------------------------------------------------------------
FAMILIES = sorted({m.family for m in bestiary.MONSTERS})


@dataclass
class PitTheme:
    day: int
    terrain: terr.Terrain
    families: Tuple[str, str]
    title: str


_PIT: Dict[int, List[PitTheme]] = {}


def pit_theme(seed: int, day: int) -> PitTheme:
    """Today's Pit. Deterministic per (seed, day); never the same terrain or featured families as yesterday."""
    days = _PIT.setdefault(seed, [])
    while len(days) <= day:
        d = len(days)
        rng = random.Random(seed * 7777 + d * 131)
        prev = days[-1] if days else None
        terrains = [t for t in terr.TERRAINS if not prev or t.key != prev.terrain.key]
        t = rng.choice(terrains)
        fams = FAMILIES
        while True:
            pair = tuple(sorted(rng.sample(fams, 2)))
            if not prev or set(pair) != set(prev.families):
                break
        title = f"{t.name}: {family_plural(pair[0])} & {family_plural(pair[1])}"
        days.append(PitTheme(d, t, pair, title))
    return days[day]


def grind_level(avg_level: float, depth: int) -> int:
    return max(1, int(round(avg_level)) + depth - 3)


def grind_wave(avg_level: float, depth: int, party_size: int, rng: random.Random,
               theme: Optional[PitTheme] = None) -> List[Enemy]:
    """A Pit wave at (party level + depth - 3). With a theme, the day's featured families dominate and the
    day's terrain supplies the rest; without one, any monster of the level band."""
    target = grind_level(avg_level, depth)
    if theme:
        feat = [m for m in bestiary.MONSTERS if m.family in theme.families]
        pool = [m for m in feat if m.lo - 12 <= target <= m.hi + 12] or \
               [m for m in feat if m.lo - 40 <= target <= m.hi + 40] or feat
        if len(pool) < 3:
            local = _pool(theme.terrain.kind, target, None, need=4)
            pool = pool + [m for m in local if m not in pool]
    else:
        pool = [m for m in bestiary.MONSTERS if m.lo - 6 <= target <= m.hi + 6] or list(bestiary.MONSTERS)
    _, picks = _compose(rng, target, pool, party_size)
    return [bestiary.build_enemy(m, target, el, pit=True) for m, el in picks]


# ---- intel: what the colony knows about a floor -----------------------------------------------------------------
def intel_level(knowledge: float) -> int:
    return sum(1 for t in config.INTEL_LEVELS if knowledge >= t)


def _counts(enemies: List[Enemy]) -> str:
    out: dict = {}
    for e in enemies:
        out[e.name] = out.get(e.name, 0) + 1
    return ", ".join(f"{n}x {name}" if n > 1 else name for name, n in out.items())


def intel_lines(seed: int, floor: int, knowledge: float, party_size: int) -> List[str]:
    """What is known about one floor. More knowledge reveals more:
        >=20 terrain, enemy count & tier | >=40 enemy types & elements | >=60 boss identity |
        >=80 abilities, total HP, purple-gel odds | 100 weaknesses, terrain advice and loot outlook."""
    lvl = intel_level(knowledge)
    if lvl < 1 or not 1 <= floor <= MAX_FLOOR:
        return ["unknown"]
    info = floor_info(seed, floor, party_size)
    enemies, t = info.enemies, info.terrain
    mobs = [e for e in enemies if not e.boss] or enemies
    lines = [f"{t.emoji} {t.name}: {terr.describe(t)}",
             f"{len(enemies)} foes, tier {max(e.tier for e in mobs)}" + (" - a guardian waits" if info.boss else "")]
    if info.affinity:
        el = elements.get(info.affinity)
        lines.append(f"{el.emoji} elemental floor: {el.name} spells hit harder here (for both sides) and the opposing element softer")
    if lvl >= 2:
        lines.append(f"{info.pattern}: " + _counts(mobs))
        els = sorted({e.element for e in enemies if e.element})
        lines.append("elements: " + (", ".join(elements.get(x).emoji + elements.get(x).name for x in els) or "none"))
    if lvl >= 3 and info.boss:
        b = enemies[0]
        lines.append(f"BOSS: {b.emoji}{b.name} ({elements.get(b.element).name if b.element else 'neutral'})")
    if lvl >= 4:
        lines.append("abilities: " + ", ".join(sorted({a for e in enemies for a in e.abilities})))
        lines.append(f"total HP ~{int(sum(e.stats['hp'] for e in enemies))}, "
                     f"purple gel chance ~{max(e.purple_chance for e in enemies):.0%} per foe")
    if lvl >= 5:
        weak: dict = {}
        tough: dict = {}
        for e in enemies:
            if e.element:
                for a, d in elements.BEATS.items():
                    if d == e.element:                              # what beats its element is its weakness ...
                        weak[a] = weak.get(a, 0) + 1
                if e.element in elements.BEATS:                     # ... and what its element beats it resists
                    d = elements.BEATS[e.element]
                    tough[d] = tough.get(d, 0) + 1
            for a in e.weak:
                weak[a] = weak.get(a, 0) + 1
            for a in e.resists:
                tough[a] = tough.get(a, 0) + 1

        def top(d: dict) -> str:
            ranked = sorted(d, key=lambda k: (-d[k], k))[:2]
            return ", ".join(f"{elements.get(k).emoji}{elements.get(k).name}" for k in ranked) or "none"
        boosted = max(t.boosts, key=t.boosts.get) if t.boosts else None
        lines.append("weak to: " + top(weak) + "; resists: " + top(tough))
        best = max(weak, key=lambda k: (weak[k], k)) if weak else None
        lines.append("weakness: " + (f"{elements.get(best).emoji}{elements.get(best).name} spells" if best else "none")
                     + (f"; terrain favours {elements.get(boosted).emoji}{elements.get(boosted).name}" if boosted else "")
                     + f"; loot ~{sum(hi for e in enemies for (_, hi) in e.loot.values())} gel/essence max")
    return lines


def intel_view(seed: int, floors, knowledge: dict, party_size: int) -> List[dict]:
    """Rows for a range of floors; `knowledge` maps floor -> 0..100."""
    rows = []
    for f in floors:
        k = knowledge.get(f, 0.0)
        known = intel_level(k) >= 1 and 1 <= f <= MAX_FLOOR
        info = floor_info(seed, f, party_size) if 1 <= f <= MAX_FLOOR else None
        rows.append(dict(floor=f, boss=is_boss_floor(f), knowledge=round(k, 1), lines=intel_lines(seed, f, k, party_size),
                         terrain=(dict(key=info.terrain.key, name=info.terrain.name, emoji=info.terrain.emoji)
                                  if known and info else None),
                         title=(info.title if known and info else "")))
    return rows


# ---- scouting: how long does a floor take to explore completely? ------------------------------
def clear_hours(floor: int, avg_level: float, knowledge: float = 0.0, size: int = 5) -> int:
    """Game hours a party needs to clear one floor: deeper floors take longer; a party stronger than the floor (and
    one that already knows it from scouting) is faster, a weaker one slower."""
    base = config.CLEAR_BASE_HOURS + config.CLEAR_HOURS_PER_FLOOR * floor
    ratio = max(0.2, avg_level) / max(1.0, floor)
    lvl = max(0.6, min(1.4, 1.3 - 0.3 * ratio))
    know = 1 - config.CLEAR_KNOWLEDGE_CUT * max(0.0, min(100.0, knowledge)) / 100
    team = 1 + 0.02 * (size - 5)                  # bigger parties move slower, small ones lighter
    return max(1, int(round(base * lvl * know * team)))


def floor_hours(seed: int, floor: int, skill: float = 1.0):
    """(nominal hours, actual hours) to scout one floor to 100%. The actual figure hides a seeded 0.85-1.20x
    factor, so an estimate is never exact - budget a margin or the party is lost."""
    nominal = config.SCOUT_HOURS_PER_FLOOR * (1 + config.SCOUT_DEPTH_GROWTH * (floor - 1)) / skill
    factor = random.Random(seed * 104729 + floor * 13).uniform(*config.SCOUT_VARIANCE)
    return nominal, nominal * factor


def scout_estimate(seed: int, first: int, last: int, skill: float = 1.0) -> dict:
    nominal = sum(floor_hours(seed, f, skill)[0] for f in range(first, last + 1))
    lo, hi = config.SCOUT_VARIANCE
    return dict(nominal=round(nominal, 1), low=round(nominal * lo, 1), high=round(nominal * hi, 1),
                safe=int(nominal * hi) + 1)
