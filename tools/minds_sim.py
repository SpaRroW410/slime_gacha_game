#!/usr/bin/env python3
"""Minds harness: how do slimes feel, fight, bond and grieve when a colony is left to live for weeks? Seeded and offline.

    python3 tools/minds_sim.py                    # markdown report to stdout (a few minutes)
    python3 tools/minds_sim.py --days 20 --slimes 12 --seeds 1
    python3 tools/minds_sim.py --check            # exit 1 if a behaviour target is missed (regression guard)

Scenarios:
  colony     N slimes for D days, hands-off (auto-care only) or with an attentive Keeper (talks to and pets everyone once a
             day, mediates open quarrels a few times a day).
  legendary  a 5-star legendary in four lives: loved at home, a cog at a work post, alone, and working while loved.
  recovery   a legendary that awoke in despair, then cared for every day.
  grief      a slime whose partner dies, hour by hour.
The targets in TARGETS describe how people behave in the same situations (see docs/MINDS.md); tests/test_minds.py runs a
small version of them.
"""
import argparse
import collections
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slime_gacha import awakening, emotions, jobs, relationships, sanity  # noqa: E402
from slime_gacha.game import Game  # noqa: E402
from slime_gacha.registry import load_plugins  # noqa: E402

BRAWL = re.compile(r"💥 (.+?) and (.+?) brawl")
EVENTS = collections.OrderedDict([
    ("quarrel", r"Conflict #"), ("brawl", r"💥"), ("made_up", r"make up|patch things up|apologi|helps .+ make peace"),
    ("cold_war", r"stop speaking"), ("friends", r"have become friends"), ("best_friends", r"are best friends"),
    ("rivals", r"become rivals"), ("cuddle", r"cuddle"), ("death", r"has died"),
])


def colony(seed: int, n: int = 20) -> Game:
    load_plugins()
    g = Game(seed)
    g.forage = True
    g.wallet.add_many({"white_gel": 100000, "food": 100000})
    while len(g.roster) < n:
        g.pull(min(10, n - len(g.roster)))
    return g


def attentive(g: Game) -> None:
    """The Keeper's day: one talk and one pet for everyone (at 9:00); open quarrels mediated every 6 hours."""
    hour = g.tick_count % 24
    if hour == 9:
        for s in g.slimes():
            for act in (g.talk, g.pet):
                try:
                    act(s.id)
                except Exception:
                    pass
    if hour % 6 == 0:
        for c in list(g.conflicts.conflicts):
            try:
                g.mediate(c.id, "talk")
            except Exception:
                pass


def run_colony(seed: int = 1, n: int = 20, days: int = 45, keeper: bool = False) -> dict:
    g = colony(seed, n)
    counts = collections.Counter()
    strong = collections.Counter()           # slime-hours a feeling is at 30 or more
    top = collections.Counter()              # slime-hours a feeling is the strongest
    brawls = collections.Counter()           # per pair of names
    hours = calm_hours = 0
    moods = []
    for _ in range(days * 24):
        if keeper:
            attentive(g)
        for e in g.tick(1):
            for k, p in EVENTS.items():
                if re.search(p, e):
                    counts[k] += 1
            m = BRAWL.search(e)
            if m:
                brawls[frozenset(m.groups())] += 1
        for s in g.slimes():
            hours += 1
            d = emotions.dominant(s, 1)
            if d and d[0][1] >= 30:
                top[d[0][0]] += 1
            else:
                calm_hours += 1
            for k, v in s.emotions.items():
                if v >= 30:
                    strong[k] += 1
        if g.tick_count % 24 == 0:
            moods.extend(s.mood() for s in g.slimes())
    rel = collections.Counter(r["kind"] for r in g.relations.rel.values())
    goals = collections.Counter(s.goal["kind"] for s in g.slimes() if s.goal)
    alive = len(g.roster) or 1
    return dict(
        events=dict(counts), alive=len(g.roster), dead=len(g.graveyard),
        strong={k: v / hours for k, v in strong.items()}, top={k: v / hours for k, v in top.items()},
        no_strong=calm_hours / hours, mood=statistics.mean(moods) if moods else 0.0,
        sanity=statistics.mean(sanity.frac(s) for s in g.slimes()) if g.roster else 0.0,
        relations=dict(rel), goals=dict(goals), rival_goals=goals.get("rival", 0) / alive,
        max_brawls_per_feud=max(brawls.values(), default=0),
        memories=statistics.mean(len(s.memories) for s in g.slimes()) if g.roster else 0.0,
        cuddles_per_day=counts["cuddle"] / days)


