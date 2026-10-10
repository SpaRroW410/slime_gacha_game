import os
import random
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config
from slime_gacha.abilities import Ability, register_ability
from slime_gacha.archetypes import ARCHETYPES, Archetype, register_archetype
from slime_gacha.battle import BattleSystem, Enemy
from slime_gacha.errors import InvalidAction, NotEnoughResources
from slime_gacha.game import Game
from slime_gacha.gacha import GachaSystem
from slime_gacha.growth import add_xp, evolve, merge_gain
from slime_gacha.resources import ResourceManager


def fresh(seed=1, n=0):
    g = Game(seed)
    g.wallet.add("silver", 100000)
    g.wallet.add("gold", 100000)
    if n:
        g.pull(n)
    return g


def full_party(g, tier_archetype="barbarian", rarity="legendary", xp=2000, name="Test"):
    """Add a full party of strong slimes and return its id."""
    p = g.create_party(name)
    for _ in range(g.parties.size):
        s = g.gacha.make_slime(rarity, tier_archetype, stars=3)
        g.roster[s.id] = s
        add_xp(s, xp)
        s.hp = s.max_hp
        g.parties.add(p.id, s.id)
    return p.id


class TestResources(unittest.TestCase):
    def test_atomic_spend(self):
        w = ResourceManager({"silver": 10, "food": 1})
        with self.assertRaises(NotEnoughResources):
            w.spend_many({"silver": 5, "food": 2})
        self.assertEqual(w.get("silver"), 10)       # nothing changed


class TestGacha(unittest.TestCase):
    def test_six_classes_registered(self):
        for k in ("barbarian", "mage", "medic", "rogue", "ranger", "necromancer"):
            self.assertIn(k, ARCHETYPES)

    def test_rates_are_90_9_point9_point09(self):
        self.assertEqual(config.RARITY_RATES, {"common": 90, "rare": 9, "epic": 0.9, "legendary": 0.09})

    def test_rarity_distribution(self):
        g = fresh(1)
        counts = {r: 0 for r in config.RARITIES}
        for _ in range(20000):
            counts[g.gacha.roll_rarity()] += 1
        self.assertGreater(counts["common"], 17500)
        self.assertTrue(1400 < counts["rare"] < 2200)
        self.assertLess(counts["legendary"], 40)

    def test_gold_boosts_rare_odds(self):
        g = fresh(2)
        silver = sum(g.gacha.roll_rarity(False) != "common" for _ in range(6000))
        gold = sum(g.gacha.roll_rarity(True) != "common" for _ in range(6000))
        self.assertGreater(gold, silver * 2.5)

    def test_star_probabilities_exponential_and_steeper_for_rank(self):
        pc = GachaSystem.star_probabilities("common")
        pl = GachaSystem.star_probabilities("legendary")
        self.assertAlmostEqual(sum(pc), 1.0)
        ratios = [pc[i + 1] / pc[i] for i in range(4)]
        self.assertTrue(all(abs(r - ratios[0]) < 1e-9 for r in ratios))        # exponential
        self.assertTrue(all(pc[i] > pc[i + 1] for i in range(4)))              # decreasing
        self.assertLess(pl[4], pc[4])                                           # high rank: rarer 5 stars
        self.assertLess(pl[4], 0.005)

    def test_stars_in_range_and_scale_stats(self):
        g = fresh(3)
        for _ in range(200):
            self.assertIn(g.gacha.roll_stars("rare"), range(1, 6))
        a = g.gacha.make_slime("common", "mage", stars=1)
        b = g.gacha.make_slime("common", "mage", stars=5)
        a.variance = b.variance = {k: 1.0 for k in a.variance}
        self.assertGreater(b.max_stats()["mag"], a.max_stats()["mag"] * 1.6)

    def test_cost_is_ten_of_silver_or_gold(self):
        g = Game(1)
        s0, g0 = g.wallet.get("silver"), g.wallet.get("gold")
        g.pull(1, "silver")
        g.pull(1, "gold")
        self.assertEqual(g.wallet.get("silver"), s0 - 10)
        self.assertEqual(g.wallet.get("gold"), g0 - 10)
        g.wallet.spend("silver", g.wallet.get("silver"))
        with self.assertRaises(NotEnoughResources):
            g.pull(1, "silver")

    def test_one_free_pull_per_day(self):
        g = Game(1)
        self.assertTrue(g.free_pull_available())
        g.pull(1, "free")
        self.assertFalse(g.free_pull_available())
        with self.assertRaises(InvalidAction):
            g.pull(1, "free")
        self.assertEqual(g.hours_to_free_pull(), config.DAY_TICKS)
        g.tick(config.DAY_TICKS)
        self.assertTrue(g.free_pull_available())
        g.pull(1, "free")
        with self.assertRaises(InvalidAction):
            g.pull(2, "free")                    # free pull is single only

    def test_pity_is_optional(self):
        g = fresh(3)
        with mock.patch.object(config, "PITY_LEGENDARY", 5):
            g.gacha.since_legendary = 4
            self.assertEqual(g.pull(1)[0].rarity, "legendary")
            self.assertEqual(g.gacha.since_legendary, 0)

    def test_deterministic_with_seed(self):
        a = [(s.name, s.archetype, s.rarity, s.stars) for s in fresh(9, 10).slimes()]
        b = [(s.name, s.archetype, s.rarity, s.stars) for s in fresh(9, 10).slimes()]
        self.assertEqual(a, b)


