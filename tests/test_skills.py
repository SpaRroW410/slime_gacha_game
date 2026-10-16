"""The 24 rarity skills and 6 evolution skills (attributes.py) built on the fx mechanics."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import attributes, config, fx
from slime_gacha.abilities import get_ability
from slime_gacha.battle import BattleSystem, KIND_HANDLERS
from tests.test_fx import mk, use
from tests.test_delves import rich, party, members

CLASSES = ("barbarian", "mage", "medic", "rogue", "ranger", "necromancer")


def arena(seed=1, foes=2):
    bs = BattleSystem(random.Random(seed))
    a = mk("A", "party", atk=60, mag=60)
    ts = [mk(f"T{i}", "foes", hp=2000.0) for i in range(foes)]
    ev = [a] + ts
    bs._everyone = ev
    return bs, a, ts, ev, []


class TestSkillTables(unittest.TestCase):
    def test_four_rarity_skills_and_one_evolution_pair_per_class(self):
        for cls in CLASSES:
            self.assertEqual(len(attributes.RARITY_SKILLS[cls]), 4)
            self.assertEqual(len(attributes.EVOLUTION_SKILLS[cls]), 2)
            for key in attributes.RARITY_SKILLS[cls] + [a.key for a in attributes.EVOLUTION_SKILLS[cls]]:
                ab = get_ability(key)
                for f in ab.fx:
                    self.assertIn(f[0], fx.__doc__, f"{key}: unknown effect {f[0]}")

    def test_slimes_get_one_skill_per_rarity_and_evolution_ranks(self):
        g = rich(41)
        s = g.gacha.make_slime("common", "mage")
        self.assertEqual(attributes.rarity_skills(s), [])
        for i, r in enumerate(config.RARITIES):
            s.rarity = r
            self.assertEqual(len(attributes.rarity_skills(s)), i)
        s.stage = 0
        self.assertNotIn("arcane_focus", s.known_abilities())
        s.stage = 1
        self.assertIn("arcane_focus", s.known_abilities())
        s.stage = 2
        ks = s.known_abilities()
        self.assertIn("arcane_focus_ii", ks)
        self.assertNotIn("arcane_focus", ks)


class TestRaritySkillsInAction(unittest.TestCase):
    def go(self, key, targets=None, seed=1, foes=2):
        bs, a, ts, ev, log = arena(seed, foes)
        ab = get_ability(key)
        tg = targets(a, ts) if targets else ts[:1]
        use(bs, a, ab, tg, ev, log)
        return bs, a, ts, ev, log

    def test_barbarian(self):
        _, _, ts, _, _ = self.go("moon_slash")
        self.assertTrue(ts[0].bleed)
        _, a, _, _, _ = self.go("titan_break", lambda a, ts: ts)
        self.assertEqual(a.extra_turns, 1)
        stunned = sum(bool(self.go("earthsplitter", seed=s)[2][0].stun) for s in range(40))
        self.assertTrue(5 < stunned < 35)

    def test_mage(self):
        bs, a, ts, ev, log = self.go("starfall", lambda a, ts: ts)
        self.assertEqual(sum("Starfall" in l for l in log), 2)
        bs, a, ts, ev, log = arena()
        bs.choose_ability = lambda *x: get_ability("void_rift")
        a.abilities = ["void_rift"]
        hp = ts[0].hp
        bs._turn(a, ev, log)
        self.assertEqual(ts[0].hp, hp)                      # nothing yet: the rift lands next round
        self.assertTrue(bs.delayed)

    def test_medic(self):
        bs, a, ts, ev, log = arena()
        a.poison, a.stun = (3, 4), 1
        a.hp = 50
        use(bs, a, get_ability("healing_light"), [a], ev, log)
        self.assertFalse(a.poison[0] or a.stun)
        bs, a, ts, ev, log = arena()
        use(bs, a, get_ability("sanctuary_mist"), [a], ev, log)
        self.assertGreater(a.mods["regen"], 0)
        bs, a, ts, ev, log = arena()
        use(bs, a, get_ability("aegis_bloom"), [a], ev, log)
        self.assertGreater(a.shield, 0)

    def test_rogue(self):
        _, _, ts, _, log = self.go("thousand_cuts", lambda a, ts: ts)
        self.assertGreaterEqual(sum("Thousand Cuts" in l for l in log), 6 - 2)     # 3 hits x 2 foes, minus dodges
        _, _, ts, _, _ = self.go("death_mark")
        self.assertGreater(ts[0].marked[0], 0)
        bs, a, ts, ev, log = arena()
        v = get_ability("viper_kiss")
        use(bs, a, v, [ts[0]], ev, log)
        first = ts[0].poison[1]
        use(bs, a, v, [ts[0]], ev, log)
        self.assertGreater(ts[0].poison[1], first)

    def test_ranger(self):
        _, _, ts, _, _ = self.go("rain_of_stars", lambda a, ts: ts)
        self.assertAlmostEqual(ts[0].stat("spd"), 7.0)
        _, _, ts, _, log = self.go("hawkeye")
        self.assertIn("CRIT", "".join(log))

    def test_necromancer(self):
        _, a, ts, ev, _ = self.go("bone_spear")
        self.assertEqual(sum(c.minion for c in ev), 1)
        _, a, ts, ev, _ = self.go("legion_of_bones", lambda a, ts: [a])
        self.assertEqual(sum(c.minion for c in ev), 3)
        _, a, ts, ev, _ = self.go("plague_cloud", lambda a, ts: ts[:1])
        self.assertTrue(ts[1].poison[0] > 0)

    def test_evolution_skills(self):
        bs, a, ts, ev, log = arena()
        use(bs, a, get_ability("berserkers_oath_ii"), [a], ev, log)
        self.assertEqual(a.oath, 0.9)
        for key, check in (("arcane_focus", lambda: a.mods.get("spell_power", 0) > 0),
                           ("vanish", lambda: a.untarget == 2)):
            bs, a, ts, ev, log = arena()
            use(bs, a, get_ability(key), [a], ev, log)
            self.assertTrue(check(), key)
        bs, a, ts, ev, log = arena()
        use(bs, a, get_ability("mark_prey"), [ts[0]], ev, log)
        self.assertGreater(ts[0].marked[0], 0)
        use(bs, a, get_ability("sacred_ward"), [a], ev, log)
        self.assertGreater(a.mods["guard"], 0)
        use(bs, a, get_ability("soul_tithe"), [a], ev, log)           # no minion: nothing to sacrifice, no crash


class TestSkillsInRealBattles(unittest.TestCase):
    def test_every_class_fights_with_its_new_skills(self):
        from tests.test_game import full_party, fresh
        for i, cls in enumerate(CLASSES):
            g = fresh(100 + i)
            pid = full_party(g, cls, "legendary", 200000)
            for s in members(g, pid):
                s.stage = 2
            rep = g.battle(pid, 2)
            self.assertIn(rep.winner, ("party", "foes", None))
            self.assertTrue(rep.log)


if __name__ == "__main__":
    unittest.main()
