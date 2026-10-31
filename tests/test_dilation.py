"""Dungeon time: each place runs its own number of dungeon hours per lobby hour (places.py), activities cost the lobby clock
ceil(hours / rate), parties inside live and bond at the dungeon's pace, mages hasten rescues, and mages are a little rarer."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, places
from slime_gacha.archetypes import all_archetypes
from slime_gacha.game import Game
from tests.test_delves import rich, party, members


class TestPlaceRates(unittest.TestCase):
    def test_every_dungeon_but_hunting_and_home_flags_runs_three_times_faster(self):
        for k in ("main", "grind", "adventure", "quarry", "mossy_burrows", "scout", "rescue", "wave"):
            self.assertEqual(places.dilation(k), 3.0, k)
        for k in ("stranded", "train", "lab", "", "hunting", "no_such_place"):
            self.assertEqual(places.dilation(k), 1.0, k)       # hunts and foraging are not places; stranded scouts wait at lobby pace

    def test_a_place_can_be_retuned_on_its_own(self):
        places.register_place(places.Place("test_flat", "Flat Cave", "🕳", "expedition", dilation=1.0)) if "test_flat" not in places.PLACES else None
        places.register_place(places.Place("test_slow", "Slow Cave", "🕳", "expedition", dilation=1.5)) if "test_slow" not in places.PLACES else None
        self.assertEqual(Game.lobby_hours("test_flat", 4), 4)
        self.assertEqual(Game.lobby_hours("test_slow", 3), 2)
        self.assertEqual(Game.lobby_hours("main", 3), 1)         # the others are untouched

    def test_data_defined_expeditions_default_to_three_and_can_say_otherwise(self):
        self.assertEqual(places.place_from_dict(dict(key="x1", name="X")).dilation, 3.0)
        self.assertEqual(places.place_from_dict(dict(key="x2", name="X", dilation=2)).dilation, 2.0)
        self.assertEqual(places.place_from_dict(dict(key="x3", name="X", kind="job")).dilation, 1.0)

    def test_lobby_hours_round_up_with_a_minimum_of_one(self):
        self.assertEqual([Game.lobby_hours("main", h) for h in (0, 1, 2, 3, 4, 6, 7, 24)], [0, 1, 1, 1, 2, 2, 3, 8])


class TestTheClock(unittest.TestCase):
    def test_a_floor_is_ready_after_a_third_of_its_hours_on_the_lobby_clock(self):
        g = rich(70)
        g.deferred_turn = True
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        t = g.tick_count
        g.delve_next(pid)
        inside = g.delves[pid]["hours"]
        self.assertEqual(g.delves[pid]["ready_tick"] - t, g.lobby_hours("main", inside))
        self.assertLessEqual(g.delves[pid]["ready_tick"] - t, -(-inside // 3))

    def test_camping_costs_a_third_of_the_hours_and_gives_the_rest_back(self):
        g = rich(71)
        g.deferred_turn = True
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        g.delves[pid]["floor"] = 6
        g.rng.random = lambda: 0.99
        for s in members(g, pid):
            s.hp, s.needs.v["energy"] = max(1, s.max_hp // 4), 30.0
        t = g.tick_count
        g.delve_camp(pid, 6)
        self.assertEqual(g.delves[pid]["ready_tick"] - t, 2)     # 6 hours inside
        self.assertTrue(all(s.needs.get("energy") > 60 for s in members(g, pid)))
        self.assertTrue(all(s.hp > s.max_hp // 4 + 1 for s in members(g, pid)))


class TestLivingFaster(unittest.TestCase):
    def test_a_party_inside_burns_three_times_the_food_and_energy_per_lobby_hour(self):
        g = rich(72)
        g.needs.auto_care = False
        a = g.gacha.make_slime("common", "barbarian", stars=2)
        b = g.gacha.make_slime("common", "barbarian", stars=2)
        for s in (a, b):
            g.roster[s.id] = s
            s.traits = []                                        # no trait changes how fast it tires or hungers
            s.needs.v["food"] = s.needs.v["energy"] = 90.0
        a.in_dungeon = "main"
        g.needs.tick(g.slimes(), [])
        lost_a = 90.0 - a.needs.get("food"), 90.0 - a.needs.get("energy")
        lost_b = 90.0 - b.needs.get("food"), 90.0 - b.needs.get("energy")
        self.assertAlmostEqual(lost_a[0], 3 * lost_b[0], places=4)
        self.assertAlmostEqual(lost_a[1], 3 * lost_b[1], places=4)

    def test_stranded_scouts_and_farming_sessions_are_not_double_counted(self):
        g = rich(73)
        g.needs.auto_care = False
        x = g.gacha.make_slime("common", "barbarian", stars=2)
        y = g.gacha.make_slime("common", "barbarian", stars=2)
        z = g.gacha.make_slime("common", "barbarian", stars=2)
        for s in (x, y, z):
            g.roster[s.id] = s
            s.traits = []
            s.needs.v["food"] = 90.0
        x.in_dungeon, y.in_dungeon = "stranded", "grind"
        g.needs.tick(g.slimes(), [])
        base = 90.0 - z.needs.get("food")
        self.assertAlmostEqual(90.0 - x.needs.get("food"), base, places=4)        # stranded: lobby pace
        self.assertEqual(y.needs.get("food"), 90.0)                               # a Pit session pays its own hours

    def test_party_members_away_together_grow_closer_at_the_dungeon_pace(self):
        g = rich(74)
        pid = party(g, strong=True)
        a, b = members(g, pid)[:2]
        before = g.social.bond(a, b)
        g._away_bonds()
        self.assertEqual(g.social.bond(a, b), before)            # at home: no travelling together
        for s in members(g, pid):
            s.in_dungeon = "main"
        g._away_bonds()
        self.assertAlmostEqual(g.social.bond(a, b) - before, config.AWAY_BOND_PER_HOUR * 3.0)

    def test_the_colony_at_home_does_not_speed_up_when_a_party_is_away(self):
        g = rich(75)
        pid = party(g, strong=True)
        home = g.gacha.make_slime("common", "barbarian", stars=2)
        g.roster[home.id] = home
        home.traits = []
        g.needs.auto_care = False
        g.enter_dungeon(pid)
        before = home.needs.get("food")
        g.tick(1)
        self.assertAlmostEqual(before - home.needs.get("food"), config.NEED_DECAY["food"], places=4)


class TestMagesAndRescues(unittest.TestCase):
    def mage(self, g, stars):
        m = g.gacha.make_slime("common", "mage", stars=stars)
        g.roster[m.id] = m
        return m

    def test_a_mage_hastens_a_rescue_more_with_stars_up_to_a_limit(self):
        g = rich(76)
        m3, m5 = self.mage(g, 3), self.mage(g, 5)
        fighter = g.gacha.make_slime("common", "barbarian", stars=5)
        g.roster[fighter.id] = fighter
        self.assertEqual(g.rescue_speed([fighter]), 0.0)
        self.assertAlmostEqual(g.rescue_speed([m3]), config.RESCUE_MAGE_SPEED + 3 * config.RESCUE_MAGE_SPEED_STAR)
        self.assertGreater(g.rescue_speed([m5]), g.rescue_speed([m3]))
        self.assertEqual(g.rescue_speed([m5, m5, m5, m5]), config.RESCUE_MAGE_SPEED_MAX)

    def test_the_trip_is_shorter_with_a_mage_along(self):
        g = rich(77)
        e = dict(id=1, ids=[], first=1, last=10, stuck=10, needed=20, deadline=g.tick_count + 24)
        base = g.rescue_hours(e)
        with_mage = g.rescue_hours(e, [self.mage(g, 5)])
        self.assertLess(with_mage, base)
        self.assertGreaterEqual(with_mage, 1)
        self.assertEqual(g.rescue_hours(e, [g.gacha.make_slime("common", "barbarian")]), base)


class TestMageRarity(unittest.TestCase):
    def test_a_mage_is_a_little_rarer_than_the_other_magic_classes(self):
        w = {a.key: a.pull_weight for a in all_archetypes()}
        for other in ("medic", "necromancer", "alchemist"):
            self.assertLess(w["mage"], w[other])
        self.assertGreater(w["mage"], 0.75 * w["medic"])         # only a little
        g = rich(78)
        n = 6000
        mages = sum(g.gacha.make_slime("common").archetype == "mage" for _ in range(n))
        self.assertLess(mages / n, 0.095)
        self.assertGreater(mages / n, 0.07)


if __name__ == "__main__":
    unittest.main()