class TestNeeds(unittest.TestCase):
    def test_auto_sleep_and_wake(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        s.needs.set("energy", 10)
        g.tick(1)
        self.assertEqual(s.state, "sleeping")
        g.tick(10)
        self.assertEqual(s.state, "idle")
        self.assertGreaterEqual(s.needs.get("energy"), config.AUTO_WAKE_AT - 20)

    def test_auto_eat_uses_food(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        s.needs.set("food", 20)
        before = g.wallet.get("food")
        g.tick(1)
        self.assertEqual(g.wallet.get("food"), before - 1)

    def test_maslow_gating(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        s.needs.set("food", 5)
        g.needs.auto_care = False
        e = s.needs.get("esteem")
        g.tick(3)
        self.assertEqual(s.needs.get("esteem"), e)      # higher tier frozen while food unmet
        self.assertEqual(s.needs.dominant(), "food")

    def test_mood_drops_when_hungry(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        happy = s.power_multiplier()
        s.needs.set("food", 0)
        self.assertLess(s.power_multiplier(), happy)


class TestConflict(unittest.TestCase):
    def test_conflict_mediation(self):
        g = fresh(1, 2)
        a, b = g.slimes()
        from slime_gacha.ai import Conflict
        g.conflicts.conflicts.append(Conflict(1, a.id, b.id, 1, 0, "test"))
        g.wallet.add("food", 5)
        g.mediate(1, "snack")
        self.assertEqual(g.conflicts.conflicts, [])
        self.assertIn(frozenset((a.id, b.id)), g.conflicts.friends)

    def test_brawl_grounds(self):
        g = fresh(1, 2)
        a, b = g.slimes()
        from slime_gacha.ai import Conflict
        g.needs.auto_care = False
        g.conflicts.conflicts.append(Conflict(1, a.id, b.id, 3, config.CONFLICT_ESCALATE_TICKS - 1, "x"))
        g.conflicts.tick(g.slimes(), [])
        self.assertTrue(a.grounded and b.grounded)
        with self.assertRaises(InvalidAction):
            g.hunt(a.id, "meadow")


class TestHunt(unittest.TestCase):
    def test_hunt_completes_and_pays(self):
        g = fresh(4, 1)
        s = g.slimes()[0]
        g.needs.auto_care = False
        before = g.wallet.get("silver") + g.wallet.get("food")
        g.hunt(s.id, "meadow")
        self.assertEqual(s.state, "hunting")
        g.tick(3)
        self.assertEqual(s.state, "idle")
        self.assertGreater(g.wallet.get("silver") + g.wallet.get("food"), before)
        self.assertGreater(s.total_xp, 0)

    def test_cannot_hunt_when_exhausted(self):
        g = fresh(4, 1)
        s = g.slimes()[0]
        s.needs.set("energy", 5)
        with self.assertRaises(InvalidAction):
            g.hunt(s.id, "meadow")


class TestGrowth(unittest.TestCase):
    def test_levelling_and_cap(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        add_xp(s, 10 ** 6)
        self.assertEqual(s.level, s.level_cap)

    def test_evolve_requires_cap_and_essence(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        with self.assertRaises(InvalidAction):
            evolve(s, g.wallet)
        add_xp(s, 10 ** 6)
        with self.assertRaises(NotEnoughResources):
            evolve(s, g.wallet)
        g.wallet.add("essence", 500)
        hp = s.max_hp
        evolve(s, g.wallet)
        self.assertEqual(s.stage, 1)
        self.assertGreater(s.max_hp, hp)

    def test_merge_transfers_xp_percentage(self):
        g = fresh(1, 2)
        t, d = g.slimes()
        add_xp(d, 500)
        expect = merge_gain(t, d)
        self.assertGreaterEqual(expect, int(500 * config.MERGE_XP_RATIO))
        before = t.total_xp
        g.merge(t.id, d.id)
        self.assertEqual(t.total_xp - before, expect)
        self.assertNotIn(d.id, g.roster)
        with self.assertRaises(InvalidAction):
            g.merge(t.id, t.id)


class TestParty(unittest.TestCase):
    def test_size_must_be_multiple_of_five(self):
        for bad in (0, 3, 7, 12):
            with self.assertRaises(ValueError):
                Game(1, party_size=bad)
        self.assertEqual(Game(1, party_size=10).parties.size, 10)

    def test_party_rules_and_multiple_parties(self):
        g = fresh(1, 12)
        a, b = g.create_party("A"), g.create_party("B")
        ids = [s.id for s in g.slimes()]
        for i in ids[:5]:
            g.party_add(a.id, i)
        with self.assertRaises(InvalidAction):
            g.party_add(a.id, ids[5])            # full
        with self.assertRaises(InvalidAction):
            g.party_add(b.id, ids[0])            # already in A
        self.assertEqual(g.party_autofill(b.id), 5)
        self.assertEqual(len(g.parties.get(b.id).members), 5)
        self.assertFalse(set(a.members) & set(b.members))
        g.party_remove(ids[0])
        self.assertEqual(len(a.members), 4)

    def test_incomplete_party_cannot_fight(self):
        g = fresh(1, 5)
        p = g.create_party("short")
        g.party_add(p.id, g.slimes()[0].id)
        with self.assertRaises(InvalidAction):
            g.battle(p.id, 1)
        with self.assertRaises(InvalidAction):
            g.party_hunt(p.id, "meadow")

    def test_party_hunt(self):
        g = fresh(1, 5)
        p = g.create_party("h")
        g.party_autofill(p.id)
        g.party_hunt(p.id, "meadow")
        self.assertTrue(all(s.state == "hunting" for s in g.slimes()))


class TestBattle(unittest.TestCase):
    def test_battle_deterministic(self):
        def run():
            g = fresh(11)
            pid = full_party(g, xp=50, rarity="common")
            return g.battle(pid, 1).log
        self.assertEqual(run(), run())

    def test_boss_is_hard(self):
        g = fresh(11)
        pid = full_party(g, rarity="common", xp=0)
        rep = g.battle(pid, 4)
        self.assertIn(rep.winner, ("foes", None))

    def test_victory_pays_loot_and_xp(self):
        g = fresh(2)
        pid = full_party(g)
        silver = g.wallet.get("silver")
        rep = g.battle(pid, 1)
        self.assertTrue(rep.victory)
        self.assertGreaterEqual(g.wallet.get("silver"), silver)
        self.assertGreater(rep.xp, 0)

    def test_necromancer_summons(self):
        g = fresh(8)
        pid = full_party(g, "necromancer", "epic", 2000)
        rep = g.battle(pid, 1)
        self.assertTrue(any("Bone Pal" in l for l in rep.log))

    def test_gold_is_rare_in_dungeons(self):
        g = fresh(5)
        gold = 0
        for _ in range(300):
            e = g.battles.generate_enemies(1, 5)
            gold += sum(1 for x in e if g.rng.random() < x.gold_chance)
        self.assertLess(gold / (300 * 5), 0.03)
        # boss always drops gold
        from slime_gacha.battle import ENEMIES
        self.assertEqual(ENEMIES.get("parched_king").gold_chance, 1.0)


class TestDeath(unittest.TestCase):
    def test_fallen_in_battle_are_gone(self):
        g = fresh(11)
        pid = full_party(g, rarity="common", xp=0)
        for s in g.party_members(pid):
            s.hp = 1                              # near death: someone will not make it
        before = set(g.roster)
        rep = g.battle(pid, 2)
        self.assertTrue(rep.deaths)
        self.assertEqual(len(g.graveyard), len(rep.deaths))
        for d in g.graveyard:
            self.assertNotIn(d["id"], g.roster)
            self.assertNotIn(d["id"], g.parties.get(pid).members)
        self.assertEqual(len(g.roster), len(before) - len(rep.deaths))

    def test_starvation_kills(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        g.wallet.spend("food", g.wallet.get("food"))
        s.needs.set("food", 0)
        events = g.tick(60)
        self.assertEqual(len(g.roster), 0)
        self.assertEqual(g.graveyard[0]["cause"], "starvation")
        self.assertTrue(any("has died" in e for e in events))

    def test_hunt_can_kill(self):
        g = fresh(3, 1)
        s = g.slimes()[0]
        g.needs.auto_care = False
        g.hunt(s.id, "crust")
        s.hp = 1                                  # wounded mid-hunt: any injury is fatal
        g.tick(8)
        self.assertNotIn(s.id, g.roster)
        self.assertIn("killed hunting", g.graveyard[-1]["cause"])

    def test_cannot_hunt_when_badly_wounded(self):
        g = fresh(1, 1)
        s = g.slimes()[0]
        s.hp = 1
        with self.assertRaises(InvalidAction):
            g.hunt(s.id, "meadow")

    def test_death_grieves_friends_and_cleans_conflicts(self):
        g = fresh(1, 3)
        a, b, c = g.slimes()
        g.needs.auto_care = False
        g.conflicts.friends.add(frozenset((a.id, b.id)))
        from slime_gacha.ai import Conflict
        g.conflicts.conflicts.append(Conflict(1, a.id, c.id))
        a.hp, a.death_cause = 0, "test"
        b.needs.set("belonging", 80)
        c.needs.set("belonging", 80)
        g._reap([])
        self.assertEqual(g.conflicts.conflicts, [])
        self.assertLess(b.needs.get("belonging"), c.needs.get("belonging"))   # friend grieves more

    def test_dead_slime_cannot_be_acted_on(self):
        g = fresh(1, 1)
        sid = g.slimes()[0].id
        g.slimes()[0].hp = 0
        g._reap([])
        with self.assertRaises(InvalidAction):
            g.feed(sid)


class TestExtensibility(unittest.TestCase):
    def test_add_bard_class_without_touching_engine(self):
        register_ability(Ability("inspire", "Inspire", "heal", 0.5, "mag", "all_allies", 2))
        register_archetype(Archetype(
            "bard", "Bard", "🎵", dict(hp=20, atk=3, defense=3, mag=8, spd=6),
            dict(hp=3, atk=.5, defense=.5, mag=1.5, spd=.5), {1: "inspire"}, "heal"))
        try:
            g = fresh(1)
            s = g.gacha.make_slime("rare", "bard")
            g.roster[s.id] = s
            self.assertEqual(s.known_abilities(), ["inspire"])
            p = g.create_party("bards")
            for _ in range(5):
                x = g.gacha.make_slime("rare", "bard")
                g.roster[x.id] = x
                g.parties.add(p.id, x.id)
            g.battle(p.id, 1)                        # works in battle too
            seen = {x.archetype for x in fresh(1, 200).slimes()}
            self.assertIn("bard", seen)              # appears in the gacha pool
        finally:
            ARCHETYPES.unregister("bard")

    def test_bad_archetype_rejected(self):
        with self.assertRaises(ValueError):
            register_archetype(Archetype("bad", "Bad", "x", dict(hp=1), dict(hp=1), {}))


class TestPersistence(unittest.TestCase):
    def test_v1_save_migrates_gel_to_silver(self):
        d = Game(1).to_dict()
        d["wallet"] = {"gel": 77, "food": 3, "essence": 0}
        h = Game.from_dict(d)
        self.assertEqual(h.wallet.get("silver"), 77)

    def test_roundtrip(self):
        g = fresh(6, 5)
        p = g.create_party("P")
        g.party_autofill(p.id)
        g.hunt(g.slimes()[0].id, "grove")
        g.pull(1, "free")
        g.graveyard.append(dict(id=99, name="Old", archetype="mage", rarity="common", stars=1,
                                level=3, tick=2, cause="test"))
        g.tick(7)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            g.save(p)
            h = Game.load(p)
        self.assertEqual(g.to_dict()["slimes"], h.to_dict()["slimes"])
        self.assertEqual(g.wallet.to_dict(), h.wallet.to_dict())
        self.assertEqual(g.parties.to_dict(), h.parties.to_dict())
        self.assertEqual(g.graveyard, h.graveyard)
        self.assertEqual(g.gacha.last_free_day, h.gacha.last_free_day)
        g.tick(5)
        h.tick(5)                                    # RNG state restored -> same future
        self.assertEqual(g.to_dict()["slimes"], h.to_dict()["slimes"])


if __name__ == "__main__":
    unittest.main()
