"""JSON command API over Game - the single entry point used by the browser front-end.

Two transports share it: `serve.py` (local HTTP server) and the Pyodide build (Python running in the page).
Every call returns the same envelope:

    {"ok": bool, "error": str|None, "log": [str], "result": {...}, "state": {...snapshot...}, "save": {...}}

`state` is a complete, render-ready snapshot (so the UI never needs a second request); `save` is the full
Game save dict which the browser keeps in localStorage. Domain errors (GameError) become `ok: false`.
"""
import json
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import ascension, attributes, guide as guide_mod, awakening, emotions, keeper as keeper_mod, relationships, config, potions as potions_mod, dungeon, elements, equipment, items as items_mod, outlook, sparring, spells, specialization
from .abilities import get_ability
from .academy import Library
from .archetypes import BEHAVIORS, all_archetypes
from .buildings import BUILDINGS
from .errors import GameError, InvalidAction
from .game import Game
from .growth import can_evolve, evolve_cost
from .hunt import ZONES
from .social import SocialEngine


# ---- views -------------------------------------------------------------------------------------
def slime_view(g: Game, s) -> dict:
    st = s.max_stats()
    a = s.arch
    party = g.parties.party_of(s.id)
    lv = sparring.style_levels(s)
    return dict(
        id=s.id, name=s.name, archetype=s.archetype, class_name=a.name, emoji=a.emoji, title=s.title(),
        rarity=s.rarity, stars=s.stars, level=s.level, level_cap=s.level_cap, stage=s.stage,
        xp=s.xp, xp_next=config.xp_to_next(s.level), total_xp=s.total_xp,
        hp=s.hp, max_hp=s.max_hp, stats=st, state=s.state, in_dungeon=s.in_dungeon, busy=s.busy,
        behavior=s.behavior, traits=list(s.traits), grounded=s.grounded, merged=s.merged, wins=s.wins,
        needs={k: round(s.needs.get(k)) for k in config.NEED_ORDER}, dominant=s.needs.dominant(),
        mood=s.mood_label(), power=round(s.power_rating(), 1), power_mult=round(s.power_multiplier(), 2),
        morale=round(s.morale), morale_label=SocialEngine.morale_label(s.morale),
        morale_factor=round(SocialEngine.morale_factor(s.morale), 2),
        abilities=[dict(key=k, name=get_ability(k).name, element=get_ability(k).element,
                        kind=get_ability(k).kind) for k in s.known_abilities()],
        spells=list(s.spells), attuned=list(s.attuned),
        mastery={b: elements.basic_level(s, b) for b in s.attuned},
        mastery_cap=elements.mastery_cap(s), element_slots=elements.slot_count(s),
        can_master=elements.can_master(s), style=lv, style_label=sparring.style_label(s),
        feelings=[dict(key=k, name=emotions.EMOTIONS[k].name, emoji=emotions.EMOTIONS[k].emoji,
                       value=round(v), kind=emotions.EMOTIONS[k].kind) for k, v in
                  sorted(s.emotions.items(), key=lambda kv: -kv[1]) if v >= 3],
        feeling_effects={k: round(100 * (m - 1)) for k, m in emotions.modifiers(s)[0].items() if abs(m - 1) >= 0.01},
        awareness=(dict(stage=awakening.stage(s), name=awakening.STAGE_NAME[awakening.stage(s)],
                        points=round(s.awareness, 1), temperament=s.temperament) if awakening.candidate(s) else None),
        relations=[dict(other=r["other"], kind=r["kind"], since=r["since"], mentor=r.get("mentor"))
                   for r in g.relations.of(s.id)],
        parents=list(s.parents), parent_names=list(s.parent_names), generation=s.generation,
        merge_bonus=dict(s.merge_bonus), core=s.core_stats(),
        stamina=s.stamina, max_stamina=s.max_stamina, buffs=[dict(b) for b in s.buffs],
        star_attrs=attributes.star_attributes(s),
        next_star_attr=next(({"star": i + 2, "label": attributes.ATTR_LABEL[k], "value": v}
                             for i, (k, v) in enumerate(attributes.STAR_ATTRS.get(s.archetype, []))
                             if s.stars < i + 2), None),
        rarity_skills=[dict(key=k, name=get_ability(k).name, desc=get_ability(k).description)
                       for k in attributes.rarity_skills(s)],
        next_rarity_skill=(get_ability(attributes.RARITY_SKILLS[s.archetype][config.RARITIES.index(s.rarity)]).name
                           if s.rarity != "legendary" and s.archetype in attributes.RARITY_SKILLS else None),
        weapons=dict(memory=list(s.weapon_memory), slots=config.WEAPON_MEMORY, favourite=items_mod.favourite_family(s),
                     proficiency={f: dict(uses=s.proficiency.get(f, 0), level=items_mod.proficiency_level(s, f))
                                  for f in items_mod.FAMILIES if s.proficiency.get(f, 0) or f in s.weapon_memory}),
        ascend=dict(next_rarity=ascension.next_rarity(s.rarity), rarity_cost=ascension.rarity_cost(s),
                    star_cost=ascension.star_cost(s), chamber=ascension.chamber_yield(s, g.buildings.level("chamber"))),
        gear=dict(s.gear), items={k: _item_view(v, s) for k, v in s.items.items()}, task=s.task, hunt=(s.hunt.to_dict() if s.hunt else None),
        party=(party.id if party else None), can_evolve=can_evolve(s),
        evolve_cost=(evolve_cost(s) if can_evolve(s) else None), discipline=a.discipline,
        progress=s.progress, exp=dict(s.exp), outlook=_outlook_view(s),
        spec=(dict(key=s.spec, name=specialization.SPECS[s.spec].name, emoji=specialization.SPECS[s.spec].emoji,
                   disc=s.spec_disc) if s.spec in specialization.SPECS else None),
        spec_options=[dict(discipline=r["discipline"], style=r["style"], name=r["spec"].name, emoji=r["spec"].emoji,
                           ability=get_ability(r["spec"].ability).name, ok=r["ok"], reason=r["reason"],
                           level=r["level"], desc=r["spec"].description) for r in specialization.options(s)],
    )


