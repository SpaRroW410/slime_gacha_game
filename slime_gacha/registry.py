"""A tiny generic registry used for every data-driven concept (archetypes, abilities, zones, ...).

Adding content = building a data object and calling `register`. Engines look things up by key
and never hard-code class names.
"""
import importlib
import pkgutil
from typing import Dict, Generic, Iterator, List, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str):
        self.kind = kind
        self._items: Dict[str, T] = {}

    def register(self, item: T, key: str) -> T:
        self._items[key] = item
        return item

    def get(self, key: str) -> T:
        try:
            return self._items[key]
        except KeyError:
            raise KeyError(f"unknown {self.kind}: {key!r}") from None

    def __contains__(self, key: str) -> bool:
        return key in self._items

    def keys(self) -> List[str]:
        return list(self._items)

    def all(self) -> List[T]:
        return list(self._items.values())

    def __iter__(self) -> Iterator[T]:
        return iter(self._items.values())

    def unregister(self, key: str) -> None:
        self._items.pop(key, None)


def load_plugins() -> List[str]:
    """Import every module in slime_gacha/plugins so it can self-register content."""
    from . import plugins
    loaded = []
    for mod in pkgutil.iter_modules(plugins.__path__):
        importlib.import_module(f"{plugins.__name__}.{mod.name}")
        loaded.append(mod.name)
    return loaded
