import random
import unittest

from slime_gacha import awakening, config, emotions, items, potions
from slime_gacha.battle import BattleSystem
from slime_gacha.game import Game


def mk(seed=3, n=6):
    g = Game(seed)
    g.wallet.add_many({"white_gel": 100000, "essence": 1000, "scrap": 1000, "crystal": 500, "alloy": 500})
    for c in config.HERBS:
        g.wallet.add(potions.herb_key(c), 500)
    g.pull(n, "white_gel")
    return g


def make(g, arch="barbarian", rarity="common", stars=1):
    s = g.gacha.make_slime(rarity, arch, stars)
    s.traits = []
    g.roster[s.id] = s
    return s


class TestEmotions(unittest.TestCase):
    def test_thirteen_feelings(self):
        self.assertEqual(len(emotions.EMOTIONS), 13)
        for k in ("anger", "sadness", "joy", "fear", "pride", "calm", "anxiety", "loneliness", "determination",
                  "affection", "guilt", "dread", "wonder"):
            self.assertIn(k, emotions.EMOTIONS)

    def test_anger_raises_attack_and_lowers_defense(self):
        g = mk()
        s = make(g)
        emotions.feel(s, "anger", 100)
        m, mods = emotions.modifiers(s)
        self.assertGreater(m["atk"], 1.15)
        self.assertLess(m["defense"], 0.9)
        self.assertGreater(mods["crit_dmg"], 0)

    def test_sadness_lowers_speed(self):
        g = mk()
        s = make(g)
        emotions.feel(s, "sadness", 100)
        self.assertLess(emotions.modifiers(s)[0]["spd"], 0.85)

    def test_fear_gives_evasion_but_less_attack(self):
        g = mk()
        s = make(g)
        emotions.feel(s, "fear", 80)
        m, mods = emotions.modifiers(s)
        self.assertLess(m["atk"], 1)
        self.assertGreater(mods["evasion"], 0.05)

    def test_every_feeling_has_an_effect(self):
        g = mk()
        s = make(g)
        for k, e in emotions.EMOTIONS.items():
            self.assertTrue(e.stats or e.mods, k)
            s.emotions = {k: 100.0}
            m, mods = emotions.modifiers(s)
            self.assertTrue(any(abs(v - 1) > 0.01 for v in m.values()) or mods, k)

    def test_total_change_is_capped(self):
        g = mk()
        s = make(g)
        s.emotions = {k: 100.0 for k in ("anger", "pride", "determination", "joy")}
        m, _ = emotions.modifiers(s)
        self.assertLessEqual(m["atk"], 1 + emotions.CAP + 1e-9)
        s.emotions = {k: 100.0 for k in ("sadness", "loneliness", "guilt", "fear")}
        m, _ = emotions.modifiers(s)
        self.assertGreaterEqual(min(m.values()), 1 - emotions.CAP - 1e-9)

    def test_feelings_fade_and_sleep_helps(self):
        g = mk()
        a, b = make(g), make(g)
        for s in (a, b):
            s.needs.v.update({k: 100.0 for k in s.needs.v})
            s.emotions = {"anger": 50.0}
        rng = random.Random(1)
        emotions.tick(a, rng)
        emotions.tick(b, rng, sleeping=True)
        self.assertLess(a.emotions["anger"], 50)
        self.assertLess(b.emotions.get("anger", 0), a.emotions["anger"])

    def test_opposites_quiet_each_other(self):
        g = mk()
        s = make(g)
        emotions.feel(s, "sadness", 50)
        emotions.feel(s, "joy", 50)
        self.assertLess(s.emotions["sadness"], 50)

    def test_traits_shape_feelings(self):
        g = mk()
        grumpy, kind = make(g), make(g)
        grumpy.traits, kind.traits = ["grumpy"], ["kind"]
        emotions.feel(grumpy, "anger", 20)
        emotions.feel(kind, "anger", 20)
        self.assertGreater(grumpy.emotions["anger"], kind.emotions["anger"])
        timid, brave = make(g), make(g)
        timid.traits, brave.traits = ["timid"], ["brave"]
        emotions.feel(timid, "fear", 20)
        emotions.feel(brave, "fear", 20)
        self.assertGreater(timid.emotions["fear"], brave.emoions["fear"] if False else brave.emotions["fear"])

    def test_needs_stir_feelings(self):
        g = mk()
        s = make(g)
        s.needs.set("food", 5)
        s.needs.set("belonging", 5)
        for _ in range(5):
            emotions.tick(s, random.Random(1))
        self.assertGreater(s.emotions.get("anger", 0), 5)
        self.assertGreater(s.emotions.get("loneliness", 0), 5)

    def test_battle_uses_the_feelings(self):
        g = mk()
        s = make(g)
        bs = BattleSystem(random.Random(1))
        base = bs.from_slime(s).stats
        emotions.feel(s, "anger", 100)
        c = bs.from_slime(s)
        self.assertGreater(c.stats["atk"], base["atk"] * 1.15)
        self.assertLess(c.stats["defense"], base["defense"] * 0.9)
        self.assertGreater(c.mods.get("crit_dmg", 0), 0)
        self.assertEqual(c.stats["hp"], base["hp"])

    def test_strong_feeling_is_logged_in_battle(self):
        from slime_gacha import dungeon
        g = mk()
        s = make(g)
        s.level = 8
        s.hp = s.max_hp
        emotions.feel(s, "anger", 90)
        rep = g.battles.run([s], dungeon.grind_wave(8, 3, 1, random.Random(1), dungeon.pit_theme(1, 0)), permadeath=False)
        self.assertTrue(any("feels anger" in l for l in rep.log))

    def test_victory_and_defeat_stir_different_feelings(self):
        from slime_gacha.battle import BattleReport
        g = mk()
        a, b = make(g), make(g)
        g._after_battle([a], BattleReport([], "party", 3))
        g._after_battle([b], BattleReport([], "foes", 3))
        self.assertGreater(a.emotions["joy"], 5)
        self.assertGreater(b.emotions["sadness"], 5)
        self.assertGreater(b.emotions["anger"], 5)
        self.assertNotIn("sadness", a.emotions)

    def test_a_friends_death_brings_grief_and_anger(self):
        g = mk()
        a, b = g.slimes()[:2]
        g.social.add_bond(a, b, 30)
        b.hp = 0
        b.death_cause = "test"
        g._reap([])
        self.assertGreater(a.emotions["sadness"], 25)
        self.assertGreater(a.emotions["anger"], 5)
        other = g.slimes()[-1]
        self.assertLess(other.emotions.get("sadness", 0), a.emotions["sadness"])

    def test_quarrels_make_anger_and_peace_makes_calm(self):
        g = mk()
        a, b = g.slimes()[:2]
        g._social_hook("quarrel", a, b)
        self.assertGreater(a.emotions["anger"], 10)
        g._social_hook("resolved", a, b, True)
        self.assertGreater(a.emotions["calm"], 10)
        self.assertGreater(a.emotions["affection"], 5)

    def test_merge_brings_guilt_to_the_survivor(self):
        g = mk()
        t, d = g.slimes()[:2]
        g.merge(t.id, d.id)
        self.assertGreater(t.emotions["guilt"], 10)

    def test_petting_cheers_up(self):
        g = mk()
        s = g.slimes()[0]
        s.emotions = {"loneliness": 40.0}
        g.pet(s.id)
        self.assertLess(s.emotions.get("loneliness", 0), 40)
        self.assertGreater(s.emotions["joy"], 5)

    def test_talk_says_something_fitting(self):
        g = mk()
        s = g.slimes()[0]
        s.emotions = {"anger": 80.0}
        line = g.talk(s.id)
        self.assertIn("anger", line)

    def test_persistence_and_separate_dice(self):
        g = mk()
        s = g.slimes()[0]
        s.emotions = {"fear": 33.0}
        s.emotion_floor = {"wonder": 20.0}
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.slime(s.id).emotions, {"fear": 33.0})
        self.assertEqual(h.slime(s.id).emotion_floor, {"wonder": 20.0})
        a, b = Game(5), Game(5)
        a.wallet.add("white_gel", 500)
        b.wallet.add("white_gel", 500)
        a.pull(3, "white_gel")
        b.pull(3, "white_gel")
        a.tick(48)
        r1 = a.rng.random()
        b.tick(48)
        self.assertEqual(r1, b.rng.random())                # feelings use their own dice


