"""Combat resources (pools.py): stamina / mana / nature pools and action points (several actions a turn)."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, pools
from slime_gacha.abilities import get_ability
from slime_gacha.battle import ENEMIES, BattleSystem
from slime_gacha.game import Game
from tests.test_fx import mk


def slime(g, arch, level=20, rarity="common"):
    s = g.gacha.make_slime(rarity, arch, 1)
    s.level, s.class_prof = level, 100
    s.hp = s.max_hp
    g.roster[s.id] = s
    return s


class TestCosts(unittest.TestCase):
    def test_each_skill_burns_the_pool_of_its_kind(self):
        self.assertEqual(pools.pool_of(get_ability("smash")), "stamina")
        self.assertEqual(pools.pool_of(get_ability("spark")), "mana")
        self.assertEqual(pools.pool_of(get_ability("mend")), "mana")
        self.assertEqual(pools.pool_of(get_ability("flame_breath")), "nature")      # it carries an element
        self.assertEqual(pools.pool_of(get_ability("splat")), "")                   # the free fallbacks
        self.assertEqual(pools.pool_of(get_ability("defend")), "")

    def test_big_area_skills_cost_two_turns_of_points(self):
        for k in ("explosive_brew", "rampage", "blorp_blast"):
            self.assertEqual(pools.ap_cost(get_ability(k)), config.AP_MAX, k)
        self.assertEqual(pools.ap_cost(get_ability("splat")), config.AP_PER_TURN)
        self.assertEqual(pools.ap_cost(get_ability("defend")), config.AP_DEFEND)
        self.assertLess(pools.ap_cost(get_ability("flame_brand")), config.AP_PER_TURN)   # a buff leaves room for a blow
        self.assertGreater(pools.pool_cost(get_ability("mend")), pools.pool_cost(get_ability("spark")))  # healing costs more

    def test_cooldowns_are_cut_to_the_minimum(self):
        self.assertEqual(pools.cooldown(get_ability("spark")), 0)
        self.assertEqual(pools.cooldown(get_ability("explosive_brew")), 1)              # not twice in one turn
        self.assertEqual(pools.cooldown(get_ability("resurrection")), 99)               # once a fight stays so


class TestActionPoints(unittest.TestCase):
    def test_a_big_spell_waits_for_saved_points(self):
        bs = BattleSystem(random.Random(1))
        a = mk("A", "party", abilities=("explosive_brew",))
        foes = [mk(f"T{i}", "foes", hp=5000) for i in range(4)]
        ev = [a] + foes
        log = []
        bs._turn(a, ev, log)                                  # turn 1: 3 AP, the brew needs 6: it saves its points
        self.assertFalse(any("Explosive Brew" in l for l in log))
        self.assertEqual(a.ap, config.AP_PER_TURN)
        bs._turn(a, ev, log)                                  # turn 2: 6 AP: the brew lands on every foe
        self.assertEqual(sum("Explosive Brew" in l for l in log), 4)
        self.assertEqual(a.ap, 0)

    def test_saved_points_buy_two_actions_in_one_turn(self):
        bs = BattleSystem(random.Random(1))
        a, t = mk("A", "party"), mk("T", "foes", hp=5000)
        a.ap = config.AP_PER_TURN
        log = []
        bs._turn(a, [a, t], log)
        self.assertEqual(sum("uses Splat" in l for l in log), 2)

    def test_monsters_play_by_the_same_rules(self):
        c = BattleSystem.from_enemy(ENEMIES.get("parched_king"))
        self.assertEqual((c.stamina_max, c.mana_max, c.nature_max), (config.FOE_POOL,) * 3)
        self.assertEqual(c.ap, 0)


class TestPools(unittest.TestCase):
    def test_a_dry_caster_falls_back_to_the_free_bonk(self):
        bs = BattleSystem(random.Random(1))
        a, t = mk("A", "party", abilities=("spark",)), mk("T", "foes", hp=5000)
        a.mana_max, a.mana = 100.0, 100.0
        log = []
        bs._turn(a, [a, t], log)
        self.assertTrue(any("Spark" in l for l in log))
        self.assertEqual(a.mana, 100 - pools.pool_cost(get_ability("spark")))
        a.mana, log = 0.0, []
        bs._turn(a, [a, t], log)
        self.assertTrue(any("Splat" in l for l in log) and not any("Spark" in l for l in log))

    def test_defend_ends_the_turn_and_catches_breath(self):
        bs = BattleSystem(random.Random(1))
        a, t = mk("A", "party"), mk("T", "foes")
        a.mana_max, a.mana = 100.0, 0.0
        a.ap = 3
        bs._act(a, get_ability("defend"), [a], [a], [t], [a, t], [])
        bs.catch_breath(a, config.POOL_DEFEND)
        self.assertEqual(a.mana, 100 * config.POOL_DEFEND)
        self.assertEqual(a.ap, 3 - config.AP_DEFEND)

    def test_mana_is_carried_out_of_a_fight_and_back_in(self):
        g = Game(4)
        s = slime(g, "mage")
        self.assertEqual(s.mana, s.max_mana)
        c = g.battles.from_slime(s)
        self.assertEqual(c.mana, s.max_mana)
        self.assertEqual(c.nature, round(c.nature_max * config.NATURE_START, 1))   # nature: half full every fight
        g.battles.run([s], [ENEMIES.get("dust_bunny")] * 3)
        self.assertLess(s.mana_frac, 1.0)
        s.mana_frac = 0.2
        g._stamina_tick()
        self.assertGreater(s.mana_frac, 0.2)                               # it comes back by the hour, like stamina
        self.assertIn("mana_frac", s.to_dict())

    def test_casters_have_the_deepest_mana_and_druids_the_widest_nature(self):
        g = Game(4)
        mage, barb, druid = slime(g, "mage"), slime(g, "barbarian"), slime(g, "druid")
        self.assertGreater(mage.max_mana, 2 * barb.max_mana)
        self.assertGreater(pools.max_nature(druid), pools.max_nature(mage))

    def test_an_arcane_potion_refills_mana(self):
        g = Game(4)
        s = slime(g, "mage")
        s.mana_frac = 0.1
        g._drink(s, "arcane", 2)
        self.assertGreater(s.mana_frac, 0.5)


class TestSpars(unittest.TestCase):
    def test_two_healers_draw_and_a_fighter_outlasts_a_healer(self):
        g = Game(5)
        draws = sum(g.battles.duel(slime(g, "medic"), slime(g, "medic")).winner is None for _ in range(4))
        self.assertGreaterEqual(draws, 3)
        for _ in range(3):
            m, b = slime(g, "medic"), slime(g, "barbarian")
            rep = g.battles.duel(m, b)
            self.assertIs(rep.winner_slime, b)                             # the medic's mana runs dry first


class TestManual(unittest.TestCase):
    def _run(self):
        g = Game(6)
        s = slime(g, "barbarian", level=30)
        run = g.battles.start([s], [ENEMIES.get("hollow_knight")] * 2, manual=True)
        run.advance()
        return run

    def test_the_view_shows_points_costs_and_why_a_skill_is_out_of_reach(self):
        run = self._run()
        v = run.view()
        me = v["units"][v["waiting"]]
        self.assertEqual(me["ap"], config.AP_PER_TURN)
        self.assertIsNotNone(me["mana"])
        abil = {a["key"]: a for a in v["abilities"]}
        self.assertIn("defend", abil)
        self.assertEqual(abil["rampage"]["ap"], config.AP_MAX)
        self.assertFalse(abil["rampage"]["ready"])
        self.assertIn("AP", abil["rampage"]["short"])
        self.assertTrue(abil["splat"]["ready"])
        with self.assertRaises(ValueError):
            run.act("rampage")

    def test_ending_the_turn_saves_the_points(self):
        run = self._run()
        me = run.waiting
        run.end_turn()
        while run.waiting is not me and not run.done:
            run.auto_turn()
        if not run.done:
            self.assertEqual(me.ap, config.AP_MAX)                         # 3 saved + 3 new: rampage is in reach
            run.act("rampage")
            self.assertTrue(any("uses Rampage" in str(l) for l in run.log))


if __name__ == "__main__":
    unittest.main()
