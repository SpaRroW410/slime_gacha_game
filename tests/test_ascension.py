import random
import unittest

from slime_gacha import ascension, config
from slime_gacha.errors import InvalidAction, NotEnoughResources
from slime_gacha.game import Game


def mk(seed=3, n=6):
    g = Game(seed)
    g.wallet.add("white_gel", 100000)
    g.pull(n, "white_gel")
    return g


class TestRarityAndStars(unittest.TestCase):
    def test_five_rarities_in_order(self):
        self.assertEqual(config.RARITIES, ["common", "uncommon", "rare", "epic", "legendary"])
        self.assertAlmostEqual(sum(config.RARITY_RATES.values()), 100)

    def test_rarity_ladder_costs(self):
        g = mk()
        s = g.slimes()[0]
        s.rarity, s.stars = "common", 1
        base = s.max_stats()["atk"]
        paid = []
        for want, cost in (("uncommon", 10), ("rare", 100), ("epic", 1000), ("legendary", 10000)):
            before = g.wallet.get("white_gel")
            g.ascend_slime_rarity(s.id)
            paid.append(before - g.wallet.get("white_gel"))
            self.assertEqual(s.rarity, want)
        self.assertEqual(paid, [10, 100, 1000, 10000])
        self.assertGreater(s.max_stats()["atk"], base * 2)
        with self.assertRaises(InvalidAction):
            g.ascend_slime_rarity(s.id)

    def test_rarity_needs_the_gel(self):
        g = mk()
        s = g.slimes()[0]
        s.rarity = "rare"
        g.wallet.add("white_gel", -g.wallet.get("white_gel") + 999)
        with self.assertRaises(NotEnoughResources):
            g.ascend_slime_rarity(s.id)                     # epic costs 1000
        self.assertEqual(s.rarity, "rare")

    def test_hp_grows_with_ascension(self):
        g = mk()
        s = g.slimes()[0]
        s.rarity, s.stars = "common", 1
        s.hp = s.max_hp
        old = s.max_hp
        g.ascend_slime_rarity(s.id)
        self.assertEqual(s.hp, s.max_hp)
        self.assertGreater(s.max_hp, old)

    def test_star_costs_in_stones(self):
        g = mk()
        s = g.slimes()[0]
        s.stars = 1
        for need, lv in ((10, 10), (100, 30), (1000, 60), (10000, 100)):
            s.level = lv
            g.wallet.add("stone_common", need - 1)
            with self.assertRaises(InvalidAction):
                g.ascend_slime_star(s.id)
            g.wallet.add("stone_common", 1)
            g.ascend_slime_star(s.id)
            self.assertEqual(g.wallet.get("stone_common"), 0)
        self.assertEqual(s.stars, 5)
        with self.assertRaises(InvalidAction):
            g.ascend_slime_star(s.id)

    def test_stone_change_and_merging(self):
        g = mk()
        s = g.slimes()[0]
        s.stars, s.level = 2, 100                           # costs 100 equivalents
        g.wallet.add("stone_uncommon", 1)                   # worth exactly 100 commons
        g.ascend_slime_star(s.id)
        self.assertEqual(ascension.stone_total(g.wallet), 0)
        s.stars = 1                                         # costs 10: paying with an uncommon gives change
        g.wallet.add("stone_uncommon", 1)
        g.ascend_slime_star(s.id)
        self.assertEqual(g.wallet.get("stone_common"), 90)
        self.assertEqual(g.wallet.get("stone_uncommon"), 0)
        g.wallet.add("stone_common", 250)
        g.merge_stone_rarity("common")
        self.assertEqual((g.wallet.get("stone_uncommon"), g.wallet.get("stone_common")), (3, 40))
        with self.assertRaises(InvalidAction):
            g.merge_stone_rarity("legendary")
        g.wallet.add("stone_uncommon", 97)
        g.merge_stone_rarity("uncommon")
        self.assertEqual(g.wallet.get("stone_rare"), 1)

    def test_stars_need_their_level_and_rarity_resets_them(self):
        g = mk()
        s = g.slimes()[0]
        s.rarity, s.stars, s.level = "common", 1, 9
        g.wallet.add("stone_common", 20000)
        for stars, lv in ((1, 10), (2, 30), (3, 60), (4, 100)):
            s.stars, s.level = stars, lv - 1
            with self.assertRaises(InvalidAction):
                g.ascend_slime_star(s.id)
            s.level = lv
            g.ascend_slime_star(s.id)
            self.assertEqual(s.stars, stars + 1)
        self.assertEqual(s.stars, 5)
        g.wallet.add("white_gel", 100)
        g.ascend_slime_rarity(s.id)
        self.assertEqual((s.rarity, s.stars), ("uncommon", 1))     # stars (and their attributes) start over

    def test_star_requirements_and_attributes_scale_with_rarity(self):
        from slime_gacha import attributes, config
        g = mk()
        s = g.slimes()[0]
        s.rarity, s.stars = "legendary", 2
        self.assertEqual(ascension.star_level(s), 12)               # common would need 30
        self.assertEqual(ascension.star_cost(s), 400)               # 100 x4
        s.level = 11
        g.wallet.add("stone_common", 400)
        with self.assertRaises(InvalidAction):
            g.ascend_slime_star(s.id)
        s.level = 12
        g.ascend_slime_star(s.id)
        self.assertEqual(s.stars, 3)
        s.rarity = "common"
        low = attributes.star_attributes(s)[0]["value"]
        s.rarity = "legendary"
        self.assertAlmostEqual(attributes.star_attributes(s)[0]["value"], low * 3, places=2)

    def test_busy_slimes_cannot_ascend(self):
        g = mk()
        s = g.slimes()[0]
        s.state = "hunting"
        with self.assertRaises(InvalidAction):
            g.ascend_slime_rarity(s.id)


