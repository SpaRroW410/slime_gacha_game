"""Text UI. Contains NO game rules - it only calls Game methods and prints results."""
import os
from typing import List

from . import config, dungeon, elements, terrain as terrain_mod
from .abilities import ABILITIES, get_ability
from .sparring import DISCIPLINES, style_label, style_levels
from .archetypes import BEHAVIORS
from .errors import GameError
from .game import Game
from .hunt import ZONES

BANNER = r"""
  ____  _ _                  ____            _
 / ___|| (_)_ __ ___   ___  / ___| __ _  ___| |__   __ _
 \___ \| | | '_ ` _ \ / _ \| |  _ / _` |/ __| '_ \ / _` |
  ___) | | | | | | | |  __/| |_| | (_| | (__| | | | (_| |
 |____/|_|_|_| |_| |_|\___| \____|\__,_|\___|_| |_|\__,_|
        ~ Pick Me Up, Little Goo! ~   (offline prototype)
"""

MENU = """
 [1] Roster           [2] Slime details      [3] Pull (free / white / purple)
 [4] Care (feed/sleep/pet)   [5] Set stance  [6] Hunt (one slime or a party)
 [7] Wait (time)      [8] Parties            [9] Dungeons / battles
 [t] Sparring arenas (fighting styles)   [l] Library & spell lab   [r] Rest Area
 [b] Buildings (upgrade)   [k] Council   [i] Inventory & Armory   [w] Wayfarer's Rift & relics   [o] Ascension, Quarry & Chamber
 [m] Merge  [e] Evolve  [c] Conflicts  [a] Auto-care  [j] Journal  [x] Graveyard  [s] Save  [q] Quit
"""


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return "q"


def _int(prompt: str):
    v = _ask(prompt)
    try:
        return int(v)
    except ValueError:
        raise GameError("Please enter a number.")


def show_roster(g: Game) -> None:
    if not g.roster:
        print("  (no slimes yet - try a pull!)")
    for s in g.slimes():
        print("  " + s.summary())


def show_status(g: Game) -> None:
    free = "READY" if g.free_pull_available() else f"in {g.hours_to_free_pull()}h"
    print(f"\n⏰ Day {g.day} (hour {g.tick_count}) | {g.wallet} | slimes: {len(g.roster)} "
          f"(🪦 {len(g.graveyard)}) | parties: {len(g.parties.parties)} (size {g.parties.size}) | "
          f"rest area: {g.resting_count()}/{g.buildings.rest_capacity()} |{f' sacrifice stress {g.sacrifice_stress:.1f} |' if g.sacrifice_stress >= 0.1 else ''} best floor {g.best_floor} | free pull: {free} | auto-care: {'on' if g.needs.auto_care else 'off'} | "
          f"conflicts: {len(g.conflicts.conflicts)}")


def show_slime(s) -> None:
    st = s.max_stats()
    print(f"\n{s.arch.emoji} {s.name} - {s.title()} ({s.rarity}, {s.star_str()}) Lv{s.level}/{s.level_cap}  "
          f"XP {s.xp}/{config.xp_to_next(s.level)}  stage {s.stage}  merged x{s.merged}")
    print(f"  HP {s.hp}/{s.max_hp}  ATK {st['atk']}  DEF {st['defense']}  MAG {st['mag']}  SPD {st['spd']}")
    print(f"  traits: {', '.join(s.traits)}  | stance: {s.behavior}  | state: {s.state}"
          + (f" ({s.hunt.zone}, {s.hunt.ticks_left}h left)" if s.hunt else ""))
    print(f"  mood: {s.mood_label()} (power x{s.power_multiplier():.2f})  wins: {s.wins}"
          + ("  [GROUNDED]" if s.grounded else ""))
    bars = []
    for k in config.NEED_ORDER:
        v = s.needs.get(k)
        bars.append(f"{k[:4]} {'█' * int(v // 10)}{'░' * (10 - int(v // 10))} {int(v):>3}")
    print("  needs: " + " | ".join(bars))
    dom = s.needs.dominant()
    if dom:
        wish = {"energy": "needs sleep", "food": "is hungry", "safety": "feels unsafe (hurt)",
                "belonging": "feels lonely - pet or pair it", "esteem": "wants to prove itself - hunt or battle!"}
        print(f"  ➜ {s.name} {wish[dom]}.")
    print(f"  abilities: {', '.join(get_ability(k).name for k in s.known_abilities())}")
    show_elements(s)
    show_style_morale(s)
    if s.gear:
        from .equipment import GEAR
        print("  gear: " + ", ".join(f"{GEAR.get(k).emoji}{GEAR.get(k).name}" for k in s.gear.values()))


def show_style_morale(s) -> None:
    from .social import SocialEngine
    from .outlook import outlook_of
    o = outlook_of(s)
    print(f"  dungeon progress: floor {s.progress} | outlook: " + (f"{o.emoji} {o.name} ({o.perk})" if o else "undecided")
          + f" | experience: {dict(s.exp) or '-'}")
    lv = style_levels(s)
    styles = ", ".join(f"{DISCIPLINES.get(k).style} {v}" for k, v in lv.items() if v) or "none yet"
    print(f"  fighting style: {style_label(s)}  (all: {styles})")
    print(f"  morale: {int(s.morale)} ({SocialEngine.morale_label(s.morale)}) -> fight power x"
          f"{SocialEngine.morale_factor(s.morale):.2f}")


