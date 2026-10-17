"""Pit XP is tied to the XP a level costs, so the climb is about the same length for every rarity."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from tests.test_delves import rich, party, members


class TestPitEconomy(unittest.TestCase):
    def _run(self, rarity, level, depth=3, seed=131):
        g = rich(seed)
        pid = party(g, rarity=rarity, strong=False)
        for s in members(g, pid):
            s.stage = 1 if level <= 30 else 2
            s.level = level
            s.hp = s.max_hp
        rep = g.grind(pid, depth, 1).runs[0]
        return g, pid, rep

    def test_a_won_run_pays_the_xp_need_over_the_runs_per_level(self):
        for rarity, level in (("common", 25), ("rare", 20), ("legendary", 15)):
            g, pid, rep = self._run(rarity, level)
            if not rep.victory:
                self.skipTest(f"{rarity} party lost the sample fight")
            mem = members(g, pid)
            need = sum(config.xp_to_next(level, s.rarity) for s in mem) / len(mem)
            runs = config.PIT_RUNS_PER_LEVEL * (1 + config.PIT_RARITY_RUNS * config.RARITIES.index(rarity))
            self.assertAlmostEqual(rep.xp, need / runs, delta=need / runs * 0.03 + 2, msg=rarity)

    def test_rarer_slimes_need_proportionally_more_runs_per_level(self):
        need = config.xp_to_next(40)
        runs = [need * (2 ** i) / config.pit_xp_per_run(need * (2 ** i), i, 3) for i in range(5)]
        self.assertEqual([round(r / runs[0], 2) for r in runs], [1.0, 1.5, 2.0, 2.5, 3.0])

    def test_deeper_pits_pay_more(self):
        need = 1000
        pays = [config.pit_xp_per_run(need, 0, d) for d in range(1, 6)]
        self.assertEqual(pays, sorted(pays))
        self.assertLess(pays[0], pays[2])
        self.assertGreater(pays[4], pays[2])

    def test_the_climb_to_floor_50_is_a_matter_of_days_not_months(self):
        import sys as _s
        _s.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
        import playtest as pt
        for rarity, level in (("common", 63), ("rare", 40), ("legendary", 22)):
            hours = pt.real_hours(pt.pit_runs_to(1, level, rarity))
            self.assertLess(hours, 200, (rarity, hours))             # at the x3 dungeon rate


if __name__ == "__main__":
    unittest.main()
