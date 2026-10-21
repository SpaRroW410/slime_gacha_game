"""Formations: front and back rows decide who melee attacks can reach, and how hard they hit."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from slime_gacha.abilities import get_ability
from slime_gacha.battle import BattleSystem, Combatant, _damage_value, default_row, is_melee
from slime_gacha.game import Game


def unit(name, side, row, **kw):
    stats = dict(hp=100.0, atk=20.0, defense=5.0, mag=20.0, spd=10.0)
    return Combatant(name, "x", side, stats, 100.0, ["splat"], row=row, **kw)


class TestRows(unittest.TestCase):
    def setUp(self):
        self.bs = BattleSystem(random.Random(1))

    def test_melee_reaches_only_the_front_row_but_arrows_and_spells_reach_anyone(self):
        front, back = unit("F", "foes", "front"), unit("B", "foes", "back")
        me = unit("Me", "party", "front")
        self.assertEqual(self.bs.reachable(me, get_ability("splat"), [front, back]), [front])
        self.assertEqual(self.bs.reachable(me, get_ability("arrow"), [front, back]), [front, back])
        self.assertEqual(self.bs.reachable(me, get_ability("spark"), [front, back]), [front, back])
        self.assertEqual(self.bs.reachable(me, get_ability("backstab"), [front, back]), [front, back])
        front.hp = 0
        self.assertEqual(self.bs.reachable(me, get_ability("splat"), [back]), [back])      # nobody in front: the back row is open

    def test_the_ai_picks_only_reachable_targets(self):
        front, back = unit("F", "foes", "front"), unit("B", "foes", "back")
        back.hp = 1.0                                              # the juiciest target stands at the back
        me = unit("Me", "party", "front")
        for _ in range(5):
            self.assertEqual(self.bs.choose_targets(me, get_ability("splat"), [me], [front, back]), [front])
        self.assertEqual(self.bs.choose_targets(me, get_ability("arrow"), [me], [front, back]), [back])

    def test_back_row_takes_less_and_a_back_row_brawler_hits_less(self):
        splat = get_ability("splat")
        a_front, a_back = unit("A", "party", "front"), unit("A2", "party", "back")
        t_front, t_back = unit("T", "foes", "front"), unit("T2", "foes", "back")
        for u in (a_front, a_back, t_front, t_back):
            u.mods = {}

        def avg(actor, target):
            bs = BattleSystem(random.Random(5))
            return sum(_damage_value(bs, actor, splat, target)[0] for _ in range(200)) / 200
        base = avg(a_front, t_front)
        self.assertLess(avg(a_front, t_back), base * (config.ROW_BACK_GUARD + 0.05))
        self.assertLess(avg(a_back, t_front), base * (config.ROW_BACK_MELEE + 0.05))
        self.assertTrue(is_melee(splat) and not is_melee(get_ability("arrow")))

    def test_classes_default_to_their_row_and_a_choice_sticks_across_a_save(self):
        g = Game(3)
        g.wallet.add("white_gel", 5000)
        g.pull(10, "white_gel")
        rows = {s.arch.discipline: default_row(s) for s in g.slimes()}
        self.assertEqual(rows.get("sword", "front"), "front")
        self.assertEqual(rows.get("magic", "back"), "back")
        s = g.slimes()[0]
        g.set_row(s.id, "back")
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.slime(s.id).row, "back")
        self.assertEqual(Combatant and BattleSystem.from_slime(h.slime(s.id)).row, "back")
        g.set_row(s.id, "auto")
        self.assertEqual(g.slime(s.id).row, "")

    def test_manual_orders_are_limited_to_reachable_foes(self):
        g = Game(4)
        g.wallet.add("white_gel", 5000)
        g.pull(6, "white_gel")
        party = g.slimes()[:3]
        for s in party:
            s.row = "front"
            s.behavior = "attack"
        from slime_gacha.battle import ENEMIES
        enemies = [e for e in ENEMIES if e.role in ("brute", "caster")][:2] or list(ENEMIES)[:2]
        run = g.battles.start(party, enemies, manual=True)
        run.advance()
        self.assertIsNotNone(run.waiting)
        legal = run.legal_abilities()
        single = [a for a in legal if a["target"] == "enemy"]
        self.assertTrue(single)
        foes = [i for i, c in enumerate(run.everyone) if c.side == "foes" and c.alive]
        for a in single:
            self.assertTrue(set(a["reach"]) <= set(foes) and a["reach"])
        # a melee hit on a back-row foe is refused while a front-row foe stands
        front = [i for i, c in enumerate(run.everyone) if c.side == "foes" and c.row == "front"]
        back = [i for i, c in enumerate(run.everyone) if c.side == "foes" and c.row == "back"]
        if front and back and "splat" in run.waiting.abilities:
            with self.assertRaises(ValueError):
                run.act("splat", back[0])


if __name__ == "__main__":
    unittest.main()
