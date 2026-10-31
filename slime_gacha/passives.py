"""Passive skills: perks a slime earns by mastering something. They are always on (nothing to cast or equip) and show on the
slime's Fight tab, locked until earned with what it takes to unlock them.

A `Passive` is data: a key, a name, a group, what it does, what it takes, and a test `earned(game, slime)`. Add one with
register_passive(...). Its effect is one of
  mods     personal combat perks (crit, guard, spell power ...) added to the slime's own fights while it holds the passive;
  a party perk that the hook for it asks about with party_has(game, party, key) (Hearth, Wellspring, Bedrock, Tailwind, the
  synergy ones), or a trade perk the jobs code asks about with has(game, slime, key).

Groups (docs/ROADMAP.md, task 82):
  element       the top mastery level of a basic element: perks for the party it travels with
  trade         the top level in a trade: that post's output
  proficiency   class proficiency 100 (the gold star on the avatar): one personal perk per class; both disciplines at 100 (teal star too)
  style         a fighting style at its top level: a personal combat perk
  synergy       ties with other slimes: the party's synergy

Not all of them are earned at once and none can be bought: a locked passive says what it takes.
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List

from . import config, elements, jobs, sparring
from .registry import Registry

GROUPS = (("element", "Elements"), ("trade", "Trades"), ("proficiency", "Proficiency"), ("style", "Fighting styles"),
          ("synergy", "Synergy"))
MOD_TEXT = {"crit_rate": "+{}% crit chance", "crit_dmg": "+{}% crit damage", "spell_power": "+{}% spell power", "guard": "{}% less damage taken",
            "resist": "+{}% magic resistance", "evasion": "+{}% dodge chance", "lifesteal": "+{}% lifesteal",
            "regen": "heals {}% of its HP every round"}
TIES = ("friend", "best_friend", "couple", "mentor")


@dataclass(frozen=True)
class Passive:
    key: str
    name: str
    emoji: str
    group: str
    blurb: str                             # what it does, in words (the personal perks in `mods` are added to it)
    need: str                              # what it takes, in plain words
    earned: Callable[[object, object], bool]       # (game, slime) -> does this slime have it?
    mods: Dict[str, float] = field(default_factory=dict)

    @property
    def desc(self) -> str:
        perks = ", ".join(MOD_TEXT.get(k, k + " +{}%").format(round(v * 100)) for k, v in self.mods.items())
        return " ".join(x for x in (self.blurb, f"In its own fights: {perks}." if perks else "") if x)


PASSIVES: "Registry[Passive]" = Registry("passive")


def register_passive(p: Passive) -> Passive:
    return PASSIVES.register(p, p.key)


def has(game, slime, key: str) -> bool:
    return key in PASSIVES and bool(PASSIVES.get(key).earned(game, slime))


def earned(game, slime) -> List[Passive]:
    return [p for p in PASSIVES if p.earned(game, slime)]


def party_has(game, party, key: str) -> bool:
    """Does anyone in this group have the passive (a perk the whole group enjoys)?"""
    return any(has(game, s, key) for s in party)


def count(game, party, key: str) -> int:
    return sum(1 for s in party if has(game, s, key))


def battle_mods(game, slime) -> Dict[str, float]:
    """Personal combat perks of the passives this slime has earned (added to its battle mods)."""
    out: Dict[str, float] = {}
    for p in PASSIVES:
        if p.mods and p.earned(game, slime):
            for k, v in p.mods.items():
                out[k] = out.get(k, 0.0) + v
    return out


def party_synergy(game, party) -> float:
    """Extra party synergy from the synergy passives (Soulbound, Heart of the Party), capped together."""
    ids = {s.id for s in party}
    bonus = 0.0
    for s in party:
        if has(game, s, "soulbound") and game.relations.partner(s.id) in ids:
            bonus += config.SYNERGY_SOULBOUND / 2                       # counted from both partners: the pair adds it once
        if has(game, s, "heart_of_the_party"):
            bonus += config.SYNERGY_HEART
    return min(config.SYNERGY_PASSIVE_MAX, bonus)


def max_mastery() -> int:
    return len(config.MASTERY_XP)


def _ties(game, s) -> int:
    return sum(1 for r in game.relations.of(s.id) if r["kind"] in TIES)


# ---- elements: the top mastery level of a basic element --------------------------------------------------------------------------
def _top(basic: str):
    return lambda g, s: elements.basic_level(s, basic) >= max_mastery()


_TOP = f"Master the {{}} element to the top level (level {len(config.MASTERY_XP)}: 5 stars, attuned to {{}})."
register_passive(Passive("tailwind", "Tailwind", "🌪️", "element",
                         f"Hastens a rescue party it goes with: the way to stranded scouts is {round(config.RESCUE_TAILWIND_SPEED * 100)}% shorter "
                         f"(up to {round(config.RESCUE_TAILWIND_MAX * 100)}% with more than one).", _TOP.format("wind", "wind"), _top("wind")))
register_passive(Passive("hearth", "Hearth", "🔥", "element",
                         f"Its party mends {round(config.HEARTH_HEAL * 100)}% more at every camp hour.", _TOP.format("fire", "fire"), _top("fire")))
register_passive(Passive("wellspring", "Wellspring", "💧", "element",
                         f"Its party burns {round(config.WELLSPRING_CUT * 100)}% less food and energy inside dungeons.",
                         _TOP.format("water", "water"), _top("water")))
register_passive(Passive("bedrock", "Bedrock", "🪨", "element",
                         f"Ambushes hurt its party {round(config.BEDROCK_CUT * 100)}% less (camps, scouting, rescue, retreat).",
                         _TOP.format("earth", "earth"), _top("earth")))

# ---- trades: the top level in a trade, while it is the slime's post (or any time: the level is kept) ---------------------------------
_TRADE_DESC = dict(
    chef=("Gourmet", "🍳", "Its dishes make {} more servings."),
    blacksmith=("Master Smith", "🔨", "It mends {} more gear each shift."),
    doctor=("Healing Touch", "🩺", "Its patients heal {} faster."),
    librarian=("Archivist", "📚", "Its lore gives {} more mastery."))
for _key, (_name, _emoji, _desc) in _TRADE_DESC.items():
    register_passive(Passive(_key + "_master", _name, _emoji, "trade", _desc.format(f"{round(config.TRADE_PASSIVE_BOOST * 100)}%"),
                             f"Reach the top trade level ({config.JOB_MAX_LEVEL}) as a {jobs.JOBS[_key].name.lower()}.",
                             (lambda k: lambda g, s: jobs.level(s, k) >= config.JOB_MAX_LEVEL)(_key)))
register_passive(Passive("distiller", "Distiller", "⚗️", "trade",
                         f"Each brew has a {round(config.DISTILLER_CHANCE * 100)}% chance of one more potion.",
                         f"Reach the top trade level ({config.JOB_MAX_LEVEL}) as a brewer.", lambda g, s: jobs.level(s, "brewer") >= config.JOB_MAX_LEVEL))
for _key, _disc in (("trainer_sword", "sword"), ("trainer_archery", "archery"), ("trainer_magic", "magic")):
    register_passive(Passive("master_" + _disc, "Master " + _disc.title() + " Trainer", jobs.JOBS[_key].emoji, "trade",
                             f"Its teaching is {round(config.MASTER_TRAINER_BOOST * 100)}% stronger.",
                             f"Reach the top trade level ({config.JOB_MAX_LEVEL}) as the {_disc} trainer.",
                             (lambda k: lambda g, s: jobs.level(s, k) >= config.JOB_MAX_LEVEL)(_key)))

# ---- proficiency: the gold star (class proficiency 100) and the teal star (the second discipline too) ------------------------------
_CLASS = dict(
    barbarian=("Unbreakable", "🛡️", dict(guard=0.08)), mage=("Arcane Focus", "🔮", dict(spell_power=0.10)),
    medic=("Gentle Hands", "💚", dict(regen=0.02)), rogue=("Quick Hands", "🗡️", dict(evasion=0.08)),
    ranger=("Steady Aim", "🏹", dict(crit_rate=0.05)), necromancer=("Soul Siphon", "💀", dict(lifesteal=0.05)),
    bard=("Steady Voice", "🎵", dict(resist=0.08)), paladin=("Sworn Shield", "⚜️", dict(guard=0.05, resist=0.05)),
    alchemist=("Volatile Mix", "⚗️", dict(crit_dmg=0.15)), druid=("Verdant Pulse", "🌿", dict(regen=0.02, resist=0.04)))
for _arch, (_name, _emoji, _mods) in _CLASS.items():
    register_passive(Passive("mastery_" + _arch, _name, _emoji, "proficiency", "",
                             f"Class proficiency 100 as {'an' if _arch[0] in 'aeiou' else 'a'} {_arch} (the gold star on its avatar).",
                             (lambda a: lambda g, s: s.archetype == a and s.class_prof >= config.PROFICIENCY_FULL)(_arch), _mods))
register_passive(Passive("dual_mastery", "Dual Mastery", "☯️", "proficiency", "",
                         "Class proficiency 100 and the second discipline's proficiency 100 as well (gold and teal stars).",
                         lambda g, s: bool(s.spec) and s.class_prof >= config.PROFICIENCY_FULL and s.spec_prof >= config.PROFICIENCY_FULL,
                         dict(crit_rate=0.03, crit_dmg=0.10)))

# ---- fighting styles: a style at its top level ---------------------------------------------------------------------------------------
for _disc, _name, _emoji, _mods in (("sword", "Blademaster", "⚔️", dict(crit_dmg=0.10)), ("archery", "Sharpshooter", "🎯", dict(crit_rate=0.04)),
                                    ("magic", "Spellweaver", "🧙", dict(spell_power=0.08))):
    register_passive(Passive("style_" + _disc, _name, _emoji, "style", "", f"Take the {_disc} fighting style to level {config.STYLE_FULL}.",
                             (lambda d: lambda g, s: sparring.style_level(s, d) >= config.STYLE_FULL)(_disc), _mods))

# ---- synergy: ties with other slimes lift the party they fight in ---------------------------------------------------------------------
register_passive(Passive("soulbound", "Soulbound", "💞", "synergy",
                         f"While its partner is in the same party, the party's synergy is {round(config.SYNERGY_SOULBOUND * 100)}% higher "
                         f"(from the pair together).", "Have a partner (a couple).", lambda g, s: g.relations.partner(s.id) is not None))
register_passive(Passive("heart_of_the_party", "Heart of the Party", "💛", "synergy",
                         f"Its party's synergy is {round(config.SYNERGY_HEART * 100)}% higher.",
                         f"Have {config.HEART_TIES} or more ties: friends, a best friend, a partner or a mentor.",
                         lambda g, s: _ties(g, s) >= config.HEART_TIES))
