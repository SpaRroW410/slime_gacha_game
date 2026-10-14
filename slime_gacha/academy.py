"""Academy: the Library (learn spells, study elements) and spell RESEARCH (fusing two spells into a new
element). Studying and researching are "tasks": the slime leaves for a few hours (state "studying") and
AcademySystem.tick() resolves the task when the hours are up. (Fighting styles live in sparring.py.)

Library level (buildings.py) adds spell slots, study speed, research odds and the Restricted Section
(tier-3 spells). New spells/elements live in spells.py / elements.py.
"""
import random
from typing import Dict, List, Optional, Set

from . import config, elements, spells
from .abilities import ABILITIES, Ability, get_ability
from .buildings import BuildingManager
from .errors import InvalidAction
from .resources import ResourceManager


# ---- the library: spell catalogue + colony knowledge -----------------------------------------
class Library:
    def __init__(self, wallet: ResourceManager, buildings: BuildingManager):
        self.wallet = wallet
        self.buildings = buildings
        self.discovered: Set[str] = set()      # keys of fused spells the colony has invented

    def catalog(self) -> List[Ability]:
        out = spells.base_spells() + [get_ability(k) for k in sorted(self.discovered) if k in ABILITIES]
        return sorted(out, key=lambda a: (a.tier, a.element, a.name))

    def learn(self, slime, key: str) -> str:
        spell = next((a for a in self.catalog() if a.key == key), None)
        if spell is None:
            raise InvalidAction(f"The Library has no spell '{key}'.")
        check_mastery_ready(slime)
        if key in slime.spells:
            raise InvalidAction(f"{slime.name} already knows {spell.name}.")
        if spell.tier >= 3 and not self.buildings.tier3_open():
            raise InvalidAction("Tier-3 spells are in the Restricted Section: upgrade the Library to level 3.")
        if len(slime.spells) >= self.spell_slots():
            raise InvalidAction(f"{slime.name} already knows {self.spell_slots()} spells - forget one first "
                                f"(or upgrade the Library).")
        missing = [c for c in spells.components_of(spell) if c not in slime.attuned]
        if missing:
            raise InvalidAction(f"{slime.name} must study {', '.join(missing)} first (attune at the Library).")
        have, need = elements.slime_mastery(slime, spell.element), spells.required_mastery(spell)
        if have < need:
            raise InvalidAction(f"{spell.name} needs {elements.get(spell.element).name} mastery {need} "
                                f"(weakest component), {slime.name} has {have}.")
        self.wallet.spend_many(spells.spell_cost(spell))
        slime.spells.append(key)
        return f"📕 {slime.name} learned {spell.name}!"

    def spell_slots(self) -> int:
        return config.MAX_SPELLS + self.buildings.extra_spell_slots()

    def forget(self, slime, key: str) -> str:
        if key not in slime.spells:
            raise InvalidAction(f"{slime.name} doesn't know that spell.")
        slime.spells.remove(key)
        return f"{slime.name} forgot {get_ability(key).name}."


def check_mastery_ready(slime) -> None:
    if not elements.can_master(slime):
        raise InvalidAction(f"{slime.name} is only {slime.stars}★ - elemental mastery needs "
                            f"{config.MASTERY_MIN_STARS}★ or more (any class).")