def show_elements(s) -> None:
    if not elements.can_master(s):
        print(f"  elements: locked (needs {config.MASTERY_MIN_STARS}★+, any class)")
        return
    parts = []
    for b in s.attuned:
        el = elements.get(b)
        parts.append(f"{el.emoji}{el.name} L{elements.basic_level(s, b)}/{elements.mastery_cap(s)}")
    print(f"  elements [{len(s.attuned)}/{elements.slot_count(s)} slots]: " + (", ".join(parts) or "none yet"))
    if s.spells:
        print("  spells: " + ", ".join(f"{elements.get(get_ability(k).element).emoji}{get_ability(k).name}"
                                      for k in s.spells))


def show_catalog(g: Game) -> None:
    for a in g.library.catalog():
        el = elements.get(a.element)
        cost = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in config.SPELL_LEARN_COST[a.tier].items())
        tgt = a.target.replace("_", " ")
        print(f"  {el.emoji} {a.name:<18} T{a.tier} {a.kind:<6} pow {a.power} cd {a.cooldown} -> {tgt}"
              f"  needs mastery {config.SPELL_TIER_MASTERY[a.tier]} | {cost}   [{a.key}]")


def show_recipes() -> None:
    for pair, res in elements.RECIPES.items():
        a, b = sorted(pair)
        r = elements.get(res)
        print(f"  {elements.get(a).emoji}{elements.get(a).name} + {elements.get(b).emoji}{elements.get(b).name}"
              f" = {r.emoji}{r.name} (tier {r.tier}; needs mastery {config.SPELL_TIER_MASTERY[r.tier]})")
    print("  Wheel: Water > Fire > Wind > Earth > Water (x1.5 damage, x0.7 the other way)")


def sparring_menu(g: Game) -> None:
    print("  Sparring = slimes duel each other to develop a FIGHTING STYLE. No XP. Non-lethal: the loser is left at"
          " 1 HP\n  (the Rest Area heals them). Costs 2 white gel + 3 hours per duel.")
    for i, d in enumerate(DISCIPLINES.all(), 1):
        print(f"  [{i}] {d.emoji} {d.name} -> {d.style}: {d.perk}")
    print(f"  Training Grounds level {g.buildings.level('training_grounds')}: "
          f"{g.buildings.describe('training_grounds')}")
    d = DISCIPLINES.all()[_int("arena #: ") - 1].key
    who = _ask("spar [s]ingle duel or a whole [p]arty: ").lower()[:1]
    if who == "p":
        show_parties(g)
        res = g.spar_party(_int("party #: "), d)
    else:
        show_roster(g)
        res = g.spar(_int("first slime id: "), _int("second slime id: "), d)
    print("\n".join("  " + x for x in res.summary))


def rest_menu(g: Game) -> None:
    print(f"  🛏️ Rest Area level {g.buildings.level('rest_area')}: {g.buildings.describe('rest_area')} "
          f"({g.resting_count()}/{g.buildings.rest_capacity()} used)")
    act = _ask("send a [s]lime, a whole [p]arty, or [w]ake someone: ").lower()[:1]
    if act == "p":
        show_parties(g)
        print("  " + g.party_rest(_int("party #: ")))
    elif act == "w":
        print("  " + g.wake(_int("slime id: ")))
    else:
        show_roster(g)
        print("  " + g.rest(_int("slime id: ")))


def buildings_menu(g: Game) -> None:
    rows = g.building_report()
    for i, r in enumerate(rows, 1):
        cost = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in r["cost"].items()) if r["cost"] else "MAX"
        print(f"  [{i}] {r['emoji']} {r['name']} L{r['level']}/{r['max']}: {r['now']}")
        if r["nxt"]:
            print(f"        next level ({cost}): {r['nxt']}")
    c = _ask("upgrade which # (Enter = none): ")
    if c:
        print("  " + g.upgrade_building(rows[int(c) - 1]["key"]))


def council_menu(g: Game) -> None:
    from .social import SocialEngine
    print("  [1] Keep-or-sacrifice advice   [2] Compatibility of two slimes   [3] Morale board")
    c = _ask("council: ")
    if c == "1":
        data = g.council()
        print(f"  Sacrifice stress: {g.sacrifice_stress:.1f} (each recent merge makes the next one cost "
              f"{config.SACRIFICE_STRESS_AMP:.0%} more morale and lowers everyone's morale target; decays 1/day)")
        for r in data["rows"]:
            s = r["slime"]
            print(f"  {r['verdict']:<11} {r['score']:>5}  #{s.id:<3} {s.arch.emoji} {s.name:<10} "
                  f"{s.star_str()} {s.rarity:<9} Lv{s.level:<2} compat avg {r['avg_compat']:+d}  "
                  f"({', '.join(r['reasons']) or '-'})")
        if data["merges"]:
            print("  Best merges (target <- donor; the donor is CONSUMED):")
            for m in data["merges"][:3]:
                print(f"    #{m['target'].id} {m['target'].name} <- #{m['donor'].id} {m['donor'].name}: "
                      f"+{m['xp']} XP, compat {m['compat']:+d}, colony morale cost {m['grief']}")
    elif c == "2":
        show_roster(g)
        r = g.compat(_int("first slime id: "), _int("second slime id: "))
        print(f"  Compatibility {r['total']:+d} ({r['label']}): " +
              ", ".join(f"{k} {v:+d}" for k, v in r["parts"].items() if v))
    elif c == "3":
        for s in sorted(g.slimes(), key=lambda s: s.morale):
            print(f"  #{s.id:<3} {s.name:<10} morale {int(s.morale):>3} {SocialEngine.morale_label(s.morale):<8}"
                  f" (power x{SocialEngine.morale_factor(s.morale):.2f})")


