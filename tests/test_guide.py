import unittest

from slime_gacha import elements, guide, specialization


class TestGuide(unittest.TestCase):
    def setUp(self):
        self.g = {s["title"]: s for s in guide.build()}

    def test_every_section_has_items(self):
        for t, s in self.g.items():
            self.assertTrue(s["items"], t)
            for i in s["items"]:
                self.assertTrue(i["name"] and i["text"], t)

    def test_elements_and_specialization_live_in_the_guide(self):
        el = self.g["Elements and spells"]
        names = " ".join(i["name"] for i in el["items"])
        for pair, res in elements.RECIPES.items():
            self.assertIn(elements.get(res).name, names)
        spec = self.g["Specialization (hybrid classes)"]
        for sp in specialization.SPECS.values():
            self.assertTrue(any(sp.name in i["name"] for i in spec["items"]), sp.name)

    def test_api_serves_it(self):
        from slime_gacha.webapi import Session
        s = Session()
        s.call("new_game", {"seed": 1})
        r = s.call("guide")
        self.assertTrue(r["ok"])
        self.assertIn("Specialization (hybrid classes)", [x["title"] for x in r["result"]["sections"]])


if __name__ == "__main__":
    unittest.main()
