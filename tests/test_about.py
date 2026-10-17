"""The About page: version, summary, sections and a roadmap that matches docs/TASKS.md."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import about, config
from slime_gacha.webapi import Session, snapshot
from tests.test_delves import rich


class TestAbout(unittest.TestCase):
    def test_version_and_command(self):
        self.assertEqual(config.VERSION, "1.001")
        s = Session()
        s.call("new_game", {"seed": 3})
        r = s.call("about")
        self.assertTrue(r["ok"])
        res = r["result"]
        self.assertEqual(res["version"], "1.001")
        self.assertTrue(res["summary"] and res["sections"] and res["roadmap"])
        self.assertEqual(snapshot(rich(1))["version"], "1.001")

    def test_sections_have_content(self):
        for sec in about.SECTIONS:
            self.assertTrue(sec["title"] and sec["items"])

    def test_the_roadmap_matches_the_unchecked_tasks(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "TASKS.md")
        if not os.path.exists(path):
            self.skipTest("docs not shipped")
        with open(path, encoding="utf-8") as f:
            open_ids = {int(m.group(1)) for m in re.finditer(r"^- \[[ ~]\] \*\*(\d+)\.", f.read(), re.M)}
        self.assertEqual({r["id"] for r in about.ROADMAP}, open_ids)


if __name__ == "__main__":
    unittest.main()
