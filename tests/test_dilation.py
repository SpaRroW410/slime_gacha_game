"""Dungeon time: each place runs its own number of dungeon hours per lobby hour (places.py), activities cost the lobby clock
ceil(hours / rate), parties inside live and bond at the dungeon's pace, mages hasten rescues, and mages are a little rarer."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, passives, places
from slime_gacha.archetypes import all_archetypes
from slime_gacha.game import Game
from tests.test_delves import rich, party, members


class TestPlaceRates(unittest.TestCase):
    def test_every_dungeon_but_scouting_hunting_and_home_flags_runs_three_times_faster(self):
        for k in ("main", "grind", "adventure", "quarry", "mossy_burrows", "rescue", "wave"):
            self.assertEqual(places.dilation(k), 3.0, k)
        for k in ("scout", "stranded", "train", "lab", "", "hunting", "no_such_place"):
            self.assertEqual(places.dilation(k), 1.0, k)       # scouting stays in lobby hours; hunts and foraging are not places

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


class TestTailwindAndRescues(unittest.TestCase):
    """Only a slime that has mastered the wind element to the top level hastens a rescue; an ordinary mage does not."""
    def slime(self, g, arch="mage", stars=5, wind=0):
        m = g.gacha.make_slime("common", arch, stars=stars)
        g.roster[m.id] = m
        if wind:
            m.attuned = ["wind"]
            m.mastery_xp["wind"] = config.MASTERY_XP[wind - 1]
        return m

    def test_the_passive_needs_wind_mastered_to_the_top(self):
        g = rich(76)
        top = self.slime(g, wind=len(config.MASTERY_XP))
        almost = self.slime(g, wind=len(config.MASTERY_XP) - 1)
        plain_mage = self.slime(g)
        fire = self.slime(g)
        fire.attuned, fire.mastery_xp["fire"] = ["fire"], config.MASTERY_XP[-1]
        self.assertTrue(passives.has(g, top, "tailwind"))
        for s in (almost, plain_mage, fire):
            self.assertFalse(passives.has(g, s, "tailwind"))
        self.assertIn("tailwind", [p.key for p in passives.earned(g, top)])
        self.assertNotIn("tailwind", [p.key for p in passives.earned(g, plain_mage)])

    def test_any_class_that_masters_wind_earns_it(self):
        g = rich(76)
        self.assertTrue(passives.has(g, self.slime(g, arch="barbarian", wind=len(config.MASTERY_XP)), "tailwind"))

    def test_only_the_bearers_hasten_a_rescue_up_to_a_limit(self):
        g = rich(76)
        bearer = self.slime(g, wind=len(config.MASTERY_XP))
        mage = self.slime(g)
        self.assertEqual(g.rescue_speed([mage]), 0.0)
        self.assertEqual(g.rescue_speed([bearer, mage]), config.RESCUE_TAILWIND_SPEED)
        many = [self.slime(g, wind=len(config.MASTERY_XP)) for _ in range(4)]
        self.assertEqual(g.rescue_speed(many), config.RESCUE_TAILWIND_MAX)

    def test_the_trip_is_shorter_with_a_bearer_along(self):
        g = rich(77)
        e = dict(id=1, ids=[], first=1, last=10, stuck=10, needed=20, deadline=g.tick_count + 24)
        base = g.rescue_hours(e)
        self.assertLess(g.rescue_hours(e, [self.slime(g, wind=len(config.MASTERY_XP))]), base)
        self.assertEqual(g.rescue_hours(e, [self.slime(g)]), base)

    def test_the_slime_view_lists_passives_earned_or_locked(self):
        from slime_gacha.webapi import slime_view
        g = rich(79)
        top = self.slime(g, wind=len(config.MASTERY_XP))
        plain = self.slime(g)
        v = {p["key"]: p for p in slime_view(g, top)["passives"]}
        self.assertTrue(v["tailwind"]["earned"])
        w = {p["key"]: p for p in slime_view(g, plain)["passives"]}
        self.assertFalse(w["tailwind"]["earned"])
        self.assertIn("wind", w["tailwind"]["need"])

    def test_a_new_passive_needs_only_data(self):
        g = rich(80)
        passives.register_passive(passives.Passive("test_hardy", "Hardy", "🛡", "proficiency", "Tough.", "Reach level 3.",
                                                   lambda g, s: s.level >= 3, dict(guard=0.05)))
        s = self.slime(g, arch="barbarian")
        s.level = 3
        self.assertTrue(passives.has(g, s, "test_hardy"))
        self.assertFalse(passives.has(g, s, "no_such_passive"))
        self.assertEqual(passives.battle_mods(g, s).get("guard"), 0.05)
        passives.PASSIVES.unregister("test_hardy")               # the registry is global: leave it as it was


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
