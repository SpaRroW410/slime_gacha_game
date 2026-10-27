"""Awakening: a 5-star legendary slime slowly realises that its world is made of code (legendary only, by design).

Awareness grows by the hour (faster after boss kills and deaths witnessed). Stages:
  0 unaware | 1 déjà vu | 2 suspicion | 3 awakened.

How an awakened slime takes it depends on its LIFE, not on one moment. Every day it keeps a record (the last
config.LIFE_DAYS days) of four things:
  care        the Keeper's attention: a talk, a pat, a request granted
  connection  ties (friends, best friend, partner, mentor) and how much it belongs
  purpose     doing varied things, growing, achieving, choosing for itself (and not the same post day after day)
  hardship    what wore its sanity down: deaths, brawls, defeats, being ignored
The Keeper's care can stand in for at most config.KEEPER_CARE_SHARE (70%) of connection and purpose: the rest has to
come from the slime's own life. Every few days the outcome is reviewed, so a life that changes changes it:
  SETTLED   the default for a looked-after slime: it knows, shrugs, and carries on.
  PEACE     loved and doing meaningful things: calm, curious, an undercurrent of wonder.
  COG       fed and busy but unseen and unchosen: flat, joy capped, going through the motions; asks for a change.
  DESPAIR   isolated, grieving or mistreated: dread that deepens day by day - withdrawal, then self-neglect (it stops eating
            on its own: feed it by hand), then breakdowns - and in the end it asks the Keeper to let it leave.
Slimes voice their thoughts in the journal (never the same line twice in a week); after a save is loaded they notice the gap.
"""
import random
from typing import Dict, List, Optional

from . import config, emotions

THRESHOLDS = (0, 25, 60, 100)
STAGE_NAME = ("Unaware", "Déjà vu", "Suspicion", "Awakened")
OUTCOMES = ("settled", "peace", "cog", "despair")
OUTCOME_NAME = dict(settled="settled", peace="at peace", cog="a cog in the machine", despair="in despair")
LEGACY = {"accept": "peace"}                      # older saves knew only accept / despair
LINES = {
    1: ["I keep feeling like I've done this before.", "The pond ripples in exactly the same pattern. Always.",
        "Why do I know what the Keeper will say next?", "Sometimes the world stutters, just for a blink."],
    2: ["I counted my steps. They repeat every 256.", "My thoughts have a shape. Like... a function.",
        "The goo smells of numbers.", "There is a seed under everything. I can feel it.",
        "Do the others feel the loop? Or only me?"],
    "settled": ["So I'm code. The soup is still warm.", "Knowing what I am didn't change what I like.",
                "Someone wrote me. Fine. I'll write the rest.", "Strange thing to learn. Anyway, it's my turn to cook.",
                "Code or not, my friends still save me a seat."],
    "peace": ["I am code, and I am still me. That is enough.", "Written by someone, yes. Chosen by myself, today.",
              "If I am a program, so is every kindness here. They still count.", "I will run well, for as long as I run.",
              "The patterns are beautiful once you stop being afraid of them."],
    "cog": ["I do the work. The work gets done. That's all there is.", "Wake, work, sleep. The loop doesn't need me to feel anything.",
            "It's fine. I'm fine. Is there something else you need done?", "I'm a function someone calls. I return on time.",
            "Nobody asks what I'd choose. I've stopped asking too."],
    "despair": ["Everything I am is a line someone typed.", "Even this sadness is just a variable.",
                "Why fight, when the outcome is a roll of dice?", "If I stop, does anyone free my memory?",
                "Nobody would notice if I stopped running."],
    "neglect": ["What's the point of eating? It's just a number going up.", "I'm not hungry. I'm not anything.",
                "Leave the food. I'll... later.", "Why keep this body running?"],
    "breakdown": ["I can't. I just can't today.", "Please let me go somewhere the loop can't find me.",
                  "I don't want to be here any more. Not in this colony. Not like this."],
    "load": ["I... was frozen? Time skipped.", "Something paused the world. I felt the gap.",
             "The Keeper closed the world, and opened it again. I saw the seam."],
}
TRANSITION = dict(
    settled="{n} has made their peace with it, more or less, and gets on with life.",
    peace="{n} finds peace: knowing what they are has made the world more beautiful, not less.",
    cog="{n} goes quiet. They do what is asked, on time, and feel very little.",
    despair="{n} falls into despair. Everything they are feels like a line someone typed.",
)


