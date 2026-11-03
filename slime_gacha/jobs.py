"""Appointments: non-combat posts for slimes, each in its own building (no wages; it makes gentle slimes useful).

A slime appointed to a post is "working": it stays in town (it can still be fed and petted) but is not free for
parties, hunts or merging until you dismiss it. Switching posts is free. Work runs in SHIFTS of three hours: a shift
that is carried through gives the post's output and a small bonus resource. A post's output grows with the worker's
level in that trade (earned per shift, kept when switching), a natural talent (+25%) and the building's level
(+10% per level above 1).

  Trainers (3)   Training Grounds   one per discipline (sword / archery / magic), 2 stars or more, and a class that fights
                                    in that discipline (a swordsman cannot teach magic): faster proficiency and fighting-style
                                    gains for drills and spars in their discipline, but only for pupils whose own proficiency
                                    in it is lower than the trainer's
  Librarian      Library            hurries students along and gives attuned slimes mastery
  Blacksmith     Armory             mends worn gear and, slowly, forges weapons and relics from the colony's materials
  Brewer         Alchemy Lab        brews basic potions from herbs the colony holds
  Chef           Kitchen            cooks the recipe you pick into the pantry; hungry slimes eat from it
  Doctor         Hospital           a medic only: heals injured slimes at home every hour

A chef, blacksmith, brewer or doctor with nothing to do on a shift goes foraging for those three hours; you can
call them back at once, and they take up their post again when they return.
"""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import attributes, config, elements, emotions, equipment
from .buildings import BUILDINGS
from .errors import InvalidAction, NotEnoughResources

SHIFT_HOURS = 3


@dataclass(frozen=True)
class Job:
    key: str
    name: str
    emoji: str
    building: str                   # the building that hosts the post
    desc: str
    talents: Tuple[str, ...] = ()   # classes with a natural knack (+25%)
    min_stars: int = 1
    classes: Tuple[str, ...] = ()   # only these classes may hold the post (empty = any)
    discipline: str = ""            # trainers: the discipline they teach
    forages: bool = False           # idle shifts go foraging


JOBS: Dict[str, Job] = {j.key: j for j in (
    Job("trainer_sword", "Sword Trainer", "🗡️", "training_grounds", "Drills and sparring in the sword style gain proficiency faster for pupils who know less than the trainer.",
        ("barbarian", "rogue"), 2, (), "sword"),
    Job("trainer_archery", "Archery Trainer", "🏹", "training_grounds", "Drills and sparring in the archery style gain proficiency faster for pupils who know less than the trainer.",
        ("ranger", "rogue"), 2, (), "archery"),
    Job("trainer_magic", "Magic Trainer", "🔮", "training_grounds", "Drills and sparring in the magic style gain proficiency faster for pupils who know less than the trainer.",
        ("mage", "necromancer"), 2, (), "magic"),
    Job("librarian", "Librarian", "📚", "library", "Hurries students along and catalogues lore: attuned slimes at home gain mastery.",
        ("mage", "necromancer")),
    Job("blacksmith", "Blacksmith", "🔨", "armory", "Mends worn gear and, slowly, forges weapons and relics from the colony's materials.",
        ("barbarian", "ranger"), forages=True),
    Job("brewer", "Brewer", "⚗️", "alchemy", "Brews basic potions from the herbs the colony holds.",
        ("medic", "necromancer"), forages=True),
    Job("chef", "Chef", "🍳", "kitchen", "Cooks the chosen recipe into the pantry; hungry slimes eat from it.",
        ("medic", "mage"), forages=True),
    Job("doctor", "Doctor", "🩺", "hospital", "Heals every injured slime at home, every hour. Only medics may be doctors.",
        ("medic",), 1, ("medic",), forages=True),
)}
TRAINERS = {j.discipline: j.key for j in JOBS.values() if j.discipline}
TRADE_PASSIVE = dict(chef="chef_master", blacksmith="blacksmith_master", doctor="doctor_master", librarian="librarian_master")   # output passives (passives.py)


def get(key: str) -> Job:
    if key not in JOBS:
        raise InvalidAction(f"Unknown post '{key}'. Choose from: {', '.join(JOBS)}.")
    return JOBS[key]


def xp_for(level: int) -> int:
    """Shifts of work needed to reach `level`."""
    return config.JOB_XP_STEP * (level - 1) ** 2


