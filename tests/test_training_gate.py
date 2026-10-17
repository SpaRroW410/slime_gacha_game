"""Training gate: sleepers are woken at a mood cost, workers leave their job, wounded drills are worth less;
brawls sour the mood; farming dungeons hand out a little extra."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from slime_gacha.errors import InvalidAction
from tests.test_delves import rich, party, members
from tests.test_jobs import slime


class TestTrainingGate(unittest.TestCase):
    def test_waking_a_sleeper_costs_mood(self):
        g = rich(41)
        s = slime(g)
        s.state = "sleeping"
        morale = s.morale
        out = g.wake(s.id)
        self.assertEqual(s.state, "idle")
        self.assertLess(s.morale, morale)
        self.assertIn("grumpy", out)

    def test_a_drill_wakes_a_sleeper_and_pulls_a_worker_off_the_job(self):
        g = rich(42)
        a, b = slime(g, "barbarian"), slime(g, "medic")
        a.state = "sleeping"
        a.needs.set("energy", 60)
        morale = a.morale
        msg = g.drill(a.id, "sword")
        self.assertIn("grumpy", msg)
        self.assertLess(a.morale, morale)
        self.assertEqual(a.state, "studying")
        g.assign_job(b.id, "chef")
        g.drill(b.id, "magic")
        self.assertEqual((b.job, b.state), ("", "studying"))

    def test_a_too_tired_sleeper_is_refused_before_being_woken(self):
        g = rich(43)
        s = slime(g)
        s.state = "sleeping"
        s.needs.set("energy", 5)
        with self.assertRaises(InvalidAction):
            g.drill(s.id, "magic")
        self.assertEqual(s.state, "sleeping")

    def test_a_hurt_slime_drills_for_less(self):
        g = rich(44)
        a, b = slime(g, "barbarian"), slime(g, "barbarian")
        a.hp = max(1, a.max_hp // 4)
        g.needs.auto_care = False
        g.drill(a.id, "sword")
        g.drill(b.id, "sword")
        pa, pb = a.class_prof, b.class_prof
        g.tick(config.DRILL_TICKS + 1)
        self.assertLess(a.class_prof - pa, b.class_prof - pb)

    def test_party_spar_is_flat_three_and_a_duel_is_two(self):
        g = rich(45)
        pid, other = party(g, name="A"), party(g, name="B")
        gel = g.wallet.get("white_gel")
        g.spar_parties(pid, other, "sword")
        self.assertEqual(gel - g.wallet.get("white_gel"), 3)
        a, b = slime(g, "barbarian"), slime(g, "rogue")
        gel = g.wallet.get("white_gel")
        g.spar(a.id, b.id, "sword")
        self.assertEqual(gel - g.wallet.get("white_gel"), 2)


class TestBrawlMood(unittest.TestCase):
    def test_a_brawl_lowers_morale_and_stirs_anger(self):
        g = rich(46)
        a, b = slime(g, "barbarian"), slime(g, "rogue")
        morale = a.morale
        anger = a.emotions.get("anger", 0) if hasattr(a, "emotions") else 0
        from slime_gacha.ai import Conflict
        c = Conflict(1, a.id, b.id, "a test", config.CONFLICT_MAX_SEVERITY)
        g.conflicts.conflicts.append(c)
        g.conflicts._brawl(c, {a.id: a, b.id: b}, [])
        self.assertTrue(a.grounded and b.grounded)
        self.assertLess(a.morale, morale)
        self.assertGreater(a.emotions.get("anger", 0), anger)


class TestFarmLoot(unittest.TestCase):
    def test_farming_dungeons_hand_out_a_little_extra(self):
        g = rich(47)
        log = []
        g.rng.random = lambda: 0.0                    # every foe drops something
        before = dict(g.wallet.items()) if hasattr(g.wallet, "items") else None
        g._farm_loot(10, log)
        self.assertTrue(any("Also found" in l for l in log))
        g.rng.random = lambda: 0.99
        log.clear()
        g._farm_loot(10, log)
        self.assertEqual(log, [])


if __name__ == "__main__":
    unittest.main()
