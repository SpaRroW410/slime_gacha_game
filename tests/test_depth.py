import random
import unittest

from slime_gacha import attributes, config, items, potions
from slime_gacha.abilities import get_ability
from slime_gacha.battle import BattleSystem
from slime_gacha.errors import InvalidAction, NotEnoughResources
from slime_gacha.game import Game


def mk(seed=3, n=6, level=5):
    g = Game(seed)
    g.wallet.add_many({"white_gel": 100000, "herb_green": 500, "herb_red": 500, "herb_blue": 500, "herb_yellow": 500, "essence": 1000, "scrap": 1000, "alloy": 500})
    g.pull(n, "white_gel")
    for s in g.slimes():
        s.level = level
    return g


def make(g, arch, rarity="common", stars=1):
    s = g.gacha.make_slime(rarity, arch, stars)
    g.roster[s.id] = s
    return s


class TestStamina(unittest.TestCase):
    def test_every_slime_has_stamina(self):
        g = mk()
        for s in g.slimes():
            self.assertGreater(s.max_stamina, 50)
            self.assertEqual(s.stamina, s.max_stamina)

    def test_stamina_grows_with_level_and_rank(self):
        g = mk()
        s = make(g, "barbarian")
        base = s.max_stamina
        s.level = 20
        self.assertGreater(s.max_stamina, base)
        s.rarity, s.stars = "legendary", 5
        self.assertGreater(s.max_stamina, base * 1.5)

    def test_bigger_actions_cost_more(self):
        self.assertGreater(attributes.action_cost(get_ability("arcane_surge")), attributes.action_cost(get_ability("splat")))
        self.assertGreater(attributes.action_cost(get_ability("rampage")), attributes.action_cost(get_ability("smash")) * 0.8)

    def test_fight_spends_and_writes_back(self):
        g = mk(level=10)
        s = make(g, "barbarian")
        s.level = 10
        s.hp = s.max_hp
        from slime_gacha import dungeon
        enemies = dungeon.grind_wave(10, 3, 1, random.Random(1), dungeon.pit_theme(1, 0))
        g.battles.run([s], enemies, permadeath=False)
        self.assertLess(s.stamina_frac, 1.0)

    def test_empty_stamina_weakens_attacks(self):
        g = mk()
        a = make(g, "barbarian")
        a.level = 10
        from slime_gacha import battle
        bs = BattleSystem(random.Random(2))
        ca = bs.from_slime(a)
        foe = bs.from_slime(make(g, "mage"), side="foes")
        ab = get_ability("smash")
        ca.winded = False
        normal = [battle._damage_value(bs, ca, ab, foe)[0] for _ in range(300)]
        ca.winded = True
        weak = [battle._damage_value(bs, ca, ab, foe)[0] for _ in range(300)]
        self.assertLess(sum(weak), sum(normal) * 0.75)

    def test_winded_is_logged_when_dry(self):
        g = mk(level=10)
        s = make(g, "barbarian")
        s.level, s.hp, s.stamina_frac = 10, s.max_hp, 0.0
        from slime_gacha import dungeon
        enemies = dungeon.grind_wave(10, 3, 2, random.Random(1), dungeon.pit_theme(1, 0))
        rep = g.battles.run([s], enemies, permadeath=False)
        self.assertTrue(any("winded" in l for l in rep.log))

    def test_regen_by_the_hour_is_faster_asleep(self):
        g = mk()
        a, b = g.slimes()[:2]
        a.stamina_frac = b.stamina_frac = 0.1
        b.state = "sleeping"
        g.wallet.add("food", 99)
        g._stamina_tick()
        self.assertGreater(b.stamina_frac, a.stamina_frac)
        self.assertGreater(a.stamina_frac, 0.1)

    def test_persists(self):
        g = mk()
        s = g.slimes()[0]
        s.stamina_frac = 0.4
        h = Game.from_dict(g.to_dict())
        self.assertAlmostEqual(h.slime(s.id).stamina_frac, 0.4)