def _item_view(it, holder=None) -> dict:
    return dict(uid=it.uid, base=it.base, name=it.name, emoji=it.spec.emoji, slot=it.slot, rarity=it.rarity,
                stars=it.stars, level=it.level, family=it.spec.family, title=it.title, durability=(None if it.unbreakable else it.durability),
                max_durability=(None if it.unbreakable else it.max_durability), ego=it.ego,
                stats=(it.stats_for(holder) if holder else it.base_stats()),
                mods=[it.mod_text(m) for m in it.mods], bond=it.bond,
                compat=(it.compat(holder) if holder else None), fits=list(it.spec.fits),
                level_cost=(it.level_cost() if it.level < config.ITEM_MAX_LEVEL else None),
                star_cost=(it.star_cost() if it.level >= config.ITEM_MAX_LEVEL and it.stars < config.MAX_STARS else None),
                rarity_cost=(it.rarity_cost() if it.stars >= config.MAX_STARS and it.level >= config.ITEM_MAX_LEVEL
                             and items_mod.next_rarity(it.rarity) and not it.ego else None),
                repair_cost=it.repair_cost(), salvage=(None if it.ego else it.salvage_yield()),
                holder=(holder.id if holder else None))


def _pit_view(g: Game) -> dict:
    th = dungeon.pit_theme(g.dungeon_seed, g.day)
    from . import terrain as terrain_mod
    return dict(day=th.day, title=th.title, terrain=dict(key=th.terrain.key, name=th.terrain.name,
                emoji=th.terrain.emoji, effects=terrain_mod.describe(th.terrain), desc=th.terrain.desc),
                families=[dungeon.family_plural(f) for f in th.families])