# ---- the legendary ------------------------------------------------------------------------------------------------
def legend_colony(seed: int, others: int = 6):
    g = colony(seed, 0)
    g.forage = False
    s = g.gacha.make_slime("legendary", "barbarian", stars=5)
    s.traits = ["lazy", "gluttonous"]                      # no kind / brave shortcut to a good outcome
    g.roster[s.id] = s
    for _ in range(others):
        o = g.gacha.make_slime("common")
        g.roster[o.id] = o
    return g, s


def _care(g: Game, ids) -> None:
    for i in ids:
        for act in (g.talk, g.pet):
            try:
                act(i)
            except Exception:
                pass


def _post(g: Game, s) -> None:
    if not s.job:
        for k in jobs.JOBS:
            try:
                g.assign_job(s.id, k)
                return
            except Exception:
                continue


LIVES = {
    "loved": "at home, talked to and petted every day, quarrels mediated",
    "cog": "always at a work post, needs met by auto-care, nobody talks to it",
    "alone": "the only slime, needs met, no attention",
    "loved_worker": "works every day and is talked to and petted every day",
}


def run_legend(seed: int = 3, life: str = "loved", days: int = 24) -> dict:
    g, s = legend_colony(seed, 0 if life == "alone" else 6)
    for _ in range(days):
        for h in range(24):
            if life in ("cog", "loved_worker"):
                _post(g, s)
            if h == 9 and life in ("loved", "loved_worker"):
                _care(g, [o.id for o in g.slimes()])
            if h % 6 == 0 and life in ("loved", "loved_worker"):
                for c in list(g.conflicts.conflicts):
                    try:
                        g.mediate(c.id, "snack")
                    except Exception:
                        pass
            g.tick(1)
    return dict(stage=awakening.stage(s), outcome=s.temperament, feelings=dict(emotions.dominant(s, 3)),
                belonging=round(s.needs.get("belonging")), mood=round(s.mood(), 2), alive=s.id in g.roster)


def run_recovery(seed: int = 4, days: int = 30) -> dict:
    """A legendary that awoke alone and in despair; then the Keeper cares for it (and it gets company) every day."""
    g, s = legend_colony(seed, 6)
    s.awareness = awakening.THRESHOLDS[-1] - 0.1
    s.needs.set("belonging", 5)
    s.life = awakening.fresh_life() if hasattr(awakening, "fresh_life") else getattr(s, "life", None)
    if hasattr(awakening, "seed_record"):
        awakening.seed_record(s, care=0.0, connection=0.0, purpose=0.0, hardship=1.0)
    g.tick(1)
    start = s.temperament
    for d in range(days):
        for h in range(24):
            if h == 9:
                _care(g, [o.id for o in g.slimes()])
            g.tick(1)
        if s.temperament not in ("despair", ""):
            return dict(start=start, recovered_on=d + 1, outcome=s.temperament)
    return dict(start=start, recovered_on=None, outcome=s.temperament)


def run_grief(seed: int = 5) -> dict:
    """Partner dies: how long until sadness drops below 10, and what sanity does meanwhile."""
    g = colony(seed, 0)
    a = g.gacha.make_slime("common", "barbarian")
    b = g.gacha.make_slime("common", "mage")
    c = g.gacha.make_slime("common", "rogue")
    for s in (a, b, c):
        s.traits = []
        g.roster[s.id] = s
    g.relations.rel[relationships.key(a, b)] = dict(kind="couple", since=0)
    g.social.add_bond(a, b, 60)
    b.hp, b.death_cause = 0, "an accident"
    g.tick(1)
    track = {}
    for h in range(1, 24 * 40 + 1):
        g.tick(1)
        if h in (24, 72, 24 * 7, 24 * 14):
            track[h] = round(emotions.level(a, "sadness"), 1)
        if emotions.level(a, "sadness") < 10 and "over_at" not in track:
            track["over_at"] = h
            break
    return dict(sadness_at=track, grief_days=round(track.get("over_at", 24 * 40) / 24, 1))