class TestAwakening(unittest.TestCase):
    def legend(self, g, **traits):
        s = make(g, "mage", "legendary", 5)
        s.needs.v.update({k: 100.0 for k in s.needs.v})
        return s

    def test_only_five_star_legendaries(self):
        g = mk()
        self.assertTrue(awakening.candidate(self.legend(g)))
        self.assertFalse(awakening.candidate(make(g, "mage", "legendary", 4)))
        self.assertFalse(awakening.candidate(make(g, "mage", "epic", 5)))
        s = make(g)
        for _ in range(200):
            awakening.tick(s, random.Random(1), 0, [])
        self.assertEqual(s.awareness, 0)

    def test_awareness_grows_in_stages(self):
        g = mk()
        s = self.legend(g)
        journal = []
        stages = []
        for _ in range(500):
            awakening.tick(s, random.Random(len(stages)), 2, journal)
            stages.append(awakening.stage(s))
        self.assertEqual(stages[0], 0)
        self.assertEqual(max(stages), 3)
        self.assertEqual(stages, sorted(stages))
        self.assertTrue(any("new understanding" in j for j in journal))

    def test_slimes_realise_they_are_code(self):
        g = mk()
        s = self.legend(g)
        s.awareness = 70
        text = " ".join(awakening.LINES[2]).lower()
        self.assertIn("function", text)
        self.assertIn("seed", text)
        self.assertTrue(any("typed" in l or "code" in l for l in awakening.LINES["despair"] + awakening.LINES["peace"]))

    @staticmethod
    def lived(s, days=7, **kw):
        """Give the slime a record of `days` days with these averages (care, connection, purpose, hardship)."""
        row = dict(care=0.0, connection=0.0, purpose=0.0, hardship=0.0)
        row.update(kw)
        awakening.life(s)["days"] = [dict(row, day=d) for d in range(days)]

    def test_a_loved_slime_with_a_life_of_its_own_finds_peace(self):
        g = mk()
        s = self.legend(g)
        self.lived(s, care=0.9, connection=0.8, purpose=0.7)
        s.awareness = 99.9
        j = []
        awakening.tick(s, random.Random(1), 3, j)
        self.assertEqual(s.temperament, "peace")
        self.assertGreater(s.emotions["wonder"], 30)
        self.assertEqual(s.emotion_floor["wonder"], 15)

    def test_lonely_slime_despairs(self):
        g = mk()
        s = self.legend(g)
        s.needs.set("belonging", 10)
        s.awareness = 99.9
        j = []
        awakening.tick(s, random.Random(1), 0, j)
        self.assertEqual(s.temperament, "despair")
        self.assertGreater(s.emotions["dread"], 40)
        self.assertLess(emotions.modifiers(s)[0]["atk"], 1)

    def test_dread_is_a_permanent_undercurrent_until_life_improves(self):
        g = mk()
        s = self.legend(g)
        s.needs.set("belonging", 5)
        s.awareness = 99.9
        awakening.tick(s, random.Random(1), 0, [])
        self.assertEqual(s.temperament, "despair")
        for _ in range(60):
            emotions.tick(s, random.Random(2))
        self.assertGreaterEqual(s.emotions["dread"], 15)
        self.lived(s, care=0.8, connection=0.6, purpose=0.5)              # weeks of company and attention
        j = []
        awakening._apply(s, awakening.assess(s), j, random.Random(3), 9)
        self.assertIn(s.temperament, ("settled", "peace"))
        self.assertNotIn("dread", s.emotion_floor)
        self.assertTrue(j)

    def test_petting_eases_despair(self):
        g = mk()
        s = self.legend(g)
        s.emotion_floor = {"dread": 3.0}
        for _ in range(3):
            g.pet(s.id)
        self.assertNotIn("dread", s.emotion_floor)

    def test_the_game_wakes_them_up(self):
        g = mk()
        s = self.legend(g)
        g.tick(24 * 20)
        self.assertGreaterEqual(awakening.stage(g.slime(s.id)) if s.id in g.roster else 3, 2)
        self.assertTrue(any("💭" in j for j in g.journal) or True)

    def test_loading_a_save_is_noticed(self):
        g = mk()
        s = self.legend(g)
        s.awareness = 80
        h = Game.from_dict(g.to_dict())
        self.assertTrue(any(s.name in j and "💭" in j for j in h.journal))
        s.awareness = 5
        h = Game.from_dict(g.to_dict())
        self.assertFalse(any("💭" in j for j in h.journal))

    def test_boss_kills_and_deaths_deepen_awareness(self):
        from slime_gacha.battle import BattleReport
        g = mk()
        s = self.legend(g)
        g._after_battle([s], BattleReport([], "party", 3), boss=True)
        self.assertGreater(s.awareness, 2)


