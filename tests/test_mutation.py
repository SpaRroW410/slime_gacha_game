"""Spell mutation: fused spells change form as the caster's mastery of the spell's element grows."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, elements, spells
from slime_gacha.abilities import get_ability
from slime_gacha.battle import BattleSystem
from slime_gacha.webapi import ability_view
from tests.test_fx import mk


def lava():
    ab = spells.design_fusion(get_ability("ember"), get_ability("rock_toss"))
    spells.register_custom(ab)
    return ab


class TestForms(unittest.TestCase):
    def test_every_fused_element_has_two_forms_and_basic_spells_have_none(self):
        for key in ("steam", "lava", "lightning", "mud", "ice", "sand", "plasma", "storm", "obsidian", "inferno",
                    "blizzard", "crystal", "sandstorm"):
            self.assertIn(key, spells.MUTATIONS)
            self.assertEqual(len(spells.MUTATIONS[key]), 2)
        self.assertEqual(spells.mutation_levels(get_ability("ember")), [])
        self.assertIs(spells.mutate(get_ability("ember"), 8), get_ability("ember"))

    def test_stages_come_at_set_mastery_levels(self):
        ab = lava()                                           # tier 2: needs mastery 3
        self.assertEqual(spells.mutation_levels(ab), [4, 6])
        self.assertEqual([spells.mutation_stage(ab, m) for m in (3, 4, 5, 6, 8)], [0, 1, 1, 2, 2])
        self.assertIs(spells.mutate(ab, 3), ab)
        one, two = spells.mutate(ab, 4), spells.mutate(ab, 6)
        self.assertTrue(one.name.startswith("Awakened"))
        self.assertTrue(two.name.startswith("Ascendant"))
        self.assertGreater(two.power, one.power)
        self.assertGreater(one.power, ab.power)
        self.assertEqual(spells.mutation_levels(spells.design_fusion(ab, get_ability("water_jet")))[0], 6)   # tier 3 needs 5

    def test_a_later_form_replaces_the_earlier_effect_instead_of_stacking(self):
        ab = lava()
        two = spells.mutate(ab, 6)
        bleeds = [f for f in two.fx if f[0] == "bleed"]
        self.assertEqual(len(bleeds), 1)
        self.assertGreater(bleeds[0][2], 0.25)

    def test_healing_fusions_become_purifying(self):
        ab = spells.design_fusion(get_ability("rain_mend"), get_ability("stone_skin"))   # water + earth: heal + guard
        self.assertIn(ab.kind, ("heal", "guard"))
        self.assertTrue(any(f[0] == "cleanse" for f in spells.mutate(ab, 8).fx))

    def test_view_lists_the_forms(self):
        v = ability_view(lava())
        self.assertEqual([f["mastery"] for f in v["forms"]], [4, 6])


class TestInBattle(unittest.TestCase):
    def cast(self, mastery):
        ab = lava()
        bs = BattleSystem(random.Random(2))
        a, t = mk("A", "party", abilities=(ab.key,)), mk("T", "foes", hp=2000)
        a.mastery = {"fire": mastery, "earth": mastery}
        bs.choose_ability = lambda *x: ab
        log = []
        bs._turn(a, [a, t], log)
        return t, log

    def test_a_high_mastery_caster_burns_the_target(self):
        t, _ = self.cast(3)
        self.assertEqual(len(t.bleed), 0)
        t, log = self.cast(4)
        self.assertEqual(len(t.bleed), 1)
        self.assertTrue(any("Awakened" in l for l in log))

    def test_weakest_component_decides(self):
        ab = lava()
        bs = BattleSystem(random.Random(2))
        a, t = mk("A", "party", abilities=(ab.key,)), mk("T", "foes", hp=2000)
        a.mastery = {"fire": 8, "earth": 2}
        bs.choose_ability = lambda *x: ab
        bs._turn(a, [a, t], [])
        self.assertEqual(len(t.bleed), 0)


if __name__ == "__main__":
    unittest.main()