def _spec_table() -> list:
    rows = []
    for (a, b), key in specialization.BY_PAIR.items():
        sp = specialization.SPECS[key]
        rows.append(dict(kind="discipline", primary=a, secondary=b, name=sp.name, emoji=sp.emoji,
                         ability=get_ability(sp.ability).name, desc=sp.description))
    for (a, b), key in specialization.BY_CLASS.items():
        sp = specialization.SPECS[key]
        rows.append(dict(kind="class", primary=a, secondary=b, name=sp.name, emoji=sp.emoji,
                         ability=get_ability(sp.ability).name, desc=sp.description))
    return rows


def _outlook_view(s):
    o = outlook.outlook_of(s)
    return dict(key=o.key, name=o.name, emoji=o.emoji, perk=o.perk, wish=o.wish) if o else None


def ability_view(a) -> dict:
    return dict(key=a.key, name=a.name, kind=a.kind, power=a.power, target=a.target, cooldown=a.cooldown,
                element=a.element, tier=a.tier, creator=a.creator, description=a.description)


def snapshot(g: Game) -> dict:
    slimes = [slime_view(g, s) for s in g.slimes()]
    parties = [dict(id=p.id, name=p.name, members=list(p.members), full=len(p.members) == g.parties.size,
                    synergy=round(g.party_synergy(p.id) - 1, 4) if len(p.members) > 1 else 0.0,
                    in_delve=p.id in g.delves,
                    entry=(g.entry_options(p.id) if p.members else [1]),
                    min_progress=min((g.slime(i).progress for i in p.members), default=0))
               for p in g.parties.parties.values()]
    return dict(
        tick=g.tick_count, day=g.day, wallet=g.wallet.to_dict(), party_size=g.parties.size,
        free_pull=dict(available=g.free_pull_available(), hours=g.hours_to_free_pull()),
        potions=dict(stock=[dict(kind=k.split(':')[0], grade=int(k.split(':')[1]), n=n) for k, n in sorted(g.potions.items())],
                     kinds=[dict(key=p.key, name=p.name, emoji=p.emoji, effect=p.effect, herbs=list(p.herbs),
                                 costs=[potions_mod.cost(p.key, i + 1) for i in range(5)])
                            for p in potions_mod.KINDS.values()],
                     lab=g.buildings.level("alchemy"),
                     grades=[dict(grade=i + 1, bonus=potions_mod.bonus(i + 1), hours=potions_mod.hours(i + 1),
                                  brew_hours=potions_mod.brew_hours(i + 1)) for i in range(5)],
                     herbs={c: g.wallet.get(potions_mod.herb_key(c)) for c in config.HERBS},
                     autonomy=g.autonomy, autonomy_share=config.AUTONOMY_SHARE),
        keeper=dict(level=g.keeper.level, xp=g.keeper.xp, xp_next=keeper_mod.xp_to_next(g.keeper.level),
                    title=keeper_mod.title(g.keeper.level), points=g.keeper.points, max_level=config.KEEPER_MAX_LEVEL,
                    branches={k: dict(name=v[0], emoji=v[1]) for k, v in keeper_mod.BRANCHES.items()},
                    skills=[dict(key=sk.key, branch=sk.branch, name=sk.name, emoji=sk.emoji, level=sk.level,
                                 per_rank=sk.per_rank, max_rank=sk.max_rank, rank=g.keeper.rank(sk.key),
                                 why_not=g.keeper.why_not(sk.key)) for sk in keeper_mod.SKILLS.values()],
                    actives=[dict(key=a.key, branch=a.branch, name=a.name, emoji=a.emoji, desc=a.desc,
                                  cooldown_days=a.cooldown_days, needs=keeper_mod.SKILLS[a.needs].name,
                                  unlocked=g.keeper.unlocked(a.key), ready=g.keeper.ready(a.key, g.day))
                             for a in keeper_mod.ACTIVES.values()]),
        family=dict(g.family_tree(), kinds={k: dict(label=relationships.LABEL[k], emoji=relationships.EMOJI[k])
                                            for k in relationships.KINDS},
                    bud_cost=config.BUD_COST),
        ascension=dict(stones={r: g.wallet.get(ascension.stone_key(r)) for r in config.RARITIES},
                       total=ascension.stone_total(g.wallet), values={r: ascension.stone_value(r) for r in config.RARITIES},
                       rarity_gel=config.RARITY_ASCEND_GEL, star_stones=config.STAR_ASCEND_STONES,
                       rates=config.STONE_RATES, merge=config.STONE_MERGE, max_party=config.ADV_MAX_PARTY,
                       max_runs=config.ADV_MAX_RUNS, chamber=g.buildings.level("chamber")),
        auto_care=g.needs.auto_care, slimes=slimes, parties=parties,
        buildings=g.building_report(),
        rest=dict(used=g.resting_count(), cap=g.buildings.rest_capacity()),
        conflicts=[dict(id=c.id, a=c.a, b=c.b, severity=c.severity, age=c.age, reason=c.reason)
                   for c in g.conflicts.conflicts],
        graveyard=list(g.graveyard)[-50:], journal=list(g.journal)[-60:],
        dungeon=dict(
            best_floor=g.best_floor, boss_every=config.MAIN_BOSS_EVERY, floors=g.intel_report(),
            max_floor=dungeon.MAX_FLOOR, cleared=g.descent_cleared,
            pit=_pit_view(g),
            delves={str(pid): dict(floor=d["floor"], start=d["start"], hours=d["hours"],
                                   boss_floor=g._checkpoint_after(d["floor"]), can_leave=g.can_leave(pid),
                                   knowledge=g._knowledge(d["floor"]),
                                   ready_in=(max(0, d.get("ready_tick", 0) - g.tick_count) if g.live else 0),
                                   next_hours=dungeon.clear_hours(d["floor"], sum(s.level for s in g._members_in("main", pid)) / max(1, len(g._members_in("main", pid))), g._knowledge(d["floor"]), max(1, len(g._members_in("main", pid)))),
                                   members=[m.id for m in g._members_in("main", pid)])
                    for pid, d in g.delves.items()},
            grind_depths=config.GRIND_DEPTHS, scout_hours=[config.SCOUT_MIN_HOURS, config.SCOUT_MAX_HOURS],
            scout_max_floors=config.SCOUT_MAX_FLOORS, scout_food=config.SCOUT_FOOD_PER_HOUR,
        ),
        clock=dict(mode=g.time_mode, scale=g.time_scale, scales=list(config.LIVE_SCALES),
                   lobby_rate=config.LIVE_LOBBY_RATE * g.time_scale, dungeon_rate=config.LIVE_DUNGEON_RATE * g.time_scale,
                   rate_now=(g.clock_rate() if g.live else None),
                   expeditions=[dict(names=[g.roster[i].name for i in e["ids"] if i in g.roster],
                                     hours=max(0, e["until"] - g.tick_count),
                                     real_min=round(max(0, e["until"] - g.tick_count) / max(1e-9, g.clock_rate()) * 60))
                                for e in g.expeditions] if g.live else []),
        stress=round(g.sacrifice_stress, 2),
        gear=dict(shop=[dict(key=x.key, name=x.name, emoji=x.emoji, slot=x.slot, tier=x.tier,
                             stats=x.stats, cost=x.cost) for x in g.gear_shop()],
                  all=[dict(key=x.key, name=x.name, emoji=x.emoji, slot=x.slot, tier=x.tier, stats=x.stats,
                            cost=x.cost) for x in equipment.GEAR],
                  inventory=dict(g.inventory.items), pit_lost=list(g.pit_lost),
                  vault=[_item_view(i) for i in sorted(g.vault.values(), key=lambda i: -i.uid)],
                  materials={m: g.wallet.get(m) for m in config.MATERIAL_OF.values()},
                  adventure=dict(max_party=config.ADV_MAX_PARTY, max_runs=config.ADV_MAX_RUNS,
                                 lure_cost=config.ADV_LURE_COST, rates=config.ITEM_RARITY_RATES,
                                 armory=g.buildings.level("armory"))),
        zones=[dict(key=z.key, name=z.name, duration=z.duration, danger=z.danger, desc=z.description,
                    rewards=z.rewards, purple=z.purple_chance) for z in ZONES],
        disciplines=[dict(key=d.key, name=d.name, emoji=d.emoji, style=d.style, perk=d.perk,
                          desc=d.description) for d in sparring.DISCIPLINES],
        elements=dict(basics=list(elements.BASICS),
                      list=[dict(key=e.key, name=e.name, emoji=e.emoji, tier=e.tier,
                                 components=sorted(e.components)) for e in elements.ELEMENTS],
                      recipes=[dict(a=sorted(k)[0], b=sorted(k)[1], result=v) for k, v in elements.RECIPES.items()],
                      beats=dict(elements.BEATS)),
        library=dict(catalog=[ability_view(a) for a in g.library.catalog()],
                     slots=g.library.spell_slots(), tier3=g.buildings.tier3_open(),
                     tier_mastery=config.SPELL_TIER_MASTERY, learn_cost=config.SPELL_LEARN_COST,
                     research_cost=config.RESEARCH_COST, study_cost=config.STUDY_COST),
        spell_defs={k: ability_view(get_ability(k)) for s in g.slimes() for k in s.spells},
        classes=[dict(key=a.key, name=a.name, emoji=a.emoji) for a in all_archetypes()],
        stances=list(BEHAVIORS),
        rates=dict(rarity=config.RARITY_RATES, purple_boost=config.PURPLE_RARITY_BOOST,
                   pull_cost=config.PULL_COST),
        mercy=dict(spar_cost=config.SPAR_COST, train_ticks=config.SPAR_TICKS),
        spec=dict(cost=config.SPEC_COST, style=config.SPEC_MIN_STYLE, level=config.SPEC_MIN_LEVEL, table=_spec_table()),
        outlooks=[dict(key=o.key, name=o.name, emoji=o.emoji, perk=o.perk) for o in outlook.OUTLOOKS.values()],
        max_stress_amp=config.SACRIFICE_STRESS_AMP,
    )


