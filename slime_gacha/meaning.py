"""Meaning: what a slime's days add up to (docs: Guide > Slimes > Meaning, docs/ROADMAP.md § 5).

Every slime keeps a short daily record - the last config.MEANING_DAYS days (config.LIFE_DAYS for a 5-star legendary, whose
awakening reads it, see awakening.py) - of four things:
  care        the Keeper's attention: a talk, a pat, praise, a request granted
  connection  ties (friends, best friend, partner, mentor) and how much it belongs
  purpose     varied days, growing, achieving or being praised, choosing for itself (the same post day after day halves it)
  hardship    what wore its sanity down: deaths, brawls, defeats, being ignored
The Keeper's care can stand in for at most config.KEEPER_CARE_SHARE of connection and purpose.

People who are fed and safe but whose days mean nothing go flat. A slime whose purpose (with care counted) stays low for
config.BURNOUT_DAYS days while it is not lonely BURNS OUT: it goes through the motions (joy and pride stay muted, mood is
capped) and, if it holds a post, asks to be taken off it. Praise, choice, variety and growth bring its spark back.
(An awakened legendary's version of this is the cog, see awakening.py.)
"""
from typing import Dict, List

from . import config


def fresh_life() -> dict:
    return dict(days=[], acc=_fresh_acc(None), last_check=-99, despair_days=0, cog_days=0, post_streak=0, said={},
                burnout_days=0, burnt=False)


def _fresh_acc(s) -> dict:
    return dict(care=0.0, chose=0, praised=0, hurt=0.0, hours=0, belong=0.0, acts=[],
                xp0=(s.total_xp if s else 0), wins0=(s.wins if s else 0), level0=(s.level if s else 1))


DAY_KEYS = ("day", "care", "connection", "purpose", "hardship")


def pack(lf):
    """The record as saved: each day as a short list instead of a dict (a big colony keeps hundreds of them)."""
    if not lf:
        return lf
    out = dict(lf, days=[[d[k] for k in DAY_KEYS] for d in lf["days"]])
    if not out.get("said"):
        out.pop("said", None)
    return out


def unpack(lf):
    if not lf:
        return lf
    lf = dict(lf)
    lf["days"] = [dict(zip(DAY_KEYS, d)) if isinstance(d, list) else d for d in lf.get("days", [])]
    for k, v in fresh_life().items():
        lf.setdefault(k, v)
    return lf


def life(s) -> dict:
    """The slime's record, created on first use."""
    if not getattr(s, "life", None):
        s.life = fresh_life()
        s.life["acc"] = _fresh_acc(s)
    return s.life


def note(s, what: str, amount: float = 1.0) -> None:
    """Record something that happened today: 'care' (the Keeper's attention), 'chose' (it acted on its own goal or had a
    request granted), 'praised' (recognition) or 'hurt' (sanity lost)."""
    acc = life(s)["acc"]
    acc[what] = acc.get(what, 0) + amount


def sample_hour(s) -> None:
    """Hourly: what it is doing and how much it belongs."""
    acc = life(s)["acc"]
    acc["hours"] += 1
    acc["belong"] += s.needs.get("belonging")
    act = s.in_dungeon or s.state
    if act not in ("sleeping", "resting") and act not in acc["acts"]:
        acc["acts"].append(act)


def keep_days(s) -> int:
    return config.LIFE_DAYS if s.rarity == "legendary" and s.stars == config.MAX_STARS else config.MEANING_DAYS


