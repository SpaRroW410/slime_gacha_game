"""Sparring / fighting styles, Rest Area, buildings, compatibility, morale and the Council."""
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, sparring
from slime_gacha.ai import Conflict
from slime_gacha.battle import BattleSystem, _style_attack
from slime_gacha.buildings import BUILDINGS
from slime_gacha.errors import InvalidAction, NotEnoughResources
from slime_gacha.game import Game
from slime_gacha.growth import add_xp


def rich(seed=1):
    g = Game(seed)
    for k in ("white_gel", "purple_gel", "essence", "food"):
        g.wallet.add(k, 20000)
    g.needs.auto_care = False
    return g


def mk(g, archetype="barbarian", stars=2, rarity="common", traits=None):
    s = g.gacha.make_slime(rarity, archetype, stars=stars)
    if traits:
        s.traits = list(traits)
    g.roster[s.id] = s
    return s


def refresh(*slimes):
    for s in slimes:
        s.hp, s.state = s.max_hp, "idle"
        s.needs.v["energy"] = s.needs.v["food"] = 100


class TestSparring(unittest.TestCase):
    def test_spar_is_nonlethal_and_gives_no_xp(self):
        g = rich()
        a, b = mk(g), mk(g)
        gel, t0 = g.wallet.get("white_gel"), g.tick_count
        res = g.spar(a.id, b.id, "sword")
        self.assertEqual(g.wallet.get("white_gel"), gel - 2)
        self.assertEqual(g.tick_count - t0, config.SPAR_TICKS)
        self.assertEqual((a.total_xp, b.total_xp, a.level, b.level), (0, 0, 1, 1))
        self.assertEqual(g.graveyard, [])
        hps = sorted([a.hp, b.hp])
        self.assertEqual(hps[0], 1)                       # the loser yielded at exactly 1 HP
        self.assertTrue(a.style_xp["sword"] > 0 and b.style_xp["sword"] > 0)
        self.assertTrue(any("beat" in l for l in res.summary))

    def test_winner_earns_more_style_xp(self):
        g = rich(3)
        a, b = mk(g), mk(g)
        g.spar(a.id, b.id, "sword")
        hi, lo = sorted([a.style_xp["sword"], b.style_xp["sword"]], reverse=True)
        self.assertAlmostEqual(hi / lo, config.SPAR_WINNER_MULT, places=1)

    def test_class_affinity(self):
        g = rich()
        r1, r2 = mk(g, "ranger"), mk(g, "ranger")
        b1, b2 = mk(g, "barbarian"), mk(g, "barbarian")
        g.spar(r1.id, r2.id, "archery")
        g.spar(b1.id, b2.id, "archery")
        self.assertGreater(r1.style_xp["archery"] + r2.style_xp["archery"],
                           (b1.style_xp["archery"] + b2.style_xp["archery"]) * 1.4)

    def test_validation(self):
        g = rich()
        a, b = mk(g), mk(g)
        with self.assertRaises(InvalidAction):
            g.spar(a.id, a.id, "sword")
        b.hp = 1
        with self.assertRaises(InvalidAction):
            g.spar(a.id, b.id, "sword")                   # too hurt
        refresh(b)
        b.state = "hunting"
        with self.assertRaises(InvalidAction):
            g.spar(a.id, b.id, "sword")
        with self.assertRaises(KeyError):
            g.spar(a.id, mk(g).id, "dance")

    def test_style_ceiling_and_training_grounds_upgrade(self):
        g = rich(4)
        a, b = mk(g), mk(g)
        cap = g.buildings.style_cap()
        self.assertEqual(cap, 4)
        for _ in range(60):
            refresh(a, b)
            try:
                g.spar(a.id, b.id, "sword")
            except InvalidAction as e:
                self.assertIn("ceiling", str(e))
                break
        else:
            self.fail("never reached the ceiling")
        self.assertEqual(sparring.style_level(a, "sword"), cap)
        g.upgrade_building("training_grounds")
        refresh(a, b)
        g.spar(a.id, b.id, "sword")                       # allowed again
        self.assertGreater(a.style_xp["sword"], config.STYLE_XP[cap - 1])

    def test_two_parties_spar_as_teams(self):
        g = rich()
        pa, pb = g.create_party("A"), g.create_party("B")
        for pid in (pa.id, pb.id):
            for _ in range(g.parties.size):
                s = mk(g)
                g.parties.add(pid, s.id)
        team_a, team_b = g.party_members(pa.id), g.party_members(pb.id)
        gel = g.wallet.get("white_gel")
        bond = g.social.bond(team_a[0], team_a[1])
        res = g.spar_parties(pa.id, pb.id, "magic")
        self.assertEqual(len(res.reports), 1)
        self.assertEqual(g.wallet.get("white_gel"), gel - 3)         # one flat price for the whole session
        self.assertTrue(all(s.style_xp.get("magic", 0) > 0 for s in team_a + team_b))
        self.assertTrue(any("synergy" in l for l in res.summary))
        self.assertGreater(g.social.bond(team_a[0], team_a[1]), bond)   # teammates grew closer
        with self.assertRaises(InvalidAction):
            g.spar_parties(pa.id, pa.id, "magic")

    def test_sparring_builds_bonds_and_morale(self):
        g = rich()
        a, b = mk(g), mk(g)
        before = g.social.bond(a, b)
        a.morale = b.morale = 50
        g.spar(a.id, b.id, "sword")
        self.assertGreater(g.social.bond(a, b), before)
        self.assertGreater(a.morale + b.morale, 100)

    def test_style_perks_in_battle(self):
        g = rich()
        a = mk(g)
        a.style_xp["sword"] = config.STYLE_XP[9]
        a.style_xp["archery"] = config.STYLE_XP[9]
        a.style_xp["magic"] = config.STYLE_XP[9]
        c = BattleSystem.from_slime(a)
        from slime_gacha.abilities import get_ability
        self.assertAlmostEqual(_style_attack(c, get_ability("splat")), 1 + 10 * config.STYLE_SWORD_DAMAGE)
        self.assertAlmostEqual(_style_attack(c, get_ability("spark")), 1 + 10 * config.STYLE_MAGIC_POWER)
        plain = BattleSystem.from_slime(mk(g))
        self.assertGreater(c.stat("spd") / plain.stat("spd"), 1.2)
        self.assertEqual(sparring.style_label(a).split()[1], "10")