# ---- command handlers: (game, args) -> (log lines, result dict) ---------------------------------------
Handler = Callable[[Game, dict], Tuple[List[str], dict]]
HANDLERS: Dict[str, Handler] = {}


def command(name: str):
    def deco(fn: Handler) -> Handler:
        HANDLERS[name] = fn
        return fn
    return deco


def _msg(text: str) -> Tuple[List[str], dict]:
    return [text], {}


def _battle(report) -> dict:
    return dict(log=list(report.log), victory=report.victory, winner=report.winner, rounds=report.rounds,
                xp=report.xp, loot=dict(report.loot), deaths=list(report.deaths),
                knocked_out=list(report.knocked_out))


def _i(args: dict, key: str, default: Optional[int] = None) -> int:
    try:
        return int(args[key])
    except (KeyError, TypeError, ValueError):
        if default is not None:
            return default
        raise InvalidAction(f"Missing or invalid '{key}'.")


@command("state")
def _state(g, a):
    return [], {}


@command("pull")
def _pull(g, a):
    new = g.pull(_i(a, "n", 1), a.get("pay", "white_gel"))
    return ([f"Pulled {s.name} the {s.arch.name} ({s.rarity}, {s.star_str()})" for s in new],
            dict(pulled=[slime_view(g, s) for s in new]))


