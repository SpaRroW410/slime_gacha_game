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


def strong_party(g):
    pid = party(g, strong=True, name="L")
    for s in members(g, pid):
        s.level, s.xp = 40, 0                  # strong, but well below the level cap
        s.hp = s.max_hp
    return pid


class TestPitLure(unittest.TestCase):
    def test_lure_costs_purple_gel_per_run_and_adds_xp(self):
        def run(lure):
            g = rich(83)
            pid = strong_party(g)
            g.rng.seed(5)
            gel = g.wallet.get("purple_gel")
            res = g.grind(pid, 3, 2, lure=lure)
            assert len(res.runs) == 2
            return gel - g.wallet.get("purple_gel"), sum(s.total_xp for s in members(g, pid))
        spent0, xp0 = run(False)
        spent1, xp1 = run(True)
        self.assertEqual(spent0, 0)
        self.assertEqual(spent1, 2 * config.PIT_LURE_COST)
        self.assertGreater(xp1, xp0)

    def test_lure_stops_when_the_gel_is_gone(self):
        g = rich(84)
        pid = strong_party(g)
        g.wallet.add("purple_gel", -g.wallet.get("purple_gel") + 1)
        res = g.grind(pid, 3, 3, lure=True)
        self.assertEqual(g.wallet.get("purple_gel"), 0)
        self.assertTrue(any("out of purple gel" in l for l in res.summary))


class TestRetreat(unittest.TestCase):
    def setup(self, floor=8):
        g, a, _ = two_parties()
        g.enter_dungeon(a)
        g.delves[a]["floor"] = floor
        return g, a

    def test_cost_grows_with_depth_and_checkpoint_exit_stays_free(self):
        g, a = self.setup(8)
        self.assertEqual(g.retreat_cost(a), config.RETREAT_PURPLE_BASE + 1)
        g.delves[a]["floor"] = 24
        self.assertEqual(g.retreat_cost(a), config.RETREAT_PURPLE_BASE + 4)
        g.delves[a]["floor"] = 6                                    # right after a boss: simply leave
        with self.assertRaises(InvalidAction):
            g.retreat(a)
        self.assertIn("climbs out", g.leave_dungeon(a))

    def test_retreat_pays_gel_morale_and_stamina_and_ends_the_delve(self):
        g, a = self.setup(8)
        g.rng.random = lambda: 0.99                                  # no ambush
        gel = g.wallet.get("purple_gel")
        morale = {s.id: s.morale for s in members(g, a)}
        out = g.retreat(a)
        self.assertEqual(gel - g.wallet.get("purple_gel"), config.RETREAT_PURPLE_BASE + 1)
        self.assertNotIn(a, g.delves)
        for s in members(g, a):
            self.assertEqual(s.in_dungeon, "")
            self.assertLess(s.morale, morale[s.id])
            self.assertLessEqual(s.stamina_frac, 0.3)
        self.assertTrue(any("flees" in l for l in out))

    def test_the_flight_can_be_ambushed_and_kill(self):
        g, a = self.setup(8)
        ids = [s.id for s in members(g, a)]
        for s in members(g, a):
            s.hp = 1                                                 # whoever is struck falls
        g.rng.random = lambda: 0.0                                   # always ambushed
        g.rng.uniform = lambda lo, hi: 50.0
        out = g.retreat(a)
        self.assertTrue(any("Ambushed during the retreat" in l for l in out))
        self.assertEqual(sum(1 for i in ids if i not in g.roster), 1)

    def test_needs_purple_gel_and_scouting_lowers_the_risk(self):
        g, a = self.setup(8)
        before = g.retreat_ambush_chance(a)
        g.intel[8] = 100.0
        self.assertLess(g.retreat_ambush_chance(a), before)
        g.wallet.add("purple_gel", -g.wallet.get("purple_gel"))
        with self.assertRaises(NotEnoughResources):
            g.retreat(a)
        self.assertIn(a, g.delves)