class TestRestArea(unittest.TestCase):
    def test_heals_at_the_base_rate_then_leaves(self):
        g = rich()
        s = mk(g)
        s.hp = 1
        g.rest(s.id)
        self.assertEqual(s.state, "resting")
        g.tick(1)
        self.assertGreaterEqual(s.hp, int(s.max_hp * config.SLEEP_HP_REGEN))
        self.assertLess(s.hp, s.max_hp * 0.5)                          # HP is not what the Rest Area improves
        g.tick(16)
        self.assertEqual((s.hp, s.state), (s.max_hp, "idle"))

    def test_energy_returns_faster_with_the_level_and_hp_stays_at_base(self):
        g = rich()
        a = mk(g)
        a.needs.set("energy", 5)
        g.rest(a.id)
        g.tick(1)
        low = a.needs.get("energy")
        g.buildings.levels["rest_area"] = 5
        c = mk(g)
        c.needs.set("energy", 5)
        c.hp = 1
        g.rest(c.id)
        g.tick(1)
        self.assertGreater(c.needs.get("energy"), low)
        self.assertLess(c.hp, c.max_hp)                   # even at level 5 health heals at the base rate

    def test_capacity_and_upgrade(self):
        g = rich()
        ss = [mk(g) for _ in range(6)]
        for s in ss[:5]:
            g.rest(s.id)
        with self.assertRaises(InvalidAction):
            g.rest(ss[5].id)
        g.upgrade_building("rest_area")
        g.rest(ss[5].id)
        self.assertEqual(g.buildings.rest_capacity(), 10)

    def test_busy_slimes_cannot_rest(self):
        g = rich()
        s = mk(g)
        s.state = "hunting"
        with self.assertRaises(InvalidAction):
            g.rest(s.id)

    def test_auto_care_admits_the_wounded(self):
        g = rich()
        g.needs.auto_care = True
        s = mk(g)
        s.hp = 2
        ev = g.tick(1)
        self.assertTrue(any("Rest Area" in e for e in ev))
        self.assertEqual(s.state, "resting")

    def test_starving_slime_cannot_heal(self):
        g = rich()
        s = mk(g)
        s.hp = 5
        s.needs.set("food", 0)
        g.rest(s.id)
        g.tick(1)
        self.assertNotEqual(s.state, "resting")

    def test_spar_loser_recovers_in_rest_area(self):
        g = rich(2)
        a, b = mk(g), mk(g)
        g.spar(a.id, b.id, "sword")
        loser = min((a, b), key=lambda s: s.hp)
        self.assertEqual(loser.hp, 1)
        g.rest(loser.id)
        g.tick(16)
        self.assertEqual(loser.hp, loser.max_hp)

    def test_party_rest_helper(self):
        g = rich()
        for _ in range(5):
            mk(g)
        p = g.create_party("p")
        g.party_autofill(p.id)
        for s in g.slimes():
            s.hp = 1
        hours = g._rest_party_until_healed(p.id)
        self.assertTrue(all(s.hp >= s.max_hp * 0.85 for s in g.slimes()))
        self.assertLessEqual(hours, 16)


