"""Total power breakdown and fusing white gel into purple gel."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, power
from slime_gacha.errors import InvalidAction, NotEnoughResources
from tests.test_delves import rich
from tests.test_jobs import slime


class TestGelFusion(unittest.TestCase):
    def test_hundred_white_make_one_purple(self):
        g = rich(61)
        white, purple = g.wallet.get("white_gel"), g.wallet.get("purple_gel")
        g.merge_gel(3)
        self.assertEqual(white - g.wallet.get("white_gel"), 3 * config.GEL_MERGE)
        self.assertEqual(g.wallet.get("purple_gel") - purple, 3)

    def test_needs_enough_white_gel(self):
        g = rich(62)
        g.wallet.add("white_gel", -g.wallet.get("white_gel") + 99)
        with self.assertRaises(NotEnoughResources):
            g.merge_gel(1)
        with self.assertRaises(InvalidAction):
            g.merge_gel(0)


class TestTotalPower(unittest.TestCase):
    def test_parts_add_up_and_grow_with_rarity_stars_level_and_skills(self):
        g = rich(63)
        s = slime(g, "mage", stars=1)
        tp = power.total_power(s)
        self.assertAlmostEqual(sum(tp["parts"].values()) * tp["multiplier"], tp["total"], delta=0.6)
        base = tp["total"]
        s.level = 40
        lv = power.total_power(s)["total"]
        self.assertGreater(lv, base)
        s.stars = 5
        st = power.total_power(s)["total"]
        self.assertGreater(st, lv)
        s.rarity = "legendary"
        rar = power.total_power(s)
        self.assertGreater(rar["total"], st)
        self.assertGreater(rar["parts"]["skills"], 0)
        self.assertGreater(rar["parts"]["attributes"], 0)

    def test_mastery_styles_proficiency_and_mood_count(self):
        g = rich(64)
        s = slime(g, "mage", stars=3)
        s.level = 30
        plain = power.total_power(s)
        s.attuned, s.mastery_xp = ["fire"], {"fire": 200}
        s.style_xp["magic"] = 200
        s.class_prof = 100
        more = power.total_power(s)
        self.assertGreater(more["parts"]["mastery"], 0)
        self.assertGreater(more["parts"]["styles"], 0)
        self.assertGreater(more["parts"]["proficiency"], plain["parts"]["proficiency"])
        s.morale = 0
        low = power.total_power(s)
        self.assertLess(low["multiplier"], more["multiplier"])
        self.assertLess(low["total"], more["total"])

    def test_the_display_number_runs_from_001_to_999(self):
        self.assertEqual(power.display(0), 1)
        self.assertEqual(power.display(-5), 1)
        self.assertEqual(power.display(10 ** 9), 999)
        self.assertEqual(power.display(config.POWER_DISPLAY_MAX), 999)
        self.assertLess(power.display(30), power.display(500))
        self.assertLess(power.display(500), power.display(5000))
        g = rich(66)
        weak = slime(g, "mage", stars=1)
        self.assertLessEqual(power.display(power.total_power(weak)["total"]), 60)

    def test_the_snapshot_exposes_the_breakdown(self):
        from slime_gacha.webapi import snapshot
        g = rich(65)
        slime(g, "mage")
        g.detail_id = g.slimes()[0].id                      # the open card gets the full view; the others a slim one
        v = snapshot(g)["slimes"][0]
        self.assertEqual(set(v["power_parts"]), {"stats", "skills", "attributes", "mastery", "styles", "proficiency"})
        self.assertGreater(v["power"], 0)
        self.assertTrue(1 <= v["power_tag"] <= 999)


if __name__ == "__main__":
    unittest.main()
