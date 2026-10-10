import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from slime_gacha.abilities import Ability, register_ability
from slime_gacha.archetypes import ARCHETYPES, Archetype, register_archetype
from slime_gacha.battle import BattleSystem, Enemy
from slime_gacha.errors import InvalidAction, NotEnoughResources
from slime_gacha.game import Game
from slime_gacha.growth import add_xp, evolve, merge_gain
from slime_gacha.resources import ResourceManager


def fresh(seed=1, n=0):
    g = Game(seed)
    g.wallet.add("gel", 100000)
    if n:
        g.pull(n)
    return g


class TestResources(unittest.TestCase):
    def test_atomic_spend(self):
        w = ResourceManager({"gel": 10, "food": 1})
        with self.assertRaises(NotEnoughResources):
            w.spend_many({"gel": 5, "food": 2})
        self.assertEqual(w.get("gel"), 10)       # nothing changed


class TestGacha(unittest.TestCase):
    def test_six_classes_registered(self):
        for k in ("barbarian", "mage", "medic", "rogue", "ranger", "necromancer"):
            self.assertIn(k, ARCHETYPES)

    def test_costs_gel_and_fails_when_poor(self):
        g = Game(1)
        g.pull(1)
        self.assertEqual(g.wallet.get("gel"), config.STARTING_WALLET["gel"] - config.PULL_COST)
        g.wallet.spend("gel", g.wallet.get("gel"))
        with self.assertRaises(NotEnoughResources):
            g.pull(1)

    def test_pity_legendary(self):
        g = fresh(3)
        g.gacha.since_legendary = config.PITY_LEGENDARY - 1
        self.assertEqual(g.pull(1)[0].rarity, "legendary")
        self.assertEqual(g.gacha.since_legendary, 0)

    def test_pity_epic_within_ten(self):
        g = fresh(5)
        rs = [g.pull(1)[0].rarity for _ in range(config.PITY_EPIC)]
        self.assertTrue(any(r in ("epic", "legendary") for r in rs))

    def test_rarity_scales_stats(self):
        g = fresh(2)
        a = g.gacha.make_slime("common", "mage")
        b = g.gacha.make_slime("legendary", "mage")
        a.variance = b.variance = {k: 1.0 for k in a.variance}
        self.assertGreater(b.max_stats()["mag"], a.max_stats()["mag"] * 2)

    def test_deterministic_with_seed(self):
        a = [(s.name, s.archetype, s.rarity) for s in fresh(9, 10).slimes()]
        b = [(s.name, s.archetype, s.rarity) for s in fresh(9, 10).slimes()]
        self.assertEqual(a, b)


