"""Enemy weaknesses and resistances beyond one element, and elemental floors."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import bestiary, config, dungeon, elements
from slime_gacha.abilities import get_ability
from slime_gacha.battle import BattleSystem, Combatant
from tests.test_fx import mk, use


class TestMatchup(unittest.TestCase):
    def test_extra_weakness_and_resistance_stack_on_the_element_cycle(self):
        adv, dis = config.ELEMENT_ADVANTAGE, config.ELEMENT_DISADVANTAGE
        self.assertEqual(elements.matchup("fire", ""), 1.0)
        self.assertAlmostEqual(elements.matchup("fire", "", weak=("fire",)), adv)
        self.assertAlmostEqual(elements.matchup("fire", "", resists=("fire",)), dis)
        self.assertAlmostEqual(elements.matchup("water", "fire", weak=("water",)), 2.0)       # 1.5 x 1.5, capped
        self.assertAlmostEqual(elements.matchup("lightning", "", weak=("wind",)), adv)       # through components
        self.assertEqual(elements.matchup("", "fire", weak=("fire",)), 1.0)

    def test_families_carry_several_resistances(self):
        undead = next(m for m in bestiary.MONSTERS if m.family == "undead")
        e = bestiary.build_enemy(undead, 10)
        self.assertIn("fire", e.weak)
        self.assertGreaterEqual(len(e.resists), 2)
        plain = bestiary.build_enemy(next(m for m in bestiary.MONSTERS if m.family == "goblin"), 10)
        self.assertEqual((plain.weak, plain.resists), ((), ()))


class TestInBattle(unittest.TestCase):
    def hit(self, weak=(), resists=()):
        bs = BattleSystem(random.Random(1))
        a = mk("A", "party", mag=100)
        t = Combatant("T", "x", "foes", dict(hp=10 ** 6, atk=10, defense=0, mag=10, spd=10), 10 ** 6, ["splat"], weak=weak, resists=resists)
        before = t.hp
        use(bs, a, get_ability("ember"), [t], [a, t], [])
        return before - t.hp

    def test_a_weak_foe_takes_more_and_a_resistant_one_less(self):
        base = self.hit()
        self.assertGreater(self.hit(weak=("fire",)), base * 1.3)
        self.assertLess(self.hit(resists=("fire",)), base * 0.85)


class TestElementalFloors(unittest.TestCase):
    def test_elemental_floors_are_every_sixth_from_three_and_never_boss(self):
        floors = [f for f in range(1, dungeon.MAX_FLOOR + 1) if dungeon.is_elemental_floor(f)]
        self.assertIn(3, floors)
        self.assertIn(9, floors)
        self.assertTrue(all(not dungeon.is_boss_floor(f) for f in floors))
        for f in floors:
            info = dungeon.floor_info(5, f, 5)
            self.assertIn(info.affinity, elements.BASICS)
        self.assertEqual(dungeon.floor_info(5, 4, 5).affinity, "")

    def test_the_terrain_favours_the_floors_element(self):
        for f in (3, 9, 21):
            info = dungeon.floor_info(11, f, 5)
            el = info.affinity
            self.assertGreaterEqual(info.terrain.boosts[el], dungeon.ELEMENTAL_BOOST)
            foe = next(a for a, d in elements.BEATS.items() if d == el)
            self.assertLessEqual(info.terrain.dampens[foe], dungeon.ELEMENTAL_DAMPEN)
            self.assertIn(elements.get(el).name, info.terrain.name)

    def test_floors_stay_fixed_and_intel_names_the_affinity_and_resistances(self):
        a = dungeon.floor_info(3, 9, 5)
        b = dungeon.floor_info(3, 9, 5)
        self.assertEqual([e.key for e in a.enemies], [e.key for e in b.enemies])
        low = dungeon.intel_lines(3, 9, 25, 5)
        self.assertTrue(any("elemental floor" in l for l in low))
        full = dungeon.intel_lines(3, 9, 100, 5)
        self.assertTrue(any(l.startswith("weak to:") and "resists:" in l for l in full))
        plain = dungeon.intel_lines(3, 4, 100, 5)
        self.assertFalse(any("elemental floor" in l for l in plain))


if __name__ == "__main__":
    unittest.main()