@command("feed")
def _feed(g, a):
    return _msg(g.feed(_i(a, "id")))


@command("sleep")
def _sleep(g, a):
    return _msg(g.sleep(_i(a, "id")))


@command("wake")
def _wake(g, a):
    return _msg(g.wake(_i(a, "id")))


@command("pet")
def _pet(g, a):
    return _msg(g.pet(_i(a, "id")))


@command("stance")
def _stance(g, a):
    return _msg(g.set_behavior(_i(a, "id"), a.get("stance", "")))


@command("hunt")
def _hunt(g, a):
    return _msg(g.hunt(_i(a, "id"), a.get("zone", "")))


@command("recall")
def _recall(g, a):
    return _msg(g.recall(_i(a, "id")))


@command("party_hunt")
def _party_hunt(g, a):
    return g.party_hunt(_i(a, "pid"), a.get("zone", "")), {}


@command("guide")
def _guide(g, a):
    return [], dict(sections=guide_mod.build())


@command("sync")
def _sync(g, a):
    return [], {}


@command("set_time")
def _set_time(g, a):
    return _msg(g.set_time_mode(a.get("mode", "turn"), a.get("scale")))


@command("wait")
def _wait(g, a):
    if g.live:
        raise InvalidAction("Time passes by itself in live mode (switch to turn-based in the menu to skip ahead).")
    hours = max(1, min(72, _i(a, "hours", 1)))
    ev = g.tick(hours)
    return [f"{hours} hour(s) pass."] + ev, {}