def _pick_spell(s, prompt: str) -> str:
    for i, k in enumerate(s.spells, 1):
        print(f"    [{i}] {get_ability(k).name}")
    return s.spells[_int(prompt) - 1]


def library_menu(g: Game) -> None:
    print("  [1] Spell catalogue   [2] Study an element   [3] Learn a spell   [4] Forget a spell\n"
          "  [5] SPELL LAB: fuse two spells into a new element   [6] Element recipes   [7] Elemental sheet\n"
          "  [8] SPECIALIZE: turn cross-training into a hybrid class (Battlemage, Spellknight ...)")
    c = _ask("library: ")
    if c == "1":
        show_catalog(g)
    elif c == "6":
        show_recipes()
    elif c in ("2", "3", "4", "5", "7", "8"):
        show_roster(g)
        s = g.slime(_int("slime id: "))
        if c == "2":
            print("  basics: " + ", ".join(elements.BASICS))
            print("  " + g.study(s.id, _ask("element: ").lower()))
        elif c == "3":
            show_catalog(g)
            print("  " + g.learn_spell(s.id, _ask("spell key: ")))
        elif c == "4":
            print("  " + g.forget_spell(s.id, _pick_spell(s, "forget #: ")))
        elif c == "5":
            if len(s.spells) < 2:
                raise GameError(f"{s.name} needs two learned elemental spells to experiment.")
            a, b = _pick_spell(s, "first spell #: "), _pick_spell(s, "second spell #: ")
            pv = g.research_preview(s.id, a, b)
            cost = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in pv["cost"].items())
            el = pv["element"]
            print(f"  {pv['a'].name} + {pv['b'].name} => {el.emoji}{el.name} (tier {el.tier}) | cost {cost} | "
                  f"{pv['hours']}h | success {int(pv['chance'] * 100)}% (failure hurts)")
            if _ask("  start the experiment? (y/n): ").lower() == "y":
                print("  " + g.research(s.id, a, b, _ask("  name your spell (Enter = auto): ") or None))
        elif c == "8":
            from .specialization import options
            for r in options(s):
                print(f"   {r['spec'].emoji} {r['spec'].name} via {r['style']} (lvl {r['level']}): "
                      + ("READY" if r["ok"] else r["reason"]) + f" - {r['spec'].description}")
            if s.spec:
                print("  already specialized")
            else:
                d = _ask("discipline to specialize in (sword/archery/magic, Enter = cancel): ")
                if d:
                    print("  " + g.specialize(s.id, d))
        else:
            show_slime(s)


def show_pulls(new) -> None:
    for s in new:
        print(f"  [{config.RARITY_TAG[s.rarity]}] {s.rarity.upper():<9} {s.star_str()} {s.arch.emoji} {s.name} "
              f"the {s.arch.name}  (traits: {', '.join(s.traits)})")


def show_parties(g: Game) -> None:
    if not g.parties.parties:
        print("  (no parties - create one from the Parties menu)")
    for p in g.parties.parties.values():
        names = ", ".join(g.slime(i).name for i in p.members) or "empty"
        syn = f" | synergy {g.party_synergy(p.id) - 1:+.1%}" if len(p.members) > 1 else ""
        print(f"  Party #{p.id} '{p.name}' [{len(p.members)}/{g.parties.size}]: {names}{syn}")


def show_graveyard(g: Game) -> None:
    if not g.graveyard:
        print("  The Memorial Pond is still. Nobody has fallen yet.")
    for d in g.graveyard:
        print(f"  🪦 {d['name']} the {d['archetype'].title()} ({d['rarity']}, {'★' * d['stars']}) Lv{d['level']} "
              f"- hour {d['tick']}: {d['cause']}")


def show_events(ev: List[str]) -> None:
    for e in ev:
        print("  " + e)
    if not ev:
        print("  (a quiet while passes)")


def pick_zone() -> str:
    zs = ZONES.all()
    for i, z in enumerate(zs, 1):
        print(f"  [{i}] {z.name} - {z.duration}h, danger {z.danger} - {z.description}")
    return zs[_int("zone #: ") - 1].key


def show_intel(g: Game, first: int = 1, last: int = None) -> None:
    rows = g.intel_report(first, last)
    print(f"  Knowledge of the Hollow Descent (floors {rows[0]['floor']}-{rows[-1]['floor']}); best floor ever cleared: {g.best_floor}")
    for r in rows:
        print(f"   floor {r['floor']}{' [BOSS]' if r['boss'] else ''}  knowledge {r['knowledge']:.0f}%")
        if r["knowledge"] > 0:
            for ln in r["lines"]:
                print(f"      - {ln}")


