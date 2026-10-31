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


# ---- trips: needs kept up by the session, calling slimes back, several groups at once, trainer lessons ---------------------
from slime_gacha import emotions
from slime_gacha.growth import add_xp
from slime_gacha.webapi import Session


def midlevel_party(g, name="P", n=None):
    pid = party(g, strong=False, name=name, n=n)
    for m in members(g, pid):
        add_xp(m, 300)
        m.hp = m.max_hp
    return pid


class TestSessionsLookAfterTheirParty(unittest.TestCase):
    def run_pit(self, auto_care, timed, energy):
        g = rich(5)
        g.deferred_turn, g.needs.auto_care = timed, auto_care
        pid = midlevel_party(g)
        for m in members(g, pid):
            m.needs.set("energy", energy)
            m.needs.set("food", 40.0)
        res = g.grind(pid, 3, 12)
        return g, pid, res

    def test_a_long_pit_session_does_not_starve_or_exhaust_the_party(self):
        for timed in (True, False):
            for auto_care in (False, True):
                with self.subTest(timed=timed, auto_care=auto_care):
                    g, pid, res = self.run_pit(auto_care, timed, 55.0)
                    self.assertEqual(len(g.graveyard), 0, res.stop_reason)
                    for m in members(g, pid):
                        self.assertGreater(m.needs.get("energy"), config.REFUSE_ENERGY)
                        self.assertGreater(m.needs.get("food"), 0)

    def test_the_party_sleeps_when_tired_and_eats_from_the_stores(self):
        g, pid, res = self.run_pit(False, True, 30.0)
        self.assertTrue(any("camped" in l for l in res.summary))
        self.assertTrue(all(m.needs.get("energy") >= 60 for m in members(g, pid)))

    def test_the_colony_leaves_a_session_partys_needs_to_the_session(self):
        g = rich(6)
        pid = midlevel_party(g)
        m = members(g, pid)[0]
        m.in_dungeon = "grind"
        m.needs.set("energy", 50.0)
        g.needs.tick(g.slimes(), [])
        self.assertEqual(m.needs.get("energy"), 50.0)          # untouched by the colony's tick
        m.in_dungeon = ""
        g.needs.tick(g.slimes(), [])
        self.assertLess(m.needs.get("energy"), 50.0)

    def test_a_session_comes_home_rather_than_die_on_the_road(self):
        g = rich(7)
        pid = midlevel_party(g)
        members(g, pid)[0].needs.set("energy", 4.0)
        self.assertIn("too exhausted", g._field_unfit(members(g, pid)))
        members(g, pid)[0].needs.set("energy", 60.0)
        members(g, pid)[1].needs.set("food", 0.0)
        self.assertIn("out of food", g._field_unfit(members(g, pid)))


class TestCallingSlimesBack(unittest.TestCase):
    def setUp(self):
        self.g = rich(8)
        self.g.deferred_turn = True
        self.s = [self.g.gacha.make_slime("common", "barbarian", stars=2) for _ in range(3)]
        for x in self.s:
            self.g.roster[x.id] = x
            x.hp = x.max_hp
            x.morale = 70.0

    def test_a_resting_slime_must_be_called_back_and_it_costs_morale_and_temper(self):
        g, (a, b, c) = self.g, self.s
        a.state = "resting"
        with self.assertRaises(InvalidAction) as cm:
            g.adventure([a.id, b.id], 1)
        self.assertIn("call them back", str(cm.exception))
        r = g.adventure([a.id, b.id], 1, recall=True)
        self.assertTrue(any("called away" in l for l in r.summary))
        self.assertLess(a.morale, 70.0)
        self.assertGreater(a.emotions.get("anger", 0), 0)

    def test_a_worker_leaves_the_post_and_a_forager_comes_home(self):
        g, (a, b, c) = self.g, self.s
        a.archetype = "medic"
        g.assign_job(a.id, "doctor")
        self.assertEqual(a.state, "working")
        self.assertTrue(g.can_pull_in(a))
        g.pull_in(a)
        self.assertEqual((a.state, a.job), ("idle", ""))
        self.assertLess(a.morale, 70.0)

    def test_a_sleeper_is_only_woken(self):
        g, (a, b, c) = self.g, self.s
        a.state = "sleeping"
        a.needs.set("energy", 90.0)
        before = a.morale
        g.pull_in(a)
        self.assertEqual((a.state, a.morale), ("idle", before))

    def test_nobody_inside_a_dungeon_can_be_reached(self):
        g, (a, b, c) = self.g, self.s
        a.in_dungeon, a.state = "main", "idle"
        self.assertFalse(g.can_pull_in(a))

    def test_the_hurt_and_the_exhausted_are_turned_away_before_anyone_pays(self):
        g, (a, b, c) = self.g, self.s
        a.state = "resting"
        b.hp = 1
        with self.assertRaises(InvalidAction):
            g.adventure([a.id, b.id], 1, recall=True)
        self.assertEqual(a.state, "resting")                    # nobody was pulled in
        self.assertEqual(a.morale, 70.0)