def close_day(g, s) -> dict:
    """End of the slime's day: turn the day's notes into one record entry (care, connection, purpose, hardship)."""
    lf = life(s)
    acc = lf["acc"]
    ties = sum(1 for r in g.relations.of(s.id) if r["kind"] in ("friend", "best_friend", "couple", "mentor"))
    belong = acc["belong"] / acc["hours"] if acc["hours"] else s.needs.get("belonging")
    connection = 0.6 * min(1.0, ties / 3.0) + 0.4 * belong / 100.0
    acts = [a for a in acc["acts"] if a != "idle"]               # sitting about (or collapsing after work) is not an activity
    if s.job:                                                     # foraging between shifts is part of the same routine
        acts = [a for a in acts if a != "hunting"]
    praised = acc.get("praised", 0) > 0
    grind = s.job and set(acts) <= {"working"} and not praised     # recognised work is not an unseen grind
    lf["post_streak"] = lf["post_streak"] + 1 if grind else 0
    achieved = s.wins > acc["wins0"] or s.level > acc["level0"] or praised     # recognition counts as an achievement ...
    purpose = (0.3 * min(1.0, len(acts) / 2.0) + 0.25 * (s.total_xp > acc["xp0"])
               + 0.2 * achieved + 0.25 * min(1.0, acc["chose"]) + config.PRAISE_PURPOSE * praised)   # ... and a little more
    if lf["post_streak"] >= config.COG_POST_DAYS:                 # the same post day after day, nothing else
        purpose *= 0.5
    hardship = min(1.0, acc["hurt"] / (config.LIFE_HURT_SCALE * config.SANITY_MAX[s.rarity]))
    entry = dict(day=g.day, care=round(min(1.0, acc["care"]), 2), connection=round(connection, 2),
                 purpose=round(min(1.0, purpose), 2), hardship=round(hardship, 2))
    lf["days"] = (lf["days"] + [entry])[-keep_days(s):]
    lf["acc"] = _fresh_acc(s)
    return entry


def scores(s) -> Dict[str, float]:
    """Averages over the record; the Keeper's care can make up at most KEEPER_CARE_SHARE of connection and purpose."""
    days = life(s)["days"]
    if not days:
        return dict(care=0.0, connection=0.5, purpose=0.5, hardship=0.0, eff_connection=0.5, eff_purpose=0.5)
    avg = {k: sum(d[k] for d in days) / len(days) for k in ("care", "connection", "purpose")}
    recent = days[-config.LIFE_HARD_DAYS:]
    avg["hardship"] = sum(d["hardship"] for d in recent) / len(recent)
    share = config.KEEPER_CARE_SHARE
    avg["eff_connection"] = max(avg["connection"], share * avg["care"])
    avg["eff_purpose"] = max(avg["purpose"], share * avg["care"])
    return avg


# ---- burnout (every slime but an awakened legendary, whose outcome covers it) -----------------------------------------
def burned_out(s) -> bool:
    return bool(getattr(s, "life", None) and s.life.get("burnt"))


def daily(g, s, journal: List[str]) -> None:
    """Once a day: close the record, and see whether the days have gone flat (or the spark is back)."""
    close_day(g, s)
    if s.rarity == "legendary" and s.stars == config.MAX_STARS and s.temperament:
        return                                                    # an awakened legendary: awakening.py decides
    lf = life(s)
    if len(lf["days"]) < config.BURNOUT_DAYS:
        return
    sc = scores(s)
    flat = sc["eff_purpose"] < config.BURNOUT_PURPOSE and sc["eff_connection"] >= config.DESPAIR_CONNECTION
    lf["burnout_days"] = lf["burnout_days"] + 1 if flat else max(0, lf["burnout_days"] - 2)
    if not lf["burnt"] and lf["burnout_days"] >= config.BURNOUT_DAYS:
        lf["burnt"] = True
        for k in ("joy", "pride"):
            s.emotions[k] = min(s.emotions.get(k, 0.0), config.BURNOUT_FEELING_CAP)
        journal.append(f"😶 {s.name} is going through the motions: the same days, nothing chosen, nobody noticing.")
    elif lf["burnt"] and lf["burnout_days"] == 0:
        lf["burnt"] = False
        journal.append(f"🌱 {s.name} has their spark back.")


def mood_cap(s) -> float:
    return config.BURNOUT_MOOD_CAP if burned_out(s) else 1.0