@command("auto_care")
def _auto_care(g, a):
    g.needs.auto_care = bool(a.get("on", True))
    return _msg(f"Auto-care {'on' if g.needs.auto_care else 'off'}.")


@command("rest")
def _rest(g, a):
    return _msg(g.rest(_i(a, "id")))


@command("party_rest")
def _party_rest(g, a):
    return _msg(g.party_rest(_i(a, "pid")))


@command("party_create")
def _party_create(g, a):
    p = g.create_party(str(a.get("name", ""))[:24])
    return _msg(f"Created party '{p.name}'.")


@command("party_add")
def _party_add(g, a):
    return _msg(g.party_add(_i(a, "pid"), _i(a, "id")))


@command("party_remove")
def _party_remove(g, a):
    return _msg(g.party_remove(_i(a, "id")))


@command("party_disband")
def _party_disband(g, a):
    g.party_disband(_i(a, "pid"))
    return _msg("Party disbanded.")


@command("party_fill")
def _party_fill(g, a):
    return _msg(f"Added {g.party_autofill(_i(a, 'pid'))} slime(s) to the party.")


@command("spar")
def _spar(g, a):
    r = g.spar(_i(a, "a"), _i(a, "b"), a.get("discipline", ""))
    return r.summary, dict(battle=[_battle(x) for x in r.reports])


@command("spar_party")
def _spar_party(g, a):
    r = g.spar_party(_i(a, "pid"), a.get("discipline", ""))
    return r.summary, dict(battle=[_battle(x) for x in r.reports])


@command("study")
def _study(g, a):
    return _msg(g.study(_i(a, "id"), a.get("element", "")))


@command("learn")
def _learn(g, a):
    return _msg(g.learn_spell(_i(a, "id"), a.get("spell", "")))


@command("forget")
def _forget(g, a):
    return _msg(g.forget_spell(_i(a, "id"), a.get("spell", "")))


@command("research_preview")
def _research_preview(g, a):
    pv = g.research_preview(_i(a, "id"), a.get("a", ""), a.get("b", ""))
    el = pv["element"]
    return [], dict(element=dict(key=el.key, name=el.name, emoji=el.emoji, tier=el.tier), cost=pv["cost"],
                    hours=pv["hours"], chance=round(pv["chance"], 3), a=ability_view(pv["a"]),
                    b=ability_view(pv["b"]))


@command("research")
def _research(g, a):
    return _msg(g.research(_i(a, "id"), a.get("a", ""), a.get("b", ""), (a.get("name") or None)))


@command("cancel_task")
def _cancel(g, a):
    return _msg(g.cancel_task(_i(a, "id")))


@command("upgrade")
def _upgrade(g, a):
    return _msg(g.upgrade_building(a.get("key", "")))


@command("buy_gear")
def _buy(g, a):
    return _msg(g.buy_gear(a.get("key", "")))


@command("equip")
def _equip(g, a):
    return _msg(g.equip(_i(a, "id"), a.get("key", "")))


@command("unequip")
def _unequip(g, a):
    return _msg(g.unequip(_i(a, "id"), a.get("slot", "")))


@command("equip_item")
def _equip_item(g, a):
    return _msg(g.equip_item(_i(a, "id"), _i(a, "uid")))


@command("unequip_item")
def _unequip_item(g, a):
    return _msg(g.unequip_item(_i(a, "id"), a.get("slot", "")))


@command("level_item")
def _level_item(g, a):
    return _msg(g.level_item(_i(a, "uid")))