def level(slime, key: str) -> int:
    xp = slime.job_xp.get(key, 0)
    return min(config.JOB_MAX_LEVEL, 1 + int(math.sqrt(xp / config.JOB_XP_STEP)))


def power(slime, key: str, game=None) -> float:
    """Output multiplier: 1.0 at level 1, +12% per level, +25% for a natural talent, +10% per building level above 1."""
    p = 1 + 0.12 * (level(slime, key) - 1)
    p *= 1.25 if slime.archetype in JOBS[key].talents else 1.0
    if game is not None and key in TRADE_PASSIVE:
        from . import passives
        if passives.has(game, slime, TRADE_PASSIVE[key]):
            p *= 1 + config.TRADE_PASSIVE_BOOST            # the trade mastered: its output is bigger
    return p * (game.buildings.job_mult(JOBS[key].building) if game else 1.0)


def slots(game, key: str) -> int:
    if JOBS[key].discipline:
        return 1                                        # one trainer per discipline
    return game.buildings.job_slots(JOBS[key].building)


def workers(game, key: str = "") -> List:
    """Slimes holding a post (at work, or out foraging on an idle shift)."""
    return [s for s in game.slimes() if s.job and (not key or s.job == key)]


def holder(game, key: str):
    ws = workers(game, key)
    return ws[0] if ws else None


def why_not(game, slime, key: str) -> str:
    """Why this slime cannot take the post right now ("" = it can)."""
    job = get(key)
    if slime.job == key:
        return "already holds this post"
    if slime.state not in ("idle", "working", "hunting", "sleeping", "resting") or slime.in_dungeon:
        return f"is {slime.in_dungeon and 'inside a dungeon' or slime.state}"
    if slime.state == "hunting" and not slime.job:
        return "is out hunting"
    if slime.grounded:
        return "is grounded after a brawl"
    if slime.stars < job.min_stars:
        return f"needs {job.min_stars}+ stars"
    if job.classes and slime.archetype not in job.classes:
        return "only " + "/".join(job.classes) + "s may hold this post"
    if job.discipline and teaching_prof(slime, job) is None:
        return f"does not fight in the {job.discipline} style (a {slime.arch.name} cannot teach it)"
    if (why := game.refusal(slime, "job")):
        return why
    if slime.needs.get("energy") < config.TASK_MIN_ENERGY:
        return "is too tired"
    party = game.parties.party_of(slime.id)
    if party and party.id in game.delves:
        return "party is in the Descent"
    return ""


def assign(game, slime, key: str) -> str:
    job = get(key)
    reason = why_not(game, slime, key)
    if reason:
        raise InvalidAction(f"{slime.name} {reason}.")
    others = [s for s in workers(game, key) if s is not slime]
    if len(others) >= slots(game, key):
        raise InvalidAction(f"All {slots(game, key)} place(s) for the {job.name.lower()} are taken. "
                            f"{'Upgrade the ' + BUILDINGS.get(job.building).name + ' or ' if not job.discipline else ''}dismiss someone first.")
    woke = ""
    if slime.state == "sleeping":
        woke = game._rouse(slime) + " "
    if slime.job:
        stop(game, slime)
    if slime.state == "hunting":
        game.hunts.recall(slime)
    slime.job, slime.job_clock, slime.state = key, 0, "working"
    return woke + f"{slime.name} takes up the post of {job.name.lower()} (level {level(slime, key)})."


def stop(game, slime) -> str:
    if not slime.job:
        raise InvalidAction(f"{slime.name} holds no post.")
    if slime.state == "hunting":
        game.hunts.recall(slime)
    slime.state, slime.job, slime.job_clock = "idle", "", 0
    return f"{slime.name} hangs up the apron."


def recall(game, slime) -> str:
    """Call a worker back from a foraging shift at once, to take up the post again."""
    if not slime.job or slime.state != "hunting":
        raise InvalidAction(f"{slime.name} is not out foraging.")
    game.hunts.recall(slime)
    slime.state, slime.job_clock = "working", 0
    return f"📞 {slime.name} is called back through the portal and returns to the {JOBS[slime.job].name.lower()}'s post."


