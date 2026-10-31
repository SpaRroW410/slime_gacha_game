"""Slime minds: feuds that cool off, feelings with a baseline, legendaries that read their whole life (docs/ROADMAP.md § 5)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import collections
import random

from slime_gacha import appraisal, awakening, config, coping, emotions, grief, meaning, memory, rituals, routine, sanity, voice
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


def legend(g, traits=("lazy",)):
    s = make(g, "barbarian", "legendary", 5, traits)
    s.needs.v.update({k: 100.0 for k in s.needs.v})
    return s


def lived(s, days=14, **kw):
    row = dict(care=0.0, connection=0.0, purpose=0.0, hardship=0.0)
    row.update(kw)
    awakening.life(s)["days"] = [dict(row, day=d) for d in range(days)]


def awake(g, s, outcome, days=0):
    s.awareness = 100.0
    s.temperament = outcome
    lf = awakening.life(s)
    lf["last_check"] = g.day
    lf["despair_days" if outcome == "despair" else "cog_days"] = days


class TestLifeRecord(unittest.TestCase):
    def test_talks_and_pats_count_as_care_for_a_legendary(self):
        g = colony()
        s = legend(g)
        g.talk(s.id), g.pet(s.id), g.talk(s.id)                      # a second talk the same day adds nothing
        self.assertAlmostEqual(awakening.life(s)["acc"]["care"], 0.9)
        plain = make(g)
        g.talk(plain.id)
        self.assertEqual(plain.life["acc"]["care"], 0.5)               # every slime keeps a record (meaning.py)

    def test_sanity_lost_counts_as_hardship(self):
        g = colony()
        s = legend(g)
        sanity.hit(s, 20)
        e = awakening.close_day(g, s)
        self.assertGreater(e["hardship"], 0.4)
        self.assertEqual(awakening.life(s)["acc"]["hurt"], 0)          # the day is closed

    def test_a_day_of_ties_variety_and_growth(self):
        g = colony()
        s = legend(g)
        for o in (make(g), make(g)):
            g.relations.rel[frozenset((s.id, o.id))] = dict(kind="friend", since=0)
        for state in ("studying", "hunting"):                           # two real activities (sitting idle is not one)
            s.state = state
            awakening.sample_hour(s)
        s.total_xp += 50
        awakening.note(s, "chose")
        e = awakening.close_day(g, s)
        self.assertGreater(e["connection"], 0.7)
        self.assertGreaterEqual(e["purpose"], 0.8)

    def test_the_same_post_day_after_day_halves_purpose(self):
        g = colony()
        s = legend(g)
        s.job, s.state = "chef", "working"
        for _ in range(config.COG_POST_DAYS + 1):
            awakening.sample_hour(s)
            e = awakening.close_day(g, s)
        self.assertLessEqual(e["purpose"], 0.15 + 1e-9)

    def test_the_record_keeps_two_weeks_and_is_saved(self):
        g = colony()
        s = legend(g)
        for _ in range(config.LIFE_DAYS + 5):
            awakening.close_day(g, s)
        self.assertEqual(len(s.life["days"]), config.LIFE_DAYS)
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.roster[s.id].life["days"], s.life["days"])


class TestFourOutcomes(unittest.TestCase):
    def test_care_alone_can_settle_it_but_not_bring_peace(self):
        g = colony()
        s = legend(g)
        lived(s, care=1.0)
        self.assertAlmostEqual(awakening.scores(s)["eff_connection"], config.KEEPER_CARE_SHARE)
        self.assertEqual(awakening.assess(s), "settled")
        lived(s, care=1.0, connection=0.6)                               # friends of its own
        self.assertEqual(awakening.assess(s), "peace")

    def test_unseen_and_unchosen_is_a_cog(self):
        g = colony()
        s = legend(g)
        lived(s, connection=0.5, purpose=0.2)
        self.assertEqual(awakening.assess(s), "cog")

    def test_isolation_or_hardship_is_despair(self):
        g = colony()
        s = legend(g)
        lived(s, connection=0.1, purpose=0.8)
        self.assertEqual(awakening.assess(s), "despair")
        lived(s, care=1.0, connection=0.8, purpose=0.8, hardship=0.6)    # loved, but too much has gone wrong this week
        self.assertEqual(awakening.assess(s), "despair")

    def test_a_cog_feels_little(self):
        g = colony()
        s = legend(g)
        s.emotions["joy"] = 80
        awakening._apply(s, "cog", [], random.Random(1), 0)
        self.assertLessEqual(s.emotions["joy"], config.COG_FEELING_CAP)
        emotions.feel(s, "joy", 50)
        self.assertLessEqual(s.emotions["joy"], config.COG_FEELING_CAP)
        self.assertLessEqual(s.mood(), config.COG_MOOD_CAP)

    def test_the_outcome_is_reviewed_and_can_change(self):
        g = colony()
        s = legend(g)
        awake(g, s, "despair")
        lived(s, care=0.9, connection=0.7, purpose=0.6)
        g.tick_count += 24 * config.LIFE_REVIEW_DAYS
        events = []
        awakening.daily(g, s, events)
        self.assertIn(s.temperament, ("settled", "peace"))              # weeks of company: the despair lifts
        self.assertNotIn("dread", s.emotion_floor)
        self.assertTrue(any("💭" in e for e in events))

    def test_old_saves_that_accepted_count_as_at_peace(self):
        g = colony()
        s = legend(g)
        s.temperament = "accept"
        self.assertEqual(awakening.outcome(s), "peace")
        self.assertEqual(Game.from_dict(g.to_dict()).roster[s.id].temperament, "accept")

    def test_it_never_repeats_a_thought_within_a_week(self):
        g = colony()
        s = legend(g)
        awake(g, s, "despair")
        rng = random.Random(4)
        week = [awakening.say(s, "despair", rng, 0) for _ in range(len(awakening.LINES["despair"]))]
        self.assertEqual(len(set(week)), len(week))


class TestDespairDeepens(unittest.TestCase):
    def test_it_refuses_dungeons_then_work(self):
        g = colony()
        s = legend(g)
        awake(g, s, "despair", 1)
        self.assertIn("despair", g.refusal(s, "dungeon"))
        self.assertNotIn("despair", g.refusal(s, "job"))
        s.life["despair_days"] = config.DESPAIR_BREAKDOWN_DAY
        self.assertIn("despair", g.refusal(s, "job"))

    def test_self_neglect_only_the_keepers_hand_feeds_it(self):
        g = colony()
        s = legend(g)
        awake(g, s, "despair", config.DESPAIR_BREAKDOWN_DAY)
        s.needs.set("food", 10)
        events = []
        g.needs._autonomy(s, [s], events)
        g.needs._autonomy(s, [s], events)
        self.assertEqual(s.needs.get("food"), 10)                       # it left its food ...
        self.assertEqual(sum("leaves their food untouched" in e for e in events), 1)   # ... and you are warned once a day
        g.feed(s.id)
        self.assertGreater(s.needs.get("food"), 10)                     # ... but eats from your hand

    def test_dread_deepens_day_by_day_and_breakdowns_come(self):
        g = colony()
        s = legend(g)
        awake(g, s, "despair")
        lived(s, connection=0.0)
        events = []
        with mock.patch.object(config, "BREAKDOWN_CHANCE", 1.0):
            for _ in range(config.DESPAIR_BREAKDOWN_DAY + 1):
                g.tick_count += 24
                awakening.daily(g, s, events)
        self.assertEqual(awakening.despair_stage(s), 3)
        self.assertGreater(s.emotion_floor["dread"], config.DESPAIR_DREAD)
        self.assertTrue(any("breaks down" in e for e in events))
        self.assertTrue(any("feed them by hand" in e for e in events))


class TestLeaving(unittest.TestCase):
    def asking(self, g, s):
        from slime_gacha import mind
        mind.daily(g, [])
        return s.request

    def test_a_long_despair_ends_with_a_request_to_leave(self):
        g = colony()
        s = legend(g)
        awake(g, s, "despair", config.LEAVE_DESPAIR_DAYS)
        r = self.asking(g, s)
        self.assertEqual(r["kind"], "leave")

    def test_the_keeper_lets_it_go(self):
        g = colony()
        s = legend(g)
        friend = make(g)
        g.relations.rel[frozenset((s.id, friend.id))] = dict(kind="best_friend", since=0)
        s.gear["weapon"] = "wooden_club"
        awake(g, s, "despair", config.LEAVE_DESPAIR_DAYS)
        self.asking(g, s)
        msg = g.answer_request(s.id, True)
        self.assertIn("leaves the colony", msg)
        self.assertNotIn(s.id, g.roster)
        self.assertGreater(emotions.level(friend, "sadness"), 10)
        self.assertEqual(g.departed[-1]["name"], s.name)
        self.assertIn("wooden_club", g.inventory.to_dict())             # its gear stays with the colony
        self.assertEqual(Game.from_dict(g.to_dict()).departed[-1]["name"], s.name)

    def test_the_keeper_asks_it_to_stay(self):
        g = colony()
        s = legend(g)
        awake(g, s, "despair", config.LEAVE_DESPAIR_DAYS)
        self.asking(g, s)
        trust = s.trust
        self.assertIn("stays", g.answer_request(s.id, False))
        self.assertIn(s.id, g.roster)
        self.assertLess(s.trust, trust)
        self.assertIsNone(self.asking(g, s))                            # it waits a few days before asking again
        g.tick_count += 24 * config.LEAVE_ASK_AGAIN_DAYS
        self.assertEqual(self.asking(g, s)["kind"], "leave")

    def test_a_cog_asks_for_a_change_first(self):
        g = colony()
        s = legend(g)
        s.job, s.state = "chef", "working"
        awake(g, s, "cog", config.COG_CHANGE_DAYS)
        self.assertEqual(self.asking(g, s)["kind"], "change")
        g.answer_request(s.id, True)
        self.assertEqual(s.job, "")
        self.assertEqual(s.life["cog_days"], 0)

    def test_any_slime_breaking_without_trust_may_ask(self):
        g = colony()
        s = make(g)
        s.sanity, s.trust, s.low_days = 1.0, 10.0, config.LEAVE_SANITY_DAYS
        self.assertEqual(self.asking(g, s)["kind"], "leave")


class TestEverydayGoals(unittest.TestCase):
    def test_goals_are_mostly_ordinary(self):
        from slime_gacha import mind
        g = colony(5, 16)
        for s in g.slimes():                                             # everyone holds a grudge against someone
            o = next(o for o in g.slimes() if o is not s)
            memory.remember(s, "brawl", o, g.day, 4.0)
        kinds = collections.Counter()
        for day in range(6):
            g.tick_count = day * 24 * 5
            for s in g.slimes():
                kinds[mind.choose_goal(g, s)["kind"]] += 1
        self.assertGreaterEqual(len(kinds), 6)                           # many kinds of wanting
        self.assertLess(kinds["rival"] / sum(kinds.values()), 0.35)      # a grudge is one candidate, not the default

    def test_personality_shapes_what_it_wants(self):
        from slime_gacha import mind
        g = colony(5, 6)
        s = g.slimes()[0]
        s.traits = ["lazy", "proud"]
        w = {goal["kind"]: weight for weight, goal in mind._goal_options(g, s)}
        s.traits = ["kind", "timid"]
        w2 = {goal["kind"]: weight for weight, goal in mind._goal_options(g, s)}
        self.assertGreater(w["rest"], w2["rest"])
        self.assertGreater(w["praise"], w2["praise"])

    def test_new_goals_are_acted_on(self):
        from slime_gacha import mind
        g = colony(5, 0)
        a, b = make(g), make(g, "mage")
        for x in (a, b):
            x.needs.v.update({k: 90.0 for k in x.needs.v})
        for kind, target, word in (("befriend", b.id, "conversation"), ("court", b.id, "flower"), ("explore", 0, "woods"),
                                   ("craft", 0, "own hands"), ("rest", 0, "easy"), ("praise", 0, "shows off"), ("master", 0, "practises")):
            a.goal = dict(kind=kind, target=target, day=g.day, text="")
            events = []
            with mock.patch.object(config, "DECIDE_CHANCE", 1.0):
                self.assertTrue(mind.decide(g, a, events), kind)
            self.assertIn(word, events[-1])

    def test_thanks_outlast_minor_grudges_when_memory_is_full(self):
        g = colony()
        a, b = make(g), make(g)
        memory.remember(a, "healed", b, 0, 1.0)
        for i in range(config.MEMORY_CAP):
            memory.remember(a, "quarrel", make(g), 0, 1.2)
        self.assertTrue(any(m["kind"] == "healed" for m in a.memories))

    def test_slimes_at_home_grow_closer_even_at_work(self):
        g = colony()
        a, b = make(g), make(g)
        a.state = "working"
        with mock.patch.object(g.social, "compat", return_value=40):
            g.relations.daily(g, g.mood_rng, [], g.day)
        self.assertGreater(g.social.bond(a, b), 0)


class TestMeaningForEverySlime(unittest.TestCase):
    def test_every_slime_keeps_a_week(self):
        g = colony()
        s = make(g)
        for _ in range(config.MEANING_DAYS + 3):
            meaning.close_day(g, s)
        self.assertEqual(len(s.life["days"]), config.MEANING_DAYS)
        L = legend(g)
        for _ in range(config.LIFE_DAYS + 3):
            meaning.close_day(g, L)
        self.assertEqual(len(L.life["days"]), config.LIFE_DAYS)        # a legendary keeps two weeks for its awakening

    def test_praise_is_recognition(self):
        g = colony()
        s = make(g)
        s.needs.set("esteem", 30)
        msg = g.praise(s.id)
        self.assertIn("did well", msg)
        self.assertGreater(s.needs.get("esteem"), 30)
        self.assertGreater(emotions.level(s, "pride"), 0)
        e = meaning.close_day(g, s)
        self.assertGreater(e["care"], 0)
        self.assertGreaterEqual(e["purpose"], 0.2)                       # being noticed counts as an achievement
        self.assertIn("already praised", g.praise(s.id))

    def test_flat_days_burn_a_slime_out_and_praise_brings_it_back(self):
        g = colony()
        s = make(g)
        lf = meaning.life(s)
        events = []
        for d in range(config.BURNOUT_DAYS + 4):
            lf["days"] = [dict(day=d, care=0.0, connection=0.5, purpose=0.1, hardship=0.0)] * config.MEANING_DAYS
            lf["acc"] = meaning._fresh_acc(s)
            with mock.patch.object(meaning, "close_day"):
                meaning.daily(g, s, events)
        self.assertTrue(meaning.burned_out(s))
        self.assertTrue(any("going through the motions" in e for e in events))
        emotions.feel(s, "joy", 90)
        self.assertLessEqual(s.emotions["joy"], config.BURNOUT_FEELING_CAP)
        self.assertLessEqual(s.mood(), config.BURNOUT_MOOD_CAP)
        for d in range(6):
            lf["days"] = [dict(day=d, care=0.8, connection=0.5, purpose=0.6, hardship=0.0)] * config.MEANING_DAYS
            with mock.patch.object(meaning, "close_day"):
                meaning.daily(g, s, events)
        self.assertFalse(meaning.burned_out(s))
        self.assertTrue(any("spark back" in e for e in events))

    def test_a_lonely_slime_is_not_burned_out_but_lonely(self):
        g = colony()
        s = make(g)
        meaning.life(s)["days"] = [dict(day=0, care=0.0, connection=0.1, purpose=0.1, hardship=0.0)] * config.MEANING_DAYS
        for _ in range(config.BURNOUT_DAYS + 2):
            with mock.patch.object(meaning, "close_day"):
                meaning.daily(g, s, [])
        self.assertFalse(meaning.burned_out(s))

    def test_a_burned_out_worker_asks_for_a_change(self):
        from slime_gacha import mind
        g = colony()
        s = make(g)
        s.job, s.state = "chef", "working"
        meaning.life(s)["burnt"] = True
        self.assertEqual(mind.urgent_request(g, s)["kind"], "change")


class TestGrief(unittest.TestCase):
    def loss(self, kind="couple"):
        g = colony()
        a, b, c = make(g), make(g, "mage"), make(g, "rogue")
        g.relations.rel[frozenset((a.id, b.id))] = dict(kind=kind, since=0)
        g.social.add_bond(a, b, 60)
        b.hp, b.death_cause = 0, "a fall"
        g._reap([])
        return g, a, b, c

    def test_depth_follows_the_tie(self):
        for kind, depth in (("couple", 90), ("best_friend", 70), ("friend", 45)):
            g, a, b, c = self.loss(kind)
            self.assertEqual(a.grief[0]["depth"], depth)
            self.assertEqual(c.grief, [])                                  # a stranger does not grieve

    def test_grief_holds_sadness_up_for_weeks(self):
        g, a, b, c = self.loss()
        g.tick(24 * 3)
        self.assertGreater(emotions.level(a, "sadness"), 25)             # not gone in two days any more
        self.assertGreater(emotions.level(a, "loneliness"), 5)
        g.tick(24 * 25)
        self.assertEqual(a.grief, [])
        self.assertLess(emotions.level(a, "sadness"), 10)

    def test_a_friend_sits_with_it(self):
        g, a, b, c = self.loss()
        g.social.add_bond(a, c, 40)
        events = []
        before = a.grief[0]["depth"]
        grief.daily(g, events)
        self.assertEqual(a.grief[0]["depth"], before - config.GRIEF_FADE - config.GRIEF_COMFORT)
        self.assertTrue(any(f"{c.name} sits with {a.name}" in e for e in events))
        self.assertGreater(memory.opinion(a, c)["gratitude"], 0)

    def test_anniversaries_bring_it_back(self):
        g, a, b, c = self.loss()
        a.emotions["sadness"] = 0
        g.tick_count += 24 * 7
        events = []
        grief.daily(g, events)
        self.assertGreater(emotions.level(a, "sadness"), 20)
        self.assertTrue(any("1 week ago today" in e for e in events))

    def test_a_gathering_at_the_memorial_pond(self):
        g, a, b, c = self.loss()
        d = make(g, "medic")
        g.relations.rel[frozenset((d.id, b.id))] = dict(kind="friend", since=0)
        d.grief = [dict(other=b.id, name=b.name, depth=45.0, start=45.0, day=0, where="", gathered=False)]
        entry = g.graveyard[-1]
        self.assertTrue(g.can_gather(entry))
        depth = a.grief[0]["depth"]
        out = g.memorial(entry["id"])
        self.assertIn("Memorial Pond", out[0])
        self.assertEqual(a.grief[0]["depth"], depth - config.GRIEF_GATHER)
        self.assertGreater(g.social.bond(a, d), 0)                        # the mourners grow closer
        self.assertFalse(g.can_gather(entry))
        with self.assertRaises(Exception):
            g.memorial(entry["id"])                                       # once per loss

    def test_leaving_is_missed_at_half_depth(self):
        g = colony()
        a, b = make(g), make(g)
        g.relations.rel[frozenset((a.id, b.id))] = dict(kind="best_friend", since=0)
        g.depart(b, "test")
        self.assertEqual(a.grief[0]["depth"], 70 * config.GRIEF_DEPART_SCALE)

    def test_grief_is_saved(self):
        g, a, b, c = self.loss()
        self.assertEqual(Game.from_dict(g.to_dict()).roster[a.id].grief, a.grief)


class TestCopingAndComfort(unittest.TestCase):
    def test_personality_decides_how_it_copes(self):
        g = colony()
        for traits, st in ((["chatty"], "seek"), (["kind", "grumpy"], "help"), (["grumpy"], "vent"), (["timid"], "withdraw"),
                           (["lazy"], "sleep"), ([], "dwell")):
            self.assertEqual(coping.style(make(g, traits=traits)), st)

    def test_healthy_coping_eases_and_dwelling_lingers(self):
        g = colony()
        brave, plain = make(g, traits=["brave"]), make(g)
        for s in (brave, plain):
            s.emotions["sadness"] = 70
        coping.cope(g, brave, random.Random(1), [])
        coping.cope(g, plain, random.Random(1), [])
        self.assertLess(brave.emotions["sadness"], 70)
        self.assertGreater(plain.emotions["sadness"], 70)

    def test_venting_can_start_a_quarrel(self):
        g = colony()
        a, b = make(g, traits=["grumpy"]), make(g)
        a.emotions["anger"] = 80
        events = []
        with mock.patch.object(config, "VENT_QUARREL", 1.0):
            coping.cope(g, a, random.Random(2), events)
        self.assertLess(a.emotions["anger"], 80)
        self.assertTrue(g.conflicts.open_between(a.id, b.id))
        self.assertIn("snaps at", events[0])

    def test_once_a_day_and_only_at_home(self):
        g = colony()
        a = make(g, traits=["brave"])
        a.emotions["fear"] = 80
        events = []
        coping.hourly(g, events)
        coping.hourly(g, events)
        self.assertEqual(sum(a.name in e for e in events), 1)
        b = make(g, traits=["brave"])
        b.emotions["fear"], b.in_dungeon = 80, "main"
        self.assertFalse(coping.cope(g, b, random.Random(1), []))

    def test_a_friend_cheers_it_up(self):
        g = colony()
        a, f = make(g), make(g)
        g.social.add_bond(a, f, 40)
        a.emotions["loneliness"] = 70
        events = []
        self.assertTrue(coping.comfort(g, a, random.Random(1), events))
        self.assertLess(a.emotions["loneliness"], 70)
        self.assertGreater(memory.opinion(a, f)["gratitude"], 0)
        self.assertIn("cheers them up", events[0])

    def test_fear_spreads_in_a_party_away(self):
        g = colony(9, 5)
        p = g.create_party("P")
        g.party_autofill(p.id)
        ms = g.party_members(p.id)
        for m in ms:
            m.in_dungeon = "main"
        ms[0].emotions["fear"] = 80
        coping.contagion(g)
        self.assertGreater(ms[1].emotions.get("fear", 0), 0)

    def test_cuddles_go_to_friends_and_are_summarised(self):
        g = colony()
        a, f, x = make(g), make(g), make(g)
        g.social.add_bond(a, f, 40)
        self.assertIs(g.needs.buddy_fn(a, [x, f]), f)
        a.needs.set("belonging", 10)
        events = []
        g.needs._autonomy(a, [a, f, x], events)
        self.assertFalse(any("cuddles up" in e for e in events))
        self.assertEqual(g.needs.cuddles, {a.name: 1})
        out = []
        g._relations_day(out)
        self.assertTrue(any("cuddle(s) at home today" in e for e in out))


class TestVoice(unittest.TestCase):
    def test_it_talks_about_who_it_misses(self):
        g = colony()
        a = make(g)
        a.grief = [dict(other=99, name="Bloop", depth=80.0, start=80.0, day=0, where="", gathered=False)]
        lines = {voice.say(g, a, random.Random(i)) for i in range(6)}
        self.assertTrue(any("Bloop" in l for l in lines))

    def test_it_names_who_it_remembers(self):
        g = colony()
        a, b = make(g), make(g)
        a.grief, a.goal = [], None
        memory.remember(a, "brawl", b, g.day, 8.0)
        line = voice.pick(a, voice.MEMORY_LINES["brawl"], random.Random(1), g.day, n=b.name)
        self.assertIn(b.name, line)
        self.assertTrue(any(c[2].get("n") == b.name for c in voice._candidates(g, a)))

    def test_it_talks_about_what_it_wants(self):
        g = colony()
        a, b = make(g), make(g)
        a.goal = dict(kind="court", target=b.id, day=0, text="")
        self.assertTrue(any(c[2].get("n") == b.name and c[1] is voice.GOAL_LINES["court"] for c in voice._candidates(g, a)))

    def test_never_the_same_line_twice_in_a_week(self):
        g = colony()
        a = make(g)
        pool = voice.DAY_LINES["good"]
        week = [voice.pick(a, pool, random.Random(i), 0) for i in range(len(pool))]
        self.assertEqual(len(set(week)), len(pool))

    def test_talk_uses_it(self):
        g = colony()
        a = make(g)
        meaning.life(a)["burnt"] = True
        a.grief, a.goal, a.memories, a.emotions = [], None, [], {}
        self.assertTrue(any(l in g.talk(a.id) for l in voice.DAY_LINES["burnt"]))


class TestRoutine(unittest.TestCase):
    def test_hungry_slimes_eat_together_and_grow_closer(self):
        g = colony()
        a, b, c = make(g), make(g), make(g)
        for x in (a, b):
            x.needs.set("food", 40)
        c.needs.set("food", 95)                                           # not hungry: not at the table
        events = []
        routine.meal(g, events, dinner=True)
        self.assertGreater(a.needs.get("food"), 40)
        self.assertGreater(g.social.bond(a, b), 0)
        self.assertEqual(g.social.bond(a, c), 0)

    def test_evenings_are_for_hobbies(self):
        g = colony()
        a, b, c = make(g, traits=["chatty"]), make(g, traits=["chatty"]), make(g, traits=["timid"])
        events = []
        routine.evening(g, events)
        self.assertGreater(g.social.bond(a, b), 0)                        # a shared hobby brings them closer
        self.assertEqual(g.social.bond(a, c), 0)
        self.assertIn("gossip at the pond", events[0])
        self.assertIn("hobby", a.life["acc"]["acts"])
        self.assertGreater(a.life["acc"]["chose"], 0)

    def test_too_tired_or_away_means_no_hobby(self):
        g = colony()
        a, b = make(g, traits=["lazy"]), make(g, traits=["lazy"])
        a.needs.set("energy", 10)
        b.in_dungeon = "main"
        events = []
        routine.evening(g, events)
        self.assertEqual(events, [])

    def test_hobby_follows_what_it_does_most(self):
        g = colony()
        a = make(g, traits=["grumpy"])
        self.assertEqual(routine.hobby(a)[0], "tinkering")
        a.exp["scout"] = 50
        self.assertEqual(routine.hobby(a)[0], "stargazing")

    def test_idle_time_is_not_variety_and_praise_breaks_the_grind(self):
        g = colony()
        s = make(g)
        s.job = "chef"
        for state in ("working", "idle"):
            s.state = state
            meaning.sample_hour(s)
        meaning.close_day(g, s)
        self.assertEqual(s.life["post_streak"], 1)                       # work and sitting about: still the grind
        s.state = "working"
        meaning.sample_hour(s)
        meaning.note(s, "praised")
        e = meaning.close_day(g, s)
        self.assertEqual(s.life["post_streak"], 0)
        self.assertGreaterEqual(e["purpose"], 0.5)


class TestTextureReactionsRituals(unittest.TestCase):
    def test_the_same_defeat_means_different_things(self):
        g = colony()
        proud, timid, brave = make(g, traits=["proud"]), make(g, traits=["timid"]), make(g, traits=["brave"])
        for s in (proud, timid, brave):
            appraisal.react(s, "defeat")
        self.assertGreater(proud.emotions.get("guilt", 0), 0)
        self.assertGreater(timid.emotions.get("fear", 0), 0)
        self.assertGreater(brave.emotions.get("determination", 0), 0)
        self.assertNotIn("fear", brave.emotions)

    def test_a_first_victory_lands_harder(self):
        g = colony()
        a, b = make(g), make(g)
        appraisal.react(a, "victory", first=True)
        appraisal.react(b, "victory", first=False)
        self.assertGreater(a.emotions.get("pride", 0), b.emotions.get("pride", 0))

    def test_ties_fade_apart_and_hold_at_home(self):
        g = colony()
        a, b, c, d = make(g), make(g), make(g), make(g)
        g.social.add_bond(a, b, 30)
        g.social.add_bond(c, d, 30)
        c.in_dungeon = "grind"                                           # c is away, d at home
        with mock.patch.object(g.social, "compat", return_value=0):
            g.relations.daily(g, g.mood_rng, [], g.day)
        self.assertEqual(g.social.bond(a, b), 30)
        self.assertLess(g.social.bond(c, d), 30)

    def test_jealousy(self):
        g = colony()
        a, p, x = make(g), make(g), make(g)
        g.relations.rel[frozenset((a.id, p.id))] = dict(kind="couple", since=0)
        g.social.add_bond(a, p, 30)
        g.social.add_bond(p, x, 60)
        events = []
        with mock.patch.object(config, "JEALOUS_CHANCE", 1.0):
            g.relations._jealousy(g, {s.id: s for s in g.slimes()}, events, g.mood_rng)
        self.assertGreater(memory.opinion(a, x)["grudge"], 0)
        self.assertTrue(any("jealous" in e for e in events))

    def test_a_kind_slime_apologises_for_an_old_grudge(self):
        g = colony()
        a, b = make(g, traits=["kind"]), make(g)
        memory.remember(b, "brawl", a, g.day, 6.0)
        events = []
        with mock.patch.object(config, "APOLOGY_CHANCE", 1.0):
            g._apologies(events)
        self.assertLess(memory.opinion(b, a)["grudge"], 6.0)
        self.assertTrue(any("apologises" in e for e in events))

    def test_the_kind_forgive_sooner(self):
        g = colony()
        kind, plain, x = make(g, traits=["kind"]), make(g), make(g)
        for s in (kind, plain):
            memory.remember(s, "brawl", x, 0, 6.0)
        for _ in range(5):
            memory.fade(kind), memory.fade(plain)
        self.assertLess(memory.opinion(kind, x)["grudge"], memory.opinion(plain, x)["grudge"])

    def test_hatch_day_is_noticed_when_remembered(self):
        g = colony()
        s = make(g)
        s.born = g.day - config.HATCH_EVERY
        self.assertTrue(rituals.is_hatch_day(g, s))
        self.assertEqual(rituals.next_hatch_in(g, s), 0)
        trust = s.trust
        self.assertIn("hatch day", g.pet(s.id))
        self.assertGreater(s.trust, trust)
        self.assertNotIn("hatch day", g.talk(s.id))                     # noticed once
        events = []
        rituals.daily(g, events)
        self.assertTrue(any("Hatch day today" in e for e in events))

    def test_pulled_slimes_know_their_hatch_day(self):
        g = colony()
        g.tick_count = 24 * 4
        s = g.pull(1, "white_gel")[0]
        self.assertEqual(s.born, 4)
        self.assertEqual(rituals.next_hatch_in(g, s), config.HATCH_EVERY)
        self.assertEqual(Game.from_dict(g.to_dict()).roster[s.id].born, 4)

    def test_a_feast_after_a_boss(self):
        g = colony()
        a, b = make(g), make(g)
        g.feast = "the fall of the boss of floor 5"
        events = []
        routine.meal(g, events, dinner=True)
        self.assertTrue(any("feast" in e for e in events))
        self.assertGreater(g.social.bond(a, b), 0)
        self.assertEqual(g.feast, "")
        self.assertEqual(Game.from_dict(g.to_dict()).feast, "")


class TestWhyItFeelsThisWay(unittest.TestCase):
    def test_causes_are_recorded_strongest_first(self):
        g = colony()
        a, b = make(g), make(g)
        g._social_hook("brawl", a, b)
        emotions.feel(a, "anger", 5, "hungry")
        self.assertEqual(emotions.causes(a, "anger")[0], f"a brawl with {b.name}")
        self.assertIn("hungry", emotions.causes(a, "anger"))

    def test_settled_feelings_keep_their_usual_reason(self):
        g = colony()
        a = make(g, traits=["grumpy"])
        emotions.feel(a, "anger", 50, "a lost fight")
        for _ in range(24):
            emotions.tick(a, g.mood_rng)
        self.assertEqual(emotions.causes(a, "anger"), ["a grumpy nature"])

    def test_grief_and_needs_name_their_reasons(self):
        g = colony()
        a = make(g)
        a.grief = [dict(other=9, name="Bloop", depth=80.0, start=80.0, day=0, where="", gathered=False)]
        a.needs.set("food", 5)
        for _ in range(30):
            emotions.tick(a, g.mood_rng)
        self.assertIn("misses Bloop", emotions.causes(a, "sadness"))
        self.assertIn("hungry", emotions.causes(a, "anger"))

    def test_colony_mood_lists_who_struggles_and_why(self):
        from slime_gacha.webapi import colony_mood
        g = colony()
        a, b = make(g), make(g)
        a.grief = [dict(other=9, name="Bloop", depth=80.0, start=80.0, day=0, where="", gathered=False)]
        m = colony_mood(g)
        self.assertEqual([r["name"] for r in m["struggling"]], [a.name])
        self.assertIn("grieving Bloop", m["struggling"][0]["why"])
        self.assertEqual(sum(m["labels"].values()), 2)

    def test_causes_are_saved(self):
        g = colony()
        a = make(g)
        emotions.feel(a, "joy", 30, "your praise")
        self.assertEqual(Game.from_dict(g.to_dict()).roster[a.id].causes, a.causes)


class TestTroublemakers(unittest.TestCase):
    """A troublemaker (fought with more than 5% of the colony lately) goes at no cost but its partner's and best friend's
    half grief; those it fought with breathe easier, and the Keeper's shadow keeps the colony calmer for a week."""

    def tie(self, g, a, b, kind):
        g.relations.rel[frozenset((a.id, b.id))] = dict(kind=kind, since=0)

    def test_the_limit_is_5_percent_of_the_colony_rounded_down_but_never_under_one(self):
        g = colony()
        for size, limit in ((5, 1), (39, 1), (40, 2), (60, 3), (100, 5)):
            while len(g.roster) < size:
                make(g)
            self.assertEqual(g.fight_limit(), limit, size)

    def test_one_feud_run_to_a_cold_war_is_not_enough(self):
        g = colony()
        a, b, c = feud(g)
        with NO_MEND:
            for _ in range(24 * 6):
                g.conflicts.tick(g.slimes(), [])
        self.assertIn(frozenset((a.id, b.id)), g.conflicts.cold)
        self.assertEqual((a.fights, b.fights), ({b.id: g.day}, {a.id: g.day}))   # two brawls with one slime count once
        self.assertLessEqual(g.recent_fights(a), g.fight_limit())

    def test_a_slime_only_snapped_at_is_not_blamed(self):
        g = colony()
        a, b = make(g, traits=("grumpy",)), make(g, "mage")
        c = g.conflicts.start(a, b, "snapping", starter=a.id)
        c.severity, c.age = config.CONFLICT_MAX_SEVERITY, config.CONFLICT_ESCALATE_TICKS - 1
        with NO_MEND:
            g.conflicts.tick(g.slimes(), [])
        self.assertEqual(c.brawls, 1)
        self.assertEqual((a.fights, b.fights), ({b.id: g.day}, {}))

    def test_coping_by_snapping_names_the_starter(self):
        g = colony()
        a, b = make(g, traits=("grumpy",)), make(g, "mage")
        a.emotions["anger"] = 90
        with mock.patch.object(config, "VENT_QUARREL", 1.0):
            coping.cope(g, a, random.Random(1), [])
        self.assertEqual(g.conflicts.open_between(a.id, b.id).starter, a.id)

    def test_old_fights_are_forgiven(self):
        g = colony()
        a, b, c = make(g), make(g), make(g)
        a.fights = {b.id: g.day, c.id: g.day}
        self.assertEqual(g.recent_fights(a), 2)
        g.tick_count += config.DAY_TICKS * config.NUISANCE_DAYS
        self.assertEqual(g.recent_fights(a), 0)

    def removal(self, how):
        g = colony()
        t, partner, best, friend, foe, other = (make(g) for _ in range(6))
        t.fights = {foe.id: g.day, other.id: g.day}                      # 2 of a colony of 6: a troublemaker
        self.tie(g, t, partner, "couple")
        self.tie(g, t, best, "best_friend")
        self.tie(g, t, friend, "friend")
        for s in g.slimes():
            s.morale = 70.0
        foe.emotions["anger"], foe.content = 50.0, 40.0
        memory.remember(foe, "brawl", t, g.day, 4.0)
        stress = g.sacrifice_stress
        self.assertTrue(g.unwelcome(t))
        log = g.merge(other.id, t.id) if how == "merge" else g.destroy_slime(t.id)
        return g, log, stress, partner, best, friend, foe, other

    def test_removing_a_troublemaker_costs_nothing_but_its_partners_and_best_friends_half_grief(self):
        for how in ("merge", "destroy"):
            with self.subTest(how=how):
                g, log, stress, partner, best, friend, foe, other = self.removal(how)
                self.assertTrue(any("relieved" in l for l in log), log)
                self.assertEqual(g.sacrifice_stress, stress)
                for s in (partner, best, friend, foe):
                    self.assertEqual(s.morale, 70.0, s.name)
                self.assertEqual(partner.grief[0]["depth"], grief.DEPTH["couple"] * config.NUISANCE_GRIEF)
                self.assertEqual(best.grief[0]["depth"], grief.DEPTH["best_friend"] * config.NUISANCE_GRIEF)
                self.assertEqual(friend.grief, [])

    def test_those_it_fought_with_breathe_easier(self):
        g, log, stress, partner, best, friend, foe, other = self.removal("destroy")
        self.assertLess(foe.emotions["anger"], 50.0)
        self.assertGreater(foe.content, 40.0)
        self.assertEqual(next(m for m in foe.memories if m["kind"] == "brawl")["weight"], 4.0 * config.RELIEF_GRUDGE_FADE)
        self.assertTrue(any(foe.name in l and "easier" in l for l in log), log)

    def test_a_liked_slime_is_grieved_whether_merged_or_destroyed(self):
        for how in ("merge", "destroy"):
            with self.subTest(how=how):
                g = colony()
                lost, friend, target = make(g), make(g), make(g)
                self.tie(g, lost, friend, "friend")
                g.social.bonds[frozenset((lost.id, friend.id))] = 40
                self.assertFalse(g.unwelcome(lost))
                g.merge(target.id, lost.id) if how == "merge" else g.destroy_slime(lost.id)
                self.assertEqual(friend.grief[0]["depth"], grief.DEPTH["friend"])
                self.assertGreater(g.sacrifice_stress, 0)

    def test_the_keepers_shadow_calms_the_colony_for_a_week(self):
        g = colony()
        x, y = make(g), make(g, "mage")
        with mock.patch.object(config, "CONFLICT_BASE_CHANCE", 0.01):
            before = g.conflicts.chance(x, y)
            g.shadow_tick = g.tick_count
            self.assertAlmostEqual(g.conflicts.chance(x, y), before * config.SHADOW_FACTOR)
            g.tick_count += config.SHADOW_HOURS // 2
            self.assertAlmostEqual(g.wary(x), 1 - (1 - config.SHADOW_FACTOR) / 2)
            g.tick_count += config.SHADOW_HOURS // 2
            self.assertAlmostEqual(g.conflicts.chance(x, y), before)

    def test_slimes_with_fights_of_their_own_hold_back_more_by_temperament(self):
        g = colony()
        plain, brave, grumpy, timid = make(g), make(g, traits=("brave",)), make(g, traits=("grumpy",)), make(g, traits=("timid",))
        for s in (plain, brave, grumpy, timid):
            s.fights = {999: g.day}
        g.shadow_tick = g.tick_count
        self.assertAlmostEqual(g.wary(plain), config.SHADOW_FEAR_FACTOR)
        self.assertAlmostEqual(g.wary(timid), config.SHADOW_FLOOR)
        self.assertGreater(g.wary(grumpy), g.wary(plain))
        self.assertGreater(g.wary(brave), g.wary(grumpy))
        self.assertLess(g.wary(brave), config.SHADOW_FACTOR)

    def test_a_second_removal_within_the_week_makes_fighters_anxious(self):
        g = colony()
        fighter = make(g)
        fighter.fights = {999: g.day}
        t1, t2 = make(g), make(g)
        for t in (t1, t2):
            t.fights = {990: g.day, 991: g.day, 992: g.day}
        g.destroy_slime(t1.id)
        self.assertGreater(fighter.emotions.get("fear", 0), 0)
        self.assertEqual(fighter.emotions.get("anxiety", 0), 0)
        g.destroy_slime(t2.id)
        self.assertGreater(fighter.emotions.get("anxiety", 0), 0)

    def test_respect_after_a_talk_lasts_three_days(self):
        g = colony()
        s = make(g)
        g.talk(s.id)
        self.assertAlmostEqual(g.wary(s), config.RESPECT_FACTOR)
        g.tick_count += config.DAY_TICKS * config.RESPECT_DAYS
        self.assertAlmostEqual(g.wary(s), 1.0)

    def test_fights_starters_and_the_shadow_survive_a_reload(self):
        g = colony()
        a, b = make(g), make(g, "mage")
        a.fights = {b.id: g.day}
        g.conflicts.start(a, b, "snapping", starter=a.id)
        g.shadow_tick = g.tick_count
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.roster[a.id].fights, {b.id: g.day})
        self.assertEqual(h.conflicts.conflicts[0].starter, a.id)
        self.assertEqual(h.shadow_tick, g.shadow_tick)


