import random
import unittest

from slime_gacha import config, emotions, relationships as rl
from slime_gacha.errors import InvalidAction, NotEnoughResources
from slime_gacha.game import Game


class Always(random.Random):
    def random(self):
        return 0.0


def mk(seed=3, n=6):
    g = Game(seed)
    g.wallet.add_many({"white_gel": 100000, "essence": 1000, "food": 500})
    g.pull(n, "white_gel")
    for s in g.slimes():
        s.needs.v.update({k: 100.0 for k in s.needs.v})
    return g


def day(g, rng=None, d=None, n=1):
    j = []
    for _ in range(n):
        g.relations.daily(g, rng or Always(), j, g.day if d is None else d)
    return j


def pair(g, i=0, j=1):
    a, b = g.slimes()[i], g.slimes()[j]
    a.parents = b.parents = []
    return a, b


def lovebirds(g):
    a, b = pair(g)
    g.social.bonds[rl.key(a, b)] = 55
    a.emotions["affection"] = b.emotions["affection"] = 30.0
    g.social.compat = lambda x, y: 40
    return a, b


class TestTies(unittest.TestCase):
    def test_friendship_forms_from_a_good_bond(self):
        g = mk()
        a, b = pair(g)
        g.social.bonds[rl.key(a, b)] = 30
        day(g)
        self.assertEqual(g.relations.kind(a, b), "friend")

    def test_a_weak_bond_makes_no_tie(self):
        g = mk()
        a, b = pair(g)
        g.social.bonds[rl.key(a, b)] = 10
        day(g)
        self.assertIsNone(g.relations.kind(a, b))

    def test_best_friends_need_time_and_are_exclusive(self):
        g = mk()
        a, b, c = g.slimes()[:3]
        for x, y in ((a, b), (a, c)):
            g.social.bonds[rl.key(x, y)] = 50
        g.social.compat = lambda x, y: 5
        day(g, d=0)
        self.assertEqual(g.relations.kind(a, b), "friend")
        day(g, d=2)
        self.assertEqual(g.relations.kind(a, b), "friend")        # too soon
        day(g, d=6)
        kinds = {g.relations.kind(a, b), g.relations.kind(a, c)}
        self.assertIn("best_friend", kinds)
        self.assertEqual(sum(1 for k in (g.relations.kind(a, b), g.relations.kind(a, c)) if k == "best_friend"), 1)

    def test_rivalry_needs_a_sour_bond_and_quarrels(self):
        g = mk()
        a, b = pair(g)
        g.social.bonds[rl.key(a, b)] = -20
        day(g)
        self.assertIsNone(g.relations.kind(a, b))
        g.relations.note_quarrel(a, b, 2)
        day(g)
        self.assertEqual(g.relations.kind(a, b), "rival")

    def test_rivals_who_make_up_become_friends(self):
        g = mk()
        a, b = pair(g)
        g.relations.rel[rl.key(a, b)] = dict(kind="rival", since=0)
        g.social.bonds[rl.key(a, b)] = 30
        j = day(g)
        self.assertEqual(g.relations.kind(a, b), "friend")
        self.assertTrue(any("rivalry" in x for x in j))

    def test_friends_drift_apart(self):
        g = mk()
        a, b = pair(g)
        g.relations.rel[rl.key(a, b)] = dict(kind="friend", since=0)
        g.social.bonds[rl.key(a, b)] = 5
        day(g)
        self.assertIsNone(g.relations.kind(a, b))

    def test_couples_form_when_everything_fits(self):
        g = mk()
        a, b = lovebirds(g)
        day(g)
        day(g)
        self.assertEqual(g.relations.kind(a, b), "couple")
        self.assertEqual(g.relations.partner(a.id), b.id)
        self.assertGreater(a.emotions["joy"], 20)

    def test_no_couples_between_kin_or_when_taken(self):
        g = mk()
        a, b = lovebirds(g)
        b.parents = [a.id]
        day(g, n=3)
        self.assertNotEqual(g.relations.kind(a, b), "couple")
        b.parents = []
        c = g.slimes()[2]
        g.relations.rel[rl.key(a, c)] = dict(kind="couple", since=0)
        g.social.bonds[rl.key(a, c)] = 50
        day(g, n=3)
        self.assertNotEqual(g.relations.kind(a, b), "couple")

    def test_a_couple_can_split(self):
        g = mk()
        a, b = pair(g)
        g.relations.rel[rl.key(a, b)] = dict(kind="couple", since=0)
        g.social.bonds[rl.key(a, b)] = 10
        j = day(g)
        self.assertIsNone(g.relations.kind(a, b))
        self.assertGreater(a.emotions["sadness"], 20)
        self.assertTrue(any("split up" in x for x in j))

    def test_mentorship(self):
        g = mk()
        a, b = pair(g)
        a.level, b.level = 20, 5
        a.archetype = b.archetype = "barbarian"
        g.social.bonds[rl.key(a, b)] = 20
        day(g)
        self.assertEqual(g.relations.mentor_of(b.id), a.id)
        self.assertEqual(g.relations.mentees(a.id), [b.id])
        b.level = 19
        day(g)
        self.assertEqual(g.relations.kind(a, b), "friend")

    def test_mentees_earn_extra_xp(self):
        g = mk()
        a, b = pair(g)
        g.relations.rel[rl.key(a, b)] = dict(kind="mentor", since=0, mentor=a.id, mentee=b.id)
        self.assertEqual(g.relations.mentee_xp([a, b], 100), {b.id: 10})
        self.assertEqual(g.relations.mentee_xp([a], 100), {})

    def test_party_synergy_reflects_ties(self):
        g = mk()
        a, b = pair(g)
        self.assertEqual(g.relations.synergy_delta([a, b]), 0)
        g.relations.rel[rl.key(a, b)] = dict(kind="couple", since=0)
        self.assertGreater(g.relations.synergy_delta([a, b]), 0.02)
        g.relations.rel[rl.key(a, b)] = dict(kind="rival", since=0)
        self.assertLess(g.relations.synergy_delta([a, b]), 0)

    def test_loved_ones_and_rivals_stir_feelings_before_a_fight(self):
        g = mk()
        a, b, c, d = g.slimes()[:4]
        g.relations.rel[rl.key(a, b)] = dict(kind="couple", since=0)
        g.relations.rel[rl.key(c, d)] = dict(kind="rival", since=0)
        g.relations.prebattle([a, b, c, d], emotions)
        self.assertGreater(a.emotions["affection"], 5)
        self.assertGreater(c.emotions["determination"], 5)
        self.assertGreater(c.emotions["anger"], 2)

    def test_losing_a_partner_is_devastating(self):
        g = mk()
        a, b, c = g.slimes()[:3]
        g.relations.rel[rl.key(a, b)] = dict(kind="couple", since=0)
        b.hp = 0
        b.death_cause = "x"
        g._reap([])
        self.assertGreater(a.emotions["sadness"], 55)
        self.assertEqual(g.relations.of(b.id), [])
        self.assertLess(c.emotions.get("sadness", 0), a.emotions["sadness"])

    def test_relations_persist(self):
        g = mk()
        a, b = pair(g)
        g.relations.rel[rl.key(a, b)] = dict(kind="mentor", since=2, mentor=a.id, mentee=b.id)
        g.relations.quarrels[rl.key(a, b)] = 3
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.relations.mentor_of(b.id), a.id)
        self.assertEqual(h.relations.quarrels[rl.key(a, b)], 3)

    def test_the_game_reviews_ties_daily_in_its_own_dice(self):
        g = mk()
        a, b = pair(g)
        g.social.bonds[rl.key(a, b)] = 40
        g.tick(24)
        self.assertIsNotNone(g.relations.kind(a, b))
        self.assertTrue(any("friends" in j for j in g.journal))

    def test_quarrels_are_counted(self):
        g = mk()
        a, b = pair(g)
        g._social_hook("quarrel", a, b)
        g._social_hook("brawl", a, b)
        self.assertEqual(g.relations.quarrels[rl.key(a, b)], 2)


