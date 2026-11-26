"""The playtest recorder: an opt-in log of every fight (and a few trip events) kept in the save, to export and share.

Off by default. Each fight adds one compact entry (~0.5-2 KB, more for bigger parties): where, the party (class, rarity, stars, level, gear and relics),
by hand or automatic, the result, rounds, deaths, and HP / stamina / mana left. The log is capped at config.PLAYLOG_MAX_KB
(the oldest entries drop off) so a forgotten recorder cannot fill the browser's save space.
"""
import json
from typing import Dict, List, Optional

from . import config
from .equipment import GEAR

VERSION = 1


def _pct(v: float, m: float) -> int:
    return int(round(100 * v / m)) if m else 0


def slime_line(s, c=None) -> dict:
    """One party member: who it is, what it wears, and (after a fight) what is left of it."""
    gear = [GEAR.get(k).tier for k in s.gear.values() if k in GEAR.keys()] if isinstance(s.gear, dict) else []
    relics = [f"{it.rarity[0].upper()}{it.stars}*L{it.level}{'E' if it.ego else ''}" for it in s.items.values()]
    out = dict(n=s.name, c=s.archetype, r=s.rarity, st=s.stars, lv=s.level, g=gear, rl=relics)
    if c is not None:
        out.update(hp=_pct(max(0, c.hp), c.max_hp), sta=_pct(c.stamina, c.stamina_max), mp=_pct(c.mana, c.mana_max),
                   ok=bool(c.alive))
    return out


def fight_entry(game, party, run, ctx: Optional[dict]) -> dict:
    rep = run.report
    foes: Dict[str, int] = {}
    for c in run.everyone:
        if c.side == "foes" and not c.minion:
            base = c.source.name if c.source is not None and hasattr(c.source, "name") else c.name
            foes[base] = foes.get(base, 0) + 1
    e = dict(t="fight", day=game.day, tick=game.tick_count, **(ctx or {}),
             man=bool(run.manual), res={"party": "win", "foes": "loss"}.get(rep.winner, "draw"), rd=rep.rounds,
             foes=foes, xp=rep.xp, dead=list(rep.deaths), ko=list(rep.knocked_out),
             party=[slime_line(s, c) for s, c in zip(run.party, run.mine)])
    if run.terrain is not None:
        e["ter"] = run.terrain.name
    return e


def event_entry(game, kind: str, **data) -> dict:
    return dict(t=kind, day=game.day, tick=game.tick_count, **data)


def _bytes(x) -> int:
    return len(json.dumps(x, separators=(",", ":")))


def add(game, entry: dict) -> None:
    if not game.playlog_on:
        return
    total = getattr(game, "_plog_bytes", None)
    if total is None:                                    # first entry since the game was loaded: measure what is there
        total = sum(_bytes(e) + 1 for e in game.playlog) + 1      # + the commas and brackets of the list
    game.playlog.append(entry)
    total += _bytes(entry) + 1
    while total > config.PLAYLOG_MAX_KB * 1024 and len(game.playlog) > 1:
        total -= _bytes(game.playlog.pop(0)) + 1         # the oldest entries drop off
    game._plog_bytes = total


def size_kb(game) -> float:
    if not game.playlog:
        return 0.0
    return max(0.1, round(_bytes(game.playlog) / 1024, 1))


def export(game) -> dict:
    """The file a player shares: a header (game version, seed, when) and the entries."""
    fights = [e for e in game.playlog if e.get("t") == "fight"]
    return dict(kind="slime-gacha-playtest-log", format=VERSION, version=config.VERSION, seed=game.seed,
                dungeon_seed=game.dungeon_seed, day=game.day, best_floor=game.best_floor,
                fights=len(fights), wins=sum(e.get("res") == "win" for e in fights),
                entries=list(game.playlog))
