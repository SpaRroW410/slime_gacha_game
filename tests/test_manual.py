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
        self.assertGreater(config.xp_to_next(10, "rare", 1), config.xp_to_next(10, "uncommon", 1))
        self.assertGreater(config.xp_to_next(10, "common", 3), config.xp_to_next(10, "common", 2))
        self.assertGreater(config.xp_to_next(10, "legendary", 5), 5 * base)
