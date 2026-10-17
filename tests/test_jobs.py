"""Appointments: trainers, librarian, blacksmith, brewer, chef, doctor - each in its own building."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import config, items, jobs
from slime_gacha.errors import InvalidAction
from slime_gacha.game import Game
from tests.test_delves import rich


def slime(g, cls="medic", stars=2):
    s = g.gacha.make_slime("common", cls, stars=stars)
    g.roster[s.id] = s
    return s


def quiet(g):
    g.needs.auto_care = False
    g.forage = False
    return g


class TestPosts(unittest.TestCase):
    def test_every_post_has_a_building_and_the_rules_hold(self):
        self.assertEqual({j.building for j in jobs.JOBS.values()},
                         {"training_grounds", "library", "armory", "alchemy", "kitchen", "hospital"})
        self.assertEqual(sorted(jobs.TRAINERS), ["archery", "magic", "sword"])
        g = quiet(rich(91))
        young, ok = slime(g, "barbarian", stars=1), slime(g, "barbarian", stars=2)
        with self.assertRaises(InvalidAction):
            g.assign_job(young.id, "trainer_sword")            # trainers need two stars
        g.assign_job(ok.id, "trainer_sword")
        self.assertEqual((ok.state, ok.job), ("working", "trainer_sword"))
        other = slime(g, "rogue")
        with self.assertRaises(InvalidAction):
            g.assign_job(other.id, "trainer_sword")            # one trainer per discipline
        g.assign_job(other.id, "trainer_archery")             # a different discipline has its own place
        self.assertEqual(jobs.slots(g, "trainer_magic"), 1)

    def test_only_medics_can_be_doctors(self):
        g = quiet(rich(92))
        with self.assertRaises(InvalidAction):
            g.assign_job(slime(g, "barbarian").id, "doctor")
        d = slime(g, "medic", stars=1)
        g.assign_job(d.id, "doctor")
        self.assertEqual(d.job, "doctor")

    def test_places_follow_the_building_level_and_switching_is_free(self):
        g = quiet(rich(93))
        a, b = slime(g), slime(g)
        g.assign_job(a.id, "chef")
        with self.assertRaises(InvalidAction):
            g.assign_job(b.id, "chef")                         # Kitchen level 1: one place
        g.buildings.levels["kitchen"] = 2
        g.assign_job(b.id, "chef")
        g.assign_job(a.id, "brewer")                           # switching
        self.assertEqual(a.job, "brewer")
        g.stop_job(b.id)
        self.assertEqual((b.state, b.job), ("idle", ""))
        with self.assertRaises(InvalidAction):
            g.assign_job(b.id, "juggler")

    def test_workers_are_off_limits_to_merging_and_saved(self):
        g = quiet(rich(94))
        a, b = slime(g), slime(g)
        g.assign_job(a.id, "chef")
        a.job_xp["chef"] = 7
        with self.assertRaises(InvalidAction):
            g.merge(b.id, a.id)
        h = Game.from_dict(g.to_dict())
        t = h.slime(a.id)
        self.assertEqual((t.state, t.job, t.job_xp), ("working", "chef", {"chef": 7}))

    def test_levels_and_talent(self):
        g = quiet(rich(95))
        s = slime(g, "medic")
        self.assertEqual(jobs.level(s, "chef"), 1)
        s.job_xp["chef"] = config.JOB_XP_STEP * 4
        self.assertEqual(jobs.level(s, "chef"), 3)
        self.assertGreater(jobs.power(s, "chef"), jobs.power(slime(g, "rogue"), "chef"))


class TestShifts(unittest.TestCase):
    def test_a_finished_shift_gives_xp_and_a_bonus(self):
        g = quiet(rich(96))
        lib = slime(g, "mage")
        g.assign_job(lib.id, "librarian")
        gel = g.wallet.get("white_gel")
        g.tick(jobs.SHIFT_HOURS - 1)
        self.assertEqual(lib.job_xp.get("librarian", 0), 0)
        g.tick(1)
        self.assertEqual(lib.job_xp["librarian"], 1)
        self.assertGreater(g.wallet.get("white_gel"), gel)

    def test_a_tired_worker_leaves_the_post(self):
        g = quiet(rich(97))
        s = slime(g)
        g.assign_job(s.id, "chef")
        s.needs.set("energy", config.AUTO_SLEEP_BELOW - 1)
        g.tick(1)
        self.assertEqual((s.state, s.job), ("idle", ""))

    def test_a_worker_with_nothing_to_do_forages_and_can_be_called_back(self):
        g = quiet(rich(98))
        g.wallet.add("food", -g.wallet.get("food"))              # nothing to cook with
        chef = slime(g, "medic")
        chef.stage = 1
        g.assign_job(chef.id, "chef")
        g.tick(jobs.SHIFT_HOURS)
        self.assertEqual(chef.state, "hunting")
        self.assertEqual(chef.job, "chef")                      # keeps the post while away
        self.assertIn("called back", g.recall(chef.id))
        self.assertEqual((chef.state, chef.job), ("working", "chef"))
        g.tick(jobs.SHIFT_HOURS)                                 # a foraging shift also ends by itself and resumes
        self.assertEqual(chef.state, "hunting")
        g.tick(3)
        self.assertIn(chef.state, ("working", "idle"))
        g.tick(1)
        self.assertEqual(chef.state, "working")

    def test_trainers_librarians_never_forage(self):
        g = quiet(rich(99))
        t = slime(g, "ranger")
        g.assign_job(t.id, "trainer_archery")
        g.tick(jobs.SHIFT_HOURS * 2)
        self.assertEqual(t.state, "working")

    def test_post_holders_and_party_members_do_not_forage_by_themselves(self):
        g = quiet(rich(100))
        g.forage = True
        p = g.create_party("P")
        member, worker = slime(g, "barbarian"), slime(g, "barbarian")
        g.parties.add(p.id, member.id)
        g.assign_job(worker.id, "trainer_sword")
        for s in (member, worker):
            s.stage = 2
            s.hp = s.max_hp
        g.tick(1)
        self.assertEqual(member.state, "idle")
        self.assertEqual(worker.state, "working")


class TestTrainers(unittest.TestCase):
    def test_an_appointed_trainer_speeds_up_drills_in_their_discipline_only(self):
        g = quiet(rich(101))
        self.assertEqual(jobs.trainer_bonus(g, "sword"), 1.0)
        t = slime(g, "barbarian")
        g.assign_job(t.id, "trainer_sword")
        self.assertGreater(jobs.trainer_bonus(g, "sword"), 1.0)
        self.assertEqual(jobs.trainer_bonus(g, "magic"), 1.0)
        a, b = slime(g, "barbarian"), slime(g, "barbarian")
        a.class_prof = b.class_prof = 30.0
        with_trainer = g.academy.drill_gain(a, "sword")
        g.stop_job(t.id)
        self.assertGreater(with_trainer, g.academy.drill_gain(b, "sword"))

    def test_the_bonus_grows_with_the_trainers_level_and_the_building(self):
        g = quiet(rich(102))
        t = slime(g, "barbarian")
        g.assign_job(t.id, "trainer_sword")
        low = jobs.trainer_bonus(g, "sword")
        t.job_xp["trainer_sword"] = config.JOB_XP_STEP * 9
        mid = jobs.trainer_bonus(g, "sword")
        g.buildings.levels["training_grounds"] = 5
        self.assertGreater(mid, low)
        self.assertGreater(jobs.trainer_bonus(g, "sword"), mid)


class TestLibrarian(unittest.TestCase):
    def test_librarian_hurries_students_and_teaches(self):
        g = quiet(rich(103))
        lib, student, scholar = slime(g, "mage"), slime(g, "mage"), slime(g, "mage")
        for s in (student, scholar):
            s.attuned, s.stars = ["fire"], 3
        g.assign_job(lib.id, "librarian")
        student.state, student.task = "studying", dict(kind="study", ticks_left=20, total=20, element="fire")
        g.tick(jobs.SHIFT_HOURS)
        self.assertLess(student.task["ticks_left"], 20 - jobs.SHIFT_HOURS)
        self.assertGreater(scholar.mastery_xp.get("fire", 0), 0)


class TestBlacksmith(unittest.TestCase):
    def test_mends_gear_and_slowly_forges_a_weapon_then_a_relic(self):
        g = quiet(rich(104))
        smith, owner = slime(g, "barbarian"), slime(g)
        it = items.Item(7, "iron_sword")
        it.durability = 1
        owner.items["weapon"] = it
        g.wallet.add("scrap", 50)
        g.assign_job(smith.id, "blacksmith")
        g.tick(jobs.SHIFT_HOURS)
        self.assertGreater(it.durability, 1)                       # mended for free
        stock = sum(g.inventory.items.values())
        vault = len(g.vault)
        g.tick(jobs.SHIFT_HOURS * (config.CRAFT_SHIFTS - 1))
        self.assertGreater(sum(g.inventory.items.values()), stock)  # a weapon came out of the forge
        g.tick(jobs.SHIFT_HOURS * config.CRAFT_SHIFTS)
        self.assertGreater(len(g.vault), vault)                    # then a relic

    def test_without_materials_nothing_is_forged(self):
        g = quiet(rich(105))
        for k in ("white_gel", "scrap", "essence", "purple_gel"):
            g.wallet.add(k, -g.wallet.get(k))
        smith = slime(g, "barbarian")
        g.assign_job(smith.id, "blacksmith")
        g.tick(jobs.SHIFT_HOURS * config.CRAFT_SHIFTS)
        self.assertEqual(sum(g.inventory.items.values()), 0)
        self.assertEqual(smith.state, "hunting")                    # nothing to do: it goes foraging


class TestBrewer(unittest.TestCase):
    def test_brews_a_potion_from_the_herbs_on_hand(self):
        g = quiet(rich(106))
        for h in ("herb_green", "herb_red", "herb_blue", "herb_yellow"):
            g.wallet.add(h, 100)
        b = slime(g, "medic")
        g.assign_job(b.id, "brewer")
        g.rng.random = lambda: 0.0
        g.tick(jobs.SHIFT_HOURS)
        self.assertGreater(sum(g.potions.values()), 0)
        self.assertEqual(b.job_xp.get("brewer"), 1)


class TestKitchen(unittest.TestCase):
    def test_chef_cooks_into_the_pantry_and_hungry_slimes_eat_from_it(self):
        g = rich(107)
        g.needs.auto_care = True
        g.forage = False
        chef, guest = slime(g, "medic"), slime(g, "barbarian")
        g.assign_job(chef.id, "chef")
        g.tick(jobs.SHIFT_HOURS)
        self.assertGreater(jobs.pantry_total(g), 0)
        food = g.wallet.get("food")
        guest.needs.set("food", config.AUTO_EAT_BELOW - 1)
        guest.state = "idle"
        g.tick(1)
        self.assertGreater(guest.needs.get("food"), config.AUTO_EAT_BELOW)
        self.assertEqual(g.wallet.get("food"), food)                # the meal came from the pantry, not the stores

    def test_recipes_unlock_with_level_and_the_pick_is_honoured(self):
        g = quiet(rich(108))
        g.wallet.add("herb_green", 5)
        chef = slime(g, "medic")
        g.assign_job(chef.id, "chef")
        self.assertEqual(jobs.pick_recipe(g, chef).key, "porridge")
        chef.job_xp["chef"] = config.JOB_XP_STEP * 1
        self.assertEqual(jobs.pick_recipe(g, chef).key, "stew")
        g.recipe_pref = "porridge"
        self.assertEqual(jobs.pick_recipe(g, chef).key, "porridge")
        g.recipe_pref = "feast"
        self.assertIsNone(jobs.pick_recipe(g, chef))                # not unlocked yet

    def test_the_pantry_is_capped_by_the_kitchen_level_and_hunger_is_counted(self):
        g = quiet(rich(109))
        self.assertEqual(jobs.pantry_cap(g), config.PANTRY_PER_LEVEL)
        g.pantry["porridge"] = jobs.pantry_cap(g)
        chef = slime(g, "medic")
        g.assign_job(chef.id, "chef")
        g.tick(jobs.SHIFT_HOURS)
        self.assertEqual(jobs.pantry_total(g), jobs.pantry_cap(g))   # full: no more cooking
        a = slime(g, "barbarian")
        a.needs.set("food", 10)
        self.assertIn(a, jobs.hungry(g))
        self.assertEqual(Game.from_dict(g.to_dict()).pantry, g.pantry)


class TestHospital(unittest.TestCase):
    def test_a_doctor_heals_the_injured_every_hour_and_they_are_counted(self):
        g = quiet(rich(110))
        doc, patient = slime(g, "medic"), slime(g, "barbarian")
        patient.hp = 1
        hurt, wounded = jobs.injured(g)
        self.assertIn(patient, hurt)
        self.assertIn(patient, wounded)
        g.tick(1)
        before = patient.hp
        g.assign_job(doc.id, "doctor")
        g.tick(1)
        self.assertGreater(patient.hp, before)
        g.buildings.levels["hospital"] = 5
        h = patient.hp
        g.tick(1)
        self.assertGreater(patient.hp - h, 0)
        g.tick(10)
        self.assertEqual(patient.hp, patient.max_hp)


if __name__ == "__main__":
    unittest.main()
