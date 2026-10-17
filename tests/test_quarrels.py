"""Quarrels need a shared place: both at home, or the same party away together."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from slime_gacha.ai import Conflict
from tests.test_delves import rich, party, members


class TestQuarrelsShareAPlace(unittest.TestCase):
    def test_together_rules(self):
        g = rich(91)
        pid = party(g, strong=True)
        mem = members(g, pid)
        a, b = mem[0], mem[1]
        outsider = g.gacha.make_slime("common", "mage")
        g.roster[outsider.id] = outsider
        self.assertTrue(g._together(a, b))                          # both home
        g.enter_dungeon(pid, 1)
        self.assertTrue(g._together(a, b))                          # away together in one party
        self.assertFalse(g._together(a, outsider))                  # one away, one home
        outsider.in_dungeon = "main"
        self.assertFalse(g._together(a, outsider))                  # both away, but not as one party

    def test_no_new_quarrels_between_a_slime_at_home_and_one_away(self):
        g = rich(92)
        for _ in range(2):
            s = g.gacha.make_slime("common", "barbarian")
            g.roster[s.id] = s
        a, b = g.slimes()[:2]
        a.in_dungeon = "grind"                                      # away
        old = config.CONFLICT_BASE_CHANCE
        config.CONFLICT_BASE_CHANCE = 1.0
        try:
            for _ in range(20):
                g.conflicts.tick(g.slimes(), [])
        finally:
            config.CONFLICT_BASE_CHANCE = old
        self.assertEqual(g.conflicts.conflicts, [])
        a.in_dungeon = ""
        config.CONFLICT_BASE_CHANCE = 1.0
        try:
            g.conflicts.tick(g.slimes(), [])
        finally:
            config.CONFLICT_BASE_CHANCE = old
        self.assertTrue(g.conflicts.conflicts)                      # at home together they can quarrel

    def test_an_open_quarrel_waits_while_one_of_them_is_away(self):
        g = rich(93)
        for _ in range(2):
            s = g.gacha.make_slime("common", "barbarian")
            g.roster[s.id] = s
        a, b = g.slimes()[:2]
        c = Conflict(id=1, a=a.id, b=b.id, severity=1, age=0, reason="t")
        g.conflicts.conflicts.append(c)
        a.in_dungeon = "grind"
        for _ in range(config.CONFLICT_ESCALATE_TICKS * 3):
            g.conflicts.tick(g.slimes(), [])
        self.assertEqual((c.age, c.severity), (0, 1))               # frozen: no escalation, no brawl
        a.in_dungeon = ""
        for _ in range(config.CONFLICT_ESCALATE_TICKS):
            g.conflicts.tick(g.slimes(), [])
        self.assertGreater(c.age, 0)


if __name__ == "__main__":
    unittest.main()
