"""Relationships: explicit ties between slimes that grow out of their bonds.

    friend       bond >= 25
    best friend  bond >= 45 after a few days; one per slime
    rival        a sour bond (<= -12) and repeated quarrels
    mentor       an experienced slime (8+ levels ahead, same class or discipline) takes a younger one under its wing
    couple       a deep bond, high compatibility and affection; one partner each, never kin
and, for couples, BUDDING: a new slime (a child) with traits, class and rarity drawn from both parents.

Ties shape the colony: party synergy, feelings before a fight (couples feel affection, rivals determination and
anger), a mentee's XP, and how hard a loss hits. Lineage (`slime.parents`) builds the family tree.
"""
import random
from typing import Dict, List, Optional

from . import config

KINDS = ("friend", "best_friend", "rival", "mentor", "couple")
LABEL = {"friend": "Friends", "best_friend": "Best friends", "rival": "Rivals", "mentor": "Mentor & mentee",
         "couple": "Couple"}
EMOJI = {"friend": "🤝", "best_friend": "💞", "rival": "⚔️", "mentor": "🎓", "couple": "💘"}
SYNERGY = {"friend": 0.01, "best_friend": 0.02, "rival": -0.02, "mentor": 0.015, "couple": 0.03}


def key(a, b) -> frozenset:
    return frozenset((a.id if hasattr(a, "id") else a, b.id if hasattr(b, "id") else b))


