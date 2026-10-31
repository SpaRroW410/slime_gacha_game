import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, elements, spells
from slime_gacha.abilities import ABILITIES, get_ability
from slime_gacha.battle import BattleSystem, Enemy
from slime_gacha.errors import InvalidAction, NotEnoughResources
from slime_gacha.game import Game
from slime_gacha.growth import add_xp


def rich_game(seed=1):
    g = Game(seed)
    for k in ("white_gel", "purple_gel", "essence", "food"):
        g.wallet.add(k, 5000)
    return g


def scholar(g, archetype="barbarian", stars=3, rarity="rare"):
    s = g.gacha.make_slime(rarity, archetype, stars=stars)
    g.roster[s.id] = s
    return s


def master(g, s, element, level):
    """Study once for real, then fast-forward mastery to `level`."""
    g.study(s.id, element)
    g.tick(config.STUDY_TICKS)
    s.mastery_xp[element] = config.MASTERY_XP[level - 1]
    s.needs.v["energy"] = s.needs.v["food"] = 100


class Cleanup(unittest.TestCase):
    def tearDown(self):
        for k in list(spells.CUSTOM):
            spells.forget_custom(k)


class TestElements(Cleanup):
    def test_basics_and_recipes(self):
        self.assertEqual(set(elements.BASICS), {"fire", "water", "earth", "wind"})
        self.assertEqual(elements.combine("fire", "wind").key, "lightning")
        self.assertEqual(elements.combine("wind", "fire").key, "lightning")        # order-free
        self.assertEqual(elements.combine("lightning", "fire").key, "plasma")
        self.assertIsNone(elements.combine("fire", "fire"))
        self.assertEqual(elements.get("lightning").tier, 2)
        self.assertEqual(elements.get("plasma").tier, 3)
        self.assertEqual(elements.get("plasma").components, frozenset({"fire", "wind"}))

    def test_wheel(self):
        self.assertEqual(elements.effectiveness("water", "fire"), config.ELEMENT_ADVANTAGE)
        self.assertEqual(elements.effectiveness("fire", "water"), config.ELEMENT_DISADVANTAGE)
        self.assertEqual(elements.effectiveness("fire", "earth"), 1.0)
        self.assertEqual(elements.effectiveness("", "fire"), 1.0)
        self.assertEqual(elements.effectiveness("lightning", "earth"), config.ELEMENT_ADVANTAGE)  # wind part

    def test_new_recipe_extension(self):
        try:
            elements.register_recipe("lava", "mud", "test_brick", "Brick", "🧱")
            self.assertEqual(elements.combine("mud", "lava").key, "test_brick")
            self.assertEqual(elements.get("test_brick").tier, 3)
        finally:
            elements.RECIPES.pop(frozenset(("lava", "mud")), None)
            elements.ELEMENTS.unregister("test_brick")

    def test_mastery_rules_by_stars(self):
        g = rich_game()
        for stars, cap, slots in ((1, 0, 0), (2, 0, 0), (3, 4, 2), (4, 6, 3), (5, 8, 4)):
            s = scholar(g, "barbarian", stars)
            self.assertEqual((elements.mastery_cap(s), elements.slot_count(s)), (cap, slots))
        m = scholar(g, "mage", 3)
        self.assertEqual(elements.slot_count(m), 3)                                # mage bonus slot

    def test_effective_mastery_is_weakest_component(self):
        self.assertEqual(elements.effective_mastery({"fire": 5, "wind": 2}, "lightning"), 2)
        self.assertEqual(elements.effective_mastery({"fire": 5}, "lightning"), 0)


