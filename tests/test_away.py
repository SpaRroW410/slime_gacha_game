"""The 'away' timers: everything that keeps slimes out of the colony, with the time left."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha.webapi import away_view, snapshot
from tests.test_time import mk, party


class TestAwayTimers(unittest.TestCase):
    def test_nothing_away_at_home(self):
        self.assertEqual(away_view(mk()), [])

    def test_a_hunt_shows_game_hours_in_turn_mode_and_a_countdown_in_live_mode(self):
        g = mk(live=False)
        s = g.slimes()[0]
        g.hunt(s.id, "meadow")
        (a,) = away_view(g)
        self.assertEqual((a["kind"], a["ids"], a["real_sec"]), ("hunt", [s.id], None))
        self.assertGreater(a["hours"], 0)
        self.assertIn("Hunting", a["label"])
        g2 = mk(live=True)
        s2 = g2.slimes()[0]
        g2.hunt(s2.id, "meadow")
        (b,) = away_view(g2)
        self.assertGreater(b["real_sec"], 0)
        self.assertAlmostEqual(b["real_sec"], b["hours"] / g2.clock_rate() * 3600, delta=2)

    def test_a_live_dungeon_session_and_the_descent_are_listed(self):
        g = mk(live=True)
        pid = party(g)
        g.grind(pid, 1, 1)
        items = away_view(g)
        self.assertTrue(any(i["kind"] == "expedition" and "Pit" in i["label"] and i["real_sec"] > 0 for i in items))
        self.assertIn("away", snapshot(g))

    def test_inside_the_descent_is_listed_even_with_no_timer(self):
        g = mk(live=False)
        pid = party(g)
        for s in g.party_members(pid):
            s.progress = 0
        g.enter_dungeon(pid, 1)
        (a,) = away_view(g)
        self.assertEqual(a["kind"], "delve")
        self.assertTrue(a["ready"])
        self.assertIsNone(a["hours"])


if __name__ == "__main__":
    unittest.main()
