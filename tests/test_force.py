"""Descent strike forces (1-5 parties by the floor's place in its segment, one more for a mage's call), no waiting after a
fight led by hand, trainer qualification and pupils, and call-back for slimes at rest, foraging or on a post."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, jobs
from slime_gacha.errors import InvalidAction
from tests.test_delves import rich, party, members


def parties(n, seed=91):
    g = rich(seed)
    pids = [party(g, strong=True, name=f"P{i}") for i in range(n)]
    for pid in pids:
        for s in members(g, pid):
            s.progress = 50
    return g, pids


def on_floor(g, pids, floor):
    for pid in pids:
        if pid not in g.delves:
            g.enter_dungeon(pid)
        g.delves[pid]["floor"] = floor
    return pids


def lead_by_hand(g, limit=300):
    """Stay in command (each turn is ordered by hand; the slimes' own AI picks the move) until the fight ends."""
    n = 0
    while g.battle_run() is not None and n < limit:
        g.battle_auto_turn()
        n += 1
    return n


class TestForceSize(unittest.TestCase):
    def test_a_floor_takes_as_many_parties_as_its_place_in_the_segment(self):
        g, _ = parties(1)
        self.assertEqual([g.force_cap(f) for f in (1, 6, 11)], [1, 1, 1])
        self.assertEqual([g.force_cap(f) for f in (2, 7, 12)], [2, 2, 2])
        self.assertEqual([g.force_cap(f) for f in (3, 8, 13)], [3, 3, 3])
        self.assertEqual([g.force_cap(f) for f in (4, 9, 14)], [4, 4, 4])
        self.assertEqual([g.force_cap(f) for f in (5, 10, 15)], [5, 5, 5])

    def test_too_many_parties_are_refused_and_the_right_number_fight_together(self):
        g, (a, b, c) = parties(3)
        on_floor(g, (a, b, c), 2)
        with self.assertRaises(InvalidAction):
            g.delve_next(a, join=[b, c])                      # floor 2 fits two
        self.assertIsNone(g.flow)
        on_floor(g, (a, b, c), 3)
        r = g.delve_next(a, join=[b, c])                      # floor 3 fits three
        self.assertTrue(r.victory)
        self.assertTrue(all(g.delves[p]["floor"] == 4 for p in (a, b, c)))

    def test_the_first_floor_of_a_segment_is_a_single_file_passage(self):
        g, (a, b) = parties(2)
        on_floor(g, (a, b), 6)
        with self.assertRaises(InvalidAction):
            g.delve_next(a, join=[b])
        self.assertTrue(g.delve_next(a).victory)              # a party can always fight alone
        self.assertEqual(g.delves[b]["floor"], 6)

    def test_boss_floors_take_five(self):
        g, pids = parties(5)
        on_floor(g, pids, 5)
        r = g.delve_next(pids[0], join=pids[1:])
        self.assertTrue(r.victory)

    def test_a_mages_call_adds_one_party_beyond_the_floors_limit(self):
        g, (a, b, c) = parties(3)
        on_floor(g, [a], 1)
        m = members(g, a)[0]
        m.archetype, m.stars, m.attuned = "mage", config.MAX_STARS, ["fire", "water"]
        g.call_reinforcements(a, b)                           # floor 1 takes one party: the called one makes two
        self.assertEqual(g.force_limit(1, [a, b]), 2)
        on_floor(g, [c], 1)
        with self.assertRaises(InvalidAction):
            g.delve_next(a, join=[b, c])                      # only ONE more than the floor takes
        self.assertTrue(g.delve_next(a, join=[b]).victory)

    def test_an_uncalled_second_party_cannot_squeeze_onto_floor_one(self):
        g, (a, b) = parties(2)
        on_floor(g, (a, b), 1)
        with self.assertRaises(InvalidAction):
            g.delve_next(a, join=[b])


class TestNoWaitingAfterAFightByHand(unittest.TestCase):
    def setUp(self):
        g, (self.a,) = parties(1)
        g.deferred_turn = True                                # the web game: time moves only when the player waits
        self.g = g
        on_floor(g, [self.a], 1)

    def test_an_automatic_win_keeps_the_party_busy(self):
        g = self.g
        self.assertTrue(g.delve_next(self.a).victory)
        self.assertGreater(g.delves[self.a]["ready_tick"], g.tick_count)

    def test_a_win_led_by_hand_is_ready_at_once(self):
        g = self.g
        self.assertIsNone(g.delve_next(self.a, manual=True))
        lead_by_hand(g)
        self.assertIsNone(g.flow)
        d = g.delves[self.a]
        self.assertEqual(d["floor"], 2)
        self.assertLessEqual(d.get("ready_tick", 0), g.tick_count)
        self.assertTrue(g.delve_next(self.a).victory)         # the next floor can be fought right away

    def test_switching_to_auto_halfway_brings_the_wait_back(self):
        g = self.g
        g.delve_next(self.a, manual=True)
        g.battle_set_manual(False)
        self.assertGreater(g.delves[self.a]["ready_tick"], g.tick_count)


class TestTrainerRules(unittest.TestCase):
    def slime(self, g, archetype, prof=0.0, stars=2):
        s = g.gacha.make_slime("common", archetype, stars=stars)
        g.roster[s.id] = s
        s.class_prof = prof
        s.hp = s.max_hp
        return s

    def test_a_trainer_must_fight_in_the_posts_discipline(self):
        g = rich(93)
        swordsman = self.slime(g, "barbarian")
        with self.assertRaises(InvalidAction):
            g.assign_job(swordsman.id, "trainer_magic")      # a swordsman cannot teach magic
        mage = self.slime(g, "mage")
        with self.assertRaises(InvalidAction):
            g.assign_job(mage.id, "trainer_sword")
        g.assign_job(mage.id, "trainer_magic")
        g.assign_job(swordsman.id, "trainer_sword")

    def test_a_trainer_only_teaches_those_who_know_less(self):
        g = rich(94)
        t = self.slime(g, "barbarian", prof=50.0)
        g.assign_job(t.id, "trainer_sword")
        novice, equal, master = (self.slime(g, "barbarian", prof=p) for p in (10.0, 50.0, 80.0))
        self.assertGreater(jobs.trainer_bonus(g, "sword", novice), 1.0)
        self.assertEqual(jobs.trainer_bonus(g, "sword", equal), 1.0)
        self.assertEqual(jobs.trainer_bonus(g, "sword", master), 1.0)
        self.assertEqual(jobs.trainer_bonus(g, "sword", t), 1.0)   # nobody teaches themselves
        self.assertGreater(g.academy.drill_gain(novice, "sword"), g.academy.drill_gain(
            self.slime(g, "barbarian", prof=10.0), "sword") * 0.99)
        g.stop_job(t.id)
        self.assertEqual(jobs.trainer_bonus(g, "sword", novice), 1.0)

    def test_a_pupil_of_another_class_is_measured_by_what_it_has_in_the_discipline(self):
        g = rich(95)
        t = self.slime(g, "barbarian", prof=40.0)
        g.assign_job(t.id, "trainer_sword")
        mage = self.slime(g, "mage", prof=90.0)               # a mage's sword skill is nil: it can learn from the trainer
        self.assertGreater(jobs.trainer_bonus(g, "sword", mage), 1.0)


class TestCallBack(unittest.TestCase):
    def test_a_resting_slime_can_be_called_back(self):
        g = rich(96)
        s = g.gacha.make_slime("common", "medic", stars=2)
        g.roster[s.id] = s
        s.state = "resting"
        self.assertIn("called back", g.recall(s.id))
        self.assertEqual(s.state, "idle")


if __name__ == "__main__":
    unittest.main()
