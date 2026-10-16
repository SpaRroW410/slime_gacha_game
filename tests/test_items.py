import random
import unittest

from slime_gacha import config, dungeon, items
from slime_gacha.errors import InvalidAction, NotEnoughResources
from slime_gacha.game import Game


def mk(seed=3, n=6, level=5):
    g = Game(seed)
    g.wallet.add("white_gel", 5000)
    g.pull(n, "white_gel")
    for s in g.slimes():
        s.level = level
    return g


def legend(g, rarity="legendary", stars=5):
    s = g.gacha.make_slime(rarity, stars=stars)
    g.roster[s.id] = s
    return s


class TestItems(unittest.TestCase):
    def test_rates_are_harsher_than_the_gacha(self):
        for r in ("rare", "epic", "legendary"):
            self.assertLess(config.ITEM_RARITY_RATES[r], config.RARITY_RATES[r])
        rng = random.Random(1)
        n = 20000
        got = [items.roll_rarity(rng) for _ in range(n)]
        self.assertGreater(got.count("common") / n, 0.95)
        self.assertLess(got.count("legendary"), 20)

    def test_mods_follow_rarity_and_stars_fall_off(self):
        rng = random.Random(2)
        for i, r in enumerate(config.RARITIES):
            it = items.roll_item(rng, 1, rarity=r)
            self.assertEqual(len(it.mods), i)
        c = [items.roll_stars(rng, "legendary") for _ in range(4000)]
        self.assertLess(c.count(5) / 4000, 0.02)

    def test_power_grows_with_level_star_rarity(self):
        a = items.Item(1, "iron_sword")
        b = items.Item(2, "iron_sword", level=10)
        c = items.Item(3, "iron_sword", stars=2)
        d = items.Item(4, "iron_sword", rarity="rare")
        self.assertGreater(b.base_stats()["atk"], a.base_stats()["atk"])
        self.assertGreaterEqual(c.base_stats()["atk"], b.base_stats()["atk"] * 0.95)
        self.assertGreater(d.base_stats()["atk"], a.base_stats()["atk"])

    def test_salvage_better_when_higher_level(self):
        lo = items.Item(1, "iron_sword")
        hi = items.Item(2, "iron_sword", stars=4, level=8)
        self.assertGreater(hi.salvage_yield()["scrap"], lo.salvage_yield()["scrap"])
        self.assertIn("alloy", hi.salvage_yield())          # a better material appears
        self.assertNotIn("alloy", lo.salvage_yield())
        self.assertLess(hi.salvage_yield(broken=True)["scrap"], hi.salvage_yield()["scrap"])

    def test_durability_wears_and_shatters(self):
        g = mk()
        s = g.slimes()[0]
        it = g.new_item(rarity="common")
        g.equip_item(s.id, it.uid)
        it.durability = 1
        out = g._wear_items([s])
        self.assertTrue(any("shatters" in l for l in out))
        self.assertEqual(s.items, {})
        self.assertGreater(g.wallet.get("scrap"), 0)

    def test_compat_changes_the_bonus(self):
        g = mk()
        a = g.slimes()[0]
        it = g.new_item()
        vals = {items.Item(i, it.base).compat(a) for i in range(1, 40)}
        self.assertGreater(len(vals), 5)
        self.assertTrue(all(0 <= v <= 100 for v in vals))
        fit = next(s for s in g.slimes() if s.archetype in it.spec.fits) if any(
            s.archetype in it.spec.fits for s in g.slimes()) else None
        if fit:
            self.assertGreaterEqual(it.compat(fit), 25)

    def test_equip_changes_stats_and_swaps(self):
        g = mk()
        s = g.slimes()[0]
        before = s.max_stats()
        w1 = items.Item(90, "war_hammer", "rare", 3)
        g.vault[90] = w1
        g.equip_item(s.id, 90)
        self.assertNotEqual(s.max_stats(), before)
        w2 = items.Item(91, "iron_sword")
        g.vault[91] = w2
        g.equip_item(s.id, 91)
        self.assertIn(90, g.vault)
        self.assertEqual(s.items["weapon"].uid, 91)

    def test_growth_rules(self):
        g = mk()
        it = items.Item(33, "iron_sword")
        g.vault[33] = it
        g.wallet.add("scrap", 1000)
        for _ in range(9):
            g.level_item(it.uid)
        self.assertEqual(it.level, 10)
        with self.assertRaises(InvalidAction):
            g.level_item(it.uid)
        with self.assertRaises(NotEnoughResources):
            g.ascend_star(it.uid)
        g.wallet.add("scrap", 1000)
        g.wallet.add("alloy", 100)
        g.ascend_star(it.uid)
        self.assertEqual((it.stars, it.level), (2, 1))
        with self.assertRaises(InvalidAction):
            g.ascend_rarity(it.uid)                       # needs 5 stars, level 10

    def test_star_ascension_needs_the_armory(self):
        g = mk()
        it = items.Item(50, "iron_sword", stars=2, level=10)
        g.vault[50] = it
        g.wallet.add_many({"scrap": 500, "alloy": 50})
        with self.assertRaises(InvalidAction):
            g.ascend_star(50)
        g.buildings.levels["armory"] = 2
        g.ascend_star(50)
        self.assertEqual(it.stars, 3)

    def test_rarity_ascension_adds_a_mod(self):
        g = mk()
        it = items.Item(60, "iron_sword", "common", 5, 10)
        g.vault[60] = it
        g.buildings.levels["armory"] = 5
        g.wallet.add_many({"scrap": 400, "alloy": 100, "purple_gel": 5, "essence": 50})
        g.ascend_rarity(60)
        self.assertEqual(it.rarity, "uncommon")
        self.assertEqual(len(it.mods), 1)
        self.assertEqual((it.stars, it.level), (5, 10))

    def test_repair_and_salvage(self):
        g = mk()
        it = g.new_item()
        it.durability = 5
        g.repair_item(it.uid)
        self.assertEqual(it.durability, it.max_durability)
        with self.assertRaises(InvalidAction):
            g.repair_item(it.uid)
        g.salvage_item(it.uid)
        self.assertNotIn(it.uid, g.vault)
        self.assertGreater(g.wallet.get("scrap"), 0)

    def test_ego_fusion(self):
        g = mk()
        soul = legend(g)
        soul.level = 40
        wielder = legend(g)
        it = items.Item(70, "iron_sword", "legendary", 5, 10)
        g.vault[70] = it
        plain = items.Item(71, "iron_sword", "rare", 5)
        g.vault[71] = plain
        with self.assertRaises(InvalidAction):
            g.fuse_ego(71, soul.id)                     # item not legendary 5-star
        weak = g.slimes()[0]
        with self.assertRaises(InvalidAction):
            g.fuse_ego(70, weak.id)                     # soul not legendary 5-star
        stress = g.sacrifice_stress
        g.fuse_ego(70, soul.id)
        self.assertNotIn(soul.id, g.roster)
        self.assertTrue(it.ego)
        self.assertGreater(g.sacrifice_stress, stress)
        self.assertTrue(it.unbreakable)
        self.assertGreater(it.power_mult(), items.Item(1, "iron_sword", "legendary", 5, 10).power_mult())
        with self.assertRaises(InvalidAction):
            g.equip_item(weak.id, 70)                   # only 5-star legendaries
        g.equip_item(wielder.id, 70)
        with self.assertRaises(InvalidAction):
            g.salvage_item(70)
        # a higher-level soul makes a stronger ego
        s2 = legend(g)
        s2.level = 5
        i2 = items.Item(72, "iron_sword", "legendary", 5, 10)
        g.vault[72] = i2
        g.fuse_ego(72, s2.id)
        self.assertGreater(it.power_mult(), i2.power_mult())

    def test_three_egos_need_three_sacrifices(self):
        g = mk()
        w = legend(g)
        souls = [legend(g) for _ in range(3)]
        for n, base in enumerate(("iron_sword", "chain_shell", "mana_bead")):
            g.vault[80 + n] = items.Item(80 + n, base, "legendary", 5, 10)
            g.fuse_ego(80 + n, souls[n].id)
            g.equip_item(w.id, 80 + n)
        self.assertEqual(len(w.items), 3)
        self.assertEqual(sum(1 for s in g.slimes() if s.id in {x.id for x in souls}), 0)

    def test_mods_affect_battle(self):
        g = mk()
        s = g.slimes()[0]
        it = items.Item(5, "iron_sword", "rare", mods=[dict(kind="crit_rate", value=0.05),
                                                      dict(kind="elem_dmg", value=0.1, element="fire")])
        it.ego = None
        s.items["weapon"] = it
        m = items.battle_mods(s)
        self.assertAlmostEqual(m["crit_rate"], 0.05)
        self.assertAlmostEqual(m["elem"]["fire"], 0.1)
        it.ego = {"level": 1}
        self.assertAlmostEqual(items.battle_mods(s)["crit_rate"], 0.10)

    def test_dying_returns_relics_outside_dungeons(self):
        g = mk()
        s = g.slimes()[0]
        it = g.new_item()
        g.equip_item(s.id, it.uid)
        s.hp = 0
        g._reap([])
        self.assertIn(it.uid, g.vault)

    def test_relics_lost_when_the_last_slime_falls_in_the_descent(self):
        g = mk()
        s = g.slimes()[0]
        it = g.new_item()
        g.equip_item(s.id, it.uid)
        log = []
        g._drop_gear([s], [], [s], "Hollow Descent", log)
        self.assertEqual(s.items, {})
        self.assertNotIn(it.uid, g.vault)
        self.assertTrue(any("lost" in l for l in log))

    def test_pit_knockout_keeps_relics(self):
        g = mk()
        s = g.slimes()[0]
        it = g.new_item(rarity="common")
        g.equip_item(s.id, it.uid)
        g._drop_gear([s], [], [s], "Gloop Pit", [])
        self.assertIn("weapon" if it.slot == "weapon" else it.slot, s.items)

    def test_merge_returns_relics(self):
        g = mk()
        a, b = g.slimes()[:2]
        it = g.new_item()
        g.equip_item(b.id, it.uid)
        g.merge(a.id, b.id)
        self.assertIn(it.uid, g.vault)

    def test_persistence_roundtrip(self):
        g = mk()
        s = g.slimes()[0]
        a, b = g.new_item(rarity="epic"), g.new_item(rarity="rare")
        a.durability = 17
        a.bond = 5
        g.equip_item(s.id, a.uid)
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.slime(s.id).items[a.slot].to_dict(), a.to_dict())
        self.assertEqual(h.vault[b.uid].to_dict(), b.to_dict())
        self.assertEqual(h.next_item_id, g.next_item_id)
        self.assertEqual(h.slime(s.id).max_stats(), s.max_stats())


