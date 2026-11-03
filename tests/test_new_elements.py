"""The tier-3 elements that mix a tier-2 element with one more basic (mist, geyser, ash, clay, glass, quicksand, glacier,
thunderstone) and the rule that every fusable element has spell forms."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import elements, spells
from slime_gacha.abilities import get_ability

NEW = {"mist": ("steam", "wind", {"fire", "water", "wind"}), "geyser": ("steam", "earth", {"fire", "water", "earth"}),
       "ash": ("lava", "wind", {"fire", "earth", "wind"}), "clay": ("mud", "fire", {"water", "earth", "fire"}),
       "glass": ("sand", "fire", {"earth", "wind", "fire"}), "quicksand": ("sand", "water", {"earth", "wind", "water"}),
       "glacier": ("ice", "water", {"water", "wind"}), "thunderstone": ("lightning", "earth", {"fire", "wind", "earth"})}


class TestNewElements(unittest.TestCase):
    def test_each_recipe_makes_a_tier_three_element_from_the_right_basics(self):
        for key, (a, b, comps) in NEW.items():
            e = elements.combine(a, b)
            self.assertIsNotNone(e, key)
            self.assertEqual((e.key, e.tier, set(e.components)), (key, 3, comps))
            self.assertIs(elements.combine(b, a), e)                      # the order does not matter

    def test_no_pair_makes_two_things_and_every_result_is_unique(self):
        results = list(elements.RECIPES.values())
        self.assertEqual(len(results), len(set(results)))
        self.assertGreaterEqual(len(results), 21)

    def test_every_fused_element_has_two_spell_forms(self):
        for res in elements.RECIPES.values():
            self.assertIn(res, spells.MUTATIONS, res)
            self.assertEqual(len(spells.MUTATIONS[res]), 2, res)

    def test_a_three_basic_element_needs_all_three_mastered(self):
        self.assertEqual(elements.effective_mastery({"fire": 6, "water": 6, "wind": 2}, "mist"), 2)
        self.assertEqual(elements.effective_mastery({"fire": 6, "water": 6}, "mist"), 0)
        self.assertEqual(elements.effective_mastery({"water": 5, "wind": 4}, "glacier"), 4)       # glacier is only water and wind

    def test_fusing_a_steam_spell_with_a_wind_spell_makes_a_mist_spell_that_mutates(self):
        steam = spells.design_fusion(get_ability("ember"), get_ability("water_jet"))
        self.assertEqual(steam.element, "steam")
        mist = spells.design_fusion(steam, get_ability("gust"))
        self.assertEqual((mist.element, mist.tier), ("mist", 3))
        self.assertEqual(len(spells.mutation_levels(mist)), 2)
        self.assertGreater(spells.mutate(mist, 8).power, mist.power)

    def test_the_wheel_still_works_through_the_components(self):
        self.assertEqual(elements.effectiveness("ash", "earth"), elements.effectiveness("wind", "earth"))   # ash holds wind


if __name__ == "__main__":
    unittest.main()