@command("ascend_star")
def _ascend_star(g, a):
    return _msg(g.ascend_star(_i(a, "uid")))


@command("ascend_rarity")
def _ascend_rarity(g, a):
    return _msg(g.ascend_rarity(_i(a, "uid")))


@command("repair_item")
def _repair_item(g, a):
    return _msg(g.repair_item(_i(a, "uid")))


@command("salvage_item")
def _salvage_item(g, a):
    return _msg(g.salvage_item(_i(a, "uid")))


@command("fuse_ego")
def _fuse_ego(g, a):
    return g.fuse_ego(_i(a, "uid"), _i(a, "id")), {}


@command("adventure")
def _adventure(g, a):
    r = g.adventure([int(x) for x in a.get("ids", [])], _i(a, "runs", 1), bool(a.get("lure")))
    return r.summary + [f"Session over: {r.stop_reason}"], dict(battle=[_battle(x) for x in r.runs[-3:]])


@command("slime_rarity")
def _slime_rarity(g, a):
    return _msg(g.ascend_slime_rarity(_i(a, "id")))


@command("slime_star")
def _slime_star(g, a):
    return _msg(g.ascend_slime_star(_i(a, "id")))


@command("merge_stones")
def _merge_stones(g, a):
    return _msg(g.merge_stone_rarity(a.get("rarity", "")))


@command("destroy_slime")
def _destroy_slime(g, a):
    return g.destroy_slime(_i(a, "id")), {}


@command("quarry")
def _quarry(g, a):
    r = g.quarry([int(x) for x in a.get("ids", [])], _i(a, "runs", 1))
    return r.summary + [f"Session over: {r.stop_reason}"], dict(battle=[_battle(x) for x in r.runs[-3:]])


@command("keeper_learn")
def _keeper_learn(g, a):
    return _msg(g.keeper_learn(a.get("key", "")))


@command("keeper_use")
def _keeper_use(g, a):
    return _msg(g.keeper_use(a.get("key", "")))


@command("bud")
def _bud(g, a):
    return g.bud(_i(a, "a"), _i(a, "b")), {}


@command("talk")
def _talk(g, a):
    return _msg(g.talk(_i(a, "id")))


@command("autonomy")
def _autonomy(g, a):
    return _msg(g.set_autonomy(bool(a.get("on", True))))


@command("brew")
def _brew(g, a):
    return g.brew(_i(a, "id"), a.get("kind", ""), _i(a, "grade", 1)), {}


@command("use_potion")
def _use_potion(g, a):
    return _msg(g.use_potion(_i(a, "id"), a.get("kind", ""), _i(a, "grade", 1)))


@command("slime_repair")
def _slime_repair(g, a):
    return g.slime_repair(_i(a, "id")), {}


@command("mediate")
def _mediate(g, a):
    return _msg(g.mediate(_i(a, "cid"), a.get("method", "talk")))


@command("merge_preview")
def _merge_preview(g, a):
    t, d = _i(a, "target"), _i(a, "donor")
    return [], dict(xp=g.merge_preview(t, d), compat=g.compat(t, d))


@command("merge")
def _merge(g, a):
    return g.merge(_i(a, "target"), _i(a, "donor")), {}


@command("evolve")
def _evolve(g, a):
    return g.evolve(_i(a, "id")), {}


@command("compat")
def _compat(g, a):
    return [], g.compat(_i(a, "a"), _i(a, "b"))


@command("council")
def _council(g, a):
    c = g.council()
    rows = [dict(id=r["slime"].id, name=r["slime"].name, verdict=r["verdict"], score=r["score"],
                 avg_compat=r["avg_compat"], close=r["close"], reasons=r["reasons"]) for r in c["rows"]]
    merges = [dict(target=m["target"].id, target_name=m["target"].name, donor=m["donor"].id,
                   donor_name=m["donor"].name, xp=m["xp"], compat=m["compat"], grief=m["grief"], net=m["net"])
              for m in c["merges"]]
    return [], dict(rows=rows, merges=merges, stress=round(g.sacrifice_stress, 2))