class TestNeeds(unittest.TestCase):
    def test_auto_sleep_and_wake(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        s.needs.set("energy", 10)
        g.tick(1)
        self.assertEqual(s.state, "sleeping")
        g.tick(10)
        self.assertEqual(s.state, "idle")
        self.assertGreaterEqual(s.needs.get("energy"), config.AUTO_WAKE_AT - 20)

    def test_auto_eat_uses_food(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        s.needs.set("food", 20)
        before = g.wallet.get("food")
        g.tick(1)
        self.assertEqual(g.wallet.get("food"), before - 1)

    def test_maslow_gating(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        s.needs.set("food", 5)
        g.needs.auto_care = False
        e = s.needs.get("esteem")
        g.tick(3)
        self.assertEqual(s.needs.get("esteem"), e)      # higher tier frozen while food unmet
        self.assertEqual(s.needs.dominant(), "food")

    def test_mood_drops_when_hungry(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        happy = s.power_multiplier()
        s.needs.set("food", 0)
        self.assertLess(s.power_multiplier(), happy)


class TestConflict(unittest.TestCase):
    def test_conflict_mediation(self):
        g = fresh(1, 2)
        a, b = g.slimes()
        from slime_gacha.ai import Conflict
        g.conflicts.conflicts.append(Conflict(1, a.id, b.id, 1, 0, "test"))
        g.wallet.add("food", 5)
        g.mediate(1, "snack")
        self.assertEqual(g.conflicts.conflicts, [])
        self.assertIn(frozenset((a.id, b.id)), g.conflicts.friends)

    def test_brawl_grounds(self):
        g = fresh(1, 2)
        a, b = g.slimes()
        from slime_gacha.ai import Conflict
        g.needs.auto_care = False
        g.conflicts.conflicts.append(Conflict(1, a.id, b.id, 3, config.CONFLICT_ESCALATE_TICKS - 1, "x"))
        g.conflicts.tick(g.slimes(), [])
        self.assertTrue(a.grounded and b.grounded)
        with self.assertRaises(InvalidAction):
            g.hunt(a.id, "meadow")


class TestHunt(unittest.TestCase):
    def test_hunt_completes_and_pays(self):
        g = fresh(4, 1)
        s = g.slimes()[0]
        g.needs.auto_care = False
        gel = g.wallet.get("gel")
        g.hunt(s.id, "meadow")
        self.assertEqual(s.state, "hunting")
        g.tick(3)
        self.assertEqual(s.state, "idle")
        self.assertGreater(g.wallet.get("gel"), gel)
        self.assertGreater(s.total_xp, 0)

    def test_cannot_hunt_when_exhausted(self):
        g = fresh(4, 1)
        s = g.slimes()[0]
        s.needs.set("energy", 5)
        with self.assertRaises(InvalidAction):
            g.hunt(s.id, "meadow")


class TestGrowth(unittest.TestCase):
    def test_levelling_and_cap(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        add_xp(s, 10 ** 6)
        self.assertEqual(s.level, s.level_cap)

    def test_evolve_requires_cap_and_essence(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        with self.assertRaises(InvalidAction):
            evolve(s, g.wallet)
        add_xp(s, 10 ** 6)
        with self.assertRaises(NotEnoughResources):
            evolve(s, g.wallet)
        g.wallet.add("essence", 500)
        hp = s.max_hp
        evolve(s, g.wallet)
        self.assertEqual(s.stage, 1)
        self.assertGreater(s.max_hp, hp)

    def test_merge_transfers_xp_percentage(self):
        g = fresh(1, 2)
        t, d = g.slimes()
        add_xp(d, 500)
        expect = merge_gain(t, d)
        self.assertGreaterEqual(expect, int(500 * config.MERGE_XP_RATIO))
        before = t.total_xp
        g.merge(t.id, d.id)
        self.assertEqual(t.total_xp - before, expect)
        self.assertNotIn(d.id, g.roster)
        with self.assertRaises(InvalidAction):
            g.merge(t.id, t.id)


class TestBattle(unittest.TestCase):
    def test_battle_deterministic(self):
        def run():
            g = fresh(11, 3)
            return g.battle([s.id for s in g.slimes()], 1).log
        self.assertEqual(run(), run())

    def test_boss_is_hard_and_hp_written_back(self):
        g = fresh(11, 3)
        party = g.slimes()
        rep = g.battle([s.id for s in party], 4)
        self.assertIn(rep.winner, ("foes", None))
        self.assertTrue(all(1 <= s.hp <= s.max_hp for s in party))

    def test_victory_pays_loot_and_xp(self):
        g = fresh(2)
        for _ in range(3):
            s = g.gacha.make_slime("legendary", "barbarian")
            g.roster[s.id] = s
            add_xp(s, 2000)
            s.hp = s.max_hp
        gel = g.wallet.get("gel")
        rep = g.battle([s.id for s in g.slimes()], 1)
        self.assertTrue(rep.victory)
        self.assertGreater(g.wallet.get("gel"), gel)

    def test_necromancer_summons(self):
        g = fresh(8)
        s = g.gacha.make_slime("epic", "necromancer")
        g.roster[s.id] = s
        add_xp(s, 2000)
        s.hp = s.max_hp
        rep = g.battle([s.id], 1)
        self.assertTrue(any("Bone Pal" in l for l in rep.log))


class TestExtensibility(unittest.TestCase):
    def test_add_bard_class_without_touching_engine(self):
        register_ability(Ability("inspire", "Inspire", "heal", 0.5, "mag", "all_allies", 2))
        register_archetype(Archetype(
            "bard", "Bard", "🎵", dict(hp=20, atk=3, defense=3, mag=8, spd=6),
            dict(hp=3, atk=.5, defense=.5, mag=1.5, spd=.5), {1: "inspire"}, "heal"))
        try:
            g = fresh(1)
            s = g.gacha.make_slime("rare", "bard")
            g.roster[s.id] = s
            self.assertEqual(s.known_abilities(), ["inspire"])
            g.battle([s.id], 1)                      # works in battle too
            seen = {x.archetype for x in fresh(1, 200).slimes()}
            self.assertIn("bard", seen)              # appears in the gacha pool
        finally:
            ARCHETYPES.unregister("bard")

    def test_bad_archetype_rejected(self):
        with self.assertRaises(ValueError):
            register_archetype(Archetype("bad", "Bad", "x", dict(hp=1), dict(hp=1), {}))


class TestPersistence(unittest.TestCase):
    def test_roundtrip(self):
        g = fresh(6, 5)
        g.hunt(g.slimes()[0].id, "grove")
        g.tick(7)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            g.save(p)
            h = Game.load(p)
        self.assertEqual(g.to_dict()["slimes"], h.to_dict()["slimes"])
        self.assertEqual(g.wallet.to_dict(), h.wallet.to_dict())
        g.tick(5)
        h.tick(5)                                    # RNG state restored -> same future
        self.assertEqual(g.to_dict()["slimes"], h.to_dict()["slimes"])


if __name__ == "__main__":
    unittest.main()