class TestMerge(unittest.TestCase):
    def test_share_curve(self):
        self.assertAlmostEqual(ascension.merge_share(0.0), 0.20)
        self.assertAlmostEqual(ascension.merge_share(0.10), 0.18)
        self.assertAlmostEqual(ascension.merge_share(0.5), 0.10)
        self.assertAlmostEqual(ascension.merge_share(1.0), 0.01)
        self.assertAlmostEqual(ascension.merge_share(7.0), 0.01)

    def test_merge_gives_collected_xp_and_a_fifth_of_stats(self):
        g = mk()
        t, d = g.slimes()[:2]
        d.total_xp = 400
        before = t.max_stats()
        dcore = d.core_stats()
        t.merge_bonus = {}
        xp = g.merge_preview(t.id, d.id)
        self.assertLessEqual(xp, int(400 * 1.25))
        self.assertGreater(xp, int(400 * 0.75))
        g.merge(t.id, d.id)
        for k in ("atk", "hp"):
            self.assertAlmostEqual(t.merge_bonus[k], dcore[k] * 0.2, delta=0.02)
        self.assertGreater(t.max_stats()["hp"], before["hp"])

    def test_diminishing_returns_and_no_cap(self):
        g = mk(n=2)
        t = g.slimes()[0]
        gains = []
        for i in range(40):
            d = g.gacha.make_slime("common", stars=1)
            d.id = 500 + i
            g.roster[d.id] = d
            before = t.merge_bonus.get("hp", 0.0)
            g.merge(t.id, d.id)
            gains.append(t.merge_bonus["hp"] - before)
            for s in g.slimes():
                s.hp = max(s.hp, 1)
        self.assertGreater(gains[0], gains[-1] * 3)
        self.assertGreater(t.merge_bonus["hp"], t.core_stats()["hp"])    # no cap: bonus beyond +100%

    def test_merge_bonus_persists(self):
        g = mk()
        t, d = g.slimes()[:2]
        g.merge(t.id, d.id)
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.slime(t.id).merge_bonus, t.merge_bonus)
        self.assertEqual(h.slime(t.id).max_stats(), t.max_stats())