def dungeon_menu(g: Game) -> None:
    th = dungeon.pit_theme(g.dungeon_seed, g.day)
    print("  [1] The Gloop Pit      - committed grinding session: no leaving until all runs are done or the whole party is down.\n"
          "                           A downed slime loses XP + morale and drops its gear (survivors may bring it back).\n"
          f"                           TODAY (day {g.day + 1}): {th.terrain.emoji} {th.title} - {terrain_mod.describe(th.terrain)}")
    print("  [2] The Hollow Descent - ROUGH, permadeath. Walk the floors in order; you may only leave after a BOSS floor\n"
          f"                           (every {config.MAIN_BOSS_EVERY}). Each slime must have cleared the floors above; other parties may re-walk them.")
    print("  [3] Scout floors with an exploration party (must reach 100% or the party is lost)   [4] Intel report   [5] Skirmish")
    mode = _ask("dungeon: ")
    if mode == "4":
        show_intel(g)
        return
    show_parties(g)
    pid = _int("party #: ")
    if mode == "1":
        depth = _int(f"depth 1-{config.GRIND_DEPTHS} (3 = your level): ")
        runs = _int("number of runs (a COMMITMENT): ")
        res = g.grind(pid, depth, runs)
        print("\n".join("  " + x for x in res.summary))
        print(f"  Session over: {res.stop_reason}")
    elif mode == "2":
        if pid not in g.delves:
            opts = g.entry_options(pid)
            s = _ask(f"start at floor {opts} (Enter = {opts[-1]}): ")
            print("  " + g.enter_dungeon(pid, int(s) if s else None))
        while True:
            st = g.delve_status(pid)
            print(f"  Inside: floor {st['floor']} (next exit: after the boss on {st['boss_floor']}), {st['hours']}h in, "
                  f"knowledge of this floor {st['knowledge']:.0f}%, party: "
                  + ", ".join(f"{s.name} {s.hp}/{s.max_hp}" for s in st["members"]))
            act = _ask("  [f]ight next floor / [c]amp / [i]ntel / " + ("[x] LEAVE (checkpoint) / " if st["can_leave"] else "")
                       + "[b]ack to menu (the party stays inside!): ").lower()[:1]
            if act == "f":
                print("\n".join(g.delve_next(pid).log[-18:]))
            elif act == "c":
                print("\n".join("  " + x for x in g.delve_camp(pid, _int("hours to camp (1-24): ")) or ["  (quiet night)"]))
            elif act == "i":
                show_intel(g, st["floor"], st["floor"] + 4)
            elif act == "x":
                print("  " + g.leave_dungeon(pid))
                break
            else:
                break
            if pid not in g.delves:
                break
    elif mode == "3":
        first, last = _int("first floor to scout: "), _int("last floor to scout: ")
        plan = g.scout_plan(pid, first, last)
        print(f"  Estimate: ~{plan['nominal']}h (somewhere between {plan['low']}h and {plan['high']}h), skill x{plan['skill']}.")
        print(f"  Supplies are paid up front: {config.SCOUT_FOOD_PER_HOUR:g} food per budgeted hour. SAFE budget: {plan['safe']}h "
              f"({plan['food']} food). Too little time and the whole party is lost!")
        res = g.scout(pid, first, last, _int("hour budget: "))
        print("\n".join("  " + x for x in res.log))
        if res.complete:
            show_intel(g, first, last)
    elif mode == "5":
        print("\n".join(g.battle(pid, _int("tier 1-3 (4 = boss): ")).log))


def inventory_menu(g: Game) -> None:
    from .equipment import GEAR
    inv = ", ".join(f"{GEAR.get(k).emoji}{GEAR.get(k).name} x{n}" for k, n in g.inventory.items.items()) or "empty"
    print(f"  Inventory: {inv}")
    if g.pit_lost:
        print("  Left behind in the Pit: " + ", ".join(GEAR.get(k).name for k in g.pit_lost))
    print("  [1] Armory (buy)   [2] Equip   [3] Unequip   [4] Who wears what")
    c = _ask("inventory: ")
    if c == "1":
        for gr in g.gear_shop():
            cost = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in gr.cost.items())
            print(f"   {gr.emoji} {gr.name:<16} T{gr.tier} {gr.slot:<6} {gr.stats}  {cost}   [{gr.key}]")
        print("  " + g.buy_gear(_ask("gear key: ")))
    elif c == "2":
        show_roster(g)
        print("  " + g.equip(_int("slime id: "), _ask("gear key: ")))
    elif c == "3":
        show_roster(g)
        print("  " + g.unequip(_int("slime id: "), _ask("slot (weapon/armor/charm): ")))
    elif c == "4":
        for s in g.slimes():
            print(f"  #{s.id:<3} {s.name:<10} " + (", ".join(f"{GEAR.get(k).emoji}{GEAR.get(k).name}"
                                                        for k in s.gear.values()) or "-"))


