import random
import unittest

from slime_gacha import config, keeper
from slime_gacha.errors import InvalidAction
from slime_gacha.game import Game


def mk(seed=3, n=6):
    g = Game(seed)
    g.wallet.add_many({"white_gel": 100000, "essence": 1000, "food": 500, "purple_gel": 50})
    g.pull(n, "white_gel")
    return g


def level_up(g, to):
    while g.keeper.level < to:
        g.keeper.gain(keeper.xp_to_next(g.keeper.level), "x", g.day)


class TestKeeperLevels(unittest.TestCase):
    def test_four_branches_sixteen_skills_four_actives(self):
        self.assertEqual(len(keeper.BRANCHES), 4)
        self.assertEqual(len(keeper.SKILLS), 16)
        self.assertEqual(len(keeper.ACTIVES), 4)
        for b in keeper.BRANCHES:
            self.assertEqual(sum(1 for s in keeper.SKILLS.values() if s.branch == b), 4)
        for a in keeper.ACTIVES.values():
            self.assertIn(a.needs, keeper.SKILLS)

    def test_xp_curve_rises(self):
        self.assertLess(keeper.xp_to_next(1), keeper.xp_to_next(10))

    def test_levelling_gives_points_and_messages(self):
        k = keeper.Keeper()
        self.assertEqual(k.points, 0)
        msgs = k.gain(keeper.xp_to_next(1), "x", 0)
        self.assertEqual(k.level, 2)
        self.assertEqual(k.points, 1)
        self.assertTrue(any("level 2" in m for m in msgs))

    def test_bonus_point_every_five_levels(self):
        k = keeper.Keeper()
        k.level = 5
        self.assertEqual(k.points, 4 + 1)

    def test_daily_caps(self):
        k = keeper.Keeper()
        k.gain(30, "care", 0, cap=10)
        self.assertEqual(k.total_xp, 10)
        k.gain(30, "care", 0, cap=10)
        self.assertEqual(k.total_xp, 10)
        k.gain(30, "care", 1, cap=10)                           # a new day
        self.assertEqual(k.total_xp, 20)

    def test_max_level(self):
        k = keeper.Keeper()
        k.level = config.KEEPER_MAX_LEVEL
        self.assertEqual(k.gain(999, "x", 0), [])

    def test_titles(self):
        self.assertEqual(keeper.title(1), "Novice Keeper")
        self.assertEqual(keeper.title(30), "Archkeeper")


class TestSkills(unittest.TestCase):
    def test_need_points_and_level(self):
        k = keeper.Keeper()
        with self.assertRaises(InvalidAction):
            k.learn("gentle_hands")
        k.level = 2
        k.learn("gentle_hands")
        self.assertEqual(k.rank("gentle_hands"), 1)
        with self.assertRaises(InvalidAction):
            k.learn("gentle_hands")                             # no points left
        k.level = 3
        with self.assertRaises(InvalidAction):
            k.learn("gentle_hands")                             # rank 2 needs level 4
        k.level = 8
        k.learn("gentle_hands")
        k.learn("gentle_hands")
        with self.assertRaises(InvalidAction):
            k.learn("gentle_hands")                             # max rank

    def test_higher_skills_need_higher_levels(self):
        k = keeper.Keeper()
        k.level = 3
        k.ranks = {}
        with self.assertRaises(InvalidAction):
            k.learn("midwife")

    def test_unknown(self):
        with self.assertRaises(InvalidAction):
            keeper.Keeper().learn("nope")

    def test_actives_unlock_with_the_branch_skill(self):
        k = keeper.Keeper()
        self.assertFalse(k.unlocked("rally"))
        k.ranks["battle_cry"] = 1
        self.assertTrue(k.unlocked("rally"))
        self.assertTrue(k.ready("rally", 0))
        k.cooldowns["rally"] = 5
        self.assertFalse(k.ready("rally", 4))
        self.assertTrue(k.ready("rally", 5))

    def test_persistence(self):
        g = mk()
        g.keeper.xp, g.keeper.level = 12, 6
        g.keeper.ranks = {"lucky_charm": 2}
        g.keeper.cooldowns = {"favor": 9}
        g._apply_keeper()
        h = Game.from_dict(g.to_dict())
        self.assertEqual((h.keeper.xp, h.keeper.level, h.keeper.ranks, h.keeper.cooldowns),
                         (12, 6, {"lucky_charm": 2}, {"favor": 9}))
        self.assertAlmostEqual(h.gacha.luck, 1.2)


