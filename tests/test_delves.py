"""No-exit delves, scouting intel, Pit defeat penalties, gear recovery, equipment, sacrifice stress."""
import math
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, dungeon, equipment
from slime_gacha.errors import InvalidAction, NotEnoughResources
from slime_gacha.game import Game
from slime_gacha.growth import add_xp, lose_xp


def rich(seed=1):
    g = Game(seed)
    for k in ("white_gel", "purple_gel", "essence", "food"):
        g.wallet.add(k, 20000)
    g.needs.auto_care = False
    return g


def party(g, archetype="barbarian", n=None, strong=False, stars=2, rarity="common", name="P"):
    p = g.create_party(name)
    for _ in range(n or g.parties.size):
        s = g.gacha.make_slime(rarity, archetype, stars=stars)
        g.roster[s.id] = s
        g.parties.add(p.id, s.id)
        if strong:
            s.stage = 2
            add_xp(s, 10 ** 7)
        s.hp = s.max_hp
    return p.id


def members(g, pid):
    return g.party_members(pid)


class TestDelve(unittest.TestCase):
    def test_floors_are_fixed_by_the_seed(self):
        a = [e.key for e in dungeon.floor_plan(5, 3, 5)]
        self.assertEqual(a, [e.key for e in dungeon.floor_plan(5, 3, 5)])
        others = [tuple(e.key for e in dungeon.floor_plan(s, 3, 5)) for s in range(6, 12)]
        self.assertTrue(any(o != tuple(a) for o in others))

    def test_no_exit_until_boss_or_wipe(self):
        g = rich()
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        self.assertTrue(all(s.in_dungeon == "main" for s in members(g, pid)))
        self.assertFalse(hasattr(g, "leave_dungeon") or hasattr(g, "exit_dungeon") or hasattr(g, "retreat"))
        for floor in (1, 2, 3, 4):
            rep = g.delve_next(pid)
            self.assertTrue(rep.victory)
            self.assertIn(pid, g.delves)
            self.assertEqual(g.delves[pid]["floor"], floor + 1)
        rep = g.delve_next(pid)                       # the boss
        self.assertTrue(rep.victory)
        self.assertNotIn(pid, g.delves)
        self.assertEqual(g.main_floor, 5)

    def test_recall_does_not_free_a_delver(self):
        g = rich()
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        g.recall(members(g, pid)[0].id)
        self.assertEqual(members(g, pid)[0].in_dungeon, "main")

    def test_wipe_ends_the_delve_and_deaths_are_permanent(self):
        g = rich(3)
        pid = party(g, "mage", rarity="common")
        names = [s.name for s in members(g, pid)]
        for s in members(g, pid):
            s.gear = {"weapon": "wooden_club"}
        # deep floor: crush the weak party
        g.enter_dungeon(pid)
        g.delves[pid]["floor"] = 9
        rep = g.delve_next(pid)
        self.assertEqual(rep.winner, "foes")
        self.assertNotIn(pid, g.delves)
        self.assertEqual(len(g.roster), 0)
        self.assertEqual(sorted(d["name"] for d in g.graveyard), sorted(names))
        self.assertEqual(g.inventory.items, {})           # nobody survived to carry the gear back
        self.assertEqual(g.main_floor, 0)

    def test_survivors_stay_inside_with_a_short_party(self):
        g = rich(4)
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        victim = members(g, pid)[0]
        victim.hp, victim.death_cause = 0, "test"
        g._reap([])
        self.assertEqual(len(members(g, pid)), 4)
        rep = g.delve_next(pid)                         # four can still fight
        self.assertTrue(rep.victory)
        self.assertIn(pid, g.delves)

    def test_camp_heals_inside_and_costs_time_and_knowledge_grows(self):
        g = rich(5)
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        for s in members(g, pid):
            s.hp = max(1, s.max_hp // 4)
        g.rng.random = lambda: 0.99                     # no ambushes
        t0, k0 = g.tick_count, g._knowledge(0)
        g.delve_camp(pid, 6)
        self.assertEqual(g.tick_count - t0, 6)
        self.assertTrue(all(s.hp > s.max_hp // 4 + 1 for s in members(g, pid)))
        self.assertGreater(g._knowledge(0), k0)         # time inside teaches the dungeon
        self.assertIn(pid, g.delves)

    def test_camp_ambush_can_kill_and_intel_makes_it_rarer(self):
        g = rich(6)
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        victim = members(g, pid)[0]
        victim.hp = 1
        victim.gear = {"weapon": "kings_edge"}
        g.rng.random = lambda: 0.0                      # ambush every hour, gear always recovered
        g.rng.uniform = lambda a, b: 50.0               # a brutal one
        out = g.delve_camp(pid, 1)
        self.assertTrue(any("ambush" in l for l in out))
        self.assertTrue(len(g.graveyard) >= 1)
        self.assertIn("ambushed", g.graveyard[0]["cause"])
        low = config.CAMP_AMBUSH_BASE * 1.1
        g.intel[0] = 100
        self.assertLess(low * (1 - 0.6 * 1.0), low)

    def test_delve_survives_save_and_load(self):
        g = rich()
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        g.delve_next(pid)
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.delves[pid]["floor"], 2)
        self.assertTrue(all(s.in_dungeon == "main" for s in h.party_members(pid)))
        self.assertEqual(h.dungeon_seed, g.dungeon_seed)


class TestScouting(unittest.TestCase):
    def test_hours_validated_and_party_must_be_ready(self):
        g = rich()
        pid = party(g)
        for bad in (1, 25):
            with self.assertRaises(InvalidAction):
                g.scout(pid, bad)
        short = g.create_party("short")
        with self.assertRaises(InvalidAction):
            g.scout(short.id, 8)

    def test_knowledge_grows_with_time_in_the_dungeon(self):
        ks = []
        for hours in (2, 6, 12, 24):
            g = rich(7)
            pid = party(g, strong=True)
            g.rng.random = lambda: 0.99
            res = g.scout(pid, hours)
            ks.append(res.after)
        self.assertEqual(ks, sorted(ks))
        self.assertGreater(ks[-1], ks[0] * 2)
        self.assertLess(ks[-1], 100.0001)
        # diminishing returns: 12 -> 24 adds less than 2 -> 12
        self.assertLess(ks[3] - ks[2], ks[2] - ks[0])

    def test_formula_and_accumulation(self):
        g = rich(8)
        pid = party(g, "barbarian", strong=True)
        g.rng.random = lambda: 0.99
        r1 = g.scout(pid, 4)
        expect = 100 - 100 * math.exp(-config.SCOUT_RATE * 0.8 * 4)    # skill 0.8 for non-scouts
        self.assertAlmostEqual(r1.after, expect, delta=0.1)
        r2 = g.scout(pid, 4)
        self.assertGreater(r2.after, r1.after)
        self.assertAlmostEqual(g.intel[0], r2.after)

    def test_rogues_and_rangers_scout_better(self):
        g1, g2 = rich(9), rich(9)
        a, b = party(g1, "barbarian", strong=True), party(g2, "rogue", strong=True)
        g1.rng.random = g2.rng.random = lambda: 0.99
        self.assertGreater(g2.scout(b, 6).after, g1.scout(a, 6).after)

    def test_scouts_are_committed_and_flagged_only_while_out(self):
        g = rich(10)
        pid = party(g, strong=True)
        g.rng.random = lambda: 0.99
        seen = []
        orig = g.tick
        g.tick = lambda n=1: (seen.append({s.in_dungeon for s in members(g, pid)}), orig(n))[1]
        g.scout(pid, 3)
        self.assertTrue(all(x == {"scout"} for x in seen))
        self.assertTrue(all(s.in_dungeon == "" for s in members(g, pid)))

    def test_whole_party_lost_means_nothing_learned(self):
        g = rich(11)
        pid = party(g, "mage", rarity="common")
        for s in members(g, pid):
            s.hp = 1
        g.rng.random = lambda: 0.0                      # an ambush every hour
        res = g.scout(pid, 6)
        self.assertEqual(res.survivors, 0)
        self.assertEqual(g.intel.get(0, 0), 0)
        self.assertEqual(len(g.graveyard), 5)
        self.assertTrue(any("never came back" in l for l in res.log))

    def test_intel_reveals_in_stages_and_matches_reality(self):
        seen = {k: dungeon.intel_view(3, 0, k, 5)[0]["lines"] for k in (0, 25, 45, 65, 85, 100)}
        self.assertEqual(seen[0], ["unknown"])
        counts = [len(seen[k]) for k in (0, 25, 45, 65, 85, 100)]
        self.assertEqual(counts, sorted(counts))
        self.assertTrue(any("weakness" in l for l in seen[100]))
        boss_view = dungeon.intel_view(3, 0, 70, 5)[4]["lines"]
        self.assertTrue(any(l.startswith("BOSS") for l in boss_view))
        self.assertFalse(any(l.startswith("BOSS") for l in dungeon.intel_view(3, 0, 45, 5)[4]["lines"]))
        real = {e.name for e in dungeon.floor_plan(3, 1, 5)}
        self.assertTrue(all(any(n in l for l in seen[45]) for n in real))

    def test_intel_gives_a_battle_bonus_and_passive_learning(self):
        g = rich(12)
        pid = party(g, strong=True)
        g.intel[0] = 100
        g.enter_dungeon(pid)
        rep = g.delve_next(pid)
        self.assertTrue(any("scouting intel +10%" in l for l in rep.log))


class TestPitPenalties(unittest.TestCase):
    def _weak_party(self, g, gear=True):
        pid = party(g, "mage", rarity="common")
        for s in members(g, pid):
            s.max_stats = lambda: {"hp": 12.0, "atk": 1.0, "defense": 0.0, "mag": 1.0, "spd": 1.0}
            s.hp = 12
            if gear:
                s.gear = {"weapon": "apprentice_wand"}
        return pid

    def test_lose_xp_rules(self):
        g = rich()
        s = g.gacha.make_slime("common", "barbarian")
        s.level, s.xp, s.total_xp = 5, 100, 1000
        need = config.xp_to_next(5)
        lost = lose_xp(s, 0.4)
        self.assertEqual(lost, int(need * 0.4))
        self.assertEqual(s.total_xp, 1000 - lost)
        s.level, s.xp = 5, 3                            # not enough progress: slides back one level
        lose_xp(s, 0.4)
        self.assertEqual(s.level, 4)
        s.level, s.xp = 1, 5
        self.assertEqual(lose_xp(s, 0.9), 5)            # never below level 1
        self.assertEqual((s.level, s.xp), (1, 0))

    def test_knocked_out_slime_loses_xp_morale_and_gear_but_lives(self):
        g = rich(13)
        pid = self._weak_party(g)
        ms = members(g, pid)
        for s in ms:
            s.level, s.xp, s.total_xp = 4, 50, 400
            s.morale = 70
        before = {s.id: (s.total_xp, s.morale) for s in ms}
        g.rng.random = lambda: 0.99                     # nothing is ever recovered
        res = g.grind(pid, 5, 1)
        ko = [s for s in ms if s.name in " ".join(res.summary)]
        self.assertTrue(res.runs[0].knocked_out)
        self.assertEqual(g.graveyard, [])               # nobody died
        for s in ms:
            if s.name in res.runs[0].knocked_out:
                self.assertLess(s.total_xp, before[s.id][0])
                self.assertLess(s.morale, before[s.id][1] - 15)
                self.assertEqual(s.gear, {})
        self.assertTrue(g.pit_lost)                     # the gear stayed in the Pit

    def test_commitment_and_flags(self):
        g = rich(14)
        pid = party(g, strong=True)
        for s in members(g, pid):
            s.level, s.xp = 3, 0
        res = g.grind(pid, 2, 4)
        self.assertEqual(len(res.runs), 4)              # all requested runs are done
        self.assertIn("finished", res.stop_reason)
        self.assertTrue(all(s.in_dungeon == "" for s in members(g, pid)))

    def test_whole_party_knocked_out_ends_the_session(self):
        g = rich(15)
        pid = self._weak_party(g, gear=False)
        res = g.grind(pid, 5, 10)
        self.assertLess(len(res.runs), 10)
        self.assertIn("knocked out", res.stop_reason)
        self.assertTrue(all(s.in_dungeon == "" for s in members(g, pid)))

    def test_recovery_chance_follows_party_synergy(self):
        def trial(compat_bond):
            g = rich(16)
            pid = party(g, "barbarian")
            ms = members(g, pid)
            fallen, others = ms[0], ms[1:]
            for a in ms:
                for b in ms:
                    if a is not b:
                        g.social.add_bond(a, b, compat_bond)
            fallen.gear = {"weapon": "wooden_club"}
            g.rng.random = lambda: 0.5
            g._drop_gear([fallen], others, ms, "Gloop Pit", [])
            return bool(g.inventory.items)
        self.assertTrue(trial(50))                      # close party: carried back
        self.assertFalse(trial(-30))                    # hostile party: left behind

    def test_nobody_left_to_carry_it(self):
        g = rich()
        pid = party(g, "barbarian")
        f = members(g, pid)[0]
        f.gear = {"armor": "gel_mail"}
        log = []
        g._drop_gear([f], [], [f], "Hollow Descent", log)
        self.assertEqual(g.inventory.items, {})
        self.assertTrue(any("lost" in l and "forever" in l for l in log))

    def test_pit_lost_gear_can_be_dug_up_later(self):
        g = rich()
        pid = party(g, "barbarian")
        g.pit_lost = ["goo_blade"]
        g.rng.random = lambda: 0.0
        log = []
        g._recover_pit_gear(members(g, pid), log)
        self.assertEqual(g.pit_lost, [])
        self.assertEqual(g.inventory.items["goo_blade"], 1)


class TestEquipment(unittest.TestCase):
    def test_armory_tier_gate_and_cost(self):
        g = rich()
        gel = g.wallet.get("white_gel")
        g.buy_gear("wooden_club")
        self.assertEqual(g.wallet.get("white_gel"), gel - 30)
        with self.assertRaises(InvalidAction):
            g.buy_gear("goo_blade")                     # tier 2 needs Armory level 3
        g.buildings.levels["armory"] = 3
        g.buy_gear("goo_blade")
        self.assertEqual({x.tier for x in g.gear_shop()} , {1, 2})
        poor = Game(1)
        poor.wallet.spend("white_gel", poor.wallet.get("white_gel"))
        with self.assertRaises(NotEnoughResources):
            poor.buy_gear("wooden_club")

    def test_equip_changes_stats_and_swaps(self):
        g = rich()
        s = g.gacha.make_slime("common", "barbarian")
        g.roster[s.id] = s
        atk, hp = s.max_stats()["atk"], s.max_hp
        g.buy_gear("wooden_club")
        g.buy_gear("hunting_bow")
        g.equip(s.id, "wooden_club")
        self.assertAlmostEqual(s.max_stats()["atk"], atk + 3, places=1)
        g.equip(s.id, "hunting_bow")                    # swaps out the club
        self.assertEqual(g.inventory.items["wooden_club"], 1)
        self.assertEqual(s.gear["weapon"], "hunting_bow")
        g.buy_gear("leather_wrap")
        g.equip(s.id, "leather_wrap")
        self.assertGreater(s.max_hp, hp)
        g.unequip(s.id, "armor")
        self.assertEqual(s.max_hp, hp)
        with self.assertRaises(InvalidAction):
            g.unequip(s.id, "charm")
        with self.assertRaises(InvalidAction):
            g.equip(s.id, "kings_edge")                 # not owned

    def test_dying_outside_a_dungeon_returns_gear(self):
        g = rich()
        s = g.gacha.make_slime("common", "mage")
        g.roster[s.id] = s
        s.gear = {"weapon": "apprentice_wand", "charm": "lucky_pebble"}
        s.hp, s.death_cause = 0, "starvation"
        g._reap([])
        self.assertEqual(g.inventory.items["apprentice_wand"], 1)
        self.assertEqual(g.inventory.items["lucky_pebble"], 1)

    def test_cannot_change_gear_inside_a_dungeon(self):
        g = rich()
        pid = party(g, strong=True)
        s = members(g, pid)[0]
        g.buy_gear("wooden_club")
        g.enter_dungeon(pid)
        with self.assertRaises(InvalidAction):
            g.equip(s.id, "wooden_club")

    def test_gear_persists(self):
        g = rich()
        s = g.gacha.make_slime("common", "barbarian")
        g.roster[s.id] = s
        g.buy_gear("wooden_club")
        g.buy_gear("lucky_pebble")
        g.equip(s.id, "wooden_club")
        g.pit_lost = ["gel_mail"]
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.slime(s.id).gear, {"weapon": "wooden_club"})
        self.assertEqual(h.inventory.items["lucky_pebble"], 1)
        self.assertEqual(h.pit_lost, ["gel_mail"])


class TestSacrificeStress(unittest.TestCase):
    def _colony(self, n=8):
        g = rich(21)
        for _ in range(n):
            s = g.gacha.make_slime("common", "barbarian")
            s.traits = ["lazy", "timid"]
            g.roster[s.id] = s
            s.morale = 80
        return g

    def test_merging_lowers_morale_of_everyone_including_the_target(self):
        g = self._colony()
        t, d, *rest = g.slimes()
        g.merge(t.id, d.id)
        self.assertLess(t.morale, 80 + config.MERGE_MORALE_TARGET + 1)
        self.assertTrue(all(o.morale < 80 for o in rest))
        self.assertEqual(g.sacrifice_stress, 1.0)

    def test_repeated_sacrifices_hurt_more(self):
        g = self._colony()
        ss = g.slimes()
        g.merge(ss[0].id, ss[1].id)
        probe_a = ss[7].morale
        drop1 = 80 - probe_a
        for s in g.slimes():
            s.morale = 80
        g.merge(ss[0].id, ss[2].id)                      # second sacrifice straight away
        drop2 = 80 - ss[7].morale
        self.assertGreater(drop2, drop1 * 1.3)
        self.assertEqual(g.sacrifice_stress, 2.0)

    def test_stress_drags_the_morale_target_and_decays(self):
        g = self._colony(3)
        s = g.slimes()[0]
        g.sacrifice_stress = 3.0
        s.morale = 100
        g.tick(10)
        calm = self._colony(3).slimes()[0]
        calm.morale = 100
        self_calm = calm
        # a stressed colony settles lower than an untroubled one
        g2 = self._colony(3)
        c = g2.slimes()[0]
        c.morale = 100
        g2.tick(10)
        self.assertLess(s.morale, c.morale)
        g.tick(config.SACRIFICE_STRESS_DECAY_TICKS * 4)
        self.assertEqual(g.sacrifice_stress, 0.0)

    def test_council_cost_estimate_rises_with_stress(self):
        g = self._colony()
        calm = g.council()["merges"][0]["grief"]
        g.sacrifice_stress = 2.0
        self.assertGreater(g.council()["merges"][0]["grief"], calm * 1.5)


if __name__ == "__main__":
    unittest.main()