# ---- day plans ------------------------------------------------------------------------------------------------------------
# A post can follow a plan for the whole day: eight 3-hour shifts, each work / forage / sleep, plus up to three "if" rules that are
# checked at the start of every shift and win over the slot ("if nobody is hurt: forage", "if the pantry holds 10+ days: sleep").
PLAN_SLOTS = 24 // SHIFT_HOURS
PLAN_ACTIONS = ("work", "forage", "sleep")
PLAN_CONDITIONS = {"always": "always", "no_patients": "nobody is hurt at home", "hurt_ge": "N or more slimes are hurt",
                   "pantry_days_ge": "the pantry holds N days of food or more", "pantry_days_lt": "the pantry holds under N days of food",
                   "energy_lt": "my energy is under N%"}
PLAN_MAX_RULES = 3


def pantry_days(game) -> float:
    """Days of food the pantry holds, at about one serving per slime per day."""
    return pantry_total(game) / max(1, len(game.slimes()))


def _rule_holds(game, s, cond: str, n: float) -> bool:
    if cond == "always":
        return True
    if cond == "no_patients":
        return not injured(game)[0]
    if cond == "hurt_ge":
        return len(injured(game)[0]) >= n
    if cond == "pantry_days_ge":
        return pantry_days(game) >= n
    if cond == "pantry_days_lt":
        return pantry_days(game) < n
    if cond == "energy_lt":
        return s.needs.get("energy") < n
    return False


def plan_action(game, s) -> str:
    """What this worker does in the shift that starts now: the first matching rule, else the plan's slot, else work."""
    plan = game.plans.get(s.job)
    if not plan:
        return "work"
    for r in plan.get("rules", []):
        if _rule_holds(game, s, r["if"], r.get("n", 0)):
            return r["do"]
    slot = (game.tick_count // SHIFT_HOURS) % PLAN_SLOTS
    return (plan.get("slots") or ["work"] * PLAN_SLOTS)[slot]


def set_plan(game, key: str, slots, rules) -> str:
    get(key)
    slots = [str(x) for x in (slots or [])][:PLAN_SLOTS]
    slots += ["work"] * (PLAN_SLOTS - len(slots))
    if any(x not in PLAN_ACTIONS for x in slots):
        raise InvalidAction("A shift is work, forage or sleep.")
    clean = []
    for r in list(rules or [])[:PLAN_MAX_RULES]:
        cond, do = str(r.get("if", "")), str(r.get("do", ""))
        if cond not in PLAN_CONDITIONS or do not in PLAN_ACTIONS:
            raise InvalidAction("Unknown rule.")
        clean.append(dict({"if": cond, "do": do}, n=float(r.get("n", 0) or 0)))
    if all(x == "work" for x in slots) and not clean:
        game.plans.pop(key, None)
        return f"The {get(key).name.lower()} works every shift again."
    game.plans[key] = dict(slots=slots, rules=clean)
    return f"📅 Day plan saved for the {get(key).name.lower()}."


# ---- time -------------------------------------------------------------------------------------------------------------
def tick(game, events: List[str]) -> None:
    for s in list(game.slimes()):
        if not s.job:
            continue
        if s.state == "hunting":                                    # on a foraging shift: the hunt brings them back
            continue
        if s.state == "idle":                                       # back from foraging: take the post up again
            s.state, s.job_clock = "working", 0
            continue
        if s.state == "sleeping":                                   # a planned sleep shift: back at the post when it is over (or rested)
            s.job_clock += 1
            if s.job_clock >= SHIFT_HOURS:
                s.state, s.job_clock = "working", 0
            continue
        if s.state != "working":
            continue
        if s.job_clock == 0 and s.job in game.plans:                # a new shift begins: the day plan decides what it is
            act = plan_action(game, s)
            if act == "sleep":
                s.state, s.job_clock = "sleeping", 1
                events.append(f"😴 {s.name} sleeps through this shift (day plan).")
                continue
            if act == "forage":
                _forage(game, s, events, planned=True)
                if s.state == "hunting":
                    continue
        if s.needs.get("energy") < config.AUTO_SLEEP_BELOW:          # too weary to carry on: leaves the post to sleep
            events.append(f"😴 {s.name} is too tired to keep working as a {JOBS[s.job].name.lower()}.")
            s.state, s.job, s.job_clock = "idle", "", 0
            continue
        s.needs.add("energy", -config.JOB_ENERGY_PER_HOUR)
        job = JOBS[s.job]
        if s.job == "doctor":
            _ward_round(game, s, events)                            # the doctor works every hour
        s.job_clock += 1
        if s.job_clock < SHIFT_HOURS:
            continue
        s.job_clock = 0
        done = RUNNERS[s.job](game, s, events)
        if done:
            s.job_xp[s.job] = s.job_xp.get(s.job, 0) + 1
            s.needs.add("esteem", 2)
            _bonus(game, s, events)
            if level(s, s.job) > level_before(s):
                events.append(f"⭐ {s.name} reaches level {level(s, s.job)} as a {job.name.lower()}!")
        elif job.forages:
            _forage(game, s, events)


def level_before(s) -> int:
    xp = s.job_xp.get(s.job, 0) - 1
    return min(config.JOB_MAX_LEVEL, 1 + int(math.sqrt(max(0, xp) / config.JOB_XP_STEP)))


def _bonus(game, s, events: List[str]) -> None:
    """A shift carried through earns a little something extra."""
    lvl = level(s, s.job)
    got = {"white_gel": game.rng.randint(1, 2 + lvl)}
    if game.rng.random() < 0.15 + 0.03 * lvl:
        got["essence"] = 1
    game.wallet.add_many(got)
    events.append(f"💰 {s.name}'s shift bonus: " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in got.items()) + ".")