class TestLibrary(Cleanup):
    def test_one_and_two_star_cannot_study(self):
        g = rich_game()
        for stars in (1, 2):
            s = scholar(g, "mage", stars, "common")
            with self.assertRaises(InvalidAction):
                g.study(s.id, "fire")

    def test_non_mage_can_master(self):
        g = rich_game()
        s = scholar(g, "barbarian", 3)
        master(g, s, "fire", 2)
        self.assertEqual(elements.basic_level(s, "fire"), 2)
        self.assertIn("fire", s.attuned)

    def test_study_levels_and_cap(self):
        g = rich_game()
        s = scholar(g, "barbarian", 3)
        g.needs.auto_care = False
        for _ in range(12):
            s.needs.v["energy"] = s.needs.v["food"] = 100
            try:
                g.study(s.id, "earth")
            except InvalidAction as e:
                self.assertIn("limit", str(e))
                break
            g.tick(config.STUDY_TICKS)
        self.assertEqual(elements.basic_level(s, "earth"), 4)

    def test_mage_studies_faster(self):
        g = rich_game()
        g.needs.auto_care = False
        m, b = scholar(g, "mage", 3), scholar(g, "barbarian", 3)
        g.study(m.id, "water")
        g.study(b.id, "water")
        g.tick(config.STUDY_TICKS)
        self.assertGreater(m.mastery_xp["water"], b.mastery_xp["water"])

    def test_attunement_slots_limit(self):
        g = rich_game()
        s = scholar(g, "barbarian", 3)
        g.needs.auto_care = False
        master(g, s, "fire", 1)
        master(g, s, "wind", 1)
        with self.assertRaises(InvalidAction):
            g.study(s.id, "water")
        with self.assertRaises(InvalidAction):
            g.study(s.id, "steam")                      # only basics can be studied

    def test_learn_requires_attunement_mastery_and_pays(self):
        g = rich_game()
        s = scholar(g, "barbarian", 3)
        with self.assertRaises(InvalidAction):
            g.learn_spell(s.id, "ember")                # not attuned
        master(g, s, "fire", 1)
        gel = g.wallet.get("white_gel")
        g.learn_spell(s.id, "ember")
        self.assertEqual(g.wallet.get("white_gel"), gel - 20)
        self.assertIn("ember", s.known_abilities())
        with self.assertRaises(InvalidAction):
            g.learn_spell(s.id, "ember")                # twice
        with self.assertRaises(InvalidAction):
            g.learn_spell(s.id, "gust")                 # wind not attuned
        poor = Game(1)
        p = scholar(poor)
        master(poor, p, "fire", 1)
        poor.wallet.spend("white_gel", poor.wallet.get("white_gel"))
        with self.assertRaises(NotEnoughResources):
            poor.learn_spell(p.id, "ember")

    def test_spell_slot_limit_and_forget(self):
        g = rich_game()
        s = scholar(g, "mage", 5)
        for el in elements.BASICS:
            master(g, s, el, 2)
        for k in ("ember", "flame_wave", "water_jet", "rain_mend"):
            g.learn_spell(s.id, k)
        with self.assertRaises(InvalidAction):
            g.learn_spell(s.id, "gust")
        g.forget_spell(s.id, "ember")
        g.learn_spell(s.id, "gust")