def rift_menu(g: Game) -> None:
    mats = "  ".join(f"{k} {g.wallet.get(k)}" for k in config.MATERIAL_OF.values())
    print(f"  Materials: {mats}")
    for it in sorted(g.vault.values(), key=lambda i: i.uid):
        print(f"   #{it.uid:<3} {it.label()}  " + ", ".join(f"+{v} {k}" for k, v in it.base_stats().items())
              + (f"  [{', '.join(it.mod_text(m) for m in it.mods)}]" if it.mods else "")
              + ("" if it.unbreakable else f"  dur {it.durability}/{it.max_durability}"))
    for s in g.slimes():
        for it in s.items.values():
            print(f"   #{it.uid:<3} {it.label()} worn by {s.name} (compat {it.compat(s)}%)")
    print("  [a] Adventure   [e] Equip   [u] Unequip   [l] Level   [s] Ascend star   [r] Raise rarity   "
          "[p] Repair   [b] Break down   [f] Fuse ego")
    c = _ask("rift: ").lower()[:1]
    if c == "a":
        show_roster(g)
        ids = [int(x) for x in _ask("slime ids (1-5, space separated): ").split()]
        r = g.adventure(ids, _int("runs: "), _ask("lure (uses purple gel)? y/n: ").lower() == "y")
        print("\n".join("  " + x for x in r.summary) + f"\n  Session over: {r.stop_reason}")
    elif c == "e":
        print("  " + g.equip_item(_int("slime id: "), _int("relic #: ")))
    elif c == "u":
        print("  " + g.unequip_item(_int("slime id: "), _ask("slot: ")))
    elif c and c in "lsrpb":
        fn = dict(l=g.level_item, s=g.ascend_star, r=g.ascend_rarity, p=g.repair_item, b=g.salvage_item)[c]
        print("  " + fn(_int("relic #: ")))
    elif c == "f":
        print("\n".join("  " + x for x in g.fuse_ego(_int("relic #: "), _int("soul slime id (consumed!): "))))


def ascension_menu(g: Game) -> None:
    from . import ascension
    stones = "  ".join(f"{r} {g.wallet.get(ascension.stone_key(r))}" for r in config.RARITIES)
    print(f"  Stones: {stones}   (worth {ascension.stone_total(g.wallet)} common)")
    print(f"  Potions: {dict(g.potions) or 'none'}   herbs " + ", ".join(f"{c} {g.wallet.get('herb_' + c)}" for c in config.HERBS) + f"   autonomy {'on' if g.autonomy else 'off'}")
    print("  [r] Ascend rarity (white gel)   [s] Ascend star (stones)   [m] Merge stones up   "
          "[q] Starfall Quarry   [d] Destroy in the chamber\n  [b] Brew a potion   [p] Drink a potion   "
          "[f] Slime repairs its gear   [v] Slime vitals (stamina, attributes)   [z] Toggle slime autonomy (66%)")
    c = _ask("ascension: ").lower()[:1]
    if c == "r":
        show_roster(g)
        print("  " + g.ascend_slime_rarity(_int("slime id: ")))
    elif c == "s":
        show_roster(g)
        print("  " + g.ascend_slime_star(_int("slime id: ")))
    elif c == "m":
        print("  " + g.merge_stone_rarity(_ask("rarity to merge up (common/uncommon/rare/epic): ")))
    elif c == "q":
        show_roster(g)
        ids = [int(x) for x in _ask("slime ids (1-5, space separated): ").split()]
        r = g.quarry(ids, _int("runs: "))
        print("\n".join("  " + x for x in r.summary) + f"\n  Session over: {r.stop_reason}")
    elif c == "b":
        from . import potions
        print("  kinds: " + ", ".join(potions.KINDS))
        print("\n".join("  " + x for x in g.brew(_int("brewer id: "), _ask("kind: "), _int("grade 1-5: "))))
    elif c == "p":
        print("  " + g.use_potion(_int("slime id: "), _ask("kind: "), _int("grade: ")))
    elif c == "f":
        print("\n".join("  " + x for x in g.slime_repair(_int("slime id: "))))
    elif c == "z":
        print("  " + g.set_autonomy(not g.autonomy))
    elif c == "v":
        from . import attributes
        s = g.slime(_int("slime id: "))
        print(f"  {s.name}: stamina {s.stamina}/{s.max_stamina}; buffs {s.buffs or 'none'}")
        print("  star attributes: " + (", ".join(f"{a['label']} +{a['value']:.0%}" for a in attributes.star_attributes(s)) or "none"))
        print("  rarity skills: " + (", ".join(get_ability(k).name for k in attributes.rarity_skills(s)) or "none"))
        print(f"  weapons: remembers {s.weapon_memory}, proficiency {s.proficiency}")
    elif c == "d":
        show_roster(g)
        sid = _int("slime id: ")
        print(f"  The chamber would yield: {g.chamber_preview(sid)}")
        if _ask("  Destroy forever? (y/n): ").lower() == "y":
            print("\n".join("  " + x for x in g.destroy_slime(sid)))