def _forage(game, s, events: List[str], planned: bool = False) -> None:
    """Nothing to do this shift (or the day plan says so): go foraging for three hours (call back at any time)."""
    try:
        game.hunts.start_from_post(s)
    except InvalidAction:
        return
    events.append(f"🧺 {s.name} " + ("forages this shift (day plan)." if planned else
                  f"has nothing to do at the {JOBS[s.job].name.lower()}'s post and goes foraging for {SHIFT_HOURS}h."))


def at_home(game, exclude=None) -> list:
    return [o for o in game.slimes() if o is not exclude and not o.in_dungeon and o.state not in ("hunting", "studying")
            and o.hp > 0]


# ---- trainers -------------------------------------------------------------------------------------------------------
def proficiency_in(slime, discipline: str) -> Optional[float]:
    """The slime's proficiency in a discipline: its class's own, or its second (specialised) one; None if it has neither."""
    if slime.arch.discipline == discipline:
        return slime.class_prof
    if slime.spec and slime.spec_disc == discipline:
        return slime.spec_prof
    return None


def teaching_prof(slime, job: Job) -> Optional[float]:
    """What a trainer's pupils are measured against: its proficiency in the post's discipline, whether that is its class's own,
    its second one, or (for a class with a natural knack for the post, like a rogue's archery) its class proficiency. None: it cannot teach."""
    p = proficiency_in(slime, job.discipline)
    return slime.class_prof if p is None and slime.archetype in job.talents else p


def trainer_bonus(game, discipline: str, pupil=None) -> float:
    """Multiplier on proficiency and style gains in a discipline while its trainer is appointed (1.0 without).
    The trainer must fight in that discipline, and with a `pupil` given only teaches one whose own proficiency in it is
    lower than the trainer's (nobody can teach themselves, and a master has nothing to learn from a novice)."""
    key = TRAINERS.get(discipline)
    t = holder(game, key) if key else None
    if t is None or t.state not in ("working", "hunting"):
        return 1.0
    mine = teaching_prof(t, JOBS[key])
    if mine is None:
        return 1.0
    if pupil is not None and (proficiency_in(pupil, discipline) or 0.0) >= mine:
        return 1.0
    b = config.TRAINER_BONUS + config.TRAINER_BONUS_PER_LEVEL * (level(t, key) - 1)
    b *= 1.25 if t.archetype in JOBS[key].talents else 1.0
    from . import passives
    if passives.has(game, t, "master_" + discipline):
        b *= 1 + config.MASTER_TRAINER_BOOST
    return 1 + b * game.buildings.job_mult("training_grounds")


def lesson(game, discipline: str, pupil) -> None:
    """A lesson was given in `discipline`: if the trainer's teaching helped this pupil, the trainer sharpens a little too."""
    if trainer_bonus(game, discipline, pupil) <= 1.0:
        return
    t = holder(game, TRAINERS[discipline])
    attributes.practise(t, discipline, config.TRAINER_LESSON_GAIN, config.TRAINER_LESSON_OTHER)


