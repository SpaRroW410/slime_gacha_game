"""ResourceManager: the player's wallet (gel / food / essence / anything in config.RESOURCES)."""
from typing import Dict

from . import config
from .errors import NotEnoughResources


class ResourceManager:
    def __init__(self, initial: Dict[str, int] = None):
        self._r = {k: 0 for k in config.RESOURCES}
        for k, v in (initial or {}).items():
            self._r[k] = int(v)

    def get(self, name: str) -> int:
        return self._r.get(name, 0)

    def add(self, name: str, amount: int) -> None:
        self._r[name] = self.get(name) + int(amount)

    def add_many(self, bundle: Dict[str, int]) -> None:
        for k, v in bundle.items():
            self.add(k, v)

    def can_afford(self, cost: Dict[str, int]) -> bool:
        return all(self.get(k) >= v for k, v in cost.items())

    def spend(self, name: str, amount: int) -> None:
        self.spend_many({name: amount})

    def spend_many(self, cost: Dict[str, int]) -> None:
        """Atomic: either everything is paid or nothing changes."""
        if not self.can_afford(cost):
            lack = {k: v - self.get(k) for k, v in cost.items() if self.get(k) < v}
            raise NotEnoughResources("Not enough resources, missing: " +
                                     ", ".join(f"{v} {k}" for k, v in lack.items()))
        for k, v in cost.items():
            self._r[k] -= int(v)

    def to_dict(self) -> Dict[str, int]:
        return dict(self._r)

    def __str__(self) -> str:
        icons = {"gel": "💧", "food": "🍖", "essence": "✨"}
        return "  ".join(f"{icons.get(k, k)} {k}: {v}" for k, v in self._r.items())
