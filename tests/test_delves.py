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


def strong(g, pid, progress=0):
    for s in members(g, pid):
        s.progress = progress
    return pid


class TestDelve(unittest.TestCase):
    def test_floors_are_fixed_by_the_seed(self):
        a = [e.key for e in dungeon.floor_plan(5, 3, 5)]
        self.assertEqual(a, [e.key for e in dungeon.floor_plan(5, 3, 5)])
        others = [tuple(e.key for e in dungeon.floor_plan(s, 3, 5)) for s in range(6, 12)]
        self.assertTrue(any(o != tuple(a) for o in others))

    def test_exit_only_at_checkpoints(self):
        g = rich()
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        self.assertTrue(all(s.in_dungeon == "main" for s in members(g, pid)))
        self.assertTrue(g.can_leave(pid))                       # before the first fight: still at the entrance
        for floor in (1, 2, 3, 4):
            g.delve_next(pid)
            self.assertFalse(g.can_leave(pid))
            with self.assertRaises(InvalidAction) as cm:
                g.leave_dungeon(pid)
            self.assertIn("boss of floor 5", str(cm.exception))
            self.assertIn(pid, g.delves)
        rep = g.delve_next(pid)                                  # the boss of floor 5
        self.assertTrue(rep.victory)
        self.assertTrue(g.can_leave(pid))                        # checkpoint reached
        self.assertTrue(all(s.progress == 5 for s in members(g, pid)))
        msg = g.leave_dungeon(pid)
        self.assertIn("climbs out", msg)
        self.assertNotIn(pid, g.delves)
        self.assertTrue(all(s.in_dungeon == "" for s in members(g, pid)))

    def test_can_push_on_past_a_checkpoint(self):
        g = rich()
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        for _ in range(5):
            g.delve_next(pid)
        self.assertEqual(g.delves[pid]["floor"], 6)
        g.delve_next(pid)                                        # floor 6 without leaving
        self.assertFalse(g.can_leave(pid))
        self.assertEqual(g.best_floor, 6)

    def test_progress_is_per_slime_and_gates_entry(self):
        g = rich()
        vets = party(g, strong=True, name="Vets")
        g.enter_dungeon(vets)
        for _ in range(5):
            g.delve_next(vets)
        g.leave_dungeon(vets)
        self.assertEqual(g.entry_options(vets), [1, 6])
        # a brand-new party cannot start at floor 6, nor can a mixed party
        rookies = party(g, strong=True, name="Rookies")
        with self.assertRaises(InvalidAction) as cm:
            g.enter_dungeon(rookies, 6)
        self.assertIn("has only cleared floor 0", str(cm.exception))
        self.assertEqual(g.entry_options(rookies), [1])
        # swap one rookie into the veterans: the whole party is held back to floor 1
        v0, r0 = members(g, vets)[0], members(g, rookies)[0]
        g.party_remove(v0.id)
        g.party_remove(r0.id)
        g.party_add(vets, r0.id)
        self.assertEqual(g.entry_options(vets), [1])
        with self.assertRaises(InvalidAction):
            g.enter_dungeon(vets, 6)
        g.enter_dungeon(vets, 1)                                 # walking down from the first floor is fine

    def test_other_parties_can_walk_the_same_floors(self):
        g = rich()
        a = party(g, strong=True, name="A")
        b = party(g, strong=True, name="B")
        g.enter_dungeon(a)
        g.enter_dungeon(b)                                       # both inside at the same time
        ra, rb = g.delve_next(a), g.delve_next(b)
        self.assertEqual(g.delves[a]["floor"], g.delves[b]["floor"])
        self.assertTrue(ra.victory and rb.victory)
        self.assertEqual([l for l in ra.log if "Hollow Descent - floor" in l][0].split("[")[0],
                         [l for l in rb.log if "Hollow Descent - floor" in l][0].split("[")[0])

    def test_boss_bounty_is_paid_once_per_boss_floor_for_the_colony(self):
        g = rich()
        a = party(g, strong=True, name="A")
        b = party(g, strong=True, name="B")
        for pid in (a, b):
            g.enter_dungeon(pid)
            for _ in range(5):
                g.delve_next(pid)
            g.leave_dungeon(pid)
        self.assertEqual(sum("First boss bounty" in l for l in g.journal), 1)
        self.assertEqual(g.bounties, {5})

    def test_recall_does_not_free_a_delver(self):
        g = rich()
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        g.delve_next(pid)
        g.recall(members(g, pid)[0].id)
        self.assertEqual(members(g, pid)[0].in_dungeon, "main")

    def test_wipe_ends_the_delve_and_deaths_are_permanent(self):
        g = rich(3)
        pid = party(g, "mage", rarity="common")
        names = [s.name for s in members(g, pid)]
        for s in members(g, pid):
            s.gear = {"weapon": "wooden_club"}
            s.progress = 45
        g.enter_dungeon(pid, 46)
        rep = g.delve_next(pid)
        self.assertEqual(rep.winner, "foes")
        self.assertNotIn(pid, g.delves)
        self.assertEqual(len(g.roster), 0)
        self.assertEqual(sorted(d["name"] for d in g.graveyard), sorted(names))
        self.assertEqual(g.inventory.items, {})

    def test_survivors_stay_inside_with_a_short_party(self):
        g = rich(4)
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        victim = members(g, pid)[0]
        victim.hp, victim.death_cause = 0, "test"
        g._reap([])
        self.assertEqual(len(members(g, pid)), 4)
        rep = g.delve_next(pid)
        self.assertTrue(rep.victory)
        self.assertIn(pid, g.delves)

    def test_camp_heals_inside_and_costs_time(self):
        g = rich(5)
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        g.delves[pid]["floor"] = 6                          # camping is limited to about one hour per floor
        for s in members(g, pid):
            s.hp = max(1, s.max_hp // 4)
        g.rng.random = lambda: 0.99
        t0 = g.tick_count
        g.delve_camp(pid, 6)
        self.assertEqual(g.tick_count - t0, 6)
        self.assertTrue(all(s.hp > s.max_hp // 4 + 1 for s in members(g, pid)))
        self.assertIn(pid, g.delves)

    def test_camp_ambush_can_kill(self):
        g = rich(6)
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        victim = members(g, pid)[0]
        victim.hp = 1
        victim.gear = {"weapon": "kings_edge"}
        g.rng.random = lambda: 0.0
        g.rng.uniform = lambda a, b: 50.0
        out = g.delve_camp(pid, 1)
        self.assertTrue(any("ambush" in l for l in out))
        self.assertIn("ambushed", g.graveyard[0]["cause"])

    def test_walking_a_floor_teaches_it(self):
        g = rich()
        pid = party(g, strong=True)
        self.assertEqual(g._knowledge(1), 0)
        g.enter_dungeon(pid)
        g.delve_next(pid)
        self.assertEqual(g._knowledge(1), 100.0)

    def test_delve_survives_save_and_load(self):
        g = rich()
        pid = party(g, strong=True)
        g.enter_dungeon(pid)
        g.delve_next(pid)
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.delves[pid]["floor"], 2)
        self.assertTrue(all(s.in_dungeon == "main" and s.progress == 1 for s in h.party_members(pid)))
        self.assertEqual(h.dungeon_seed, g.dungeon_seed)
        self.assertEqual(h.intel, g.intel)

    def test_v6_save_migrates_progress_and_segment_intel(self):
        g = rich()
        a = g.gacha.make_slime("common", "barbarian")
        g.roster[a.id] = a
        d = g.to_dict()
        d["version"] = 6
        d["main_floor"] = 5
        d["intel"] = {"0": 60.0}
        d.pop("bounties", None)
        h = Game.from_dict(d)
        self.assertEqual(h.slime(a.id).progress, 5)
        self.assertEqual(h.intel[3], 60.0)
        self.assertEqual(h.bounties, {5})


class TestScouting(unittest.TestCase):
    def test_validation(self):
        g = rich()
        pid = party(g, strong=True)
        for bad in [(0, 1, 5), (3, 2, 5), (1, 12, 5)]:
            with self.assertRaises(InvalidAction):
                g.scout(pid, *bad)
        with self.assertRaises(InvalidAction):
            g.scout(pid, 1, 2, 1)                       # budget below the minimum
        with self.assertRaises(InvalidAction):
            g.scout(pid, 3, 4, 8)                       # nobody has cleared floor 2
        short = g.create_party("short")
        with self.assertRaises(InvalidAction):
            g.scout(short.id, 1, 1, 8)

    def test_scouts_must_have_walked_the_floors_above(self):
        g = rich()
        pid = party(g, strong=True)
        strong(g, pid, progress=4)
        g.rng.random = lambda: 0.99
        res = g.scout(pid, 5, 5, g.scout_plan(pid, 5, 5)["safe"])
        self.assertTrue(res.complete)

    def test_single_floor_and_ranges_are_both_allowed(self):
        g = rich(7)
        pid = party(g, strong=True)
        g.rng.random = lambda: 0.99
        one = g.scout(pid, 1, 1, g.scout_plan(pid, 1, 1)["safe"])
        self.assertTrue(one.complete)
        self.assertEqual(g.intel[1], 100.0)
        self.assertNotIn(2, g.intel)
        strong(g, pid, progress=1)                              # floors above 2 are walked
        three = g.scout(pid, 2, 4, g.scout_plan(pid, 2, 4)["safe"])
        self.assertTrue(three.complete)
        self.assertTrue(all(g.intel[f] == 100.0 for f in (1, 2, 3, 4)))

    def test_not_100_percent_strands_the_party_and_unrescued_they_are_lost(self):
        g = rich(8)
        pid = party(g, strong=True)
        names = [s.name for s in members(g, pid)]
        for s in members(g, pid):
            s.gear = {"weapon": "wooden_club"}
        g.rng.random = lambda: 0.99
        plan = g.scout_plan(pid, 1, 4)
        res = g.scout(pid, 1, 4, max(2, int(plan["low"] * 0.5)))
        self.assertFalse(res.complete)
        self.assertTrue(res.stranded)
        self.assertEqual(len(g.roster), 5)                      # overdue, not dead yet: a rescue party may still come
        self.assertTrue(any("overdue" in l for l in res.log))
        g.tick(config.RESCUE_DEADLINE_HOURS)
        self.assertEqual(len(g.roster), 0)
        self.assertEqual(sorted(d["name"] for d in g.graveyard), sorted(names))
        self.assertEqual(g.inventory.items, {})                 # nobody left to carry the gear
        # a half-finished note survives: partial knowledge on the floors they reached
        partial = [f for f in (1, 2, 3, 4) if 0 < g.intel.get(f, 0) < 100.0]
        self.assertTrue(partial and all(g.intel[f] <= 100 * config.SCOUT_NOTE_FRACTION for f in partial))   # the floor they were on
        self.assertTrue(all(g.intel.get(f, 0) in (0, 100.0) or f in partial for f in (1, 2, 3, 4)))       # finished floors stay fully known

    def test_budget_between_estimate_and_truth(self):
        # the hidden per-floor factor means the nominal estimate can be too short
        seeds_short = 0
        for seed in range(1, 40):
            nominal, actual = dungeon.floor_hours(seed, 3, 1.0)
            self.assertGreaterEqual(actual, nominal * config.SCOUT_VARIANCE[0] - 1e-9)
            self.assertLessEqual(actual, nominal * config.SCOUT_VARIANCE[1] + 1e-9)
            seeds_short += actual > nominal
        self.assertTrue(0 < seeds_short < 39)
        est = dungeon.scout_estimate(5, 1, 3)
        self.assertLess(est["low"], est["nominal"] < est["high"] and est["high"])
        self.assertGreaterEqual(est["safe"], est["high"])

    def test_deeper_floors_take_longer_and_skill_helps(self):
        self.assertGreater(dungeon.scout_estimate(1, 9, 9)["nominal"], dungeon.scout_estimate(1, 1, 1)["nominal"])
        self.assertLess(dungeon.scout_estimate(1, 1, 5, 2.0)["nominal"], dungeon.scout_estimate(1, 1, 5, 1.0)["nominal"])
        g1, g2 = rich(9), rich(9)
        a, b = party(g1, "barbarian", strong=True), party(g2, "rogue", strong=True)
        self.assertGreater(g1.scout_plan(a, 1, 3)["nominal"], g2.scout_plan(b, 1, 3)["nominal"])

    def test_supplies_are_paid_up_front_and_unused_time_is_not_refunded(self):
        g = rich(10)
        pid = party(g, strong=True)
        g.rng.random = lambda: 0.99
        food, t0 = g.wallet.get("food"), g.tick_count
        res = g.scout(pid, 1, 1, 12)
        self.assertGreaterEqual(food - g.wallet.get("food"), 12)    # the whole budget was packed
        self.assertLess(g.tick_count - t0, 12)                  # they came back as soon as they finished
        self.assertTrue(res.complete)
        poor = rich(11)
        p2 = party(poor, strong=True)
        poor.wallet.spend("food", poor.wallet.get("food"))
        with self.assertRaises(NotEnoughResources):
            poor.scout(p2, 1, 1, 8)

    def test_flags_only_while_out(self):
        g = rich(12)
        pid = party(g, strong=True)
        g.rng.random = lambda: 0.99
        seen = []
        orig = g.tick
        g.tick = lambda n=1: (seen.append({s.in_dungeon for s in members(g, pid)}), orig(n))[1]
        g.scout(pid, 1, 1, 8)
        self.assertTrue(all(x == {"scout"} for x in seen))
        self.assertTrue(all(s.in_dungeon == "" for s in members(g, pid)))

    def test_ambush_deaths_during_a_scout_are_permanent(self):
        g = rich(13)
        pid = party(g, "mage", rarity="common")
        for s in members(g, pid):
            s.progress = 3
            s.hp = 1
        g.rng.random = lambda: 0.0
        res = g.scout(pid, 4, 4, 12)
        self.assertFalse(res.complete)
        self.assertEqual(len(g.graveyard), 5)

    def test_intel_reveals_in_stages_and_matches_reality(self):
        seen = {k: dungeon.intel_lines(3, 1, k, 5) for k in (0, 25, 45, 65, 85, 100)}
        self.assertEqual(seen[0], ["unknown"])
        counts = [len(seen[k]) for k in (0, 25, 45, 65, 85, 100)]
        self.assertEqual(counts, sorted(counts))
        self.assertTrue(any("weakness" in l for l in seen[100]))
        self.assertTrue(any(l.startswith("BOSS") for l in dungeon.intel_lines(3, 5, 70, 5)))
        self.assertFalse(any(l.startswith("BOSS") for l in dungeon.intel_lines(3, 5, 45, 5)))
        real = {e.name for e in dungeon.floor_plan(3, 1, 5)}
        self.assertTrue(all(any(n in l for l in seen[45]) for n in real))

    def test_intel_gives_a_battle_bonus(self):
        g = rich(14)
        pid = party(g, strong=True)
        g.intel[1] = 100
        g.enter_dungeon(pid)
        rep = g.delve_next(pid)
        self.assertTrue(any("scouting intel +10%" in l for l in rep.log))

    def test_floor_horizon_grows_with_progress(self):
        g = rich()
        self.assertEqual(g.floor_horizon(), 10)
        g.best_floor = 12
        self.assertEqual(g.floor_horizon(), 20)
        self.assertEqual(len(g.intel_report()), 20)


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
        need = s.xp_needed(5)
        lost = lose_xp(s, 0.4)
        self.assertEqual(lost, int(need * 0.4))
        self.assertEqual(s.total_xp, 1000 - lost)
        s.level, s.xp = 5, 3                            # not enough progress: slides back one level
        lose_xp(s, 0.4)
        self.assertEqual(s.level, 4)
        s.level, s.xp = 1, 5
        self.assertEqual(lose_xp(s, 0.9), 5)            # never below level 1
        self.assertEqual((s.level, s.xp), (1, 0))

    def test_knocked_out_slime_loses_morale_and_gear_but_never_xp(self):
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
                self.assertGreaterEqual(s.total_xp, before[s.id][0])      # an XP farm: no negative XP
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