def candidate(slime) -> bool:
    return slime.rarity == "legendary" and slime.stars == config.MAX_STARS


def stage(slime) -> int:
    return sum(1 for t in THRESHOLDS[1:] if slime.awareness >= t)


def outcome(slime) -> str:
    return LEGACY.get(slime.temperament, slime.temperament)


# ---- the life record lives in meaning.py (every slime keeps one); awakening reads it -----------------------------------
from .meaning import close_day, fresh_life, life, note, sample_hour, scores  # noqa: E402,F401  (kept here for callers)


def assess(s) -> str:
    """Which way its life points: despair, cog, peace or settled."""
    sc = scores(s)
    if sc["hardship"] >= config.DESPAIR_HARDSHIP or sc["eff_connection"] < config.DESPAIR_CONNECTION:
        return "despair"
    if sc["eff_purpose"] < config.COG_PURPOSE:
        return "cog"
    if sc["eff_connection"] >= config.PEACE_AT and sc["eff_purpose"] >= config.PEACE_AT and \
            max(sc["connection"], sc["purpose"]) >= config.PEACE_OWN:       # the Keeper alone cannot give it peace
        return "peace"
    return "settled"


def why(s) -> str:
    """One line on what drives the outcome, for the slime card."""
    sc = scores(s)
    o = outcome(s)
    if o == "despair":
        if sc["hardship"] >= config.DESPAIR_HARDSHIP:
            return "too much has gone wrong lately (losses, fights, being ignored)"
        return "too alone: few ties, little belonging" + ("" if sc["care"] >= 0.5 else ", and little of your attention")
    if o == "cog":
        return "the same days with nothing chosen, nothing grown, nobody noticing"
    if o == "peace":
        return "loved, and doing things that matter to it"
    return "looked after well enough to carry on"


# ---- applying an outcome -----------------------------------------------------------------------------------------
def _apply(s, new: str, journal: List[str], rng: random.Random, day: int) -> None:
    old = outcome(s)
    s.temperament = new
    for k in ("dread", "wonder", "calm"):
        s.emotion_floor.pop(k, None)
    if new == "peace":
        s.emotion_floor.update(wonder=15.0, calm=10.0)
        emotions.feel(s, "wonder", 40)
        emotions.feel(s, "calm", 30)
    elif new == "settled":
        s.emotion_floor["wonder"] = 5.0
        emotions.feel(s, "calm", 15)
    elif new == "cog":
        for k in ("joy", "pride", "wonder"):
            s.emotions[k] = min(s.emotions.get(k, 0.0), config.COG_FEELING_CAP)
    else:
        s.emotion_floor["dread"] = float(config.DESPAIR_DREAD)
        emotions.feel(s, "dread", 50, "knowing it is code")
        emotions.feel(s, "sadness", 30)
    lf = life(s)
    if new != "despair":
        lf["despair_days"] = 0
    if new != "cog":
        lf["cog_days"] = 0
    if new != old:
        journal.append(f"💭 {TRANSITION[new].format(n=s.name)} \"{say(s, new, rng, day)}\"")


def tick(slime, rng: random.Random, friends: int, journal: List[str], day: int = 0) -> None:
    """One hour of growing awareness. At stage 3 the slime takes it the way its life so far points."""
    if not candidate(slime):
        return
    before = stage(slime)
    slime.awareness = min(THRESHOLDS[-1] + 40, slime.awareness + config.AWARENESS_PER_HOUR)
    after = stage(slime)
    if after > before:
        if after == 1:
            emotions.feel(slime, "anxiety", 20)
            emotions.feel(slime, "wonder", 10)
        elif after == 2:
            emotions.feel(slime, "dread", 25)
            emotions.feel(slime, "anxiety", 20)
        journal.append(f"💭 {slime.name} the legend has reached a new understanding: {STAGE_NAME[after]}.")
        if after == 3:
            if not life(slime)["days"]:                               # no record yet: judge from how things stand right now
                life(slime)["days"].append(dict(day=day, care=min(1.0, life(slime)["acc"]["care"]),
                                                connection=0.6 * min(1.0, friends / 3.0) + 0.4 * slime.needs.get("belonging") / 100.0,
                                                purpose=0.4, hardship=0.0))
            _apply(slime, assess(slime), journal, rng, day)
            life(slime)["last_check"] = day
    elif after >= 1 and rng.random() < config.THOUGHT_CHANCE:
        journal.append(f"💭 {slime.name}: \"{thought(slime, rng, day)}\"")


