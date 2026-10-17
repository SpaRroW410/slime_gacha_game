import unittest

from slime_gacha import config, dungeon
from slime_gacha.errors import InvalidAction
from slime_gacha.game import Game


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, real_hours):
        self.t += real_hours * 3600


def mk(seed=3, n=8, live=False, scale=1):
    g = Game(seed)
    g.wallet.add_many({"white_gel": 100000, "food": 800, "essence": 500})
    g.pull(n, "white_gel")
    for s in g.slimes():
        s.level = 8
        s.hp = s.max_hp
    g.conflicts.tick = lambda *a, **k: None
    g.clock = Clock()
    g.clock_fn = g.clock
    if live:
        g.set_time_mode("live", scale)
    return g


def party(g):
    p = g.create_party("A")
    g.party_autofill(p.id)
    return p.id


class TestNoCareInDungeons(unittest.TestCase):
    def setUp(self):
        self.g = mk()
        self.pid = party(self.g)
        self.g.enter_dungeon(self.pid)
        self.s = self.g.party_members(self.pid)[0]

    def test_everything_gentle_is_refused_inside(self):
        g, s = self.g, self.s
        g.potions["might:1"] = 1
        for call in (lambda: g.feed(s.id), lambda: g.pet(s.id), lambda: g.sleep(s.id), lambda: g.wake(s.id),
                     lambda: g.talk(s.id), lambda: g.use_potion(s.id, "might", 1), lambda: g.rest(s.id)):
            with self.assertRaises(InvalidAction):
                call()

    def test_it_works_again_outside(self):
        g = self.g
        for pid in list(g.delves):
            g._clear_flag(g._members_in("main", pid))
            del g.delves[pid]
        self.assertIn("nibbles", g.feed(self.s.id))
        self.assertIn("pet", g.pet(self.s.id))

    def test_other_slimes_are_unaffected(self):
        home = next(s for s in self.g.slimes() if not s.in_dungeon)
        self.g.pet(home.id)

    def test_every_session_kind_counts(self):
        g = mk()
        s = g.slimes()[0]
        for kind in ("grind", "scout", "adventure", "quarry"):
            s.in_dungeon = kind
            with self.assertRaises(InvalidAction):
                g.pet(s.id)
        s.in_dungeon = "lab"                         # brewing at home is not a dungeon
        g.pet(s.id)


class TestClearTime(unittest.TestCase):
    def test_deeper_takes_longer(self):
        self.assertLess(dungeon.clear_hours(5, 5), dungeon.clear_hours(45, 45))

    def test_stronger_parties_are_faster_and_weaker_slower(self):
        base = dungeon.clear_hours(40, 40)
        self.assertLess(dungeon.clear_hours(40, 80), base)
        self.assertGreater(dungeon.clear_hours(40, 16), base)

    def test_knowledge_helps(self):
        self.assertLess(dungeon.clear_hours(40, 40, 100), dungeon.clear_hours(40, 40, 0))
        self.assertLessEqual(dungeon.clear_hours(40, 40, 100), round(dungeon.clear_hours(40, 40, 0) * 0.7))

    def test_party_size_and_minimum(self):
        self.assertGreater(dungeon.clear_hours(50, 50, 0, 15), dungeon.clear_hours(50, 50, 0, 5))
        self.assertGreaterEqual(dungeon.clear_hours(1, 100, 100), 1)

    def test_a_floor_costs_game_time_in_turn_mode(self):
        g = mk()
        pid = party(g)
        g.enter_dungeon(pid)
        t = g.tick_count
        g.delve_next(pid)
        self.assertEqual(g.tick_count - t, g.delves[pid]["hours"] if pid in g.delves else g.tick_count - t)
        self.assertGreaterEqual(g.tick_count - t, 1)