def party_menu(g: Game) -> None:
    show_parties(g)
    act = _ask("[n]ew / [a]dd slime / [r]emove slime / [f]ill with best free / [d]isband / [z] rest party (Rest Area): ").lower()[:1]
    if act == "n":
        p = g.create_party(_ask("name (optional): "))
        print(f"  Created party #{p.id} '{p.name}' - needs {g.parties.size} slimes.")
    elif act == "a":
        show_roster(g)
        print("  " + g.party_add(_int("party #: "), _int("slime id: ")))
    elif act == "r":
        print("  " + g.party_remove(_int("slime id: ")))
    elif act == "f":
        pid = _int("party #: ")
        print(f"  Added {g.party_autofill(pid)} slime(s).")
    elif act == "d":
        g.party_disband(_int("party #: "))
        print("  Party disbanded.")
    elif act == "z":
        print("  " + g.party_rest(_int("party #: ")))


def handle(g: Game, choice: str) -> bool:
    """Returns False to quit."""
    if choice == "1":
        show_roster(g)
    elif choice == "2":
        show_roster(g)
        show_slime(g.slime(_int("slime id: ")))
    elif choice == "3":
        pay = _ask("pay with [f]ree daily / [w]hite gel / [p]urple gel: ").lower()[:1]
        pay = {"f": "free", "w": "white_gel", "p": "purple_gel"}.get(pay)
        if not pay:
            raise GameError("Choose f, w or p.")
        n = 1 if pay == "free" else _int(f"how many (10 {pay} each)? ")
        show_pulls(g.pull(n, pay))
    elif choice == "4":
        show_roster(g)
        sid = _int("slime id: ")
        act = _ask("[f]eed (1 food) / [s]leep / [w]ake / [p]et: ").lower()
        print("  " + {"f": g.feed, "s": g.sleep, "w": g.wake, "p": g.pet}.get(act, lambda _: "Unknown action.")(sid))
    elif choice == "5":
        show_roster(g)
        sid = _int("slime id: ")
        print("  " + g.set_behavior(sid, _ask(f"stance ({'/'.join(BEHAVIORS)}): ").lower()))
    elif choice == "6":
        who = _ask("hunt with a [s]lime, a [p]arty, or [r]ecall everyone: ").lower()[:1]
        if who == "r":
            for s in g.slimes():
                g.recall(s.id)
            print("  Everyone is back.")
        elif who == "p":
            show_parties(g)
            pid = _int("party #: ")
            print("\n".join("  " + x for x in g.party_hunt(pid, pick_zone())))
        else:
            show_roster(g)
            sid = _int("slime id: ")
            print("  " + g.hunt(sid, pick_zone()))
    elif choice == "7":
        n = _int("hours to wait (1-72): ")
        show_events(g.tick(max(1, min(72, n))))
    elif choice == "8":
        party_menu(g)
    elif choice == "9":
        show_parties(g)
        dungeon_menu(g)
    elif choice == "m":
        show_roster(g)
        t, d = _int("TARGET id (keeps): "), _int("DONOR id (consumed!): ")
        print(f"  Target would gain ~{g.merge_preview(t, d)} XP.")
        if _ask("  Confirm merge? (y/n): ").lower() == "y":
            print("\n".join("  " + x for x in g.merge(t, d)))
    elif choice == "e":
        show_roster(g)
        sid = _int("slime id: ")
        from .growth import evolve_cost
        print(f"  Cost: {evolve_cost(g.slime(sid))} essence.")
        print("\n".join("  " + x for x in g.evolve(sid)))
    elif choice == "c":
        if not g.conflicts.conflicts:
            print("  The colony is peaceful.")
        for c in g.conflicts.conflicts:
            print(f"  #{c.id}: {g.slime(c.a).name} vs {g.slime(c.b).name} - {c.reason} (severity {c.severity})")
        if g.conflicts.conflicts:
            cid = _int("conflict # to mediate (0 = skip): ")
            if cid:
                print("  " + g.mediate(cid, _ask("[t]alk / [s]nack (2 food): ").lower().startswith("s") and "snack" or "talk"))
    elif choice == "a":
        g.needs.auto_care = not g.needs.auto_care
        print(f"  auto-care {'ON' if g.needs.auto_care else 'OFF'}")
    elif choice == "t":
        sparring_menu(g)
    elif choice == "r":
        rest_menu(g)
    elif choice == "b":
        buildings_menu(g)
    elif choice == "k":
        council_menu(g)
    elif choice == "i":
        inventory_menu(g)
    elif choice == "w":
        rift_menu(g)
    elif choice == "o":
        ascension_menu(g)
    elif choice == "l":
        library_menu(g)
    elif choice == "x":
        show_graveyard(g)
    elif choice == "j":
        print("\n".join("  " + x for x in g.journal[-20:]) or "  (empty)")
    elif choice == "q":
        return False
    return True


def run_interactive(seed, save_path: str, party_size: int = config.PARTY_SIZE) -> None:
    print(BANNER)
    if os.path.exists(save_path) and _ask(f"Load {save_path}? (y/n): ").lower() == "y":
        g = Game.load(save_path)
    else:
        g = Game(seed, party_size)
        print("Welcome, Keeper. The Last Gacha Well hums. Claim your free daily pull (menu 3 -> f)!\n"
              "Beware: slimes that starve, hunt badly or fall in battle are gone for good.")
    while True:
        show_status(g)
        print(MENU)
        choice = _ask("> ").lower()
        if choice == "s":
            g.save(save_path)
            print(f"  saved to {save_path}")
            continue
        try:
            if not handle(g, choice):
                if _ask("Save before quitting? (y/n): ").lower() == "y":
                    g.save(save_path)
                print("Goodbye, Keeper. The goo will wait. 🫧")
                return
        except GameError as e:
            print(f"  ✋ {e}")
        except (ValueError, IndexError):
            print("  ✋ That didn't look right.")


