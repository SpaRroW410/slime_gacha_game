import random
import unittest

from slime_gacha import config, potions, terrain
from slime_gacha.errors import InvalidAction
from slime_gacha.game import Game


def mk(seed=8, n=6):
    g = Game(seed)
    g.wallet.add_many({"white_gel": 100000, "essence": 1000, "scrap": 1000, "alloy": 300, "crystal": 300})
    for c in config.HERBS:
        g.wallet.add(potions.herb_key(c), 500)
    g.pull(n, "white_gel")
    return g


class TestHerbsAndCombos(unittest.TestCase):
    def test_four_herbs_four_basic_potions(self):
        self.assertEqual(config.HERBS, ("green", "red", "blue", "yellow"))
        basic = {k: p.herbs for k, p in potions.KINDS.items() if len(p.herbs) == 1}
        self.assertEqual(basic, {"vigor": ("green",), "might": ("red",), "ironhide": ("blue",), "stamina": ("yellow",)})
        self.assertEqual(potions.KINDS["vigor"].stats, {"hp": 1.0})
        self.assertEqual(potions.KINDS["might"].stats, {"atk": 1.0})
        self.assertEqual(potions.KINDS["ironhide"].stats, {"defense": 1.0})

    def test_every_pair_makes_a_further_attribute_potion(self):
        pairs = {tuple(sorted(p.herbs)) for p in potions.KINDS.values() if len(p.herbs) == 2}
        self.assertEqual(len(pairs), 6)
        for p in potions.KINDS.values():
            if len(p.herbs) == 2:
                self.assertTrue(p.mods or p.stats)

    def test_combo_costs_two_colours(self):
        c = potions.cost("bloodthirst", 3)
        self.assertEqual({k for k in c if k.startswith("herb_")}, {"herb_green", "herb_red"})
        single = potions.cost("might", 3)["herb_red"]
        self.assertLess(c["herb_green"], single)
        self.assertGreater(c["white_gel"], potions.cost("might", 3)["white_gel"])

    def test_brewing_a_combo_spends_both_herbs(self):
        g = mk()
        g.buildings.levels["alchemy"] = 3
        s = g.slimes()[0]
        gr, rd = g.wallet.get("herb_green"), g.wallet.get("herb_red")
        g.brew(s.id, "bloodthirst", 2)
        self.assertLess(g.wallet.get("herb_green"), gr)
        self.assertLess(g.wallet.get("herb_red"), rd)
        self.assertEqual(g.wallet.get("herb_blue"), 500)

    def test_combo_effects_reach_the_battle(self):
        from slime_gacha import attributes
        g = mk()
        s = g.slimes()[0]
        for kind, expect in (("bloodthirst", "lifesteal"), ("bulwark", "guard"), ("renewal", "regen"),
                             ("fury", "crit_rate"), ("gale", "evasion"), ("arcane", "spell_power")):
            s.buffs = [dict(kind=kind, grade=3, bonus=0.2, hours=5)]
            self.assertGreater(attributes.battle_mods(s).get(expect, 0), 0, kind)
        s.buffs = [dict(kind="gale", grade=3, bonus=0.2, hours=5)]
        base = s.core_stats()["spd"]
        self.assertGreater(s.max_stats()["spd"], base)
        s.buffs = [dict(kind="arcane", grade=3, bonus=0.2, hours=5)]
        self.assertGreater(s.max_stats()["mag"], s.core_stats()["mag"])

    def test_terrain_picks_the_main_herb(self):
        g = mk()
        for c in config.HERBS:
            g.wallet.add(potions.herb_key(c), -g.wallet.get(potions.herb_key(c)))
        t = next(t for t in terrain.TERRAINS if config.TERRAIN_HERB[t.kind] == "red")
        g.rng = random.Random(5)
        for _ in range(60):
            g._herb_drop("grind", 5, [], t)
        red = g.wallet.get("herb_red")
        others = sum(g.wallet.get(potions.herb_key(c)) for c in config.HERBS if c != "red")
        self.assertGreater(red, others)
        self.assertGreater(others, 0)

    def test_every_terrain_kind_has_a_herb(self):
        for k in terrain.KINDS:
            self.assertIn(config.TERRAIN_HERB[k], config.HERBS)

    def test_the_pit_theme_changes_the_herb_by_day(self):
        from slime_gacha import dungeon
        herbs = {config.TERRAIN_HERB[dungeon.pit_theme(7, d).terrain.kind] for d in range(40)}
        self.assertGreaterEqual(len(herbs), 3)

    def test_old_herbs_are_shared_out_on_load(self):
        g = mk()
        d = g.to_dict()
        for c in config.HERBS:
            d["wallet"].pop(potions.herb_key(c), None)
        d["wallet"]["herb"] = 10
        h = Game.from_dict(d)
        self.assertEqual(sum(h.wallet.get(potions.herb_key(c)) for c in config.HERBS), 10)
        self.assertEqual(h.wallet.get("herb"), 0)


