"""Slime minds: feuds that cool off, feelings with a baseline, legendaries that read their whole life (docs/MINDS.md)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, emotions, memory
from slime_gacha.ai import Conflict
from slime_gacha.game import Game


def colony(seed=7, n=0):
    g = Game(seed)
    g.wallet.add_many({"white_gel": 10000, "food": 10000})
    if n:
        g.pull(n, "white_gel")
    return g


def make(g, arch="barbarian", rarity="common", stars=1, traits=()):
    s = g.gacha.make_slime(rarity, arch, stars)
    s.traits = list(traits)
    g.roster[s.id] = s
    return s


def feud(g, severity=3, age=None, **kw):
    a, b = make(g), make(g, "mage")
    c = Conflict(1, a.id, b.id, severity, config.CONFLICT_ESCALATE_TICKS - 1 if age is None else age, "a rude blorp", **kw)
    g.conflicts.conflicts.append(c)
    return a, b, c


NO_MEND = mock.patch.object(config, "CONFLICT_SELF_MEND", 0.0)


class TestFeudsCoolOff(unittest.TestCase):
    def test_a_brawl_is_followed_by_time_apart(self):
        g = colony()
        a, b, c = feud(g)
        with NO_MEND:
            g.conflicts.tick(g.slimes(), [])
            self.assertEqual((c.brawls, c.cool), (1, config.CONFLICT_BRAWL_COOL))
            age = c.age
            for _ in range(config.CONFLICT_BRAWL_COOL - 1):
                g.conflicts.tick(g.slimes(), [])
        self.assertEqual(c.age, age)                                  # no escalation while they keep apart
        self.assertEqual(c.brawls, 1)

    def test_a_feud_brawls_at_most_twice_then_turns_cold(self):
        g = colony()
        a, b, c = feud(g)
        events = []
        with NO_MEND:
            for _ in range(24 * 6):
                g.conflicts.tick(g.slimes(), events)
        self.assertEqual(sum("brawl!" in e for e in events), config.CONFLICT_MAX_BRAWLS)
        self.assertTrue(any("stop speaking" in e for e in events))
        self.assertEqual(g.conflicts.conflicts, [])
        self.assertIn(frozenset((a.id, b.id)), g.conflicts.cold)
        self.assertFalse(a.grounded or b.grounded)                    # the fighting is over

    def test_no_quarrels_and_no_growing_closer_in_a_cold_war(self):
        g = colony()
        a, b = make(g), make(g, "mage")
        g.conflicts.cold[frozenset((a.id, b.id))] = 48
        with mock.patch.object(config, "CONFLICT_BASE_CHANCE", 1.0):
            self.assertEqual(g.conflicts.chance(a, b), 0.0)
        before = g.social.bond(a, b)
        g.relations.daily(g, g.mood_rng, [], g.day)
        self.assertEqual(g.social.bond(a, b), before)
        for _ in range(48):
            g.conflicts.tick(g.slimes(), [])
        self.assertNotIn(frozenset((a.id, b.id)), g.conflicts.cold)  # it thaws into plain civility

    def test_cold_wars_and_feud_state_are_saved(self):
        g = colony()
        a, b, c = feud(g, brawls=1, cool=5, retry=2)
        x, y = make(g), make(g)
        g.conflicts.cold[frozenset((x.id, y.id))] = 30
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.conflicts.cold, {frozenset((x.id, y.id)): 30})
        self.assertEqual((h.conflicts.conflicts[0].brawls, h.conflicts.conflicts[0].cool, h.conflicts.conflicts[0].retry), (1, 5, 2))

    def test_old_saves_without_the_new_fields_load(self):
        g = colony()
        feud(g)
        d = g.to_dict()
        for c in d["conflicts"]:
            for k in ("brawls", "cool", "retry"):
                c.pop(k)
        d.pop("cold_wars")
        h = Game.from_dict(d)
        self.assertEqual(h.conflicts.conflicts[0].brawls, 0)
        self.assertEqual(h.conflicts.cold, {})

    def test_spats_can_mend_without_help(self):
        g = colony()
        a, b, c = feud(g, severity=1, age=0)
        events = []
        with mock.patch.object(config, "CONFLICT_SELF_MEND", 1.0):
            g.conflicts.tick(g.slimes(), events)
        self.assertEqual(g.conflicts.conflicts, [])
        self.assertTrue(any("patch things up on their own" in e for e in events))
        self.assertTrue(any(m["kind"] == "made_up" for m in a.memories))

    def test_kind_slimes_mend_more_easily_than_grumpy_ones(self):
        g = colony()
        a, b, c = feud(g, severity=1, age=0)
        plain = g.conflicts.mend_chance(a, b, c)
        a.traits, b.traits = ["kind"], ["kind"]
        kind = g.conflicts.mend_chance(a, b, c)
        a.traits, b.traits = ["grumpy"], ["proud"]
        sour = g.conflicts.mend_chance(a, b, c)
        self.assertGreater(kind, plain)
        self.assertLess(sour, plain)
        c.severity = 3
        self.assertLess(g.conflicts.mend_chance(a, b, c), sour)      # a worse quarrel is harder to let go of

    def test_a_guilty_slime_apologises(self):
        g = colony()
        a, b, c = feud(g, severity=2, age=0)
        a.emotions["guilt"] = 60
        events = []
        with mock.patch.object(config, "APOLOGY_CHANCE", 1.0):
            g._peacemaking(events)
        self.assertEqual(g.conflicts.conflicts, [])
        self.assertTrue(any(f"{a.name} apologises to {b.name}" in e for e in events))
        self.assertLess(emotions.level(a, "guilt"), 60)

    def test_a_friend_of_both_makes_peace(self):
        g = colony()
        a, b, c = feud(g, severity=2, age=0)
        f = make(g, "medic")
        g.social.add_bond(f, a, 40)
        g.social.add_bond(f, b, 40)
        events = []
        with mock.patch.object(config, "PEACEMAKER_CHANCE", 1.0), mock.patch.object(g.conflicts, "mediate_chance", return_value=1.0):
            g._peacemaking(events)
        self.assertEqual(g.conflicts.conflicts, [])
        self.assertTrue(any(f"{f.name} helps" in e for e in events))
        self.assertGreater(memory.opinion(a, f)["gratitude"], 0)     # they remember who helped

    def test_no_peacemaker_when_nobody_likes_both(self):
        g = colony()
        a, b, c = feud(g, severity=2, age=0)
        make(g, "medic")
        with mock.patch.object(config, "PEACEMAKER_CHANCE", 1.0), mock.patch.object(g.conflicts, "mediate_chance", return_value=1.0):
            g._peacemaking([])
        self.assertEqual(len(g.conflicts.conflicts), 1)


if __name__ == "__main__":
    unittest.main()