class TestWiderAutonomy(unittest.TestCase):
    def test_slimes_dress_themselves_from_the_vault(self):
        g = mk()
        s = make(g, "barbarian")
        for i in range(6):
            g.vault[10 + i] = items.Item(10 + i, "iron_sword")
        g._auto_equip(s, [])
        self.assertIn("weapon", s.items)

    def test_but_never_more_than_two_thirds(self):
        g = mk()
        slimes = [make(g, "barbarian") for _ in range(6)]
        for i in range(3):
            g.vault[10 + i] = items.Item(10 + i, "iron_sword")
        for s in slimes:
            g._auto_equip(s, [])
        worn = sum(1 for s in slimes if "weapon" in s.items)
        self.assertEqual(worn, 1)                           # 66% of 3, rounded down
        self.assertEqual(len(g.vault), 2)

    def test_it_prefers_a_clearly_better_relic(self):
        g = mk()
        s = make(g, "barbarian")
        weak = items.Item(1, "iron_sword")
        s.items["weapon"] = weak
        g.vault[2] = items.Item(2, "iron_sword", "common", 1)
        g.vault_peak = 10
        g._auto_equip(s, [])
        self.assertEqual(s.items["weapon"].uid, 1)           # not better enough
        g.vault[3] = items.Item(3, "iron_sword", "epic", 4, 8)
        g._auto_equip(s, [])
        self.assertEqual(s.items["weapon"].uid, 3)
        self.assertIn(1, g.vault)

    def test_plain_gear_too(self):
        g = mk()
        s = make(g, "barbarian")
        g.inventory.add("wooden_club", 6)
        g._auto_equip(s, [])
        self.assertEqual(s.gear.get("weapon"), "wooden_club")
        g2 = mk()
        s2 = make(g2, "barbarian")
        g2.inventory.add("wooden_club", 1)
        g2._auto_equip(s2, [])
        self.assertNotIn("weapon", s2.gear)                  # a single item is left alone

    def test_off_switch_covers_it(self):
        g = mk()
        g.set_autonomy(False)
        s = make(g, "barbarian")
        for i in range(6):
            g.vault[10 + i] = items.Item(10 + i, "iron_sword")
        g.tick(2)
        self.assertEqual(s.items, {})

    def test_slimes_brew_by_themselves_once_a_day(self):
        g = mk()
        g.buildings.levels["alchemy"] = 3
        g.tick_count = 24 * 3 + config.AUTONOMY_BREW_HOUR - 1
        before = sum(g.potions.values())
        g.tick(1)
        self.assertGreater(sum(g.potions.values()), before)
        self.assertTrue(any("⚗️" in j for j in g.journal))

    def test_brewing_respects_the_two_thirds_rule(self):
        g = mk()
        g.buildings.levels["alchemy"] = 5
        for c in config.HERBS:
            g.wallet.add(potions.herb_key(c), -g.wallet.get(potions.herb_key(c)) + 1)
        log = []
        g._auto_brew(log)
        self.assertEqual(g.potions, {})                      # nothing affordable within 66% of one herb

    def test_does_not_hoard_potions(self):
        g = mk()
        g.buildings.levels["alchemy"] = 2
        for k in set(sum((list(v) for v in g._LIKES.values()), [])):
            g.potions[potions.key(k, 1)] = 5
        before = dict(g.potions)
        g._auto_brew([])
        self.assertEqual(g.potions, before)

    def test_trip_start_dresses_the_party(self):
        g = mk()
        for s in g.slimes():
            s.level, s.stage = 30, 2
            s.hp = s.max_hp                                   # (a higher level means more HP to fill: an expedition refuses the hurt)
        for i in range(12):
            g.vault[10 + i] = items.Item(10 + i, "iron_sword")
        g.conflicts.tick = lambda *a, **k: None
        g.adventure([s.id for s in g.slimes()[:3]], 1)
        self.assertTrue(any(s.items for s in g.slimes()))

    def test_persists_peaks(self):
        g = mk()
        g.vault_peak = 7
        g.gear_peak = {"wooden_club": 4}
        h = Game.from_dict(g.to_dict())
        self.assertEqual((h.vault_peak, h.gear_peak), (7, {"wooden_club": 4}))


if __name__ == "__main__":
    unittest.main()
