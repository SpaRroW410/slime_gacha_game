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


class TestRefusals(unittest.TestCase):
    def test_slimes_refuse_posts_and_expeditions_when_exhausted_hurt_or_bleak(self):
        g = quiet(rich(92))
        s = slime(g, "medic")
        self.assertEqual(g.refusal(s, "job"), "")
        s.needs.set("energy", 5)
        self.assertIn("exhausted", g.refusal(s, "job"))
        with self.assertRaises(InvalidAction):
            g.assign_job(s.id, "doctor")
        s.needs.set("energy", 80)
        s.hp = s.max_hp * 0.3                                  # hurt enough for an expedition to be refused, not a post
        self.assertEqual(g.refusal(s, "job"), "")
        self.assertIn("hurt", g.refusal(s, "dungeon"))
        with self.assertRaises(InvalidAction):
            g.hunt(s.id, "pond")
        s.hp = s.max_hp
        s.emotions["anger"] = 90
        self.assertIn("rage", g.refusal(s, "job"))

    def test_a_sleeper_can_be_appointed_and_wake_all_spares_the_exhausted(self):
        g = quiet(rich(93))
        a, b, c = slime(g, "medic"), slime(g, "medic"), slime(g, "medic")
        for s in (a, b, c):
            s.state = "sleeping"
        a.needs.set("energy", 80)
        b.needs.set("energy", 5)
        c.needs.set("energy", 30)
        out = g.wake_all()
        self.assertEqual((a.state, b.state, c.state), ("idle", "sleeping", "idle"))
        self.assertTrue(any("under 10%" in l for l in out))
        a.state = "sleeping"
        g.assign_job(a.id, "doctor")
        self.assertEqual(a.state, "working")


class TestViceKeeperWorks(unittest.TestCase):
    def test_the_vice_keeper_can_hold_a_post_and_still_reach_slimes_at_home(self):
        g = quiet(rich(94))
        v, other = slime(g, "medic", stars=4), slime(g, "rogue")
        g.appoint_vice(v.id)
        g.assign_job(v.id, "doctor")
        self.assertEqual((v.state, v.job), ("working", "doctor"))
        self.assertTrue(g.vice_reaches(other))
        w = slime(g, "medic", stars=4)
        g.assign_job(w.id, "brewer")
        g.appoint_vice(w.id)                                   # a worker can also be made Vice Keeper
        self.assertEqual(g.vice, w.id)


class TestServing(unittest.TestCase):
    def test_dishes_can_be_served_by_hand(self):
        g = quiet(rich(95))
        a, b = slime(g), slime(g)
        a.needs.set("food", 10)
        b.needs.set("food", 20)
        with self.assertRaises(InvalidAction):
            g.serve(a.id)                                       # nothing cooked yet
        g.pantry = {"stew": 1} if "stew" in jobs.RECIPES else {next(iter(jobs.RECIPES)): 1}
        out = g.serve_hungry()
        self.assertEqual(len([l for l in out if "served" in l]), 1)   # one dish: the hungriest gets it
        self.assertGreater(a.needs.get("food"), 10)
        self.assertEqual(b.needs.get("food"), 20)
        self.assertIn("ran out", " ".join(out))
        self.assertEqual(g.pantry, {})


class TestHospitalWard(unittest.TestCase):
    def hurt(self, g, s):
        s.hp = max(1, int(s.max_hp * 0.2))
        s.needs.set("food", 90)

    def test_ward_patients_heal_faster_with_a_doctor_and_leave_healed(self):
        g = quiet(rich(96))
        a, b, doc = slime(g), slime(g), slime(g, "medic", stars=2)
        for s in (a, b):
            s.level = 30                                          # enough HP for the percentages to show
            self.hurt(g, s)
        g.admit(a.id)
        self.assertEqual((a.state, g.ward_count(), g.resting_count()), ("resting", 1, 0))
        g.tick(1)
        no_doc = a.hp - int(a.max_hp * 0.2)
        g.rest(b.id)                                              # the Rest Area for comparison
        g.assign_job(doc.id, "doctor")
        a.hp = int(a.max_hp * 0.2)
        b.hp = int(b.max_hp * 0.2)
        g.tick(1)
        with_doc = a.hp - int(a.max_hp * 0.2)
        rest_gain = b.hp - int(b.max_hp * 0.2)
        self.assertGreater(with_doc, rest_gain)
        self.assertGreaterEqual(no_doc, rest_gain - 1)             # without a doctor the ward is about the Rest Area's pace
        for _ in range(30):
            g.tick(1)
        self.assertEqual((a.hp, a.state), (a.max_hp, "idle"))
        self.assertEqual(g.ward, [])

    def test_the_ward_is_limited_and_calling_back_frees_a_bed(self):
        g = quiet(rich(97))
        ss = [slime(g) for _ in range(3)]
        for s in ss:
            self.hurt(g, s)
        g.admit(ss[0].id)
        g.admit(ss[1].id)                                         # level 1: two beds
        with self.assertRaises(InvalidAction):
            g.admit(ss[2].id)
        g.recall(ss[0].id)
        self.assertEqual(ss[0].state, "idle")
        g.admit(ss[2].id)
        with self.assertRaises(InvalidAction):
            g.admit(ss[0].id) if False else g.admit(slime(g).id)  # not hurt: nothing to treat