# ---- tasks -----------------------------------------------------------------------------------------
class AcademySystem:
    def __init__(self, wallet: ResourceManager, rng: random.Random, library: Library,
                 buildings: BuildingManager):
        self.wallet = wallet
        self.rng = rng
        self.library = library
        self.buildings = buildings

    # -- shared ----------------------------------------------------------------
    def _begin(self, slime, kind: str, ticks: int, cost: Dict[str, int], **args) -> None:
        self.wallet.spend_many(cost)
        slime.state = "studying"
        slime.task = dict(kind=kind, ticks_left=ticks, total=ticks, **args)

    @staticmethod
    def _check_free(slime) -> None:
        if slime.state != "idle":
            raise InvalidAction(f"{slime.name} is {slime.state}, not available.")
        if slime.grounded:
            raise InvalidAction(f"{slime.name} is grounded after a brawl. Mediate first.")
        if slime.needs.get("energy") < config.TASK_MIN_ENERGY:
            raise InvalidAction(f"{slime.name} is too tired.")

    def cancel(self, slime) -> None:
        if slime.state == "studying":
            slime.state, slime.task = "idle", None

    # -- library: study an element -------------------------------------------------------
    def start_study(self, slime, element: str) -> str:
        if element not in elements.BASICS:
            raise InvalidAction(f"Study a basic element: {', '.join(elements.BASICS)}.")
        check_mastery_ready(slime)
        self._check_free(slime)
        if element not in slime.attuned:
            if len(slime.attuned) >= elements.slot_count(slime):
                raise InvalidAction(f"{slime.name} can only attune {elements.slot_count(slime)} elements "
                                    f"({', '.join(slime.attuned)}).")
        if elements.basic_level(slime, element) >= elements.mastery_cap(slime) and element in slime.attuned:
            raise InvalidAction(f"{slime.name} has reached the limit of {slime.stars}★ mastery in "
                                f"{elements.get(element).name} (level {elements.mastery_cap(slime)}).")
        self._begin(slime, "study", config.STUDY_TICKS, config.STUDY_COST, element=element)
        if element not in slime.attuned:
            slime.attuned.append(element)
        return f"{slime.name} studies {elements.get(element).name} in the Library for {config.STUDY_TICKS} hours."

    def _finish_study(self, s, events) -> None:
        e = s.task["element"]
        gain = config.STUDY_XP * self.buildings.study_mult() * \
            (config.MAGE_STUDY_MULT if s.archetype == "mage" else 1.0)
        before = elements.basic_level(s, e)
        top = config.MASTERY_XP[max(0, elements.mastery_cap(s) - 1)]
        s.mastery_xp[e] = min(top, s.mastery_xp.get(e, 0) + gain)
        after = elements.basic_level(s, e)
        el = elements.get(e)
        events.append(f"📖 {s.name} studied {el.emoji}{el.name}: mastery {after}"
                      + (" ⬆ level up!" if after > before else f" ({int(s.mastery_xp[e])} xp)"))
        s.needs.add("esteem", 4)

    # -- research: fuse two learned spells -----------------------------------------------
    def plan_research(self, slime, key_a: str, key_b: str):
        """Validate and return (spell_a, spell_b, result_element, cost, ticks, success_chance)."""
        check_mastery_ready(slime)
        if key_a == key_b:
            raise InvalidAction("Pick two different spells to fuse.")
        for k in (key_a, key_b):
            if k not in slime.spells:
                raise InvalidAction(f"{slime.name} must have learned both spells first.")
        a, b = get_ability(key_a), get_ability(key_b)
        el = elements.combine(a.element, b.element)
        if el is None:
            raise InvalidAction(f"{elements.get(a.element).name} + {elements.get(b.element).name}: "
                                f"no known fusion.")
        missing = [c for c in el.components if c not in slime.attuned]
        if missing:
            raise InvalidAction(f"{slime.name} lacks attunement to: {', '.join(missing)}.")
        if el.tier >= 3 and not self.buildings.tier3_open():
            raise InvalidAction("Tier-3 research is in the Restricted Section: upgrade the Library to level 3.")
        need = config.SPELL_TIER_MASTERY[el.tier]
        have = elements.slime_mastery(slime, el.key)
        if have < need:
            raise InvalidAction(f"Creating {el.name} needs mastery {need} in every component "
                                f"({', '.join(sorted(el.components))}); {slime.name} has {have}.")
        ms = slime.max_stats()
        chance = 0.5 + 0.06 * (have - need) + 0.002 * max(ms["mag"], config.IMBUE_ATK_FACTOR * ms["atk"]) + \
            (0.1 if slime.archetype == "mage" else 0.0) + self.buildings.research_bonus()
        chance = max(0.25, min(0.95, chance))
        return a, b, el, dict(config.RESEARCH_COST[el.tier]), config.RESEARCH_TICKS[el.tier], chance

    def start_research(self, slime, key_a: str, key_b: str, name: Optional[str] = None) -> str:
        a, b, el, cost, ticks, chance = self.plan_research(slime, key_a, key_b)
        self._check_free(slime)
        if slime.hp < slime.max_hp * config.RESEARCH_MIN_HP:
            raise InvalidAction(f"{slime.name} is too wounded for risky experiments.")
        self._begin(slime, "research", ticks, cost, a=key_a, b=key_b, name=name or "")
        return (f"{slime.name} begins fusing {a.name} + {b.name} into {el.emoji}{el.name} "
                f"({ticks}h, {int(chance * 100)}% chance).")

    def _finish_research(self, s, events) -> None:
        t = s.task
        try:
            a, b, el, _, _, chance = self.plan_research(s, t["a"], t["b"])
        except InvalidAction as e:               # state changed mid-experiment (e.g. forgot a spell)
            events.append(f"🧪 {s.name}'s experiment was abandoned: {e}")
            return
        if self.rng.random() >= chance:
            loss = max(1, int(s.max_hp * config.RESEARCH_BACKFIRE))
            s.hp = max(1, s.hp - loss)           # backfires hurt but never kill
            s.needs.add("esteem", -6)
            events.append(f"💥 {s.name}'s {el.name} experiment fizzled and backfired (-{loss} HP).")
            return
        key = spells.fused_key(a.key, b.key)
        fresh = key not in ABILITIES
        spell = spells.register_custom(spells.design_fusion(a, b, t.get("name") or None, s.name)) \
            if fresh else get_ability(key)
        self.library.discovered.add(key)
        for c in el.components:                  # insight boosts the underlying elements
            s.mastery_xp[c] = min(config.MASTERY_XP[max(0, elements.mastery_cap(s) - 1)],
                                  s.mastery_xp.get(c, 0) + 10)
        s.needs.add("esteem", 15)
        msg = f"✨ {s.name} {'invented' if fresh else 'recreated'} {el.emoji}{spell.name}! "
        if key not in s.spells and len(s.spells) < self.library.spell_slots():
            s.spells.append(key)
            msg += "It is now in their spellbook and the Library."
        elif key in s.spells:
            msg += "Already in their spellbook."
        else:
            msg += f"Their spellbook is full ({self.library.spell_slots()}) - it is stored in the Library."
        events.append(msg)

    # -- time ---------------------------------------------------------------------------------
    def tick(self, slimes: List, events: List[str]) -> None:
        for s in slimes:
            if s.state != "studying" or not s.task:
                continue
            s.task["ticks_left"] -= 1
            if s.task["ticks_left"] > 0:
                continue
            kind = s.task["kind"]
            {"study": self._finish_study, "research": self._finish_research}[kind](s, events)
            s.state, s.task = "idle", None