def _teach(game, trainer, events: List[str]) -> bool:
    return True                                                     # the lessons themselves are the trainer_bonus on gains


# ---- librarian ------------------------------------------------------------------------------------------------------
def _lore(game, librarian, events: List[str]) -> bool:
    p = power(librarian, "librarian", game)
    helped = []
    for o in game.slimes():                                         # students finish sooner
        if o.state == "studying" and o.task and o.task.get("ticks_left", 0) > 1:
            o.task["ticks_left"] = max(1, o.task["ticks_left"] - max(1, int(round(p))))
            helped.append(o.name)
    scholars = [o for o in at_home(game, librarian) if o.attuned and o.state == "idle"]
    note = ""
    if scholars:
        o = min(scholars, key=lambda x: min(elements.basic_level(x, b) for b in x.attuned))
        e = min(o.attuned, key=lambda b: elements.basic_level(o, b))
        elements.add_mastery_xp(o, e, config.LIBRARIAN_LORE_XP * p)
        note = f"; {o.name} learns from the shelves ({elements.get(e).name})"
        helped.append(o.name)
    if helped:
        events.append(f"📚 {librarian.name} hurries the students along{note}.")
    return True                                                     # a librarian always has books to tend


# ---- blacksmith ------------------------------------------------------------------------------------------------------
def _forge(game, smith, events: List[str]) -> bool:
    p = power(smith, "blacksmith", game)
    share = config.SMITH_MEND_SHARE * p
    left = config.SMITH_ITEMS + level(smith, "blacksmith") // 2
    fixed = []
    for o in sorted(at_home(game), key=lambda o: o.id):
        for it in o.items.values():
            if left <= 0:
                break
            if it.unbreakable or it.durability >= it.max_durability:
                continue
            it.durability = min(it.max_durability, it.durability + max(1, int(it.max_durability * share)))
            fixed.append(f"{o.name}'s {it.label()}")
            left -= 1
    if fixed:
        events.append(f"🔨 {smith.name} mends {', '.join(fixed[:3])}{' and more' if len(fixed) > 3 else ''}.")
    made = _craft(game, smith, events)
    return bool(fixed) or made


def _craft(game, smith, events: List[str]) -> bool:
    """Slowly forge a weapon or a relic when the colony has the materials (every CRAFT_SHIFTS shifts, alternating)."""
    game.forge_progress += 1
    if game.forge_progress < config.CRAFT_SHIFTS:
        return True                                                 # work in progress
    kind = game.forge_next
    try:
        if kind == "weapon":
            tier = game.buildings.gear_tier()
            options = [g for g in equipment.GEAR if g.tier <= tier]
            if not options:
                raise NotEnoughResources("nothing to forge")
            options.sort(key=lambda g: (-g.tier, g.key))
            pick = next((g for g in options if game.wallet.can_afford(_craft_cost(g.cost))), None)
            if not pick:
                raise NotEnoughResources("no materials")
            game.wallet.spend_many(_craft_cost(pick.cost))
            game.inventory.add(pick.key)
            events.append(f"⚒️ {smith.name} forges a {pick.emoji}{pick.name}.")
        else:
            cost = dict(config.CRAFT_RELIC_COST)
            game.wallet.spend_many(cost)
            it = game.new_item(False)
            events.append(f"⚒️ {smith.name} forges a relic: {it.label()}.")
    except NotEnoughResources:
        game.forge_progress = config.CRAFT_SHIFTS - 1              # keeps waiting for materials
        return False
    game.forge_progress = 0
    game.forge_next = "relic" if kind == "weapon" else "weapon"
    return True


def _craft_cost(cost: Dict[str, int]) -> Dict[str, int]:
    return {k: max(1, int(v * config.CRAFT_COST_SHARE)) for k, v in cost.items()}


# ---- brewer -----------------------------------------------------------------------------------------------------------
def _brew(game, brewer, events: List[str]) -> bool:
    out = game.brew_for_post(brewer)
    if out:
        events.extend(out)
    return bool(out)