class TestAdventure(unittest.TestCase):
    def test_party_size_one_to_five(self):
        g = mk(n=7)
        ids = [s.id for s in g.slimes()]
        with self.assertRaises(InvalidAction):
            g.adventure([], 1)
        with self.assertRaises(InvalidAction):
            g.adventure(ids[:6], 1)
        for k in (1, 3, 5):
            r = g.adventure(ids[:k], 1)
            self.assertTrue(r.runs)
            self.assertEqual(len(r.runs[0].log) > 0, True)
            for s in g.slimes():
                s.hp = s.max_hp

    def test_monsters_are_one_level_above(self):
        theme = dungeon.pit_theme(5, 0)
        for avg in (3, 10, 24):
            lv = {e.level if hasattr(e, "level") else None for e in dungeon.grind_wave(avg, 4, 3, random.Random(1), theme)}
            self.assertEqual(dungeon.grind_level(avg, 4), avg + 1)

    def test_nobody_dies_and_slimes_are_released(self):
        g = mk()
        ids = [s.id for s in g.slimes()[:3]]
        n = len(g.roster)
        g.adventure(ids, 6)
        self.assertEqual(len(g.roster), n)
        self.assertTrue(all(s.in_dungeon == "" for s in g.slimes()))

    def test_it_drops_relics(self):
        g = mk(level=25)
        for s in g.slimes():
            s.stage = 1
        for _ in range(4):
            g.conflicts.tick = lambda *a, **k: None
            g.adventure([s.id for s in g.slimes()[:5]], 8)
            for s in g.slimes():
                s.hp = s.max_hp
                s.needs.v.update({k: 100.0 for k in s.needs.v})
        self.assertGreater(len(g.vault), 0)

    def test_lure_costs_purple_gel(self):
        g = mk()
        p = g.wallet.get("purple_gel")
        g.adventure([g.slimes()[0].id], 2, lure=True)
        self.assertLess(g.wallet.get("purple_gel"), p)

    def test_busy_slimes_cannot_go(self):
        g = mk()
        s = g.slimes()[0]
        s.state = "hunting"
        with self.assertRaises(InvalidAction):
            g.adventure([s.id], 1)

    def test_ko_damages_relics(self):
        g = mk()
        s = g.slimes()[0]
        it = g.new_item(rarity="common")
        g.equip_item(s.id, it.uid)
        before = it.durability
        g._ko_wear([s], [])
        self.assertLess(it.durability, before)


if __name__ == "__main__":
    unittest.main()
