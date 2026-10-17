"""Training gate: sleepers are woken at a mood cost, workers leave their job, wounded drills are worth less;
brawls sour the mood; farming dungeons hand out a little extra."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from slime_gacha.errors import InvalidAction
from tests.test_delves import rich, party, members
from tests.test_jobs import slime


class TestTrainingGate(unittest.TestCase):
    def test_waking_a_tired_sleeper_costs_mood_but_a_rested_one_is_free(self):
        g = rich(41)
        s = slime(g)
        s.state = "sleeping"
        s.needs.set("energy", 30)
        morale = s.morale
        out = g.wake(s.id)
        self.assertEqual(s.state, "idle")
        self.assertLess(s.morale, morale)
        self.assertIn("grumpy", out)
        r = slime(g)
        r.state = "sleeping"
        r.needs.set("energy", 60)
        morale = r.morale
        g.wake(r.id)
        self.assertEqual((r.state, r.morale), ("idle", morale))

    def test_a_drill_wakes_a_sleeper_and_pulls_a_worker_off_the_job(self):
        g = rich(42)
        a, b = slime(g, "barbarian"), slime(g, "medic")
        a.state = "sleeping"
        a.needs.set("energy", 40)
        morale = a.morale
        msg = g.drill(a.id, "sword")
        self.assertIn("grumpy", msg)
        self.assertLess(a.morale, morale)
        self.assertEqual(a.state, "studying")
        g.assign_job(b.id, "chef")
        g.drill(b.id, "magic")
        self.assertEqual((b.job, b.state), ("", "studying"))

    def test_a_too_tired_sleeper_is_refused_before_being_woken(self):
        g = rich(43)
        s = slime(g)
        s.state = "sleeping"
        s.needs.set("energy", 5)
        with self.assertRaises(InvalidAction):
            g.drill(s.id, "magic")
        self.assertEqual(s.state, "sleeping")

    def test_a_hurt_slime_drills_for_less(self):
        g = rich(44)
        a, b = slime(g, "barbarian"), slime(g, "barbarian")
        a.hp = max(1, a.max_hp // 4)
        g.needs.auto_care = False
        g.drill(a.id, "sword")
        g.drill(b.id, "sword")
        pa, pb = a.class_prof, b.class_prof
        g.tick(config.DRILL_TICKS + 1)
        self.assertLess(a.class_prof - pa, b.class_prof - pb)

    def test_party_spar_is_flat_three_and_a_duel_is_two(self):
        g = rich(45)
        pid, other = party(g, name="A"), party(g, name="B")
        gel = g.wallet.get("white_gel")
        g.spar_parties(pid, other, "sword")
        self.assertEqual(gel - g.wallet.get("white_gel"), 3)
        a, b = slime(g, "barbarian"), slime(g, "rogue")
        gel = g.wallet.get("white_gel")
        g.spar(a.id, b.id, "sword")
        self.assertEqual(gel - g.wallet.get("white_gel"), 2)


class TestHunts(unittest.TestCase):
    def test_the_pond_is_a_one_hour_hunt(self):
        from slime_gacha.hunt import ZONES
        self.assertEqual(ZONES.get("pond").duration, 1)
        self.assertEqual(min(z.duration for z in ZONES), 1)

    def test_a_hunt_sharpens_class_proficiency(self):
        g = rich(48)
        g.needs.auto_care = False
        s = slime(g, "barbarian")
        s.class_prof = 30.0
        g.hunt(s.id, "pond")
        g.tick(1)
        self.assertGreater(s.class_prof, 30.0)

    def test_a_party_that_hunts_together_grows_closer(self):
        g = rich(49)
        g.needs.auto_care = False
        pid = party(g, name="H")
        a, b = members(g, pid)[:2]
        bond = g.social.bond(a, b)
        g.party_hunt(pid, "pond")
        groups = {s.hunt.group for s in members(g, pid)}
        self.assertEqual(len(groups), 1)
        self.assertNotIn(0, groups)
        g.tick(1)
        self.assertGreater(g.social.bond(a, b), bond)

    def test_hunts_now_and_then_bring_other_materials(self):
        from slime_gacha.hunt import HuntSystem
        g = rich(50)
        g.needs.auto_care = False
        s = slime(g, "barbarian")
        s.stage = 2
        from slime_gacha.growth import add_xp
        add_xp(s, 10 ** 6)
        s.hp = s.max_hp
        other = {k: 0 for k in ("scrap", "stone_common", "herb_green", "herb_red", "herb_blue", "herb_yellow")}
        g.rng.random = lambda: 0.0                       # best rolls: the side loot always comes
        g.rng.randint = lambda lo, hi: hi
        g.hunt(s.id, "meadow")
        before = {k: g.wallet.get(k) for k in other}
        g.tick(3)
        self.assertTrue(any(g.wallet.get(k) > before[k] for k in other))

    def test_a_sleeper_and_a_worker_can_be_sent_and_a_hurt_slime_cannot(self):
        g = rich(51)
        g.needs.auto_care = False
        a, b, c = slime(g), slime(g), slime(g, "barbarian")
        a.state, a.needs.v["energy"] = "sleeping", 70
        morale = a.morale
        g.hunt(a.id, "pond")
        self.assertEqual((a.state, a.morale), ("hunting", morale))       # rested: woken free
        g.assign_job(b.id, "chef")
        g.hunt(b.id, "pond")
        self.assertEqual((b.state, b.job), ("hunting", ""))
        c.hp = 1
        with self.assertRaises(InvalidAction):
            g.hunt(c.id, "pond")


class TestBrawlMood(unittest.TestCase):
    def test_a_brawl_lowers_morale_and_stirs_anger(self):
        g = rich(46)
        a, b = slime(g, "barbarian"), slime(g, "rogue")
        morale = a.morale
        anger = a.emotions.get("anger", 0) if hasattr(a, "emotions") else 0
        from slime_gacha.ai import Conflict
        c = Conflict(1, a.id, b.id, "a test", config.CONFLICT_MAX_SEVERITY)
        g.conflicts.conflicts.append(c)
        g.conflicts._brawl(c, {a.id: a, b.id: b}, [])
        self.assertTrue(a.grounded and b.grounded)
        self.assertLess(a.morale, morale)
        self.assertGreater(a.emotions.get("anger", 0), anger)


class TestFarmLoot(unittest.TestCase):
    def test_farming_dungeons_hand_out_a_little_extra(self):
        g = rich(47)
        log = []
        g.rng.random = lambda: 0.0                    # every foe drops something
        before = dict(g.wallet.items()) if hasattr(g.wallet, "items") else None
        g._farm_loot(10, log)
        self.assertTrue(any("Also found" in l for l in log))
        g.rng.random = lambda: 0.99
        log.clear()
        g._farm_loot(10, log)
        self.assertEqual(log, [])


if __name__ == "__main__":
    unittest.main()


class TestHuntXp(unittest.TestCase):
    def test_hunt_xp_scales_with_the_cost_of_a_level_but_not_with_stars(self):
        def gain(rarity, stars, level):
            g = rich(70)
            g.needs.auto_care = False
            s = g.gacha.make_slime(rarity, "barbarian", stars=stars)
            g.roster[s.id] = s
            s.stage, s.level, s.xp, s.total_xp = 2, level, 0, 0
            s.hp = s.max_hp
            g.rng.random = lambda: 0.0
            g.hunt(s.id, "meadow")
            g.tick(3)
            return s.total_xp
        low, high = gain("common", 1, 5), gain("common", 1, 60)
        self.assertGreater(high, low * 5)                         # a deep level is no longer a rounding error
        self.assertGreater(gain("rare", 1, 30), gain("common", 1, 30))   # rarer slimes pay more per level, so hunts give more
        self.assertEqual(gain("common", 1, 30), gain("common", 5, 30))   # stars change nothing