class TestBuildings(unittest.TestCase):
    def test_buildings_start_at_level_one(self):
        g = rich()
        self.assertEqual(set(BUILDINGS.keys()), {"rest_area", "training_grounds", "library", "barracks", "armory", "chamber", "alchemy", "kitchen", "hospital"})
        self.assertTrue(all(g.buildings.level(k) == 1 for k in BUILDINGS.keys()))

    def test_upgrade_pays_and_caps(self):
        g = rich()
        gel = g.wallet.get("white_gel")
        cost = g.buildings.next_cost("rest_area")
        g.upgrade_building("rest_area")
        self.assertEqual(g.wallet.get("white_gel"), gel - cost["white_gel"])
        for _ in range(3):
            g.upgrade_building("rest_area")
        self.assertEqual(g.buildings.level("rest_area"), 5)
        with self.assertRaises(InvalidAction):
            g.upgrade_building("rest_area")
        with self.assertRaises(InvalidAction):
            g.upgrade_building("castle")

    def test_poor_cannot_upgrade(self):
        g = Game(1)
        g.wallet.spend("white_gel", g.wallet.get("white_gel"))
        with self.assertRaises(NotEnoughResources):
            g.upgrade_building("barracks")

    def test_effects_scale(self):
        b = rich().buildings
        self.assertEqual([b.rest_capacity(l) for l in (1, 3, 5)], [5, 15, 25])
        self.assertEqual([b.style_cap(l) for l in (1, 2, 4, 5)], [4, 6, 10, 10])
        self.assertEqual([b.extra_spell_slots(l) for l in (1, 3, 5)], [0, 1, 2])
        self.assertFalse(b.tier3_open(2))
        self.assertTrue(b.tier3_open(3))
        self.assertLess(b.synergy_mult(1), b.synergy_mult(5))

    def test_library_level_gates_tier_three_and_adds_slots(self):
        g = rich()
        self.assertEqual(g.library.spell_slots(), 4)
        g.buildings.levels["library"] = 3
        self.assertEqual(g.library.spell_slots(), 5)

    def test_report_and_persistence(self):
        g = rich()
        g.upgrade_building("barracks")
        rep = {r["key"]: r for r in g.building_report()}
        self.assertEqual(rep["barracks"]["level"], 2)
        self.assertIn("synergy", rep["barracks"]["now"])
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.buildings.level("barracks"), 2)