class TestResearch(Cleanup):
    def _fusion_ready(self, g, archetype="barbarian", stars=3):
        s = scholar(g, archetype, stars)
        master(g, s, "fire", 3)
        master(g, s, "wind", 3)
        g.learn_spell(s.id, "ember")
        g.learn_spell(s.id, "gust")
        return s

    def _until_success(self, g, s, a, b, name=None):
        for _ in range(30):
            s.hp, s.state = s.max_hp, "idle"
            s.needs.v["energy"] = s.needs.v["food"] = 100
            g.research(s.id, a, b, name)
            ev = g.tick(config.RESEARCH_TICKS[2])
            if any("invented" in e for e in ev):
                return
        self.fail("fusion never succeeded")

    def test_fire_plus_wind_makes_lightning(self):
        g = rich_game()
        s = self._fusion_ready(g)
        pv = g.research_preview(s.id, "ember", "gust")
        self.assertEqual(pv["element"].key, "lightning")
        self._until_success(g, s, "ember", "gust", "Thunder Spear")
        key = spells.fused_key("ember", "gust")
        sp = get_ability(key)
        self.assertEqual((sp.element, sp.tier, sp.name, sp.creator), ("lightning", 2, "Thunder Spear", s.name))
        self.assertIn(key, s.spells)
        self.assertIn(key, g.library.discovered)
        self.assertIn(key, [a.key for a in g.library.catalog()])

    def test_other_slimes_can_buy_discovered_spell(self):
        g = rich_game()
        s = self._fusion_ready(g)
        self._until_success(g, s, "ember", "gust")
        key = spells.fused_key("ember", "gust")
        t = scholar(g, "rogue", 4)
        master(g, t, "fire", 3)
        master(g, t, "wind", 3)
        essence = g.wallet.get("essence")
        g.learn_spell(t.id, key)
        self.assertEqual(g.wallet.get("essence"), essence - config.SPELL_LEARN_COST[2]["essence"])

    def test_requirements(self):
        g = rich_game()
        s = scholar(g, "barbarian", 3)
        master(g, s, "fire", 1)
        master(g, s, "wind", 1)
        g.learn_spell(s.id, "ember")
        g.learn_spell(s.id, "gust")
        with self.assertRaises(InvalidAction):
            g.research(s.id, "ember", "gust")           # mastery 1 < 3
        with self.assertRaises(InvalidAction):
            g.research(s.id, "ember", "ember")
        with self.assertRaises(InvalidAction):
            g.research(s.id, "ember", "flame_wave")     # not learned
        s.mastery_xp.update(fire=120, wind=120)
        s2 = scholar(g, "barbarian", 2)
        with self.assertRaises(InvalidAction):
            g.research(s2.id, "ember", "gust")          # 2-star

    def test_no_fusion_for_same_or_unmixable(self):
        g = rich_game()
        s = scholar(g, "mage", 4)
        for el in ("fire", "wind"):
            master(g, s, el, 3)
        g.learn_spell(s.id, "ember")
        g.learn_spell(s.id, "flame_wave")
        with self.assertRaises(InvalidAction):
            g.research(s.id, "ember", "flame_wave")     # fire + fire

    def test_tier_three_needs_mastery_five(self):
        g = rich_game()
        s = self._fusion_ready(g, "mage", 3)            # 3-star: mastery cap 4
        self._until_success(g, s, "ember", "gust")
        key = spells.fused_key("ember", "gust")
        with self.assertRaises(InvalidAction):
            g.research(s.id, key, "ember")              # plasma needs 5
        g.buildings.levels["library"] = 3               # Restricted Section
        t = self._fusion_ready(g, "mage", 5)            # 5-star can reach it
        t.mastery_xp.update(fire=config.MASTERY_XP[5], wind=config.MASTERY_XP[5])
        t.spells.append(key)
        pv = g.research_preview(t.id, key, "ember")
        self.assertEqual(pv["element"].key, "plasma")
        self.assertEqual(pv["cost"]["purple_gel"], 2)

    def test_failure_backfires_but_never_kills(self):
        g = rich_game(3)
        s = self._fusion_ready(g)
        fizzles = 0
        for _ in range(40):
            s.hp, s.state = s.max_hp, "idle"
            s.needs.v["energy"] = s.needs.v["food"] = 100
            hp = s.hp
            g.research(s.id, "ember", "gust")
            ev = g.tick(config.RESEARCH_TICKS[2])
            if any("fizzled" in e for e in ev):
                fizzles += 1
                self.assertGreaterEqual(s.hp, 1)
                self.assertLess(s.hp, hp)
            self.assertIn(s.id, g.roster)
        self.assertGreater(fizzles, 0)

    def test_wounded_cannot_experiment(self):
        g = rich_game()
        s = self._fusion_ready(g)
        s.hp = 1
        with self.assertRaises(InvalidAction):
            g.research(s.id, "ember", "gust")

    def test_custom_spells_survive_save_and_load(self):
        g = rich_game()
        s = self._fusion_ready(g)
        self._until_success(g, s, "ember", "gust", "Thunder Spear")
        key = spells.fused_key("ember", "gust")
        data = g.to_dict()
        spells.forget_custom(key)                       # simulate a fresh process
        self.assertNotIn(key, ABILITIES)
        h = Game.from_dict(data)
        self.assertIn(key, ABILITIES)
        self.assertEqual(get_ability(key).name, "Thunder Spear")
        self.assertIn(key, h.slime(s.id).spells)
        self.assertIn(key, h.library.discovered)
        self.assertEqual(h.slime(s.id).style_xp, s.style_xp)
        self.assertEqual(h.slime(s.id).morale, s.morale)
        self.assertEqual(h.slime(s.id).attuned, s.attuned)

    def test_fusion_kinds(self):
        a, b = get_ability("rain_mend"), get_ability("ember")
        x = spells.design_fusion(a, b)                  # heal + damage = drain, aoe because rain_mend is
        self.assertEqual((x.kind, x.element, x.target), ("drain", "steam", "all_enemies"))
        y = spells.design_fusion(get_ability("stone_skin"), get_ability("rain_mend"))
        self.assertEqual((y.kind, y.element), ("guard", "mud"))


