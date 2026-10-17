"""Renaming, and the Vice Keeper: a trusted slime that stands in for the Keeper (never merging or destroying)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from slime_gacha.ai import Conflict
from slime_gacha.errors import InvalidAction
from slime_gacha.game import Game
from slime_gacha.webapi import Session
from tests.test_delves import rich, party, members


def three_star(g, cls="medic"):
    s = g.gacha.make_slime("rare", cls, stars=3)
    g.roster[s.id] = s
    return s


class TestRename(unittest.TestCase):
    def test_rename_slime_and_party(self):
        g = rich(71)
        pid = party(g)
        s = members(g, pid)[0]
        self.assertIn("is now called Zed", g.rename_slime(s.id, "  Zed  "))
        self.assertEqual(s.name, "Zed")
        g.rename_party(pid, "Night Watch")
        self.assertEqual(g.parties.get(pid).name, "Night Watch")

    def test_names_are_validated_and_unique(self):
        g = rich(72)
        pid = party(g)
        a, b = members(g, pid)[:2]
        g.rename_slime(a.id, "Zed")
        for bad in ("", "   ", "x" * 25, "<b>hi</b>", 'a"b'):
            with self.assertRaises(InvalidAction):
                g.rename_slime(b.id, bad)
        with self.assertRaises(InvalidAction):
            g.rename_slime(b.id, "zed")                         # case-insensitive duplicate
        g.rename_slime(a.id, "Zed")                              # its own name is fine
        p2 = g.create_party("Other")
        with self.assertRaises(InvalidAction):
            g.rename_party(p2.id, g.parties.get(pid).name)

    def test_rename_survives_a_save(self):
        g = rich(73)
        s = three_star(g)
        g.rename_slime(s.id, "Moss")
        self.assertEqual(Game.from_dict(g.to_dict()).slime(s.id).name, "Moss")


class TestViceKeeper(unittest.TestCase):
    def test_appointing_needs_stars_and_a_free_slime(self):
        g = rich(74)
        low = g.gacha.make_slime("common", "medic", stars=1)
        g.roster[low.id] = low
        with self.assertRaises(InvalidAction):
            g.appoint_vice(low.id)
        s = three_star(g)
        s.in_dungeon = "grind"
        with self.assertRaises(InvalidAction):
            g.appoint_vice(s.id)
        s.in_dungeon = ""
        self.assertIn("Vice Keeper", g.appoint_vice(s.id))
        self.assertEqual(g.vice_slime(), s)
        g.dismiss_vice()
        self.assertIsNone(g.vice_slime())
        with self.assertRaises(InvalidAction):
            g.dismiss_vice()

    def test_the_vice_keeper_cannot_be_merged_or_destroyed_in_office(self):
        g = rich(75)
        vice, other = three_star(g), three_star(g, "mage")
        g.appoint_vice(vice.id)
        with self.assertRaises(InvalidAction):
            g.merge(other.id, vice.id)
        with self.assertRaises(InvalidAction):
            g.destroy_slime(vice.id)
        self.assertNotIn(vice.id, [m["donor"].id for m in g.council()["merges"]])
        g.dismiss_vice()
        g.destroy_slime(vice.id)                                  # allowed once they have stepped down

    def test_reach_inside_a_dungeon_needs_the_same_group(self):
        g = rich(76)
        pid = party(g, strong=True)
        mem = members(g, pid)
        vice = mem[0]
        vice.stars = 3
        g.appoint_vice(vice.id)
        outsider = three_star(g, "mage")
        g.enter_dungeon(pid, 1)
        other = mem[1]
        self.assertTrue(g.vice_reaches(other))                   # same party, same dungeon
        outsider.in_dungeon = "main"
        self.assertFalse(g.vice_reaches(outsider))               # busy, but in no group with the vice keeper
        other.needs.add("food", -90)
        self.assertIn("nibbles", g.feed(other.id))               # care works inside, thanks to the vice keeper
        g.dismiss_vice()
        with self.assertRaises(InvalidAction):
            g.feed(other.id)

    def test_mediation_inside_a_dungeon_and_automatic_settling(self):
        g = rich(77)
        pid = party(g, strong=True)
        mem = members(g, pid)
        vice = mem[0]
        vice.stars = 3
        g.appoint_vice(vice.id)
        g.enter_dungeon(pid, 1)
        a, b = mem[1], mem[2]
        g.conflicts.conflicts.append(Conflict(id=1, a=a.id, b=b.id, severity=3, age=0, reason="t"))
        g.mediate(1, "snack")                                    # allowed: the vice keeper is with them
        self.assertFalse(g.conflicts.conflicts)
        g.conflicts.conflicts.append(Conflict(id=2, a=a.id, b=b.id, severity=3, age=0, reason="t"))
        old = config.VICE_MEDIATE_CHANCE
        config.VICE_MEDIATE_CHANCE = 1.0
        try:
            events = []
            g._vice_tick(events)
        finally:
            config.VICE_MEDIATE_CHANCE = old
        self.assertFalse(g.conflicts.conflicts)
        self.assertTrue(any("settles the quarrel" in e for e in events))

    def test_at_home_serious_quarrels_are_left_to_the_keeper(self):
        g = rich(78)
        vice, a, b = three_star(g), three_star(g, "mage"), three_star(g, "rogue")
        g.appoint_vice(vice.id)
        g.conflicts.conflicts.append(Conflict(id=3, a=a.id, b=b.id, severity=3, age=0, reason="t"))
        old = config.VICE_MEDIATE_CHANCE
        config.VICE_MEDIATE_CHANCE = 1.0
        try:
            g._vice_tick([])
            self.assertTrue(g.conflicts.conflicts)               # severity 3: still there
            g.conflicts.conflicts[0].severity = 2
            g._vice_tick([])
            self.assertFalse(g.conflicts.conflicts)
        finally:
            config.VICE_MEDIATE_CHANCE = old

    def test_the_vice_keeper_is_forgotten_if_it_dies_and_is_saved(self):
        g = rich(79)
        s = three_star(g)
        g.appoint_vice(s.id)
        self.assertEqual(Game.from_dict(g.to_dict()).vice, s.id)
        del g.roster[s.id]
        self.assertIsNone(g.vice_slime())

    def test_web_commands(self):
        se = Session()
        se.new_game(80)
        g = se.game
        s = three_star(g)
        r = se.call("appoint_vice", dict(id=s.id))
        self.assertTrue(r["ok"] and r["state"]["vice"]["id"] == s.id)
        self.assertTrue(next(x for x in r["state"]["slimes"] if x["id"] == s.id)["is_vice"])
        self.assertTrue(se.call("rename_slime", dict(id=s.id, name="Boss"))["ok"])
        self.assertFalse(se.call("rename_slime", dict(id=s.id, name=""))["ok"])


if __name__ == "__main__":
    unittest.main()