@command("enter_dungeon")
def _enter(g, a):
    start = a.get("start")
    return _msg(g.enter_dungeon(_i(a, "pid"), int(start) if start not in (None, "") else None))


@command("leave_dungeon")
def _leave(g, a):
    return _msg(g.leave_dungeon(_i(a, "pid")))


@command("specialize")
def _specialize(g, a):
    return _msg(g.specialize(_i(a, "id"), a.get("discipline", "")))


@command("scout_plan")
def _scout_plan(g, a):
    return [], g.scout_plan(_i(a, "pid"), _i(a, "first"), _i(a, "last"))


@command("delve_next")
def _delve_next(g, a):
    r = g.delve_next(_i(a, "pid"))
    return [r.log[0]] + [l for l in r.log if "cleared" in l or "fallen" in l or "bounty" in l
                         or "found" in l or "carries" in l or "lost in" in l], dict(battle=[_battle(r)])


@command("delve_camp")
def _delve_camp(g, a):
    out = g.delve_camp(_i(a, "pid"), _i(a, "hours", 4))
    return (out or ["A quiet night at camp."]), {}


@command("descend")
def _descend(g, a):
    r = g.descend(_i(a, "pid"))
    return [r.log[0]], dict(battle=[_battle(r)])


@command("scout")
def _scout(g, a):
    r = g.scout(_i(a, "pid"), _i(a, "first"), _i(a, "last", _i(a, "first")), _i(a, "hours", 8))
    return r.log, dict(before=r.before, after=r.after, survivors=r.survivors, complete=r.complete,
                       required=r.required)


@command("grind")
def _grind(g, a):
    r = g.grind(_i(a, "pid"), _i(a, "depth", 3), min(60, _i(a, "runs", 1)))
    return r.summary + [f"Session over: {r.stop_reason}"], dict(battle=[_battle(x) for x in r.runs[-3:]])


@command("skirmish")
def _skirmish(g, a):
    r = g.battle(_i(a, "pid"), _i(a, "tier", 1))
    return [r.log[-1]], dict(battle=[_battle(r)])


# ---- session -----------------------------------------------------------------------------------------------
class Session:
    """Holds one Game. `call` is the only method transports need."""

    def __init__(self):
        self.game: Optional[Game] = None

    def new_game(self, seed: Optional[int] = None, party_size: int = 5) -> None:
        self.game = Game(seed, int(party_size))

    def call(self, cmd: str, args: Optional[dict] = None) -> dict:
        args = args or {}
        try:
            if cmd == "new_game":
                self.new_game(args.get("seed"), args.get("party_size", 5))
                return self._ok(["A new colony begins. The Last Gacha Well hums..."], {})
            if cmd == "load":
                self.game = Game.from_dict(args["save"])
                return self._ok(["Save loaded."], {})
            if self.game is None:
                return dict(ok=False, error="No game in progress.", log=[], result={}, state=None, save=None)
            if cmd not in HANDLERS:
                raise InvalidAction(f"Unknown command '{cmd}'.")
            woke = self.game.sync()                    # live mode: the wall clock moves the colony forward first
            log, result = HANDLERS[cmd](self.game, args)
            return self._ok(woke + log, result)
        except GameError as e:
            return self._fail(str(e))
        except KeyError as e:                         # unknown zone / class / spell keys from the client
            return self._fail(f"Unknown {str(e).strip(chr(39))}.")
        except (ValueError, TypeError) as e:
            return self._fail(f"Bad request: {e}")

    def call_json(self, cmd: str, args_json: str = "{}") -> str:
        """String in / string out - what the Pyodide transport uses."""
        return json.dumps(self.call(cmd, json.loads(args_json or "{}")))

    # -- envelopes
    def _ok(self, log, result) -> dict:
        return dict(ok=True, error=None, log=log, result=result, state=snapshot(self.game),
                    save=self.game.to_dict())

    def _fail(self, msg: str) -> dict:
        return dict(ok=False, error=msg, log=[], result={},
                    state=snapshot(self.game) if self.game else None, save=None)
