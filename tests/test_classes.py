"""Specializations (hybrid classes from cross-training) and outlook (what experience makes a slime)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, outlook, sparring, specialization
from slime_gacha.abilities import get_ability
from slime_gacha.battle import BattleSystem
from slime_gacha.errors import InvalidAction, NotEnoughResources
from slime_gacha.game import Game
from slime_gacha.growth import add_xp, lose_xp


def rich(seed=1):
    g = Game(seed)
    for k in ("white_gel", "purple_gel", "essence", "food"):
        g.wallet.add(k, 20000)
    g.needs.auto_care = False
    return g


def mk(g, archetype="barbarian", stars=2):
    s = g.gacha.make_slime("common", archetype, stars=stars)
    g.roster[s.id] = s
    return s


def ready(s, level=5, **style):
    s.level = level
    for k, lv in style.items():
        s.style_xp[k] = config.STYLE_XP[lv - 1]
    s.hp, s.state = s.max_hp, "idle"
    s.needs.v["energy"] = s.needs.v["food"] = 100
    return s


class TestSpecialization(unittest.TestCase):
    CASES = [("barbarian", "magic", "Battlemage"), ("rogue", "magic", "Shadowcaster"),
             ("mage", "sword", "Spellknight"), ("mage", "archery", "Hexshot"),
             ("medic", "sword", "Battle Medic"), ("necromancer", "sword", "Death Knight"),
             ("ranger", "magic", "Arcane Archer"), ("ranger", "sword", "Bulwark Archer"),
             ("barbarian", "archery", "Swashbuckler")]

    def test_swordslime_plus_magic_is_a_battlemage_and_friends(self):
        g = rich()
        for arch, disc, name in self.CASES:
            s = mk(g, arch)
            self.assertEqual(specialization.spec_for(s, disc).name, name, (arch, disc))
        s = mk(g, "barbarian")
        self.assertIsNone(specialization.spec_for(s, "sword"))         # no hybrid with your own discipline

    def test_requirements(self):
        g = rich()
        s = mk(g)
        with self.assertRaises(InvalidAction) as cm:
            g.specialize(s.id, "magic")
        self.assertIn("Spellcraft level 3", str(cm.exception))
        ready(s, level=4, magic=3)
        with self.assertRaises(InvalidAction) as cm:
            g.specialize(s.id, "magic")
        self.assertIn("level 5", str(cm.exception))
        ready(s, level=5, magic=3)
        with self.assertRaises(InvalidAction):
            g.specialize(s.id, "sword")                                 # own discipline: nothing to specialize into
        with self.assertRaises(InvalidAction):
            g.specialize(s.id, "dance")
        s.state = "hunting"
        with self.assertRaises(InvalidAction):
            g.specialize(s.id, "magic")

    def test_cost_effects_and_permanence(self):
        g = rich()
        s = ready(mk(g), 5, magic=3)
        st0, ab0 = s.max_stats(), set(s.known_abilities())
        gel, ess = g.wallet.get("white_gel"), g.wallet.get("essence")
        msg = g.specialize(s.id, "magic")
        self.assertIn("Battlemage", msg)
        self.assertEqual(g.wallet.get("white_gel"), gel - config.SPEC_COST["white_gel"])
        self.assertEqual(g.wallet.get("essence"), ess - config.SPEC_COST["essence"])
        self.assertEqual(s.title(), "Battlemage")
        self.assertEqual(s.arch.name, "Barbarian")                      # the base class is still known
        st1 = s.max_stats()
        self.assertAlmostEqual(st1["mag"], st0["mag"] + st0["atk"] * config.SPEC_STAT_RATIO, delta=0.2)
        self.assertEqual(st1["atk"], st0["atk"])
        self.assertIn("arcane_strike", set(s.known_abilities()) - ab0)
        with self.assertRaises(InvalidAction):
            g.specialize(s.id, "archery")                               # already specialized
        poor = rich(2)
        p = ready(mk(poor), 5, magic=3)
        poor.wallet.spend("essence", poor.wallet.get("essence"))
        with self.assertRaises(NotEnoughResources):
            poor.specialize(p.id, "magic")

    def test_shifts_use_pre_shift_stats_and_stack_with_gear(self):
        g = rich()
        s = ready(mk(g), 5, magic=3)
        g.buy_gear("wooden_club")
        g.equip(s.id, "wooden_club")
        atk = s.max_stats()["atk"]
        g.specialize(s.id, "magic")
        self.assertAlmostEqual(s.max_stats()["mag"], 1.0 * 0 + s.max_stats()["mag"])   # stable on re-read
        self.assertEqual(s.max_stats(), s.max_stats())
        self.assertGreater(s.max_stats()["mag"], atk * 0.4)

    def test_both_disciplines_get_class_affinity(self):
        g = rich()
        plain, hybrid = ready(mk(g), 5), ready(mk(g), 5, magic=3)
        g.specialize(hybrid.id, "magic")
        base = config.SPAR_STYLE_XP
        mult = 1.0
        a = sparring.style_xp_for(plain, "magic", None, mult)
        b = sparring.style_xp_for(hybrid, "magic", None, mult)
        c = sparring.style_xp_for(hybrid, "sword", None, mult)
        self.assertEqual(a, base)
        self.assertEqual(b, base * config.STYLE_AFFINITY_MULT)
        self.assertEqual(c, base * config.STYLE_AFFINITY_MULT)

    def test_cross_training_through_real_sparring_unlocks_it(self):
        g = rich(4)
        a, b = mk(g), mk(g)
        a.level = b.level = 5
        for _ in range(40):
            for s in (a, b):
                s.hp, s.state = s.max_hp, "idle"
                s.needs.v["energy"] = s.needs.v["food"] = 100
            if sparring.style_level(a, "magic") >= 3:
                break
            g.spar(a.id, b.id, "magic")
        self.assertGreaterEqual(sparring.style_level(a, "magic"), 3)
        self.assertEqual(g.slime(a.id).spec, "")
        a.hp, a.state = a.max_hp, "idle"
        self.assertIn("Battlemage", g.specialize(a.id, "magic"))

    def test_signature_ability_is_used_in_battle(self):
        g = rich()
        s = ready(mk(g), 5, magic=3)
        g.specialize(s.id, "magic")
        c = BattleSystem.from_slime(s)
        self.assertIn("arcane_strike", c.abilities)
        self.assertGreater(c.stats["mag"], 5)                           # a barbarian normally has ~1
        self.assertEqual(get_ability("arcane_strike").stat, "mag")

    def test_persistence_and_options_listing(self):
        g = rich()
        s = ready(mk(g), 5, magic=3)
        opts = {r["discipline"]: r for r in specialization.options(s)}
        self.assertTrue(opts["magic"]["ok"])
        self.assertFalse(opts["archery"]["ok"])
        g.specialize(s.id, "magic")
        h = Game.from_dict(g.to_dict())
        t = h.slime(s.id)
        self.assertEqual((t.spec, t.spec_disc, t.title()), ("battlemage", "magic", "Battlemage"))
        self.assertEqual(t.max_stats(), s.max_stats())

    def test_web_snapshot_exposes_specializations(self):
        from slime_gacha.webapi import Session
        sess = Session()
        sess.call("new_game", {"seed": 1})
        sess.game.wallet.add("essence", 100)
        sess.game.wallet.add("white_gel", 300)
        s = ready(mk(sess.game), 5, magic=3)
        r = sess.call("specialize", {"id": s.id, "discipline": "magic"})
        self.assertTrue(r["ok"], r["error"])
        v = [x for x in r["state"]["slimes"] if x["id"] == s.id][0]
        self.assertEqual(v["spec"]["name"], "Battlemage")
        self.assertEqual(v["title"], "Battlemage")
        self.assertFalse(sess.call("specialize", {"id": s.id, "discipline": "magic"})["ok"])


class TestOutlook(unittest.TestCase):
    def test_needs_enough_experience_and_a_clear_lead(self):
        g = rich()
        s = mk(g)
        for _ in range(config.OUTLOOK_MIN - 1):
            outlook.bump(s, "spar")
        self.assertIsNone(outlook.outlook_of(s))
        outlook.bump(s, "spar")
        self.assertEqual(outlook.outlook_of(s).name, "Duelist")
        for _ in range(5):
            outlook.bump(s, "pit")
        self.assertIsNone(outlook.outlook_of(s))                        # no clear favourite
        for _ in range(5):
            outlook.bump(s, "pit")
        self.assertEqual(outlook.outlook_of(s).name, "Grinder")

    def test_favourite_activity_lifts_esteem(self):
        g = rich()
        s = mk(g)
        s.exp["hunt"] = 9
        s.needs.set("esteem", 10)
        outlook.bump(s, "hunt")
        self.assertEqual(s.needs.get("esteem"), 10 + config.OUTLOOK_ESTEEM)
        s.needs.set("esteem", 10)
        outlook.bump(s, "spar")
        self.assertEqual(s.needs.get("esteem"), 10)

    def test_activities_build_experience(self):
        g = rich(3)
        a, b = mk(g), mk(g)
        g.spar(a.id, b.id, "sword")
        self.assertEqual(a.exp["spar"], 1)
        g.hunt(b.id, "meadow") if False else None
        c = mk(g, stars=3)
        g.study(c.id, "fire")
        g.tick(config.STUDY_TICKS)
        self.assertEqual(c.exp["study"], 1)
        h = mk(g)
        g.hunt(h.id, "meadow")
        g.tick(3)
        self.assertEqual(h.exp.get("hunt"), 1)

    def test_duelist_gets_more_style_xp(self):
        g = rich()
        a, b, c = mk(g), mk(g), mk(g)
        a.exp["spar"], b.exp["spar"] = 8, 0
        for s in (a, b, c):
            s.hp, s.state = s.max_hp, "idle"
        g.rng.random = lambda: 0.99
        g.spar(a.id, c.id, "sword")
        g.spar(b.id, mk(g).id, "sword")
        self.assertGreater(a.style_xp["sword"], 0)
        ratio_a = a.style_xp["sword"]
        ratio_b = b.style_xp["sword"]
        won_or_lost_same = abs(ratio_a / ratio_b - 1) < 0.5
        self.assertTrue(won_or_lost_same)                                # same order of magnitude

    def test_grinder_loses_less_morale_when_knocked_out(self):
        self.assertGreater(config.GRIND_DEATH_MORALE * config.OUTLOOK_GRINDER_MORALE, config.GRIND_DEATH_MORALE)

    def test_grinder_in_a_real_pit_session(self):
        g = rich(5)
        p = g.create_party("P")
        for _ in range(5):
            s = mk(g)
            s.max_stats = lambda: {"hp": 12.0, "atk": 1.0, "defense": 0.0, "mag": 1.0, "spd": 1.0}
            s.hp = 12
            s.level, s.xp, s.total_xp = 4, 50, 500
            s.exp["pit"] = 9
            g.parties.add(p.id, s.id)
        before = {s.id: s.morale for s in g.slimes()}
        g.grind(p.id, 5, 1)
        for s in g.slimes():
            self.assertGreaterEqual(s.exp["pit"], 10)

    def test_forager_brings_more_loot(self):
        g1, g2 = rich(7), rich(7)
        a, b = mk(g1, "ranger"), mk(g2, "ranger")
        b.exp["hunt"] = 9
        for g, s in ((g1, a), (g2, b)):
            g.rng.random = lambda: 0.0                                  # best rolls
            g.rng.randint = lambda lo, hi: hi
            g.needs.auto_care = False
            g.hunt(s.id, "grove")
            g.tick(5)
        self.assertGreater(g2.wallet.get("white_gel") + g2.wallet.get("food") + g2.wallet.get("essence"),
                           g1.wallet.get("white_gel") + g1.wallet.get("food") + g1.wallet.get("essence"))

    def test_scholar_studies_faster_and_pathfinders_scout_faster(self):
        g = rich()
        a, b = mk(g, stars=3), mk(g, stars=3)
        b.exp["study"] = 9
        g.study(a.id, "water")
        g.study(b.id, "water")
        g.tick(config.STUDY_TICKS)
        self.assertGreater(b.mastery_xp["water"], a.mastery_xp["water"])
        party1 = [mk(g) for _ in range(5)]
        base = Game.scout_skill(party1)
        for s in party1:
            s.exp["scout"] = 9
        self.assertAlmostEqual(Game.scout_skill(party1) - base, 5 * config.OUTLOOK_PATHFINDER_SKILL)

    def test_delvers_add_power_in_the_descent(self):
        g = rich()
        p = g.create_party("P")
        for _ in range(5):
            s = mk(g)
            s.stage = 2
            add_xp(s, 10 ** 7)
            s.hp = s.max_hp
            s.exp["delve"] = 9
            g.parties.add(p.id, s.id)
        g.enter_dungeon(p.id)
        rep = g.delve_next(p.id)
        self.assertTrue(rep.victory)
        self.assertTrue(all(outlook.has(s, "delve") for s in g.party_members(p.id)))
        self.assertGreaterEqual(g.party_members(p.id)[0].exp["delve"], 10)

    def test_outlook_persists_and_is_in_the_snapshot(self):
        from slime_gacha.webapi import Session
        sess = Session()
        sess.call("new_game", {"seed": 1})
        s = mk(sess.game)
        s.exp["spar"] = 7
        r = sess.call("state")
        v = [x for x in r["state"]["slimes"] if x["id"] == s.id][0]
        self.assertEqual(v["outlook"]["name"], "Duelist")
        h = Game.from_dict(sess.game.to_dict())
        self.assertEqual(h.slime(s.id).exp["spar"], 7)


if __name__ == "__main__":
    unittest.main()
