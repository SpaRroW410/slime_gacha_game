"""Floor 1-50 content: bestiary, terrain, varied floors, bosses, and the daily Gloop Pit."""
import os
import random
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import bestiary, config, dungeon, elements, terrain
from slime_gacha.abilities import ABILITIES, get_ability
from slime_gacha.battle import BattleSystem, Enemy, _damage_value
from slime_gacha.errors import InvalidAction
from slime_gacha.game import Game
from slime_gacha.growth import add_xp

SEEDS = (1, 2, 3, 4, 5)


def rich(seed=1):
    g = Game(seed)
    for k in ("white_gel", "purple_gel", "essence", "food"):
        g.wallet.add(k, 20000)
    g.needs.auto_care = False
    return g


def mk_party(g, n=5, strong=False):
    p = g.create_party("P")
    for _ in range(n):
        s = g.gacha.make_slime("rare", "barbarian", stars=3)
        g.roster[s.id] = s
        if strong:
            s.stage = 2
            s.max_stats = lambda: {"hp": 9999.0, "atk": 9999.0, "defense": 500.0, "mag": 9999.0, "spd": 20.0}
        s.hp = s.max_hp
        g.parties.add(p.id, s.id)
    return p.id


class TestBestiary(unittest.TestCase):
    def test_a_big_varied_roster(self):
        ms = bestiary.MONSTERS.all()
        self.assertGreaterEqual(len(ms), 60)
        fams = {m.family for m in ms}
        self.assertGreaterEqual(len(fams), 15)
        for f in ("goblin", "direwolf", "orc", "ogre", "troll", "undead", "scarab", "sea", "golem", "aerial"):
            self.assertIn(f, fams)
        for m in ms:
            self.assertIn(m.role, bestiary.ROLES, m.key)
            self.assertLessEqual(m.lo, m.hi)
            for h in m.habitats:
                self.assertIn(h, terrain.KINDS, (m.key, h))
            for a in m.abilities:
                self.assertIn(a, ABILITIES, (m.key, a))
            if m.element:
                self.assertIn(m.element, elements.BASICS)

    def test_every_terrain_kind_has_monsters_at_every_depth(self):
        for kind in terrain.KINDS:
            for floor in range(1, 51, 7):
                self.assertTrue(bestiary.pool_for(kind, floor, None, 60), (kind, floor))

    def test_stats_come_from_the_floor_and_the_role(self):
        wolf = bestiary.MONSTERS.get("direwolf")
        hp = [bestiary.build_enemy(wolf, f).stats["hp"] for f in (1, 10, 20, 30, 50)]
        self.assertEqual(hp, sorted(hp))
        self.assertGreater(hp[-1], hp[0] * 10)
        f = 20
        tank, swarm = (bestiary.build_enemy(bestiary.MONSTERS.get(k), f) for k in ("ice_golem", "skeleton"))
        caster, brute = (bestiary.build_enemy(bestiary.MONSTERS.get(k), f) for k in ("frost_witch", "ogre_brute"))
        hunter = bestiary.build_enemy(wolf, f)
        self.assertGreater(tank.stats["hp"], swarm.stats["hp"] * 2)
        self.assertGreater(caster.stats["mag"], caster.stats["atk"] * 3)
        self.assertGreater(hunter.stats["spd"], brute.stats["spd"] * 2)
        self.assertGreater(brute.stats["atk"], hunter.stats["atk"])
        elite = bestiary.build_enemy(wolf, f, elite=1.25)
        self.assertGreater(elite.stats["hp"], hunter.stats["hp"])
        self.assertGreater(elite.xp, hunter.xp)

    def test_difficulty_follows_player_progression_with_stage_steps(self):
        c = bestiary.player_curve
        self.assertEqual(c(1), 1.0)
        self.assertGreater(c(11), c(10) * 1.4)              # evolving to stage 1
        self.assertGreater(c(31), c(30) * 1.3)              # evolving to stage 2
        self.assertEqual(bestiary.difficulty(1), 1.0)
        self.assertAlmostEqual(bestiary.difficulty(8), 1.65)
        self.assertEqual(bestiary.difficulty(30, pit=True), 1.0)

    def test_the_descent_gets_steadily_harder(self):
        def band(lo, hi):
            tot = [sum(e.stats["hp"] for e in dungeon.floor_plan(3, f, 5)) for f in range(lo, hi) if f % 5]
            return sum(tot) / len(tot)
        bands = [band(1 + 10 * i, 11 + 10 * i) for i in range(5)]
        self.assertEqual(bands, sorted(bands))

    def test_pit_enemies_are_gentler_and_never_drop_purple_gel(self):
        m = bestiary.MONSTERS.get("orc_grunt")
        main, pit = bestiary.build_enemy(m, 20), bestiary.build_enemy(m, 20, pit=True)
        self.assertLess(pit.stats["hp"], main.stats["hp"])
        self.assertEqual(pit.purple_chance, 0)
        self.assertGreater(main.purple_chance, 0)
        self.assertLessEqual(pit.loot["white_gel"][1], main.loot["white_gel"][1])

    def test_ten_unique_bosses_one_per_segment(self):
        self.assertEqual(sorted(bestiary.BOSSES), list(range(5, 55, 5)))
        self.assertEqual(len({b.key for b in bestiary.BOSSES.values()}), 10)
        self.assertEqual(bestiary.BOSSES[50].key, "parched_king")
        for fl, b in bestiary.BOSSES.items():
            e = bestiary.build_boss(b)
            self.assertTrue(e.boss)
            self.assertIn(b.terrain, terrain.TERRAINS.keys())
            self.assertTrue(all(a in ABILITIES for a in b.abilities), b.key)
            others = max(x.stats["hp"] for x in dungeon.floor_plan(1, fl, 5) if not x.boss)
            self.assertGreater(e.stats["hp"], others * 2)

    def test_summoners_name_their_minions(self):
        from slime_gacha.abilities import get_ability
        self.assertIn("Goblin Whelp", get_ability("summon_whelp").minion)
        g = rich()
        pid = mk_party(g)
        boss = bestiary.build_boss(bestiary.BOSSES[10])
        rep = g.battles.run(g.party_members(pid), [boss])
        self.assertTrue(any("Goblin Whelp" in l for l in rep.log))


