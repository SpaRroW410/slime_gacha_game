"""Slimes that act on their own: training they start (autonomy, gel from an hourly real-time budget), rival spar requests,
requests for posts they are made for, and a free Rest Area bed before a nap."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, mind
from slime_gacha.errors import InvalidAction
from tests.test_magic import rich_game, scholar


def ready(s):
    s.hp = s.max_hp
    s.state = "idle"
    for k in ("energy", "food", "safety", "belonging", "esteem"):
        s.needs.set(k, 100)


class TestSelfStartedTraining(unittest.TestCase):
    def _game(self):
        g = rich_game(3)
        g.wallet.add("white_gel", 5000)
        s = scholar(g, "barbarian", 3)
        ready(s)
        return g, s

    def test_a_slime_that_wants_to_master_its_style_goes_to_drill(self):
        g, s = self._game()
        s.goal = dict(kind="master", target=0, day=g.day, text="wants to master swordsmanship")
        log = []
        with mock.patch.object(config, "AUTO_TRAIN_CHANCE", 1.0):
            g._auto_train(s, log)
        self.assertEqual(s.state, "studying")
        self.assertEqual(s.task["kind"], "drill")
        self.assertTrue(any("goes by itself" in l for l in log))
        self.assertLess(g.auto_gel, config.AUTO_GEL_PER_HOUR)

    def test_a_slime_that_wants_to_learn_studies_its_element(self):
        g, s = self._game()
        el = mind.learn_target(s)
        self.assertTrue(el)
        s.goal = dict(kind="learn", target=0, el=el, day=g.day, text="wants to learn more about it")
        with mock.patch.object(config, "AUTO_TRAIN_CHANCE", 1.0):
            g._auto_train(s, [])
        self.assertEqual((s.state, s.task["kind"]), ("studying", "study"))
        self.assertIn(el, s.attuned)

    def test_gel_comes_only_from_the_hourly_budget_and_never_banks_past_an_hour(self):
        g, s = self._game()
        s.goal = dict(kind="master", target=0, day=g.day, text="wants to master swordsmanship")
        t0 = 1_000_000.0
        with mock.patch("time.time", return_value=t0):
            g.auto_gel, g.auto_gel_at = 0.0, t0
            with mock.patch.object(config, "AUTO_TRAIN_CHANCE", 1.0):
                g._auto_train(s, [])
            self.assertEqual(s.state, "idle")                       # nothing left this hour
        with mock.patch("time.time", return_value=t0 + 1800):       # half an hour later: half the hourly gel
            self.assertAlmostEqual(g.gel_budget(), config.AUTO_GEL_PER_HOUR / 2)
        with mock.patch("time.time", return_value=t0 + 86400):      # a day away: still one hour's worth at most
            self.assertEqual(g.gel_budget(), config.AUTO_GEL_PER_HOUR)

    def test_autonomy_off_or_a_tired_slime_does_not_go(self):
        g, s = self._game()
        s.goal = dict(kind="master", target=0, day=g.day, text="wants to master swordsmanship")
        g.autonomy = False
        log = []
        with mock.patch.object(config, "AUTO_TRAIN_CHANCE", 1.0):
            g._autonomy_tick(log)
        self.assertEqual(s.state, "idle")
        g.autonomy = True
        s.needs.set("energy", 20)
        with mock.patch.object(config, "AUTO_TRAIN_CHANCE", 1.0):
            g._auto_train(s, [])
        self.assertEqual(s.state, "idle")


class TestRequests(unittest.TestCase):
    def test_rivals_ask_for_a_spar_and_a_granted_one_clears_the_air(self):
        g = rich_game(4)
        a, b = scholar(g, "barbarian", 3), scholar(g, "rogue", 3)
        for s in (a, b):
            ready(s)
        g.relations.rel[frozenset((a.id, b.id))] = dict(kind="rival", since=0)
        g.social.bonds[frozenset((a.id, b.id))] = -30
        r = mind.make_request(g, a)
        self.assertEqual((r["kind"], r["target"]), ("spar", b.id))
        a.request = r
        msg = mind.answer(g, a.id, True)
        self.assertIn("rivalry cools", msg)
        self.assertGreater(g.social.bond(a, b), -30)
        self.assertIsNone(a.request)

    def test_a_refused_spar_keeps_the_request_when_it_cannot_happen(self):
        g = rich_game(4)
        a, b = scholar(g, "barbarian", 3), scholar(g, "rogue", 3)
        for s in (a, b):
            ready(s)
        a.request = dict(kind="spar", target=b.id, day=g.day, text="asks for a sparring match")
        b.needs.set("energy", 1)                                   # too tired by the time the Keeper says yes
        with self.assertRaises(InvalidAction):
            mind.answer(g, a.id, True)
        self.assertIsNotNone(a.request)

    def test_a_slime_with_a_knack_asks_for_the_chef_post(self):
        g = rich_game(5)
        s = scholar(g, "mage", 3)
        ready(s)
        with mock.patch.object(mind, "spar_rival", lambda g, s: None):
            r = mind.make_request(g, s)
        self.assertIsNotNone(r)
        self.assertEqual(r["kind"], "post")
        self.assertIn(r["job"], ("chef", "librarian", "trainer_magic"))


class TestRestAreaFirst(unittest.TestCase):
    def test_sleepers_at_home_take_a_free_bed(self):
        g = rich_game(6)
        s = scholar(g, "barbarian", 3)
        ready(s)
        s.state = "sleeping"
        s.needs.set("energy", 30)
        events = []
        g._to_free_beds(events)
        self.assertEqual(s.state, "resting")
        self.assertTrue(events)


if __name__ == "__main__":
    unittest.main()
