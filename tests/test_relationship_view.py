"""A slime card's Relationships tab: ties with the bond, slimes it is growing close to or clashing with, its children."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha.webapi import Session


class TestRelationshipsView(unittest.TestCase):
    def test_a_slime_view_lists_its_ties_neighbours_and_children(self):
        se = Session()
        se.call("new_game", {})
        g = se.game
        g.wallet.add("white_gel", 5000)
        g.pull(5, "white_gel")
        a, b, c, d = [s.id for s in g.slimes()[:4]]
        g.relations.rel[frozenset((a, b))] = dict(kind="couple", since=0)
        g.social.bonds[frozenset((a, b))] = 60
        g.social.bonds[frozenset((a, c))] = 20
        g.social.bonds[frozenset((a, d))] = -25
        g.roster[d].parents = [a, b]
        v = next(x for x in se.call("state")["state"]["slimes"] if x["id"] == a)
        self.assertEqual(v["relations"], [dict(other=b, kind="couple", since=0, mentor=None, bond=60)])
        self.assertEqual(v["near"], [dict(other=c, bond=20)])                  # no tie yet, growing close
        self.assertEqual(v["friction"], [dict(other=d, bond=-25)])
        self.assertEqual(v["children"], [d])


if __name__ == "__main__":
    unittest.main()
