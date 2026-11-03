"""Floor modifiers (fx statuses over a whole floor) and wayside stops between floors."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, dungeon, modifiers
from slime_gacha.battle import BattleSystem
from slime_gacha.errors import InvalidAction, NotEnoughResources
from slime_gacha.webapi import snapshot
from tests.test_delves import rich, party, members
from tests.test_fx import mk


class TestModifiers(unittest.TestCase):
    def test_floors_have_a_fixed_modifier_and_bosses_never_do(self):
        mods = [dungeon.floor_modifier(5, f) for f in range(1, dungeon.MAX_FLOOR + 1)]
        self.assertEqual(mods, [dungeon.floor_modifier(5, f) for f in range(1, dungeon.MAX_FLOOR + 1)])
        self.assertEqual(mods[0], "")
        self.assertTrue(all(m == "" for f, m in enumerate(mods, 1) if dungeon.is_boss_floor(f)))
        used = {m for m in mods if m}
        self.assertGreaterEqual(len(used), 4)                              # a good spread of the six
        self.assertTrue(used <= set(modifiers.MODIFIERS))
        share = sum(1 for m in mods if m) / len(mods)
        self.assertTrue(0.15 < share < 0.5)
        self.assertEqual(dungeon.floor_info(5, 7, 5).modifier, mods[6])

    def test_each_modifier_changes_the_fight_with_fx_statuses(self):
        for key, mod in modifiers.MODIFIERS.items():
            party, foes = [mk("A", "party", hp=100)], [mk("T", "foes", hp=100)]
            log = modifiers.apply(mod, party, foes)
            self.assertTrue(log and mod.name in log[0])
            changed = any(c.buffs for c in party + foes) or any(c.poison[0] for c in party + foes)
            self.assertTrue(changed, key)
        a, t = [mk("A", "party", hp=100)], [mk("T", "foes", hp=100)]
        modifiers.apply(modifiers.MODIFIERS["poison_fog"], a, t)
        self.assertEqual(a[0].poison, (4, 3))
        a, t = [mk("A", "party", spd=10.0)], [mk("T", "foes", spd=10.0)]
        modifiers.apply(modifiers.MODIFIERS["thin_air"], a, t)
        self.assertAlmostEqual(a[0].stat("spd"), 8.0)
        a, t = [mk("A", "party")], [mk("T", "foes")]
        modifiers.apply(modifiers.MODIFIERS["sacred_spring"], a, t)
        self.assertAlmostEqual(a[0].mods["regen"], 0.04)
        self.assertFalse(t[0].buffs)

    def test_intel_reveals_the_modifier_at_forty_percent(self):
        f = next(x for x in range(2, 50) if dungeon.floor_modifier(5, x))
        name = modifiers.get(dungeon.floor_modifier(5, f)).name
        self.assertFalse(any(name in l for l in dungeon.intel_lines(5, f, 25, 5)))
        self.assertTrue(any(name in l for l in dungeon.intel_lines(5, f, 45, 5)))

    def test_the_fight_logs_the_modifier(self):
        g = rich(21)
        pid = party(g, strong=True)
        for s in members(g, pid):
            s.progress = 50
        g.enter_dungeon(pid)
        f = next(x for x in range(2, 40) if dungeon.floor_modifier(g.dungeon_seed, x) and not dungeon.has_stop(x))
        g.delves[pid]["floor"] = f
        r = g.delve_next(pid)
        self.assertTrue(any(modifiers.get(dungeon.floor_modifier(g.dungeon_seed, f)).name in l for l in r.log[:12]))


class TestWaysideStop(unittest.TestCase):
    def setup(self, floor=8):
        g = rich(22)
        pid = party(g, strong=True)
        for s in members(g, pid):
            s.progress = 50
        g.enter_dungeon(pid)
        g.delves[pid]["floor"] = floor
        return g, pid

    def test_stops_wait_on_floors_three_eight_thirteen(self):
        self.assertEqual([f for f in range(1, 20) if dungeon.has_stop(f)], [3, 8, 13, 18])
        g, pid = self.setup(5)
        with self.assertRaises(InvalidAction):
            g.stop_rest(pid)
        self.assertIsNone(g.stop_view(pid))

    def test_rest_is_safe_once_and_heals_half(self):
        g, pid = self.setup()
        for s in members(g, pid):
            s.hp = max(1, s.max_hp // 10)
        t0 = g.tick_count
        g.stop_rest(pid)
        self.assertEqual(g.tick_count - t0, g.lobby_hours("main", config.STOP_REST_HOURS))
        self.assertTrue(all(s.hp >= s.max_hp * 0.5 for s in members(g, pid)))
        with self.assertRaises(InvalidAction):
            g.stop_rest(pid)

    def test_shop_sells_one_of_each_and_boons_last_one_fight(self):
        g, pid = self.setup()
        view = g.stop_view(pid)
        self.assertEqual({i["key"] for i in view["items"]}, {"salve", "ration", "ward", "whetstone"})
        gel = g.wallet.get("white_gel")
        g.stop_buy(pid, "ward")
        self.assertEqual(gel - g.wallet.get("white_gel"), g.stop_price(pid, "ward"))
        with self.assertRaises(InvalidAction):
            g.stop_buy(pid, "ward")
        food = g.wallet.get("food")
        g.stop_buy(pid, "ration")
        self.assertEqual(g.wallet.get("food"), food + 5)
        r = g.delve_next(pid)
        self.assertTrue(any("wayside stop" in l for l in r.log))
        self.assertEqual(g.delves.get(pid, {}).get("boons", []), [])

    def test_shop_needs_gel_and_a_new_floor_has_a_new_stock(self):
        g, pid = self.setup()
        g.wallet.add("white_gel", -g.wallet.get("white_gel"))
        with self.assertRaises(NotEnoughResources):
            g.stop_buy(pid, "salve")
        g.wallet.add("white_gel", 1000)
        g.stop_buy(pid, "salve")
        g.delves[pid]["floor"] = 13
        self.assertFalse(any(i["bought"] for i in g.stop_view(pid)["items"]))

    def test_the_snapshot_carries_stop_and_modifier(self):
        g, pid = self.setup()
        v = snapshot(g)["dungeon"]["delves"][str(pid)]
        self.assertIsNotNone(v["stop"])
        self.assertIn("poison_fog", snapshot(g)["modifiers"])


if __name__ == "__main__":
    unittest.main()
