"""Battle effect mechanics (fx.py): bleed, stun, mark, buffs, shield, revive, delay, pierce, execute ..."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import fx
from slime_gacha.abilities import Ability, register_ability, get_ability
from slime_gacha.battle import BattleSystem, Combatant, _damage_value, KIND_HANDLERS


def ab(key, kind="damage", power=1.5, stat="atk", target="enemy", fxs=(), cooldown=0, duration=0):
    try:
        return get_ability(key)
    except Exception:
        return register_ability(Ability(key, key, kind, power, stat, target, cooldown, duration, "", fx=tuple(fxs)))


def mk(name, side, hp=200.0, atk=30.0, defense=4.0, mag=30.0, spd=10.0, abilities=("splat",)):
    return Combatant(name, "🫧", side, dict(hp=hp, atk=atk, defense=defense, mag=mag, spd=spd), hp, list(abilities))


def duo(seed=1):
    bs = BattleSystem(random.Random(seed))
    a, t = mk("A", "party"), mk("T", "foes")
    return bs, a, t, [a, t], []


def use(bs, a, ability, targets, everyone, log):
    bs.last_hits = {}
    KIND_HANDLERS[ability.kind](bs, a, ability, targets, everyone, log)
    fx.apply(bs, a, ability, targets, everyone, log, a.stat(ability.stat))


class TestStatuses(unittest.TestCase):
    def test_bleed_stacks_to_three_and_hurts_each_turn(self):
        bs, a, t, ev, log = duo()
        b = ab("t_bleed", fxs=[("bleed", 3, 0.2)])
        for _ in range(4):
            use(bs, a, b, [t], ev, log)
        self.assertEqual(len(t.bleed), 3)
        hp = t.hp
        self.assertEqual(fx.tick(t, log), "")
        self.assertLess(t.hp, hp)

    def test_stun_loses_the_turn_once(self):
        bs, a, t, ev, log = duo()
        use(bs, a, ab("t_stun", fxs=[("stun", 1.0)]), [t], ev, log)
        self.assertEqual(t.stun, 1)
        self.assertEqual(fx.tick(t, log), "skip")
        self.assertEqual(fx.tick(t, log), "")

    def test_bosses_resist_stun_half_the_time(self):
        class B:
            boss = True
        bs, a, t, ev, log = duo(3)
        t.source = B()
        n = 0
        for _ in range(200):
            t.stun = 0
            fx.apply(bs, a, ab("t_stun", fxs=[("stun", 1.0)]), [t], ev, log, 10)
            n += t.stun
        self.assertTrue(70 < n < 130)

    def test_mark_pierce_execute_and_crit_flags_raise_damage(self):
        def dmg(ability, prep=None, target_hp=None):
            bs, a, t, ev, log = duo(5)
            if prep:
                prep(t)
            if target_hp:
                t.hp = target_hp
            return _damage_value(bs, a, ability, t)

        base = ab("t_plain", power=2.0)
        d0 = dmg(base)[0]
        self.assertGreater(dmg(base, lambda t: setattr(t, "marked", (2, 0.5)))[0], d0)
        self.assertGreater(dmg(ab("t_pierce", power=2.0, fxs=[("pierce", "def", 1.0)]))[0], d0)
        self.assertGreater(dmg(ab("t_exec", power=2.0, fxs=[("execute", 0.25, 3.0)]), target_hp=20)[0], d0 * 2)
        self.assertTrue(dmg(ab("t_crit", power=2.0, fxs=[("crit",)]))[1])
        self.assertTrue(dmg(ab("t_first", power=2.0, fxs=[("first_strike",)]))[1])      # target has not acted
        crits = 0
        for seed in range(60):                              # a target that already acted gets no guaranteed crit
            bs, a, t, ev, log = duo(seed)
            t.acted = True
            crits += _damage_value(bs, a, ab("t_first", power=2.0, fxs=[("first_strike",)]), t)[1]
        self.assertLess(crits, 20)

    def test_buffs_and_debuffs_expire_and_restore_mods(self):
        bs, a, t, ev, log = duo()
        use(bs, a, ab("t_crit_up", "utility", 0, "mag", "self", [("buff", "crit_rate", 0.3, 2)]), [a], ev, log)
        self.assertAlmostEqual(a.mods["crit_rate"], 0.3)
        use(bs, a, ab("t_atk_down", "utility", 0, "atk", "enemy", [("debuff", "atk", 0.5, 2)]), [t], ev, log)
        self.assertAlmostEqual(t.stat("atk"), 15.0)
        for _ in range(2):
            fx.tick(a, log)
            fx.tick(t, log)
        self.assertAlmostEqual(a.mods["crit_rate"], 0.0)
        self.assertAlmostEqual(t.stat("atk"), 30.0)

    def test_rewrite_sets_a_stat_for_a_while(self):
        bs, a, t, ev, log = duo()
        use(bs, a, ab("t_edit", "utility", 0, "mag", "enemy", [("rewrite", "atk", 1, 2)]), [t], ev, log)
        self.assertEqual(t.stat("atk"), 1)
        fx.tick(t, log)
        self.assertEqual(t.stat("atk"), 1)
        fx.tick(t, log)
        self.assertEqual(t.stat("atk"), 30.0)

    def test_shield_absorbs_and_overheal_becomes_shield(self):
        bs, a, t, ev, log = duo()
        use(bs, a, ab("t_shield", "utility", 1.0, "mag", "self", [("shield", 1.0)]), [a], ev, log)
        self.assertGreater(a.shield, 0)
        hp, sh = a.hp, a.shield
        a.hurt(sh - 1)
        self.assertEqual(a.hp, hp)
        a.shield = 0
        a.hp = a.max_hp - 5
        use(bs, a, ab("t_over", "heal", 2.0, "mag", "self", [("overheal",)]), [a], ev, log)
        self.assertEqual(a.hp, a.max_hp)
        self.assertGreater(a.shield, 0)

    def test_cleanse_and_strip(self):
        bs, a, t, ev, log = duo()
        a.poison, a.bleed, a.stun = (3, 5), [(2, 4)], 1
        add = fx.add_buff
        add(a, "atk", -0.3, 3)
        use(bs, a, ab("t_clean", "utility", 0, "mag", "self", [("cleanse",)]), [a], ev, log)
        self.assertFalse(a.poison[0] or a.bleed or a.stun or a.buffs)
        add(t, "defense", 0.5, 3)
        t.shield = 30
        use(bs, a, ab("t_strip", "utility", 0, "mag", "self", [("strip",)]), [a], ev, log)
        self.assertFalse(t.buffs or t.shield)

    def test_revive_raise_and_tithe(self):
        bs, a, t, ev, log = duo()
        friend = mk("F", "party")
        friend.hp = 0
        ev.append(friend)
        use(bs, a, ab("t_rev", "utility", 0, "mag", "self", [("revive", 0.4)]), [a], ev, log)
        self.assertTrue(friend.alive)
        self.assertAlmostEqual(friend.hp, friend.max_hp * 0.4)
        t.hp = 0
        use(bs, a, ab("t_raise", "utility", 0, "mag", "self", [("raise",)]), [a], ev, log)
        thrall = [c for c in ev if c.minion]
        self.assertEqual(len(thrall), 1)
        self.assertEqual(thrall[0].side, "party")
        a.hp = 10
        use(bs, a, ab("t_tithe", "utility", 0, "mag", "self", [("tithe",)]), [a], ev, log)
        self.assertGreater(a.hp, 10)
        self.assertFalse(thrall[0].alive)

    def test_untargetable_undying_counter_and_oath(self):
        bs, a, t, ev, log = duo()
        t.untarget = 2
        other = mk("T2", "foes")
        self.assertEqual(bs.targetable([t, other]), [other])
        self.assertEqual(bs.targetable([t]), [t])                     # hidden only if nobody else is left
        a.undying = 2
        a.hurt(10 ** 6)
        self.assertEqual(a.hp, 1)
        bs2, a2, t2, ev2, log2 = duo()
        t2.counter = (2, 1.0)
        hp = a2.hp
        KIND_HANDLERS["damage"](bs2, a2, ab("t_hit", power=1.0), [t2], ev2, log2)
        self.assertLess(a2.hp, hp)
        a2.oath = 0.6
        self.assertEqual(a2.stat("atk"), 30.0)
        a2.hp = a2.max_hp * 0.2
        self.assertAlmostEqual(a2.stat("atk"), 48.0)

    def test_spread_poison_and_chorus(self):
        bs, a, t, ev, log = duo()
        t2 = mk("T2", "foes")
        ev.append(t2)
        use(bs, a, ab("t_plague", "poison", 0.7, "mag", "enemy", [("spread",)], duration=4), [t], ev, log)
        self.assertTrue(t2.poison[0] > 0)

        class S:
            archetype = "ranger"
        a.source = S()
        mate = mk("M", "party")
        mate.source = S()
        ev.append(mate)
        hp = t.hp
        use(bs, a, ab("t_choir", power=1.0, fxs=[("chorus", "splat")]), [t], ev, log)
        self.assertTrue(any("M uses Splat" in l for l in log))
        self.assertLess(t.hp, hp)


class TestTimingEffects(unittest.TestCase):
    def _fight(self, ability, seed=2, rounds=2):
        bs = BattleSystem(random.Random(seed))
        a = mk("A", "party", hp=5000, atk=20, spd=20, abilities=(ability.key,))
        t = mk("T", "foes", hp=5000, atk=5, spd=1)
        log = []
        bs._simulate([a, t], log, rounds)
        return a, t, log

    def test_extra_turn_acts_twice_in_a_round(self):
        a, t, log = self._fight(ab("t_extra", power=1.0, fxs=[("extra_turn",)]), rounds=1)
        self.assertGreaterEqual(sum("A uses" in l for l in log), 2)

    def test_delayed_hit_lands_a_round_later(self):
        a, t, log = self._fight(ab("t_delay", power=3.0, fxs=[("delay", 1)]), rounds=2)
        text = "\n".join(log)
        self.assertIn("gathers power", text)
        self.assertIn("lands!", text)
        self.assertLess(text.index("gathers power"), text.index("lands!"))

    def test_copy_uses_the_foes_last_skill(self):
        bs, a, t, ev, log = duo()
        t.last_ability = "smash"
        a.abilities = ["t_copy"]
        ab("t_copy", "utility", 0, "mag", "enemy", [("copy",)])
        bs.choose_ability = lambda *x: get_ability("t_copy")
        bs._turn(a, ev, log)
        self.assertTrue(any("copies" in l for l in log))


class TestUtilityAI(unittest.TestCase):
    def test_ai_revives_a_fallen_ally_and_shields_the_hurt(self):
        bs = BattleSystem(random.Random(1))
        rev = ab("t_ai_rev", "utility", 0, "mag", "self", [("revive", 0.5)], cooldown=3)
        sh = ab("t_ai_shield", "utility", 1.0, "mag", "ally", [("shield", 1.0)], cooldown=2)
        a = mk("A", "party", abilities=("splat", "t_ai_rev", "t_ai_shield"))
        friend = mk("F", "party")
        t = mk("T", "foes")
        ev = [a, friend, t]
        bs._everyone = ev
        friend.hp = 0
        allies = [c for c in ev if c.side == "party" and c.alive]
        self.assertEqual(bs.choose_ability(a, allies, [t]).key, "t_ai_rev")
        friend.hp = friend.max_hp * 0.4
        allies = [c for c in ev if c.side == "party" and c.alive]
        self.assertEqual(bs.choose_ability(a, allies, [t]).key, "t_ai_shield")

    def test_view_shows_statuses(self):
        a = mk("A", "party")
        a.shield, a.stun = 10, 1
        self.assertIn("💫", fx.statuses(a))


if __name__ == "__main__":
    unittest.main()


class TestSetupSkillsAI(unittest.TestCase):
    def test_buffs_are_skipped_when_the_fight_will_be_over_fast_and_used_when_it_will_not(self):
        bs = BattleSystem(random.Random(1))
        focus = ab("t_focus", "utility", 0, "mag", "self", [("buff", "spell_power", 0.4, 3)], cooldown=4)
        a = mk("A", "party", atk=300, abilities=("splat", "t_focus"))
        weak = mk("W", "foes", hp=100.0)
        bs._everyone = [a, weak]
        self.assertEqual(bs.choose_ability(a, [a], [weak]).key, "splat")          # one more hit and it is over
        tank = mk("T", "foes", hp=100000.0)
        bs._everyone = [a, tank]
        self.assertEqual(bs.choose_ability(a, [a], [tank]).key, "t_focus")        # a long fight: set up first
