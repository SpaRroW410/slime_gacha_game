"""Text UI. Contains NO game rules - it only calls Game methods and prints results."""
import os
from typing import List

from . import config
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
 [1] Roster           [2] Slime details      [3] Pull (free / silver / gold)
 [4] Care (feed/sleep/pet)   [5] Set stance  [6] Hunt (one slime or a party)
 [7] Wait (time)      [8] Parties            [9] Battle (full party)
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
          f"free pull: {free} | auto-care: {'on' if g.needs.auto_care else 'off'} | "
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
    print(f"  abilities: {', '.join(s.known_abilities())}")


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


def party_menu(g: Game) -> None:
    show_parties(g)
    act = _ask("[n]ew party / [a]dd slime / [r]emove slime / [f]ill with best free / [d]isband: ").lower()[:1]
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


def handle(g: Game, choice: str) -> bool:
    """Returns False to quit."""
    if choice == "1":
        show_roster(g)
    elif choice == "2":
        show_roster(g)
        show_slime(g.slime(_int("slime id: ")))
    elif choice == "3":
        pay = _ask("pay with [f]ree daily / [s]ilver / [g]old: ").lower()[:1]
        pay = {"f": "free", "s": "silver", "g": "gold"}.get(pay)
        if not pay:
            raise GameError("Choose f, s or g.")
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
        pid = _int("party # to send: ")
        tier = _int("tier 1-3 (4 = boss): ")
        print("\n".join(g.battle(pid, tier).log))
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
    print("== 1. GACHA: daily free pull, then a 10x silver pull, then 1 gold pull ==")
    show_pulls(g.pull(1, "free"))
    try:
        g.pull(1, "free")
    except GameError as e:
        print(f"  ✋ {e}")
    show_pulls(g.pull(10, "silver"))
    show_pulls(g.pull(1, "gold"))
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

    print("\n== 5. CONFLICT: let the colony simmer for 24h ==")
    ev = g.tick(24)
    show_events([e for e in ev if "Conflict" in e or "brawl" in e or "died" in e][:8])
    for c in list(g.conflicts.conflicts)[:2]:
        print("  " + g.mediate(c.id, "talk"))

    print("\n== 6. BATTLE: the Vanguard fights tier-1 foes (casualties are permanent) ==")
    g.wallet.add("food", 30)
    for s in g.slimes():          # top everyone up so the demo starts healthy
        s.state, s.hunt, s.grounded = "idle", None, False
        s.hp, s.needs.v["energy"], s.needs.v["food"] = s.max_hp, 100, 100
    rep = g.battle(1, 1)
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
