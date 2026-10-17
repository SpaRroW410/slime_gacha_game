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


class TestLeadersHuntsAndChallenges(unittest.TestCase):
    def test_default_leader_is_the_highest_level_and_the_keeper_can_choose(self):
        g = rich(81)
        pid = party(g)
        mem = members(g, pid)
        for i, s in enumerate(mem):
            s.level = 5 + i
        self.assertEqual(g.party_leader(pid), mem[-1])
        g.set_party_leader(pid, mem[0].id)
        self.assertEqual(g.party_leader(pid), mem[0])
        outsider = three_star(g)
        with self.assertRaises(InvalidAction):
            g.set_party_leader(pid, outsider.id)
        self.assertEqual(Game.from_dict(g.to_dict()).party_leader(pid).id, mem[0].id)

    def test_a_leader_adds_a_little_synergy_and_confidence_matters(self):
        g = rich(82)
        pid = party(g)
        mem = members(g, pid)
        g.set_party_leader(pid, mem[0].id)
        mem[0].morale = 100
        bonus = g._leader_bonus(mem)
        self.assertGreater(bonus, 0)
        self.assertLessEqual(bonus, config.LEADER_POWER)
        mem[0].morale = 0
        self.assertLess(g._leader_bonus(mem), bonus)
        self.assertEqual(g._leader_bonus(mem[:2] + [three_star(g)]), 0.0)         # not one party

    def test_a_party_leader_can_mediate_inside_a_dungeon_without_a_vice_keeper(self):
        g = rich(83)
        pid = party(g, strong=True)
        mem = members(g, pid)
        g.set_party_leader(pid, mem[0].id)
        g.enter_dungeon(pid, 1)
        a, b = mem[1], mem[2]
        g.conflicts.conflicts.append(Conflict(id=5, a=a.id, b=b.id, severity=2, age=0, reason="t"))
        self.assertIn("make up", g.mediate(5, "snack"))
        old = config.LEADER_MEDIATE_CHANCE
        config.LEADER_MEDIATE_CHANCE = 1.0
        try:
            g.conflicts.conflicts.append(Conflict(id=6, a=a.id, b=b.id, severity=2, age=0, reason="t"))
            ev = []
            g._leaders_tick(ev)
        finally:
            config.LEADER_MEDIATE_CHANCE = old
        self.assertTrue(any("👑" in e for e in ev))

    def test_the_vice_keeper_organises_a_multi_party_hunt_and_leads_it_all(self):
        g = rich(84)
        for _ in range(12):
            s = g.gacha.make_slime("common", "barbarian", stars=1)
            g.roster[s.id] = s
            s.hp = s.max_hp
        vice = three_star(g)
        vice.hp = vice.max_hp
        with self.assertRaises(InvalidAction):
            g.vice_organize_hunt("meadow", 1)                    # nobody appointed
        g.appoint_vice(vice.id)
        out = g.vice_organize_hunt("meadow", 2)
        self.assertIn("2 parties", out[0])
        ps = [p for p in g.parties.parties.values() if p.temp]
        self.assertEqual(len(ps), 2)
        self.assertIn(vice.id, ps[0].members)
        self.assertEqual(g.party_leader(ps[0].id).id, vice.id)
        hunters = [g.roster[m] for p in ps for m in p.members]
        self.assertTrue(all(h.state == "hunting" and h.hunt.group == g.hunt_group for h in hunters))
        far = next(h for h in hunters if h.id not in ps[0].members)
        self.assertTrue(g.vice_reaches(far))                     # the other party is under the Vice Keeper's lead too
        # the hunt ends, the temporary parties disband
        ev = []
        for _ in range(30):
            ev += g.tick(1)
        self.assertFalse([p for p in g.parties.parties.values() if p.temp])
        self.assertTrue(any("disbands" in e for e in ev))

    def test_vice_hunt_needs_enough_free_slimes(self):
        g = rich(85)
        vice = three_star(g)
        g.appoint_vice(vice.id)
        with self.assertRaises(InvalidAction):
            g.vice_organize_hunt("meadow", 1)

    def test_challenge_needs_approval_and_a_duel_decides(self):
        g = rich(86)
        vice, rival = three_star(g), three_star(g, "barbarian")
        with self.assertRaises(InvalidAction):
            g.challenge_vice(rival.id)                           # no Vice Keeper yet
        g.appoint_vice(vice.id)
        weak = g.gacha.make_slime("common", "mage", stars=1)
        g.roster[weak.id] = weak
        with self.assertRaises(InvalidAction):
            g.challenge_vice(weak.id)
        with self.assertRaises(InvalidAction):
            g.challenge_vice(vice.id)
        g.challenge_vice(rival.id)
        self.assertEqual(g.vice, vice.id)                        # nothing changes until the Keeper decides
        with self.assertRaises(InvalidAction):
            g.challenge_vice(rival.id)                           # one at a time
        out = g.resolve_challenge(False)
        self.assertIn("turn down", out[0])
        self.assertIsNone(g.vice_challenge)
        self.assertEqual(g.vice, vice.id)
        g.challenge_vice(rival.id)
        rival.level, vice.level = 40, 1                          # the duel is a real fight
        out = g.resolve_challenge(True)
        self.assertEqual(g.vice, rival.id)
        self.assertIn("new Vice Keeper", out[-1])

    def test_an_approved_challenge_waits_for_slimes_to_be_home(self):
        g = rich(87)
        vice, rival = three_star(g), three_star(g, "barbarian")
        g.appoint_vice(vice.id)
        g.challenge_vice(rival.id)
        rival.in_dungeon = "grind"
        with self.assertRaises(InvalidAction):
            g.resolve_challenge(True)
        self.assertIsNotNone(g.vice_challenge)                   # still pending
        rival.in_dungeon = ""
        del g.roster[rival.id]
        with self.assertRaises(InvalidAction):
            g.resolve_challenge(True)                            # the challenger is gone: it lapses
        self.assertIsNone(g.vice_challenge)

    def test_proud_stronger_slimes_may_ask_for_the_post_by_themselves(self):
        g = rich(88)
        vice, rival = three_star(g), three_star(g, "barbarian")
        g.appoint_vice(vice.id)
        vice.level, rival.level = 5, 20
        rival.emotions["pride"] = 60
        old = config.VICE_CHALLENGE_DAILY
        config.VICE_CHALLENGE_DAILY = 1.0
        try:
            ev = []
            g._vice_challenge_day(ev)
        finally:
            config.VICE_CHALLENGE_DAILY = old
        self.assertEqual(g.vice_challenge["challenger"], rival.id)
        self.assertTrue(any("challenges" in e for e in ev))

    def test_web_commands_and_state(self):
        se = Session()
        se.new_game(89)
        g = se.game
        vice, rival = three_star(g), three_star(g, "barbarian")
        pid = g.create_party("P").id
        g.party_add(pid, vice.id)
        se.call("appoint_vice", dict(id=vice.id))
        r = se.call("set_leader", dict(pid=pid, id=vice.id))
        self.assertTrue(r["ok"])
        self.assertEqual(next(p for p in r["state"]["parties"] if p["id"] == pid)["leader"], vice.id)
        r = se.call("challenge_vice", dict(id=rival.id))
        self.assertEqual(r["state"]["vice_challenge"]["id"], rival.id)
        r = se.call("resolve_challenge", dict(approve=False))
        self.assertTrue(r["ok"] and r["state"]["vice_challenge"] is None)


if __name__ == "__main__":
    unittest.main()