def run_demo(seed: int) -> None:
    """Non-interactive tour: free pull, gacha, parties, hunting, conflict, battle, death, merge."""
    g = Game(seed)
    print(BANNER)
    print("== 1. GACHA: daily free pull, then a 10x white-gel pull, then 1 purple-gel pull ==")
    show_pulls(g.pull(1, "free"))
    try:
        g.pull(1, "free")
    except GameError as e:
        print(f"  ✋ {e}")
    show_pulls(g.pull(10, "white_gel"))
    show_pulls(g.pull(1, "purple_gel"))
    show_status(g)

    print("\n== 2. PARTIES: two fixed-size parties of 5 ==")
    for name in ("Vanguard", "Reserve"):
        p = g.create_party(name)
        g.party_autofill(p.id)
    show_parties(g)

    print("\n== 3. NEEDS & SLEEP: wait 12 hours (auto-care on) ==")
    show_events([e for e in g.tick(12) if "Conflict" not in e][:8])
    show_slime(g.slimes()[0])

    print("\n== 4. AUTO-HUNT: the Reserve party hunts the Meadow ==")
    print("\n".join("  " + x for x in g.party_hunt(2, "meadow")))
    show_events(g.tick(4))
    show_status(g)

    print("\n== 4b. LIBRARY (the demo hires a 3-star scholar: ANY class can master elements) ==")
    sch = g.gacha.make_slime("rare", "barbarian", stars=3)
    g.roster[sch.id] = sch
    g.wallet.add("white_gel", 400)
    g.wallet.add("essence", 60)
    for el in ("fire", "wind"):
        print("  " + g.study(sch.id, el))
        show_events([e for e in g.tick(4) if "studied" in e])
        sch.mastery_xp[el] = 130            # (demo shortcut: a few more study sessions)
        sch.needs.v["energy"] = 100
    print("  " + g.learn_spell(sch.id, "ember"))
    print("  " + g.learn_spell(sch.id, "gust"))
    pv = g.research_preview(sch.id, "ember", "gust")
    print(f"  Fusing Ember + Gust => {pv['element'].emoji}{pv['element'].name}, {int(pv['chance'] * 100)}% chance")
    for attempt in range(3):
        sch.hp, sch.needs.v["energy"] = sch.max_hp, 100
        print("  " + g.research(sch.id, "ember", "gust", "Thunder Spear"))
        done = [e for e in g.tick(6) if "experiment" in e or "invented" in e or "recreated" in e]
        show_events(done)
        if any("invented" in e or "recreated" in e for e in done):
            break
    show_slime(sch)

    print("\n== 4c. SPARRING (fighting styles, no XP) -> RESTING AREA -> BUILDINGS ==")
    g.wallet.add("white_gel", 300)
    g.wallet.add("essence", 40)
    g.conflicts.conflicts.clear()      # (the demo calls a truce so everyone can train)
    for s in g.slimes():
        s.grounded = False
        s.hp, s.state = s.max_hp, "idle"
        s.needs.v["energy"] = s.needs.v["food"] = 100
    res = g.spar_party(1, "sword")
    print("\n".join("  " + x for x in res.summary[:9]))
    print("  HP after sparring: " + ", ".join(f"{s.name} {s.hp}/{s.max_hp}" for s in g.party_members(1)))
    print("  " + g.party_rest(1))
    g.tick(4)
    print("  4 hours later:     " + ", ".join(f"{s.name} {s.hp}/{s.max_hp}" for s in g.party_members(1)))
    print("  " + g.upgrade_building("training_grounds"))
    print("  " + g.upgrade_building("barracks"))
    for r in g.building_report():
        print(f"  {r['emoji']} {r['name']} L{r['level']}: {r['now']}")
    a, b = g.party_members(1)[:2]
    c = g.compat(a.id, b.id)
    print(f"  Compatibility {a.name} & {b.name}: {c['total']:+d} ({c['label']}) "
          + ", ".join(f"{k} {v:+d}" for k, v in c['parts'].items() if v))
    print(f"  Vanguard synergy {g.party_synergy(1) - 1:+.1%}; morale: "
          + ", ".join(f"{s.name} {int(s.morale)}" for s in g.party_members(1)))

    print("\n== 4d. SPECIALIZATION: the barbarian scholar cross-trains in magic ==")
    sch.level, sch.style_xp["magic"] = 5, config.STYLE_XP[2]
    sch.state, sch.hp = "idle", sch.max_hp
    print("  " + g.specialize(sch.id, "magic"))
    print(f"  {sch.name}: {sch.title()} | ATK {sch.max_stats()['atk']} MAG {sch.max_stats()['mag']} | abilities: "
          + ", ".join(get_ability(k).name for k in sch.known_abilities()))

    print("\n== 5. CONFLICT: let the colony simmer for 24h ==")
    ev = g.tick(24)
    show_events([e for e in ev if "Conflict" in e or "brawl" in e or "died" in e][:8])
    for c in list(g.conflicts.conflicts)[:2]:
        print("  " + g.mediate(c.id, "talk"))

    print("\n== 6. GRINDING DUNGEON: a committed Gloop Pit session (downed slimes drop gear, lose XP + morale) ==")
    g.conflicts.conflicts.clear()   # keep the demo uninterrupted by brawls
    g.wallet.add("food", 60)
    g.wallet.add("white_gel", 200)
    for s in g.slimes():          # top everyone up so the demo starts healthy
        s.state, s.hunt, s.grounded = "idle", None, False
        s.hp, s.needs.v["energy"], s.needs.v["food"] = s.max_hp, 100, 100
    for s, key in zip(g.party_members(1), ("wooden_club", "hunting_bow", "apprentice_wand", "leather_wrap",
                                           "lucky_pebble")):
        g.buy_gear(key)
        print("  " + g.equip(s.id, key))
    res = g.grind(1, 4, 5)
    print("\n".join("  " + x for x in res.summary[:16]))
    print(f"  Session over: {res.stop_reason}  | inventory: {dict(g.inventory.items)}  | left in the Pit: {g.pit_lost}")

    print("\n== 6b. SCOUTING floors 1-3: the Reserve must finish (100%) or it is lost ==")
    for s in g.slimes():
        s.state, s.hunt, s.grounded = "idle", None, False
        s.hp, s.needs.v["energy"], s.needs.v["food"] = s.max_hp, 100, 100
    g.wallet.add("food", 40)
    plan = g.scout_plan(2, 1, 3)
    print(f"  estimate ~{plan['nominal']}h (between {plan['low']} and {plan['high']}), safe budget {plan['safe']}h, food {plan['food']}")
    g.conflicts.conflicts.clear()
    for s in g.slimes():
        s.grounded = False
    sc = g.scout(2, 1, 3, plan["safe"])
    print("\n".join("  " + x for x in sc.log[:5]))
    for r in g.intel_report(1, 3)[:3]:
        print(f"   floor {r['floor']} ({r['knowledge']:.0f}%): " + " | ".join(r['lines'][:3]))

    print("\n== 6c. THE HOLLOW DESCENT: floors in order, exit only after a boss; progress is per slime ==")
    for s in g.slimes():
        s.state, s.hunt, s.grounded = "idle", None, False
        s.hp, s.needs.v["energy"], s.needs.v["food"] = s.max_hp, 100, 100
    g.conflicts.conflicts.clear()
    print("  " + g.enter_dungeon(1))
    for _ in range(14):
        if 1 not in g.delves:
            break
        if g.can_leave(1) and g.delves[1]["floor"] > 1:
            print("  " + g.leave_dungeon(1))
            break
        if any(s.hp < s.max_hp * 0.5 for s in g._members_in("main", 1)):
            out = g.delve_camp(1, 8)
            print("  camped 8h" + (": " + "; ".join(out[:2]) if out else ""))
        rep = g.descend(1)
        extra = [l for l in rep.log if any(w in l for w in ("fallen", "lost", "carries", "found", "checkpoint",
                                                           "bounty", "died"))]
        print(f"  {rep.log[0]} -> {'WON' if rep.victory else 'LOST' if rep.winner == 'foes' else 'draw'}")
        print("\n".join("      " + x for x in extra[:5]))
    print("  Progress of the survivors: " + ", ".join(f"{s.name} floor {s.progress}" for s in g.party_members(1)))
    print(f"  This party may start again from floors {g.entry_options(1)}; a fresh slime could not join a floor-6 run.")
    for s in g.slimes():          # (demo housekeeping so later steps are not blocked)
        s.in_dungeon = ""
    g.delves.clear()

    print("\n== 7. COUNCIL: who to keep, who to sacrifice? Then MERGE the best suggestion ==")
    data = g.council()
    for r in data["rows"][:3] + data["rows"][-2:]:
        s = r["slime"]
        print(f"  {r['verdict']:<11} {r['score']:>5} {s.name:<9} {s.star_str()} compat avg {r['avg_compat']:+d} "
              f"({', '.join(r['reasons']) or '-'})")
    m = data["merges"][0]
    print(f"  merging {m['donor'].name} into {m['target'].name} (+{m['xp']} XP, compat {m['compat']:+d}, "
          f"colony morale cost {m['grief']})")
    print("\n".join("  " + x for x in g.merge(m["target"].id, m["donor"].id)))
    if len(g.slimes()) > 3:
        m2 = g.council()["merges"][0]
        print(f"  ...and a SECOND sacrifice right away (stress {g.sacrifice_stress:.1f}): colony morale cost now "
              f"{m2['grief']}")
        print("\n".join("  " + x for x in g.merge(m2["target"].id, m2["donor"].id)[-2:]))

    print("\n== 8. NEGLECT: the food runs out and nobody is fed for 6 days... ==")
    g.wallet.spend("food", g.wallet.get("food"))
    show_events([e for e in g.tick(144) if "died" in e][:10])

    print("\n== 9. MEMORIAL POND ==")
    show_graveyard(g)
    show_roster(g)
    show_status(g)
