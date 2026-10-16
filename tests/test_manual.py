"""Manual (turn-based) battles: Descent, Pit and skirmishes can be commanded slime by slime; switching to auto mid-fight."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha.errors import InvalidAction
from slime_gacha.webapi import Session
from tests.test_delves import rich, party, members


def manual_game(seed=3, strong=True):
    g = rich(seed)
    pid = party(g, strong=strong)
    return g, pid


def play_by_hand(g, limit=400):
    """Always use the first ready ability on the first valid target; returns number of commands issued."""
    n = 0
    while g.battle_run() is not None and n < limit:
        run = g.battle_run()
        w = run.waiting
        ab = next(a for a in run.legal_abilities() if a["ready"])
        tgt = None
        if ab["target"] == "enemy":
            tgt = next(i for i, c in enumerate(run.everyone) if c.side != w.side and c.alive)
        elif ab["target"] == "ally":
            tgt = next(i for i, c in enumerate(run.everyone) if c.side == w.side and c.alive and not c.minion)
        g.battle_act(ab["key"], tgt)
        n += 1
    return n


class TestManualBattle(unittest.TestCase):
    def test_skirmish_pauses_for_each_party_slime_and_then_finishes(self):
        g, pid = manual_game()
        self.assertIsNone(g.battle(pid, 1, manual=True))
        run = g.battle_run()
        self.assertIsNotNone(run)
        self.assertEqual(run.waiting.side, "party")
        self.assertIsNotNone(g.flow)
        acts = 0
        seen = set()
        while g.battle_run() is not None:
            seen.add(g.battle_run().waiting.name)
            play_by_hand_one(g)
            acts += 1
        self.assertGreaterEqual(acts, 1)
        self.assertGreaterEqual(len(seen), 2)           # every slime gets its own turn
        self.assertIsNone(g.flow)

    def test_switching_to_auto_mid_battle_finishes_it(self):
        g, pid = manual_game()
        g.battle(pid, 1, manual=True)
        play_by_hand_one(g)
        r = g.battle_set_manual(False)
        self.assertIsNotNone(r)                         # the BattleReport
        self.assertTrue(r.victory)
        self.assertIsNone(g.flow)

    def test_auto_turn_lets_the_ai_take_one_turn_only(self):
        g, pid = manual_game()
        g.battle(pid, 1, manual=True)
        first = g.battle_run().waiting.name
        g.battle_auto_turn()
        run = g.battle_run()
        if run is not None:
            self.assertTrue(run.waiting is not None)

    def test_bad_orders_are_refused_cleanly(self):
        g, pid = manual_game()
        g.battle(pid, 1, manual=True)
        with self.assertRaises(InvalidAction):
            g.battle_act("not_an_ability")
        run = g.battle_run()
        splat = next(a for a in run.legal_abilities() if a["target"] == "enemy")
        ally_idx = next(i for i, c in enumerate(run.everyone) if c.side == "party")
        with self.assertRaises(InvalidAction):
            g.battle_act(splat["key"], ally_idx)        # cannot hit a friend with an enemy-targeted move
        with self.assertRaises(InvalidAction):
            g.battle(pid, 1, manual=True)               # one battle at a time

    def test_a_manual_fight_matches_auto_rewards_shape(self):
        g, pid = manual_game(5)
        g.battle(pid, 1, manual=True)
        g.battle_set_manual(False)
        self.assertIsNone(g.flow)
        self.assertTrue(all(s.hp > 0 for s in members(g, pid)))

    def test_descent_floor_by_hand(self):
        g, pid = manual_game(7)
        g.enter_dungeon(pid, 1)
        self.assertIsNone(g.delve_next(pid, manual=True))
        play_by_hand(g)
        self.assertIsNone(g.flow)
        d = g.delves.get(pid)
        self.assertTrue(d is None or d["floor"] in (1, 2))

    def test_pit_session_continues_across_runs_and_can_flip_to_auto(self):
        g, pid = manual_game(9, strong=False)
        self.assertIsNone(g.grind(pid, 1, 3, manual=True))
        play_by_hand_one(g)
        res = g.battle_set_manual(False)
        self.assertEqual(len(res.runs), 3)
        self.assertIsNone(g.flow)
        for s in members(g, pid):
            self.assertEqual(s.in_dungeon, "")

    def test_web_api_gates_other_commands_while_a_battle_is_open(self):
        se = Session()
        se.new_game(11)
        g = se.game
        for k in ("white_gel", "essence", "food"):
            g.wallet.add(k, 5000)
        pid = party(g, strong=True)
        r = se.call("skirmish", dict(pid=pid, tier=1, manual=True))
        self.assertTrue(r["ok"] and r["result"]["pending"])
        self.assertTrue(r["state"]["battle"]["waiting"] is not None)
        self.assertEqual(r["state"]["battle"]["kind"], "skirmish")
        blocked = se.call("wait", dict(hours=1))
        self.assertFalse(blocked["ok"])
        r = se.call("battle_manual", dict(manual=False))
        self.assertTrue(r["ok"] and not r["result"]["pending"])
        self.assertIsNone(r["state"]["battle"])
        self.assertTrue(se.call("wait", dict(hours=1))["ok"])

    def test_an_open_battle_is_not_saved_and_the_party_is_freed_on_load(self):
        from slime_gacha.game import Game
        g, pid = manual_game(13, strong=False)
        g.grind(pid, 1, 2, manual=True)
        self.assertTrue(all(s.in_dungeon == "grind" for s in members(g, pid)))
        g2 = Game.from_dict(g.to_dict())
        self.assertIsNone(g2.flow)
        self.assertTrue(all(s.in_dungeon == "" for s in g2.party_members(pid)))


def play_by_hand_one(g):
    run = g.battle_run()
    w = run.waiting
    ab = next(a for a in run.legal_abilities() if a["ready"])
    tgt = None
    if ab["target"] == "enemy":
        tgt = next(i for i, c in enumerate(run.everyone) if c.side != w.side and c.alive)
    elif ab["target"] == "ally":
        tgt = next(i for i, c in enumerate(run.everyone) if c.side == w.side and c.alive and not c.minion)
    g.battle_act(ab["key"], tgt)


if __name__ == "__main__":
    unittest.main()


class TestXpCurve(unittest.TestCase):
    def test_rarer_and_higher_star_slimes_need_more_xp(self):
        from slime_gacha import config
        base = config.xp_to_next(10)
        self.assertEqual(config.xp_to_next(10, "common", 1), base)
        self.assertEqual([config.xp_to_next(1, r) for r in config.RARITIES], [20, 40, 80, 160, 320])
        self.assertEqual(config.xp_to_next(10, "common", 5), base)       # stars do not change it


class TestLevelHundredBalance(unittest.TestCase):
    def test_stat_growth_slows_above_fifty_and_pit_xp_keeps_pace(self):
        from slime_gacha import config
        self.assertEqual(config.stat_level(50), 50)
        self.assertAlmostEqual(config.stat_level(100), 80)
        self.assertEqual(config.pit_xp_boost(10), 1.0)
        self.assertGreater(config.pit_xp_boost(100), config.pit_xp_boost(60))
        self.assertGreater(config.pit_xp_boost(100), 3.0)

    def test_a_level_hundred_party_still_beats_the_pit_and_levels_in_reasonable_runs(self):
        from slime_gacha import config
        g = rich(3)
        pid = party(g, strong=False)
        for s in members(g, pid):
            s.stage, s.level = 2, 99
            s.hp = s.max_hp
        rep = g.grind(pid, 3, 1).runs[0]
        self.assertTrue(rep.victory)
        self.assertLess(config.xp_to_next(99) / max(1, rep.xp), 20)      # common: well under 20 Pit runs per level


class TestMergeAndMediate(unittest.TestCase):
    def test_keeper_cannot_mediate_for_slimes_away_from_the_colony(self):
        g = rich(21)
        a, b = (g.gacha.make_slime("common", "barbarian") for _ in range(2))
        for s in (a, b):
            g.roster[s.id] = s
        from slime_gacha.ai import Conflict
        c = Conflict(id=1, a=a.id, b=b.id, severity=1, age=0, reason="test")
        g.conflicts.conflicts.append(c)
        a.in_dungeon = "grind"
        with self.assertRaises(InvalidAction):
            g.mediate(1, "talk")
        with self.assertRaises(InvalidAction):
            g.mediate(1, "snack")
        a.in_dungeon = ""
        self.assertIn("make up", g.mediate(1, "snack"))

    def test_manual_merge_preview_and_merge_of_any_two_free_slimes(self):
        se = Session()
        se.new_game(5)
        g = se.game
        ids = [g.gacha.make_slime("common", "barbarian") for _ in range(2)]
        for s in ids:
            g.roster[s.id] = s
        t, d = ids
        d.total_xp = 500
        pv = se.call("merge_preview", dict(target=t.id, donor=d.id))
        self.assertTrue(pv["ok"] and pv["result"]["xp"] > 0 and "grief" in pv["result"])
        self.assertFalse(se.call("merge_preview", dict(target=t.id, donor=t.id))["ok"])
        r = se.call("merge", dict(target=t.id, donor=d.id))
        self.assertTrue(r["ok"])
        self.assertNotIn(d.id, g.roster)
        d2 = g.gacha.make_slime("common", "mage")
        g.roster[d2.id] = d2
        d2.in_dungeon = "grind"
        self.assertFalse(se.call("merge", dict(target=t.id, donor=d2.id))["ok"])
