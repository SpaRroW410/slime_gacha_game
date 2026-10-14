"""Social layer: bonds, COMPATIBILITY between slimes, party synergy, MORALE (fight readiness), and the
Council's keep-vs-sacrifice advice.

* bond        pair value (-40..60) grown by sparring, fighting side by side, resolving quarrels.
* compat      -100..100 = traits + class chemistry + shared/fusable elements + friendship + bond - open quarrels.
* synergy     a party's average compatibility becomes a +/-10% power modifier (Barracks boosts it).
* morale      0..100 "ready to fight". Drifts toward a target set by mood; wins, losses, deaths and rest move it.
              It scales battle power by x0.85..x1.15 and a broken slime (<20) may freeze.
* council     ranks the roster (KEEP / FLEX / SACRIFICE?) and suggests merges (donor is consumed!) so you can
              decide who to sacrifice and who to keep.
"""
from itertools import combinations
from typing import Dict, Iterable, List, Optional

from . import config, elements
from .archetypes import get_archetype

# ---- trait chemistry (unordered). Same-trait entries are written as a 1-tuple key. ---------
TRAIT_PAIRS: Dict[frozenset, int] = {
    frozenset(["grumpy"]): -10, frozenset(["proud"]): -8, frozenset(["kind"]): 6, frozenset(["chatty"]): 3,
    frozenset(["brave"]): 3, frozenset(["lazy"]): 4, frozenset(["gluttonous"]): 4, frozenset(["timid"]): 2,
    frozenset(["chatty", "timid"]): 6, frozenset(["brave", "timid"]): 6, frozenset(["lazy", "gluttonous"]): 6,
    frozenset(["grumpy", "chatty"]): -8, frozenset(["grumpy", "kind"]): 3, frozenset(["proud", "brave"]): -6,
    frozenset(["proud", "timid"]): -4, frozenset(["kind", "timid"]): 5, frozenset(["kind", "gluttonous"]): 4,
}
COMPLEMENT = {frozenset(["medic", "barbarian"]): 14, frozenset(["medic", "ranger"]): 10,
              frozenset(["mage", "rogue"]): 10, frozenset(["necromancer", "barbarian"]): 8,
              frozenset(["ranger", "mage"]): 10}
RARITY_INDEX = {r: i for i, r in enumerate(config.RARITIES)}


def pair(a, b) -> frozenset:
    return frozenset((a.id if hasattr(a, "id") else a, b.id if hasattr(b, "id") else b))