class TestTerrain(unittest.TestCase):
    def test_catalogue(self):
        ts = terrain.TERRAINS.all()
        self.assertGreaterEqual(len(ts), 25)
        self.assertEqual({t.kind for t in ts}, set(terrain.KINDS))
        names = " ".join(t.name for t in ts)
        for w in ("Valley", "Dune", "Isles", "Tundra", "Ashlands", "Canyon", "Cliffs", "Crypt"):
            self.assertIn(w, names)

    def test_element_factors(self):
        ash, storm, plain = terrain.get("ashlands"), terrain.get("storm_plains"), terrain.get("hollow_halls")
        self.assertAlmostEqual(terrain.element_factor(ash, "fire"), 1.2)
        self.assertAlmostEqual(terrain.element_factor(ash, "water"), 0.75)
        self.assertAlmostEqual(terrain.element_factor(storm, "lightning"), 1.25)
        self.assertAlmostEqual(terrain.element_factor(ash, "steam"), 0.9)        # best x worst component
        self.assertEqual(terrain.element_factor(ash, ""), 1.0)
        self.assertEqual(terrain.element_factor(None, "fire"), 1.0)
        self.assertEqual(terrain.element_factor(plain, "fire"), 1.0)
        self.assertIn("Fire +20%", terrain.describe(ash))
        self.assertEqual(terrain.describe(plain), "no special effects")

    def _fight(self, terr, caster_el="fire", seed=1):
        g = rich(seed)
        s = g.gacha.make_slime("rare", "mage", stars=3)
        g.roster[s.id] = s
        s.attuned = [caster_el]
        s.mastery_xp[caster_el] = 130
        spell = {"fire": "ember", "water": "water_jet"}[caster_el]
        s.spells = [spell]
        s.known_abilities = lambda: [spell]
        s.hp = s.max_hp
        foe = Enemy("dummy", "Dummy", "🎯", 1, dict(hp=5000, atk=0, defense=0, mag=0, spd=1), ["splat"], 1, {})
        rep = BattleSystem(random.Random(seed)).run([s], [foe], terrain=terr)
        dmg = [int(l.split(": ")[1].split(" dmg")[0]) for l in rep.log if "dmg" in l and get_ability(spell).name in l]
        return sum(dmg) / len(dmg), rep

    def test_terrain_boosts_and_dampens_spells_for_everyone(self):
        base, _ = self._fight(None)
        up, rep = self._fight(terrain.get("magma_shelf"))                # fire +25%
        down, _ = self._fight(terrain.get("glacier_hall"))               # fire -25%
        self.assertGreater(up, base * 1.1)
        self.assertLess(down, base * 0.9)
        self.assertTrue(any("Magma Shelf" in l for l in rep.log))        # announced at the start

    def test_hazard_hurts_the_unprepared_and_spares_the_immune(self):
        t = terrain.get("dune_sea")                                       # 2%/round, immune fire/earth
        g = rich(2)
        a = g.gacha.make_slime("rare", "barbarian", stars=3)
        b = g.gacha.make_slime("rare", "barbarian", stars=3)
        for s in (a, b):
            g.roster[s.id] = s
        b.attuned, b.mastery_xp = ["fire"], {"fire": 130}
        foes = [Enemy("t", "Totem", "🗿", 1, dict(hp=300, atk=0, defense=0, mag=0, spd=1), ["splat"], 1, {}),
                Enemy("sc", "Scarab", "🪲", 1, dict(hp=300, atk=0, defense=0, mag=0, spd=1), ["splat"], 1, {}, element="earth")]
        for s in (a, b):
            s.known_abilities = lambda: ["splat"]
            s.hp = s.max_hp
        hp = {s.id: s.hp for s in (a, b)}
        rep = BattleSystem(random.Random(1)).run([a, b], foes, terrain=t)
        self.assertGreater(rep.rounds, 2)
        log = "\n".join(rep.log)
        self.assertIn("scorching heat", log)
        self.assertLess(a.hp, hp[a.id])                                   # unprepared: hurt
        hazard_lines = [l for l in rep.log if "scorching heat (party)" in l]
        self.assertTrue(all(b.name not in l for l in hazard_lines))      # fire-attuned: immune
        self.assertTrue(any(a.name in l for l in hazard_lines))
        self.assertTrue(any("Totem" in l for l in rep.log if "(foes)" in l))      # monsters suffer too
        self.assertFalse(any("Scarab -" in l for l in rep.log))                 # native earth monster: immune

    def test_crit_bonus_applies(self):
        class FakeBS:
            rng = random.Random(1)
            terrain = terrain.get("crystal_canyon")                       # crit +8%
        actor = BattleSystem.from_slime(rich().gacha.make_slime("common", "barbarian"))
        target = BattleSystem.from_enemy(Enemy("d", "D", "x", 1, dict(hp=99, atk=0, defense=0, mag=0, spd=1), ["splat"], 1, {}))
        crits = lambda bs: sum(_damage_value(bs, actor, get_ability("splat"), target)[1] for _ in range(4000))
        plain = type("P", (), {"rng": random.Random(1), "terrain": None})
        self.assertGreater(crits(FakeBS), crits(plain) + 100)

    def test_duels_ignore_terrain(self):
        g = rich()
        a, b = (g.gacha.make_slime("common", "barbarian") for _ in range(2))
        for s in (a, b):
            g.roster[s.id] = s
        bs = BattleSystem(random.Random(1))
        bs.terrain = terrain.get("magma_shelf")
        rep = bs.duel(a, b)
        self.assertFalse(any("Magma Shelf" in l or "radiant heat" in l for l in rep.log))