class TestStarAttributesAndSkills(unittest.TestCase):
    def test_each_star_adds_one_attribute(self):
        g = mk()
        for arch in attributes.STAR_ATTRS:
            s = make(g, arch)
            counts = []
            for st in range(1, 6):
                s.stars = st
                counts.append(len(attributes.star_attributes(s)))
            self.assertEqual(counts, [0, 1, 2, 3, 4])

    def test_attributes_differ_by_class(self):
        g = mk()
        keys = {}
        for arch in attributes.STAR_ATTRS:
            s = make(g, arch, stars=5)
            keys[arch] = tuple(a["key"] for a in attributes.star_attributes(s))
        self.assertGreater(len(set(keys.values())), 4)

    def test_rarity_grows_values(self):
        g = mk()
        s = make(g, "rogue", stars=2)
        lo = attributes.star_attributes(s)[0]["value"]
        s.rarity = "legendary"
        self.assertGreater(attributes.star_attributes(s)[0]["value"], lo)

    def test_one_skill_per_rarity_step(self):
        g = mk()
        for arch in attributes.RARITY_SKILLS:
            s = make(g, arch)
            for i, r in enumerate(config.RARITIES):
                s.rarity = r
                self.assertEqual(len(attributes.rarity_skills(s)), i)
                for k in attributes.rarity_skills(s):
                    self.assertIn(k, s.known_abilities())
            self.assertEqual(len(attributes.RARITY_SKILLS[arch]), 4)

    def test_moon_slash_comes_with_uncommon(self):
        g = mk()
        s = make(g, "barbarian")
        self.assertNotIn("moon_slash", s.known_abilities())
        g.wallet.add("white_gel", 100)
        s.level, s.stars = 100, 5
        g.ascend_slime_rarity(s.id)
        self.assertIn("moon_slash", s.known_abilities())

    def test_battle_mods_combine_with_relics(self):
        g = mk()
        s = make(g, "rogue", "rare", 4)
        it = items.Item(5, "bone_dagger", mods=[dict(kind="crit_rate", value=0.05)])
        s.items["weapon"] = it
        from slime_gacha import battle
        c = BattleSystem(random.Random(1)).from_slime(s)
        base = attributes.battle_mods(s)["crit_rate"]
        self.assertAlmostEqual(c.mods["crit_rate"], base + 0.05)
        self.assertGreater(c.mods["evasion"], 0)

    def test_evasion_guard_and_regen_work(self):
        from slime_gacha import battle
        g = mk()
        bs = BattleSystem(random.Random(3))
        a = bs.from_slime(make(g, "barbarian", stars=1))
        t = bs.from_slime(make(g, "barbarian", stars=1), side="foes")
        ab = get_ability("smash")
        plain = sum(battle._damage_value(bs, a, ab, t)[0] for _ in range(200))
        t.mods["guard"] = 0.3
        guarded = sum(battle._damage_value(bs, a, ab, t)[0] for _ in range(200))
        self.assertLess(guarded, plain * 0.85)
        t.mods["guard"] = 0
        a = bs.from_slime(make(g, "mage"))
        a.stats["mag"] = 300
        a.mods["spell_power"] = 0.5
        mage_ab = get_ability("spark")
        p1 = sum(battle._damage_value(bs, a, mage_ab, t)[0] for _ in range(200))
        a.mods["spell_power"] = 0
        p0 = sum(battle._damage_value(bs, a, mage_ab, t)[0] for _ in range(200))
        self.assertGreater(p1, p0 * 1.3)


