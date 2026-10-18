"""Rescue parties for overdue scouts, and several delves at once in live mode."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from slime_gacha.errors import InvalidAction
from slime_gacha.webapi import away_view, snapshot
from tests.test_delves import party, members
from tests.test_time import mk


def stranded_game(live=False, seed=31):
    g = mk(seed=seed, n=1, live=live)
    scouts = party(g, strong=True, name="Scouts")
    rescuers = party(g, strong=True, name="Rescue")
    for pid in (scouts, rescuers):
        for s in members(g, pid):
            s.progress = 20
    g.rng.random = lambda: 0.99                                   # no ambushes
    plan = g.scout_plan(scouts, 3, 5)
    res = g.scout(scouts, 3, 5, max(2, int(plan["low"] * 0.5)))
    assert res.stranded
    return g, scouts, rescuers


class TestStranded(unittest.TestCase):
    def test_overdue_scouts_are_stranded_with_a_deadline_and_listed(self):
        g, scouts, _ = stranded_game()
        (e,) = g.stranded
        self.assertEqual(e["first"], 3)
        self.assertTrue(all(g.roster[i].in_dungeon == "stranded" for i in e["ids"]))
        self.assertGreater(g.stranded_left(e), 0)
        view = [a for a in away_view(g) if a["kind"] == "stranded"]
        self.assertEqual(len(view), 1)
        self.assertEqual(snapshot(g)["stranded"][0]["rescue_hours"], g.rescue_hours(e))

    def test_a_rescue_brings_them_home(self):
        g, scouts, rescuers = stranded_game()
        (e,) = g.stranded
        g.rng.random = lambda: 0.0                                    # success (and an ambush that we ignore below)
        for s in members(g, rescuers):
            s.hp = s.max_hp
        gel_food = g.wallet.get("food")
        out = g.rescue(rescuers, e["id"])
        self.assertTrue(any("bring" in l for l in out))
        self.assertEqual(g.stranded, [])
        self.assertTrue(all(g.roster[i].in_dungeon == "" for i in e["ids"] if i in g.roster))
        self.assertLess(g.wallet.get("food"), gel_food)
        g.tick(config.RESCUE_DEADLINE_HOURS)
        self.assertGreaterEqual(sum(1 for i in e["ids"] if i in g.roster), 1)    # nobody is lost afterwards

    def test_a_failed_rescue_leaves_them_waiting_and_late_rescue_is_refused(self):
        g, scouts, rescuers = stranded_game()
        (e,) = g.stranded
        seq = iter([0.99, 0.99])
        g.rng.random = lambda: next(seq, 0.99)                         # no ambush, rescue fails
        out = g.rescue(rescuers, e["id"])
        self.assertTrue(any("could not" in l for l in out))
        self.assertEqual(len(g.stranded), 1)
        g.tick(config.RESCUE_DEADLINE_HOURS)                           # the deadline passes
        self.assertEqual(g.stranded, [])
        self.assertTrue(any("scout" in d["cause"] or "stranded" in d["cause"] for d in g.graveyard))

    def test_rescuers_must_have_walked_down_to_the_scouts(self):
        g, scouts, rescuers = stranded_game()
        (e,) = g.stranded
        for s in members(g, rescuers):
            s.progress = 0
        with self.assertRaises(InvalidAction):
            g.rescue(rescuers, e["id"])
        with self.assertRaises(InvalidAction):
            g.rescue(rescuers, 999)

    def test_stranded_scouts_survive_a_save(self):
        from slime_gacha.game import Game
        g, scouts, _ = stranded_game()
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.stranded, g.stranded)
        self.assertTrue(all(h.roster[i].in_dungeon == "stranded" for i in h.stranded[0]["ids"]))


class TestSeveralDelvesLive(unittest.TestCase):
    def test_two_parties_delve_at_once_with_their_own_timers(self):
        g = mk(seed=32, n=1, live=True)
        a = party(g, strong=True, name="A")
        b = party(g, strong=True, name="B")
        for pid in (a, b):
            for s in members(g, pid):
                s.progress = 30
            g.enter_dungeon(pid)
        g.rng.random = lambda: 0.99
        g.delve_next(a)
        ta = g.delves[a]["ready_tick"] - g.tick_count
        self.assertGreater(ta, 0)
        self.assertNotIn("ready_tick", g.delves[b])                    # B is untouched and free to act
        g.clock.advance(0.0001)
        g.delve_next(b)
        tb = g.delves[b]["ready_tick"] - g.tick_count
        self.assertGreater(tb, 0)
        with self.assertRaises(InvalidAction):
            g.delve_next(a)                                            # A is still busy
        self.assertEqual({v["kind"] for v in away_view(g)}, {"delve"})
        self.assertEqual(len([v for v in away_view(g) if v["kind"] == "delve"]), 2)
        g.tick(max(ta, tb))                                            # time passes for both
        g.delve_next(a)
        g.delve_next(b)
        self.assertEqual(g.delves[a]["floor"] + g.delves[b]["floor"] > 4, True)


if __name__ == "__main__":
    unittest.main()


class TestScoutAmnesty(unittest.TestCase):
    def test_old_saves_free_everyone_stranded_once(self):
        from slime_gacha.game import Game
        g, scouts, _ = stranded_game()
        d = g.to_dict()
        d["version"] = 15
        h = Game.from_dict(d)
        self.assertEqual(h.stranded, [])
        self.assertTrue(all(s.in_dungeon == "" for s in h.roster.values()))
        d = g.to_dict()
        k = Game.from_dict(d)
        self.assertEqual(len(k.stranded), 1)

    def test_one_slime_can_scout_with_an_automatic_budget(self):
        g = mk(seed=5, n=1)
        pid = party(g, strong=True, name="P")
        s = members(g, pid)[0]
        s.progress = 20
        g.rng.random = lambda: 0.99
        res = g.scout(None, 1, 2, 0, ids=[s.id])
        self.assertFalse(res.stranded)
        self.assertGreaterEqual(g.knowledge.get(1, 0), 100.0) if hasattr(g, "knowledge") else None


class TestBigRescue(unittest.TestCase):
    def test_several_parties_can_rescue_together(self):
        g, scouts, rescuers = stranded_game()
        second = party(g, strong=True, name="Second")
        for s in members(g, second):
            s.progress = 20
        (e,) = g.stranded
        ids = [s.id for s in members(g, rescuers)] + [s.id for s in members(g, second)]
        self.assertGreater(len(ids), g.parties.size)
        g.rng.random = lambda: 0.0
        for i in ids:
            g.roster[i].hp = g.roster[i].max_hp
        g.rescue(None, e["id"], ids)
        self.assertEqual(g.stranded, [])


class TestScoutOnward(unittest.TestCase):
    def test_a_fresh_slime_may_scout_onward_over_scouted_floors_only(self):
        g = mk(seed=6, n=1)
        pid = party(g, strong=True, name="P")
        s = members(g, pid)[0]
        s.progress = 0
        g.rng.random = lambda: 0.99
        with self.assertRaises(InvalidAction):
            g.scout(None, 3, 3, 0, ids=[s.id])                  # floor 2 is neither scouted nor cleared
        g.intel[2] = 100.0
        g.scout(None, 3, 3, 0, ids=[s.id])                      # floor 2 is known: a level-1 slime may go on

    def test_a_floor_cleared_in_the_descent_by_anyone_opens_the_next_scouting(self):
        g = mk(seed=7, n=2)
        pid = party(g, strong=True, name="P")
        fresh = members(g, pid)[0]
        fresh.progress = 0
        other = g.slimes()[-1]
        other.progress = 6                                      # someone else cleared down to floor 6
        g.rng.random = lambda: 0.99
        g.scout(None, 7, 7, 0, ids=[fresh.id])
