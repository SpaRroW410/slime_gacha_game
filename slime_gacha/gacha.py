"""GachaSystem: rarity + star rolls, daily free pull, white/purple gel payment. Offline, RNG injected.

Rarity weights come from config.RARITY_RATES (90 / 9 / 0.9 / 0.09 %). Paying with PURPLE gel multiplies the
non-common weights by config.PURPLE_RARITY_BOOST. Stars (1-5) follow an exponential falloff whose steepness
grows with rarity (config.STAR_DECAY), so a 5-star legendary is astronomically rare.
"""
import math
import random
from typing import List

from . import config
from .ai import TRAITS
from .archetypes import STAT_KEYS, all_archetypes
from .errors import InvalidAction
from .resources import ResourceManager
from .slime import Slime

_SYL_A = ["blo", "gloo", "sqi", "wob", "plu", "jel", "mo", "slu", "bi", "zi", "fli", "gur", "pi", "dro"]
_SYL_B = ["p", "b", "mp", "z", "x", "bo", "ggle", "ssy", "nk", "rp", "ppy", "ndle", "bble", "t"]
PAY_METHODS = ("free", "white_gel", "purple_gel")


class GachaSystem:
    def __init__(self, wallet: ResourceManager, rng: random.Random):
        self.wallet = wallet
        self.rng = rng
        self.since_epic = 0
        self.since_legendary = 0
        self.total_pulls = 0
        self.next_id = 1
        self.last_free_day = -1          # game day of the last free pull
        self.luck = 1.0                  # Keeper skill: multiplies the non-common weights
        self.favor = False               # Keeper active: the next pull has double rare odds

    # ---- probabilities (pure functions, handy for tests/UI) --------------------
    @staticmethod
    def rarity_weights(purple: bool = False) -> dict:
        return {r: config.RARITY_RATES[r] * (config.PURPLE_RARITY_BOOST if purple and r != "common" else 1.0)
                for r in config.RARITIES}

    @staticmethod
    def star_probabilities(rarity: str) -> List[float]:
        lam = config.STAR_DECAY[rarity]
        w = [math.exp(-lam * k) for k in range(config.MAX_STARS)]
        total = sum(w)
        return [x / total for x in w]

    # ---- rolls ---------------------------------------------------------------
    def roll_rarity(self, purple: bool = False) -> str:
        # optional pity (disabled by default, see config)
        if config.PITY_LEGENDARY and self.since_legendary + 1 >= config.PITY_LEGENDARY:
            return "legendary"
        if config.PITY_EPIC and self.since_epic + 1 >= config.PITY_EPIC:
            return self.rng.choices(["epic", "legendary"],
                                    [config.RARITY_RATES["epic"], config.RARITY_RATES["legendary"]])[0]
        w = self.rarity_weights(purple)
        boost = self.luck * (2.0 if self.favor else 1.0)
        w = {r: v * (boost if r != "common" else 1.0) for r, v in w.items()}
        return self.rng.choices(config.RARITIES, [w[r] for r in config.RARITIES])[0]

    def roll_stars(self, rarity: str) -> int:
        return self.rng.choices(range(1, config.MAX_STARS + 1), self.star_probabilities(rarity))[0]

    def make_slime(self, rarity: str, archetype_key: str = None, stars: int = None) -> Slime:
        if archetype_key is None:
            pool = all_archetypes()
            arch = self.rng.choices(pool, [a.pull_weight for a in pool])[0]
        else:
            arch = next(a for a in all_archetypes() if a.key == archetype_key)
        var = {k: round(1 + self.rng.uniform(-config.VARIANCE, config.VARIANCE), 3) for k in STAT_KEYS}
        traits = self.rng.sample(sorted(TRAITS), 2)
        if stars is None:
            stars = self.roll_stars(rarity)
            if arch.key in config.SCHOLAR_CLASSES:       # the magic classes are scholars: never pulled below 3 stars
                stars = max(stars, config.SCHOLAR_MIN_STARS)
        s = Slime(self.next_id, self._name(), arch.key, rarity, var, traits, stars)
        self.next_id += 1
        return s

    def _name(self) -> str:
        return (self.rng.choice(_SYL_A) + self.rng.choice(_SYL_B)).capitalize()

    # ---- daily free pull -----------------------------------------------------------
    def free_available(self, day: int) -> bool:
        return day > self.last_free_day

    # ---- public --------------------------------------------------------------
    def pull(self, n: int = 1, pay: str = "white_gel", day: int = 0) -> List[Slime]:
        """pay: 'free' (once per game day, n must be 1), 'white_gel' or 'purple_gel' (PULL_COST each)."""
        if pay not in PAY_METHODS:
            raise InvalidAction(f"Pay with one of: {', '.join(PAY_METHODS)}.")
        if n < 1:
            raise InvalidAction("Pull at least one.")
        if pay == "free":
            if n != 1:
                raise InvalidAction("The daily free pull is a single pull.")
            if not self.free_available(day):
                raise InvalidAction("You already used today's free pull.")
            self.last_free_day = day
        else:
            self.wallet.spend(pay, config.PULL_COST * n)
        out = []
        for _ in range(n):
            r = self.roll_rarity(purple=(pay == "purple_gel"))
            self.total_pulls += 1
            self.since_epic = 0 if r in ("epic", "legendary") else self.since_epic + 1
            self.since_legendary = 0 if r == "legendary" else self.since_legendary + 1
            out.append(self.make_slime(r))
        return out

    def to_dict(self):
        return dict(since_epic=self.since_epic, since_legendary=self.since_legendary,
                    total_pulls=self.total_pulls, next_id=self.next_id,
                    last_free_day=self.last_free_day)

    def load(self, d):
        self.since_epic = d.get("since_epic", 0)
        self.since_legendary = d.get("since_legendary", 0)
        self.total_pulls = d.get("total_pulls", 0)
        self.next_id = d.get("next_id", 1)
        self.last_free_day = d.get("last_free_day", -1)