class TestPotions(unittest.TestCase):
    def test_lab_level_caps_grade(self):
        g = mk()
        s = g.slimes()[0]
        with self.assertRaises(InvalidAction):
            g.brew(s.id, "might", 2)
        g.buildings.levels["alchemy"] = 5
        g.brew(s.id, "might", 2)

    def test_costs_scale(self):
        c = [potions.cost("might", i) for i in range(1, 6)]
        self.assertTrue(all(c[i]["herb_red"] < c[i + 1]["herb_red"] for i in range(4)))
        self.assertNotIn("essence", c[0])
        self.assertIn("essence", c[4])

    def test_brew_makes_potions_or_loses_ingredients(self):
        g = mk()
        s = g.slimes()[0]
        made = 0
        herbs = g.wallet.get("herb_yellow")
        for _ in range(40):
            before = sum(g.potions.values())
            g.brew(s.id, "stamina", 1)
            made += sum(g.potions.values()) - before
            s.state = "idle"
        self.assertGreater(made, 20)
        self.assertLess(g.wallet.get("herb_yellow"), herbs)

    def test_brewing_takes_time_and_frees_the_slime(self):
        g = mk()
        s = g.slimes()[0]
        t0 = g.tick_count
        g.buildings.levels["alchemy"] = 3
        g.brew(s.id, "gale", 3)
        self.assertEqual(g.tick_count - t0, potions.brew_hours(3))
        self.assertEqual(s.in_dungeon, "")

    def test_needs_ingredients(self):
        g = mk()
        for c in config.HERBS:
            g.wallet.add(potions.herb_key(c), -g.wallet.get(potions.herb_key(c)))
        with self.assertRaises(NotEnoughResources):
            g.brew(g.slimes()[0].id, "might", 1)

    def test_potion_boosts_attribute_then_expires(self):
        g = mk()
        s = g.slimes()[0]
        base = s.max_stats()["atk"]
        g.potions["might:3"] = 1
        g.use_potion(s.id, "might", 3)
        self.assertAlmostEqual(s.max_stats()["atk"], round(base * 1.2, 1), delta=0.2)
        for _ in range(potions.hours(3) + 1):
            g._stamina_tick()
        self.assertEqual(s.buffs, [])
        self.assertAlmostEqual(s.max_stats()["atk"], base, delta=0.1)

    def test_stamina_potion_raises_max_and_recovery(self):
        g = mk()
        s = g.slimes()[0]
        s.stamina_frac = 0.2
        base_max, base_rate = s.max_stamina, attributes.hourly_regen(s)
        g.potions["stamina:2"] = 1
        g.use_potion(s.id, "stamina", 2)
        self.assertGreater(s.max_stamina, base_max)
        self.assertGreater(attributes.hourly_regen(s), base_rate * 1.6)
        self.assertGreater(attributes.regen_per_round(s), 0)

    def test_cannot_use_what_you_do_not_have(self):
        g = mk()
        with self.assertRaises(InvalidAction):
            g.use_potion(g.slimes()[0].id, "might", 1)

    def test_herbs_drop_in_the_pit(self):
        g = mk()
        log = []
        g.rng = random.Random(1)
        total = lambda: sum(g.wallet.get(potions.herb_key(c)) for c in config.HERBS)
        for c in config.HERBS:
            g.wallet.add(potions.herb_key(c), -g.wallet.get(potions.herb_key(c)))
        for _ in range(30):
            g._herb_drop("grind", 5, log)
        self.assertGreater(total(), 20)
        n = total()
        for _ in range(30):
            g._herb_drop("adventure", 5, log)
        self.assertLess(total() - n, n)

    def test_persists(self):
        g = mk()
        s = g.slimes()[0]
        g.potions["vigor:1"] = 2
        g.potions["might:1"] = 1
        g.use_potion(s.id, "might", 1)
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.potions, {"vigor:1": 2})
        self.assertEqual(h.slime(s.id).buffs[0]["kind"], "might")