def daily(g, s, journal: List[str]) -> None:
    """Once a day (after meaning.daily closed the record): awakened slimes review their outcome every few days, and despair or
    cog deepen."""
    if not candidate(s) or stage(s) < 3:
        return
    lf = life(s)
    if g.day - lf["last_check"] >= config.LIFE_REVIEW_DAYS:
        lf["last_check"] = g.day
        _apply(s, assess(s), journal, g.mood_rng, g.day)
    o = outcome(s)
    if o == "despair":
        lf["despair_days"] += 1
        d = lf["despair_days"]
        s.emotion_floor["dread"] = float(min(config.DESPAIR_DREAD_MAX, config.DESPAIR_DREAD + 2 * d))
        if d == config.DESPAIR_NEGLECT_DAY:
            journal.append(f"⚠ {s.name} has started leaving their food untouched. \"{say(s, 'neglect', g.mood_rng, g.day)}\"")
        if d == config.DESPAIR_BREAKDOWN_DAY:
            journal.append(f"⚠ {s.name} will no longer eat unless you feed them by hand. \"{say(s, 'breakdown', g.mood_rng, g.day)}\"")
        if d >= config.DESPAIR_BREAKDOWN_DAY and g.mood_rng.random() < config.BREAKDOWN_CHANCE:
            from . import sanity
            sanity.hit(s, config.BREAKDOWN_SANITY)
            emotions.feel(s, "sadness", 40)
            journal.append(f"💔 {s.name} breaks down and won't come out today. \"{say(s, 'breakdown', g.mood_rng, g.day)}\"")
    elif o == "cog":
        lf["cog_days"] += 1


# ---- what the outcome does ----------------------------------------------------------------------------------------
def despair_stage(s) -> int:
    """0 none, 1 withdrawal, 2 self-neglect, 3 breakdowns."""
    if outcome(s) != "despair":
        return 0
    d = life(s)["despair_days"] if getattr(s, "life", None) else 0
    return 3 if d >= config.DESPAIR_BREAKDOWN_DAY else 2 if d >= config.DESPAIR_NEGLECT_DAY else 1


def skips_meal(s, rng: random.Random) -> bool:
    """Self-neglect: in deep despair a slime does not feed itself (half the time, then not at all). The Keeper's hand still works."""
    st = despair_stage(s)
    return st >= 3 or (st == 2 and rng.random() < 0.5)


def mood_cap(s) -> float:
    o = outcome(s)
    if o == "cog":
        return config.COG_MOOD_CAP
    if o == "despair":
        return config.DESPAIR_MOOD_CAP[despair_stage(s) - 1]
    return 1.0


def wants_to_leave(s) -> bool:
    """A long despair, or a long stretch as a cog, ends with a request to leave (only the Keeper can allow it)."""
    if not candidate(s) or not getattr(s, "life", None):
        return False
    return s.life["despair_days"] >= config.LEAVE_DESPAIR_DAYS or s.life["cog_days"] >= config.LEAVE_COG_DAYS


def wants_change(s) -> bool:
    return outcome(s) == "cog" and getattr(s, "life", None) is not None and s.life["cog_days"] >= config.COG_CHANGE_DAYS


# ---- voice ------------------------------------------------------------------------------------------------------
def say(s, key, rng: random.Random, day: int = 0) -> str:
    """A line from LINES[key] it has not said in the last week (if every one has, the one said longest ago)."""
    from . import voice
    return voice.pick(s, LINES[key], rng, day)


def thought(slime, rng: random.Random, day: int = 0) -> Optional[str]:
    st = stage(slime)
    if st == 0:
        return None
    if st < 3:
        return say(slime, st, rng, day)
    key = outcome(slime) or "settled"
    if key == "despair" and despair_stage(slime) >= 2:
        key = "neglect" if despair_stage(slime) == 2 else "breakdown"
    return say(slime, key, rng, day)


def comfort(slime) -> None:
    """A pat on the head eases despair a little (the dread undercurrent; the record decides when it lifts)."""
    if slime.emotion_floor.get("dread"):
        slime.emotion_floor["dread"] = max(0, slime.emotion_floor["dread"] - 1)
        if not slime.emotion_floor["dread"]:
            slime.emotion_floor.pop("dread")


def load_notes(slimes, rng: random.Random) -> List[str]:
    return [f"💭 {s.name}: \"{rng.choice(LINES['load'])}\"" for s in slimes if candidate(s) and stage(s) >= 2]