class TestBudding(unittest.TestCase):
    def couple(self, g, since=-20):
        a, b = pair(g)
        g.relations.rel[rl.key(a, b)] = dict(kind="couple", since=since, last_bud=-999)
        return a, b

    def test_requires_a_couple(self):
        g = mk()
        a, b = pair(g)
        with self.assertRaises(InvalidAction):
            g.bud(a.id, b.id)

    def test_new_couples_must_wait(self):
        g = mk()
        a, b = self.couple(g, since=g.day)
        with self.assertRaises(InvalidAction):
            g.bud(a.id, b.id)

    def test_a_child_is_born(self):
        g = mk()
        a, b = self.couple(g)
        a.traits, b.traits = ["kind"], ["brave"]
        n, food = len(g.roster), g.wallet.get("food")
        log = g.bud(a.id, b.id)
        kid = max(g.slimes(), key=lambda s: s.id)
        self.assertEqual(len(g.roster), n + 1)
        self.assertEqual(kid.parents, [a.id, b.id])
        self.assertEqual(kid.parent_names, [a.name, b.name])
        self.assertEqual(kid.generation, 1)
        self.assertEqual(kid.level, 1)
        self.assertIn(kid.archetype, (a.archetype, b.archetype))
        self.assertEqual(set(kid.traits), {"kind", "brave"})
        self.assertLess(g.wallet.get("food"), food)
        self.assertTrue(any("welcome a child" in x for x in log))
        self.assertGreater(a.emotions["joy"], 30)

    def test_cooldown_and_cost(self):
        g = mk()
        a, b = self.couple(g)
        g.bud(a.id, b.id)
        with self.assertRaises(InvalidAction):
            g.bud(a.id, b.id)
        g.tick_count += 24 * config.BUD_COOLDOWN_DAYS
        for s in (a, b):
            s.state = "idle"
        g.bud(a.id, b.id)
        g.wallet.add("food", -g.wallet.get("food"))
        g.tick_count += 24 * config.BUD_COOLDOWN_DAYS
        with self.assertRaises(NotEnoughResources):
            g.bud(a.id, b.id)

    def test_children_never_beat_the_parents_by_much(self):
        g = mk()
        a, b = pair(g)
        a.rarity, b.rarity = "common", "rare"
        rng = random.Random(1)
        got = [rl.child_rarity(a, b, rng) for _ in range(2000)]
        idx = [config.RARITIES.index(r) for r in got]
        self.assertGreater(idx.count(0), 800)                      # mostly the lower parent
        self.assertGreater(idx.count(2), 500)                      # often the higher
        self.assertLess(idx.count(3), 150)                         # rarely above both

    def test_stars_come_from_strong_parents(self):
        g = mk()
        a, b = pair(g)
        a.stars = b.stars = 1
        rng = random.Random(2)
        self.assertEqual({rl.child_stars(a, b, rng) for _ in range(200)}, {1})
        a.stars = b.stars = 5
        self.assertGreater(max(rl.child_stars(a, b, rng) for _ in range(300)), 1)

    def test_midwife_makes_it_cheaper(self):
        g = mk()
        g.keeper.ranks["midwife"] = 3
        a, b = self.couple(g)
        food = g.wallet.get("food")
        g.bud(a.id, b.id)
        self.assertEqual(food - g.wallet.get("food"), round(config.BUD_COST["food"] * 0.4))

    def test_child_name_blends_the_parents(self):
        g = mk()
        a, b = pair(g)
        a.name, b.name = "Plumbo", "Zikky"
        self.assertEqual(rl.child_name(a, b, random.Random(1)), "Plukky")

    def test_family_tree(self):
        g = mk()
        a, b = self.couple(g)
        g.bud(a.id, b.id)
        t = g.family_tree()
        self.assertEqual(len(t["families"]), 1)                    # one family unit, not two roots
        self.assertEqual(set(t["families"][0]["ids"]), {a.id, b.id})
        kid = max(g.slimes(), key=lambda s: s.id)
        self.assertEqual([c["id"] for c in t["families"][0]["children"]], [kid.id])
        self.assertEqual(len(t["ties"]["couple"]), 1)
        self.assertIsNotNone(t["ties"]["couple"][0]["bud_in"])

    def test_lineage_survives_saving_and_grief(self):
        g = mk()
        a, b = self.couple(g)
        g.bud(a.id, b.id)
        kid = max(g.slimes(), key=lambda s: s.id)
        h = Game.from_dict(g.to_dict())
        self.assertEqual(h.slime(kid.id).parents, [a.id, b.id])
        self.assertEqual(h.slime(kid.id).generation, 1)
        a.hp = 0
        a.death_cause = "x"
        g._reap([])
        tree = g.family_tree()
        fam = tree["families"][0]
        self.assertEqual(dict(zip(fam["ids"], fam["alive"]))[a.id], False)

    def test_grandchildren_extend_the_tree(self):
        g = mk()
        a, b = self.couple(g)
        g.bud(a.id, b.id)
        kid = max(g.slimes(), key=lambda s: s.id)
        c = g.slimes()[2]
        c.parents = []
        g.relations.rel[rl.key(kid, c)] = dict(kind="couple", since=-20, last_bud=-999)
        for s in (kid, c):
            s.state = "idle"
        g.bud(kid.id, c.id)
        self.assertEqual(max(s.generation for s in g.slimes()), 2)
        t = g.family_tree()
        self.assertTrue(any(ch["families"] for r in t["families"] for ch in r["children"]))


if __name__ == "__main__":
    unittest.main()