class TestCompatibility(unittest.TestCase):
    def test_rivals_vs_complements(self):
        g = rich()
        rival = g.compat(mk(g, "barbarian", traits=["brave", "kind"]).id, mk(g, "mage", traits=["brave", "kind"]).id)
        pals = g.compat(mk(g, "barbarian", traits=["brave", "kind"]).id, mk(g, "medic", traits=["brave", "kind"]).id)
        self.assertLess(rival["total"], 0)
        self.assertGreater(pals["total"], rival["total"] + 30)
        self.assertLess(rival["parts"]["class"], 0)

    def test_traits_matter_and_symmetric(self):
        g = rich()
        a, b = mk(g, "rogue", traits=["grumpy", "proud"]), mk(g, "ranger", traits=["grumpy", "proud"])
        c, d = mk(g, "rogue", traits=["kind", "chatty"]), mk(g, "rogue", traits=["timid", "brave"])
        self.assertLess(g.social.compat(a, b), g.social.compat(c, d))
        self.assertEqual(g.social.compat(c, d), g.social.compat(d, c))

    def test_shared_and_fusable_elements(self):
        g = rich()
        a, b = mk(g, "rogue", 3, traits=["lazy", "timid"]), mk(g, "rogue", 3, traits=["lazy", "timid"])
        base = g.social.compat(a, b)
        a.attuned, b.attuned = ["fire"], ["fire"]
        shared = g.social.compat(a, b)
        b.attuned = ["wind"]
        fusable = g.social.compat(a, b)                   # fire + wind = lightning
        self.assertGreater(shared, base)
        self.assertGreater(fusable, base)

    def test_bonds_friends_and_quarrels(self):
        g = rich()
        a, b = mk(g, traits=["lazy", "timid"]), mk(g, traits=["lazy", "timid"])
        base = g.social.compat(a, b)
        g.social.add_bond(a, b, 20)
        self.assertEqual(g.social.compat(a, b), base + 20)
        g.conflicts.conflicts.append(Conflict(1, a.id, b.id))
        self.assertEqual(g.social.compat(a, b), base + 20 + config.COMPAT_OPEN_CONFLICT)

    def test_conflict_hooks_move_bonds_and_morale(self):
        g = rich()
        a, b = mk(g), mk(g)
        a.morale = b.morale = 50
        g.conflicts.hook("brawl", a, b)
        self.assertEqual(a.morale, 35)
        self.assertLess(g.social.bond(a, b), 0)
        g.conflicts.conflicts.append(Conflict(1, a.id, b.id, 1, 0, "x"))
        g.wallet.add("food", 5)
        g.mediate(1, "snack")
        self.assertGreater(a.morale, 35)
        self.assertGreater(g.social.bond(a, b), -10)

    def test_compat_changes_quarrel_odds(self):
        g = rich()
        a, b = mk(g, "barbarian", traits=["grumpy", "proud"]), mk(g, "mage", traits=["grumpy", "proud"])
        c, d = mk(g, "barbarian", traits=["kind", "chatty"]), mk(g, "medic", traits=["kind", "chatty"])
        self.assertGreater(g.conflicts.chance(a, b), g.conflicts.chance(c, d) * 2)
        g.social.add_bond(c, d, 50)
        self.assertLess(g.conflicts.chance(c, d), config.CONFLICT_BASE_CHANCE)


