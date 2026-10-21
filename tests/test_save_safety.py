"""Damaged and foreign saves are refused with a message, never a traceback."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from slime_gacha.errors import SaveError
from slime_gacha.game import Game
from slime_gacha.webapi import Session


class TestBadSaves(unittest.TestCase):
    def good(self):
        g = Game(5)
        g.wallet.add("white_gel", 500)
        g.pull(3, "white_gel")
        return g.to_dict()

    def test_a_good_save_round_trips(self):
        d = self.good()
        self.assertEqual(Game.from_dict(d).tick_count, d["tick"])

    def test_junk_is_refused_with_a_save_error(self):
        d = self.good()
        junk = [None, [], "save", 7, {}, {"settings": {}}, {"version": "x"}, {"version": True},
                {"version": config.SAVE_VERSION + 1, "wallet": {}},
                dict(d, gacha=None), dict(d, parties=[]), dict(d, tick=-50), dict(d, tick="5"), dict(d, slimes={}),
                dict(d, wallet={"white_gel": -5}), dict(d, wallet={"white_gel": "lots"}), dict(d, wallet={"white_gel": 10 ** 20})]
        for j in junk:
            with self.assertRaises(SaveError, msg=repr(j)[:60]):
                Game.from_dict(copy.deepcopy(j))

    def test_a_broken_inner_save_still_becomes_a_save_error(self):
        d = self.good()
        d["slimes"][0] = {"id": 1}                           # a slime missing its fields: passes the shape check, breaks the loader
        with self.assertRaises(SaveError):
            Game.from_dict(d)

    def test_the_session_reports_a_bad_save_and_keeps_the_running_game(self):
        s = Session()
        s.new_game(3)
        r = s.call("load", {"save": {"save": {"gacha": None}}})
        self.assertFalse(r["ok"])
        self.assertIn("save", r["error"].lower())
        self.assertIsNotNone(r["state"])                       # the colony that was running is untouched
        self.assertTrue(s.call("load", {"save": self.good()})["ok"])


if __name__ == "__main__":
    unittest.main()
