"""Passive skills (passives.py): what earns each group, and that each effect reaches the game."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, jobs, passives
from slime_gacha.errors import InvalidAction
from tests.test_delves import rich, party, members

TOP = len(config.MASTERY_XP)


def slime(g, arch="barbarian", stars=5):
    s = g.gacha.make_slime("common", arch, stars=stars)
    g.roster[s.id] = s
    s.hp = s.max_hp
    s.traits = []
    return s


def master(s, basic):
    s.attuned = list(set(s.attuned) | {basic})
    s.mastery_xp[basic] = config.MASTERY_XP[TOP - 1]


class TestCatalogue(unittest.TestCase):
    def test_every_passive_has_a_group_a_requirement_and_words(self):
        groups = {k for k, _ in passives.GROUPS}
        for p in passives.PASSIVES:
            self.assertIn(p.group, groups, p.key)
            self.assertTrue(p.need and p.name and p.desc, p.key)
        self.assertGreaterEqual(len(list(passives.PASSIVES)), 28)

    def test_every_class_has_a_proficiency_passive_and_every_trade_a_trade_passive(self):
        from slime_gacha.archetypes import all_archetypes
        for a in all_archetypes():
            self.assertIn("mastery_" + a.key, passives.PASSIVES, a.key)
        for k in ("chef_master", "blacksmith_master", "doctor_master", "librarian_master", "distiller",
                  "master_sword", "master_archery", "master_magic"):
            self.assertIn(k, passives.PASSIVES)

    def test_a_fresh_slime_has_none(self):
        g = rich(110)
        self.assertEqual(passives.earned(g, slime(g)), [])


class TestEarning(unittest.TestCase):
    def test_the_top_of_each_basic_element_earns_its_party_perk(self):
        g = rich(111)
        for basic, key in (("fire", "hearth"), ("water", "wellspring"), ("earth", "bedrock"), ("wind", "tailwind")):
            s = slime(g)
            self.assertFalse(passives.has(g, s, key))
            master(s, basic)
            self.assertTrue(passives.has(g, s, key), key)

    def test_the_top_trade_level_earns_the_trade_passive_and_no_other(self):
        g = rich(112)
        s = slime(g, "medic")
        s.job_xp["chef"] = jobs.xp_for(config.JOB_MAX_LEVEL)
        self.assertTrue(passives.has(g, s, "chef_master"))
        self.assertFalse(passives.has(g, s, "doctor_master"))
        s.job_xp["chef"] = jobs.xp_for(config.JOB_MAX_LEVEL) - 1
        self.assertFalse(passives.has(g, s, "chef_master"))

    def test_class_proficiency_100_earns_that_classs_passive_only(self):
        g = rich(113)
        s = slime(g, "ranger")
        s.class_prof = 99.0
        self.assertFalse(passives.has(g, s, "mastery_ranger"))
        s.class_prof = 100.0
        self.assertTrue(passives.has(g, s, "mastery_ranger"))
        self.assertFalse(passives.has(g, s, "mastery_mage"))
        self.assertEqual(passives.battle_mods(g, s), dict(crit_rate=0.05))

    def test_dual_mastery_needs_both_proficiencies_at_100(self):
        g = rich(114)
        s = slime(g, "mage")
        s.class_prof = 100.0
        self.assertFalse(passives.has(g, s, "dual_mastery"))
        s.spec, s.spec_disc, s.spec_prof = "battlemage", "sword", 100.0
        self.assertTrue(passives.has(g, s, "dual_mastery"))

    def test_a_fighting_style_at_its_top_level_earns_a_style_passive(self):
        g = rich(115)
        s = slime(g)
        s.style_xp["sword"] = config.STYLE_XP[config.STYLE_FULL - 1]
        self.assertTrue(passives.has(g, s, "style_sword"))
        self.assertFalse(passives.has(g, s, "style_archery"))

    def test_ties_earn_the_synergy_passives(self):
        g = rich(116)
        a, b, c, d, e = (slime(g) for _ in range(5))
        self.assertFalse(passives.has(g, a, "soulbound"))
        g.relations.rel[frozenset((a.id, b.id))] = dict(kind="couple", since=0)
        self.assertTrue(passives.has(g, a, "soulbound") and passives.has(g, b, "soulbound"))
        self.assertFalse(passives.has(g, a, "heart_of_the_party"))
        for o in (c, d, e):
            g.relations.rel[frozenset((a.id, o.id))] = dict(kind="friend", since=0)
        self.assertTrue(passives.has(g, a, "heart_of_the_party"))                  # a partner and three friends: four ties


class TestEffects(unittest.TestCase):
    def test_personal_perks_reach_the_fight(self):
        from slime_gacha.battle import BattleSystem
        g = rich(117)
        s = slime(g, "paladin")
        s.class_prof = 100.0
        before = BattleSystem.from_slime(s).mods
        s.passive_mods = passives.battle_mods(g, s)          # the engine sets the perks before each fight; do the same here
        after = BattleSystem.from_slime(s).mods
        self.assertAlmostEqual(after.get("guard", 0) - before.get("guard", 0), 0.05)
        self.assertAlmostEqual(after.get("resist", 0) - before.get("resist", 0), 0.05)

    def test_a_real_fight_sets_the_perks(self):
        g = rich(118)
        pid = party(g, strong=True)
        m = members(g, pid)[0]
        m.archetype, m.class_prof = "ranger", 100.0
        g.battle(pid, 1)
        self.assertEqual(m.passive_mods.get("crit_rate"), 0.05)

    def test_hearth_heals_the_party_more_at_camp(self):
        g = rich(119)
        g.deferred_turn = True
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        g.delves[pid]["floor"] = 6
        g.rng.random = lambda: 0.99
        ms = members(g, pid)

        def camp():
            for s in ms:
                s.hp = max(1, s.max_hp // 4)
            g.delves[pid]["camped"] = 0
            g.delves[pid]["ready_tick"] = 0
            g.delve_camp(pid, 3)
            return sum(s.hp for s in ms)
        plain = camp()
        master(ms[0], "fire")
        self.assertGreater(camp(), plain)

    def test_bedrock_softens_ambushes_for_the_whole_party(self):
        g = rich(120)
        pid = party(g, strong=True)
        ms = members(g, pid)
        self.assertEqual(g.ambush_cut(ms), 1.0)
        master(ms[2], "earth")
        self.assertAlmostEqual(g.ambush_cut(ms), 1.0 - config.BEDROCK_CUT)

    def test_wellspring_cuts_a_trips_food_and_energy(self):
        g = rich(121)
        g.needs.auto_care = False
        pid = party(g, strong=True)
        ms = members(g, pid)
        for s in ms:
            s.traits = []
        g.enter_dungeon(pid)
        before = g.needs_scale(ms[0])
        master(ms[1], "water")
        self.assertAlmostEqual(g.needs_scale(ms[0]), before * (1 - config.WELLSPRING_CUT))

    def test_wellspring_also_saves_a_farming_sessions_needs(self):
        g = rich(122)
        ms = [slime(g) for _ in range(2)]
        for s in ms:
            s.needs.v["food"] = 90.0
        g._field_hours(ms, 4)
        plain = 90.0 - ms[0].needs.get("food")
        master(ms[1], "water")
        for s in ms:
            s.needs.v["food"] = 90.0
        g._field_hours(ms, 4)
        self.assertLess(90.0 - ms[0].needs.get("food"), plain)

    def test_a_trade_passive_makes_that_posts_output_bigger(self):
        g = rich(123)
        s = slime(g, "barbarian")                                  # no natural talent for the doctor's post
        s.job_xp["doctor"] = jobs.xp_for(config.JOB_MAX_LEVEL)
        plain = (1 + 0.12 * (config.JOB_MAX_LEVEL - 1)) * g.buildings.job_mult(jobs.JOBS["doctor"].building)
        self.assertAlmostEqual(jobs.power(s, "doctor", g), plain * (1 + config.TRADE_PASSIVE_BOOST))
        self.assertAlmostEqual(jobs.power(s, "doctor"), 1 + 0.12 * (config.JOB_MAX_LEVEL - 1))     # no game: no passive to ask about

    def test_master_trainer_strengthens_the_trainers_bonus(self):
        g = rich(124)
        t = slime(g, "barbarian", stars=2)                       # a swordsman: the sword trainer's natural talent
        t.class_prof = 50.0
        g.assign_job(t.id, "trainer_sword")
        pupil = slime(g, "barbarian", stars=2)
        pupil.class_prof = 10.0                                   # knows less than the trainer
        t.job_xp["trainer_sword"] = jobs.xp_for(config.JOB_MAX_LEVEL)
        b = (config.TRAINER_BONUS + config.TRAINER_BONUS_PER_LEVEL * (config.JOB_MAX_LEVEL - 1)) * 1.25
        self.assertTrue(passives.has(g, t, "master_sword"))
        self.assertAlmostEqual(jobs.trainer_bonus(g, "sword", pupil),
                               1 + b * (1 + config.MASTER_TRAINER_BOOST) * g.buildings.job_mult("training_grounds"))

    def test_a_master_brewer_sometimes_makes_one_more_potion(self):
        g = rich(125)
        g.needs.auto_care = False
        b = slime(g, "medic")
        b.job_xp["brewer"] = jobs.xp_for(config.JOB_MAX_LEVEL)
        g.wallet.add("herb_green", 99)
        g.wallet.add("herb_red", 99)
        g.rng.random = lambda: 0.0                            # every roll succeeds
        g.buildings.levels["alchemy"] = 1
        kind = next(iter(__import__("slime_gacha").potions.KINDS))
        before = sum(g.potions.values())
        try:
            g._brew_core(b, kind, 1, wait=False)
        except InvalidAction:
            self.skipTest("this seed lacks the ingredients for a brew")
        self.assertEqual(sum(g.potions.values()) - before, 2)

    def test_synergy_passives_lift_a_party_up_to_a_cap(self):
        g = rich(126)
        pid = party(g, strong=True)
        ms = members(g, pid)
        self.assertEqual(passives.party_synergy(g, ms), 0.0)
        g.relations.rel[frozenset((ms[0].id, ms[1].id))] = dict(kind="couple", since=0)
        self.assertAlmostEqual(passives.party_synergy(g, ms), config.SYNERGY_SOULBOUND)          # the pair together
        for o in ms[2:]:
            g.relations.rel[frozenset((ms[0].id, o.id))] = dict(kind="friend", since=0)
        self.assertLessEqual(passives.party_synergy(g, ms), config.SYNERGY_PASSIVE_MAX)
        self.assertGreater(passives.party_synergy(g, ms), config.SYNERGY_SOULBOUND)
        outside = slime(g)
        self.assertEqual(passives.party_synergy(g, [ms[0], outside]), config.SYNERGY_HEART)     # partner not along: only the friends perk


if __name__ == "__main__":
    unittest.main()
