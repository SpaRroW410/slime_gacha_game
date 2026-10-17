"""Hybrid skills and capstones: weaker than pure ones, scaled by the second discipline's proficiency."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import attributes, config, fx, specialization
from slime_gacha.abilities import get_ability
from slime_gacha.battle import BattleSystem
from slime_gacha.game import Game
from tests.test_fx import mk, use
from tests.test_delves import rich, party, members


def hybrid(g, cls="mage", spec="battlemage", disc="sword", rarity="legendary", stars=5):
    s = g.gacha.make_slime(rarity, cls, stars=stars)
    g.roster[s.id] = s
    s.spec, s.spec_disc = spec, disc
    return s


class TestHybridSkills(unittest.TestCase):
    def test_nine_hybrid_capstones_one_per_spec(self):
        self.assertEqual(set(specialization.HYBRID_CAPSTONES), set(specialization.SPECS))
        self.assertEqual(len(specialization.HYBRID_CAPSTONES), 9)

    def test_capstone_needs_legendary_five_star_and_scales_with_second_proficiency(self):
        g = rich(61)
        s = hybrid(g)
        self.assertEqual(attributes.hybrid_capstone(s), "overload")
        self.assertIn("overload", s.known_abilities())
        self.assertIn("arcane_strike", s.known_abilities())             # the signature skill, as before
        for rarity, stars in (("epic", 5), ("legendary", 4)):
            t = hybrid(g, rarity=rarity, stars=stars)
            self.assertIsNone(attributes.hybrid_capstone(t))
            self.assertNotIn("overload", t.known_abilities())
        s.spec_prof = 100
        self.assertAlmostEqual(attributes.hybrid_scale(s), 0.6)
        s.spec_prof = 0
        self.assertAlmostEqual(attributes.hybrid_scale(s), 0.3)

    def test_fx_scale_shrinks_amounts_not_durations(self):
        ab = get_ability("curse_barrage")
        small = fx.scale(ab, 0.5)
        self.assertAlmostEqual(small.power, ab.power * 0.5)
        deb = next(f for f in small.fx if f[0] == "debuff")
        self.assertAlmostEqual(deb[2], 0.15)
        self.assertEqual(deb[3], 3)
        ex = fx.scale(get_ability("assassinate"), 0.5)
        self.assertAlmostEqual(next(f for f in ex.fx if f[0] == "execute")[2], 2.0)

    def test_a_hybrid_capstone_hits_softer_than_the_same_skill_at_full_strength(self):
        def dmg(scale):
            bs = BattleSystem(random.Random(3))
            a, t = mk("A", "party", mag=100), mk("T", "foes", hp=10 ** 6, defense=0)
            ab = fx.scale(get_ability("overload"), scale)
            before = t.hp
            use(bs, a, ab, [t], [a, t], [])
            return before - t.hp
        self.assertLess(dmg(0.3), dmg(0.6))
        self.assertLess(dmg(0.6), dmg(1.0))

    def test_cast_in_battle_uses_the_slimes_scale(self):
        g = rich(62)
        s = hybrid(g)
        s.spec_prof = 100
        c = BattleSystem.from_slime(s)
        self.assertEqual(c.cap_scale, {"overload": 0.6})
        self.assertIn("arcane_strike", c.hybrid)

    def test_new_signature_effects_work(self):
        bs = BattleSystem(random.Random(2))
        a, t = mk("A", "party"), mk("T", "foes")
        use(bs, a, get_ability("riposte"), [t], [a, t], [])
        self.assertEqual(a.counter[0], 2)
        use(bs, a, get_ability("shield_volley"), [t], [a, t], [])
        self.assertGreater(a.shield, 0)
        use(bs, a, get_ability("shadow_bolt"), [t], [a, t], [])
        self.assertLess(t.stat("spd"), 10)
        friend = mk("F", "party")
        friend.hp = 20
        use(bs, a, get_ability("martyrs_smite"), [t], [a, t, friend], [])
        self.assertGreater(friend.hp, 20)
        t.last_ability = "smash"
        bs.choose_ability = lambda *x: get_ability("stolen_spell")
        a.abilities = ["stolen_spell"]
        log = []
        bs._turn(a, [a, t], log)
        self.assertTrue(any("copies" in l for l in log))


class TestSecondProficiencyAndDrift(unittest.TestCase):
    def test_specializing_starts_the_second_proficiency(self):
        g = rich(63)
        s = g.gacha.make_slime("common", "mage")
        g.roster[s.id] = s
        s.level = 30
        s.style_xp["sword"] = config.STYLE_XP[2]
        g.wallet.add_many({k: 10 ** 5 for k in config.SPEC_COST})
        g.specialize(s.id, "sword")
        self.assertEqual((s.spec, s.spec_prof), ("spellknight", config.PROF_SPEC_START))

    def test_sparring_in_the_secondary_discipline_feeds_the_second_proficiency(self):
        g = rich(64)
        s = hybrid(g, rarity="common", stars=1)
        s.spec_prof, s.class_prof = 40, 40
        Game.practise_discipline(s, "sword", 3, 1)           # the secondary discipline
        self.assertEqual((s.spec_prof, s.class_prof), (43, 40))
        Game.practise_discipline(s, "magic", 3, 1)           # the class's own discipline
        self.assertEqual(s.class_prof, 43)
        Game.practise_discipline(s, "archery", 3, 1)         # something else: a little general practice
        self.assertEqual(s.class_prof, 44)

    def test_pure_capstones_fade_while_the_hybrid_side_grows(self):
        g = rich(65)
        s = hybrid(g)                                       # legendary 5-star mage that specialized later
        s.pure_earned = True
        s.class_prof, s.spec_prof = 72, 40
        events = []
        for _ in range(config.PROF_IDLE_DAYS + 3):          # three idle days beyond the grace period
            g._proficiency_day(events)
        self.assertLess(s.class_prof, 70)
        self.assertEqual(attributes.capstones(s), ["edit_source"])            # the second pure capstone is lost first
        s.spec_idle = 0
        for _ in range(6):
            s.spec_prof = min(100, s.spec_prof + 3)         # keeps training the hybrid discipline
            s.spec_idle = 0
            g._proficiency_day(events)
        self.assertGreater(attributes.hybrid_scale(s), 0.45)
        self.assertLess(s.class_prof, 66)

    def test_hybrid_skill_use_in_a_fight_counts_for_the_second_proficiency(self):
        g = rich(66)
        pid = party(g, strong=True)
        s0 = members(g, pid)[0]
        s0.spec, s0.spec_disc = "battlemage", "sword"
        s0.spec_prof = 40
        g.battle(pid, 1)
        self.assertGreaterEqual(s0.spec_prof, 40)                # (a battlemage only gains by casting its own skills)

    def test_saved(self):
        g = rich(67)
        s = hybrid(g)
        s.spec_prof, s.spec_idle = 77.5, 4
        s2 = Game.from_dict(g.to_dict()).slime(s.id)
        self.assertEqual((s2.spec_prof, s2.spec_idle), (77.5, 4))


if __name__ == "__main__":
    unittest.main()
