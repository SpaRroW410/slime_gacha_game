"""Text UI. Contains NO game rules - it only calls Game methods and prints results."""
import os
from typing import List

from . import config, elements
from .abilities import ABILITIES, get_ability
from .academy import DISCIPLINES
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
 [t] Training grounds   [l] Library & spell lab (elements, fusion)
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
          f"main dungeon: floor {g.main_floor} cleared | free pull: {free} | auto-care: {'on' if g.needs.auto_care else 'off'} | "
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


def show_elements(s) -> None:
    if s.training:
        print("  trained: " + ", ".join(f"+{v} {k}" for k, v in s.training.items()))
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


def training_menu(g: Game) -> None:
    for i, d in enumerate(DISCIPLINES.all(), 1):
        print(f"  [{i}] {d.emoji} {d.name} ({d.key}) trains {', '.join(d.weights)} - {d.description}")
    print(f"  Cost {config.TRAIN_COST} per session, {config.TRAIN_TICKS}h. Your class's own discipline is "
          f"x{config.TRAIN_AFFINITY_MULT} as effective. Gains are permanent but capped by level.")
    d = DISCIPLINES.all()[_int("discipline #: ") - 1].key
    who = _ask("train a [s]lime or a whole [p]arty: ").lower()[:1]
    if who == "p":
        show_parties(g)
        print("\n".join("  " + x for x in g.train_party(_int("party #: "), d)))
    else:
        show_roster(g)
        print("  " + g.train(_int("slime id: "), d))


def _pick_spell(s, prompt: str) -> str:
    for i, k in enumerate(s.spells, 1):
        print(f"    [{i}] {get_ability(k).name}")
    return s.spells[_int(prompt) - 1]


def library_menu(g: Game) -> None:
    print("  [1] Spell catalogue   [2] Study an element   [3] Learn a spell   [4] Forget a spell\n"
          "  [5] SPELL LAB: fuse two spells into a new element   [6] Element recipes   [7] Elemental sheet")
    c = _ask("library: ")
    if c == "1":
        show_catalog(g)
    elif c == "6":
        show_recipes()
    elif c in ("2", "3", "4", "5", "7"):
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
        print(f"  Party #{p.id} '{p.name}' [{len(p.members)}/{g.parties.size}]: {names}")


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


def dungeon_menu(g: Game) -> None:
    print("  [1] The Gloop Pit  - safe grinding dungeon: nobody dies, great XP, little loot")
    print(f"  [2] The Hollow Descent - ROUGH main dungeon (next: floor {g.main_floor + 1}), permadeath, "
          f"boss every {config.MAIN_BOSS_EVERY} floors, rare purple gel")
    print("  [3] Skirmish - a single quick fight vs a tier 1-4 wave (permadeath)")
    mode = _ask("dungeon: ")
    pid = _int("party # to send: ")
    if mode == "1":
        depth = _int(f"depth 1-{config.GRIND_DEPTHS} (3 = your level): ")
        runs = _int("number of runs: ")
        rest = _ask("auto-rest between runs when hurt? (y/n): ").lower() == "y"
        res = g.grind(pid, depth, runs, rest)
        print("\n".join("  " + x for x in res.summary))
        print(f"  Stopped: {res.stop_reason}")
    elif mode == "2":
        fl = _ask(f"floor (Enter = {g.main_floor + 1}): ")
        print("\n".join(g.descend(pid, int(fl) if fl else None).log))
    elif mode == "3":
        print("\n".join(g.battle(pid, _int("tier 1-3 (4 = boss): ")).log))


def party_menu(g: Game) -> None:
    show_parties(g)
    act = _ask("[n]ew / [a]dd slime / [r]emove slime / [f]ill with best free / [d]isband / [z] rest party: ").lower()[:1]
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
        training_menu(g)
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

    print("\n== 4b. TRAINING GROUNDS & LIBRARY (the demo hires a 3-star scholar: ANY class can master elements) ==")
    sch = g.gacha.make_slime("rare", "barbarian", stars=3)
    g.roster[sch.id] = sch
    g.wallet.add("white_gel", 400)
    g.wallet.add("essence", 60)
    print("  " + g.train(sch.id, "sword"))
    show_events([e for e in g.tick(4) if "Blade" in e])
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

    print("\n== 5. CONFLICT: let the colony simmer for 24h ==")
    ev = g.tick(24)
    show_events([e for e in ev if "Conflict" in e or "brawl" in e or "died" in e][:8])
    for c in list(g.conflicts.conflicts)[:2]:
        print("  " + g.mediate(c.id, "talk"))

    print("\n== 6. GRINDING DUNGEON: the Vanguard farms the Gloop Pit (nobody can die here) ==")
    g.conflicts.conflicts.clear()   # keep the demo grind uninterrupted by brawls
    g.wallet.add("food", 30)
    for s in g.slimes():          # top everyone up so the demo starts healthy
        s.state, s.hunt, s.grounded = "idle", None, False
        s.hp, s.needs.v["energy"], s.needs.v["food"] = s.max_hp, 100, 100
    res = g.grind(1, 3, 6, auto_rest=True)
    print("\n".join("  " + x for x in res.summary[:14]))
    print(f"  Stopped: {res.stop_reason}")

    print("\n== 6b. MAIN DUNGEON: the Hollow Descent, floor 1 (rough! casualties are permanent) ==")
    for s in g.slimes():
        s.state, s.hunt, s.grounded = "idle", None, False
        s.hp, s.needs.v["energy"], s.needs.v["food"] = s.max_hp, 100, 100
    rep = g.descend(1)
    print("\n".join(rep.log[-14:]))

    print("\n== 7. MERGE: weakest into strongest ==")
    ordered = sorted(g.slimes(), key=lambda s: s.power_rating())
    weak, strong = ordered[0], ordered[-1]
    print(f"  merging {weak.name} into {strong.name} (preview +{g.merge_preview(strong.id, weak.id)} XP)")
    print("\n".join("  " + x for x in g.merge(strong.id, weak.id)))

    print("\n== 8. NEGLECT: the food runs out and nobody is fed for 6 days... ==")
    g.wallet.spend("food", g.wallet.get("food"))
    show_events([e for e in g.tick(144) if "died" in e][:10])

    print("\n== 9. MEMORIAL POND ==")
    show_graveyard(g)
    show_roster(g)
    show_status(g)
