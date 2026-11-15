"""Gentle Keeper badges: milestone floors of the Descent cleared with few slimes merged or destroyed."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import achievements, config
from slime_gacha.game import Game
from tests.test_delves import rich, party, members


def clear_floor(g, floor):
    pid = party(g, strong=True, name=f"F{floor}")
    for s in members(g, pid):
        s.progress = 50
    g.enter_dungeon(pid)
    g.delves[pid]["floor"] = floor
    return g.delve_next(pid)


def spare(g, n=1):
    out = []
    for _ in range(n):
        s = g.gacha.make_slime("common", "barbarian")
        g.roster[s.id] = s
        s.hp = s.max_hp
        out.append(s)
    return out


class TestCounting(unittest.TestCase):
    def test_merges_and_chamber_destroys_both_count(self):
        g = rich(140)
        a, b, c = spare(g, 3)
        self.assertEqual(g.sacrifices, 0)
        g.merge(a.id, b.id)
        self.assertEqual(g.sacrifices, 1)
        g.destroy_slime(c.id)
        self.assertEqual(g.sacrifices, 2)

    def test_deaths_and_departures_do_not_count(self):
        g = rich(141)
        a, b = spare(g, 2)
        g.depart(a, "test")
        b.hp, b.death_cause = 0, "an accident"
        g.tick(1)
        self.assertEqual(g.sacrifices, 0)


class TestGrades(unittest.TestCase):
    def test_grades_follow_the_floors_limits(self):
        gold, silver, bronze = config.GENTLE_FLOORS[10]
        self.assertEqual(achievements.gentle_grade(10, gold), "gold")
        self.assertEqual(achievements.gentle_grade(10, silver), "silver")
        self.assertEqual(achievements.gentle_grade(10, bronze), "bronze")
        self.assertEqual(achievements.gentle_grade(10, bronze + 1), "")
        self.assertEqual(achievements.gentle_grade(11, 0), "")            # not a milestone
        self.assertEqual(achievements.gentle_grade(10, -1), "")           # cleared before the count

    def test_deeper_floors_allow_more(self):
        floors = sorted(config.GENTLE_FLOORS)
        for lo, hi in zip(floors, floors[1:]):
            for i in range(3):
                self.assertLessEqual(config.GENTLE_FLOORS[lo][i], config.GENTLE_FLOORS[hi][i])


class TestMilestones(unittest.TestCase):
    def test_clearing_floor_10_without_sacrifices_earns_gold_and_the_title(self):
        g = rich(142)
        rep = clear_floor(g, 10)
        self.assertTrue(rep.victory)
        self.assertEqual(g.milestones, {10: 0})
        self.assertTrue(any("gold Gentle Keeper" in l for l in rep.log), rep.log)
        events = achievements.check(g)
        self.assertIn("gentle_gold", g.keeper.achieved)
        self.assertIn("gentle_bronze", g.keeper.achieved)
        self.assertTrue(any("the Gentle" in e for e in events))

    def test_the_count_at_the_first_clear_is_kept(self):
        g = rich(143)
        g.sacrifices = config.GENTLE_FLOORS[10][1]               # a silver count
        clear_floor(g, 10)
        self.assertEqual(achievements.gentle_badges(g)[0]["grade"], "silver")
        g.sacrifices = 0                                          # clearing it again later changes nothing
        g.best_floor = 9
        g.milestones[10] = config.GENTLE_FLOORS[10][1]
        clear_floor(g, 10)
        self.assertEqual(g.milestones[10], config.GENTLE_FLOORS[10][1])

    def test_too_many_sacrifices_earn_no_badge(self):
        g = rich(144)
        g.sacrifices = config.GENTLE_FLOORS[10][2] + 1
        rep = clear_floor(g, 10)
        self.assertTrue(any("No Gentle Keeper badge" in l for l in rep.log))
        achievements.check(g)
        self.assertNotIn("gentle_bronze", g.keeper.achieved)

    def test_ordinary_floors_are_not_milestones(self):
        g = rich(145)
        clear_floor(g, 7)
        self.assertEqual(g.milestones, {})


class TestSaves(unittest.TestCase):
    def test_the_count_and_milestones_survive_a_reload(self):
        g = rich(146)
        g.sacrifices = 4
        g.milestones = {10: 2}
        h = Game.from_dict(g.to_dict())
        self.assertEqual((h.sacrifices, h.sacrifices_tracked, h.milestones), (4, True, {10: 2}))

    def test_a_colony_from_before_the_count_earns_no_badge(self):
        g = rich(147)
        d = g.to_dict()
        for k in ("sacrifices", "sacrifices_tracked", "milestones"):
            d.pop(k)
        h = Game.from_dict(d)
        self.assertFalse(h.sacrifices_tracked)
        rep = clear_floor(h, 10)
        self.assertTrue(rep.victory)
        self.assertEqual(h.milestones, {10: -1})
        self.assertEqual(achievements.gentle_badges(h)[0]["grade"], "")

    def test_the_web_state_carries_the_badges(self):
        from slime_gacha.webapi import Session
        se = Session()
        se.new_game(5)
        gk = se.call("state")["state"]["keeper"]["gentle"]
        self.assertEqual((gk["sacrifices"], gk["tracked"]), (0, True))
        self.assertEqual([b["floor"] for b in gk["badges"]], sorted(config.GENTLE_FLOORS))
        self.assertIsNone(gk["badges"][0]["sacrifices"])


if __name__ == "__main__":
    unittest.main()