class SocialEngine:
    def __init__(self, conflicts, buildings):
        self.conflicts = conflicts
        self.buildings = buildings
        self.bonds: Dict[frozenset, float] = {}

    # ---- bonds ---------------------------------------------------------------------
    def bond(self, a, b) -> float:
        return self.bonds.get(pair(a, b), 0.0)

    def add_bond(self, a, b, amount: float) -> None:
        amount = amount * self.buildings.bond_mult() if amount > 0 else amount
        k = pair(a, b)
        self.bonds[k] = max(config.BOND_MIN, min(config.BOND_MAX, self.bonds.get(k, 0.0) + amount))

    def forget(self, sid: int) -> None:
        self.bonds = {k: v for k, v in self.bonds.items() if sid not in k}

    def inherit(self, donor, target, others: Iterable) -> None:
        """Merging: the target inherits a share of the donor's bonds ('memories')."""
        for o in others:
            if o.id in (donor.id, target.id):
                continue
            v = self.bonds.get(pair(donor, o), 0.0)
            if v > 0:
                self.add_bond(target, o, v * config.MERGE_BOND_INHERIT / self.buildings.bond_mult())

    # ---- compatibility ---------------------------------------------------------------
    def compat_parts(self, a, b) -> Dict[str, int]:
        parts: Dict[str, int] = {}
        t = sum(TRAIT_PAIRS.get(frozenset((x, y)), 0) for x in a.traits for y in b.traits)
        parts["traits"] = max(-30, min(30, t))
        cls = 0
        if b.archetype in get_archetype(a.archetype).rivals or a.archetype in get_archetype(b.archetype).rivals:
            cls += config.COMPAT_RIVAL
        if a.archetype == b.archetype:
            cls += config.COMPAT_SAME_CLASS
        cls += COMPLEMENT.get(frozenset((a.archetype, b.archetype)), 0)
        parts["class"] = cls
        el = 0
        shared = set(a.attuned) & set(b.attuned)
        el += min(2, len(shared)) * config.COMPAT_SHARED_ELEMENT
        if any(elements.combine(x, y) for x in a.attuned for y in b.attuned if x != y):
            el += config.COMPAT_FUSION_PARTNERS
        parts["elements"] = el
        parts["friends"] = config.COMPAT_FRIEND if pair(a, b) in self.conflicts.friends else 0
        parts["bond"] = int(self.bond(a, b))
        parts["quarrel"] = config.COMPAT_OPEN_CONFLICT if self.conflicts.open_between(a.id, b.id) else 0
        return parts

    def compat(self, a, b) -> int:
        return max(-100, min(100, sum(self.compat_parts(a, b).values())))

    @staticmethod
    def compat_label(v: int) -> str:
        return ("soulmates" if v >= 60 else "close" if v >= 30 else "friendly" if v >= 10 else
                "neutral" if v > -10 else "tense" if v > -30 else "hostile")

    def avg_compat(self, slimes: List) -> float:
        pairs = list(combinations(slimes, 2))
        return sum(self.compat(a, b) for a, b in pairs) / len(pairs) if pairs else 0.0

    def synergy(self, slimes: List) -> float:
        """Power multiplier for a party: 1 + up to +/-10% from average compatibility."""
        return 1.0 + max(-1.0, min(1.0, self.avg_compat(slimes) / 100.0)) * \
            config.SYNERGY_MAX * self.buildings.synergy_mult()

    # ---- morale ------------------------------------------------------------------------
    @staticmethod
    def morale_label(m: float) -> str:
        return ("fired up" if m >= 80 else "ready" if m >= 55 else "steady" if m >= 35 else
                "shaky" if m >= config.MORALE_BROKEN else "broken")

    @staticmethod
    def morale_factor(m: float) -> float:
        return config.MORALE_POWER_MIN + (config.MORALE_POWER_MAX - config.MORALE_POWER_MIN) * m / 100.0

    @staticmethod
    def shift_morale(slime, delta: float) -> None:
        slime.morale = max(0.0, min(100.0, slime.morale + delta))

    def morale_tick(self, slimes: List, stress: float = 0.0) -> None:
        """`stress` = recent sacrifices (merges): it drags every morale target down."""
        drift = self.buildings.morale_drift()
        drag = min(config.SACRIFICE_TARGET_PENALTY_MAX, config.SACRIFICE_TARGET_PENALTY * stress)
        for s in slimes:
            if s.state in ("resting",):             # the Rest Area manages its own morale
                continue
            target = min(100.0, config.MORALE_BASE_TARGET + config.MORALE_MOOD_SPAN * s.mood()
                         + self.buildings.morale_target_bonus() - drag)
            s.morale += (target - s.morale) * drift

    # ---- council: keep / sacrifice -----------------------------------------------------
    def keep_scores(self, slimes: List, in_party: Optional[set] = None) -> List[dict]:
        if not slimes:
            return []
        in_party = in_party or set()
        top = max(s.power_rating() for s in slimes) or 1.0
        rows = []
        for s in slimes:
            others = [o for o in slimes if o is not s]
            avg = sum(self.compat(s, o) for o in others) / len(others) if others else 0
            close = sum(1 for o in others if self.compat(s, o) >= 30)
            quality = 0.5 * s.stars / config.MAX_STARS + 0.5 * RARITY_INDEX[s.rarity] / (len(config.RARITIES) - 1)
            invested = min(1.0, s.total_xp / 3000.0)
            arcane = min(1.0, (len(s.spells) + sum(elements.basic_level(s, b) for b in s.attuned) / 4) / 6.0)
            social = max(0.0, min(1.0, (avg + 100) / 200.0 + 0.05 * close))
            score = 100 * (0.35 * s.power_rating() / top + 0.20 * quality + 0.10 * invested
                           + 0.10 * arcane + 0.15 * min(1.0, social) + 0.10 * (1 if s.id in in_party else 0))
            reasons = []
            if s.stars >= 4 or s.rarity in ("epic", "legendary"):
                reasons.append(f"{s.star_str()} {s.rarity}")
            if close:
                reasons.append(f"{close} close friend(s)")
            if s.spells:
                reasons.append(f"{len(s.spells)} spell(s)")
            if s.id in in_party:
                reasons.append("in a party")
            if avg < -10:
                reasons.append("disliked by the colony")
            if s.power_rating() / top < 0.5:
                reasons.append("low power")
            rows.append(dict(slime=s, score=round(score, 1), avg_compat=round(avg), close=close,
                             reasons=reasons))
        rows.sort(key=lambda r: -r["score"])
        n = len(rows)
        for i, r in enumerate(rows):
            r["verdict"] = "KEEP" if i < max(1, round(n * 0.4)) else \
                ("SACRIFICE?" if n >= 4 and i >= n - max(1, round(n * 0.25)) else "FLEX")
        return rows

    def grief(self, donor, slimes: List, amp: float = 1.0) -> int:
        """Total morale the colony loses if `donor` is sacrificed (friends hurt most). `amp` = 1 + stress effect."""
        total = 0
        for o in slimes:
            if o is donor:
                continue
            total += -config.MERGE_MORALE_FRIENDS if (pair(donor, o) in self.conflicts.friends or
                                                      self.bond(donor, o) >= 20) else -config.MERGE_MORALE_OTHERS
        return int(round(total * amp + (-config.MERGE_MORALE_TARGET) * amp))
