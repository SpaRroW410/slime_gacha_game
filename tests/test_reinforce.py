"""Descent reinforcements: limited camping, ambush relief, joint fights and the mage's call."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from slime_gacha.errors import InvalidAction, NotEnoughResources
from tests.test_delves import rich, party, members


def two_parties(floor=3, seed=81):
    g = rich(seed)
    a = party(g, strong=True, name="A")
    b = party(g, strong=True, name="B")
    for pid in (a, b):
        for s in members(g, pid):
            s.progress = 50
    return g, a, b


class TestCampLimit(unittest.TestCase):
    def test_floor_three_allows_three_hours_then_refuses(self):
        g, a, _ = two_parties()
        g.enter_dungeon(a)
        g.delves[a]["floor"] = 3
        g.intel[3] = 0.0
        g.rng.random = lambda: 0.99
        self.assertEqual(g.camp_limit(a), 3)
        g.delve_camp(a, 24)                                  # trimmed to the 3 hours that are left
        self.assertEqual(g.delves[a]["camped"], 3)
        with self.assertRaises(InvalidAction):
            g.delve_camp(a, 1)

    def test_scouting_stretches_the_limit_and_a_new_floor_resets_it(self):
        g, a, _ = two_parties()
        g.enter_dungeon(a)
        g.delves[a]["floor"] = 4
        g.intel[4] = 100.0
        self.assertEqual(g.camp_limit(a), 8)
        g.delves[a]["camped"] = 8
        g.delves[a]["floor"] = 5
        g.delves[a]["camped"] = 0
        self.assertGreater(g.camp_left(a), 0)


class TestAmbushRelief(unittest.TestCase):
    def test_nearby_party_lowers_ambush_chance(self):
        g, a, b = two_parties()
        g.enter_dungeon(a)
        g.delves[a]["floor"] = 6
        base = g.relief(a)
        g.enter_dungeon(b)
        g.delves[b]["floor"] = 5
        self.assertEqual(base, 0.0)
        self.assertGreater(g.relief(a), 0.0)
        g.delves[b]["floor"] = 6
        self.assertEqual(g.relief(a), 1.0)


class TestCall(unittest.TestCase):
    def _mage(self, g, pid, stars=5, attuned=("fire", "water")):
        m = members(g, pid)[0]
        m.archetype, m.stars, m.attuned = "mage", stars, list(attuned)
        return m

    def test_five_star_two_element_mage_calls_for_purple_gel(self):
        g, a, b = two_parties()
        g.enter_dungeon(a)
        g.delves[a]["floor"] = 11
        self._mage(g, a)
        before = g.wallet.get("purple_gel")
        g.call_reinforcements(a, b)
        self.assertEqual(before - g.wallet.get("purple_gel"), 1 + 11 // 5)
        self.assertEqual(g.delves[b]["floor"], 11)
        self.assertIn(b, g.joinable(a))

    def test_call_rules(self):
        g, a, b = two_parties()
        g.enter_dungeon(a)
        g.delves[a]["floor"] = 11
        m = self._mage(g, a, stars=4)
        with self.assertRaises(InvalidAction):
            g.call_reinforcements(a, b)                      # not 5 stars
        m.stars = 5
        m.attuned = ["fire"]
        with self.assertRaises(InvalidAction):
            g.call_reinforcements(a, b)                      # one element only
        m.attuned = ["fire", "water"]
        for s in members(g, b):
            s.progress = 0                                   # the call skips the "cleared the floor above" rule
        g.wallet.add("purple_gel", -g.wallet.get("purple_gel"))
        with self.assertRaises(NotEnoughResources):
            g.call_reinforcements(a, b)
        g.wallet.add("purple_gel", 10)
        g.call_reinforcements(a, b)
        self.assertEqual(g.delves[b]["floor"], 11)

    def test_two_parties_fight_one_floor_together(self):
        g, a, b = two_parties()
        g.enter_dungeon(a)
        g.enter_dungeon(b)
        g.delves[a]["floor"] = g.delves[b]["floor"] = 2
        r = g.delve_next(a, join=[b])
        self.assertTrue(r.victory)
        self.assertTrue(all(g.slime(s.id).progress >= 2 for s in members(g, a) + members(g, b)))
        self.assertEqual(g.delves[a]["floor"], 3)
        self.assertEqual(g.delves[b]["floor"], 3)

    def test_cannot_join_another_floor(self):
        g, a, b = two_parties()
        g.enter_dungeon(a)
        g.enter_dungeon(b)
        g.delves[b]["floor"] = 4
        with self.assertRaises(InvalidAction):
            g.delve_next(a, join=[b])


if __name__ == "__main__":
    unittest.main()