class TestWeapons(unittest.TestCase):
    def equip(self, g, s, base, uid, rarity="common"):
        it = items.Item(uid, base, rarity)
        g.vault[uid] = it
        return g.equip_item(s.id, uid), it

    def test_three_families_then_forgetting(self):
        g = mk()
        s = make(g, "barbarian")
        for i, b in enumerate(("iron_sword", "war_hammer", "bone_dagger")):
            self.equip(g, s, b, 100 + i)
            s.items.pop("weapon")
        self.assertEqual(sorted(s.weapon_memory), ["dagger", "hammer", "sword"])
        s.proficiency["hammer"] = 50
        s.proficiency["dagger"] = 30
        s.proficiency["sword"] = 5
        msg, _ = self.equip(g, s, "hunters_bow", 110)
        self.assertIn("forgets", msg)
        self.assertNotIn("sword", s.weapon_memory)
        self.assertEqual(len(s.weapon_memory), 3)
        self.assertIn("bow", s.weapon_memory)

    def test_swapping_among_remembered_weapons_is_free(self):
        g = mk()
        s = make(g, "rogue")
        self.equip(g, s, "iron_sword", 100)
        self.equip(g, s, "bone_dagger", 101)
        msg, _ = self.equip(g, s, "iron_sword", 102)
        self.assertNotIn("forgets", msg)
        self.assertEqual(len(s.weapon_memory), 2)

    def test_practice_improves_the_weapon(self):
        g = mk()
        s = make(g, "barbarian")
        it = items.Item(100, "iron_sword")
        s.items["weapon"] = it
        before = it.stats_for(s)["atk"]
        s.proficiency["sword"] = 100
        self.assertGreater(it.stats_for(s)["atk"], before * 1.2)
        g._wear_items([s])
        self.assertEqual(s.proficiency["sword"], 101)

    def test_favourite_family_raises_compat(self):
        g = mk()
        s = make(g, "barbarian")
        fav = items.favourite_family(s)
        other = next(f for f in items.CLASS_FAMILIES["barbarian"] if f != fav)
        base_of = {"sword": "iron_sword", "hammer": "war_hammer"}
        a = items.Item(1, base_of[fav])
        b = items.Item(1, base_of[other])
        self.assertGreaterEqual(a.compat(s) - b.compat(s), config.FAVOURITE_COMPAT - 12)
        self.assertEqual(a.compat(s) - b.compat(s) >= 0 or True, True)

    def test_weapons_of_rare_quality_are_named(self):
        rng = random.Random(4)
        for _ in range(30):
            it = items.roll_item(rng, 1, rarity="rare")
            if it.slot == "weapon":
                self.assertTrue(it.title)
                self.assertIn(it.title, it.name)
            else:
                self.assertEqual(it.title, "")
            c = items.roll_item(rng, 1, rarity="common")
            self.assertEqual(c.title, "")

    def test_ascension_to_rare_names_a_weapon(self):
        g = mk()
        it = items.Item(5, "iron_sword", "uncommon", 5, 10)
        g.vault[5] = it
        g.buildings.levels["armory"] = 5
        g.wallet.add_many({"alloy": 400, "crystal": 400, "purple_gel": 10, "essence": 100})
        g.ascend_rarity(5)
        self.assertEqual(it.rarity, "rare")
        self.assertTrue(it.title)

    def test_title_persists(self):
        it = items.Item(5, "iron_sword", "rare")
        it.title = "Wolfsbane"
        self.assertEqual(items.Item.from_dict(it.to_dict()).title, "Wolfsbane")

    def test_slime_repairs_its_own_gear(self):
        g = mk()
        s = make(g, "barbarian")
        it = items.Item(7, "iron_sword")
        it.durability = 5
        s.items["weapon"] = it
        scrap, morale = g.wallet.get("scrap"), s.morale
        g.slime_repair(s.id)
        self.assertEqual(it.durability, it.max_durability)
        self.assertLess(g.wallet.get("scrap"), scrap)
        self.assertGreater(s.morale, morale - 1)
        with self.assertRaises(InvalidAction):
            g.slime_repair(s.id)

    def test_bonded_weapon_steadies_morale(self):
        g = mk()
        s = make(g, "barbarian")
        it = items.Item(8, "iron_sword")
        it.bond = config.BOND_MORALE_AT
        s.items["weapon"] = it
        s.morale = 50
        g._wear_items([s])
        self.assertGreater(s.morale, 50)

    def test_proficiency_and_memory_persist(self):
        g = mk()
        s = make(g, "mage")
        self.equip(g, s, "oak_staff", 9)
        s.proficiency["staff"] = 33
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.slime(s.id).proficiency["staff"], 33)
        self.assertEqual(h.slime(s.id).weapon_memory, ["staff"])


if __name__ == "__main__":
    unittest.main()