class TestFloors(unittest.TestCase):
    def test_floors_are_deterministic_and_seed_dependent(self):
        a = [dungeon.floor_info(1, f, 5).signature for f in range(1, 51)]
        b = [dungeon.floor_info(1, f, 5).signature for f in range(1, 51)]
        c = [dungeon.floor_info(2, f, 5).signature for f in range(1, 51)]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_no_floor_repeats_and_terrain_never_repeats_back_to_back(self):
        for seed in SEEDS:
            plans = [dungeon.floor_info(seed, f, 5) for f in range(1, 51)]
            self.assertEqual(len({p.signature for p in plans}), 50, seed)
            for a, b in zip(plans, plans[1:]):
                self.assertNotEqual(a.terrain.key, b.terrain.key, (seed, a.floor))
            for p in plans:                                              # the same wave never returns within 4 floors
                near = [q.signature for q in plans if 0 < p.floor - q.floor <= 4]
                self.assertNotIn(p.signature, near)

    def test_lots_of_different_ground_and_monsters(self):
        for seed in SEEDS:
            plans = [dungeon.floor_info(seed, f, 5) for f in range(1, 51)]
            self.assertGreaterEqual(len({p.terrain.key for p in plans}), 20, seed)
            self.assertGreaterEqual(len({p.terrain.kind for p in plans}), 11, seed)
            self.assertGreaterEqual(len({e.key for p in plans for e in p.enemies}), 55, seed)

    def test_waves_mix_families(self):
        for seed in SEEDS:
            plans = [p for p in (dungeon.floor_info(seed, f, 5) for f in range(1, 51)) if not p.boss]
            mixed = sum(len({e.family for e in p.enemies}) >= 2 for p in plans)
            self.assertGreaterEqual(mixed / len(plans), 0.6, seed)
        # goblins ride with direwolves, orcs march with ogres
        gw = og = 0
        for seed in range(1, 16):
            for f in range(1, 51):
                fams = {e.family for e in dungeon.floor_plan(seed, f, 5)}
                gw += {"goblin", "direwolf"} <= fams
                og += {"orc", "ogre"} <= fams
        self.assertGreater(gw, 0)
        self.assertGreater(og, 0)

    def test_segment_themes_shape_the_terrain(self):
        for seed in SEEDS:
            for f in range(1, 51):
                p = dungeon.floor_info(seed, f, 5)
                if not p.boss:
                    self.assertIn(p.terrain.key, dungeon.SEGMENT_TERRAINS[dungeon.segment_of(f)])
        early = {dungeon.floor_info(1, f, 5).terrain.kind for f in range(1, 11) if not dungeon.is_boss_floor(f)}
        self.assertTrue(early <= {"valley", "caverns", "dunes"})
        late = {dungeon.floor_info(1, f, 5).terrain.kind for f in range(46, 51) if not dungeon.is_boss_floor(f)}
        self.assertTrue(late <= {"volcano", "ruins", "barrens"})

    def test_boss_floors_are_lairs(self):
        for f, b in bestiary.BOSSES.items():
            p = dungeon.floor_info(1, f, 5)
            self.assertTrue(p.boss and p.enemies[0].boss and p.enemies[0].key == b.key)
            self.assertEqual(p.terrain.key, b.terrain)
            self.assertEqual(len(p.enemies), 3)
            self.assertIn("lair", p.title)
            esc = {e.family for e in p.enemies[1:]}
            self.assertTrue(esc, f)

    def test_party_size_scales_waves(self):
        self.assertEqual(len(dungeon.floor_plan(1, 3, 10)), 10)
        self.assertEqual(len(dungeon.floor_plan(1, 5, 10)), 5)           # boss + 4 escorts
        self.assertEqual(len(dungeon.floor_plan(1, 3, 15)), 15)

    def test_nothing_below_floor_50(self):
        with self.assertRaises(ValueError):
            dungeon.floor_info(1, 51, 5)
        g = rich()
        pid = mk_party(g, strong=True)
        for s in g.party_members(pid):
            s.progress = 50
        self.assertNotIn(51, g.entry_options(pid))
        self.assertEqual(g.entry_options(pid)[-1], 46)
        g.enter_dungeon(pid, 46)
        g.delves[pid]["floor"] = 51
        with self.assertRaises(InvalidAction):
            g.delve_next(pid)

    def test_clearing_the_final_boss_ends_the_descent(self):
        g = rich(3)
        pid = mk_party(g, strong=True)
        for s in g.party_members(pid):
            s.progress = 45
        g.enter_dungeon(pid, 46)
        for _ in range(5):
            rep = g.delve_next(pid)
            self.assertTrue(rep.victory, rep.log[-5:])
        self.assertTrue(g.descent_cleared)
        self.assertEqual(g.best_floor, 50)
        self.assertTrue(any("PARCHED KING FALLS" in l for l in rep.log))
        self.assertTrue(g.can_leave(pid))
        with self.assertRaises(InvalidAction):
            g.delve_next(pid)
        g.leave_dungeon(pid)
        self.assertTrue(Game.from_dict(g.to_dict()).descent_cleared)

    def test_fight_reports_the_terrain_and_floor_title(self):
        g = rich()
        pid = mk_party(g, strong=True)
        g.enter_dungeon(pid)
        rep = g.delve_next(pid)
        info = dungeon.floor_info(g.dungeon_seed, 1, 5)
        self.assertIn(info.title, rep.log[0])
        self.assertTrue(any(info.terrain.name in l for l in rep.log))

    def test_intel_shows_terrain_early_and_advice_at_100(self):
        l20 = dungeon.intel_lines(1, 7, 25, 5)
        self.assertTrue(l20[0].startswith(dungeon.floor_info(1, 7, 5).terrain.emoji))
        l100 = dungeon.intel_lines(1, 7, 100, 5)
        self.assertTrue(any("weakness" in l for l in l100))
        rows = dungeon.intel_view(1, range(1, 4), {1: 100}, 5)
        self.assertEqual(rows[0]["terrain"]["key"], dungeon.floor_info(1, 1, 5).terrain.key)
        self.assertIsNone(rows[1]["terrain"])                             # unknown until scouted

    def test_scouting_range_and_deep_budgets(self):
        g = rich()
        pid = mk_party(g, strong=True)
        for s in g.party_members(pid):
            s.progress = 49
        with self.assertRaises(InvalidAction):
            g.scout(pid, 50, 51, 20)
        est = g.scout_plan(pid, 41, 50)
        self.assertLess(est["safe"], config.SCOUT_MAX_HOURS)
        self.assertGreater(g.scout_plan(pid, 50, 50)["nominal"], g.scout_plan(pid, 1, 1)["nominal"] * 2)


