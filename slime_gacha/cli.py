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
 [1] Roster          [2] Pull x1 (100 gel)   [3] Pull x10 (900 gel)
 [4] Slime details   [5] Feed / Sleep / Pet  [6] Set stance
 [7] Send to hunt    [8] Wait (advance time) [9] Battle
 [m] Merge slimes    [e] Evolve              [c] Conflicts / mediate
 [a] Toggle auto-care [j] Journal            [s] Save    [q] Quit
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
    print(f"\n⏰ Hour {g.tick_count} | {g.wallet} | slimes: {len(g.roster)} | "
          f"auto-care: {'on' if g.needs.auto_care else 'off'} | conflicts: {len(g.conflicts.conflicts)}")


def show_slime(s) -> None:
    st = s.max_stats()
    print(f"\n{s.arch.emoji} {s.name} - {s.title()} ({s.rarity}) Lv{s.level}/{s.level_cap}  "
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
        print(f"  {config.RARITY_COLOR[s.rarity]:<3} {s.rarity.upper():<9} {s.arch.emoji} {s.name} "
              f"the {s.arch.name}  (traits: {', '.join(s.traits)})")


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


def handle(g: Game, choice: str) -> bool:
    """Returns False to quit."""
    if choice == "1":
        show_roster(g)
    elif choice in ("2", "3"):
        show_pulls(g.pull(1 if choice == "2" else 10))
    elif choice == "4":
        show_roster(g)
        show_slime(g.slime(_int("slime id: ")))
    elif choice == "5":
        show_roster(g)
        sid = _int("slime id: ")
        act = _ask("[f]eed (1 food) / [s]leep / [w]ake / [p]et: ").lower()
        print("  " + {"f": g.feed, "s": g.sleep, "w": g.wake, "p": g.pet}.get(act, lambda _: "Unknown action.")(sid))
    elif choice == "6":
        show_roster(g)
        sid = _int("slime id: ")
        print("  " + g.set_behavior(sid, _ask(f"stance ({'/'.join(BEHAVIORS)}): ").lower()))
    elif choice == "7":
        show_roster(g)
        sid = _int("slime id (0 = recall everyone): ")
        if sid == 0:
            for s in g.slimes():
                g.recall(s.id)
            print("  Everyone is back.")
        else:
            print("  " + g.hunt(sid, pick_zone()))
    elif choice == "8":
        n = _int("hours to wait (1-48): ")
        show_events(g.tick(max(1, min(48, n))))
    elif choice == "9":
        show_roster(g)
        ids = [int(x) for x in _ask(f"party ids (up to {config.MAX_PARTY}, space-separated): ").split()]
        tier = _int("tier 1-3 (4 = boss): ")
        report = g.battle(ids, tier)
        print("\n".join(report.log))
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
    elif choice == "j":
        print("\n".join("  " + x for x in g.journal[-20:]) or "  (empty)")
    elif choice == "q":
        return False
    return True


def run_interactive(seed, save_path: str) -> None:
    print(BANNER)
    if os.path.exists(save_path) and _ask(f"Load {save_path}? (y/n): ").lower() == "y":
        g = Game.load(save_path)
    else:
        g = Game(seed)
        print("Welcome, Keeper. The Last Gacha Well hums. You have 1000 gel - make a wish!")
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
    """Non-interactive tour: pull, care, hunt, conflict, battle, merge, evolve."""
    g = Game(seed)
    print(BANNER)
    print("== 1. GACHA: ten-pull ==")
    show_pulls(g.pull(10))
    show_status(g)

    print("\n== 2. NEEDS & SLEEP: wait 12 hours (auto-care on) ==")
    show_events(g.tick(12)[:15])
    show_slime(g.slimes()[0])

    print("\n== 3. AUTO-HUNT: send three slimes to the Meadow, wait 4h ==")
    for s in g.slimes()[:3]:
        try:
            print("  " + g.hunt(s.id, "meadow"))
        except GameError as e:
            print("  ✋ " + str(e))
    show_events(g.tick(4))
    show_status(g)

    print("\n== 4. CONFLICT: let the colony simmer for 24h ==")
    ev = g.tick(24)
    show_events([e for e in ev if "Conflict" in e or "quarrel" in e or "brawl" in e or "make up" in e][:10])
    for c in list(g.conflicts.conflicts)[:2]:
        print("  " + g.mediate(c.id, "talk"))

    print("\n== 5. BATTLE: best three slimes vs tier-1 foes ==")
    g.wallet.add("food", 20)
    for s in g.slimes():          # top everyone up so the demo is healthy
        s.state, s.hunt, s.grounded = "idle", None, False
        s.hp, s.needs.v["energy"], s.needs.v["food"] = s.max_hp, 100, 100
    best = sorted(g.slimes(), key=lambda s: -s.power_rating())[:3]
    print("\n".join(g.battle([s.id for s in best], 1).log))

    print("\n== 6. MERGE: weakest slime into strongest ==")
    ordered = sorted(g.slimes(), key=lambda s: s.power_rating())
    weak, strong = ordered[0], ordered[-1]
    print(f"  merging {weak.name} into {strong.name} (preview +{g.merge_preview(strong.id, weak.id)} XP)")
    print("\n".join("  " + x for x in g.merge(strong.id, weak.id)))

    print("\n== 7. FINAL ROSTER ==")
    show_roster(g)
    show_status(g)