class TestChamber(unittest.TestCase):
    def test_yield_scales_with_rarity_and_stars(self):
        g = mk()
        a, b = g.gacha.make_slime("common", stars=1), g.gacha.make_slime("legendary", stars=5)
        ya, yb = ascension.chamber_yield(a, 1), ascension.chamber_yield(b, 1)
        self.assertGreater(yb["white_gel"], ya["white_gel"] * 1000)
        eq = lambda y: sum(v * ascension.stone_value(k[6:]) for k, v in y.items() if k.startswith("stone_"))
        self.assertGreater(eq(yb), eq(ya))
        self.assertGreater(ascension.chamber_yield(a, 5)["white_gel"], ya["white_gel"])

    def test_destroy_pays_out_and_costs_morale(self):
        g = mk()
        s = g.slimes()[0]
        s.stars, s.rarity = 3, "rare"
        it = g.new_item()
        g.equip_item(s.id, it.uid)
        gel, n, stress = g.wallet.get("white_gel"), len(g.roster), g.sacrifice_stress
        y = g.chamber_preview(s.id)
        g.destroy_slime(s.id)
        self.assertEqual(len(g.roster), n - 1)
        self.assertEqual(g.wallet.get("white_gel"), gel + y["white_gel"])
        self.assertGreater(ascension.stone_total(g.wallet), 0)
        self.assertGreater(g.sacrifice_stress, stress)
        self.assertIn(it.uid, g.vault)                       # its relic came home

    def test_busy_slime_is_safe(self):
        g = mk()
        s = g.slimes()[0]
        s.in_dungeon = "main"
        with self.assertRaises(InvalidAction):
            g.destroy_slime(s.id)


class TestQuarry(unittest.TestCase):
    def test_stone_rolls(self):
        rng = random.Random(1)
        n = 5000
        got = {}
        for _ in range(n):
            for k, v in ascension.roll_stone(rng).items():
                got[k] = got.get(k, 0) + 1
        self.assertGreater(got["stone_common"], n * 0.94)
        self.assertGreater(got.get("stone_uncommon", 0), 40)
        self.assertLess(got.get("stone_rare", 0), 60)

    def test_quarry_yields_stones_not_relics(self):
        g = mk(seed=5, n=7)
        for s in g.slimes():
            s.level, s.stage = 40, 2
        g.conflicts.tick = lambda *a, **k: None
        for _ in range(3):
            for s in g.slimes():
                s.state, s.hp = "idle", s.max_hp
                s.needs.v.update({k: 100.0 for k in s.needs.v})
            g.quarry([s.id for s in g.slimes()[:5]], 10)
        self.assertGreater(ascension.stone_total(g.wallet), 0)
        self.assertEqual(len(g.vault), 0)
        self.assertTrue(all(s.in_dungeon == "" for s in g.slimes()))

    def test_party_size_rules(self):
        g = mk(n=7)
        with self.assertRaises(InvalidAction):
            g.quarry([], 1)
        with self.assertRaises(InvalidAction):
            g.quarry([s.id for s in g.slimes()[:6]], 1)

    def test_boss_hoards_hold_stones(self):
        # the pile is tracked by the wallet; a quick structural check of the side-drop helper
        g = mk()
        log = []
        random.seed(0)
        g.rng = random.Random(1)
        for _ in range(60):
            g._stone_side_drop("grind", 5, log)
        self.assertGreater(g.wallet.get("stone_common"), 0)


class TestChamberBuilding(unittest.TestCase):
    def test_building_levels(self):
        g = mk()
        self.assertEqual(g.buildings.level("chamber"), 1)
        g.wallet.add_many({"white_gel": 10**6, "essence": 10**4, "purple_gel": 99})
        g.upgrade_building("chamber")
        self.assertEqual(g.buildings.level("chamber"), 2)


if __name__ == "__main__":
    unittest.main()
