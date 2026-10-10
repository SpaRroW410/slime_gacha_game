"""GachaSystem: rarity roll, pity counters, slime generation. Fully offline, RNG injected."""
import random
from typing import List

from . import config
from .archetypes import STAT_KEYS, all_archetypes
from .ai import TRAITS
from .resources import ResourceManager
from .slime import Slime

_SYL_A = ["blo", "gloo", "sqi", "wob", "plu", "jel", "mo", "slu", "bi", "zi", "fli", "gur", "pi", "dro"]
_SYL_B = ["p", "b", "mp", "z", "x", "bo", "ggle", "ssy", "nk", "rp", "ppy", "ndle", "bble", "t"]


class GachaSystem:
    def __init__(self, wallet: ResourceManager, rng: random.Random):
        self.wallet = wallet
        self.rng = rng
        self.since_epic = 0
        self.since_legendary = 0
        self.total_pulls = 0
        self.next_id = 1

    # ---- rolls ---------------------------------------------------------------
    def roll_rarity(self) -> str:
        # pity first (legendary beats epic)
        if self.since_legendary + 1 >= config.PITY_LEGENDARY:
            return "legendary"
        if self.since_epic + 1 >= config.PITY_EPIC:
            return self.rng.choices(["epic", "legendary"],
                                    [config.RARITY_RATES["epic"], config.RARITY_RATES["legendary"]])[0]
        names = config.RARITIES
        return self.rng.choices(names, [config.RARITY_RATES[r] for r in names])[0]

    def make_slime(self, rarity: str, archetype_key: str = None) -> Slime:
        if archetype_key is None:
            pool = all_archetypes()
            arch = self.rng.choices(pool, [a.pull_weight for a in pool])[0]
        else:
            arch = next(a for a in all_archetypes() if a.key == archetype_key)
        var = {k: round(1 + self.rng.uniform(-config.VARIANCE, config.VARIANCE), 3) for k in STAT_KEYS}
        traits = self.rng.sample(sorted(TRAITS), 2)
        s = Slime(self.next_id, self._name(), arch.key, rarity, var, traits)
        self.next_id += 1
        return s

    def _name(self) -> str:
        return (self.rng.choice(_SYL_A) + self.rng.choice(_SYL_B)).capitalize()

    # ---- public --------------------------------------------------------------
    def pull(self, n: int = 1) -> List[Slime]:
        cost = config.PULL10_COST if n == 10 else config.PULL_COST * n
        self.wallet.spend("gel", cost)
        out = []
        for _ in range(n):
            r = self.roll_rarity()
            self.total_pulls += 1
            self.since_epic = 0 if r in ("epic", "legendary") else self.since_epic + 1
            self.since_legendary = 0 if r == "legendary" else self.since_legendary + 1
            out.append(self.make_slime(r))
        return out

    def to_dict(self):
        return dict(since_epic=self.since_epic, since_legendary=self.since_legendary,
                    total_pulls=self.total_pulls, next_id=self.next_id)

    def load(self, d):
        self.since_epic = d.get("since_epic", 0)
        self.since_legendary = d.get("since_legendary", 0)
        self.total_pulls = d.get("total_pulls", 0)
        self.next_id = d.get("next_id", 1)
