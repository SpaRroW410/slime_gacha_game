"""Occupations: non-combat work for slimes in town (no wages; it is what makes a gentle slime useful).

A slime with a job is "working": it stays in town (it can still be fed and petted) but is not free for parties,
hunts, drills or merging until you stop it - jobs are switchable at any time. The Workshops building sets how many
slimes can work at once. Every `cycle` hours a worker finishes one round; its output grows with its job level
(earned per round, per job, and kept when it switches) and with a natural talent for the trade.

  Chef        cooks for the colony: one Food item stretches into hearty meals for the hungriest slimes at home
  Blacksmith  mends worn gear of slimes at home, no materials needed
  Trainer     coaches idle slimes at home in their own discipline, no Training Grounds drill needed
"""
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

from . import attributes, config, emotions
from .errors import InvalidAction


@dataclass(frozen=True)
class Job:
    key: str
    name: str
    emoji: str
    cycle: int                      # hours per round of work
    description: str
    talents: Tuple[str, ...]        # classes with a natural knack (+25%)


JOBS: Dict[str, Job] = {j.key: j for j in (
    Job("chef", "Chef", "🍳", 4, "Turns one Food item per round into hearty meals for the hungriest slimes at home.",
        ("medic", "mage")),
    Job("blacksmith", "Blacksmith", "🔨", 6, "Mends worn gear carried by slimes at home - no materials needed.",
        ("barbarian", "ranger")),
    Job("trainer", "Trainer", "📣", 6, "Coaches idle slimes at home in their own discipline (class proficiency), no drill needed.",
        ("rogue", "necromancer")),
)}


def get(key: str) -> Job:
    if key not in JOBS:
        raise InvalidAction(f"Unknown occupation '{key}'. Choose from: {', '.join(JOBS)}.")
    return JOBS[key]


def xp_for(level: int) -> int:
    """Rounds of work needed to reach `level`."""
    return config.JOB_XP_STEP * (level - 1) ** 2


def level(slime, key: str) -> int:
    xp = slime.job_xp.get(key, 0)
    return min(config.JOB_MAX_LEVEL, 1 + int(math.sqrt(xp / config.JOB_XP_STEP)))


def power(slime, key: str) -> float:
    """Output multiplier: 1.0 at level 1, +12% per level, +25% for a natural talent."""
    p = 1 + 0.12 * (level(slime, key) - 1)
    return p * (1.25 if slime.archetype in JOBS[key].talents else 1.0)


def slots(game) -> int:
    return game.buildings.job_slots()


def workers(game) -> List:
    return [s for s in game.slimes() if s.job and s.state == "working"]


def assign(game, slime, key: str) -> str:
    job = get(key)
    if slime.state == "working":
        stop(game, slime)
    if slime.state != "idle" or slime.in_dungeon:
        raise InvalidAction(f"{slime.name} is {slime.in_dungeon and 'inside a dungeon' or slime.state}, not available.")
    if slime.grounded:
        raise InvalidAction(f"{slime.name} is grounded after a brawl.")
    if slime.id == game.vice:
        raise InvalidAction(f"{slime.name} is the Vice Keeper and has no time for a trade.")
    if slime.needs.get("energy") < config.TASK_MIN_ENERGY:
        raise InvalidAction(f"{slime.name} is too tired.")
    if len(workers(game)) >= slots(game):
        raise InvalidAction(f"All {slots(game)} workshop places are taken. Upgrade the Workshops or free one up.")
    if game.parties.party_of(slime.id) and game.parties.party_of(slime.id).id in game.delves:
        raise InvalidAction(f"{slime.name}'s party is in the Descent.")
    slime.job, slime.job_clock, slime.state = key, 0, "working"
    return f"{slime.name} starts work as a {job.name.lower()} (level {level(slime, key)})."


def stop(game, slime) -> str:
    if slime.state != "working":
        raise InvalidAction(f"{slime.name} is not working.")
    slime.state, slime.job, slime.job_clock = "idle", "", 0
    return f"{slime.name} hangs up the apron."


# ---- time -------------------------------------------------------------------------------------------------------------
def tick(game, events: List[str]) -> None:
    for s in workers(game):
        if s.needs.get("energy") < config.AUTO_SLEEP_BELOW:          # too weary to carry on: leaves the job to sleep
            events.append(f"😴 {s.name} is too tired to keep working as a {JOBS[s.job].name.lower()}.")
            s.state, s.job, s.job_clock = "idle", "", 0
            continue
        s.needs.add("energy", -config.JOB_ENERGY_PER_HOUR)
        s.job_clock += 1
        if s.job_clock < JOBS[s.job].cycle:
            continue
        s.job_clock = 0
        done = {"chef": _cook, "blacksmith": _mend, "trainer": _coach}[s.job](game, s, events)
        if done:
            s.job_xp[s.job] = s.job_xp.get(s.job, 0) + 1
            s.needs.add("esteem", 2)
            if level(s, s.job) > level_before(s):
                events.append(f"⭐ {s.name} reaches level {level(s, s.job)} as a {JOBS[s.job].name.lower()}!")


def level_before(s) -> int:
    key = s.job
    xp = s.job_xp.get(key, 0) - 1
    return min(config.JOB_MAX_LEVEL, 1 + int(math.sqrt(max(0, xp) / config.JOB_XP_STEP)))


def _at_home(game, exclude=None):
    return [o for o in game.slimes() if o is not exclude and not o.in_dungeon and o.state not in ("hunting", "studying")
            and o.hp > 0]


def _cook(game, chef, events: List[str]) -> bool:
    if game.wallet.get("food") < 1:
        events.append(f"🍳 {chef.name} has no Food to cook with.")
        return False
    guests = sorted(_at_home(game), key=lambda o: o.needs.get("food"))
    guests = [o for o in guests if o.needs.get("food") < 90][:config.CHEF_GUESTS + level(chef, "chef") // 3]
    if not guests:
        return False
    game.wallet.spend("food", 1)
    meal = config.FOOD_NUTRITION * config.CHEF_MEAL_SHARE * power(chef, "chef")
    for o in guests:
        o.needs.add("food", meal)
        o.needs.add("belonging", 2)
        emotions.feel(o, "joy", 4)
    events.append(f"🍳 {chef.name} serves a hot meal to {', '.join(o.name for o in guests)}.")
    return True


def _mend(game, smith, events: List[str]) -> bool:
    share = config.SMITH_MEND_SHARE * power(smith, "blacksmith")
    left = config.SMITH_ITEMS + level(smith, "blacksmith") // 2
    fixed = []
    for o in sorted(_at_home(game), key=lambda o: o.id):
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
    return bool(fixed)


def _coach(game, trainer, events: List[str]) -> bool:
    pupils = [o for o in _at_home(game, trainer) if o.state == "idle" and not o.grounded
              and o.class_prof < 100 and o.needs.get("energy") >= config.TASK_MIN_ENERGY]
    pupils.sort(key=lambda o: o.class_prof)
    pupils = pupils[:config.TRAINER_PUPILS + level(trainer, "trainer") // 4]
    if not pupils:
        return False
    power_ = power(trainer, "trainer")
    names = []
    for o in pupils:
        gain = config.TRAINER_GAIN * power_ * max(0.1, 1 - o.class_prof / 110.0)
        attributes.practise(o, o.arch.discipline, gain, 0.0)
        o.needs.add("energy", -3)
        names.append(o.name)
    events.append(f"📣 {trainer.name} coaches {', '.join(names)} (class proficiency).")
    return True