class TestSynergyAndMorale(unittest.TestCase):
    def _party(self, g, archetypes, traits):
        for k in archetypes:
            mk(g, k, traits=traits)
        p = g.create_party("P")
        g.party_autofill(p.id)
        return p.id

    def test_synergy_range_and_barracks(self):
        g = rich()
        harmonious = self._party(g, ["barbarian", "medic", "barbarian", "medic", "ranger"], ["kind", "chatty"])
        for a in g.party_members(harmonious):
            for b in g.party_members(harmonious):
                if a is not b:
                    g.social.add_bond(a, b, 40)
        s1 = g.party_synergy(harmonious)
        self.assertGreater(s1, 1.0)
        self.assertLessEqual(s1, 1 + config.SYNERGY_MAX + 1e-9)
        g.buildings.levels["barracks"] = 5
        self.assertGreater(g.party_synergy(harmonious), s1)
        g2 = rich()
        bad = self._party(g2, ["barbarian", "mage", "rogue", "ranger", "necromancer"], ["grumpy", "proud"])
        self.assertLess(g2.party_synergy(bad), 1.0)

    def test_synergy_applies_in_battle(self):
        g = rich()
        pid = self._party(g, ["barbarian"] * 5, ["kind", "chatty"])
        rep = g.battle(pid, 1)
        self.assertTrue(any("Party synergy" in l for l in rep.log))
        mine = g.party_members(pid)
        base = BattleSystem.from_slime(mine[0], 1.0).power_mult
        self.assertAlmostEqual(BattleSystem.from_slime(mine[0], 1.1).power_mult / base, 1.1)

    def test_morale_scales_power(self):
        g = rich()
        s = mk(g)
        s.morale = 100
        hi = BattleSystem.from_slime(s).power_mult
        s.morale = 0
        lo = BattleSystem.from_slime(s).power_mult
        self.assertAlmostEqual(hi / lo, config.MORALE_POWER_MAX / config.MORALE_POWER_MIN)

    def test_morale_drifts_toward_mood_target(self):
        g = rich()
        s = mk(g)
        s.morale = 0
        g.tick(30)
        self.assertGreater(s.morale, 40)
        g.buildings.levels["barracks"] = 5
        s2 = mk(g)
        s2.morale = 0
        s3 = mk(g)
        s3.morale = 0
        g.buildings.levels["barracks"] = 1
        g.tick(1)
        a = s2.morale
        s3.morale = 0
        g.buildings.levels["barracks"] = 5
        s2.morale = 0
        g.tick(1)
        self.assertGreater(s2.morale, a)                  # higher barracks -> faster recovery

    def test_victory_and_defeat_move_morale(self):
        g = rich(2)
        pid = self._party(g, ["barbarian"] * 5, ["kind", "timid"])
        for s in g.party_members(pid):
            s.stage = 2
            add_xp(s, 10 ** 7)
            s.hp = s.max_hp
            s.morale = 50
        ms = g.party_members(pid)
        rep = g.battle(pid, 1)
        self.assertTrue(rep.victory)
        self.assertTrue(all(s.morale > 50 for s in ms if s.id in g.roster))
        g2 = rich(3)
        pid2 = self._party(g2, ["mage"] * 5, ["kind", "timid"])
        for s in g2.party_members(pid2):
            s.morale = 50
        ms2 = g2.party_members(pid2)
        rep2 = g2.battle(pid2, 4)                         # the boss crushes level-1 mages
        self.assertEqual(rep2.winner, "foes")
        self.assertTrue(all(s.morale < 50 for s in ms2 if s.id in g2.roster))

    def test_broken_morale_can_freeze(self):
        g = rich(5)
        s = mk(g)
        s.morale = 5
        from slime_gacha.battle import Enemy
        foe = Enemy("dummy", "Dummy", "🎯", 1, dict(hp=500, atk=0, defense=0, mag=0, spd=1), ["splat"], 1, {})
        rep = BattleSystem(random.Random(5)).run([s], [foe])
        self.assertTrue(any("freezes" in l for l in rep.log))

    def test_death_grief_hits_friends_harder(self):
        g = rich()
        a, b, c = mk(g), mk(g), mk(g)
        g.social.add_bond(a, b, 40)
        for s in (b, c):
            s.morale = 70
        a.hp, a.death_cause = 0, "test"
        g._reap([])
        self.assertLess(b.morale, c.morale)
        self.assertEqual(g.social.bonds, {})