class TestDailyPit(unittest.TestCase):
    def test_theme_is_stable_within_a_day_and_changes_between_days(self):
        for seed in SEEDS:
            themes = [dungeon.pit_theme(seed, d) for d in range(40)]
            self.assertEqual(themes[7].title, dungeon.pit_theme(seed, 7).title)
            for a, b in zip(themes, themes[1:]):
                self.assertNotEqual(a.terrain.key, b.terrain.key)
                self.assertNotEqual(set(a.families), set(b.families))
            self.assertGreaterEqual(len({t.terrain.key for t in themes}), 15)
            self.assertGreaterEqual(len({f for t in themes for f in t.families}), 12)
        self.assertNotEqual([dungeon.pit_theme(1, d).title for d in range(10)],
                            [dungeon.pit_theme(2, d).title for d in range(10)])

    def test_each_run_draws_a_different_mix(self):
        th = dungeon.pit_theme(1, 3)
        sigs = set()
        for i in range(12):
            wave = dungeon.grind_wave(14, 3, 5, random.Random(100 + i), th)
            self.assertEqual(len(wave), 5)
            sigs.add(tuple(sorted(Counter(e.key for e in wave).items())))
        self.assertGreaterEqual(len(sigs), 6)

    def test_the_days_families_feature(self):
        for day in range(8):
            th = dungeon.pit_theme(2, day)
            share = []
            for i in range(10):
                wave = dungeon.grind_wave(18, 3, 5, random.Random(i), th)
                share.append(sum(e.family in th.families for e in wave) / 5)
            self.assertGreater(sum(share) / len(share), 0.45, th.title)

    def test_grind_wave_still_scales_and_never_drops_purple(self):
        th = dungeon.pit_theme(1, 0)
        for depth in range(1, 6):
            self.assertTrue(all(e.purple_chance == 0 for e in dungeon.grind_wave(10, depth, 5, random.Random(1), th)))
        lo = sum(e.stats["hp"] for e in dungeon.grind_wave(8, 1, 5, random.Random(1), th))
        hi = sum(e.stats["hp"] for e in dungeon.grind_wave(8, 5, 5, random.Random(1), th))
        self.assertLess(lo, hi)

    def test_a_grind_session_reports_todays_pit_and_the_day_rolls_over(self):
        g = rich(5)
        pid = mk_party(g, strong=True)
        for s in g.party_members(pid):
            s.level, s.xp, s.total_xp = 3, 0, 0
        g.conflicts.tick = lambda *a: None
        r1 = g.grind(pid, 2, 2)
        self.assertTrue(any("Today's Pit (day 1)" in l for l in r1.summary))
        theme0 = dungeon.pit_theme(g.dungeon_seed, 0)
        self.assertTrue(any(theme0.terrain.name in l for l in r1.runs[0].log))
        g.tick(24)
        for s in g.party_members(pid):
            s.state, s.hp = "idle", s.max_hp
        r2 = g.grind(pid, 2, 1)
        self.assertTrue(any("Today's Pit (day 2)" in l for l in r2.summary))
        self.assertNotEqual(theme0.title, dungeon.pit_theme(g.dungeon_seed, 1).title)

    def test_web_snapshot_has_floor_terrain_and_pit(self):
        from slime_gacha.webapi import Session
        s = Session()
        s.call("new_game", {"seed": 3})
        st = s.call("state")["state"]["dungeon"]
        self.assertEqual(st["max_floor"], 50)
        self.assertIn("title", st["pit"])
        self.assertTrue(st["pit"]["terrain"]["effects"])
        before = st["pit"]["title"]
        after = s.call("wait", {"hours": 24})["state"]["dungeon"]["pit"]["title"]
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()


class TestFloorThreatSmoothing(unittest.TestCase):
    def test_every_floor_stays_inside_its_threat_band_for_any_seed_and_party_size(self):
        from slime_gacha import config, dungeon
        for seed in (1, 2, 3, 4, 5, 17, 99):
            for size in (5, 10):
                for f in range(1, dungeon.MAX_FLOOR + 1):
                    info = dungeon.floor_info(seed, f, size)
                    lo, hi = config.BOSS_THREAT_BAND if info.boss else config.FLOOR_THREAT_BAND
                    r = dungeon.threat_ratio(info.enemies, f, size)
                    self.assertTrue(lo * 0.97 <= r <= hi * 1.03, (seed, size, f, round(r, 2)))

    def test_smoothing_keeps_the_enemy_mix_and_only_rescales_stats(self):
        from slime_gacha import dungeon
        i = dungeon.floor_info(7, 32, 5)
        self.assertEqual(len(i.enemies), 5)
        self.assertTrue(all(e.stats["hp"] >= 1 for e in i.enemies))
        self.assertEqual(dungeon.floor_info(7, 32, 5).signature, i.signature)
