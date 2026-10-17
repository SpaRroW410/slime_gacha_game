"""Occupations: chef, blacksmith, trainer."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, jobs
from slime_gacha.errors import InvalidAction
from slime_gacha.game import Game
from tests.test_delves import rich


def slime(g, cls="medic"):
    s = g.gacha.make_slime("common", cls, stars=1)
    g.roster[s.id] = s
    return s


class TestJobs(unittest.TestCase):
    def test_assign_switch_stop_and_slots(self):
        g = rich(91)
        a, b, c = slime(g), slime(g), slime(g)
        g.assign_job(a.id, "chef")
        self.assertEqual(a.state, "working")
        self.assertTrue(a.busy)
        g.assign_job(a.id, "trainer")                       # switching is free
        self.assertEqual(a.job, "trainer")
        g.assign_job(b.id, "chef")
        with self.assertRaises(InvalidAction):
            g.assign_job(c.id, "blacksmith")                # only two places at Workshops level 1
        g.buildings.levels["workshops"] = 2
        g.assign_job(c.id, "blacksmith")
        g.stop_job(a.id)
        self.assertEqual((a.state, a.job), ("idle", ""))
        with self.assertRaises(InvalidAction):
            g.assign_job(a.id, "juggler")

    def test_working_slimes_cannot_be_merged_or_sent_away(self):
        g = rich(92)
        a, b = slime(g), slime(g)
        g.assign_job(a.id, "chef")
        with self.assertRaises(InvalidAction):
            g.merge(b.id, a.id)

    def test_chef_feeds_the_hungriest(self):
        g = rich(93)
        chef, guest = slime(g), slime(g, "barbarian")
        guest.needs.set("food", 20)
        g.assign_job(chef.id, "chef")
        food = g.wallet.get("food")
        g.needs.auto_care = False
        g.tick(jobs.JOBS["chef"].cycle)
        self.assertGreater(guest.needs.get("food"), 40)
        self.assertEqual(food - g.wallet.get("food"), 1)
        self.assertEqual(chef.job_xp["chef"], 1)

    def test_blacksmith_mends_gear_for_free(self):
        from slime_gacha import items
        g = rich(94)
        smith, owner = slime(g, "barbarian"), slime(g)
        it = items.Item(7, "iron_sword")
        it.durability = 1
        owner.items["weapon"] = it
        g.assign_job(smith.id, "blacksmith")
        g.needs.auto_care = False
        g.tick(jobs.JOBS["blacksmith"].cycle)
        self.assertGreater(it.durability, 1)
        self.assertEqual(smith.job_xp["blacksmith"], 1)

    def test_trainer_raises_proficiency(self):
        g = rich(95)
        trainer, pupil = slime(g, "rogue"), slime(g, "barbarian")
        pupil.class_prof = 30.0
        g.assign_job(trainer.id, "trainer")
        g.needs.auto_care = False
        g.tick(jobs.JOBS["trainer"].cycle)
        self.assertGreater(pupil.class_prof, 30.0)

    def test_levels_and_talent(self):
        g = rich(96)
        s = slime(g, "medic")
        self.assertEqual(jobs.level(s, "chef"), 1)
        s.job_xp["chef"] = config.JOB_XP_STEP * 4
        self.assertEqual(jobs.level(s, "chef"), 3)
        self.assertGreater(jobs.power(s, "chef"), jobs.power(slime(g, "rogue"), "chef"))

    def test_jobs_are_saved(self):
        g = rich(97)
        s = slime(g)
        g.assign_job(s.id, "chef")
        s.job_xp["chef"] = 7
        h = Game.from_dict(g.to_dict())
        t = h.slime(s.id)
        self.assertEqual((t.state, t.job, t.job_xp), ("working", "chef", {"chef": 7}))

    def test_tired_worker_stops(self):
        g = rich(98)
        s = slime(g)
        g.assign_job(s.id, "chef")
        s.needs.set("energy", config.AUTO_SLEEP_BELOW - 1)
        g.needs.auto_care = False
        g.tick(1)
        self.assertEqual(s.state, "idle")


if __name__ == "__main__":
    unittest.main()