class TestBehaviourTargets(unittest.TestCase):
    """A small run of tools/minds_sim.py: the colony and legendary scenarios must meet the behaviour targets."""
    PENDING = {"friends look after each other"}   # too rare to count in this small colony; the full harness checks it
    MIN_SHARE = {"care builds bonds": 0.75}        # a 14-slime colony is noisy: three of four small colonies must make more friends than rivals

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
        import minds_sim
        cls.sim = minds_sim
        cls.results = dict(hands_off=[minds_sim.run_colony(1, 14, 25, keeper=False)],
                           attentive=[minds_sim.run_colony(sd, 14, 25, keeper=True) for sd in (1, 2, 3, 4)],
                           recovery=[minds_sim.run_recovery(4)],
                           grief=[minds_sim.run_grief(5)], grief_supported=[minds_sim.run_grief(5, True)],
                           worker_unseen=[minds_sim.run_worker(6, False)], worker_praised=[minds_sim.run_worker(6, True)],
                           **{"legend_" + life: [minds_sim.run_legend(3, life)] for life in minds_sim.LIVES})

    def test_targets(self):
        for name, share, why in self.sim.check(self.results):
            if name in self.PENDING:
                continue
            with self.subTest(target=name):
                self.assertGreaterEqual(share, self.MIN_SHARE.get(name, 1.0), why)


if __name__ == "__main__":
    unittest.main()
