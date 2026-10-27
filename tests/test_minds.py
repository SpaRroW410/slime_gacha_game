"""Slime minds: feuds that cool off, feelings with a baseline, legendaries that read their whole life (docs/MINDS.md)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, emotions, memory
from slime_gacha.ai import Conflict
from slime_gacha.game import Game


def colony(seed=7, n=0):
    g = Game(seed)
    g.wallet.add_many({"white_gel": 10000, "food": 10000})
    if n:
        g.pull(n, "white_gel")
    return g


def make(g, arch="barbarian", rarity="common", stars=1, traits=()):
    s = g.gacha.make_slime(rarity, arch, stars)
    s.traits = list(traits)
    g.roster[s.id] = s
    return s


def feud(g, severity=3, age=None, **kw):
    a, b = make(g), make(g, "mage")
    c = Conflict(1, a.id, b.id, severity, config.CONFLICT_ESCALATE_TICKS - 1 if age is None else age, "a rude blorp", **kw)
    g.conflicts.conflicts.append(c)
    return a, b, c


NO_MEND = mock.patch.object(config, "CONFLICT_SELF_MEND", 0.0)


class TestFeudsCoolOff(unittest.TestCase):
    def test_a_brawl_is_followed_by_time_apart(self):
        g = colony()
        a, b, c = feud(g)
        with NO_MEND:
            g.conflicts.tick(g.slimes(), [])
            self.assertEqual((c.brawls, c.cool), (1, config.CONFLICT_BRAWL_COOL))
            age = c.age
            for _ in range(config.CONFLICT_BRAWL_COOL - 1):
                g.conflicts.tick(g.slimes(), [])
        self.assertEqual(c.age, age)                                  # no escalation while they keep apart
        self.assertEqual(c.brawls, 1)

    def test_a_feud_brawls_at_most_twice_then_turns_cold(self):
        g = colony()
        a, b, c = feud(g)
        events = []
        with NO_MEND:
            for _ in range(24 * 6):
                g.conflicts.tick(g.slimes(), events)
        self.assertEqual(sum("brawl!" in e for e in events), config.CONFLICT_MAX_BRAWLS)
        self.assertTrue(any("stop speaking" in e for e in events))
        self.assertEqual(g.conflicts.conflicts, [])
        self.assertIn(frozenset((a.id, b.id)), g.conflicts.cold)
        self.assertFalse(a.grounded or b.grounded)                    # the fighting is over

    def test_no_quarrels_and_no_growing_closer_in_a_cold_war(self):
        g = colony()
        a, b = make(g), make(g, "mage")
        g.conflicts.cold[frozenset((a.id, b.id))] = 48
        with mock.patch.object(config, "CONFLICT_BASE_CHANCE", 1.0):
            self.assertEqual(g.conflicts.chance(a, b), 0.0)
        before = g.social.bond(a, b)
        g.relations.daily(g, g.mood_rng, [], g.day)
        self.assertEqual(g.social.bond(a, b), before)
        for _ in range(48):
            g.conflicts.tick(g.slimes(), [])
        self.assertNotIn(frozenset((a.id, b.id)), g.conflicts.cold)  # it thaws into plain civility

    def test_cold_wars_and_feud_state_are_saved(self):
        g = colony()
        a, b, c = feud(g, brawls=1, cool=5, retry=2)
        x, y = make(g), make(g)
        g.conflicts.cold[frozenset((x.id, y.id))] = 30
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.conflicts.cold, {frozenset((x.id, y.id)): 30})
        self.assertEqual((h.conflicts.conflicts[0].brawls, h.conflicts.conflicts[0].cool, h.conflicts.conflicts[0].retry), (1, 5, 2))

    def test_old_saves_without_the_new_fields_load(self):
        g = colony()
        feud(g)
        d = g.to_dict()
        for c in d["conflicts"]:
            for k in ("brawls", "cool", "retry"):
                c.pop(k)
        d.pop("cold_wars")
        h = Game.from_dict(d)
        self.assertEqual(h.conflicts.conflicts[0].brawls, 0)
        self.assertEqual(h.conflicts.cold, {})

    def test_spats_can_mend_without_help(self):
        g = colony()
        a, b, c = feud(g, severity=1, age=0)
        events = []
        with mock.patch.object(config, "CONFLICT_SELF_MEND", 1.0):
            g.conflicts.tick(g.slimes(), events)
        self.assertEqual(g.conflicts.conflicts, [])
        self.assertTrue(any("patch things up on their own" in e for e in events))
        self.assertTrue(any(m["kind"] == "made_up" for m in a.memories))

    def test_kind_slimes_mend_more_easily_than_grumpy_ones(self):
        g = colony()
        a, b, c = feud(g, severity=1, age=0)
        plain = g.conflicts.mend_chance(a, b, c)
        a.traits, b.traits = ["kind"], ["kind"]
        kind = g.conflicts.mend_chance(a, b, c)
        a.traits, b.traits = ["grumpy"], ["proud"]
        sour = g.conflicts.mend_chance(a, b, c)
        self.assertGreater(kind, plain)
        self.assertLess(sour, plain)
        c.severity = 3
        self.assertLess(g.conflicts.mend_chance(a, b, c), sour)      # a worse quarrel is harder to let go of

    def test_a_guilty_slime_apologises(self):
        g = colony()
        a, b, c = feud(g, severity=2, age=0)
        a.emotions["guilt"] = 60
        events = []
        with mock.patch.object(config, "APOLOGY_CHANCE", 1.0):
            g._peacemaking(events)
        self.assertEqual(g.conflicts.conflicts, [])
        self.assertTrue(any(f"{a.name} apologises to {b.name}" in e for e in events))
        self.assertLess(emotions.level(a, "guilt"), 60)

    def test_a_friend_of_both_makes_peace(self):
        g = colony()
        a, b, c = feud(g, severity=2, age=0)
        f = make(g, "medic")
        g.social.add_bond(f, a, 40)
        g.social.add_bond(f, b, 40)
        events = []
        with mock.patch.object(config, "PEACEMAKER_CHANCE", 1.0), mock.patch.object(g.conflicts, "mediate_chance", return_value=1.0):
            g._peacemaking(events)
        self.assertEqual(g.conflicts.conflicts, [])
        self.assertTrue(any(f"{f.name} helps" in e for e in events))
        self.assertGreater(memory.opinion(a, f)["gratitude"], 0)     # they remember who helped

    def test_no_peacemaker_when_nobody_likes_both(self):
        g = colony()
        a, b, c = feud(g, severity=2, age=0)
        make(g, "medic")
        with mock.patch.object(config, "PEACEMAKER_CHANCE", 1.0), mock.patch.object(g.conflicts, "mediate_chance", return_value=1.0):
            g._peacemaking([])
        self.assertEqual(len(g.conflicts.conflicts), 1)


class TestCareMakesFriendsNotRivals(unittest.TestCase):
    def test_a_failed_talk_means_not_yet_and_costs_nothing(self):
        g = colony()
        a, b, c = feud(g, severity=2, age=0)
        a.needs.set("belonging", 60)
        bond = g.social.bond(a, b)
        with mock.patch.object(g.conflicts, "mediate_chance", return_value=0.0):
            msg = g.mediate(c.id, "talk")
        self.assertIn("not ready", msg)
        self.assertEqual((g.social.bond(a, b), a.needs.get("belonging")), (bond, 60))
        self.assertEqual(c.retry, config.MEDIATE_RETRY_HOURS)
        with self.assertRaises(Exception):                            # too soon to try again ...
            g.mediate(c.id, "talk")
        self.assertIn("make up", g.mediate(c.id, "snack"))            # ... but a snack works any time

    def test_making_up_counts_towards_friendship_not_rivalry(self):
        g = colony()
        a, b, c = feud(g, severity=1, age=0)
        g.relations.note_quarrel(a, b, 2)
        g.mediate(c.id, "snack")
        self.assertEqual(g.relations.quarrels.get(frozenset((a.id, b.id)), 0), 1)

    def test_no_new_quarrel_right_after_making_up(self):
        g = colony()
        a, b, c = feud(g, severity=1, age=0)
        x = make(g, "rogue")
        g.mediate(c.id, "snack")
        with mock.patch.object(config, "CONFLICT_BASE_CHANCE", 1.0):
            g.conflicts.tick(g.slimes(), [])
        self.assertFalse(any({a.id, b.id} & {q.a, q.b} for q in g.conflicts.conflicts))

    def test_angry_slimes_snap_and_content_ones_let_go(self):
        g = colony()
        a, b = make(g), make(g)
        ordinary = g.conflicts.temper(a, b)
        a.emotions["anger"] = b.emotions["anger"] = 70
        self.assertGreater(g.conflicts.temper(a, b), ordinary)
        a.emotions.clear(), b.emotions.clear()
        a.content = b.content = 90
        self.assertLess(g.conflicts.temper(a, b), ordinary)


class TestUsualMood(unittest.TestCase):
    def test_traits_set_a_baseline(self):
        g = colony()
        s = make(g, traits=["chatty", "grumpy"])
        base = emotions.baseline(s)
        self.assertGreater(base["joy"], 0)
        self.assertGreater(base["anger"], 0)
        self.assertTrue(all(v < 5 for v in emotions.baseline(make(g)).values()))   # no traits, a new life: only a faint mood

    def test_feelings_settle_back_to_the_baseline_not_to_nothing(self):
        g = colony()
        s = make(g, traits=["grumpy"])
        s.emotions["anger"] = 90
        for _ in range(48):
            emotions.tick(s, g.mood_rng)
        self.assertAlmostEqual(s.emotions["anger"], emotions.TRAIT_BASELINE["grumpy"]["anger"], delta=0.01)

    def test_a_soothed_feeling_climbs_back_slowly(self):
        g = colony()
        s = make(g, traits=["lazy"])
        s.needs.v.update({k: 100.0 for k in s.needs.v})
        s.emotions.pop("calm", None)
        emotions.tick(s, g.mood_rng)
        self.assertGreater(s.emotions.get("calm", 0), 0)
        self.assertLess(s.emotions.get("calm", 0), emotions.TRAIT_BASELINE["lazy"]["calm"])

    def test_contentment_follows_mood_over_days(self):
        g = colony()
        s = make(g)
        for _ in range(12):
            emotions.settle(s, 1.0)
        self.assertLess(s.content, 65)                                  # half a day of bliss is not a good life
        for _ in range(24 * 6):
            emotions.settle(s, 1.0)
        self.assertGreater(s.content, 85)
        self.assertGreater(emotions.baseline(s)["joy"], 15)             # a good life shows as everyday joy
        for _ in range(24 * 10):
            emotions.settle(s, 0.1)
        self.assertGreater(emotions.baseline(s)["sadness"], 5)          # a hard one as a low hum of sadness
        self.assertIn(emotions.content_label(s), ("struggling", "worn down"))

    def test_needs_keep_a_feeling_simmering_but_not_boiling(self):
        g = colony()
        s = make(g)
        s.needs.set("food", 0)
        for _ in range(48):
            emotions.tick(s, g.mood_rng)
        self.assertLessEqual(s.emotions["anger"], emotions.DRIFT_CEIL + 8)
        self.assertGreater(s.emotions["anger"], 30)

    def test_a_reload_feels_exactly_the_same(self):
        import json
        g = colony(11, 8)
        g.tick(30)
        h = Game.from_dict(json.loads(json.dumps(g.to_dict())))
        g.tick(48)
        h.tick(48)
        self.assertEqual([s.emotions for s in g.slimes()], [h.roster[s.id].emotions for s in g.slimes()])

    def test_contentment_is_saved(self):
        g = colony()
        s = make(g)
        s.content = 72.5
        self.assertEqual(Game.from_dict(g.to_dict()).roster[s.id].content, 72.5)


if __name__ == "__main__":
    unittest.main()
