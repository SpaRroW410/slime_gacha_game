"""Mages are pulled at 3 stars or more; the training facility raises class proficiency (no stars needed)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from slime_gacha.errors import InvalidAction
from slime_gacha.game import Game
from slime_gacha.webapi import Session
from tests.test_delves import rich, party, members


class TestMagePulls(unittest.TestCase):
    def test_a_rolled_mage_is_never_below_three_stars_but_explicit_stars_are_respected(self):
        g = rich(101)
        stars = [g.gacha.make_slime("common", "mage").stars for _ in range(300)]
        self.assertGreaterEqual(min(stars), config.SCHOLAR_MIN_STARS)
        self.assertEqual(g.gacha.make_slime("common", "mage", stars=1).stars, 1)      # (tests / ascension reset)
        self.assertLess(min(g.gacha.make_slime("common", "barbarian").stars for _ in range(300)), 3)   # others unchanged

    def test_pulling_gives_three_star_mages(self):
        g = rich(102)
        mages = [s for s in g.pull(60, "white_gel") if s.archetype == "mage"]
        self.assertTrue(mages)
        self.assertTrue(all(m.stars >= config.SCHOLAR_MIN_STARS for m in mages))


class TestTrainingFacility(unittest.TestCase):
    def mk(self, seed=103, cls="mage", stars=1):
        g = rich(seed)
        s = g.gacha.make_slime("common", cls, stars=stars)
        g.roster[s.id] = s
        s.class_prof = 40.0
        return g, s

    def test_a_drill_takes_time_costs_gel_and_raises_proficiency(self):
        g, s = self.mk()
        white = g.wallet.get("white_gel")
        g.drill(s.id, "magic")
        self.assertEqual((s.state, s.task["kind"]), ("studying", "drill"))
        self.assertEqual(g.wallet.get("white_gel"), white - config.DRILL_COST["white_gel"])
        ev = []
        for _ in range(config.DRILL_TICKS):
            ev += g.tick(1)
        self.assertEqual(s.state, "idle")
        self.assertGreater(s.class_prof, 41)
        self.assertEqual(s.prof_idle, 0)
        self.assertTrue(any("drilling" in e for e in ev))

    def test_no_stars_needed_unlike_the_library(self):
        g, s = self.mk(stars=1)                                   # a mage that has just risen in rarity
        with self.assertRaises(InvalidAction):
            g.study(s.id, "fire")                                 # the Library still needs three stars
        g.drill(s.id, "magic")                                    # the training facility does not

    def test_the_gain_shrinks_near_mastery_and_grows_with_the_training_grounds(self):
        g, s = self.mk()
        lo = g.academy.drill_gain(s, "magic")
        s.class_prof = 95
        self.assertLess(g.academy.drill_gain(s, "magic"), lo)
        s.class_prof = 40
        g.buildings.levels["training_grounds"] = 3
        self.assertGreater(g.academy.drill_gain(s, "magic"), lo)

    def test_only_their_own_discipline_counts_fully(self):
        g, s = self.mk()
        self.assertEqual(g.academy.drill_gain(s, "sword"), 0.0)
        g.drill(s.id, "sword")
        for _ in range(config.DRILL_TICKS):
            g.tick(1)
        self.assertEqual(s.class_prof, 40.5)                      # a little general practice only

    def test_a_hybrid_drills_its_second_discipline_for_the_second_proficiency(self):
        g, s = self.mk()
        s.spec, s.spec_disc, s.spec_prof = "spellknight", "sword", 30.0
        self.assertGreater(g.academy.drill_gain(s, "sword"), 0)
        g.drill(s.id, "sword")
        for _ in range(config.DRILL_TICKS):
            g.tick(1)
        self.assertGreater(s.spec_prof, 30)
        self.assertEqual(s.class_prof, 40)

    def test_busy_or_tired_slimes_cannot_drill_and_parties_can(self):
        g, s = self.mk()
        s.in_dungeon = "grind"
        with self.assertRaises(InvalidAction):
            g.drill(s.id, "magic")
        pid = party(g)
        out = g.drill_party(pid, "sword")
        self.assertEqual(len(out), g.parties.size)
        self.assertTrue(all("heads to" in o for o in out))

    def test_web_state_and_commands(self):
        se = Session()
        se.new_game(104)
        g = se.game
        g.wallet.add("white_gel", 50)
        s = g.gacha.make_slime("common", "mage")
        g.roster[s.id] = s
        r = se.call("drill", dict(id=s.id, discipline="magic"))
        self.assertTrue(r["ok"])
        self.assertIn("Drilling", [a["label"] for a in r["state"]["away"]][0])
        self.assertTrue(r["state"]["drill"]["ticks"])
        self.assertIn("Mage", " ".join(next(d for d in r["state"]["disciplines"] if d["key"] == "magic")["feeds"]))
        self.assertFalse(se.call("drill", dict(id=s.id, discipline="nope"))["ok"])


if __name__ == "__main__":
    unittest.main()


class TestScholarsAndPausedMastery(unittest.TestCase):
    def test_medics_and_necromancers_are_pulled_at_three_stars_too(self):
        g = rich(111)
        for cls in ("mage", "medic", "necromancer"):
            self.assertGreaterEqual(min(g.gacha.make_slime("common", cls).stars for _ in range(200)), 3, cls)
        self.assertLess(min(g.gacha.make_slime("common", "rogue").stars for _ in range(200)), 3)

    def _adept(self, g):
        s = g.gacha.make_slime("common", "mage", stars=5)
        g.roster[s.id] = s
        s.attuned = ["fire"]
        s.mastery_xp["fire"] = config.MASTERY_XP[7]               # level 8, the 5-star maximum
        s.stars = 5
        return s

    def test_rarity_ascension_keeps_earned_mastery_but_pauses_its_growth(self):
        from slime_gacha import elements
        g = rich(112)
        s = self._adept(g)
        self.assertEqual(elements.basic_level(s, "fire"), 8)
        g.wallet.add("white_gel", 100)
        g.ascend_slime_rarity(s.id)                                # stars back to 1
        self.assertEqual(s.stars, 1)
        self.assertEqual(elements.basic_level(s, "fire"), 8)       # not reset to 0
        self.assertEqual(elements.slime_mastery(s, "fire"), 8)     # and it still counts in battle
        self.assertTrue(elements.mastery_paused(s))
        self.assertEqual(elements.stars_to_resume(s), 5)
        xp = s.mastery_xp["fire"]
        elements.add_mastery_xp(s, "fire", 500)
        self.assertEqual(s.mastery_xp["fire"], xp)                 # paused: it neither grows nor shrinks
        with self.assertRaises(InvalidAction):
            g.study(s.id, "fire")                                  # needs 3 stars at all
        s.stars = 3
        self.assertTrue(elements.mastery_paused(s))                # cap 4 < level 8: still paused
        with self.assertRaises(InvalidAction):
            g.study(s.id, "fire")
        s.stars = 5
        self.assertFalse(elements.mastery_paused(s))

    def test_battles_use_the_kept_mastery(self):
        from slime_gacha.battle import BattleSystem
        g = rich(113)
        s = self._adept(g)
        g.wallet.add("white_gel", 100)
        g.ascend_slime_rarity(s.id)
        c = BattleSystem.from_slime(s)
        self.assertEqual(c.mastery.get("fire"), 8)

    def test_growth_resumes_when_the_stars_allow_it(self):
        from slime_gacha import elements
        g = rich(114)
        s = g.gacha.make_slime("common", "mage", stars=3)
        g.roster[s.id] = s
        s.attuned = ["fire"]
        s.mastery_xp["fire"] = config.MASTERY_XP[1]                # level 2, cap at 3 stars is 4
        elements.add_mastery_xp(s, "fire", 50)
        self.assertGreater(s.mastery_xp["fire"], config.MASTERY_XP[1])
