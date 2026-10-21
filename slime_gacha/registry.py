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


PLUGIN_ERRORS: Dict[str, str] = {}        # plugin name -> why it was skipped


def load_plugins() -> List[str]:
    """Import every module in slime_gacha/plugins so it can self-register content (docs/MODDING.md).
    A module with a `register()` function gets it called (unless `ENABLED = False`); one without registers at import time.
    A module with `ENABLED = False` is skipped; one that raises is skipped too (and noted in PLUGIN_ERRORS) so a broken
    mod never stops the game from starting."""
    from . import plugins
    loaded = []
    for mod in pkgutil.iter_modules(plugins.__path__):
        name = f"{plugins.__name__}.{mod.name}"
        try:
            m = importlib.import_module(name)
            if getattr(m, "ENABLED", True):
                if callable(getattr(m, "register", None)):
                    m.register()
                loaded.append(mod.name)
        except Exception as e:                      # noqa: BLE001 - any failure in a mod is that mod's problem
            PLUGIN_ERRORS[mod.name] = f"{type(e).__name__}: {e}"
    return loaded