# ---- chef & kitchen ----------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Recipe:
    key: str
    name: str
    emoji: str
    cost: Dict[str, int]
    nutrition: int                  # food need each serving restores
    servings: int
    morale: int                     # morale each serving gives
    level: int                      # chef level needed


RECIPES: Dict[str, Recipe] = {r.key: r for r in (
    Recipe("porridge", "Porridge", "🥣", {"food": 1}, 35, 3, 0, 1),
    Recipe("stew", "Hearty Stew", "🍲", {"food": 2, "herb_green": 1}, 55, 4, 3, 2),
    Recipe("pie", "Berry Pie", "🥧", {"food": 2, "herb_red": 1}, 40, 4, 7, 3),
    Recipe("feast", "Feast", "🍗", {"food": 4, "essence": 1}, 70, 6, 9, 5),
)}


def pantry_cap(game) -> int:
    return config.PANTRY_PER_LEVEL * game.buildings.level("kitchen")


def pantry_total(game) -> int:
    return sum(game.pantry.values())


def hungry(game) -> List:
    """Slimes at home who could do with a meal."""
    return [o for o in at_home(game) if o.needs.get("food") < config.HUNGRY_BELOW]


def pick_recipe(game, chef) -> Optional[Recipe]:
    lvl = level(chef, "chef")
    pref = game.recipe_pref
    options = [r for r in RECIPES.values() if r.level <= lvl and game.wallet.can_afford(r.cost)]
    if pref != "auto":
        r = RECIPES.get(pref)
        return r if r in options else None
    return max(options, key=lambda r: (r.nutrition * r.servings + 10 * r.morale * r.servings), default=None)


def _cook(game, chef, events: List[str]) -> bool:
    room = pantry_cap(game) - pantry_total(game)
    if room <= 0:
        return False
    r = pick_recipe(game, chef)
    if r is None:
        return False
    game.wallet.spend_many(r.cost)
    n = max(1, min(room, int(round(r.servings * power(chef, "chef", game)))))
    game.pantry[r.key] = game.pantry.get(r.key, 0) + n
    events.append(f"🍳 {chef.name} cooks {r.emoji}{r.name}: {n} serving(s) into the pantry.")
    return True


def eat_from_pantry(game, slime, key: Optional[str] = None) -> bool:
    """A slime takes a dish from the pantry (the chosen one, else the most nourishing), if there is one."""
    if key is not None:
        best = RECIPES.get(key) if game.pantry.get(key, 0) > 0 else None
    else:
        best = max((RECIPES[k] for k, n in game.pantry.items() if n > 0 and k in RECIPES), key=lambda r: r.nutrition, default=None)
    if best is None:
        return False
    game.pantry[best.key] -= 1
    if game.pantry[best.key] <= 0:
        del game.pantry[best.key]
    slime.needs.add("food", best.nutrition)
    if best.morale:
        game.social.shift_morale(slime, best.morale)
        emotions.feel(slime, "joy", best.morale)
    return True


# ---- doctor & hospital -------------------------------------------------------------------------------------------------
def injured(game) -> Tuple[List, List]:
    """(injured, wounded): slimes at home below full health, and the ones below half."""
    hurt = [o for o in at_home(game) if o.hp < o.max_hp]
    return hurt, [o for o in hurt if o.hp < o.max_hp * 0.5]


def _ward_round(game, doctor, events: List[str]) -> None:
    """Every hour a doctor on duty heals the injured at home (more with a bigger Hospital and a better doctor)."""
    rate = config.HOSPITAL_HEAL[game.buildings.level("hospital") - 1] * power(doctor, "doctor", game)
    for o in injured(game)[0]:
        if (o is doctor and o.state == "working") or o.state == "resting":
            continue                                      # (patients in the ward / Rest Area have their own care)
        o.hp = min(o.max_hp, o.hp + max(1, int(o.max_hp * rate)))


def _doctor_shift(game, doctor, events: List[str]) -> bool:
    hurt, wounded = injured(game)
    if hurt:
        events.append(f"🩺 {doctor.name} finishes a shift on the wards ({len(hurt)} injured, {len(wounded)} wounded).")
    return bool(hurt)


RUNNERS = {"trainer_sword": _teach, "trainer_archery": _teach, "trainer_magic": _teach, "librarian": _lore,
           "blacksmith": _forge, "brewer": _brew, "chef": _cook, "doctor": _doctor_shift}