class TestBattleMagic(Cleanup):
    def _fight(self, seed, element_enemy, spell_key, mastery=0, archetype="mage"):
        g = rich_game(seed)
        s = scholar(g, archetype, 3)
        add_xp(s, 50)
        s.attuned = list(elements.components(get_ability(spell_key).element))
        for b in s.attuned:
            s.mastery_xp[b] = config.MASTERY_XP[mastery - 1] if mastery else 0
        s.spells = [spell_key]
        s.known_abilities = lambda: [spell_key]      # isolate the spell from class abilities
        s.hp = s.max_hp
        foe = Enemy("dummy", "Dummy", "🎯", 1, dict(hp=1000, atk=0, defense=0, mag=0, spd=1), ["splat"],
                    1, {}, element=element_enemy)
        bs = BattleSystem(random.Random(seed))
        rep = bs.run([s], [foe])
        dmg = [int(l.split(": ")[1].split(" dmg")[0]) for l in rep.log if f"uses" in l and "dmg" in l
               and get_ability(spell_key).name in l]
        return s, rep, dmg

    def test_advantage_beats_resist(self):
        _, rep_w, dmg_w = self._fight(1, "fire", "water_jet")      # water > fire
        _, rep_r, dmg_r = self._fight(1, "water", "water_jet")     # water vs water: neutral
        _, rep_x, dmg_x = self._fight(1, "earth", "water_jet")     # earth > water: resisted
        self.assertGreater(sum(dmg_w) / len(dmg_w), sum(dmg_r) / len(dmg_r) * 1.3)
        self.assertLess(sum(dmg_x) / len(dmg_x), sum(dmg_r) / len(dmg_r) * 0.85)
        self.assertTrue(any("WEAK" in l for l in rep_w.log))
        self.assertTrue(any("resisted" in l for l in rep_x.log))

    def test_mastery_boosts_spells(self):
        _, _, low = self._fight(2, "", "ember", mastery=1)
        _, _, high = self._fight(2, "", "ember", mastery=4)
        self.assertGreater(sum(high) / len(high), sum(low) / len(low))

    def test_non_mage_spells_use_attack(self):
        _, _, barb = self._fight(3, "", "ember", mastery=2, archetype="barbarian")
        _, _, nec = self._fight(3, "", "ember", mastery=2, archetype="rogue")
        self.assertGreater(sum(barb) / len(barb), 8)               # barbarian atk >> its mag
        self.assertGreater(sum(nec) / len(nec), 5)

    def test_casting_builds_mastery(self):
        s, rep, _ = self._fight(4, "", "ember", mastery=1)
        self.assertGreater(s.mastery_xp["fire"], config.MASTERY_XP[0])


if __name__ == "__main__":
    unittest.main()