class RelationshipEngine:
    def __init__(self):
        self.rel: Dict[frozenset, dict] = {}              # pair -> {kind, since, [mentor, mentee], [last_bud]}
        self.quarrels: Dict[frozenset, int] = {}

    # ---- lookup ---------------------------------------------------------------------------------------------
    def kind(self, a, b) -> Optional[str]:
        r = self.rel.get(key(a, b))
        return r["kind"] if r else None

    def of(self, sid: int) -> List[dict]:
        out = []
        for k, r in self.rel.items():
            if sid in k:
                other = next(iter(k - {sid}))
                out.append(dict(other=other, **r))
        return out

    def partner(self, sid: int) -> Optional[int]:
        return next((r["other"] for r in self.of(sid) if r["kind"] == "couple"), None)

    def best_friend(self, sid: int) -> Optional[int]:
        return next((r["other"] for r in self.of(sid) if r["kind"] == "best_friend"), None)

    def mentees(self, sid: int) -> List[int]:
        return [r["other"] for r in self.of(sid) if r["kind"] == "mentor" and r["mentor"] == sid]

    def mentor_of(self, sid: int) -> Optional[int]:
        return next((r["mentor"] for r in self.of(sid) if r["kind"] == "mentor" and r["mentee"] == sid), None)

    def forget(self, sid: int) -> None:
        self.rel = {k: v for k, v in self.rel.items() if sid not in k}
        self.quarrels = {k: v for k, v in self.quarrels.items() if sid not in k}

    def _jealousy(self, game, slimes, journal, rng) -> None:
        """A partner much closer to someone else may stir jealousy (and a small grudge against that someone)."""
        from . import emotions, memory
        social, lines = game.social, 0
        for k, r in self.rel.items():
            if r["kind"] != "couple":
                continue
            for me_id, p_id in (tuple(k), tuple(k)[::-1]):
                me, p = slimes.get(me_id), slimes.get(p_id)
                if not me or not p:
                    continue
                ours = social.bond(me, p)
                rival = max((o for o in slimes.values() if o.id not in k), key=lambda o: social.bond(p, o), default=None)
                if rival and social.bond(p, rival) > ours + config.JEALOUS_GAP and rng.random() < config.JEALOUS_CHANCE:
                    emotions.feel(me, "anger", 8, f"jealous of {rival.name}")
                    emotions.feel(me, "sadness", 6, f"jealous of {rival.name}")
                    memory.remember(me, "slight", rival, game.day, 1.5, f"(so close to {p.name})")
                    if lines < 2:
                        journal.append(f"💚 {me.name} feels a little jealous: {p.name} spends so much time with {rival.name}.")
                        lines += 1

    def note_quarrel(self, a, b, n: int = 1) -> None:
        """Count quarrels towards a rivalry; a quarrel that ends in making up takes one back (n=-1)."""
        k = key(a, b)
        self.quarrels[k] = max(0, self.quarrels.get(k, 0) + n)
        if not self.quarrels[k]:
            del self.quarrels[k]

    # ---- kin ------------------------------------------------------------------------------------------------------
    @staticmethod
    def kin(a, b) -> bool:
        """Parent/child, siblings (shared parent)."""
        return a.id in b.parents or b.id in a.parents or bool(set(a.parents) & set(b.parents))

    # ---- party effects --------------------------------------------------------------------------------------------
    def synergy_delta(self, party) -> float:
        ids = {s.id for s in party}
        d = sum(SYNERGY[r["kind"]] for k, r in self.rel.items() if k <= ids)
        return max(-0.10, min(0.15, d))

    def prebattle(self, party, emotions) -> None:
        """Fighting beside a loved one or a rival stirs feelings."""
        by_id = {s.id: s for s in party}
        for k, r in self.rel.items():
            if not k <= set(by_id):
                continue
            a, b = (by_id[i] for i in k)
            if r["kind"] in ("couple", "best_friend"):
                for s in (a, b):
                    emotions.feel(s, "affection", 8)
                    emotions.feel(s, "determination", 5)
            elif r["kind"] == "rival":
                for s in (a, b):
                    emotions.feel(s, "determination", 12)
                    emotions.feel(s, "anger", 6)
            elif r["kind"] == "mentor":
                emotions.feel(by_id[r["mentor"]], "pride", 8)
                emotions.feel(by_id[r["mentee"]], "determination", 8)

    def mentee_xp(self, party, xp: int) -> Dict[int, int]:
        """Bonus XP for mentees fighting beside their mentor."""
        ids = {s.id for s in party}
        return {r["mentee"]: max(1, int(xp * config.MENTOR_XP)) for k, r in self.rel.items()
                if r["kind"] == "mentor" and k <= ids}

    # ---- daily evolution --------------------------------------------------------------------------------------------
    def daily(self, game, rng: random.Random, journal: List[str], day: int) -> None:
        slimes = {s.id: s for s in game.slimes()}
        social, emo = game.social, game.emotions_mod
        match = 1 + 0.25 * game.keeper.rank("matchmaker")
        # 1. companionship: slimes who share the colony's days (idle, resting or at a post in town - not away on a trip or a
        #    foraging walk) and like each other grow closer
        idle = [s for s in slimes.values() if s.state in ("idle", "resting", "sleeping", "working") and not s.in_dungeon]
        cold = game.conflicts.cold
        home = {s.id for s in idle}
        for k, v in list(social.bonds.items()):          # ties fade on days the two did not share (apart, on different trips)
            if v < config.BOND_FADE_FROM or len(k) != 2:
                continue
            a, b = (slimes.get(i) for i in k)
            if a and b and not (a.id in home and b.id in home) and not game._together(a, b):
                social.add_bond(a, b, -config.BOND_FADE)
        self._jealousy(game, slimes, journal, rng)
        for i, a in enumerate(idle):
            for b in idle[i + 1:]:
                if key(a, b) in cold:                     # a cold war: they keep out of each other's way
                    continue
                c = social.compat(a, b)
                if c >= 10:
                    social.add_bond(a, b, (1.5 + (1.0 if c >= 35 else 0.0)) * match)
                    for s in (a, b):
                        s.needs.add("belonging", 2)
                        emo.feel(s, "affection", 6 if c >= 35 else 3)
        # 2. existing ties may fade or deepen
        for k, r in list(self.rel.items()):
            a, b = (slimes.get(i) for i in k)
            if not a or not b:
                continue
            bond = social.bond(a, b)
            if r["kind"] == "friend" and bond < 15:
                del self.rel[k]
                journal.append(f"💔 {a.name} and {b.name} have drifted apart.")
            elif r["kind"] == "best_friend" and bond < 35:
                r["kind"] = "friend"
                journal.append(f"💔 {a.name} and {b.name} are no longer best friends.")
            elif r["kind"] == "rival" and bond >= 5:
                r["kind"] = "friend" if bond >= 25 else "rival"
                if r["kind"] == "friend":
                    journal.append(f"🤝 {a.name} and {b.name} have settled their rivalry and become friends.")
                else:
                    del self.rel[k]
            elif r["kind"] == "couple" and (bond < 25 or self.kind(a, b) == "rival"):
                del self.rel[k]
                for s in (a, b):
                    emo.feel(s, "sadness", 40)
                    emo.feel(s, "anger", 10)
                journal.append(f"💔 {a.name} and {b.name} have split up.")
            elif r["kind"] == "mentor":
                mentor, mentee = slimes.get(r["mentor"]), slimes.get(r["mentee"])
                if mentor and mentee and mentee.level >= mentor.level - 2:
                    r.clear()
                    r.update(kind="friend", since=day)
                    emo.feel(mentee, "pride", 30)
                    emo.feel(mentor, "pride", 30)
                    journal.append(f"🎓 {mentee.name} has caught up with {mentor.name}. They are friends now.")
        # 3. new ties
        for k, bond in list(social.bonds.items()):
            if k in self.rel or len(k) != 2:
                continue
            a, b = (slimes.get(i) for i in k)
            if not a or not b:
                continue
            if bond <= -12 and self.quarrels.get(k, 0) >= 2:
                self.rel[k] = dict(kind="rival", since=day)
                journal.append(f"⚔️ {a.name} and {b.name} have become rivals.")
            elif bond >= config.FRIEND_BOND:
                self.rel[k] = dict(kind="friend", since=day)
                journal.append(f"🤝 {a.name} and {b.name} have become friends.")
        for k, r in list(self.rel.items()):
            a, b = (slimes.get(i) for i in k)
            if not a or not b:
                continue
            bond = social.bond(a, b)
            age = day - r.get("since", day)
            if r["kind"] == "friend" and bond >= config.BEST_FRIEND_BOND and age >= 5 \
                    and not self.best_friend(a.id) and not self.best_friend(b.id):
                r.update(kind="best_friend", since=day)
                journal.append(f"💞 {a.name} and {b.name} are best friends!")
            elif r["kind"] in ("friend", "best_friend") and self._couple_ok(game, a, b, bond) \
                    and rng.random() < config.COUPLE_CHANCE * match:
                r.clear()
                r.update(kind="couple", since=day, last_bud=-999)
                for s in (a, b):
                    emo.feel(s, "joy", 35)
                    emo.feel(s, "affection", 40)
                journal.append(f"💘 {a.name} and {b.name} have fallen in love.")
        for a in slimes.values():                                    # mentorships
            if self.mentor_of(a.id) or len(self.mentees(a.id)) >= 2:
                continue
            for b in slimes.values():
                if b.id == a.id or self.mentor_of(b.id) or key(a, b) in self.rel and self.kind(a, b) != "friend":
                    continue
                if (a.level - b.level >= 8 and (a.archetype == b.archetype or a.arch.discipline == b.arch.discipline)
                        and social.bond(a, b) >= 15 and len(self.mentees(a.id)) < 2
                        and rng.random() < config.MENTOR_CHANCE * match):
                    self.rel[key(a, b)] = dict(kind="mentor", since=day, mentor=a.id, mentee=b.id)
                    emo.feel(a, "pride", 25)
                    emo.feel(b, "determination", 25)
                    journal.append(f"🎓 {a.name} takes {b.name} under their wing.")
                    break

    def _couple_ok(self, game, a, b, bond: float) -> bool:
        return (bond >= config.COUPLE_BOND and game.social.compat(a, b) >= 20 and not self.partner(a.id)
                and not self.partner(b.id) and not self.kin(a, b)
                and a.needs.get("belonging") >= 60 and b.needs.get("belonging") >= 60
                and (a.emotions.get("affection", 0) + b.emotions.get("affection", 0)) >= 20)

    # ---- persistence ----------------------------------------------------------------------------------------------------
    def to_dict(self) -> dict:
        return dict(rel=[[*sorted(k), v] for k, v in self.rel.items()],
                    quarrels=[[*sorted(k), n] for k, n in self.quarrels.items()])

    def load(self, d: dict, alive: set) -> None:
        self.rel = {frozenset(x[:2]): x[2] for x in (d or {}).get("rel", []) if x[0] in alive and x[1] in alive}
        self.quarrels = {frozenset(x[:2]): x[2] for x in (d or {}).get("quarrels", [])
                         if x[0] in alive and x[1] in alive}


# ---- budding ---------------------------------------------------------------------------------------------------------------
_SYL = [("blo", "p"), ("gloo", "b")]


def child_name(a, b, rng: random.Random) -> str:
    na, nb = a.name.lower(), b.name.lower()
    return (na[:max(2, len(na) // 2)] + nb[len(nb) // 2:]).capitalize()


def child_rarity(a, b, rng: random.Random, midwife: int = 0) -> str:
    r = config.RARITIES
    ia, ib = r.index(a.rarity), r.index(b.rarity)
    lo, hi = min(ia, ib), max(ia, ib)
    i = hi if rng.random() < config.BUD_TOP_PARENT + 0.05 * midwife else lo
    if rng.random() < config.BUD_BLESSING + 0.01 * midwife:
        i = min(len(r) - 1, hi + 1)
    return r[i]


def child_stars(a, b, rng: random.Random) -> int:
    stars = 1
    if max(a.stars, b.stars) >= 3 and rng.random() < 0.25:
        stars += 1
    if min(a.stars, b.stars) >= 4 and rng.random() < 0.10:
        stars += 1
    return stars
