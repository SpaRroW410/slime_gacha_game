"""The playtest recorder (playlog.py): off by default, records fights and trip events when on, capped, exportable."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from slime_gacha.game import Game
from slime_gacha.webapi import Session
from tests.test_delves import members, party, rich


class TestRecorder(unittest.TestCase):
    def test_off_by_default_nothing_is_written(self):
        g = rich(5)
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        g.delve_next(pid)
        self.assertFalse(g.playlog_on)
        self.assertEqual(g.playlog, [])

    def test_on_it_records_floors_and_trip_events_and_survives_a_save(self):
        g = rich(5)
        pid = party(g, strong=True)
        g.playlog_set(True)
        g.enter_dungeon(pid)
        g.delve_next(pid)
        kinds = [e["t"] for e in g.playlog]
        self.assertEqual(kinds[:2], ["enter", "fight"])
        f = g.playlog[1]
        self.assertEqual((f["p"], f["f"], f["res"]), ("descent", 1, "win"))
        self.assertEqual(len(f["party"]), len(members(g, pid)))
        for k in ("c", "r", "st", "lv", "g", "rl", "hp", "sta", "mp"):
            self.assertIn(k, f["party"][0])
        self.assertTrue(f["foes"] and f["rd"] >= 1)
        h = Game.from_dict(json.loads(json.dumps(g.to_dict())))
        self.assertTrue(h.playlog_on)
        self.assertEqual(h.playlog, g.playlog)

    def test_the_log_is_capped(self):
        g = rich(5)
        g.playlog_set(True)
        from slime_gacha import playlog
        pad = "x" * 1000                                                   # ~1 KB entries
        n = int(config.PLAYLOG_MAX_KB * 1.2)
        for i in range(n):
            playlog.add(g, playlog.event_entry(g, "camp", n=i, pad=pad))
        self.assertLessEqual(playlog.size_kb(g), config.PLAYLOG_MAX_KB)
        self.assertGreater(playlog.size_kb(g), config.PLAYLOG_MAX_KB * 0.9)
        self.assertEqual(g.playlog[-1]["n"], n - 1)
        self.assertGreater(g.playlog[0]["n"], 0)                          # the oldest dropped off

    def test_waves_and_the_pit_are_tagged(self):
        g = rich(6)
        pid = party(g, strong=False)
        for s in members(g, pid):
            s.level = 5
        g.playlog_set(True)
        g.grind(pid, 1, 1)
        self.assertEqual(g.playlog[-1]["p"], "pit")


class TestRecorderApi(unittest.TestCase):
    def test_switch_size_export_and_clear(self):
        se = Session()
        se.call("new_game", {})
        st = se.call("state")["state"]["playlog"]
        self.assertEqual((st["on"], st["n"]), (False, 0))
        r = se.call("playlog_set", {"on": True})
        self.assertTrue(r["ok"] and r["state"]["playlog"]["on"])
        from slime_gacha import playlog
        playlog.add(se.game, playlog.event_entry(se.game, "camp", hours=3))
        st = se.call("state")["state"]["playlog"]
        self.assertEqual(st["n"], 1)
        self.assertGreater(st["kb"], 0)
        ex = se.call("playlog_export")["result"]
        self.assertEqual(ex["kind"], "slime-gacha-playtest-log")
        self.assertEqual(len(ex["entries"]), 1)
        se.call("playlog_clear")
        self.assertEqual(se.call("state")["state"]["playlog"]["n"], 0)


if __name__ == "__main__":
    unittest.main()