class TestLiveTime(unittest.TestCase):
    def test_nothing_moves_without_real_time(self):
        g = mk(live=True)
        t = g.tick_count
        g.sync()
        self.assertEqual(g.tick_count, t)

    def test_lobby_runs_at_one_game_hour_per_real_hour(self):
        g = mk(live=True)
        g.clock.advance(5)
        g.sync()
        self.assertEqual(g.tick_count, 5)

    def test_speed_presets(self):
        g = mk(live=True, scale=60)
        g.clock.advance(0.5)                          # 30 real minutes
        g.sync()
        self.assertEqual(g.tick_count, 30)
        with self.assertRaises(InvalidAction):
            g.set_time_mode("live", 7)

    def test_dungeon_clock_is_three_times_faster(self):
        g = mk(live=True)
        pid = party(g)
        g.enter_dungeon(pid)
        self.assertEqual(g.clock_rate(), config.LIVE_DUNGEON_RATE)
        g.clock.advance(2)
        g.sync()
        self.assertEqual(g.tick_count, 6)
        self.assertGreater(g.clock_rate(), config.LIVE_LOBBY_RATE)

    def test_fractions_accumulate(self):
        g = mk(live=True)
        for _ in range(6):
            g.clock.advance(1 / 6)
            g.sync()
        self.assertEqual(g.tick_count, 1)

    def test_offline_progress_is_capped(self):
        g = mk(live=True)
        g.clock.advance(24 * 30)
        g.sync()
        self.assertEqual(g.tick_count, config.LIVE_CATCHUP_MAX_HOURS)

    def test_a_floor_keeps_the_party_busy_without_moving_the_colony(self):
        g = mk(live=True)
        pid = party(g)
        g.enter_dungeon(pid)
        t = g.tick_count
        rep = g.delve_next(pid)
        self.assertEqual(g.tick_count, t)                       # the colony did not jump forward
        if pid in g.delves:
            with self.assertRaises(InvalidAction) as cm:
                g.delve_next(pid)
            self.assertIn("busy", str(cm.exception))
            need = g.delves[pid]["ready_tick"] - g.tick_count
            self.assertGreaterEqual(need, 1)
            g.clock.advance(need / config.LIVE_DUNGEON_RATE + 0.01)
            g.sync()
            self.assertGreaterEqual(g.tick_count, g.delves[pid]["ready_tick"])
            g.delve_next(pid)

    def test_pit_session_returns_on_the_wall_clock(self):
        g = mk(live=True)
        for s in g.slimes():
            s.archetype, s.level, s.stage = "barbarian", 40, 2     # a fighting party (pulled slimes may be all healers)
            s.hp = s.max_hp
        pid = party(g)
        g.wallet.add("food", 500)
        t = g.tick_count
        g.grind(pid, 3, 4)
        self.assertEqual(g.tick_count, t)
        away = g.party_members(pid)
        self.assertTrue(all(s.in_dungeon == "grind" for s in away if s.id in g.roster))
        self.assertEqual(len(g.expeditions), 1)
        hours = g.expeditions[0]["until"] - g.tick_count
        self.assertGreaterEqual(hours, 4 * config.GRIND_TICKS - 1)
        with self.assertRaises(InvalidAction):
            g.pet(away[0].id)
        g.clock.advance(hours / config.LIVE_DUNGEON_RATE + 0.05)
        events = g.sync()
        self.assertEqual(g.expeditions, [])
        self.assertTrue(all(s.in_dungeon == "" for s in g.slimes()))
        self.assertTrue(any("return" in e for e in events))

    def test_rift_and_quarry_too(self):
        for call in ("adventure", "quarry"):
            g = mk(live=True)
            for s in g.slimes():
                s.level, s.stage = 40, 2
                s.hp = s.max_hp
            ids = [s.id for s in g.slimes()[:3]]
            getattr(g, call)(ids, 3)
            self.assertEqual(len(g.expeditions), 1, call)

    def test_study_takes_wall_clock_time(self):
        g = mk(live=True)
        s = g.gacha.make_slime("common", "mage", 3)
        g.roster[s.id] = s
        g.wallet.add_many({"white_gel": 500, "essence": 100})
        g.study(s.id, "fire")
        left = s.task["ticks_left"] if s.task else 0
        self.assertGreater(left, 0)
        g.clock.advance(1)
        g.sync()
        self.assertEqual((s.task or {}).get("ticks_left", 0), left - 1)

    def test_brewing_occupies_the_brewer_in_real_time(self):
        g = mk(live=True)
        g.wallet.add_many({"herb_green": 50, "herb_red": 50, "herb_blue": 50, "herb_yellow": 50})
        s = g.slimes()[0]
        t = g.tick_count
        g.brew(s.id, "stamina", 1)
        self.assertEqual(g.tick_count, t)
        self.assertEqual(s.in_dungeon, "lab")
        g.clock.advance(3)
        g.sync()
        self.assertEqual(s.in_dungeon, "")

    def test_scouting_in_live_mode(self):
        g = mk(live=True)
        pid = party(g)
        t = g.tick_count
        res = g.scout(pid, 1, 1, 12)
        self.assertEqual(g.tick_count, t)
        if res.complete:
            self.assertEqual(len(g.expeditions), 1)

    def test_back_to_turn_mode_brings_everyone_home(self):
        g = mk(live=True)
        pid = party(g)
        g.grind(pid, 3, 2)
        g.set_time_mode("turn")
        self.assertEqual(g.expeditions, [])
        self.assertTrue(all(s.in_dungeon == "" for s in g.slimes()))

    def test_persistence(self):
        g = mk(live=True, scale=6)
        pid = party(g)
        g.grind(pid, 3, 2)
        h = Game.from_dict(g.to_dict())
        self.assertEqual((h.time_mode, h.time_scale), ("live", 6.0))
        self.assertEqual(h.expeditions, g.expeditions)
        self.assertEqual(h.wall_last, g.wall_last)

    def test_turn_mode_is_unchanged(self):
        g = mk()
        self.assertEqual(g.sync(), [])
        self.assertEqual(g.time_mode, "turn")
        self.assertIsNone(g.wall_last)


class TestApi(unittest.TestCase):
    def test_wait_is_refused_in_live_mode_and_clock_is_exposed(self):
        from slime_gacha.webapi import Session
        s = Session()
        s.call("new_game", {"seed": 4})
        r = s.call("set_time", {"mode": "live", "scale": 6})
        self.assertTrue(r["ok"])
        self.assertEqual(r["state"]["clock"]["mode"], "live")
        self.assertEqual(r["state"]["clock"]["dungeon_rate"], 18.0)
        self.assertFalse(s.call("wait", {"hours": 2})["ok"])
        self.assertTrue(s.call("sync")["ok"])
        s.call("set_time", {"mode": "turn"})
        self.assertTrue(s.call("wait", {"hours": 2})["ok"])


if __name__ == "__main__":
    unittest.main()