# ---- targets ------------------------------------------------------------------------------------------------------
TARGETS = [
    # (name, scenario key, function(result) -> bool, what a person would do)
    ("feuds cool off", "hands_off", lambda r: r["max_brawls_per_feud"] <= 2,
     "a feud blows up once or twice, then people avoid each other or make up"),
    ("anger is an episode", "hands_off", lambda r: r["strong"].get("anger", 0) <= 0.20,
     "anger at 30+ for at most a fifth of the time, even with nobody stepping in"),
    ("sadness is an episode", "hands_off", lambda r: r["strong"].get("sadness", 0) <= 0.20,
     "sadness at 30+ for at most a fifth of the time"),
    ("good days happen", "attentive", lambda r: r["strong"].get("joy", 0) + r["strong"].get("calm", 0) + r["strong"].get("affection", 0) >= 0.10,
     "a cared-for colony feels joy, calm or affection at 30+ at least a tenth of the time"),
    ("care builds bonds", "attentive", lambda r: r["relations"].get("rival", 0) <= r["relations"].get("friend", 0) + r["relations"].get("best_friend", 0),
     "an attentive Keeper's colony has more friends than rivals"),
    ("ordinary goals", "hands_off", lambda r: r["rival_goals"] <= 0.40, "most slimes want something other than revenge"),
    ("loved legendary is fine", "legend_loved", lambda r: r["outcome"] in ("settled", "peace"),
     "a loved slime absorbs the truth about its world and carries on"),
    ("lonely legendary despairs", "legend_alone", lambda r: r["outcome"] == "despair", "isolation is what breaks people"),
    ("unloved worker is a cog", "legend_cog", lambda r: r["outcome"] in ("cog", "despair"),
     "fed and busy but unseen: flat, going through the motions"),
    ("despair can lift", "recovery", lambda r: r["recovered_on"] is not None, "company and care pull people back out"),
]


def run_all(seeds=(1,), slimes: int = 20, days: int = 45) -> dict:
    out = collections.defaultdict(list)
    for sd in seeds:
        out["hands_off"].append(run_colony(sd, slimes, days, keeper=False))
        out["attentive"].append(run_colony(sd, slimes, days, keeper=True))
        for life in LIVES:
            out["legend_" + life].append(run_legend(sd + 2, life))
        out["recovery"].append(run_recovery(sd + 3))
        out["grief"].append(run_grief(sd + 4))
    return out


def check(results: dict) -> list:
    """[(target name, passed share, explanation)] over every seed."""
    rows = []
    for name, key, fn, why in TARGETS:
        rs = results.get(key) or []
        if rs:
            rows.append((name, sum(1 for r in rs if fn(r)) / len(rs), why))
    return rows


def report(results: dict) -> str:
    def pct(x):
        return f"{100 * x:.0f}%"
    lines = ["# Slime minds report", ""]
    for key in ("hands_off", "attentive"):
        for i, r in enumerate(results[key]):
            lines += [f"## Colony, {key.replace('_', '-')} (seed {i + 1})", "",
                      f"- events: {r['events']}",
                      f"- feeling at 30+: " + ", ".join(f"{k} {pct(v)}" for k, v in sorted(r['strong'].items(), key=lambda kv: -kv[1])),
                      f"- no strong feeling: {pct(r['no_strong'])} · mood {r['mood']:.2f} · sanity {r['sanity']:.2f}",
                      f"- relationships: {r['relations']} · goals: {r['goals']} · most brawls in one feud: {r['max_brawls_per_feud']}",
                      f"- memories per slime: {r['memories']:.1f} · cuddle lines per day: {r['cuddles_per_day']:.0f}", ""]
    lines += ["## The legendary", ""]
    for life, text in LIVES.items():
        for r in results["legend_" + life]:
            lines.append(f"- **{life}** ({text}): outcome `{r['outcome'] or '-'}`, feelings {r['feelings']}, mood {r['mood']}")
    lines += ["", "## Recovery and grief", ""]
    for r in results["recovery"]:
        lines.append(f"- recovery: started `{r['start']}`, outcome `{r['outcome']}`, lifted on day {r['recovered_on']}")
    for r in results["grief"]:
        lines.append(f"- grief: sadness {r['sadness_at']} (hours after) - over after {r['grief_days']} days")
    lines += ["", "## Targets", "", "| Target | Passed | What a person would do |", "|---|---|---|"]
    for name, share, why in check(results):
        lines.append(f"| {name} | {pct(share)} | {why} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Slime minds harness")
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--slimes", type=int, default=20)
    ap.add_argument("--days", type=int, default=45)
    ap.add_argument("--check", action="store_true", help="exit 1 if a target fails on any seed")
    ap.add_argument("--out", help="write the report here instead of stdout")
    a = ap.parse_args()
    res = run_all(range(1, a.seeds + 1), a.slimes, a.days)
    text = report(res)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)
    if a.check:
        bad = [n for n, share, _ in check(res) if share < 1.0]
        if bad:
            print("FAILED: " + ", ".join(bad), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