class TestSendingSeveralGroups(unittest.TestCase):
    def setUp(self):
        self.se = Session()
        self.se.new_game(21)
        self.g = self.se.game
        for k in ("white_gel", "essence", "food"):
            self.g.wallet.add(k, 5000)
        self.a = midlevel_party(self.g, "A")
        self.b = midlevel_party(self.g, "B")
        self.g.needs.auto_care = False

    def ids(self, pid):
        return [s.id for s in members(self.g, pid)]

    def test_two_parties_go_at_once_and_fight_separately(self):
        r = self.se.call("send_groups", dict(kind="adventure", groups=[self.ids(self.a), self.ids(self.b)], runs=1))
        self.assertTrue(r["ok"], r["error"])
        text = " ".join(self.g.held[-1]["summary"])              # the web game keeps the party away: the report comes back with it
        self.assertIn("Group 1", text)
        self.assertIn("Group 2", text)
        self.assertEqual(len(self.g.expeditions), 2)             # two separate expeditions, not one big one
        self.assertTrue(all(s.in_dungeon == "adventure" for s in members(self.g, self.a) + members(self.g, self.b)))

    def test_a_group_that_cannot_go_stays_home_and_the_others_go(self):
        members(self.g, self.b)[0].hp = 1
        r = self.se.call("send_groups", dict(kind="quarry", groups=[self.ids(self.a), self.ids(self.b)], runs=1))
        self.assertTrue(r["ok"], r["error"])
        self.assertTrue(any("stays home" in l for l in self.g.held[-1]["summary"]))
        self.assertEqual(len(self.g.expeditions), 1)

    def test_nobody_able_to_go_is_an_error(self):
        for s in members(self.g, self.a):
            s.hp = 1
        r = self.se.call("send_groups", dict(kind="adventure", groups=[self.ids(self.a)], runs=1))
        self.assertFalse(r["ok"])

    def test_an_empty_request_and_too_many_groups_are_refused(self):
        self.assertFalse(self.se.call("send_groups", dict(kind="adventure", groups=[], runs=1))["ok"])
        many = [[i] for i in range(1, 14)]
        self.assertFalse(self.se.call("send_groups", dict(kind="adventure", groups=many, runs=1))["ok"])


class TestTrainerLessons(unittest.TestCase):
    def test_a_trainer_sharpens_a_little_for_each_pupil_it_helps(self):
        g = rich(97)
        t = g.gacha.make_slime("common", "barbarian", stars=2)
        pupil = g.gacha.make_slime("common", "barbarian", stars=2)
        master = g.gacha.make_slime("common", "barbarian", stars=2)
        for x in (t, pupil, master):
            g.roster[x.id] = x
        t.class_prof, pupil.class_prof, master.class_prof = 50.0, 10.0, 80.0
        g.assign_job(t.id, "trainer_sword")
        jobs.lesson(g, "sword", pupil)
        self.assertAlmostEqual(t.class_prof, 50.0 + config.TRAINER_LESSON_GAIN)
        jobs.lesson(g, "sword", master)                         # it knows less than the master: nothing taught, nothing gained
        self.assertAlmostEqual(t.class_prof, 50.0 + config.TRAINER_LESSON_GAIN)
        self.assertLess(config.TRAINER_LESSON_GAIN, 1.0)        # a minute amount next to a drill's gain

    def test_a_finished_drill_teaches_the_trainer_too(self):
        g = rich(98)
        t = g.gacha.make_slime("common", "barbarian", stars=2)
        pupil = g.gacha.make_slime("common", "barbarian", stars=2)
        for x in (t, pupil):
            g.roster[x.id] = x
            x.hp = x.max_hp
        t.class_prof, pupil.class_prof = 60.0, 5.0
        g.assign_job(t.id, "trainer_sword")
        g.buildings.levels["training_grounds"] = max(1, g.buildings.level("training_grounds"))
        g.drill(pupil.id, "sword", 1)
        g.tick(config.DRILL_TIERS[0][2] + 1)
        self.assertGreater(t.class_prof, 60.0)
        self.assertGreater(pupil.class_prof, 5.0)


class TestTradesAndRequests(unittest.TestCase):
    def test_a_slime_view_lists_its_trades_with_progress(self):
        from slime_gacha.webapi import slime_view
        g = rich(99)
        s = g.gacha.make_slime("common", "medic", stars=2)
        g.roster[s.id] = s
        g.assign_job(s.id, "doctor")
        s.job_xp["doctor"], s.job_xp["chef"] = 30, 7
        t = {x["key"]: x for x in slime_view(g, s)["trades"]}
        self.assertEqual((t["doctor"]["level"], t["doctor"]["current"]), (3, True))
        self.assertEqual((t["doctor"]["floor"], t["doctor"]["next"]), (20, 45))     # 10 of 25 shifts into level 3
        self.assertEqual(t["chef"]["level"], 2)
        self.assertNotIn("brewer", t)                                                # a trade it never worked is not listed

    def test_a_rest_request_can_be_granted_through_the_web_api(self):
        se = Session()
        se.new_game(33)
        g = se.game
        g.wallet.add("white_gel", 500)
        se.call("pull", dict(n=3, pay="white_gel"))
        s = g.slimes()[0]
        s.request = dict(kind="rest", target=0, day=g.day, text="asks for a rest day: \"I can't keep going like this.\"")
        s.needs.set("energy", 40.0)
        r = se.call("answer_request", dict(id=s.id, accept=True))
        self.assertTrue(r["ok"], r["error"])
        self.assertIsNone(s.request)
        self.assertGreater(s.needs.get("energy"), 40.0)