class TestEffects(unittest.TestCase):
    def test_actions_earn_xp(self):
        g = mk()
        g.keeper.earned = {}
        x = g.keeper.total_xp
        g.pet(g.slimes()[0].id)
        self.assertGreater(g.keeper.total_xp, x)
        g.keeper.earned = {}
        x = g.keeper.total_xp
        g.pull(1, "white_gel")
        self.assertGreater(g.keeper.total_xp, x)

    def test_level_up_reaches_the_journal(self):
        g = mk()
        g.keeper.earned = {}
        g.keeper.xp = keeper.xp_to_next(1) - 1
        g.pull(1, "white_gel")
        self.assertEqual(g.keeper.level, 2)
        self.assertTrue(any("level 2" in j for j in g.journal))

    def test_gentle_hands(self):
        a, b = mk(), mk()
        b.keeper.ranks["gentle_hands"] = 3
        for g in (a, b):
            s = g.slimes()[0]
            s.traits = []
            s.emotions = {}
            g.pet(s.id)
        self.assertGreater(b.slimes()[0].emotions["joy"], a.slimes()[0].emotions["joy"] * 2)

    def test_lucky_charm_raises_rare_odds(self):
        g = mk()
        n = lambda: sum(g.gacha.roll_rarity() != "common" for _ in range(8000))
        g.gacha.rng = random.Random(1)
        base = n()
        g.keeper.ranks["lucky_charm"] = 3
        g._apply_keeper()
        g.gacha.rng = random.Random(1)
        self.assertGreater(n(), base * 1.15)

    def test_fortunes_favor_is_used_up_by_the_next_pull(self):
        g = mk()
        g.keeper.ranks["lucky_charm"] = 1
        g.keeper.level = 5
        g.keeper_use("favor")
        self.assertTrue(g.gacha.favor)
        g.pull(1, "white_gel")
        self.assertFalse(g.gacha.favor)
        with self.assertRaises(InvalidAction):
            g.keeper_use("favor")                               # cooldown

    def test_rally_and_soothe(self):
        g = mk()
        g.keeper.ranks.update(battle_cry=1, gentle_hands=1)
        g.keeper_use("rally")
        s = g.slimes()[0]
        self.assertGreater(s.emotions["determination"], 20)
        s.emotions["sadness"] = 80.0
        g.keeper_use("soothe")
        self.assertLess(s.emotions["sadness"], 60)
        with self.assertRaises(InvalidAction):
            g.keeper_use("rally")
        g.tick(24)
        g.keeper_use("rally")                                   # a day later

    def test_locked_ability(self):
        with self.assertRaises(InvalidAction):
            mk().keeper_use("rally")

    def test_bond_night(self):
        g = mk()
        g.keeper.ranks["matchmaker"] = 1
        a, b = g.slimes()[:2]
        before = g.social.bond(a, b)
        g.social.compat = lambda x, y: 10
        g.keeper_use("bond_night")
        self.assertGreater(g.social.bond(a, b), before)

    def test_matchmaker_speeds_bonds(self):
        g = mk()
        a, b = g.slimes()[:2]
        g.social.add_bond(a, b, 10)
        base = g.social.bond(a, b)
        g.social.bonds.clear()
        g.keeper.ranks["matchmaker"] = 2
        g._apply_keeper()
        g.social.add_bond(a, b, 10)
        self.assertAlmostEqual(g.social.bond(a, b), base * 1.5)

    def test_thrifty_cuts_building_costs(self):
        g = mk()
        full = g.buildings.next_cost("library")
        g.keeper.ranks["thrifty"] = 3
        g._apply_keeper()
        cut = g.buildings.next_cost("library")
        self.assertLess(cut["white_gel"], full["white_gel"] * 0.9)

    def test_peacemaker_and_quartermaster(self):
        g = mk()
        g.keeper.ranks.update(peacemaker=3, quartermaster=2)
        g._apply_keeper()
        self.assertAlmostEqual(g.conflicts.calm, 0.7)
        self.assertAlmostEqual(g.share, 0.76)

    def test_stonecutter_and_appraiser(self):
        from slime_gacha import items
        g = mk()
        it = items.Item(1, "iron_sword", stars=4, level=8)
        g.vault[1] = it
        base = it.salvage_yield()["scrap"]
        g.keeper.ranks["appraiser"] = 3
        g.salvage_item(1)
        self.assertGreater(g.wallet.get("scrap"), base)

    def test_field_medic_heals_in_camp(self):
        g = mk()
        s = g.slimes()[0]
        s.hp = 1
        g.keeper.ranks["field_medic"] = 3
        g.conflicts.tick = lambda *a, **k: None
        s.state = "idle"
        g._camp([s], max_hours=2)
        self.assertGreater(s.hp, s.max_hp * 0.2)

    def test_battle_cry_starts_fights_fired_up(self):
        g = mk()
        g.keeper.ranks["battle_cry"] = 2
        party = g.slimes()[:2]
        from slime_gacha import dungeon
        for s in party:
            s.emotions = {}
            s.traits = []
        g._run_battle(party, dungeon.grind_wave(5, 3, 2, random.Random(1), dungeon.pit_theme(1, 0)), permadeath=False)
        self.assertTrue(all(s.emotions.get("determination", 0) > 0 for s in party))

    def test_mediation_skill(self):
        g = mk()
        a, b = g.slimes()[:2]
        base = g.conflicts.mediate_chance(a, b, "talk")
        self.assertLessEqual(base, 0.95)


if __name__ == "__main__":
    unittest.main()
