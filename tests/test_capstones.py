"""Pure capstones: earned at legendary 5 stars without specializing, gated by class proficiency that fades."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import attributes, config
from slime_gacha.abilities import get_ability
from slime_gacha.game import Game
from slime_gacha.slime import Slime
from tests.test_fx import mk, use
from tests.test_skills import arena, CLASSES
from tests.test_delves import rich, party, members


def legend(g, cls="mage", prof=100.0):
    s = g.gacha.make_slime("legendary", cls, stars=5)
    g.roster[s.id] = s
    s.class_prof = prof
    return s


class TestEarningAndProficiency(unittest.TestCase):
    def test_earned_only_by_a_legendary_five_star_who_never_specialized(self):
        g = rich(51)
        for rarity, stars, spec, want in (("legendary", 5, "", True), ("legendary", 4, "", False),
                                          ("epic", 5, "", False), ("legendary", 5, "battlemage", False)):
            s = g.gacha.make_slime(rarity, "mage", stars=stars)
            s.spec = spec
            self.assertEqual(attributes.pure_earned(s), want, (rarity, stars, spec))

    def test_specializing_later_keeps_the_capstones(self):
        g = rich(52)
        s = legend(g)
        self.assertEqual(len(attributes.capstones(s)), 2)
        s.spec = "battlemage"
        self.assertEqual(len(attributes.capstones(s)), 2)
        self.assertIn("edit_source", s.known_abilities())

    def test_proficiency_gates_the_capstones(self):
        g = rich(53)
        s = legend(g)
        for prof, n in ((100, 2), (70, 2), (69, 1), (30, 1), (29, 0), (20, 0)):
            s.class_prof = prof
            self.assertEqual(len(attributes.capstones(s)), n, prof)
        s.class_prof = 50
        self.assertEqual(attributes.capstones(s), ["edit_source"])           # the first one goes last
        self.assertNotIn("debug", s.known_abilities())

    def test_proficiency_fades_after_idle_days_and_practice_restores_it(self):
        g = rich(54)
        s = legend(g, prof=71)
        events = []
        for _ in range(config.PROF_IDLE_DAYS):
            g._proficiency_day(events)
        self.assertEqual(s.class_prof, 71)                       # still within the grace period
        g._proficiency_day(events)
        self.assertEqual(s.class_prof, 70)
        g._proficiency_day(events)
        self.assertEqual(s.class_prof, 69)
        self.assertTrue(any("capstone" in e for e in events))
        g.practise(s, 5)
        self.assertEqual((s.class_prof, s.prof_idle), (74, 0))
        s.class_prof = 21
        for _ in range(30):
            g._proficiency_day(events)
        self.assertEqual(s.class_prof, config.PROF_FLOOR)

    def test_fighting_builds_proficiency(self):
        g = rich(55)
        pid = party(g, strong=True)
        for s in members(g, pid):
            s.class_prof, s.prof_idle = 40, 5
        g.battle(pid, 1)
        gained = [s for s in members(g, pid) if s.class_prof > 40]
        self.assertTrue(gained)                                   # whoever acted before the foes fell practised
        self.assertTrue(all(s.prof_idle == 0 for s in gained))

    def test_state_survives_a_save(self):
        g = rich(56)
        s = legend(g, prof=61.5)
        s.prof_idle = 2
        attributes.pure_earned(s)
        s2 = Game.from_dict(g.to_dict()).slime(s.id)
        self.assertEqual((s2.class_prof, s2.prof_idle, s2.pure_earned), (61.5, 2, True))


class TestCapstonesInAction(unittest.TestCase):
    def test_twelve_capstones_exist_two_per_class(self):
        keys = [a.key for c in CLASSES for a in attributes.PURE_CAPSTONES[c]]
        self.assertEqual(len(keys), 12)
        self.assertEqual(len(set(keys)), 12)

    def test_effects(self):
        bs, a, ts, ev, log = arena()
        use(bs, a, get_ability("edit_source"), [ts[0]], ev, log)
        self.assertEqual(ts[0].stat("atk"), 1)
        ts[1].shield = 40
        add = __import__("slime_gacha.fx", fromlist=["x"]).add_buff
        add(ts[1], "defense", 0.5, 3)
        a.poison = (3, 5)
        use(bs, a, get_ability("debug"), [a], ev, log)
        self.assertFalse(a.poison[0] or ts[1].shield or ts[1].buffs)
        use(bs, a, get_ability("warlords_cry"), [a], ev, log)
        self.assertAlmostEqual(a.stat("atk"), 60 * 1.4)
        use(bs, a, get_ability("undying_rage"), [a], ev, log)
        self.assertEqual(a.undying, 2)
        use(bs, a, get_ability("smoke_bomb"), [a], ev, log)
        use(bs, a, get_ability("eagle_eye"), [a], ev, log)
        self.assertAlmostEqual(a.mods["evasion"], 0.3)
        self.assertAlmostEqual(a.mods["crit_rate"], 0.3)
        use(bs, a, get_ability("trapfield"), ts, ev, log)
        self.assertAlmostEqual(ts[0].stat("spd"), 5.0)

    def test_revival_raising_harvest_and_overheal(self):
        bs, a, ts, ev, log = arena()
        friend = mk("F", "party")
        friend.hp = 0
        ev.append(friend)
        use(bs, a, get_ability("resurrection"), [a], ev, log)
        self.assertTrue(friend.alive)
        ts[0].hp = 0
        use(bs, a, get_ability("raise_fallen"), [a], ev, log)
        self.assertEqual(sum(c.minion for c in ev), 1)
        a.hp = 50
        friend.hp = 50
        use(bs, a, get_ability("soul_harvest"), ts[1:], ev, log)
        self.assertGreater(friend.hp, 50)
        a.hp = a.max_hp - 3
        use(bs, a, get_ability("overheal_shield"), [a], ev, log)
        self.assertGreater(a.shield, 0)

    def test_assassinate_executes_the_wounded(self):
        bs, a, ts, ev, log = arena(seed=4, foes=1)
        ts[0].hp = 100
        use(bs, a, get_ability("assassinate"), ts, ev, log)
        self.assertFalse(ts[0].alive)

    def test_every_class_fights_with_both_capstones(self):
        from tests.test_game import full_party, fresh
        for i, cls in enumerate(CLASSES):
            g = fresh(200 + i)
            pid = full_party(g, cls, "legendary", 300000)
            for s in members(g, pid):
                s.stage, s.stars, s.class_prof = 2, 5, 100
                s.hp = s.max_hp
            self.assertEqual(len(members(g, pid)[0].known_abilities()) > 0 and len(attributes.capstones(members(g, pid)[0])), 2)
            rep = g.battle(pid, 2)
            self.assertTrue(rep.log)


if __name__ == "__main__":
    unittest.main()
