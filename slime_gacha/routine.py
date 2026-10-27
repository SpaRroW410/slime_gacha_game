"""Routine: the shape of a slime's day at home (docs: Guide > Slimes > A day at home, docs/MINDS.md).

People's days have a rhythm, and much of their social life happens inside it: meals are eaten together, evenings belong to
hobbies and the people who share them.
  MEALS    at breakfast, lunch and dinner (config.MEAL_HOURS) slimes at home who are getting hungry eat together; everyone at
           a table (up to config.TABLE_SIZE) grows a little closer.
  EVENING  at config.HOBBY_HOUR every free slime at home spends the evening on its hobby (from its personality or outlook):
           it is something it chose for itself (meaning), it lifts the mood, and slimes who share a hobby grow closer.
"""
from typing import Dict, List

from . import config, emotions, meaning

HOBBIES = (  # (trait or outlook, key, what it does, who does it with others)
    ("chatty", "gossip", "gossips at the pond"), ("kind", "cooking", "helps the cook"), ("proud", "showing off", "shows off its moves"),
    ("brave", "wrestling", "wrestles for fun"), ("timid", "reading", "reads in a quiet corner"),
    ("grumpy", "tinkering", "tinkers in the shed"), ("gluttonous", "baking", "bakes something sweet"),
    ("lazy", "lounging", "lounges by the fire"),
    ("scout", "stargazing", "maps the stars"), ("study", "reading", "reads in the Library"), ("spar", "wrestling", "spars for fun"),
    ("hunt", "foraging", "goes looking for mushrooms"), ("pit", "wrestling", "wrestles for fun"), ("delve", "stories", "trades dungeon stories"),
)
DEFAULT = ("walking", "takes a walk around the colony")


def hobby(s) -> tuple:
    """(key, text) of this slime's hobby: its outlook first (what it does most), else its first fitting trait."""
    from . import outlook
    o = outlook.outlook_key(s)
    for who, key, text in HOBBIES:
        if who == o:
            return key, text
    for t in s.traits:
        for who, key, text in HOBBIES:
            if who == t:
                return key, text
    return DEFAULT


def _home(s) -> bool:
    return not s.busy and s.state == "idle" and s.hp > 0


def meal(g, events: List[str], dinner: bool) -> None:
    """Slimes at home who are getting hungry eat together; table-mates grow closer. After a boss falls, dinner is a feast."""
    from . import rituals
    if dinner and rituals.feast(g, events):
        return
    diners = []
    for s in g.slimes():
        if not _home(s) or s.needs.get("food") >= config.MEAL_BELOW or (g.needs.skip_meal and g.needs.skip_meal(s, events)):
            continue
        if g.needs.meal_hook and g.needs.meal_hook(s):
            diners.append(s)
        elif g.wallet.get("food") >= 1:
            g.wallet.spend("food", 1)
            s.needs.add("food", config.FOOD_NUTRITION)
            diners.append(s)
    for i in range(0, len(diners), config.TABLE_SIZE):
        table = diners[i:i + config.TABLE_SIZE]
        for j, a in enumerate(table):
            a.needs.add("belonging", 3)
            for b in table[j + 1:]:
                g.social.add_bond(a, b, config.MEAL_BOND)
    if dinner and len(diners) >= 3:
        events.append(f"🍲 Dinner together: {len(diners)} slimes around the table.")


def evening(g, events: List[str]) -> None:
    """Every free slime at home spends the evening on its hobby; those who share one grow closer."""
    clubs: Dict[str, list] = {}
    for s in g.slimes():
        if not _home(s) or s.needs.get("energy") < config.HOBBY_MIN_ENERGY:    # too worn out: it just collapses
            continue
        key, text = hobby(s)
        clubs.setdefault(key, []).append((s, text))
        emotions.feel(s, "joy", config.HOBBY_JOY)
        emotions.feel(s, "calm", config.HOBBY_JOY)
        meaning.note(s, "chose", 0.5)                                   # time of its own, spent as it likes
        acts = meaning.life(s)["acc"]["acts"]
        if "hobby" not in acts:
            acts.append("hobby")
    parts = []
    for key, members in clubs.items():
        for i, (a, _) in enumerate(members):
            for b, _ in members[i + 1:]:
                g.social.add_bond(a, b, config.HOBBY_BOND)
        names = [s.name for s, _ in members]
        who = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}" if len(names) <= 3 else f"{names[0]} and {len(names) - 1} others"
        text = members[0][1] if len(members) == 1 else members[0][1].replace("its ", "their ")
        parts.append(f"{who} {text if len(members) == 1 else _plural(text)}")
    if parts:
        events.append("🌙 Evening: " + "; ".join(parts[:config.EVENING_LINE_PARTS]) + ("…" if len(parts) > config.EVENING_LINE_PARTS else "."))


def _plural(text: str) -> str:
    """'gossips at the pond' -> 'gossip at the pond' (several slimes)."""
    verb, _, rest = text.partition(" ")
    if verb.endswith("es") and verb[:-2].endswith(("sh", "ch", "x", "s", "o")):
        verb = verb[:-2]
    elif verb.endswith("s"):
        verb = verb[:-1]
    return f"{verb} {rest}".strip()


def hourly(g, events: List[str]) -> None:
    hour = g.tick_count % 24
    if hour in config.MEAL_HOURS:
        meal(g, events, dinner=hour == config.MEAL_HOURS[-1])
    if hour == config.HOBBY_HOUR:
        evening(g, events)