class TestCouncil(unittest.TestCase):
    def _colony(self):
        g = rich()
        star = mk(g, "mage", 5, "legendary", ["kind", "chatty"])
        mid = mk(g, "ranger", 3, "rare", ["kind", "timid"])
        weak1 = mk(g, "rogue", 1, "common", ["grumpy", "proud"])
        weak2 = mk(g, "barbarian", 1, "common", ["grumpy", "proud"])
        return g, star, mid, weak1, weak2

    def test_ranking_and_verdicts(self):
        g, star, mid, w1, w2 = self._colony()
        rows = g.council()["rows"]
        self.assertEqual(rows[0]["slime"], star)
        self.assertEqual(rows[0]["verdict"], "KEEP")
        self.assertIn(rows[-1]["slime"], (w1, w2))
        self.assertEqual(rows[-1]["verdict"], "SACRIFICE?")
        self.assertTrue(any("5" in r or "legendary" in r for r in rows[0]["reasons"]))

    def test_bonds_protect_a_slime(self):
        g, star, mid, w1, w2 = self._colony()
        before = {r["slime"].id: r["score"] for r in g.council()["rows"]}
        for o in (star, mid, w2):
            g.social.add_bond(w1, o, 40)
        after = {r["slime"].id: r["score"] for r in g.council()["rows"]}
        self.assertGreater(after[w1.id], before[w1.id])

    def test_merge_suggestions_prefer_unloved_donors(self):
        g, star, mid, w1, w2 = self._colony()
        for o in (star, mid, w2):
            g.social.add_bond(w1, o, 50)                  # w1 is beloved: sacrificing hurts
        sugg = g.council()["merges"]
        self.assertTrue(sugg)
        self.assertEqual(sugg[0]["donor"], w2)
        self.assertGreater(g.social.grief(w1, g.slimes()), g.social.grief(w2, g.slimes()))
        nets = [s["net"] for s in sugg]
        self.assertEqual(nets, sorted(nets, reverse=True))

    def test_merge_compat_swings_xp(self):
        g = rich()
        t = mk(g, "barbarian", traits=["kind", "chatty"])
        good = mk(g, "medic", traits=["kind", "chatty"])
        bad = mk(g, "mage", traits=["grumpy", "proud"])
        for d in (good, bad):
            add_xp(d, 400)
        self.assertGreater(g.merge_preview(t.id, good.id), g.merge_preview(t.id, bad.id) * 1.1)

    def test_merge_inherits_bonds_and_costs_morale(self):
        g = rich()
        t, d, friend, stranger = mk(g), mk(g), mk(g), mk(g)
        g.social.add_bond(d, friend, 40)
        friend.morale = stranger.morale = t.morale = 70
        log = g.merge(t.id, d.id)
        self.assertGreater(g.social.bond(t, friend), 0)             # inherited
        self.assertEqual(g.social.bond(t, stranger), 0)
        self.assertLess(friend.morale, stranger.morale)             # friend grieves more
        self.assertLess(stranger.morale, 70)
        self.assertTrue(any("morale" in l for l in log))
        self.assertTrue(all(d.id not in k for k in g.social.bonds))

    def test_persistence_of_social_state(self):
        g = rich()
        a, b = mk(g), mk(g)
        g.social.add_bond(a, b, 25)
        a.morale = 33
        g.spar(a.id, b.id, "magic")
        h = Game.from_dict(g.to_dict())
        self.assertAlmostEqual(h.social.bond(h.slime(a.id), h.slime(b.id)), g.social.bond(a, b), places=1)
        self.assertEqual(h.slime(a.id).style_xp, a.style_xp)
        self.assertAlmostEqual(h.slime(a.id).morale, a.morale, places=3)


if __name__ == "__main__":
    unittest.main()