class TestAutonomy(unittest.TestCase):
    def test_share_is_two_thirds(self):
        self.assertEqual(config.AUTONOMY_SHARE, 0.66)

    def test_slimes_leave_a_third_alone(self):
        g = mk()
        g.potions["stamina:1"] = 10
        g.potion_peak["stamina:1"] = 10
        taken = 0
        for s in g.slimes():
            s.stamina_frac = 0.1
            s.buffs = []
            log = []
            if g._auto_drink(s, "stamina", log):
                taken += 1
        self.assertEqual(taken, 6)                          # 66% of 10, rounded down to keep 34% (4 left)
        self.assertEqual(g.potions["stamina:1"], 4)

    def test_single_potion_is_never_taken(self):
        g = mk()
        g.potions["vigor:1"] = 1
        g.potion_peak["vigor:1"] = 1
        self.assertFalse(g._auto_drink(g.slimes()[0], "vigor", []))
        self.assertEqual(g.potions["vigor:1"], 1)

    def test_the_reserve_is_based_on_the_peak(self):
        g = mk()
        g.potions["might:1"] = 3
        g.potion_peak["might:1"] = 9                         # you once held nine: keep ceil(3.06) = 4 back
        self.assertFalse(g._auto_drink(g.slimes()[0], "might", []))

    def test_tired_slime_drinks_by_itself_each_hour(self):
        g = mk()
        s = g.slimes()[0]
        g.potions["stamina:1"] = 6
        g.potion_peak["stamina:1"] = 6
        s.stamina_frac = 0.05
        log = []
        g._autonomy_tick(log)
        self.assertTrue(any("drinks" in l for l in log))
        self.assertTrue(any(b["kind"] == "stamina" for b in s.buffs))

    def test_hurt_slime_takes_vigor(self):
        g = mk()
        s = g.slimes()[0]
        g.potions["vigor:1"] = 6
        g.potion_peak["vigor:1"] = 6
        s.hp = 1
        g._autonomy_tick([])
        self.assertTrue(any(b["kind"] == "vigor" for b in s.buffs))

    def test_off_means_off(self):
        g = mk()
        g.set_autonomy(False)
        g.potions["stamina:1"] = 6
        g.potion_peak["stamina:1"] = 6
        s = g.slimes()[0]
        s.stamina_frac = 0.0
        g._autonomy_tick([])
        g._autonomy_prepare([s], [])
        self.assertEqual(s.buffs, [])

    def test_trip_preparation_follows_class(self):
        g = mk()
        s = g.gacha.make_slime("common", "barbarian")
        g.roster[s.id] = s
        for k in ("might:1", "ironhide:1", "arcane:1", "bulwark:1"):
            g.potions[k] = 6
            g.potion_peak[k] = 6
        log = []
        g._autonomy_prepare([s], log)
        kinds = {b["kind"] for b in s.buffs}
        self.assertEqual(len(kinds), config.AUTONOMY_MAX_BUFFS)
        self.assertTrue(kinds <= {"might", "ironhide", "bulwark"})
        self.assertNotIn("arcane", kinds)

    def test_expedition_start_uses_it(self):
        g = mk(n=6)
        for s in g.slimes():
            s.level, s.stage = 40, 2
        g.potions["might:1"] = 20
        g.potion_peak["might:1"] = 20
        g.conflicts.tick = lambda *a, **k: None
        r = g.adventure([s.id for s in g.slimes()[:3]], 1)
        self.assertTrue(any("drinks" in l for l in r.summary))

    def test_slime_mends_gear_with_at_most_two_thirds_of_the_scrap(self):
        from slime_gacha import items
        g = mk()
        s = g.slimes()[0]
        it = items.Item(5, "iron_sword")
        it.durability = 3
        s.items["weapon"] = it
        g.wallet.add("scrap", -g.wallet.get("scrap") + 6)    # 6 scrap; the repair needs ~5
        log = []
        g._auto_repair(s, log)
        self.assertEqual(it.durability, 3)                   # 5 > 66% of 6
        g.wallet.add("scrap", 100)
        g._auto_repair(s, log)
        self.assertEqual(it.durability, it.max_durability)

    def test_persists(self):
        g = mk()
        g.set_autonomy(False)
        g.potions["might:1"] = 2
        g.potion_peak["might:1"] = 5
        h = Game.from_dict(g.to_dict())
        self.assertFalse(h.autonomy)
        self.assertEqual(h.potion_peak["might:1"], 5)


if __name__ == "__main__":
    unittest.main()
